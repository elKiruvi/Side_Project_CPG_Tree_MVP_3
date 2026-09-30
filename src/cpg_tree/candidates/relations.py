"""CandidateRelation: evidence-bound proposed relationship between known IDs."""

# ruff: noqa: TRY004

from __future__ import annotations

from dataclasses import dataclass, field

from cpg_tree.candidates.enums import CandidateState, EvidenceClass, RelationType
from cpg_tree.candidates.evidence import EvidenceBinding, bindings_to_canonical
from cpg_tree.candidates.hashing import hash_canonical_dict
from cpg_tree.knowledge._validation import validate_identifier

_MIN_REVISION: int = 1


@dataclass(frozen=True, slots=True)
class CandidateRelation:
    """A versioned, non-approved proposed relationship between known entity IDs.

    Endpoints are typed references: identifiers of known entities only.
    Free-text pseudo IDs and wildcards (``*``) are never permitted. Relation
    types distinguish clinical sequence (``FLOW``, ``BRANCH``) from contextual
    relationships; no type implies execution order by itself.

    ``content_hash`` binds the relationship content to an exact digest; it is
    computed automatically when omitted and verified when supplied. Identity
    and lifecycle fields never participate.
    """

    candidate_relation_id: str
    revision: int
    source_ref: str
    target_refs: tuple[str, ...]
    relation_type: RelationType
    evidence_class: EvidenceClass
    observation_refs: tuple[str, ...] = ()
    branch_label: str | None = None
    temporal_qualifier: str | None = None
    evidence_bindings: tuple[EvidenceBinding, ...] = ()
    candidate_state: CandidateState = CandidateState.PROPOSED
    generation_attempt_id: str | None = None
    content_hash: str | None = field(default=None)

    def __post_init__(self) -> None:
        validate_identifier(self.candidate_relation_id, "CandidateRelation.candidate_relation_id")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int):
            raise ValueError("CandidateRelation.revision must be an integer")
        if self.revision < _MIN_REVISION:
            raise ValueError("CandidateRelation.revision must be positive")
        validate_identifier(self.source_ref, "CandidateRelation.source_ref")
        if not self.target_refs:
            raise ValueError("CandidateRelation.target_refs must not be empty")
        for ref in self.target_refs:
            validate_identifier(ref, "CandidateRelation.target_refs entry")
            if ref == self.source_ref:
                raise ValueError("CandidateRelation must not reference itself")
        if self.branch_label is not None and not self.branch_label:
            raise ValueError("CandidateRelation.branch_label must not be empty when set")
        if self.temporal_qualifier is not None and not self.temporal_qualifier:
            raise ValueError("CandidateRelation.temporal_qualifier must not be empty when set")
        for ref in self.observation_refs:
            validate_identifier(ref, "CandidateRelation.observation_refs entry")
        if self.generation_attempt_id is not None:
            validate_identifier(
                self.generation_attempt_id, "CandidateRelation.generation_attempt_id"
            )
        self._bind_content_hash()

    def _bind_content_hash(self) -> None:
        computed = compute_candidate_relation_content_hash(
            source_ref=self.source_ref,
            target_refs=self.target_refs,
            relation_type=self.relation_type,
            evidence_class=self.evidence_class,
            observation_refs=self.observation_refs,
            branch_label=self.branch_label,
            temporal_qualifier=self.temporal_qualifier,
            evidence_bindings=self.evidence_bindings,
        )
        if self.content_hash is None:
            object.__setattr__(self, "content_hash", computed)
            return
        if self.content_hash != computed:
            raise ValueError("CandidateRelation.content_hash does not match the relation content")

    def is_current_revision(self, revision: int, content_hash: str) -> bool:
        """True when this candidate is exactly the reviewed revision and hash."""
        return self.revision == revision and self.content_hash == content_hash


def compute_candidate_relation_content_hash(  # noqa: PLR0913
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
    """Compute the content hash of candidate relation fields.

    This is the single definition of what "reviewed content" means for a
    candidate relation; ``CandidateRelation.__post_init__`` verifies against it.
    """
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
