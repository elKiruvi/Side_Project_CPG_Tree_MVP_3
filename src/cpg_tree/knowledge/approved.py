"""Approved knowledge: immutable snapshots of clinically reviewed semantics.

These contracts are the review-governed counterparts of the candidate layer.
An ``ApprovedRule`` / ``ApprovedRelation`` is an immutable snapshot of exactly
reviewed content: it references the exact candidate revision and hash it was
compiled from and the decision that approved it, and it never changes when
its source candidate changes. Corrections create a new candidate revision and
a new decision; they never silently mutate approved content.

``ApprovedKnowledgePackage`` is the only package intended for normal
deterministic clinical-rule execution after review.

Layering note: this module depends on the candidate and review layers (it
snapshots their content). It is intentionally NOT re-exported from
``cpg_tree.knowledge.__init__`` to keep the legacy YAML-package model
(``Rule``/``Action``/``ProtocolVersion``) import-independent from the
candidate pipeline. The Phase 7 compiler is the only bridge between the two
canonical models.
"""

# ruff: noqa: TRY004

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

from cpg_tree.candidates.actions import ActionSpec
from cpg_tree.candidates.enums import EvidenceClass, IssueSeverity, RelationType
from cpg_tree.candidates.evidence import EvidenceBinding, bindings_to_canonical
from cpg_tree.candidates.expressions import ClinicalExpression
from cpg_tree.candidates.hashing import (
    expression_to_canonical,
    hash_canonical_dict,
    validate_sha256_hex,
)
from cpg_tree.candidates.issues import Issue
from cpg_tree.candidates.rules import action_spec_to_canonical
from cpg_tree.candidates.variables import VariableSpec
from cpg_tree.extraction.spans import SourceSpan
from cpg_tree.knowledge._validation import validate_identifier, validate_iso_datetime
from cpg_tree.knowledge.documents import SourceDocument
from cpg_tree.review.model import ReviewDecision

APPROVED_KNOWLEDGE_PACKAGE_SCHEMA_VERSION: Final = "approved-knowledge-package-v1"
"""Schema version of the approved knowledge package contract."""

_MIN_REVISION: Final = 1


@dataclass(frozen=True, slots=True)
class ApprovedRule:
    """Immutable snapshot of one clinically approved rule.

    ``approved_content_hash`` binds the snapshot to an exact digest of the
    approved content; it is computed automatically when omitted and verified
    when supplied. ``source_candidate_id``/``source_candidate_revision``/
    ``source_candidate_content_hash`` identify the exact candidate revision
    this snapshot was compiled from; changing the candidate later never
    changes this snapshot.
    """

    approved_rule_id: str
    source_candidate_id: str
    source_candidate_revision: int
    source_candidate_content_hash: str
    approval_decision_id: str
    approved_by: str
    approved_at: str
    condition: ClinicalExpression
    evidence_class: EvidenceClass
    observation_refs: tuple[str, ...] = ()
    applies_to: ClinicalExpression | None = None
    actions: tuple[ActionSpec, ...] = ()
    exceptions: tuple[ClinicalExpression, ...] = ()
    modality: str | None = None
    statement_kind: str | None = None
    evidence_bindings: tuple[EvidenceBinding, ...] = ()
    approved_content_hash: str | None = field(default=None)

    def __post_init__(self) -> None:
        validate_identifier(self.approved_rule_id, "ApprovedRule.approved_rule_id")
        validate_identifier(self.source_candidate_id, "ApprovedRule.source_candidate_id")
        if isinstance(self.source_candidate_revision, bool) or not isinstance(
            self.source_candidate_revision, int
        ):
            raise ValueError("ApprovedRule.source_candidate_revision must be an integer")
        if self.source_candidate_revision < _MIN_REVISION:
            raise ValueError("ApprovedRule.source_candidate_revision must be positive")
        validate_sha256_hex(
            self.source_candidate_content_hash, "ApprovedRule.source_candidate_content_hash"
        )
        validate_identifier(self.approval_decision_id, "ApprovedRule.approval_decision_id")
        validate_identifier(self.approved_by, "ApprovedRule.approved_by")
        validate_iso_datetime(self.approved_at, "ApprovedRule.approved_at")
        for ref in self.observation_refs:
            validate_identifier(ref, "ApprovedRule.observation_refs entry")
        self._bind_content_hash()

    def _bind_content_hash(self) -> None:
        computed = compute_approved_rule_content_hash(
            condition=self.condition,
            evidence_class=self.evidence_class,
            observation_refs=self.observation_refs,
            applies_to=self.applies_to,
            actions=self.actions,
            exceptions=self.exceptions,
            modality=self.modality,
            statement_kind=self.statement_kind,
            evidence_bindings=self.evidence_bindings,
        )
        if self.approved_content_hash is None:
            object.__setattr__(self, "approved_content_hash", computed)
            return
        if self.approved_content_hash != computed:
            raise ValueError("ApprovedRule.approved_content_hash does not match the rule content")

    def references_source_candidate(
        self, candidate_id: str, revision: int, content_hash: str
    ) -> bool:
        """True when this snapshot was compiled from the exact candidate revision."""
        return (
            self.source_candidate_id == candidate_id
            and self.source_candidate_revision == revision
            and self.source_candidate_content_hash == content_hash
        )


def compute_approved_rule_content_hash(  # noqa: PLR0913
    *,
    condition: ClinicalExpression,
    evidence_class: EvidenceClass,
    observation_refs: tuple[str, ...],
    applies_to: ClinicalExpression | None,
    actions: tuple[ActionSpec, ...],
    exceptions: tuple[ClinicalExpression, ...],
    modality: str | None,
    statement_kind: str | None,
    evidence_bindings: tuple[EvidenceBinding, ...],
) -> str:
    """Compute the content hash of approved rule fields.

    The approved content hash is intentionally computed over the same content
    shape as ``cpg_tree.candidates.rules.compute_candidate_rule_content_hash``
    (verified via the shared helpers) so that, for an unmodified candidate,
    ``approved_content_hash`` equals the candidate's ``content_hash``.
    """
    payload: dict[str, object] = {
        "condition": expression_to_canonical(condition),
        "evidence_class": evidence_class.value,
        "observation_refs": sorted(observation_refs),
    }
    if applies_to is not None:
        payload["applies_to"] = expression_to_canonical(applies_to)
    if actions:
        payload["actions"] = [action_spec_to_canonical(action) for action in actions]
    if exceptions:
        payload["exceptions"] = [expression_to_canonical(item) for item in exceptions]
    if modality is not None:
        payload["modality"] = modality
    if statement_kind is not None:
        payload["statement_kind"] = statement_kind
    if evidence_bindings:
        payload["evidence_bindings"] = bindings_to_canonical(evidence_bindings)
    result: str = hash_canonical_dict(payload)
    return result


@dataclass(frozen=True, slots=True)
class ApprovedRelation:
    """Immutable snapshot of one clinically approved relationship."""

    approved_relation_id: str
    source_candidate_relation_id: str
    source_candidate_revision: int
    source_candidate_content_hash: str
    approval_decision_id: str
    approved_by: str
    approved_at: str
    source_ref: str
    target_refs: tuple[str, ...]
    relation_type: RelationType
    evidence_class: EvidenceClass
    observation_refs: tuple[str, ...] = ()
    branch_label: str | None = None
    temporal_qualifier: str | None = None
    evidence_bindings: tuple[EvidenceBinding, ...] = ()
    approved_content_hash: str | None = field(default=None)

    def __post_init__(self) -> None:
        validate_identifier(self.approved_relation_id, "ApprovedRelation.approved_relation_id")
        validate_identifier(
            self.source_candidate_relation_id, "ApprovedRelation.source_candidate_relation_id"
        )
        if isinstance(self.source_candidate_revision, bool) or not isinstance(
            self.source_candidate_revision, int
        ):
            raise ValueError("ApprovedRelation.source_candidate_revision must be an integer")
        if self.source_candidate_revision < _MIN_REVISION:
            raise ValueError("ApprovedRelation.source_candidate_revision must be positive")
        validate_sha256_hex(
            self.source_candidate_content_hash,
            "ApprovedRelation.source_candidate_content_hash",
        )
        validate_identifier(self.approval_decision_id, "ApprovedRelation.approval_decision_id")
        validate_identifier(self.approved_by, "ApprovedRelation.approved_by")
        validate_iso_datetime(self.approved_at, "ApprovedRelation.approved_at")
        validate_identifier(self.source_ref, "ApprovedRelation.source_ref")
        if not self.target_refs:
            raise ValueError("ApprovedRelation.target_refs must not be empty")
        for ref in self.target_refs:
            validate_identifier(ref, "ApprovedRelation.target_refs entry")
        if not self.relation_type:
            raise ValueError("ApprovedRelation.relation_type must not be empty")
        self._bind_content_hash()

    def _bind_content_hash(self) -> None:
        computed = compute_approved_relation_content_hash(
            source_ref=self.source_ref,
            target_refs=self.target_refs,
            relation_type=self.relation_type,
            evidence_class=self.evidence_class,
            observation_refs=self.observation_refs,
            branch_label=self.branch_label,
            temporal_qualifier=self.temporal_qualifier,
            evidence_bindings=self.evidence_bindings,
        )
        if self.approved_content_hash is None:
            object.__setattr__(self, "approved_content_hash", computed)
            return
        if self.approved_content_hash != computed:
            raise ValueError(
                "ApprovedRelation.approved_content_hash does not match the relation content"
            )

    def references_source_candidate(
        self, candidate_relation_id: str, revision: int, content_hash: str
    ) -> bool:
        """True when this snapshot was compiled from the exact candidate revision."""
        return (
            self.source_candidate_relation_id == candidate_relation_id
            and self.source_candidate_revision == revision
            and self.source_candidate_content_hash == content_hash
        )


def compute_approved_relation_content_hash(  # noqa: PLR0913
    *,
    source_ref: str,
    target_refs: tuple[str, ...],
    relation_type: RelationType,
    evidence_class: EvidenceClass,
    observation_refs: tuple[str, ...],
    branch_label: str | None,
    temporal_qualifier: str | None,
    evidence_bindings: tuple[EvidenceBinding, ...],
) -> str:
    """Compute the content hash of approved relation fields."""
    payload: dict[str, object] = {
        "source_ref": source_ref,
        "target_refs": sorted(target_refs),
        "relation_type": relation_type.value,
        "evidence_class": evidence_class.value,
        "observation_refs": sorted(observation_refs),
    }
    if branch_label is not None:
        payload["branch_label"] = branch_label
    if temporal_qualifier is not None:
        payload["temporal_qualifier"] = temporal_qualifier
    if evidence_bindings:
        payload["evidence_bindings"] = bindings_to_canonical(evidence_bindings)
    result: str = hash_canonical_dict(payload)
    return result


@dataclass(frozen=True, slots=True)
class ApprovedKnowledgePackage:
    """The reviewed, immutable package for deterministic execution.

    Collections are keyed by the id of their entries. ``accepted_issues`` may
    only hold ``NON_BLOCKING`` Issues that review explicitly accepted as
    persistent; a blocking Issue prevents compilation and therefore can never
    appear here. The Phase 7 compiler is responsible for populating this
    package from decisions and verified candidate revisions; this contract
    enforces the structural invariants only.
    """

    schema_version: str
    package_id: str
    protocol_id: str
    protocol_version: str
    source_documents: dict[str, SourceDocument] = field(default_factory=dict)
    variables: dict[str, VariableSpec] = field(default_factory=dict)
    actions: dict[str, ActionSpec] = field(default_factory=dict)
    rules: dict[str, ApprovedRule] = field(default_factory=dict)
    relations: dict[str, ApprovedRelation] = field(default_factory=dict)
    spans: dict[str, SourceSpan] = field(default_factory=dict)
    review_decisions: dict[str, ReviewDecision] = field(default_factory=dict)
    accepted_issues: dict[str, Issue] = field(default_factory=dict)
    build_manifest: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != APPROVED_KNOWLEDGE_PACKAGE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported schema_version {self.schema_version!r}; expected "
                f"{APPROVED_KNOWLEDGE_PACKAGE_SCHEMA_VERSION!r}"
            )
        validate_identifier(self.package_id, "ApprovedKnowledgePackage.package_id")
        validate_identifier(self.protocol_id, "ApprovedKnowledgePackage.protocol_id")
        if not self.protocol_version:
            raise ValueError("ApprovedKnowledgePackage.protocol_version must not be empty")
        self._check_keys(self.source_documents, "source_documents", "document_id")
        self._check_keys(self.variables, "variables", "variable_id")
        self._check_keys(self.actions, "actions", "action_id")
        self._check_keys(self.rules, "rules", "approved_rule_id")
        self._check_keys(self.relations, "relations", "approved_relation_id")
        self._check_keys(self.spans, "spans", "span_id")
        self._check_keys(self.review_decisions, "review_decisions", "decision_id")
        self._check_keys(self.accepted_issues, "accepted_issues", "issue_id")
        for issue in self.accepted_issues.values():
            if issue.severity is IssueSeverity.BLOCKING:
                raise ValueError(
                    f"accepted issue {issue.issue_id!r} is BLOCKING and cannot appear "
                    "in an approved package"
                )

    @staticmethod
    def _check_keys(mapping: Mapping[str, object], field_name: str, id_field: str) -> None:
        for key, value in mapping.items():
            entry_id = getattr(value, id_field)
            if entry_id != key:
                raise ValueError(
                    f"ApprovedKnowledgePackage.{field_name} key {key!r} does not match "
                    f"entry {id_field} {entry_id!r}"
                )
