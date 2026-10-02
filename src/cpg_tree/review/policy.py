"""Configurable approval policy.

The number and policy of clinical reviewers are not known in advance. The
policy is therefore an explicit configuration entity kept outside
``ReviewDecision``: one reviewer, two independent reviewers, N-of-M reviewers,
unanimous acceptance, or adjudication-required configurations can all be
expressed without changing the decision record.

Phase 7 extends the Phase 1 contract with:

- distinct-reviewer counting (N-of-M and unanimity semantics);
- ``REVIEW_CONFLICT``: disagreement between accepting and rejecting verdicts
  is represented explicitly and never resolved automatically;
- blocking verdicts (``REJECT``, ``REQUEST_CHANGES``) prevent approval even
  when the minimum number of accepting reviewers is reached.
"""

# ruff: noqa: TRY004

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cpg_tree.review.model import ReviewDecision, ReviewVerdict

_MIN_DECISIONS: int = 1

_BLOCKING_VERDICTS = (ReviewVerdict.REJECT, ReviewVerdict.REQUEST_CHANGES)


class PolicySatisfaction(StrEnum):
    """Outcome of evaluating an approval policy over a decision set."""

    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    REVIEW_CONFLICT = "REVIEW_CONFLICT"


@dataclass(frozen=True, slots=True)
class ApprovalPolicy:
    """Configuration of when a candidate is considered approved.

    ``minimum_decisions`` counts accepting decisions in the Phase 1
    ``policy_satisfied`` helper and DISTINCT reviewers in the Phase 7
    ``evaluate_approval`` helper (N-of-M / unanimity semantics). In Phase 7, a
    negative verdict from any reviewer (``REJECT``/``REQUEST_CHANGES``) blocks
    approval and produces ``REVIEW_CONFLICT`` when accepting reviewers also
    exist: disagreement is never silently resolved by this evaluator.
    """

    name: str
    minimum_decisions: int
    accepted_verdicts: tuple[ReviewVerdict, ...] = (ReviewVerdict.APPROVE,)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("ApprovalPolicy.name must not be empty")
        if isinstance(self.minimum_decisions, bool) or not isinstance(self.minimum_decisions, int):
            raise ValueError("ApprovalPolicy.minimum_decisions must be an integer")
        if self.minimum_decisions < _MIN_DECISIONS:
            raise ValueError("ApprovalPolicy.minimum_decisions must be positive")
        if not self.accepted_verdicts:
            raise ValueError("ApprovalPolicy.accepted_verdicts must not be empty")


def count_accepting_decisions(policy: ApprovalPolicy, decisions: tuple[ReviewDecision, ...]) -> int:
    """Count decisions whose verdict is accepted by the policy.

    Counting never considers whether the decision is current: stale-decision
    rejection is the caller's responsibility, so a policy evaluation can never
    silently accept an outdated review.
    """
    return sum(1 for decision in decisions if decision.verdict in policy.accepted_verdicts)


def distinct_accepting_reviewers(
    policy: ApprovalPolicy, decisions: tuple[ReviewDecision, ...]
) -> tuple[str, ...]:
    """Distinct reviewer ids whose verdict is accepted by the policy."""
    return tuple(
        sorted(
            {
                decision.reviewer_id
                for decision in decisions
                if decision.verdict in policy.accepted_verdicts
            }
        )
    )


def policy_satisfied(
    policy: ApprovalPolicy, decisions: tuple[ReviewDecision, ...]
) -> PolicySatisfaction:
    """Evaluate the policy over a set of decisions (Phase 1 contract).

    This helper assumes the caller has already filtered to decisions bound to
    the exact candidate revision and hash under review; it only counts
    verdicts. Stale decisions must be filtered before calling. Distinct-
    reviewer and disagreement semantics live in ``evaluate_approval``.
    """
    if count_accepting_decisions(policy, decisions) >= policy.minimum_decisions:
        return PolicySatisfaction.SATISFIED
    return PolicySatisfaction.NOT_SATISFIED


def evaluate_approval(
    policy: ApprovalPolicy,
    decisions: tuple[ReviewDecision, ...],
    *,
    require_distinct_reviewers: bool = True,
    require_conflict_free: bool = True,
) -> PolicySatisfaction:
    """Evaluate an approval policy over current decisions.

    ``require_distinct_reviewers`` counts distinct reviewer identities toward
    ``minimum_decisions`` (N-of-M / unanimity semantics). When
    ``require_conflict_free`` is set, any blocking verdict coexisting with an
    accepting verdict produces ``REVIEW_CONFLICT``; a blocking verdict alone
    produces ``NOT_SATISFIED``. Disagreement is represented, never resolved.
    """
    accepting = distinct_accepting_reviewers(policy, decisions)
    blocking = _has_blocking_verdict(decisions)
    if blocking and require_conflict_free and accepting:
        return PolicySatisfaction.REVIEW_CONFLICT
    if blocking:
        return PolicySatisfaction.NOT_SATISFIED
    if require_distinct_reviewers:
        if len(accepting) >= policy.minimum_decisions:
            return PolicySatisfaction.SATISFIED
        return PolicySatisfaction.NOT_SATISFIED
    if count_accepting_decisions(policy, decisions) >= policy.minimum_decisions:
        return PolicySatisfaction.SATISFIED
    return PolicySatisfaction.NOT_SATISFIED


def _has_blocking_verdict(decisions: tuple[ReviewDecision, ...]) -> bool:
    return any(decision.verdict in _BLOCKING_VERDICTS for decision in decisions)


def current_decisions(
    decisions: tuple[ReviewDecision, ...], *, revision: int, content_hash: str
) -> tuple[ReviewDecision, ...]:
    """Filter decisions to those bound to the exact revision and hash."""
    return tuple(
        decision
        for decision in decisions
        if decision.candidate_revision == revision
        and decision.candidate_content_hash == content_hash
    )


def stale_decisions(
    decisions: tuple[ReviewDecision, ...], *, revision: int, content_hash: str
) -> tuple[ReviewDecision, ...]:
    """Filter decisions NOT bound to the exact revision and hash."""
    return tuple(
        decision for decision in decisions if decision.is_stale_for(revision, content_hash)
    )
