"""CandidateRule: versioned, non-approved computable interpretation."""

# ruff: noqa: TRY004

from __future__ import annotations

from dataclasses import dataclass, field

from cpg_tree.candidates.actions import ActionSpec
from cpg_tree.candidates.enums import CandidateState, EvidenceClass
from cpg_tree.candidates.evidence import EvidenceBinding, bindings_to_canonical
from cpg_tree.candidates.expressions import ClinicalExpression
from cpg_tree.candidates.hashing import expression_to_canonical, hash_canonical_dict
from cpg_tree.knowledge._validation import validate_identifier

_MIN_REVISION: int = 1


@dataclass(frozen=True, slots=True)
class CandidateRule:
    """A computable interpretation that still requires clinical review.

    A candidate is never approved knowledge: there is deliberately no
    ``APPROVED`` candidate state, and the candidate can never be fed to the
    deterministic engine as support. Approval exists only in the review layer.

    ``content_hash`` binds clinical content (condition, applicability,
    exceptions, actions, evidence, observation refs) to an exact digest; it is
    computed automatically when omitted and verified when supplied. Identity
    and lifecycle fields (``candidate_id``, ``revision``, ``candidate_state``,
    ``generation_attempt_id``, ``supersedes_candidate_id``) never participate,
    so renumbering or re-versioning does not change what was reviewed.

    ``modality`` and ``statement_kind`` are free-text qualifiers whose
    vocabulary is fixed by Phase 4 normalization; they are validated as
    non-empty strings, not against an invented enum.
    """

    candidate_id: str
    revision: int
    protocol_version_id: str
    condition: ClinicalExpression
    evidence_class: EvidenceClass
    observation_refs: tuple[str, ...] = ()
    applies_to: ClinicalExpression | None = None
    actions: tuple[ActionSpec, ...] = ()
    exceptions: tuple[ClinicalExpression, ...] = ()
    modality: str | None = None
    statement_kind: str | None = None
    evidence_bindings: tuple[EvidenceBinding, ...] = ()
    ambiguity_flags: tuple[str, ...] = ()
    candidate_state: CandidateState = CandidateState.PROPOSED
    generation_attempt_id: str | None = None
    supersedes_candidate_id: str | None = None
    content_hash: str | None = field(default=None)

    def __post_init__(self) -> None:
        self._validate_identity()
        self._validate_references()
        self._bind_content_hash()

    def _validate_identity(self) -> None:
        validate_identifier(self.candidate_id, "CandidateRule.candidate_id")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int):
            raise ValueError("CandidateRule.revision must be an integer")
        if self.revision < _MIN_REVISION:
            raise ValueError("CandidateRule.revision must be positive")
        validate_identifier(self.protocol_version_id, "CandidateRule.protocol_version_id")

    def _validate_references(self) -> None:
        for ref in self.observation_refs:
            validate_identifier(ref, "CandidateRule.observation_refs entry")
        if self.modality is not None and not self.modality:
            raise ValueError("CandidateRule.modality must not be empty when set")
        if self.statement_kind is not None and not self.statement_kind:
            raise ValueError("CandidateRule.statement_kind must not be empty when set")
        for flag in self.ambiguity_flags:
            if not flag:
                raise ValueError("CandidateRule.ambiguity_flags entries must not be empty")
        if self.generation_attempt_id is not None:
            validate_identifier(self.generation_attempt_id, "CandidateRule.generation_attempt_id")
        if self.supersedes_candidate_id is not None:
            validate_identifier(
                self.supersedes_candidate_id, "CandidateRule.supersedes_candidate_id"
            )
            if self.supersedes_candidate_id == self.candidate_id and self.revision <= 1:
                raise ValueError("a candidate superseding itself must have a newer revision")

    def _bind_content_hash(self) -> None:
        computed = compute_candidate_rule_content_hash(
            condition=self.condition,
            evidence_class=self.evidence_class,
            observation_refs=self.observation_refs,
            applies_to=self.applies_to,
            actions=self.actions,
            exceptions=self.exceptions,
            modality=self.modality,
            statement_kind=self.statement_kind,
            evidence_bindings=self.evidence_bindings,
            ambiguity_flags=self.ambiguity_flags,
        )
        if self.content_hash is None:
            object.__setattr__(self, "content_hash", computed)
            return
        if self.content_hash != computed:
            raise ValueError("CandidateRule.content_hash does not match the rule content")

    def is_current_revision(self, revision: int, content_hash: str) -> bool:
        """True when this candidate is exactly the reviewed revision and hash."""
        return self.revision == revision and self.content_hash == content_hash


def compute_candidate_rule_content_hash(  # noqa: PLR0913
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
    ambiguity_flags: tuple[str, ...],
) -> str:
    """Compute the content hash of candidate rule fields.

    This is the single definition of what "reviewed content" means for a
    candidate rule; ``CandidateRule.__post_init__`` verifies against it.
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
    if ambiguity_flags:
        payload["ambiguity_flags"] = sorted(ambiguity_flags)
    result: str = hash_canonical_dict(payload)
    return result


_ACTION_TEXT_FIELDS = (
    "target_text",
    "dose_value",
    "dose_unit",
    "route",
    "frequency",
    "duration",
    "timing",
    "alternative_group",
)


def action_spec_to_canonical(action: ActionSpec) -> dict[str, object]:
    """Serialize one ActionSpec canonically."""
    payload: dict[str, object] = {
        "action_id": action.action_id,
        "action_type": action.action_type.value,
    }
    for field_name in _ACTION_TEXT_FIELDS:
        value = getattr(action, field_name)
        if value is not None:
            payload[field_name] = value
    if action.qualifiers:
        payload["qualifiers"] = sorted(action.qualifiers)
    if action.evidence_bindings:
        payload["evidence_bindings"] = bindings_to_canonical(action.evidence_bindings)
    return payload
