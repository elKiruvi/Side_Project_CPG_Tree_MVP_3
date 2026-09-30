"""Tests for bounded fail-closed provider invocation."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime

import pytest
from unit.llm.fakes import FakeClinicalLLMProvider

from cpg_tree.llm.attempts import AttemptStatus, StructuredOutputError, invoke_structured
from cpg_tree.llm.provider import ClinicalLLMRequest, SemanticStage
from cpg_tree.llm.schemas import OBSERVATION_BATCH_SCHEMA_VERSION, ObservationBatch

_EXPECTED_ATTEMPT_COUNT = 2


def _request() -> ClinicalLLMRequest:
    return ClinicalLLMRequest(
        request_id="generation-observations",
        stage=SemanticStage.OBSERVATIONS,
        prompt="source context",
        prompt_version="observations-v1",
        schema_version=OBSERVATION_BATCH_SCHEMA_VERSION,
        response_schema=ObservationBatch.model_json_schema(),
        input_span_ids=("span-1",),
        input_hash="a" * 64,
    )


def test_invalid_json_retries_then_accepts() -> None:
    provider = FakeClinicalLLMProvider(
        deque(
            [
                "not json",
                {
                    "schema_version": OBSERVATION_BATCH_SCHEMA_VERSION,
                    "outcome": "NO_CANDIDATES",
                },
            ]
        )
    )

    def now() -> datetime:
        return datetime(2026, 1, 1, tzinfo=UTC)

    result = invoke_structured(provider, _request(), ObservationBatch, max_retries=1, now=now)
    assert [item.status for item in result.attempts] == [
        AttemptStatus.REJECTED,
        AttemptStatus.ACCEPTED,
    ]
    assert result.attempts[1].parent_attempt_id == result.attempts[0].attempt_id
    assert provider.requests[1].retry_feedback


def test_invalid_output_is_quarantined_after_retry_limit() -> None:
    provider = FakeClinicalLLMProvider(deque(["not json", "still not json"]))
    with pytest.raises(StructuredOutputError) as error:
        invoke_structured(provider, _request(), ObservationBatch, max_retries=1)
    assert len(error.value.attempts) == _EXPECTED_ATTEMPT_COUNT
    assert all(item.status is AttemptStatus.REJECTED for item in error.value.attempts)
