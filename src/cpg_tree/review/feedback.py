"""Review feedback for content the reviewer considers missing.

Review cannot assume all required content already exists: clinicians must be
able to report missing decisions, conditions, actions, branches, relations,
or evidence. A feedback record is review input, never an automatically
created ``ApprovedRule`` or ``ApprovedRelation``: it becomes material for a
future candidate revision.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cpg_tree.knowledge._validation import validate_identifier, validate_iso_datetime


class ReviewFeedbackType(StrEnum):
    """Kinds of missing-content feedback a reviewer can report."""

    MISSING_RULE = "MISSING_RULE"
    MISSING_RELATION = "MISSING_RELATION"
    MISSING_DECISION = "MISSING_DECISION"
    MISSING_CONDITION = "MISSING_CONDITION"
    MISSING_ACTION = "MISSING_ACTION"
    MISSING_BRANCH = "MISSING_BRANCH"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"


@dataclass(frozen=True, slots=True)
class ReviewFeedback:
    """One structured missing-content report from a reviewer."""

    feedback_id: str
    feedback_type: ReviewFeedbackType
    description: str
    reviewer_id: str
    reviewed_at: str
    protocol_version_id: str
    proposed_content: str | None = None
    related_ids: tuple[str, ...] = ()
    evidence_reference: str | None = None

    def __post_init__(self) -> None:
        validate_identifier(self.feedback_id, "ReviewFeedback.feedback_id")
        validate_identifier(self.reviewer_id, "ReviewFeedback.reviewer_id")
        validate_identifier(self.protocol_version_id, "ReviewFeedback.protocol_version_id")
        validate_iso_datetime(self.reviewed_at, "ReviewFeedback.reviewed_at")
        if not self.description:
            raise ValueError("ReviewFeedback.description must not be empty")
        if self.proposed_content is not None and not self.proposed_content:
            raise ValueError("ReviewFeedback.proposed_content must not be empty when set")
        for related in self.related_ids:
            validate_identifier(related, "ReviewFeedback.related_ids entry")
        if self.evidence_reference is not None and not self.evidence_reference:
            raise ValueError("ReviewFeedback.evidence_reference must not be empty when set")
