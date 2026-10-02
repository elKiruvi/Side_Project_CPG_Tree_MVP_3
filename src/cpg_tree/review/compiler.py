"""Generic approval compiler (Phase 7B interface).

The compiler can produce ``ApprovedRule`` / ``ApprovedRelation`` /
``ApprovedKnowledgePackage`` snapshots ONLY from real, valid, current
``ReviewDecision`` records satisfying the configured ``ApprovalPolicy``.

- Stale decisions never count.
- ``REQUEST_CHANGES``/``REJECT`` block approval; coexistence with acceptance
  is ``REVIEW_CONFLICT`` and never silently resolved.
- A ``REQUEST_CHANGES`` decision never mutates the candidate: the correction
  is recorded for a future, explicitly revalidated candidate revision.
- BLOCKED candidates and candidates linked to blocking Issues prevent
  approval while ``require_blocking_resolved`` is set.
- The compiler is tested exclusively with synthetic fixtures; no real NAC/ITU
  package is compiled in this phase.
"""

# ruff: noqa: PLR0913

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cpg_tree.candidates.enums import CandidateState, IssueSeverity
from cpg_tree.candidates.graph import CandidateGraph
from cpg_tree.candidates.relations import CandidateRelation
from cpg_tree.candidates.rules import CandidateRule
from cpg_tree.knowledge.approved import (
    APPROVED_KNOWLEDGE_PACKAGE_SCHEMA_VERSION,
    ApprovedKnowledgePackage,
    ApprovedRelation,
    ApprovedRule,
)
from cpg_tree.review.model import ReviewDecision, ReviewSubjectType, ReviewVerdict
from cpg_tree.review.policy import ApprovalPolicy, PolicySatisfaction, evaluate_approval

COMPILATION_BLOCKED = "COMPILATION_BLOCKED"


@dataclass(frozen=True, slots=True)
class CompilationBlocker:
    """One deterministic reason a candidate cannot be compiled to approved knowledge."""

    code: str
    candidate_id: str
    message: str


def compilation_blockers(
    graph: CandidateGraph,
    decisions: tuple[ReviewDecision, ...],
    policy: ApprovalPolicy,
    *,
    require_blocking_resolved: bool = True,
) -> tuple[CompilationBlocker, ...]:
    """Compute every reason compilation of the whole graph cannot proceed."""
    blockers: list[CompilationBlocker] = []
    issues_by_related = {related: issue for issue in graph.issues for related in issue.related_ids}
    for rule in graph.rules:
        decision = _decision_for(
            decisions,
            ReviewSubjectType.RULE,
            rule.candidate_id,
            rule.revision,
            rule.content_hash or "",
        )
        rule_blockers = _candidate_blockers(
            candidate_id=rule.candidate_id,
            candidate_state=rule.candidate_state,
            issues=tuple(
                issue
                for related, issue in issues_by_related.items()
                if related == rule.candidate_id
            ),
            decisions=decision,
            policy=policy,
            require_blocking_resolved=require_blocking_resolved,
        )
        blockers.extend(rule_blockers)
    for relation in graph.relations:
        decision = _decision_for(
            decisions,
            ReviewSubjectType.RELATION,
            relation.candidate_relation_id,
            relation.revision,
            relation.content_hash or "",
        )
        relation_blockers = _candidate_blockers(
            candidate_id=relation.candidate_relation_id,
            candidate_state=relation.candidate_state,
            issues=tuple(
                issue
                for related, issue in issues_by_related.items()
                if related == relation.candidate_relation_id
            ),
            decisions=decision,
            policy=policy,
            require_blocking_resolved=require_blocking_resolved,
        )
        blockers.extend(relation_blockers)
    return tuple(blockers)


def _candidate_blockers(
    *,
    candidate_id: str,
    candidate_state: CandidateState,
    issues: tuple[Any, ...],
    decisions: tuple[ReviewDecision, ...],
    policy: ApprovalPolicy,
    require_blocking_resolved: bool,
) -> tuple[CompilationBlocker, ...]:
    blockers: list[CompilationBlocker] = []
    if candidate_state is CandidateState.BLOCKED:
        blockers.append(
            CompilationBlocker(
                code=COMPILATION_BLOCKED,
                candidate_id=candidate_id,
                message="candidate is BLOCKED and cannot be approved before adjudication",
            )
        )
    blocking_issues = [issue for issue in issues if issue.severity is IssueSeverity.BLOCKING]
    if require_blocking_resolved and blocking_issues:
        blockers.append(
            CompilationBlocker(
                code=COMPILATION_BLOCKED,
                candidate_id=candidate_id,
                message=(
                    f"candidate is linked to blocking Issue(s) "
                    f"{[issue.issue_id for issue in blocking_issues]}"
                ),
            )
        )
    outcome = evaluate_approval(policy, decisions)
    if outcome is not PolicySatisfaction.SATISFIED:
        blockers.append(
            CompilationBlocker(
                code=outcome.value,
                candidate_id=candidate_id,
                message=(
                    "approval policy is not satisfied"
                    if outcome is PolicySatisfaction.NOT_SATISFIED
                    else "reviewers disagree; adjudication is required"
                ),
            )
        )
    return tuple(blockers)


def _decision_for(
    decisions: tuple[ReviewDecision, ...],
    subject_type: ReviewSubjectType,
    candidate_id: str,
    revision: int,
    content_hash: str,
) -> tuple[ReviewDecision, ...]:
    current = tuple(
        decision
        for decision in decisions
        if decision.subject_type is subject_type
        and decision.candidate_id == candidate_id
        and decision.candidate_revision == revision
        and decision.candidate_content_hash == content_hash
    )
    return current


def can_compile(
    graph: CandidateGraph,
    decisions: tuple[ReviewDecision, ...],
    policy: ApprovalPolicy,
    *,
    require_blocking_resolved: bool = True,
) -> bool:
    """True when the complete graph can be compiled to approved knowledge."""
    return not compilation_blockers(
        graph, decisions, policy, require_blocking_resolved=require_blocking_resolved
    )


def compile_approved_rule(rule: CandidateRule, decision: ReviewDecision) -> ApprovedRule:
    """Snapshot one approved rule from the exact reviewed candidate content."""
    if decision.verdict is not ReviewVerdict.APPROVE:
        raise ValueError("only APPROVE decisions can compile an approved rule")
    if not rule.is_current_revision(decision.candidate_revision, decision.candidate_content_hash):
        raise ValueError("decision does not match the current rule revision")
    return ApprovedRule(
        approved_rule_id=rule.candidate_id,
        source_candidate_id=rule.candidate_id,
        source_candidate_revision=rule.revision,
        source_candidate_content_hash=rule.content_hash or "",
        approval_decision_id=decision.decision_id,
        approved_by=decision.reviewer_id,
        approved_at=decision.reviewed_at,
        condition=rule.condition,
        evidence_class=rule.evidence_class,
        observation_refs=rule.observation_refs,
        applies_to=rule.applies_to,
        actions=rule.actions,
        exceptions=rule.exceptions,
        modality=rule.modality,
        statement_kind=rule.statement_kind,
        evidence_bindings=rule.evidence_bindings,
    )


def compile_approved_relation(
    relation: CandidateRelation, decision: ReviewDecision
) -> ApprovedRelation:
    """Snapshot one approved relation from the exact reviewed candidate content."""
    if decision.verdict is not ReviewVerdict.APPROVE:
        raise ValueError("only APPROVE decisions can compile an approved relation")
    if not relation.is_current_revision(
        decision.candidate_revision, decision.candidate_content_hash
    ):
        raise ValueError("decision does not match the current relation revision")
    return ApprovedRelation(
        approved_relation_id=relation.candidate_relation_id,
        source_candidate_relation_id=relation.candidate_relation_id,
        source_candidate_revision=relation.revision,
        source_candidate_content_hash=relation.content_hash or "",
        approval_decision_id=decision.decision_id,
        approved_by=decision.reviewer_id,
        approved_at=decision.reviewed_at,
        source_ref=relation.source_ref,
        target_refs=relation.target_refs,
        relation_type=relation.relation_type,
        evidence_class=relation.evidence_class,
        observation_refs=relation.observation_refs,
        branch_label=relation.branch_label,
        temporal_qualifier=relation.temporal_qualifier,
        evidence_bindings=relation.evidence_bindings,
    )


def compile_approved_package(
    graph: CandidateGraph,
    decisions: tuple[ReviewDecision, ...],
    policy: ApprovalPolicy,
    *,
    require_blocking_resolved: bool = True,
    accepted_non_blocking_issues: tuple[str, ...] = (),
) -> ApprovedKnowledgePackage:
    """Compile the full approved knowledge package, or raise with all blockers.

    Compilation is strict: every rule and every relation must individually
    satisfy the policy with current decisions, no candidate may be BLOCKED,
    and no blocking Issue may remain unresolved (when configured). The
    package never contains content the reviewers did not approve.
    """
    blockers = compilation_blockers(
        graph, decisions, policy, require_blocking_resolved=require_blocking_resolved
    )
    if blockers:
        raise ValueError(
            f"cannot compile approved package: {[(item.code, item.candidate_id) for item in blockers]}"
        )
    approved_rules: dict[str, ApprovedRule] = {}
    approved_relations: dict[str, ApprovedRelation] = {}
    decision_by_rule: dict[str, ReviewDecision] = {}
    decision_by_relation: dict[str, ReviewDecision] = {}
    for decision in decisions:
        if decision.verdict is not ReviewVerdict.APPROVE:
            continue
        if decision.subject_type is ReviewSubjectType.RULE:
            decision_by_rule[decision.candidate_id] = decision
        else:
            decision_by_relation[decision.candidate_id] = decision
    for rule in graph.rules:
        decision = decision_by_rule.get(rule.candidate_id)
        if decision is None:
            raise ValueError(f"no APPROVE decision for rule {rule.candidate_id}")
        approved_rules[rule.candidate_id] = compile_approved_rule(rule, decision)
    for relation in graph.relations:
        decision = decision_by_relation.get(relation.candidate_relation_id)
        if decision is None:
            raise ValueError(f"no APPROVE decision for relation {relation.candidate_relation_id}")
        approved_relations[relation.candidate_relation_id] = compile_approved_relation(
            relation, decision
        )
    accepted_issues = {
        issue.issue_id: issue
        for issue in graph.issues
        if issue.issue_id in accepted_non_blocking_issues
    }
    return ApprovedKnowledgePackage(
        schema_version=APPROVED_KNOWLEDGE_PACKAGE_SCHEMA_VERSION,
        package_id=f"approved-{graph.protocol_version_id}",
        protocol_id=graph.protocol_version_id.split("-")[0],
        protocol_version=graph.protocol_version_id.split("-v")[-1],
        source_documents={},
        variables={variable.variable_id: variable for variable in graph.variables},
        actions={
            action.action_id: action for rule in approved_rules.values() for action in rule.actions
        },
        rules=approved_rules,
        relations=approved_relations,
        spans={span.span_id: span for span in graph.source_spans},
        review_decisions={decision.decision_id: decision for decision in decisions},
        accepted_issues=accepted_issues,
        build_manifest={
            "policy": policy.name,
            "compiler": "cpg_tree.review.compiler",
        },
    )
