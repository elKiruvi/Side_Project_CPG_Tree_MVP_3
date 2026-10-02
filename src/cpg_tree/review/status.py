"""Review status summary for one protocol's candidate graph.

Computes, independently per protocol, how many candidate rules and relations
have been reviewed, which verdicts exist, what is still pending, whether any
decisions are stale, and how many remain BLOCKED. Clinical review state is
never combined across protocols.
"""

# ruff: noqa: PLR0912

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from cpg_tree.candidates.enums import CandidateState
from cpg_tree.candidates.graph import CandidateGraph
from cpg_tree.review.model import ReviewDecision, ReviewSubjectType, ReviewVerdict

REVIEW_STATUS_SCHEMA = "review-status-v1"


@dataclass(frozen=True, slots=True)
class ReviewStatus:
    """Deterministic review progress for one candidate graph."""

    protocol_version_id: str
    rule_count: int
    relation_count: int
    reviewed_rules: int
    reviewed_relations: int
    pending_rules: tuple[str, ...]
    pending_relations: tuple[str, ...]
    accepted_rules: int
    accepted_relations: int
    rejected_rules: int
    rejected_relations: int
    change_requests: int
    needs_clarification: int
    deferred: int
    abstained: int
    blocked_rules: int
    blocked_relations: int
    stale_decisions: int
    decision_count: int
    reviewer_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Deterministic JSON-safe representation."""
        return {
            "schema": REVIEW_STATUS_SCHEMA,
            "protocol_version_id": self.protocol_version_id,
            "rule_count": self.rule_count,
            "relation_count": self.relation_count,
            "reviewed_rules": self.reviewed_rules,
            "reviewed_relations": self.reviewed_relations,
            "pending_rules": sorted(self.pending_rules),
            "pending_relations": sorted(self.pending_relations),
            "accepted_rules": self.accepted_rules,
            "accepted_relations": self.accepted_relations,
            "rejected_rules": self.rejected_rules,
            "rejected_relations": self.rejected_relations,
            "change_requests": self.change_requests,
            "needs_clarification": self.needs_clarification,
            "deferred": self.deferred,
            "abstained": self.abstained,
            "blocked_rules": self.blocked_rules,
            "blocked_relations": self.blocked_relations,
            "stale_decisions": self.stale_decisions,
            "decision_count": self.decision_count,
            "reviewer_ids": sorted(self.reviewer_ids),
        }


def compute_review_status(  # noqa: C901, PLR0915
    graph: CandidateGraph, decisions: tuple[ReviewDecision, ...]
) -> ReviewStatus:
    """Compute the review progress of one protocol independently."""
    rule_ids = {rule.candidate_id: rule for rule in graph.rules}
    relation_ids = {relation.candidate_relation_id: relation for relation in graph.relations}
    reviewed_rules: set[str] = set()
    reviewed_relations: set[str] = set()
    stale = 0
    reviewers: set[str] = set()
    accepted_rules = accepted_relations = 0
    rejected_rules = rejected_relations = 0
    changes = clarification = deferred = abstained = 0
    for decision in decisions:
        reviewers.add(decision.reviewer_id)
        if decision.subject_type is ReviewSubjectType.RULE:
            rule = rule_ids.get(decision.candidate_id)
            if rule is None:
                continue
            if decision.is_stale_for(rule.revision, rule.content_hash or ""):
                stale += 1
                continue
            reviewed_rules.add(decision.candidate_id)
            if decision.verdict is ReviewVerdict.APPROVE:
                accepted_rules += 1
            elif decision.verdict is ReviewVerdict.REJECT:
                rejected_rules += 1
            elif decision.verdict is ReviewVerdict.REQUEST_CHANGES:
                changes += 1
            elif decision.verdict is ReviewVerdict.NEEDS_CLARIFICATION:
                clarification += 1
            elif decision.verdict is ReviewVerdict.DEFER:
                deferred += 1
            else:
                abstained += 1
        else:
            relation = relation_ids.get(decision.candidate_id)
            if relation is None:
                continue
            if decision.is_stale_for(relation.revision, relation.content_hash or ""):
                stale += 1
                continue
            reviewed_relations.add(decision.candidate_id)
            if decision.verdict is ReviewVerdict.APPROVE:
                accepted_relations += 1
            elif decision.verdict is ReviewVerdict.REJECT:
                rejected_relations += 1
            elif decision.verdict is ReviewVerdict.REQUEST_CHANGES:
                changes += 1
            elif decision.verdict is ReviewVerdict.NEEDS_CLARIFICATION:
                clarification += 1
            elif decision.verdict is ReviewVerdict.DEFER:
                deferred += 1
            else:
                abstained += 1
    pending_rules = tuple(sorted(set(rule_ids) - reviewed_rules))
    pending_relations = tuple(sorted(set(relation_ids) - reviewed_relations))
    blocked_rules = sum(rule.candidate_state is CandidateState.BLOCKED for rule in graph.rules)
    blocked_relations = sum(
        relation.candidate_state is CandidateState.BLOCKED for relation in graph.relations
    )
    return ReviewStatus(
        protocol_version_id=graph.protocol_version_id,
        rule_count=len(rule_ids),
        relation_count=len(relation_ids),
        reviewed_rules=len(reviewed_rules),
        reviewed_relations=len(reviewed_relations),
        pending_rules=pending_rules,
        pending_relations=pending_relations,
        accepted_rules=accepted_rules,
        accepted_relations=accepted_relations,
        rejected_rules=rejected_rules,
        rejected_relations=rejected_relations,
        change_requests=changes,
        needs_clarification=clarification,
        deferred=deferred,
        abstained=abstained,
        blocked_rules=blocked_rules,
        blocked_relations=blocked_relations,
        stale_decisions=stale,
        decision_count=len(decisions),
        reviewer_ids=tuple(sorted(reviewers)),
    )


def dump_review_status(status: ReviewStatus) -> str:
    """Serialize the review status deterministically."""
    return (
        json.dumps(
            status.to_dict(),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def render_review_status(status: ReviewStatus) -> str:
    """Render the review status as human-readable text."""
    lines = [
        f"Review status — {status.protocol_version_id}",
        "",
        f"rules: {status.reviewed_rules}/{status.rule_count} reviewed "
        f"(pending: {len(status.pending_rules)})",
        f"relations: {status.reviewed_relations}/{status.relation_count} reviewed "
        f"(pending: {len(status.pending_relations)})",
        f"accepted: {status.accepted_rules} rules, {status.accepted_relations} relations",
        f"rejected: {status.rejected_rules} rules, {status.rejected_relations} relations",
        f"requested changes: {status.change_requests}",
        f"needs clarification: {status.needs_clarification}",
        f"deferred: {status.deferred} · abstained: {status.abstained}",
        f"blocked: {status.blocked_rules} rules, {status.blocked_relations} relations",
        f"stale decisions: {status.stale_decisions}",
        f"total decisions: {status.decision_count}",
        f"reviewers: {', '.join(status.reviewer_ids) or '—'}",
    ]
    return "\n".join(lines) + "\n"
