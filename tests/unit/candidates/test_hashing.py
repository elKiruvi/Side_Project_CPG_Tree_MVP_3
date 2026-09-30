"""Tests for stable content hashing."""

from __future__ import annotations

import pytest

from cpg_tree.candidates import (
    CandidateRule,
    CandidateState,
    EvidenceBinding,
    EvidenceClass,
    compute_candidate_rule_content_hash,
    sha256_hex,
    stable_json_dumps,
)
from cpg_tree.candidates.enums import RelationType
from cpg_tree.candidates.relations import compute_candidate_relation_content_hash
from cpg_tree.knowledge import ComparisonOperator, Condition, ConditionKind

BUN_GT_30 = Condition(
    kind=ConditionKind.COMPARISON,
    variable_ref="bun",
    operator=ComparisonOperator.GT,
    operand=30,
)

SHA256_LENGTH = 64


def test_stable_json_is_deterministic_across_key_order() -> None:
    assert stable_json_dumps({"b": 1, "a": 2}) == stable_json_dumps({"a": 2, "b": 1})


def test_sha256_hex_is_stable() -> None:
    assert sha256_hex("abc") == sha256_hex("abc")
    assert len(sha256_hex("abc")) == SHA256_LENGTH
    assert sha256_hex("abc") != sha256_hex("abd")


def _make_binding(claim_path: str, span: str) -> EvidenceBinding:
    return EvidenceBinding(
        claim_path=claim_path,
        evidence_class=EvidenceClass.SOURCE_STATED,
        source_span_refs=(span,),
        exact_quote="BUN > 30",
    )


def test_candidate_rule_hash_is_computed_on_construction() -> None:
    rule = CandidateRule(
        candidate_id="cand-nac-001",
        revision=1,
        protocol_version_id="CT-PL-193-v09",
        condition=BUN_GT_30,
        evidence_class=EvidenceClass.SOURCE_STATED,
        observation_refs=("obs-1",),
        evidence_bindings=(_make_binding("/condition/operand", "span-1"),),
    )
    assert rule.content_hash is not None
    assert len(rule.content_hash) == SHA256_LENGTH


def test_candidate_rule_hash_ignores_identity_and_lifecycle_fields() -> None:
    base = CandidateRule(
        candidate_id="cand-nac-001",
        revision=1,
        protocol_version_id="CT-PL-193-v09",
        condition=BUN_GT_30,
        evidence_class=EvidenceClass.SOURCE_STATED,
    )
    renamed = CandidateRule(
        candidate_id="cand-nac-002",
        revision=7,
        protocol_version_id="CT-PL-193-v09",
        condition=BUN_GT_30,
        evidence_class=EvidenceClass.SOURCE_STATED,
        candidate_state=CandidateState.NEEDS_CHANGES,
    )
    assert base.content_hash == renamed.content_hash


def test_candidate_rule_hash_changes_with_content() -> None:
    base = CandidateRule(
        candidate_id="cand-nac-001",
        revision=1,
        protocol_version_id="CT-PL-193-v09",
        condition=BUN_GT_30,
        evidence_class=EvidenceClass.SOURCE_STATED,
    )
    changed_threshold = CandidateRule(
        candidate_id="cand-nac-001",
        revision=1,
        protocol_version_id="CT-PL-193-v09",
        condition=Condition(
            kind=ConditionKind.COMPARISON,
            variable_ref="bun",
            operator=ComparisonOperator.GT,
            operand=20,
        ),
        evidence_class=EvidenceClass.SOURCE_STATED,
    )
    assert base.content_hash != changed_threshold.content_hash


def test_candidate_rule_accepts_verified_hash_and_rejects_mismatch() -> None:
    verified = CandidateRule(
        candidate_id="cand-nac-001",
        revision=1,
        protocol_version_id="CT-PL-193-v09",
        condition=BUN_GT_30,
        evidence_class=EvidenceClass.SOURCE_STATED,
        content_hash=compute_candidate_rule_content_hash(
            condition=BUN_GT_30,
            evidence_class=EvidenceClass.SOURCE_STATED,
            observation_refs=(),
            applies_to=None,
            actions=(),
            exceptions=(),
            modality=None,
            statement_kind=None,
            evidence_bindings=(),
            ambiguity_flags=(),
        ),
    )
    assert verified.content_hash is not None

    with pytest.raises(ValueError, match="content_hash"):
        CandidateRule(
            candidate_id="cand-nac-001",
            revision=1,
            protocol_version_id="CT-PL-193-v09",
            condition=BUN_GT_30,
            evidence_class=EvidenceClass.SOURCE_STATED,
            content_hash="0" * 64,
        )


def test_relation_hash_ignores_identity_fields() -> None:
    base = compute_candidate_relation_content_hash(
        source_ref="cand-a",
        target_refs=("cand-b",),
        relation_type=RelationType.FLOW,
        evidence_class=EvidenceClass.SOURCE_STATED,
        observation_refs=(),
        branch_label=None,
        temporal_qualifier=None,
        evidence_bindings=(),
    )
    reordered = compute_candidate_relation_content_hash(
        source_ref="cand-a",
        target_refs=("cand-b",),
        relation_type=RelationType.FLOW,
        evidence_class=EvidenceClass.SOURCE_STATED,
        observation_refs=(),
        branch_label=None,
        temporal_qualifier=None,
        evidence_bindings=(),
    )
    assert base == reordered


def test_relation_hash_changes_with_target() -> None:
    base = compute_candidate_relation_content_hash(
        source_ref="cand-a",
        target_refs=("cand-b",),
        relation_type=RelationType.FLOW,
        evidence_class=EvidenceClass.SOURCE_STATED,
        observation_refs=(),
        branch_label=None,
        temporal_qualifier=None,
        evidence_bindings=(),
    )
    other = compute_candidate_relation_content_hash(
        source_ref="cand-a",
        target_refs=("cand-c",),
        relation_type=RelationType.FLOW,
        evidence_class=EvidenceClass.SOURCE_STATED,
        observation_refs=(),
        branch_label=None,
        temporal_qualifier=None,
        evidence_bindings=(),
    )
    assert base != other
