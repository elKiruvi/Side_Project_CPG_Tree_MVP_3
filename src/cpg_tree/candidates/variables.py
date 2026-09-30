"""VariableSpec: typed data element referenced by clinical expressions."""

from __future__ import annotations

from dataclasses import dataclass

from cpg_tree.candidates.evidence import EvidenceBinding
from cpg_tree.knowledge._validation import validate_identifier
from cpg_tree.knowledge.enums import VariableType


@dataclass(frozen=True, slots=True)
class VariableSpec:
    """A candidate variable specification with its evidence bindings.

    The generic variable type is reused from the canonical knowledge model.
    Disputed definitions must not be collapsed into one variable merely for
    convenience: they stay separate specs with separate evidence until
    clinical adjudication.
    """

    variable_id: str
    label: str
    value_type: VariableType
    unit: str | None = None
    allowed_values: tuple[str, ...] | None = None
    evidence_bindings: tuple[EvidenceBinding, ...] = ()

    def __post_init__(self) -> None:
        validate_identifier(self.variable_id, "VariableSpec.variable_id")
        if not self.label:
            raise ValueError("VariableSpec.label must not be empty")
        if self.allowed_values is not None:
            if self.value_type is not VariableType.CATEGORICAL:
                raise ValueError(
                    "VariableSpec.allowed_values is only valid for CATEGORICAL variables"
                )
            if not self.allowed_values:
                raise ValueError("VariableSpec.allowed_values must not be empty when set")
