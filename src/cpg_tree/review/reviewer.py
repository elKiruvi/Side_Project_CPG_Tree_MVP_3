"""Reviewer identity records for the clinical review workflow.

A reviewer identity is the minimum audit metadata needed to attribute a
``ReviewDecision``: an identifier, a display name, and a role. It stores no
sensitive credentials; authentication is out of scope for this phase. An
optional registry validates that submitted decisions come from known
reviewers without ever becoming an authorization mechanism.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from cpg_tree.knowledge._validation import validate_identifier


@dataclass(frozen=True, slots=True)
class ReviewerRecord:
    """Non-sensitive identity of one qualified reviewer."""

    reviewer_id: str
    display_name: str
    role: str
    organization: str | None = None

    def __post_init__(self) -> None:
        validate_identifier(self.reviewer_id, "ReviewerRecord.reviewer_id")
        if not self.display_name:
            raise ValueError("ReviewerRecord.display_name must not be empty")
        if not self.role:
            raise ValueError("ReviewerRecord.role must not be empty")
        if self.organization is not None and not self.organization:
            raise ValueError("ReviewerRecord.organization must not be empty when set")


class ReviewerRegistry:
    """Immutable, optional registry of known reviewers.

    The registry is audit metadata, not authentication: it rejects decisions
    from unknown reviewer ids when configured, but it cannot prove who
    submitted them.
    """

    def __init__(self, reviewers: Iterable[ReviewerRecord]) -> None:
        self._reviewers = {record.reviewer_id: record for record in reviewers}
        if len(self._reviewers) != len(list(reviewers)):
            raise ValueError("ReviewerRegistry contains duplicate reviewer ids")

    def contains(self, reviewer_id: str) -> bool:
        """True when the reviewer id is known."""
        return reviewer_id in self._reviewers

    def get(self, reviewer_id: str) -> ReviewerRecord | None:
        """Return the record for a known reviewer id, or None."""
        return self._reviewers.get(reviewer_id)

    def to_dict(self) -> dict[str, Mapping[str, str | None]]:
        """Deterministic registry representation."""
        return {
            reviewer_id: {
                "reviewer_id": record.reviewer_id,
                "display_name": record.display_name,
                "role": record.role,
                **({"organization": record.organization} if record.organization else {}),
            }
            for reviewer_id, record in sorted(self._reviewers.items())
        }

    def __len__(self) -> int:
        return len(self._reviewers)

    def __contains__(self, reviewer_id: str) -> bool:
        return reviewer_id in self._reviewers
