"""ActionSpec: declarative actions supported by evidence."""

from __future__ import annotations

from dataclasses import dataclass

from cpg_tree.candidates.evidence import EvidenceBinding
from cpg_tree.knowledge._validation import validate_identifier
from cpg_tree.knowledge.enums import ActionType

type DoseValue = str | int | float


@dataclass(frozen=True, slots=True)
class ActionSpec:
    """A declarative action or recommendation with evidence bindings.

    ``alternative_group`` links mutually exclusive alternatives; alternatives
    must never be converted into a medication sequence. Doses may be numeric
    or textual (for example an unresolved range); a text dose is never
    silently coerced into a number.
    """

    action_id: str
    action_type: ActionType
    target_text: str | None = None
    dose_value: DoseValue | None = None
    dose_unit: str | None = None
    route: str | None = None
    frequency: str | None = None
    duration: str | None = None
    timing: str | None = None
    alternative_group: str | None = None
    qualifiers: tuple[str, ...] = ()
    evidence_bindings: tuple[EvidenceBinding, ...] = ()

    def __post_init__(self) -> None:
        validate_identifier(self.action_id, "ActionSpec.action_id")
        if self.target_text is not None and not self.target_text:
            raise ValueError("ActionSpec.target_text must not be empty when set")
        if self.dose_value is not None:
            if isinstance(self.dose_value, bool):
                raise ValueError("ActionSpec.dose_value must be a string or number")
            if isinstance(self.dose_value, str) and not self.dose_value:
                raise ValueError("ActionSpec.dose_value must not be empty when set")
        if self.dose_unit is not None and not self.dose_unit:
            raise ValueError("ActionSpec.dose_unit must not be empty when set")
        if self.alternative_group is not None:
            validate_identifier(self.alternative_group, "ActionSpec.alternative_group")
        for qualifier in self.qualifiers:
            if not qualifier:
                raise ValueError("ActionSpec.qualifiers entries must not be empty")
