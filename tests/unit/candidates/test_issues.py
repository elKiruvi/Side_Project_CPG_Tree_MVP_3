"""Tests for the Issue domain contract."""

from __future__ import annotations

import pytest

from cpg_tree.candidates import (
    Issue,
    IssueCategory,
    IssueSeverity,
    IssueStatus,
)


def test_issue_construction() -> None:
    issue = Issue(
        issue_id="issue-bun-conflict",
        category=IssueCategory.SOURCE_CONFLICT,
        severity=IssueSeverity.BLOCKING,
        description="narrative threshold differs from flowchart threshold",
        related_ids=("cand-nac-001", "obs-flow-7"),
    )
    assert issue.severity is IssueSeverity.BLOCKING
    assert issue.status is IssueStatus.OPEN


def test_issue_generic_representation_of_conflicts() -> None:
    """A source conflict is represented generically, without protocol-specific meaning."""
    narrative = Issue(
        issue_id="issue-a",
        category=IssueCategory.SOURCE_CONFLICT,
        severity=IssueSeverity.BLOCKING,
        description="two source representations disagree",
    )
    table = Issue(
        issue_id="issue-b",
        category=IssueCategory.TABLE_ALIGNMENT,
        severity=IssueSeverity.NON_BLOCKING,
        description="cell-to-footnote alignment uncertain",
    )
    assert narrative.category is not table.category
    assert narrative.category.value == "SOURCE_CONFLICT"


def test_blocking_issue_never_erases_evidence() -> None:
    issue = Issue(
        issue_id="issue-x",
        category=IssueCategory.MISSING_EVIDENCE,
        severity=IssueSeverity.BLOCKING,
        description="no bindable source span",
        related_ids=("cand-1",),
    )
    assert issue.related_ids == ("cand-1",)
    assert issue.status is IssueStatus.OPEN


def test_issue_requires_description() -> None:
    with pytest.raises(ValueError, match="description"):
        Issue(
            issue_id="issue-x",
            category=IssueCategory.AMBIGUITY,
            severity=IssueSeverity.NON_BLOCKING,
            description="",
        )


def test_issue_supports_all_handoff_categories() -> None:
    expected = {
        "AMBIGUITY",
        "SOURCE_CONFLICT",
        "MISSING_EVIDENCE",
        "EXTRACTION_LIMITATION",
        "SOURCE_CONTENT_ABSENT",
        "TABLE_ALIGNMENT",
        "NEGATION_UNCERTAIN",
        "UNIT_UNCERTAIN",
        "RELATION_UNCERTAIN",
        "OUT_OF_SCOPE",
    }
    assert {category.value for category in IssueCategory} == expected
