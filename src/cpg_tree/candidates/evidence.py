"""Field-level evidence bindings for candidate claims.

Rule-level citations are insufficient when one rule contains several
conditions, numbers, units, actions, doses, or temporal constraints. An
``EvidenceBinding`` attaches evidence to one clinically meaningful claim
identified by ``claim_path`` (for example ``/condition/operands/1/value`` or
``/actions/0/dose_value``).

Missing provenance is a structural failure: every bindable claim must carry a
binding, and a binding must reference source spans unless the claim is
explicitly ``UNRESOLVED``. Phase 6 validates that ``exact_quote`` is found in
the referenced extraction channel; Phase 1 establishes the contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cpg_tree.candidates.enums import EvidenceClass
from cpg_tree.knowledge._validation import validate_identifier


@dataclass(frozen=True, slots=True)
class EvidenceBinding:
    """Evidence for one clinically meaningful claim.

    ``source_span_refs`` identify ``SourceSpan`` entries. A binding whose
    evidence is ``UNRESOLVED`` may legitimately reference no spans; every
    other evidence class must reference at least one span.
    """

    claim_path: str
    evidence_class: EvidenceClass
    source_span_refs: tuple[str, ...] = ()
    exact_quote: str | None = None
    transformation: str | None = None

    def __post_init__(self) -> None:
        if not self.claim_path or not self.claim_path.startswith("/"):
            raise ValueError(
                "EvidenceBinding.claim_path must be a non-empty path starting with '/'"
            )
        for ref in self.source_span_refs:
            validate_identifier(ref, "EvidenceBinding.source_span_refs entry")
        if not self.source_span_refs and self.evidence_class is not EvidenceClass.UNRESOLVED:
            raise ValueError(
                "EvidenceBinding requires at least one source span unless the evidence "
                "class is UNRESOLVED"
            )
        if self.exact_quote is not None and not self.exact_quote:
            raise ValueError("EvidenceBinding.exact_quote must not be empty when set")
        if self.transformation is not None and not self.transformation:
            raise ValueError("EvidenceBinding.transformation must not be empty when set")


def evidence_binding_to_canonical(binding: EvidenceBinding) -> dict[str, Any]:
    """Serialize one evidence binding canonically."""
    payload: dict[str, Any] = {
        "claim_path": binding.claim_path,
        "evidence_class": binding.evidence_class.value,
        "source_span_refs": sorted(binding.source_span_refs),
    }
    if binding.exact_quote is not None:
        payload["exact_quote"] = binding.exact_quote
    if binding.transformation is not None:
        payload["transformation"] = binding.transformation
    return payload


def bindings_to_canonical(bindings: tuple[EvidenceBinding, ...]) -> list[dict[str, Any]]:
    """Serialize a tuple of evidence bindings canonically, in stable order."""
    return sorted(
        (evidence_binding_to_canonical(binding) for binding in bindings),
        key=lambda item: item["claim_path"],
    )
