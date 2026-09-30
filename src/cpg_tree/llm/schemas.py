"""Pydantic v2 wire schemas for untrusted structured LLM outputs.

These models are the *boundary* contracts: anything an LLM provider returns
crosses this boundary as a frozen, strict (``extra="forbid"``) envelope. They
are deliberately separate from the validated internal domain models in
``cpg_tree.candidates``; Phase 3/4 converters map wire items onto those
contracts with additional validation. No provider SDK type leaks into these
schemas, and no clinical logic is evaluated here.

Fail-closed posture: unknown fields, unknown schema versions, malformed
expressions, and structurally impossible items are rejected at the boundary.
Invalid JSON, invalid schema, timeout, or provider refusal never produces a
candidate by fallback to unconstrained free text (enforced by the retry
policy in Phase 3, not by this module).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

OBSERVATION_BATCH_SCHEMA_VERSION = "observation-batch-v1"
CANDIDATE_RULE_BATCH_SCHEMA_VERSION = "candidate-rule-batch-v1"
CANDIDATE_RELATION_BATCH_SCHEMA_VERSION = "candidate-relation-batch-v1"

SUPPORTED_BATCH_SCHEMA_VERSIONS = frozenset(
    {
        OBSERVATION_BATCH_SCHEMA_VERSION,
        CANDIDATE_RULE_BATCH_SCHEMA_VERSION,
        CANDIDATE_RELATION_BATCH_SCHEMA_VERSION,
    }
)

EVIDENCE_CLASS_VALUES = Literal[
    "SOURCE_STATED", "EXTRACTED", "NORMALIZED", "INFERRED", "UNRESOLVED"
]


class BatchOutcome(StrEnum):
    """Outcome of one structured extraction attempt.

    ``NO_CANDIDATES`` is a valid, preferable outcome: it means the evidence
    supported nothing, which is better than an invented rule.
    """

    COMPLETE = "COMPLETE"
    NO_CANDIDATES = "NO_CANDIDATES"
    NEEDS_MORE_CONTEXT = "NEEDS_MORE_CONTEXT"
    FAILED = "FAILED"


class _WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceBindingWire(_WireModel):
    """Wire form of one field-level evidence binding."""

    claim_path: str
    evidence_class: EVIDENCE_CLASS_VALUES
    source_span_refs: tuple[str, ...] = ()
    exact_quote: str | None = None
    transformation: str | None = None

    @field_validator("claim_path")
    @classmethod
    def _claim_path_is_absolute(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("claim_path must be a non-empty path starting with '/'")
        return value

    @model_validator(mode="after")
    def _span_refs_required_except_unresolved(self) -> EvidenceBindingWire:
        if not self.source_span_refs and self.evidence_class != "UNRESOLVED":
            raise ValueError("source_span_refs required unless evidence_class is UNRESOLVED")
        return self


class WireComparison(_WireModel):
    kind: Literal["COMPARISON"]
    variable_ref: str = Field(min_length=1)
    operator: Literal["EQ", "NE", "LT", "LE", "GT", "GE"]
    operand: int | float

    @field_validator("operand")
    @classmethod
    def _operand_is_number(cls, value: int | float) -> int | float:
        if isinstance(value, bool):
            raise ValueError(  # noqa: TRY004 — boundary rejects bool-for-number as a value error
                "operand must be a number, not a boolean"
            )
        return value


class WireMembership(_WireModel):
    kind: Literal["MEMBERSHIP"]
    variable_ref: str = Field(min_length=1)
    values: tuple[str, ...] = Field(min_length=1)


class WireFlag(_WireModel):
    kind: Literal["FLAG"]
    variable_ref: str = Field(min_length=1)
    expected: bool


class WireTemporal(_WireModel):
    kind: Literal["TEMPORAL"]
    variable_ref: str = Field(min_length=1)
    temporal_operator: Literal["AT_LEAST_FOR_LAST", "WITHIN_LAST"]
    duration_value: float = Field(ge=0)
    duration_unit: str = Field(min_length=1)


class WireLogical(_WireModel):
    kind: Literal["LOGICAL"]
    operator: Literal["AND", "OR", "NOT", "AT_LEAST_N"]
    operands: tuple[WireExpression, ...]
    threshold: int | None = None

    @model_validator(mode="after")
    def _logical_arity_is_valid(self) -> WireLogical:
        if not self.operands:
            raise ValueError("logical expressions require at least one operand")
        if self.operator == "NOT":
            if len(self.operands) != 1:
                raise ValueError("NOT expressions require exactly one operand")
            if self.threshold is not None:
                raise ValueError("NOT expressions do not accept a threshold")
        elif self.operator == "AT_LEAST_N":
            if self.threshold is None:
                raise ValueError("AT_LEAST_N expressions require a threshold")
            if not 1 <= self.threshold <= len(self.operands):
                raise ValueError("AT_LEAST_N threshold must be between 1 and the operand count")
        elif self.threshold is not None:
            raise ValueError(f"{self.operator} expressions do not accept a threshold")
        return self


type WireExpression = Annotated[
    WireComparison | WireMembership | WireFlag | WireTemporal | WireLogical,
    Field(discriminator="kind"),
]
"""Discriminated union of wire expression nodes, discriminated by ``kind``."""


WireLogical.model_rebuild()


class ActionWire(_WireModel):
    """Wire form of one declarative action."""

    action_id: str = Field(min_length=1)
    action_type: Literal[
        "DECISION",
        "REQUEST_TEST",
        "ADMIT",
        "DISCHARGE",
        "PRESCRIBE",
        "FOLLOW_UP",
        "CLASSIFY",
        "EDUCATE",
        "RESTRICTION",
    ]
    target_text: str | None = None
    dose_value: str | int | float | None = None
    dose_unit: str | None = None
    route: str | None = None
    frequency: str | None = None
    duration: str | None = None
    timing: str | None = None
    alternative_group: str | None = None
    qualifiers: tuple[str, ...] = ()
    evidence_bindings: tuple[EvidenceBindingWire, ...] = ()

    @field_validator("dose_value")
    @classmethod
    def _dose_is_not_bool(cls, value: str | int | float | None) -> str | int | float | None:
        if isinstance(value, bool):
            raise ValueError(  # noqa: TRY004 — boundary rejects bool-for-number as a value error
                "dose_value must be a string or number, not a boolean"
            )
        return value


class BatchIssueWire(_WireModel):
    """Wire form of one batch-level Issue."""

    issue_id: str = Field(min_length=1)
    category: Literal[
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
    ]
    severity: Literal["BLOCKING", "NON_BLOCKING"]
    description: str = Field(min_length=1)
    related_ids: tuple[str, ...] = ()


class ObservationItem(_WireModel):
    """Wire form of one evidence-bound atomic source observation."""

    observation_id: str = Field(min_length=1)
    kind: Literal[
        "HEADING",
        "DEFINITION",
        "RECOMMENDATION",
        "LIST_ITEM",
        "TABLE_ROW",
        "TABLE_CELL",
        "FOOTNOTE",
        "EXPLICIT_RELATION",
        "DIAGRAM_LABEL",
    ]
    span_refs: tuple[str, ...]
    exact_quote: str | None = None
    subject_text: str | None = None
    predicate_text: str | None = None
    object_text: str | None = None
    negated: bool = False
    issue_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _span_refs_required(self) -> ObservationItem:
        if not self.span_refs:
            raise ValueError("an observation requires at least one span reference")
        return self


class CandidateRuleItem(_WireModel):
    """Wire form of one candidate rule.

    No approval state exists on the wire: the candidate can only be proposed,
    blocked, rejected, or superseded by the pipeline; approval happens in the
    review layer and never inside an LLM response.
    """

    candidate_id: str = Field(min_length=1)
    condition: WireExpression
    evidence_class: EVIDENCE_CLASS_VALUES
    observation_refs: tuple[str, ...] = ()
    applies_to: WireExpression | None = None
    actions: tuple[ActionWire, ...] = ()
    exceptions: tuple[WireExpression, ...] = ()
    modality: str | None = None
    statement_kind: str | None = None
    evidence_bindings: tuple[EvidenceBindingWire, ...] = ()
    ambiguity_flags: tuple[str, ...] = ()


class CandidateRelationItem(_WireModel):
    """Wire form of one candidate relationship.

    Endpoints must be known entity ids; free-text pseudo ids and wildcards are
    rejected at the boundary.
    """

    candidate_relation_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    target_refs: tuple[str, ...]
    relation_type: Literal[
        "FLOW",
        "BRANCH",
        "REFERENCE",
        "SUPPORTS",
        "EXCEPTION_CONTEXT",
        "BRANCH_CONTEXT",
        "COMPOSITION",
        "DECLARES_ACTION",
    ]
    evidence_class: EVIDENCE_CLASS_VALUES
    observation_refs: tuple[str, ...] = ()
    branch_label: str | None = None
    temporal_qualifier: str | None = None
    evidence_bindings: tuple[EvidenceBindingWire, ...] = ()

    @model_validator(mode="after")
    def _endpoints_are_typed_references(self) -> CandidateRelationItem:
        if not self.target_refs:
            raise ValueError("target_refs must not be empty")
        if "*" in self.source_ref or any("*" in ref for ref in self.target_refs):
            raise ValueError("endpoints must not use wildcard references")
        if self.source_ref in self.target_refs:
            raise ValueError("a relation must not reference itself")
        return self


class _BatchEnvelope(_WireModel):
    """Shared strict envelope shape for all structured LLM responses."""

    schema_version: str
    run_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    outcome: BatchOutcome
    issues: tuple[BatchIssueWire, ...] = ()


class ObservationBatch(_BatchEnvelope):
    """Structured LLM response envelope for source observations."""

    items: tuple[ObservationItem, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        if value != OBSERVATION_BATCH_SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version {value!r}")
        return value


class CandidateRuleBatch(_BatchEnvelope):
    """Structured LLM response envelope for candidate rules."""

    items: tuple[CandidateRuleItem, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        if value != CANDIDATE_RULE_BATCH_SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version {value!r}")
        return value


class CandidateRelationBatch(_BatchEnvelope):
    """Structured LLM response envelope for candidate relations."""

    items: tuple[CandidateRelationItem, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        if value != CANDIDATE_RELATION_BATCH_SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version {value!r}")
        return value
