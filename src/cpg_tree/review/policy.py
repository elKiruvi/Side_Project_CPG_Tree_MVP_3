"""Configurable approval policy.

The number and policy of clinical reviewers are not known in advance. The
policy is therefore an explicit configuration entity kept outside
``ReviewDecision``: one reviewer, two independent reviewers, or any other
aggregation rule can be configured without changing the decision record.
"""

# ruff: noqa: TRY004

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cpg_tree.review.model import ReviewDecision, ReviewVerdict

_MIN_DECISIONS: int = 1


class PolicySatisfaction(StrEnum):
    """Outcome of evaluating an approval policy over a decision set."""

    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"


@dataclass(frozen=True, slots=True)
class ApprovalPolicy:
    """Configuration of when a candidate is considered approved.

    ``minimum_decisions`` counts decisions whose verdict appears in
    ``accepted_verdicts``. Reviewer identity counting, per-verdict quotas,
    and other aggregation refinements are policy extensions for Phase 7; the
    contract keeps them out of the decision record.
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


def policy_satisfied(
    policy: ApprovalPolicy, decisions: tuple[ReviewDecision, ...]
) -> PolicySatisfaction:
    """Evaluate the policy over a set of decisions.

    This helper assumes the caller has already filtered to decisions bound to
    the exact candidate revision and hash under review; it only counts
    verdicts. Stale decisions must be filtered before calling.
    """
    if count_accepting_decisions(policy, decisions) >= policy.minimum_decisions:
        return PolicySatisfaction.SATISFIED
    return PolicySatisfaction.NOT_SATISFIED
