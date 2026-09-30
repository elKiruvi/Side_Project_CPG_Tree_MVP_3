"""Tests for the Pydantic wire schemas of structured LLM outputs."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cpg_tree.llm import (
    CANDIDATE_RELATION_BATCH_SCHEMA_VERSION,
    CANDIDATE_RULE_BATCH_SCHEMA_VERSION,
    OBSERVATION_BATCH_SCHEMA_VERSION,
    CandidateRelationBatch,
    CandidateRuleBatch,
    ObservationBatch,
    WireLogical,
)

DOSE_MG = 1000


def test_observation_batch_round_trip() -> None:
    payload = {
        "schema_version": OBSERVATION_BATCH_SCHEMA_VERSION,
        "run_id": "run-1",
        "segment_id": "seg-1",
        "outcome": "COMPLETE",
        "items": [
            {
                "observation_id": "obs-1",
                "kind": "RECOMMENDATION",
                "span_refs": ["span-1"],
                "exact_quote": "BUN > 30",
            }
        ],
    }
    batch = ObservationBatch.model_validate(payload)
    dumped = batch.model_dump(mode="json")
    round_tripped = ObservationBatch.model_validate(dumped)
    assert round_tripped.items[0].observation_id == "obs-1"
    assert round_tripped.outcome.value == "COMPLETE"


def test_no_candidates_is_a_valid_outcome() -> None:
    batch = ObservationBatch.model_validate(
        {
            "schema_version": OBSERVATION_BATCH_SCHEMA_VERSION,
            "run_id": "run-1",
            "segment_id": "seg-1",
            "outcome": "NO_CANDIDATES",
        }
    )
    assert batch.items == ()


def test_unknown_fields_fail_closed() -> None:
    with pytest.raises(ValidationError):
        ObservationBatch.model_validate(
            {
                "schema_version": OBSERVATION_BATCH_SCHEMA_VERSION,
                "run_id": "run-1",
                "segment_id": "seg-1",
                "outcome": "COMPLETE",
                "hallucinated_field": "x",
            }
        )


def test_unknown_schema_version_fails_closed() -> None:
    with pytest.raises(ValidationError, match="schema_version"):
        ObservationBatch.model_validate(
            {
                "schema_version": "observation-batch-v999",
                "run_id": "run-1",
                "segment_id": "seg-1",
                "outcome": "COMPLETE",
            }
        )


def test_observation_requires_span_refs() -> None:
    with pytest.raises(ValidationError):
        ObservationBatch.model_validate(
            {
                "schema_version": OBSERVATION_BATCH_SCHEMA_VERSION,
                "run_id": "run-1",
                "segment_id": "seg-1",
                "outcome": "COMPLETE",
                "items": [
                    {
                        "observation_id": "obs-1",
                        "kind": "RECOMMENDATION",
                        "span_refs": [],
                    }
                ],
            }
        )


def test_evidence_binding_requires_spans_unless_unresolved() -> None:
    with pytest.raises(ValidationError):
        CandidateRuleBatch.model_validate(
            {
                "schema_version": CANDIDATE_RULE_BATCH_SCHEMA_VERSION,
                "run_id": "run-1",
                "segment_id": "seg-1",
                "outcome": "COMPLETE",
                "items": [
                    {
                        "candidate_id": "cand-1",
                        "condition": {
                            "kind": "COMPARISON",
                            "variable_ref": "bun",
                            "operator": "GT",
                            "operand": 30,
                        },
                        "evidence_class": "SOURCE_STATED",
                        "evidence_bindings": [
                            {
                                "claim_path": "/condition/operand",
                                "evidence_class": "SOURCE_STATED",
                            }
                        ],
                    }
                ],
            }
        )


def test_wire_expression_discriminated_union_round_trip() -> None:
    payload = {
        "kind": "LOGICAL",
        "operator": "AT_LEAST_N",
        "threshold": 2,
        "operands": [
            {
                "kind": "COMPARISON",
                "variable_ref": "bun",
                "operator": "GT",
                "operand": 30,
            },
            {
                "kind": "FLAG",
                "variable_ref": "confusion",
                "expected": True,
            },
            {
                "kind": "MEMBERSHIP",
                "variable_ref": "setting",
                "values": ["outpatient", "inpatient"],
            },
        ],
    }
    expression = WireLogical.model_validate(payload)
    dumped = expression.model_dump(mode="json")
    assert WireLogical.model_validate(dumped) == expression
    assert expression.operands[0].kind == "COMPARISON"  # type: ignore[union-attr]


def test_wire_expression_rejects_bad_at_least_n_threshold() -> None:
    with pytest.raises(ValidationError):
        WireLogical.model_validate(
            {
                "kind": "LOGICAL",
                "operator": "AT_LEAST_N",
                "threshold": 5,
                "operands": [
                    {"kind": "FLAG", "variable_ref": "x", "expected": True},
                ],
            }
        )


def test_wire_expression_rejects_not_with_two_operands() -> None:
    with pytest.raises(ValidationError):
        WireLogical.model_validate(
            {
                "kind": "LOGICAL",
                "operator": "NOT",
                "operands": [
                    {"kind": "FLAG", "variable_ref": "x", "expected": True},
                    {"kind": "FLAG", "variable_ref": "y", "expected": False},
                ],
            }
        )


def test_wire_expression_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        WireLogical.model_validate(
            {
                "kind": "LOGICAL",
                "operator": "AND",
                "operands": [{"kind": "INVENTED", "variable_ref": "x"}],
            }
        )


def test_candidate_relation_batch_rejects_wildcard_endpoints() -> None:
    with pytest.raises(ValidationError):
        CandidateRelationBatch.model_validate(
            {
                "schema_version": CANDIDATE_RELATION_BATCH_SCHEMA_VERSION,
                "run_id": "run-1",
                "segment_id": "seg-1",
                "outcome": "COMPLETE",
                "items": [
                    {
                        "candidate_relation_id": "rel-1",
                        "source_ref": "cand-1",
                        "target_refs": ["cand-*"],
                        "relation_type": "FLOW",
                        "evidence_class": "SOURCE_STATED",
                    }
                ],
            }
        )


def test_candidate_rule_batch_accepts_full_nested_item() -> None:
    batch = CandidateRuleBatch.model_validate(
        {
            "schema_version": CANDIDATE_RULE_BATCH_SCHEMA_VERSION,
            "run_id": "run-1",
            "segment_id": "seg-1",
            "outcome": "COMPLETE",
            "items": [
                {
                    "candidate_id": "cand-nac-001",
                    "condition": {
                        "kind": "COMPARISON",
                        "variable_ref": "bun",
                        "operator": "GT",
                        "operand": 30,
                    },
                    "evidence_class": "NORMALIZED",
                    "actions": [
                        {
                            "action_id": "act-1",
                            "action_type": "PRESCRIBE",
                            "target_text": "ceftriaxone",
                            "dose_value": DOSE_MG,
                            "dose_unit": "mg",
                            "evidence_bindings": [
                                {
                                    "claim_path": "/dose_value",
                                    "evidence_class": "NORMALIZED",
                                    "source_span_refs": ["span-4"],
                                    "exact_quote": "1 g",
                                    "transformation": "unit normalized",
                                }
                            ],
                        }
                    ],
                    "evidence_bindings": [
                        {
                            "claim_path": "/condition/operand",
                            "evidence_class": "SOURCE_STATED",
                            "source_span_refs": ["span-3"],
                            "exact_quote": "BUN > 30",
                        }
                    ],
                }
            ],
        }
    )
    item = batch.items[0]
    assert item.actions[0].dose_value == DOSE_MG
    assert item.condition.kind == "COMPARISON"  # type: ignore[union-attr]


def test_batches_are_frozen() -> None:
    batch = ObservationBatch.model_validate(
        {
            "schema_version": OBSERVATION_BATCH_SCHEMA_VERSION,
            "run_id": "run-1",
            "segment_id": "seg-1",
            "outcome": "COMPLETE",
        }
    )
    with pytest.raises(ValidationError):
        batch.run_id = "changed"  # type: ignore[misc]


def test_batch_issues_carry_categories_and_severity() -> None:
    batch = ObservationBatch.model_validate(
        {
            "schema_version": OBSERVATION_BATCH_SCHEMA_VERSION,
            "run_id": "run-1",
            "segment_id": "seg-1",
            "outcome": "COMPLETE",
            "issues": [
                {
                    "issue_id": "issue-1",
                    "category": "SOURCE_CONFLICT",
                    "severity": "BLOCKING",
                    "description": "two source representations disagree",
                    "related_ids": ["span-1"],
                }
            ],
        }
    )
    assert batch.issues[0].severity == "BLOCKING"


def test_numeric_strings_are_not_coerced_into_clinical_thresholds() -> None:
    with pytest.raises(ValidationError):
        CandidateRuleBatch.model_validate(
            {
                "schema_version": CANDIDATE_RULE_BATCH_SCHEMA_VERSION,
                "run_id": "run-1",
                "segment_id": "seg-1",
                "outcome": "COMPLETE",
                "items": [
                    {
                        "candidate_id": "cand-1",
                        "condition": {
                            "kind": "COMPARISON",
                            "variable_ref": "bun",
                            "operator": "GT",
                            "operand": "30",
                        },
                        "evidence_class": "SOURCE_STATED",
                    }
                ],
            }
        )


def test_no_candidates_rejects_items_and_variables() -> None:
    with pytest.raises(ValidationError):
        CandidateRuleBatch.model_validate(
            {
                "schema_version": CANDIDATE_RULE_BATCH_SCHEMA_VERSION,
                "run_id": "run-1",
                "segment_id": "seg-1",
                "outcome": "NO_CANDIDATES",
                "variables": [{"variable_id": "bun", "label": "BUN", "value_type": "NUMERIC"}],
            }
        )


def test_non_finite_clinical_number_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CandidateRuleBatch.model_validate(
            {
                "schema_version": CANDIDATE_RULE_BATCH_SCHEMA_VERSION,
                "run_id": "run-1",
                "segment_id": "seg-1",
                "outcome": "COMPLETE",
                "items": [
                    {
                        "candidate_id": "cand-1",
                        "condition": {
                            "kind": "COMPARISON",
                            "variable_ref": "bun",
                            "operator": "GT",
                            "operand": float("inf"),
                        },
                        "evidence_class": "SOURCE_STATED",
                    }
                ],
            }
        )


def test_relation_rejects_duplicate_targets() -> None:
    with pytest.raises(ValidationError, match="duplicates"):
        CandidateRelationBatch.model_validate(
            {
                "schema_version": CANDIDATE_RELATION_BATCH_SCHEMA_VERSION,
                "run_id": "run-1",
                "segment_id": "seg-1",
                "outcome": "COMPLETE",
                "items": [
                    {
                        "candidate_relation_id": "rel-1",
                        "source_ref": "rule-1",
                        "target_refs": ["rule-2", "rule-2"],
                        "relation_type": "FLOW",
                        "evidence_class": "SOURCE_STATED",
                    }
                ],
            }
        )


def test_normalized_evidence_requires_transformation_record() -> None:
    with pytest.raises(ValidationError, match="transformation"):
        CandidateRuleBatch.model_validate(
            {
                "schema_version": CANDIDATE_RULE_BATCH_SCHEMA_VERSION,
                "run_id": "run-1",
                "segment_id": "seg-1",
                "outcome": "COMPLETE",
                "items": [
                    {
                        "candidate_id": "cand-1",
                        "condition": {
                            "kind": "FLAG",
                            "variable_ref": "flag",
                            "expected": True,
                        },
                        "evidence_class": "NORMALIZED",
                        "evidence_bindings": [
                            {
                                "claim_path": "/condition/expected",
                                "evidence_class": "NORMALIZED",
                                "source_span_refs": ["span-1"],
                                "exact_quote": "present",
                            }
                        ],
                    }
                ],
            }
        )
