"""Enumerations of the candidate pipeline contracts.

These enums describe evidence-bound, pre-approval artifacts. Nothing here
carries an approval meaning: candidates are always pending human review.
"""

from enum import StrEnum


class EvidenceClass(StrEnum):
    """How a claim was derived from its source evidence.

    ``SOURCE_STATED`` is a verbatim source statement; ``EXTRACTED`` is a
    faithful structured transcription; ``NORMALIZED`` underwent
    semantic-preserving transformations (abbreviation expansion, unit
    normalization); ``INFERRED`` was produced by a transformation process
    beyond the literal statement; ``UNRESOLVED`` has no bindable evidence.

    This enum intentionally mirrors ``reconciliation.model.EvidenceClass``
    (same values). Both coexist during Phase 1; the reconciliation layer is
    adapted onto this contract in Phase 5.
    """

    SOURCE_STATED = "SOURCE_STATED"
    EXTRACTED = "EXTRACTED"
    NORMALIZED = "NORMALIZED"
    INFERRED = "INFERRED"
    UNRESOLVED = "UNRESOLVED"


class CandidateState(StrEnum):
    """Lifecycle state of a candidate.

    Approval deliberately does not exist as a candidate state: approval is a
    review-layer concept (``ReviewDecision`` -> approved snapshots). A
    candidate can be superseded by a newer revision but can never become
    approved itself.
    """

    PROPOSED = "PROPOSED"
    BLOCKED = "BLOCKED"
    NEEDS_CHANGES = "NEEDS_CHANGES"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class RelationType(StrEnum):
    """Semantic type of a candidate relationship.

    ``FLOW`` and ``BRANCH`` are clinical sequence relationships; the rest are
    contextual. No type implies an execution order by itself.
    """

    FLOW = "FLOW"
    BRANCH = "BRANCH"
    REFERENCE = "REFERENCE"
    SUPPORTS = "SUPPORTS"
    EXCEPTION_CONTEXT = "EXCEPTION_CONTEXT"
    BRANCH_CONTEXT = "BRANCH_CONTEXT"
    COMPOSITION = "COMPOSITION"
    DECLARES_ACTION = "DECLARES_ACTION"


class ObservationKind(StrEnum):
    """Kinds of evidence-bound atomic source observations."""

    HEADING = "HEADING"
    DEFINITION = "DEFINITION"
    RECOMMENDATION = "RECOMMENDATION"
    LIST_ITEM = "LIST_ITEM"
    TABLE_ROW = "TABLE_ROW"
    TABLE_CELL = "TABLE_CELL"
    FOOTNOTE = "FOOTNOTE"
    EXPLICIT_RELATION = "EXPLICIT_RELATION"
    DIAGRAM_LABEL = "DIAGRAM_LABEL"


class IssueCategory(StrEnum):
    """Category of an unresolved problem in the candidate inventory."""

    AMBIGUITY = "AMBIGUITY"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    EXTRACTION_LIMITATION = "EXTRACTION_LIMITATION"
    SOURCE_CONTENT_ABSENT = "SOURCE_CONTENT_ABSENT"
    TABLE_ALIGNMENT = "TABLE_ALIGNMENT"
    NEGATION_UNCERTAIN = "NEGATION_UNCERTAIN"
    UNIT_UNCERTAIN = "UNIT_UNCERTAIN"
    RELATION_UNCERTAIN = "RELATION_UNCERTAIN"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class IssueSeverity(StrEnum):
    """Severity of an Issue, independent of its resolution state.

    A ``BLOCKING`` Issue prevents compilation of the candidate into approved
    knowledge; it never erases the candidate or its evidence.
    """

    BLOCKING = "BLOCKING"
    NON_BLOCKING = "NON_BLOCKING"


class IssueStatus(StrEnum):
    """Resolution state of an Issue."""

    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
