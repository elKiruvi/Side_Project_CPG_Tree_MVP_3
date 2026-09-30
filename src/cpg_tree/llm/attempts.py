"""Fail-closed structured response parsing and generation-attempt records."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import cast

from pydantic import BaseModel, ValidationError

from cpg_tree.candidates.hashing import sha256_hex, stable_json_dumps
from cpg_tree.llm.provider import (
    ClinicalLLMProvider,
    ClinicalLLMRequest,
    ProviderInvocationError,
    provider_messages,
)


class AttemptStatus(StrEnum):
    """Result of parsing and validating one provider response."""

    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class GenerationAttempt:
    """Reproducible metadata for one provider invocation."""

    attempt_id: str
    request_id: str
    parent_attempt_id: str | None
    provider: str
    model: str
    model_version: str | None
    prompt_version: str
    schema_version: str
    temperature: float
    reasoning_effort: str | None
    input_span_ids: tuple[str, ...]
    input_hash: str
    raw_response: str | None
    raw_response_hash: str | None
    status: AttemptStatus
    validation_errors: tuple[str, ...]
    started_at: str
    completed_at: str
    usage: tuple[tuple[str, int | float | str], ...] = ()


@dataclass(frozen=True, slots=True)
class StructuredBatchResult[BatchT: BaseModel]:
    """Validated batch and the complete bounded attempt history."""

    batch: BatchT
    accepted_attempt_id: str
    attempts: tuple[GenerationAttempt, ...]


class StructuredOutputError(RuntimeError):
    """Raised after all strict structured-output attempts are rejected."""

    def __init__(self, message: str, attempts: tuple[GenerationAttempt, ...]) -> None:
        super().__init__(message)
        self.attempts = attempts


def invoke_structured[BatchT: BaseModel](  # noqa: PLR0913
    provider: ClinicalLLMProvider,
    request: ClinicalLLMRequest,
    batch_type: type[BatchT],
    *,
    max_retries: int,
    validate: Callable[[BatchT], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> StructuredBatchResult[BatchT]:
    """Invoke, parse, and validate with bounded retries and no silent repair."""
    if max_retries < 0:
        raise ValueError("max_retries must not be negative")
    clock = now or (lambda: datetime.now(UTC))
    attempts: list[GenerationAttempt] = []
    feedback: tuple[str, ...] = request.retry_feedback
    parent_attempt_id: str | None = None
    for ordinal in range(max_retries + 1):
        batch: BatchT | None = None
        current = ClinicalLLMRequest(
            request_id=request.request_id,
            stage=request.stage,
            prompt=request.prompt,
            prompt_version=request.prompt_version,
            schema_version=request.schema_version,
            response_schema=request.response_schema,
            input_span_ids=request.input_span_ids,
            input_hash=request.input_hash,
            temperature=request.temperature,
            reasoning_effort=request.reasoning_effort,
            retry_feedback=feedback,
        )
        current = replace(
            current,
            input_hash=sha256_hex(stable_json_dumps(provider_messages(current))),
        )
        started_at = _iso(clock())
        raw_response: str | None = None
        model_version: str | None = None
        usage: dict[str, int | float | str] = {}
        errors: tuple[str, ...]
        try:
            response = provider.generate(current)
            raw_response = response.raw_response or response.content
            model_version = response.model_version
            usage = response.usage
            batch = cast(BatchT, batch_type.model_validate_json(response.content))
            _validate_envelope(batch, request)
            if validate is not None:
                validate(batch)
            errors = ()
        except ProviderInvocationError as exc:
            raw_response = exc.raw_response
            errors = (str(exc),)
        except (RuntimeError, ValidationError, ValueError) as exc:
            errors = (str(exc),)
        response_hash = sha256_hex(raw_response) if raw_response is not None else None
        attempt_id = _attempt_id(request.request_id, ordinal, response_hash, errors)
        status = AttemptStatus.ACCEPTED if not errors else AttemptStatus.REJECTED
        attempt = GenerationAttempt(
            attempt_id=attempt_id,
            request_id=request.request_id,
            parent_attempt_id=parent_attempt_id,
            provider=provider.provider_id,
            model=provider.model_id,
            model_version=model_version,
            prompt_version=request.prompt_version,
            schema_version=request.schema_version,
            temperature=request.temperature,
            reasoning_effort=request.reasoning_effort,
            input_span_ids=request.input_span_ids,
            input_hash=current.input_hash,
            raw_response=raw_response,
            raw_response_hash=response_hash,
            status=status,
            validation_errors=errors,
            started_at=started_at,
            completed_at=_iso(clock()),
            usage=tuple(sorted(usage.items())),
        )
        attempts.append(attempt)
        if not errors and batch is not None:
            return StructuredBatchResult(
                batch=batch,
                accepted_attempt_id=attempt_id,
                attempts=tuple(attempts),
            )
        feedback = errors
        parent_attempt_id = attempt_id
    raise StructuredOutputError(
        f"structured output rejected after {len(attempts)} attempts", tuple(attempts)
    )


def _validate_envelope(batch: BaseModel, request: ClinicalLLMRequest) -> None:
    if getattr(batch, "run_id", None) != request.request_id:
        raise ValueError("response run_id does not match the request_id")
    if getattr(batch, "segment_id", None) != "document-full":
        raise ValueError("response segment_id must be 'document-full'")


def _attempt_id(
    request_id: str, ordinal: int, response_hash: str | None, errors: tuple[str, ...]
) -> str:
    material = f"{request_id}|{ordinal}|{response_hash or ''}|{'|'.join(errors)}"
    return f"attempt-{sha256_hex(material)[:20]}"


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()
