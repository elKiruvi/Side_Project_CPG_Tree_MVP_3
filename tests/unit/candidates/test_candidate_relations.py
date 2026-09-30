"""Tests for the CandidateRelation contract."""

from __future__ import annotations

import pytest

from cpg_tree.candidates import (
    CandidateRelation,
    EvidenceBinding,
    EvidenceClass,
    RelationType,
)

TWO_TARGETS = 2


def make_relation(**overrides: object) -> CandidateRelation:
    fields: dict[str, object] = {
        "candidate_relation_id": "rel-1",
        "revision": 1,
        "source_ref": "cand-nac-001",
        "target_refs": ("cand-nac-002",),
        "relation_type": RelationType.FLOW,
        "evidence_class": EvidenceClass.SOURCE_STATED,
    }
    fields.update(overrides)
    return CandidateRelation(**fields)  # type: ignore[arg-type]


def test_candidate_relation_construction() -> None:
    relation = make_relation()
    assert relation.content_hash is not None
    assert relation.branch_label is None


def test_relation_types_cover_handoff_vocabulary() -> None:
    assert {relation_type.value for relation_type in RelationType} == {
        "FLOW",
        "BRANCH",
        "REFERENCE",
        "SUPPORTS",
        "EXCEPTION_CONTEXT",
        "BRANCH_CONTEXT",
        "COMPOSITION",
        "DECLARES_ACTION",
    }


def test_flow_and_branch_are_sequence_relations_only() -> None:
    """Relation type never implies execution order by itself."""
    flow = make_relation(relation_type=RelationType.FLOW)
    reference = make_relation(relation_type=RelationType.REFERENCE)
    assert flow.relation_type is not reference.relation_type
    assert not hasattr(flow, "evaluate")


def test_candidate_relation_requires_targets() -> None:
    with pytest.raises(ValueError, match="target_refs"):
        make_relation(target_refs=())


def test_candidate_relation_rejects_self_edges() -> None:
    with pytest.raises(ValueError, match="itself"):
        make_relation(target_refs=("cand-nac-001",))


def test_candidate_relation_rejects_wildcards() -> None:
    with pytest.raises(ValueError, match="source_ref"):
        make_relation(source_ref="*")
    with pytest.raises(ValueError, match="target_refs"):
        make_relation(target_refs=("cand-*",))


def test_candidate_relation_supports_multiple_targets_with_branch_label() -> None:
    relation = make_relation(
        relation_type=RelationType.BRANCH,
        target_refs=("cand-nac-002", "cand-nac-003"),
        branch_label="sepsis vs no sepsis",
        evidence_bindings=(
            EvidenceBinding(
                claim_path="/target_refs/1",
                evidence_class=EvidenceClass.SOURCE_STATED,
                source_span_refs=("span-4",),
                exact_quote="si sepsis",
            ),
        ),
    )
    assert len(relation.target_refs) == TWO_TARGETS
    assert relation.branch_label == "sepsis vs no sepsis"


def test_candidate_relation_requires_valid_identifiers() -> None:
    with pytest.raises(ValueError, match="source_ref"):
        make_relation(source_ref="free text ref")
    with pytest.raises(ValueError, match="candidate_relation_id"):
        make_relation(candidate_relation_id="")


def test_candidate_relation_is_current_revision() -> None:
    relation = make_relation()
    assert relation.is_current_revision(1, relation.content_hash or "")
    assert not relation.is_current_revision(1, "0" * 64)
