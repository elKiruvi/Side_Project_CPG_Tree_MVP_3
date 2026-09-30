"""ReviewDecision: append-only human decisions over exact candidate revisions."""

# ruff: noqa: TRY004

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cpg_tree.candidates.hashing import validate_sha256_hex
from cpg_tree.knowledge._validation import validate_identifier, validate_iso_datetime

_MIN_REVISION: int = 1


class ReviewVerdict(StrEnum):
    """Verdict a reviewer can record for one exact candidate revision."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    ABSTAIN = "ABSTAIN"


class ReviewSubjectType(StrEnum):
    """What kind of candidate a decision refers to."""

    RULE = "RULE"
    RELATION = "RELATION"


@dataclass(frozen=True, slots=True)
class ChecklistAnswer:
    """One answered question of the review checklist."""

    question: str
    answer: str

    def __post_init__(self) -> None:
        if not self.question:
            raise ValueError("ChecklistAnswer.question must not be empty")
        if not self.answer:
            raise ValueError("ChecklistAnswer.answer must not be empty")


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    """One append-only human decision over an exact candidate revision.

    The decision binds to the exact ``candidate_revision`` and
    ``candidate_content_hash`` that was reviewed; a decision about any other
    revision or content is stale and never counts toward approval. The
    reviewer policy (how many decisions and of which verdicts satisfy
    approval) is configurable outside this entity; this entity only records
    one auditable decision. ``supersedes_decision_id`` links the append-only
    chain: superseding creates a new decision and never mutates history.
    """

    decision_id: str
    subject_type: ReviewSubjectType
    candidate_id: str
    candidate_revision: int
    candidate_content_hash: str
    verdict: ReviewVerdict
    reviewer_id: str
    reviewed_at: str
    rationale: str | None = None
    checklist_answers: tuple[ChecklistAnswer, ...] = ()
    proposed_corrections: tuple[str, ...] = ()
    supersedes_decision_id: str | None = None

    def __post_init__(self) -> None:
        validate_identifier(self.decision_id, "ReviewDecision.decision_id")
        validate_identifier(self.candidate_id, "ReviewDecision.candidate_id")
        if isinstance(self.candidate_revision, bool) or not isinstance(
            self.candidate_revision, int
        ):
            raise ValueError("ReviewDecision.candidate_revision must be an integer")
        if self.candidate_revision < _MIN_REVISION:
            raise ValueError("ReviewDecision.candidate_revision must be positive")
        validate_sha256_hex(self.candidate_content_hash, "ReviewDecision.candidate_content_hash")
        validate_identifier(self.reviewer_id, "ReviewDecision.reviewer_id")
        validate_iso_datetime(self.reviewed_at, "ReviewDecision.reviewed_at")
        if self.rationale is not None and not self.rationale:
            raise ValueError("ReviewDecision.rationale must not be empty when set")
        for correction in self.proposed_corrections:
            if not correction:
                raise ValueError("ReviewDecision.proposed_corrections entries must not be empty")
        if self.supersedes_decision_id is not None:
            validate_identifier(
                self.supersedes_decision_id, "ReviewDecision.supersedes_decision_id"
            )
            if self.supersedes_decision_id == self.decision_id:
                raise ValueError("ReviewDecision cannot supersede itself")

    def references_candidate(self, candidate_id: str, revision: int, content_hash: str) -> bool:
        """True when this decision refers to the exact candidate revision and hash."""
        return (
            self.candidate_id == candidate_id
            and self.candidate_revision == revision
            and self.candidate_content_hash == content_hash
        )

    def is_stale_for(self, revision: int, content_hash: str) -> bool:
        """True when the decision no longer matches the current candidate revision."""
        return not (
            self.candidate_revision == revision and self.candidate_content_hash == content_hash
        )
