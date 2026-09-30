"""Tests for the ReviewDecision contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cpg_tree.review import (
    ChecklistAnswer,
    ReviewDecision,
    ReviewSubjectType,
    ReviewVerdict,
)

CANDIDATE_HASH = "a" * 64


def make_decision(**overrides: object) -> ReviewDecision:
    fields: dict[str, object] = {
        "decision_id": "dec-1",
        "subject_type": ReviewSubjectType.RULE,
        "candidate_id": "cand-nac-001",
        "candidate_revision": 1,
        "candidate_content_hash": CANDIDATE_HASH,
        "verdict": ReviewVerdict.APPROVE,
        "reviewer_id": "reviewer-dr-garcia",
        "reviewed_at": "2026-09-29T15:00:00",
    }
    fields.update(overrides)
    return ReviewDecision(**fields)  # type: ignore[arg-type]


def test_review_decision_construction() -> None:
    decision = make_decision()
    assert decision.verdict is ReviewVerdict.APPROVE
    assert decision.rationale is None


def test_review_decision_binds_to_exact_candidate_hash() -> None:
    decision = make_decision()
    assert decision.references_candidate("cand-nac-001", 1, CANDIDATE_HASH)
    assert not decision.references_candidate("cand-nac-001", 1, "b" * 64)
    assert not decision.references_candidate("cand-nac-001", 2, CANDIDATE_HASH)
    assert not decision.references_candidate("cand-nac-999", 1, CANDIDATE_HASH)


def test_review_decision_detects_stale_revision() -> None:
    decision = make_decision()
    assert not decision.is_stale_for(1, CANDIDATE_HASH)
    assert decision.is_stale_for(2, CANDIDATE_HASH)
    assert decision.is_stale_for(1, "b" * 64)


def test_review_decision_rejects_bad_hash() -> None:
    with pytest.raises(ValueError, match="candidate_content_hash"):
        make_decision(candidate_content_hash="not-a-hash")


def test_review_decision_rejects_bad_revision() -> None:
    with pytest.raises(ValueError, match="candidate_revision"):
        make_decision(candidate_revision=0)


def test_review_decision_requires_iso_datetime() -> None:
    with pytest.raises(ValueError, match="reviewed_at"):
        make_decision(reviewed_at="2026-09-29")


def test_request_changes_records_proposed_corrections() -> None:
    decision = make_decision(
        verdict=ReviewVerdict.REQUEST_CHANGES,
        rationale="threshold does not match the flowchart",
        proposed_corrections=("use BUN > 20 with a conflict Issue",),
        checklist_answers=(ChecklistAnswer(question="operator correct?", answer="no"),),
    )
    assert decision.verdict is ReviewVerdict.REQUEST_CHANGES
    assert len(decision.proposed_corrections) == 1


def test_review_decision_supersedes_chain_is_append_only() -> None:
    original = make_decision()
    successor = make_decision(
        decision_id="dec-2",
        verdict=ReviewVerdict.REJECT,
        supersedes_decision_id=original.decision_id,
    )
    assert successor.supersedes_decision_id == "dec-1"
    assert original.verdict is ReviewVerdict.APPROVE


def test_review_decision_cannot_supersede_itself() -> None:
    with pytest.raises(ValueError, match="supersede"):
        make_decision(supersedes_decision_id="dec-1")


def test_review_decision_is_not_mutable() -> None:
    decision = make_decision()
    with pytest.raises(FrozenInstanceError):
        decision.verdict = ReviewVerdict.REJECT  # type: ignore[misc]
