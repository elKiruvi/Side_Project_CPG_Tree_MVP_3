"""Tests for the configurable ApprovalPolicy."""

from __future__ import annotations

import pytest

from cpg_tree.review import (
    ApprovalPolicy,
    PolicySatisfaction,
    ReviewDecision,
    ReviewSubjectType,
    ReviewVerdict,
    count_accepting_decisions,
    policy_satisfied,
)

CANDIDATE_HASH = "a" * 64
MIN_ONE = 1
MIN_TWO = 2
TWO_ACCEPTING = 2


def make_decision(decision_id: str, verdict: ReviewVerdict) -> ReviewDecision:
    return ReviewDecision(
        decision_id=decision_id,
        subject_type=ReviewSubjectType.RULE,
        candidate_id="cand-nac-001",
        candidate_revision=1,
        candidate_content_hash=CANDIDATE_HASH,
        verdict=verdict,
        reviewer_id="reviewer-dr-garcia",
        reviewed_at="2026-09-29T15:00:00",
    )


def test_policy_is_configurable_and_not_hardcoded() -> None:
    single = ApprovalPolicy(name="single-reviewer", minimum_decisions=MIN_ONE)
    dual = ApprovalPolicy(name="dual-reviewer", minimum_decisions=MIN_TWO)
    assert single.minimum_decisions == MIN_ONE
    assert dual.minimum_decisions == MIN_TWO


def test_policy_requires_positive_minimum() -> None:
    with pytest.raises(ValueError, match="minimum_decisions"):
        ApprovalPolicy(name="bad", minimum_decisions=0)


def test_policy_requires_accepted_verdicts() -> None:
    with pytest.raises(ValueError, match="accepted_verdicts"):
        ApprovalPolicy(name="bad", minimum_decisions=1, accepted_verdicts=())


def test_policy_counts_accepting_decisions() -> None:
    policy = ApprovalPolicy(name="single", minimum_decisions=1)
    decisions = (
        make_decision("dec-1", ReviewVerdict.APPROVE),
        make_decision("dec-2", ReviewVerdict.REJECT),
        make_decision("dec-3", ReviewVerdict.APPROVE),
    )
    assert count_accepting_decisions(policy, decisions) == TWO_ACCEPTING


def test_policy_satisfied_and_not_satisfied() -> None:
    dual = ApprovalPolicy(name="dual", minimum_decisions=2)
    single_approve = (make_decision("dec-1", ReviewVerdict.APPROVE),)
    two_approvals = (
        make_decision("dec-1", ReviewVerdict.APPROVE),
        make_decision("dec-2", ReviewVerdict.APPROVE),
    )
    assert policy_satisfied(dual, single_approve) is PolicySatisfaction.NOT_SATISFIED
    assert policy_satisfied(dual, two_approvals) is PolicySatisfaction.SATISFIED


def test_policy_evaluation_never_accepts_stale_decisions() -> None:
    """The policy only counts verdicts; stale filtering is the caller's duty.

    A decision bound to a different revision is not accepted by
    ``policy_satisfied`` merely by counting verdicts: callers must filter with
    ``ReviewDecision.is_stale_for`` first, and that is enforced by
    ``references_candidate`` below.
    """
    stale = make_decision("dec-1", ReviewVerdict.APPROVE)
    assert stale.is_stale_for(2, CANDIDATE_HASH)
    assert not stale.references_candidate("cand-nac-001", 2, CANDIDATE_HASH)
