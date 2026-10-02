"""Generic Phase 7A clinical review workflow tests (synthetic data only).

These tests exercise decision parsing, policy evaluation, disagreement,
staleness, MODIFY semantics, missing-content feedback, approval compilation,
status summaries, and package portability with SYNTHETIC reviewers and
candidates. No real NAC/ITU approval is created or asserted.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from cpg_tree.candidates.actions import ActionSpec
from cpg_tree.candidates.enums import (
    CandidateState,
    EvidenceClass,
    IssueCategory,
    IssueSeverity,
    ObservationKind,
    RelationType,
)
from cpg_tree.candidates.evidence import EvidenceBinding
from cpg_tree.candidates.graph import CandidateGraph
from cpg_tree.candidates.graph_serialization import dump_candidate_graph
from cpg_tree.candidates.issues import Issue
from cpg_tree.candidates.observations import Observation
from cpg_tree.candidates.relations import CandidateRelation
from cpg_tree.candidates.rules import CandidateRule
from cpg_tree.candidates.variables import VariableSpec
from cpg_tree.extraction.spans import SourceSpan, SpanRepresentation
from cpg_tree.knowledge.conditions import Condition
from cpg_tree.knowledge.enums import ActionType, ConditionKind, VariableType
from cpg_tree.review.compiler import (
    can_compile,
    compilation_blockers,
    compile_approved_package,
    compile_approved_relation,
    compile_approved_rule,
)
from cpg_tree.review.feedback import ReviewFeedback, ReviewFeedbackType
from cpg_tree.review.ingestion import (
    append_review_records,
    load_review_records,
    parse_review_submission,
)
from cpg_tree.review.model import ReviewDecision, ReviewSubjectType, ReviewVerdict
from cpg_tree.review.package import build_review_package
from cpg_tree.review.package_validation import validate_review_package
from cpg_tree.review.policy import (
    ApprovalPolicy,
    PolicySatisfaction,
    current_decisions,
    evaluate_approval,
    stale_decisions,
)
from cpg_tree.review.reviewer import ReviewerRecord, ReviewerRegistry
from cpg_tree.review.status import compute_review_status

_PROTOCOL = "SYN-999-v1"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _span(span_id: str) -> SourceSpan:
    text = f"Evidence for {span_id}."
    return SourceSpan(
        span_id=span_id,
        document_id="doc-synthetic",
        extraction_run_id="run-synthetic",
        page=1,
        representation=SpanRepresentation.TEXT,
        extraction_method="test",
        extracted_text_exact=text,
        text_sha256=_sha(text),
    )


def _binding(claim_path: str, span_id: str) -> EvidenceBinding:
    return EvidenceBinding(
        claim_path=claim_path,
        evidence_class=EvidenceClass.NORMALIZED,
        source_span_refs=(span_id,),
        exact_quote=f"Evidence for {span_id}.",
    )


def _rule(
    rule_id: str,
    *,
    state: CandidateState = CandidateState.PROPOSED,
) -> CandidateRule:
    action = ActionSpec(
        action_id=f"act-{rule_id}",
        action_type=ActionType.DECISION,
        target_text=f"{rule_id} action",
        evidence_bindings=(_binding("/target_text", f"span-{rule_id}"),),
    )
    return CandidateRule(
        candidate_id=rule_id,
        revision=1,
        protocol_version_id=_PROTOCOL,
        condition=Condition(kind=ConditionKind.FLAG, variable_ref="var-a", expected=True),
        actions=(action,),
        observation_refs=(f"obs-{rule_id}",),
        evidence_class=EvidenceClass.NORMALIZED,
        evidence_bindings=(_binding("/condition", f"span-{rule_id}"),),
        candidate_state=state,
    )


def _relation(
    relation_id: str,
    source: str,
    target: str,
    relation_type: RelationType = RelationType.FLOW,
    *,
    state: CandidateState = CandidateState.PROPOSED,
) -> CandidateRelation:
    return CandidateRelation(
        candidate_relation_id=relation_id,
        revision=1,
        source_ref=source,
        target_refs=(target,),
        relation_type=relation_type,
        branch_label="condition label",
        observation_refs=(f"obs-{source}",),
        evidence_class=EvidenceClass.NORMALIZED,
        evidence_bindings=(_binding("/target_refs/0", f"span-{source}"),),
        candidate_state=state,
    )


def _graph(
    *,
    issues: tuple[Issue, ...] = (),
    blocked_rule: str | None = None,
    blocked_relation: str | None = None,
) -> CandidateGraph:
    rules = (
        _rule(
            "rule-a",
            state=CandidateState.BLOCKED if blocked_rule == "rule-a" else CandidateState.PROPOSED,
        ),
        _rule(
            "rule-b",
            state=CandidateState.BLOCKED if blocked_rule == "rule-b" else CandidateState.PROPOSED,
        ),
    )
    relations = (
        _relation(
            "rel-ab",
            "rule-a",
            "rule-b",
            state=CandidateState.BLOCKED
            if blocked_relation == "rel-ab"
            else CandidateState.PROPOSED,
        ),
    )
    spans = (
        _span("span-rule-a"),
        _span("span-rule-b"),
        _span("span-var-a"),
    )
    observations = (
        Observation(
            observation_id="obs-rule-a",
            kind=ObservationKind.RECOMMENDATION,
            span_refs=("span-rule-a",),
            exact_quote="Evidence for span-rule-a.",
        ),
        Observation(
            observation_id="obs-rule-b",
            kind=ObservationKind.RECOMMENDATION,
            span_refs=("span-rule-b",),
            exact_quote="Evidence for span-rule-b.",
        ),
    )
    variables = (
        VariableSpec(
            variable_id="var-a",
            label="synthetic flag",
            value_type=VariableType.BOOLEAN,
            evidence_bindings=(_binding("/label", "span-var-a"),),
        ),
    )
    return CandidateGraph(
        graph_id="graph-synthetic",
        generation_run_id="run-synthetic-phase7",
        protocol_version_id=_PROTOCOL,
        document_id="doc-synthetic",
        extraction_run_id="run-synthetic",
        observations=observations,
        variables=variables,
        rules=rules,
        relations=relations,
        issues=issues,
        source_spans=spans,
        attempts=(),
    )


def _reviewer(identifier: str = "rev-1") -> ReviewerRecord:
    return ReviewerRecord(
        reviewer_id=identifier,
        display_name=f"Reviewer {identifier}",
        role="médico internista",
    )


def _decision(  # noqa: PLR0913
    decision_id: str,
    candidate_id: str,
    content_hash: str,
    verdict: ReviewVerdict,
    *,
    subject_type: ReviewSubjectType = ReviewSubjectType.RULE,
    reviewer_id: str = "rev-1",
    reviewed_at: str = "2026-10-03T10:00:00Z",
    corrections: tuple[str, ...] = (),
    rationale: str | None = None,
    supersedes: str | None = None,
) -> ReviewDecision:
    return ReviewDecision(
        decision_id=decision_id,
        subject_type=subject_type,
        candidate_id=candidate_id,
        candidate_revision=1,
        candidate_content_hash=content_hash,
        verdict=verdict,
        reviewer_id=reviewer_id,
        reviewed_at=reviewed_at,
        rationale=rationale,
        proposed_corrections=corrections,
        supersedes_decision_id=supersedes,
    )


def _approve_all(graph: CandidateGraph) -> tuple[ReviewDecision, ...]:
    decisions: list[ReviewDecision] = []
    for rule in graph.rules:
        decisions.append(
            _decision(
                f"d-rule-{rule.candidate_id}",
                rule.candidate_id,
                rule.content_hash or "",
                ReviewVerdict.APPROVE,
                reviewer_id="rev-1",
            )
        )
    for relation in graph.relations:
        decisions.append(
            _decision(
                f"d-rel-{relation.candidate_relation_id}",
                relation.candidate_relation_id,
                relation.content_hash or "",
                ReviewVerdict.APPROVE,
                subject_type=ReviewSubjectType.RELATION,
                reviewer_id="rev-1",
            )
        )
    return tuple(decisions)


# --- Ingestion ----------------------------------------------------------------


def test_valid_submission_parses() -> None:
    graph = _graph()
    rule = graph.rules[0]
    data = {
        "schema": "review-submission-v1",
        "protocol_version_id": _PROTOCOL,
        "reviewer_id": "rev-1",
        "decisions": [
            {
                "decision_id": "d-1",
                "subject_type": "RULE",
                "candidate_id": rule.candidate_id,
                "candidate_revision": 1,
                "candidate_content_hash": rule.content_hash,
                "verdict": "APPROVE",
                "reviewer_id": "rev-1",
                "reviewed_at": "2026-10-03T10:00:00Z",
            }
        ],
        "feedback": [],
    }
    submission = parse_review_submission(data, graph)
    assert submission.is_valid
    assert len(submission.decisions) == 1


def test_invalid_candidate_id_rejected() -> None:
    graph = _graph()
    data = {
        "schema": "review-submission-v1",
        "protocol_version_id": _PROTOCOL,
        "reviewer_id": "rev-1",
        "decisions": [
            {
                "decision_id": "d-1",
                "subject_type": "RULE",
                "candidate_id": "rule-missing",
                "candidate_revision": 1,
                "candidate_content_hash": "a" * 64,
                "verdict": "APPROVE",
                "reviewer_id": "rev-1",
                "reviewed_at": "2026-10-03T10:00:00Z",
            }
        ],
        "feedback": [],
    }
    submission = parse_review_submission(data, graph)
    assert not submission.is_valid
    assert any(finding.code == "REVIEW_UNKNOWN_CANDIDATE" for finding in submission.findings)


def test_stale_hash_rejected() -> None:
    graph = _graph()
    rule = graph.rules[0]
    data = {
        "schema": "review-submission-v1",
        "protocol_version_id": _PROTOCOL,
        "reviewer_id": "rev-1",
        "decisions": [
            {
                "decision_id": "d-1",
                "subject_type": "RULE",
                "candidate_id": rule.candidate_id,
                "candidate_revision": 1,
                "candidate_content_hash": "b" * 64,
                "verdict": "APPROVE",
                "reviewer_id": "rev-1",
                "reviewed_at": "2026-10-03T10:00:00Z",
            }
        ],
        "feedback": [],
    }
    submission = parse_review_submission(data, graph)
    assert not submission.is_valid
    assert any(finding.code == "REVIEW_STALE_CANDIDATE_BINDING" for finding in submission.findings)


def test_cross_protocol_submission_rejected() -> None:
    graph = _graph()
    data = {
        "schema": "review-submission-v1",
        "protocol_version_id": "OTHER-001-v1",
        "reviewer_id": "rev-1",
        "decisions": [],
        "feedback": [],
    }
    submission = parse_review_submission(data, graph)
    assert not submission.is_valid
    assert any(finding.code == "REVIEW_PROTOCOL_MISMATCH" for finding in submission.findings)


def test_unknown_reviewer_rejected_when_registry_configured() -> None:
    graph = _graph()
    registry = ReviewerRegistry([_reviewer("rev-known")])
    data = {
        "schema": "review-submission-v1",
        "protocol_version_id": _PROTOCOL,
        "reviewer_id": "rev-1",
        "decisions": [],
        "feedback": [],
    }
    submission = parse_review_submission(data, graph, reviewers=registry)
    assert not submission.is_valid
    assert any(finding.code == "REVIEW_UNKNOWN_REVIEWER" for finding in submission.findings)


def test_modify_payload_must_carry_correction() -> None:
    graph = _graph()
    rule = graph.rules[0]
    base = {
        "schema": "review-submission-v1",
        "protocol_version_id": _PROTOCOL,
        "reviewer_id": "rev-1",
        "feedback": [],
    }
    malformed = {
        **base,
        "decisions": [
            {
                "decision_id": "d-1",
                "subject_type": "RULE",
                "candidate_id": rule.candidate_id,
                "candidate_revision": 1,
                "candidate_content_hash": rule.content_hash,
                "verdict": "REQUEST_CHANGES",
                "reviewer_id": "rev-1",
                "reviewed_at": "2026-10-03T10:00:00Z",
            }
        ],
    }
    assert any(
        finding.code == "REVIEW_MODIFY_PAYLOAD_MALFORMED"
        for finding in parse_review_submission(malformed, graph).findings
    )
    wellformed = {
        **base,
        "decisions": [
            {
                "decision_id": "d-1",
                "subject_type": "RULE",
                "candidate_id": rule.candidate_id,
                "candidate_revision": 1,
                "candidate_content_hash": rule.content_hash,
                "verdict": "REQUEST_CHANGES",
                "reviewer_id": "rev-1",
                "reviewed_at": "2026-10-03T10:00:00Z",
                "rationale": "threshold should differ",
                "proposed_corrections": ["use BUN > 30"],
            }
        ],
    }
    submission = parse_review_submission(wellformed, graph)
    assert submission.is_valid
    assert submission.decisions[0].proposed_corrections == ("use BUN > 30",)
    # MODIFY never changes the original candidate.
    assert rule.content_hash == _graph().rules[0].content_hash


def test_missing_rule_feedback_parsed() -> None:
    graph = _graph()
    data = {
        "schema": "review-submission-v1",
        "protocol_version_id": _PROTOCOL,
        "reviewer_id": "rev-1",
        "decisions": [],
        "feedback": [
            {
                "feedback_id": "fb-1",
                "feedback_type": "MISSING_RULE",
                "description": "the pathway lacks a reassessment step",
                "reviewed_at": "2026-10-03T10:00:00Z",
                "proposed_content": "add reassessment at 48-72 h",
            }
        ],
    }
    submission = parse_review_submission(data, graph)
    assert submission.is_valid
    assert submission.feedback
    assert submission.feedback[0].feedback_type is ReviewFeedbackType.MISSING_RULE


def test_missing_relation_feedback_parsed() -> None:
    graph = _graph()
    data = {
        "schema": "review-submission-v1",
        "protocol_version_id": _PROTOCOL,
        "reviewer_id": "rev-1",
        "decisions": [],
        "feedback": [
            {
                "feedback_id": "fb-2",
                "feedback_type": "MISSING_RELATION",
                "description": "blood cultures should also follow severe labs",
                "reviewed_at": "2026-10-03T10:00:00Z",
            }
        ],
    }
    submission = parse_review_submission(data, graph)
    assert submission.is_valid
    assert submission.feedback[0].feedback_type is ReviewFeedbackType.MISSING_RELATION


# --- Append-only history ------------------------------------------------------


def test_append_only_history_rejects_duplicates() -> None:
    graph = _graph()
    decision = _approve_all(graph)[0]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "reviews.jsonl"
        append_review_records(path, (decision,))
        with pytest.raises(ValueError, match="already contains ids"):
            append_review_records(path, (decision,))
        assert load_review_records(path) == (decision,)


# --- Policy -------------------------------------------------------------------


def test_single_reviewer_policy() -> None:
    graph = _graph()
    rule = graph.rules[0]
    decision = _decision("d-1", rule.candidate_id, rule.content_hash or "", ReviewVerdict.APPROVE)
    policy = ApprovalPolicy(name="single-reviewer", minimum_decisions=1)
    assert evaluate_approval(policy, (decision,)) is PolicySatisfaction.SATISFIED


def test_two_reviewers_both_required() -> None:
    graph = _graph()
    rule = graph.rules[0]
    one = _decision(
        "d-1",
        rule.candidate_id,
        rule.content_hash or "",
        ReviewVerdict.APPROVE,
        reviewer_id="rev-1",
    )
    two = _decision(
        "d-2",
        rule.candidate_id,
        rule.content_hash or "",
        ReviewVerdict.APPROVE,
        reviewer_id="rev-2",
    )
    policy = ApprovalPolicy(name="two-reviewers", minimum_decisions=2)
    assert evaluate_approval(policy, (one,)) is PolicySatisfaction.NOT_SATISFIED
    assert evaluate_approval(policy, (one, two)) is PolicySatisfaction.SATISFIED


def test_two_of_three_reviewers() -> None:
    graph = _graph()
    rule = graph.rules[0]
    decisions = tuple(
        _decision(
            f"d-{i}",
            rule.candidate_id,
            rule.content_hash or "",
            ReviewVerdict.APPROVE,
            reviewer_id=f"rev-{i}",
        )
        for i in (1, 2, 3)
    )
    policy = ApprovalPolicy(name="2-of-3", minimum_decisions=2)
    assert evaluate_approval(policy, decisions[:2]) is PolicySatisfaction.SATISFIED
    assert evaluate_approval(policy, decisions) is PolicySatisfaction.SATISFIED


def test_same_reviewer_does_not_count_twice() -> None:
    graph = _graph()
    rule = graph.rules[0]
    decisions = tuple(
        _decision(
            f"d-{i}",
            rule.candidate_id,
            rule.content_hash or "",
            ReviewVerdict.APPROVE,
            reviewer_id="rev-1",
        )
        for i in (1, 2)
    )
    policy = ApprovalPolicy(name="two-reviewers", minimum_decisions=2)
    assert evaluate_approval(policy, decisions) is PolicySatisfaction.NOT_SATISFIED


def test_disagreement_is_review_conflict() -> None:
    graph = _graph()
    rule = graph.rules[0]
    approve = _decision(
        "d-1",
        rule.candidate_id,
        rule.content_hash or "",
        ReviewVerdict.APPROVE,
        reviewer_id="rev-1",
    )
    reject = _decision(
        "d-2", rule.candidate_id, rule.content_hash or "", ReviewVerdict.REJECT, reviewer_id="rev-2"
    )
    policy = ApprovalPolicy(name="two-reviewers", minimum_decisions=2)
    assert evaluate_approval(policy, (approve, reject)) is PolicySatisfaction.REVIEW_CONFLICT


def test_stale_decisions_filtered() -> None:
    graph = _graph()
    rule = graph.rules[0]
    old = _decision("d-old", rule.candidate_id, "b" * 64, ReviewVerdict.APPROVE)
    assert stale_decisions((old,), revision=1, content_hash=rule.content_hash or "") == (old,)
    assert current_decisions((old,), revision=1, content_hash=rule.content_hash or "") == ()


def test_superseding_decisions_chain() -> None:
    graph = _graph()
    rule = graph.rules[0]
    first = _decision(
        "d-1",
        rule.candidate_id,
        rule.content_hash or "",
        ReviewVerdict.REQUEST_CHANGES,
        corrections=("fix",),
        rationale="needs fix",
    )
    second = _decision(
        "d-2", rule.candidate_id, rule.content_hash or "", ReviewVerdict.APPROVE, supersedes="d-1"
    )
    assert first.proposed_corrections == ("fix",)
    assert second.supersedes_decision_id == "d-1"


# --- Compiler (synthetic only) ------------------------------------------------


def test_full_approval_compiles_snapshot() -> None:
    graph = _graph()
    decisions = _approve_all(graph)
    assert can_compile(graph, decisions, ApprovalPolicy(name="single", minimum_decisions=1))
    package = compile_approved_package(
        graph, decisions, ApprovalPolicy(name="single", minimum_decisions=1)
    )
    assert set(package.rules) == {"rule-a", "rule-b"}
    assert set(package.relations) == {"rel-ab"}
    approved = package.rules["rule-a"]
    assert approved.source_candidate_content_hash == graph.rules[0].content_hash
    assert approved.approved_content_hash == graph.rules[0].content_hash


def test_rejected_candidate_cannot_compile() -> None:
    graph = _graph()
    decisions = list(_approve_all(graph))
    rule = graph.rules[0]
    decisions.append(
        _decision(
            "d-reject",
            rule.candidate_id,
            rule.content_hash or "",
            ReviewVerdict.REJECT,
            reviewer_id="rev-2",
        )
    )
    assert not can_compile(
        graph, tuple(decisions), ApprovalPolicy(name="single", minimum_decisions=1)
    )
    blockers = compilation_blockers(
        graph, tuple(decisions), ApprovalPolicy(name="single", minimum_decisions=1)
    )
    assert any(blocker.code == "REVIEW_CONFLICT" for blocker in blockers)


def test_mutation_after_review_triggers_staleness() -> None:
    graph = _graph()
    decisions = _approve_all(graph)
    mutated_rules = tuple(
        replace(
            rule,
            condition=Condition(kind=ConditionKind.FLAG, variable_ref="var-a", expected=False),
            content_hash=None,
        )
        if rule.candidate_id == "rule-a"
        else rule
        for rule in graph.rules
    )
    mutated = replace(graph, rules=mutated_rules)
    assert not can_compile(mutated, decisions, ApprovalPolicy(name="single", minimum_decisions=1))


def test_blocked_candidate_blocks_compilation() -> None:
    graph = _graph(blocked_rule="rule-a")
    decisions = _approve_all(graph)
    assert not can_compile(graph, decisions, ApprovalPolicy(name="single", minimum_decisions=1))


def test_blocking_issue_blocks_compilation_when_required() -> None:
    graph = _graph(
        issues=(
            Issue(
                issue_id="issue-x",
                category=IssueCategory.SOURCE_CONFLICT,
                severity=IssueSeverity.BLOCKING,
                description="conflict",
                related_ids=("rule-a",),
            ),
        )
    )
    decisions = _approve_all(graph)
    assert can_compile(
        graph,
        decisions,
        ApprovalPolicy(name="single", minimum_decisions=1),
        require_blocking_resolved=False,
    )
    assert not can_compile(graph, decisions, ApprovalPolicy(name="single", minimum_decisions=1))


def test_compile_single_rule_and_relation() -> None:
    graph = _graph()
    rule_decision = _approve_all(graph)[0]
    relation_decision = _approve_all(graph)[2]
    approved_rule = compile_approved_rule(graph.rules[0], rule_decision)
    approved_relation = compile_approved_relation(graph.relations[0], relation_decision)
    assert approved_rule.approval_decision_id == rule_decision.decision_id
    assert approved_relation.approval_decision_id == relation_decision.decision_id


# --- Status -------------------------------------------------------------------


def test_review_status_counts() -> None:
    graph = _graph()
    decisions = _approve_all(graph)[:1]
    status = compute_review_status(graph, decisions)
    assert status.rule_count == len(graph.rules)
    assert status.relation_count == len(graph.relations)
    assert status.reviewed_rules == 1
    assert status.reviewed_relations == 0
    assert status.pending_rules == ("rule-b",)
    assert status.accepted_rules == 1
    assert status.stale_decisions == 0
    stale = _decision("d-stale", "rule-a", "b" * 64, ReviewVerdict.APPROVE)
    stale_status = compute_review_status(graph, (stale,))
    assert stale_status.stale_decisions == 1


# --- Package portability ------------------------------------------------------


def test_review_package_built_portable_and_hash_bound() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        graph = _graph()
        graph_json = root / "candidate_graph.json"
        graph_json.write_text(dump_candidate_graph(graph), encoding="utf-8")
        phase5 = root / "phase5"
        phase5.mkdir()
        (phase5 / "review_summary.md").write_text("# summary\n", encoding="utf-8")
        (phase5 / "clinical_review_questions.md").write_text("# questions\n", encoding="utf-8")
        phase6 = root / "phase6"
        phase6.mkdir()
        (phase6 / "review_tree.html").write_text("<html>tree</html>\n", encoding="utf-8")
        (phase6 / "review_tree.svg").write_text("<svg></svg>\n", encoding="utf-8")
        (phase6 / "validation_report.md").write_text("# report\n", encoding="utf-8")
        (phase6 / "review_manifest.json").write_text(
            json.dumps({"document_sha256": "c" * 64, "validation_report_sha256": "d" * 64}),
            encoding="utf-8",
        )
        phase7 = root / "phase7"
        phase7.mkdir()
        (phase7 / "review_questions.md").write_text("# clinician questions\n", encoding="utf-8")
        payload = build_review_package(
            graph=graph,
            phase5_dir=phase5,
            phase6_dir=phase6,
            phase7_dir=phase7,
            review_questions_path=phase7 / "review_questions.md",
            project_root=root,
        )
        assert payload["status"] == "AWAITING_CLINICAL_REVIEW"
        assert payload["approved_rules"] == 0
        assert payload["approval_policy"] == "policy_pending"
        findings = validate_review_package(phase7, graph, project_root=root)
        assert not [finding for finding in findings if finding.severity.value == "ERROR"]
        for entry in payload["bundle_files"]:
            assert not Path(entry["path"]).is_absolute()
            assert ".." not in Path(entry["path"]).parts
        relocated = Path(tmp) / "other-checkout"
        shutil.copytree(root, relocated, dirs_exist_ok=True)
        relocated_manifest = json.loads(
            (relocated / "phase7" / "review_manifest.json").read_text(encoding="utf-8")
        )
        for entry in relocated_manifest["bundle_files"]:
            target = relocated / Path(entry["path"])
            assert target.exists()
            assert entry["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()


def test_reviewer_registry_and_verdicts() -> None:
    registry = ReviewerRegistry([_reviewer()])
    assert "rev-1" in registry
    assert registry.get("rev-1").role == "médico internista"
    assert "rev-2" not in registry
    assert ReviewVerdict.NEEDS_CLARIFICATION.value == "NEEDS_CLARIFICATION"
    assert ReviewVerdict.DEFER.value == "DEFER"
    feedback = ReviewFeedback(
        feedback_id="fb-1",
        feedback_type=ReviewFeedbackType.MISSING_BRANCH,
        description="missing discharge branch",
        reviewer_id="rev-1",
        reviewed_at="2026-10-03T10:00:00Z",
        protocol_version_id=_PROTOCOL,
    )
    assert feedback.feedback_type is ReviewFeedbackType.MISSING_BRANCH
