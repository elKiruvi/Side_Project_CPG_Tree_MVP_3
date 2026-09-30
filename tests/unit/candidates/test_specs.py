"""Tests for VariableSpec and ActionSpec candidate contracts."""

from __future__ import annotations

import pytest

from cpg_tree.candidates import ActionSpec, EvidenceBinding, EvidenceClass, VariableSpec
from cpg_tree.knowledge import ActionType, VariableType

DOSE_750 = 750
TEXT_DOSE = "500\u20131000"


def test_variable_spec_construction() -> None:
    spec = VariableSpec(
        variable_id="bun",
        label="BUN",
        value_type=VariableType.NUMERIC,
        unit="mg/dL",
    )
    assert spec.value_type is VariableType.NUMERIC


def test_variable_spec_allowed_values_only_for_categorical() -> None:
    with pytest.raises(ValueError, match="CATEGORICAL"):
        VariableSpec(
            variable_id="bun",
            label="BUN",
            value_type=VariableType.NUMERIC,
            allowed_values=("low", "high"),
        )
    spec = VariableSpec(
        variable_id="setting",
        label="Care setting",
        value_type=VariableType.CATEGORICAL,
        allowed_values=("outpatient", "inpatient"),
        evidence_bindings=(
            EvidenceBinding(
                claim_path="/allowed_values",
                evidence_class=EvidenceClass.SOURCE_STATED,
                source_span_refs=("span-1",),
                exact_quote="ambulatorio u hospitalizado",
            ),
        ),
    )
    assert spec.allowed_values == ("outpatient", "inpatient")


def test_variable_spec_disputed_definitions_remain_separate() -> None:
    first = VariableSpec(
        variable_id="itu_complicada_structural",
        label="Complicated UTI (structural definition)",
        value_type=VariableType.BOOLEAN,
    )
    second = VariableSpec(
        variable_id="itu_complicada_sindromica",
        label="Complicated UTI (syndromic definition)",
        value_type=VariableType.BOOLEAN,
    )
    assert first.variable_id != second.variable_id


def test_action_spec_construction() -> None:
    action = ActionSpec(
        action_id="act-levo-750",
        action_type=ActionType.PRESCRIBE,
        target_text="levofloxacin",
        dose_value=DOSE_750,
        dose_unit="mg",
        route="oral",
        frequency="each 24 h",
    )
    assert action.dose_value == DOSE_750


def test_action_spec_accepts_textual_dose_without_coercion() -> None:
    action = ActionSpec(
        action_id="act-range",
        action_type=ActionType.PRESCRIBE,
        target_text="amoxicillin",
        dose_value=TEXT_DOSE,
    )
    assert action.dose_value == TEXT_DOSE


def test_action_spec_rejects_bool_dose() -> None:
    with pytest.raises(ValueError, match="dose_value"):
        ActionSpec(
            action_id="act-bad",
            action_type=ActionType.PRESCRIBE,
            dose_value=True,  # type: ignore[arg-type]
        )


def test_action_spec_alternative_group_links_alternatives() -> None:
    first = ActionSpec(
        action_id="act-alt-1",
        action_type=ActionType.PRESCRIBE,
        target_text="ceftriaxone",
        alternative_group="nac-outpatient-alt",
    )
    second = ActionSpec(
        action_id="act-alt-2",
        action_type=ActionType.PRESCRIBE,
        target_text="amoxicillin-clavulanate",
        alternative_group="nac-outpatient-alt",
    )
    assert first.alternative_group == second.alternative_group
