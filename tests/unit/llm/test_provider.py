"""Tests for provider adapter security and strict schema adaptation."""

from __future__ import annotations

import pytest

from cpg_tree.llm.provider import OpenAICompatibleProvider, _strict_json_schema
from cpg_tree.llm.schemas import ObservationBatch


def test_strict_schema_requires_every_object_property() -> None:
    schema = _strict_json_schema(ObservationBatch.model_json_schema())

    def assert_strict(value: object) -> None:
        if isinstance(value, list):
            for item in value:
                assert_strict(item)
            return
        if not isinstance(value, dict):
            return
        assert "oneOf" not in value
        properties = value.get("properties")
        if isinstance(properties, dict):
            assert value["additionalProperties"] is False
            assert set(value["required"]) == set(properties)
        assert "default" not in value
        assert "discriminator" not in value
        for item in value.values():
            assert_strict(item)

    assert_strict(schema)


def test_remote_plaintext_provider_endpoint_is_rejected() -> None:
    with pytest.raises(ValueError, match="loopback"):
        OpenAICompatibleProvider(
            base_url="http://example.com/v1",
            api_key="secret",
            model="model",
        )


def test_loopback_plaintext_provider_endpoint_is_allowed() -> None:
    provider = OpenAICompatibleProvider(
        base_url="http://127.0.0.1:8000/v1",
        api_key="local-secret",
        model="local-model",
    )
    assert provider.provider_id == "openai-compatible"
