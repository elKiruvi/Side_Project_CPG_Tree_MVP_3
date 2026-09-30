"""Issue: explicit ambiguity, conflict, gap, or extraction limitation."""

from __future__ import annotations

from dataclasses import dataclass

from cpg_tree.candidates.enums import IssueCategory, IssueSeverity, IssueStatus
from cpg_tree.knowledge._validation import validate_identifier


@dataclass(frozen=True, slots=True)
class Issue:
    """An unresolved problem in the candidate inventory.

    Severity and resolution state are separate. A ``BLOCKING`` Issue prevents
    compilation but never erases candidates or evidence; an ``OPEN`` Issue is
    preserved for human review, and resolving it does not rewrite history.
    """

    issue_id: str
    category: IssueCategory
    severity: IssueSeverity
    description: str
    related_ids: tuple[str, ...] = ()
    status: IssueStatus = IssueStatus.OPEN

    def __post_init__(self) -> None:
        validate_identifier(self.issue_id, "Issue.issue_id")
        if not self.description:
            raise ValueError("Issue.description must not be empty")
        for related in self.related_ids:
            validate_identifier(related, "Issue.related_ids entry")
