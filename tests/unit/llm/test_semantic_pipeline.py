"""End-to-end tests of the LLM-first semantic pipeline with a fake provider."""

from __future__ import annotations

import copy
from collections import deque
from dataclasses import replace
from pathlib import Path

import pytest
from unit.llm.fakes import FakeClinicalLLMProvider, build_document_map

from cpg_tree.candidates import RelationType
from cpg_tree.candidates.graph_serialization import dump_candidate_graph, write_candidate_graph
from cpg_tree.llm.attempts import AttemptStatus
from cpg_tree.llm.schemas import (
    CANDIDATE_RELATION_BATCH_SCHEMA_VERSION,
    CANDIDATE_RULE_BATCH_SCHEMA_VERSION,
    OBSERVATION_BATCH_SCHEMA_VERSION,
)
from cpg_tree.pipelines.semantic import (
    SemanticPipelineConfig,
    SemanticPipelineError,
    run_semantic_pipeline,
)

_EXPECTED_ENTITY_COUNT = 2
_EXPECTED_STAGE_COUNT = 4


def _bindings(
    paths: tuple[str, ...],
    span_id: str,
    quote: str,
    evidence_class: str = "SOURCE_STATED",
) -> list[dict[str, object]]:
    return [
        {
            "claim_path": path,
            "evidence_class": evidence_class,
            "source_span_refs": [span_id],
            "exact_quote": quote,
        }
        for path in paths
    ]


def _observation_payload(span_id: str = "span-1") -> dict[str, object]:
    return {
        "schema_version": OBSERVATION_BATCH_SCHEMA_VERSION,
        "outcome": "COMPLETE",
        "items": [
            {
                "observation_id": "obs-bun",
                "kind": "RECOMMENDATION",
                "span_refs": [span_id],
                "exact_quote": "BUN > 30",
            },
            {
                "observation_id": "obs-admit",
                "kind": "EXPLICIT_RELATION",
                "span_refs": ["span-2"],
                "exact_quote": "If elevated, admit patient",
            },
        ],
    }


def _rule_payload() -> dict[str, object]:
    return {
        "schema_version": CANDIDATE_RULE_BATCH_SCHEMA_VERSION,
        "outcome": "COMPLETE",
        "variables": [
            {
                "variable_id": "bun",
                "label": "BUN",
                "value_type": "NUMERIC",
                "evidence_bindings": _bindings(("/label", "/value_type"), "span-1", "BUN > 30"),
            },
            {
                "variable_id": "elevated_bun",
                "label": "elevated BUN",
                "value_type": "BOOLEAN",
                "evidence_bindings": _bindings(
                    ("/label", "/value_type"),
                    "span-2",
                    "If elevated, admit patient",
                    "INFERRED",
                ),
            },
        ],
        "items": [
            {
                "candidate_id": "rule-assess",
                "condition": {
                    "kind": "COMPARISON",
                    "variable_ref": "bun",
                    "operator": "GT",
                    "operand": 30,
                },
                "evidence_class": "SOURCE_STATED",
                "observation_refs": ["obs-bun"],
                "actions": [
                    {
                        "action_id": "action-assess",
                        "action_type": "DECISION",
                        "target_text": "assess severity",
                        "evidence_bindings": _bindings(
                            ("/action_type", "/target_text"), "span-1", "BUN > 30"
                        ),
                    }
                ],
                "evidence_bindings": _bindings(
                    (
                        "/condition/variable_ref",
                        "/condition/operator",
                        "/condition/operand",
                    ),
                    "span-1",
                    "BUN > 30",
                ),
            },
            {
                "candidate_id": "rule-admit",
                "condition": {
                    "kind": "FLAG",
                    "variable_ref": "elevated_bun",
                    "expected": True,
                },
                "evidence_class": "INFERRED",
                "observation_refs": ["obs-admit"],
                "actions": [
                    {
                        "action_id": "action-admit",
                        "action_type": "ADMIT",
                        "target_text": "patient",
                        "evidence_bindings": _bindings(
                            ("/action_type", "/target_text"),
                            "span-2",
                            "admit patient",
                        ),
                    }
                ],
                "evidence_bindings": _bindings(
                    ("/condition/variable_ref", "/condition/expected"),
                    "span-2",
                    "If elevated, admit patient",
                    "INFERRED",
                ),
            },
        ],
    }


def _relation_payload() -> dict[str, object]:
    return {
        "schema_version": CANDIDATE_RELATION_BATCH_SCHEMA_VERSION,
        "outcome": "COMPLETE",
        "items": [
            {
                "candidate_relation_id": "relation-flow",
                "source_ref": "rule-assess",
                "target_refs": ["rule-admit"],
                "relation_type": "FLOW",
                "evidence_class": "SOURCE_STATED",
                "observation_refs": ["obs-admit"],
                "evidence_bindings": _bindings(
                    ("/source_ref", "/target_refs", "/relation_type"),
                    "span-2",
                    "If elevated, admit patient",
                ),
            }
        ],
    }


def _empty_reconciliation_payload() -> dict[str, object]:
    return {
        "schema_version": CANDIDATE_RELATION_BATCH_SCHEMA_VERSION,
        "outcome": "NO_CANDIDATES",
    }


def _qualified_reconciliation_payload() -> dict[str, object]:
    payload = copy.deepcopy(_relation_payload())
    relation = payload["items"][0]  # type: ignore[index]
    relation["candidate_relation_id"] = "relation-qualified"  # type: ignore[index]
    relation["branch_label"] = "explicit qualified continuation"  # type: ignore[index]
    relation["evidence_bindings"].extend(  # type: ignore[index,union-attr]
        _bindings(
            ("/branch_label",),
            "span-2",
            "If elevated, admit patient",
        )
    )
    return payload


def test_pipeline_builds_graph_only_from_provider_candidates() -> None:
    provider = FakeClinicalLLMProvider(
        deque(
            [
                _observation_payload(),
                _rule_payload(),
                _relation_payload(),
                _empty_reconciliation_payload(),
            ]
        )
    )
    result = run_semantic_pipeline(
        build_document_map(),
        provider,
        SemanticPipelineConfig(
            generation_run_id="generation-test",
            protocol_version_id="TEST-v01",
            max_retries=0,
        ),
    )
    assert len(result.graph.observations) == _EXPECTED_ENTITY_COUNT
    assert len(result.graph.rules) == _EXPECTED_ENTITY_COUNT
    assert len(result.graph.variables) == _EXPECTED_ENTITY_COUNT
    assert len(result.graph.relations) == 1
    assert result.graph.relations[0].relation_type is RelationType.FLOW
    assert result.graph.relations[0].source_ref == "rule-assess"
    assert len(provider.requests) == _EXPECTED_STAGE_COUNT
    assert [request.stage.value for request in provider.requests] == [
        "OBSERVATIONS",
        "RULES",
        "RELATIONS",
        "RECONCILIATION",
    ]
    assert all(item.status is AttemptStatus.ACCEPTED for item in result.graph.attempts)
    assert not result.graph.findings
    assert dump_candidate_graph(result.graph) == dump_candidate_graph(result.graph)


def test_nonexistent_span_is_rejected_and_retried_without_repair() -> None:
    provider = FakeClinicalLLMProvider(
        deque(
            [
                _observation_payload("invented-span"),
                _observation_payload(),
                _rule_payload(),
                _relation_payload(),
                _empty_reconciliation_payload(),
            ]
        )
    )
    result = run_semantic_pipeline(
        build_document_map(),
        provider,
        SemanticPipelineConfig(
            generation_run_id="generation-retry",
            protocol_version_id="TEST-v01",
            max_retries=1,
        ),
    )
    assert result.graph.attempts[0].status is AttemptStatus.REJECTED
    assert "nonexistent SourceSpan" in result.graph.attempts[0].validation_errors[0]
    assert result.graph.observations[0].span_refs == ("span-1",)


def test_reconciliation_cannot_overwrite_existing_relation() -> None:
    provider = FakeClinicalLLMProvider(
        deque(
            [
                _observation_payload(),
                _rule_payload(),
                _relation_payload(),
                _relation_payload(),
            ]
        )
    )
    with pytest.raises(SemanticPipelineError, match="structured output rejected") as error:
        run_semantic_pipeline(
            build_document_map(),
            provider,
            SemanticPipelineConfig(
                generation_run_id="generation-conflict",
                protocol_version_id="TEST-v01",
                max_retries=0,
            ),
        )
    assert len(error.value.attempts) == _EXPECTED_STAGE_COUNT


def test_protocol_version_must_match_registered_document_metadata() -> None:
    provider = FakeClinicalLLMProvider(deque())
    with pytest.raises(ValueError, match="does not match document metadata"):
        run_semantic_pipeline(
            build_document_map(),
            provider,
            SemanticPipelineConfig(
                generation_run_id="generation-wrong-protocol",
                protocol_version_id="OTHER-v01",
                max_retries=0,
            ),
        )
    assert not provider.requests


def test_protocol_version_accepts_source_metadata_with_v_prefix() -> None:
    document_map = build_document_map()
    document_map = replace(
        document_map,
        document=replace(document_map.document, protocol_version="v01"),
    )
    provider = FakeClinicalLLMProvider(
        deque(
            [
                _observation_payload(),
                _rule_payload(),
                _relation_payload(),
                _empty_reconciliation_payload(),
            ]
        )
    )
    result = run_semantic_pipeline(
        document_map,
        provider,
        SemanticPipelineConfig(
            generation_run_id="generation-prefixed-version",
            protocol_version_id="TEST-v01",
            max_retries=0,
        ),
    )
    assert result.graph.protocol_version_id == "TEST-v01"


def test_invalid_claim_path_is_quarantined_in_rule_stage() -> None:
    rule_payload = copy.deepcopy(_rule_payload())
    rule_payload["items"][0]["evidence_bindings"][0]["claim_path"] = "/not-a-field"  # type: ignore[index]
    provider = FakeClinicalLLMProvider(deque([_observation_payload(), rule_payload]))
    with pytest.raises(SemanticPipelineError) as error:
        run_semantic_pipeline(
            build_document_map(),
            provider,
            SemanticPipelineConfig(
                generation_run_id="generation-bad-claim",
                protocol_version_id="TEST-v01",
                max_retries=0,
            ),
        )
    assert len(error.value.attempts) == _EXPECTED_ENTITY_COUNT
    assert "claim_path does not resolve" in error.value.attempts[-1].validation_errors[0]


def test_expression_must_match_llm_declared_variable_type() -> None:
    rule_payload = copy.deepcopy(_rule_payload())
    rule_payload["variables"][0]["value_type"] = "BOOLEAN"  # type: ignore[index]
    provider = FakeClinicalLLMProvider(deque([_observation_payload(), rule_payload]))
    with pytest.raises(SemanticPipelineError) as error:
        run_semantic_pipeline(
            build_document_map(),
            provider,
            SemanticPipelineConfig(
                generation_run_id="generation-type-mismatch",
                protocol_version_id="TEST-v01",
                max_retries=0,
            ),
        )
    assert "requires NUMERIC variable" in error.value.attempts[-1].validation_errors[0]


def test_candidate_graph_writer_never_overwrites_history(tmp_path: Path) -> None:
    provider = FakeClinicalLLMProvider(
        deque(
            [
                _observation_payload(),
                _rule_payload(),
                _relation_payload(),
                _empty_reconciliation_payload(),
            ]
        )
    )
    result = run_semantic_pipeline(
        build_document_map(),
        provider,
        SemanticPipelineConfig(
            generation_run_id="generation-write-once",
            protocol_version_id="TEST-v01",
            max_retries=0,
        ),
    )
    path = tmp_path / "candidate_graph.json"
    write_candidate_graph(result.graph, path)
    with pytest.raises(FileExistsError):
        write_candidate_graph(result.graph, path)


def test_distinct_qualified_relation_is_preserved() -> None:
    provider = FakeClinicalLLMProvider(
        deque(
            [
                _observation_payload(),
                _rule_payload(),
                _relation_payload(),
                _qualified_reconciliation_payload(),
            ]
        )
    )
    result = run_semantic_pipeline(
        build_document_map(),
        provider,
        SemanticPipelineConfig(
            generation_run_id="generation-qualified-relation",
            protocol_version_id="TEST-v01",
            max_retries=0,
        ),
    )
    assert len(result.graph.relations) == _EXPECTED_ENTITY_COUNT
    assert result.graph.relations[1].branch_label == "explicit qualified continuation"


def test_post_generation_graph_failure_preserves_all_attempts() -> None:
    rule_payload = copy.deepcopy(_rule_payload())
    rule_payload["items"][0]["actions"][0]["action_id"] = "rule-assess"  # type: ignore[index]
    provider = FakeClinicalLLMProvider(
        deque(
            [
                _observation_payload(),
                rule_payload,
                _relation_payload(),
                _empty_reconciliation_payload(),
            ]
        )
    )
    with pytest.raises(SemanticPipelineError, match="collide") as error:
        run_semantic_pipeline(
            build_document_map(),
            provider,
            SemanticPipelineConfig(
                generation_run_id="generation-graph-failure",
                protocol_version_id="TEST-v01",
                max_retries=0,
            ),
        )
    assert len(error.value.attempts) == _EXPECTED_STAGE_COUNT
