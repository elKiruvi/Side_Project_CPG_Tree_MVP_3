"""Provider-neutral request and response boundary for clinical interpretation."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class SemanticStage(StrEnum):
    """Auditable semantic passes in the LLM-first pipeline."""

    OBSERVATIONS = "OBSERVATIONS"
    RULES = "RULES"
    RELATIONS = "RELATIONS"
    RECONCILIATION = "RECONCILIATION"


@dataclass(frozen=True, slots=True)
class ClinicalLLMRequest:
    """One provider-neutral structured-output request."""

    request_id: str
    stage: SemanticStage
    prompt: str
    prompt_version: str
    schema_version: str
    response_schema: dict[str, object]
    input_span_ids: tuple[str, ...]
    input_hash: str
    temperature: float = 0.0
    reasoning_effort: str | None = None
    retry_feedback: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ClinicalLLMResponse:
    """Provider-neutral raw response plus diagnostic metadata."""

    content: str
    raw_response: str | None = None
    model_version: str | None = None
    usage: dict[str, int | float | str] = field(default_factory=dict)


class ProviderInvocationError(RuntimeError):
    """Provider failure that may retain a raw HTTP response for quarantine."""

    def __init__(self, message: str, raw_response: str | None = None) -> None:
        super().__init__(message)
        self.raw_response = raw_response


class ClinicalLLMProvider(Protocol):
    """Replaceable structured-output provider; no SDK types cross this boundary."""

    @property
    def provider_id(self) -> str: ...

    @property
    def model_id(self) -> str: ...

    def generate(self, request: ClinicalLLMRequest) -> ClinicalLLMResponse: ...


@dataclass(frozen=True, slots=True)
class OpenAICompatibleProvider:
    """Optional adapter for configurable OpenAI-compatible HTTP endpoints.

    The endpoint, model, and credential are supplied by the caller. This adapter
    works with services that implement strict ``json_schema`` chat completions;
    it is not part of the domain and can be replaced without pipeline changes.
    """

    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 120.0
    provider_name: str = "openai-compatible"

    def __post_init__(self) -> None:
        parsed_url = urllib.parse.urlparse(self.base_url)
        scheme = parsed_url.scheme
        if scheme not in {"http", "https"}:
            raise ValueError("base_url must use http or https")
        if scheme == "http" and parsed_url.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("plaintext HTTP is allowed only for loopback development endpoints")
        if not self.api_key:
            raise ValueError("api_key must not be empty")
        if not self.model:
            raise ValueError("model must not be empty")

    @property
    def provider_id(self) -> str:
        return self.provider_name

    @property
    def model_id(self) -> str:
        return self.model

    def generate(self, request: ClinicalLLMRequest) -> ClinicalLLMResponse:
        body: dict[str, object] = {
            "model": self.model,
            "temperature": request.temperature,
            "messages": list(provider_messages(request)),
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_version.replace("-", "_"),
                    "strict": True,
                    "schema": _strict_json_schema(request.response_schema),
                },
            },
        }
        if request.reasoning_effort is not None:
            body["reasoning_effort"] = request.reasoning_effort
        raw_request = json.dumps(body, ensure_ascii=False).encode("utf-8")
        http_request = urllib.request.Request(  # noqa: S310 - scheme validated in __post_init__
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=raw_request,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            opener = urllib.request.build_opener(_NoRedirectHandler())
            with opener.open(http_request, timeout=self.timeout_seconds) as response:
                raw_response = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raw_error = exc.read().decode("utf-8", errors="replace")
            raise ProviderInvocationError(
                f"structured provider HTTP request failed: {exc.code}", raw_error
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ProviderInvocationError(f"structured provider request failed: {exc}") from exc
        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise ProviderInvocationError(
                "structured provider response was not valid JSON", raw_response
            ) from exc
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderInvocationError(
                "provider response did not contain message content", raw_response
            ) from exc
        if not isinstance(content, str):
            raise ProviderInvocationError("provider message content must be a string", raw_response)
        usage_raw = payload.get("usage", {})
        usage = usage_raw if isinstance(usage_raw, dict) else {}
        model_version = payload.get("model")
        return ClinicalLLMResponse(
            content=content,
            raw_response=raw_response,
            model_version=model_version if isinstance(model_version, str) else None,
            usage={
                str(key): value
                for key, value in usage.items()
                if isinstance(value, int | float | str)
            },
        )


def _strict_json_schema(schema: dict[str, object]) -> dict[str, object]:
    """Adapt Pydantic JSON Schema to the strict structured-output subset."""
    adapted = _strict_schema_node(schema)
    if not isinstance(adapted, dict):
        raise TypeError("response schema root must be an object")
    return adapted


def _strict_schema_node(value: object) -> object:
    if isinstance(value, list):
        return [_strict_schema_node(item) for item in value]
    if not isinstance(value, dict):
        return value
    result: dict[str, object] = {}
    for key, item in value.items():
        if key in {"default", "discriminator"}:
            continue
        strict_key = "anyOf" if key == "oneOf" else str(key)
        result[strict_key] = _strict_schema_node(item)
    properties = result.get("properties")
    if isinstance(properties, dict):
        result["additionalProperties"] = False
        result["required"] = list(properties)
    return result


def retry_feedback_message(feedback: tuple[str, ...]) -> str:
    """Render the exact retry message hashed and sent to a provider."""
    return (
        "The previous response was rejected. Return a complete replacement without silently "
        "changing clinical meaning. Validation errors:\n" + "\n".join(feedback)
    )


def provider_messages(request: ClinicalLLMRequest) -> tuple[dict[str, str], ...]:
    """Return the exact provider-neutral message structure sent by this adapter."""
    messages: tuple[dict[str, str], ...] = ({"role": "user", "content": request.prompt},)
    if request.retry_feedback:
        messages += (
            {
                "role": "user",
                "content": retry_feedback_message(request.retry_feedback),
            },
        )
    return messages


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None
