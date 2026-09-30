"""Tests for ApprovedRule, ApprovedRelation, and ApprovedKnowledgePackage."""

from __future__ import annotations

import pytest

from cpg_tree.candidates import (
    ActionSpec,
    CandidateRule,
    EvidenceBinding,
    EvidenceClass,
    Issue,
    IssueCategory,
    IssueSeverity,
    RelationType,
    VariableSpec,
)
from cpg_tree.extraction import SourceSpan, SpanRepresentation
from cpg_tree.knowledge import (
    ActionType,
    ComparisonOperator,
    Condition,
    ConditionKind,
    SourceDocument,
    VariableType,
)
from cpg_tree.knowledge.approved import (
    APPROVED_KNOWLEDGE_PACKAGE_SCHEMA_VERSION,
    ApprovedKnowledgePackage,
    ApprovedRelation,
    ApprovedRule,
)
from cpg_tree.review import ReviewDecision, ReviewSubjectType, ReviewVerdict

VALID_SHA256 = "3a1654757801b7b618661f846f8335ced6fb9e388891d6bca96f1cd81d6f5882"
SHA256_LENGTH = 64

BUN_GT_30 = Condition(
    kind=ConditionKind.COMPARISON,
    variable_ref="bun",
    operator=ComparisonOperator.GT,
    operand=30,
)


def make_candidate() -> CandidateRule:
    return CandidateRule(
        candidate_id="cand-nac-001",
        revision=1,
        protocol_version_id="CT-PL-193-v09",
        condition=BUN_GT_30,
        evidence_class=EvidenceClass.SOURCE_STATED,
    )


def make_decision(candidate: CandidateRule) -> ReviewDecision:
    return ReviewDecision(
        decision_id="dec-1",
        subject_type=ReviewSubjectType.RULE,
        candidate_id=candidate.candidate_id,
        candidate_revision=candidate.revision,
        candidate_content_hash=candidate.content_hash or "",
        verdict=ReviewVerdict.APPROVE,
        reviewer_id="reviewer-dr-garcia",
        reviewed_at="2026-09-29T15:00:00",
    )


def make_approved_rule(**overrides: object) -> ApprovedRule:
    candidate = make_candidate()
    fields: dict[str, object] = {
        "approved_rule_id": "apr-nac-001",
        "source_candidate_id": candidate.candidate_id,
        "source_candidate_revision": candidate.revision,
        "source_candidate_content_hash": candidate.content_hash or "",
        "approval_decision_id": "dec-1",
        "approved_by": "reviewer-dr-garcia",
        "approved_at": "2026-09-29T15:05:00",
        "condition": BUN_GT_30,
        "evidence_class": EvidenceClass.SOURCE_STATED,
    }
    fields.update(overrides)
    return ApprovedRule(**fields)  # type: ignore[arg-type]


def test_approved_rule_is_immutable_snapshot() -> None:
    approved = make_approved_rule()
    assert approved.approved_content_hash is not None
    assert len(approved.approved_content_hash) == SHA256_LENGTH


def test_approved_rule_hash_equals_unmodified_candidate_hash() -> None:
    candidate = make_candidate()
    approved = make_approved_rule(
        source_candidate_content_hash=candidate.content_hash or "",
    )
    assert approved.approved_content_hash == candidate.content_hash


def test_approved_rule_rejects_mismatched_content_hash() -> None:
    with pytest.raises(ValueError, match="approved_content_hash"):
        make_approved_rule(approved_content_hash="0" * 64)


def test_approved_rule_never_changes_when_candidate_changes() -> None:
    candidate = make_candidate()
    approved = make_approved_rule(
        source_candidate_content_hash=candidate.content_hash or "",
    )
    changed = CandidateRule(
        candidate_id="cand-nac-001",
        revision=2,
        protocol_version_id="CT-PL-193-v09",
        condition=Condition(
            kind=ConditionKind.COMPARISON,
            variable_ref="bun",
            operator=ComparisonOperator.GT,
            operand=20,
        ),
        evidence_class=EvidenceClass.SOURCE_STATED,
    )
    assert approved.references_source_candidate(
        "cand-nac-001", candidate.revision, candidate.content_hash or ""
    )
    assert not approved.references_source_candidate(
        "cand-nac-001", changed.revision, changed.content_hash or ""
    )
    assert approved.approved_content_hash != changed.content_hash


def test_approved_relation_snapshot() -> None:
    relation = ApprovedRelation(
        approved_relation_id="apr-rel-1",
        source_candidate_relation_id="rel-1",
        source_candidate_revision=1,
        source_candidate_content_hash="a" * 64,
        approval_decision_id="dec-rel-1",
        approved_by="reviewer-dr-garcia",
        approved_at="2026-09-29T15:05:00",
        source_ref="apr-nac-001",
        target_refs=("apr-nac-002",),
        relation_type=RelationType.FLOW,
        evidence_class=EvidenceClass.SOURCE_STATED,
    )
    assert relation.approved_content_hash is not None


def _build_package(**overrides: object) -> ApprovedKnowledgePackage:
    approved_rule = make_approved_rule()
    candidate = make_candidate()
    span = SourceSpan(
        span_id="span-1",
        document_id="doc-1",
        extraction_run_id="run-1",
        page=3,
        representation=SpanRepresentation.TEXT,
        extraction_method="pypdf-text",
    )
    document = SourceDocument(
        document_id="doc-1",
        filename="CT-PL-193_v09.pdf",
        sha256=VALID_SHA256,
    )
    fields: dict[str, object] = {
        "schema_version": APPROVED_KNOWLEDGE_PACKAGE_SCHEMA_VERSION,
        "package_id": "pkg-CT-PL-193-v09",
        "protocol_id": "CT-PL-193",
        "protocol_version": "v09",
        "source_documents": {"doc-1": document},
        "spans": {"span-1": span},
        "rules": {approved_rule.approved_rule_id: approved_rule},
        "review_decisions": {"dec-1": make_decision(candidate)},
        "build_manifest": {"compiler": "phase-7-compiler"},
    }
    fields.update(overrides)
    return ApprovedKnowledgePackage(**fields)  # type: ignore[arg-type]


def test_approved_package_construction() -> None:
    package = _build_package()
    assert package.schema_version == APPROVED_KNOWLEDGE_PACKAGE_SCHEMA_VERSION
    assert list(package.rules) == ["apr-nac-001"]


def test_approved_package_rejects_unknown_schema_version() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        _build_package(schema_version="approved-knowledge-package-v999")


def test_approved_package_rejects_key_mismatch() -> None:
    approved_rule = make_approved_rule()
    with pytest.raises(ValueError, match="rules"):
        _build_package(rules={"wrong-key": approved_rule})


def test_approved_package_rejects_blocking_accepted_issue() -> None:
    blocking = Issue(
        issue_id="issue-blocking",
        category=IssueCategory.SOURCE_CONFLICT,
        severity=IssueSeverity.BLOCKING,
        description="conflict",
    )
    with pytest.raises(ValueError, match="BLOCKING"):
        _build_package(accepted_issues={"issue-blocking": blocking})


def test_approved_package_accepts_non_blocking_accepted_issue() -> None:
    non_blocking = Issue(
        issue_id="issue-known",
        category=IssueCategory.EXTRACTION_LIMITATION,
        severity=IssueSeverity.NON_BLOCKING,
        description="table cell alignment uncertain",
    )
    package = _build_package(accepted_issues={"issue-known": non_blocking})
    assert list(package.accepted_issues) == ["issue-known"]


def test_approved_package_carries_variables_and_actions_as_specs() -> None:
    package = _build_package(
        variables={
            "bun": VariableSpec(
                variable_id="bun",
                label="BUN",
                value_type=VariableType.NUMERIC,
                unit="mg/dL",
            )
        },
        actions={
            "act-1": ActionSpec(
                action_id="act-1",
                action_type=ActionType.PRESCRIBE,
                target_text="ceftriaxone",
                evidence_bindings=(
                    EvidenceBinding(
                        claim_path="/target_text",
                        evidence_class=EvidenceClass.SOURCE_STATED,
                        source_span_refs=("span-1",),
                        exact_quote="ceftriaxona",
                    ),
                ),
            )
        },
    )
    assert list(package.variables) == ["bun"]
    assert list(package.actions) == ["act-1"]
