"""Tests for the CandidateRule contract: candidate != approved semantics."""

from __future__ import annotations

import pytest

from cpg_tree.candidates import (
    ActionSpec,
    CandidateRule,
    CandidateState,
    EvidenceBinding,
    EvidenceClass,
)
from cpg_tree.knowledge import (
    ActionType,
    ComparisonOperator,
    Condition,
    ConditionKind,
    LogicalExpression,
    LogicalOperator,
)

BUN_GT_30 = Condition(
    kind=ConditionKind.COMPARISON,
    variable_ref="bun",
    operator=ComparisonOperator.GT,
    operand=30,
)

ICU_CRITERIA = LogicalExpression(
    operator=LogicalOperator.AT_LEAST_N,
    threshold=1,
    operands=(
        Condition(
            kind=ConditionKind.COMPARISON,
            variable_ref="respiratory_rate",
            operator=ComparisonOperator.GT,
            operand=30,
        ),
        Condition(
            kind=ConditionKind.COMPARISON,
            variable_ref="systolic_bp",
            operator=ComparisonOperator.LT,
            operand=90,
        ),
    ),
)

REVISION_ONE = 1
REVISION_TWO = 2
SHA256_LENGTH = 64


def make_rule(**overrides: object) -> CandidateRule:
    fields: dict[str, object] = {
        "candidate_id": "cand-nac-001",
        "revision": 1,
        "protocol_version_id": "CT-PL-193-v09",
        "condition": BUN_GT_30,
        "evidence_class": EvidenceClass.SOURCE_STATED,
    }
    fields.update(overrides)
    return CandidateRule(**fields)  # type: ignore[arg-type]


def test_candidate_rule_construction_computes_hash() -> None:
    rule = make_rule()
    assert rule.content_hash is not None
    assert rule.candidate_state is CandidateState.PROPOSED
    assert rule.revision == 1


def test_candidate_state_has_no_approved_value() -> None:
    assert {state.value for state in CandidateState} == {
        "PROPOSED",
        "BLOCKED",
        "NEEDS_CHANGES",
        "REJECTED",
        "SUPERSEDED",
    }


def test_candidate_rule_references_condition_ast_without_duplication() -> None:
    """The canonical Condition/LogicalExpression AST is reused, not duplicated."""
    rule = make_rule(condition=ICU_CRITERIA)
    assert rule.condition.operator is LogicalOperator.AT_LEAST_N


def test_candidate_rule_with_actions_and_exceptions() -> None:
    rule = make_rule(
        applies_to=Condition(
            kind=ConditionKind.FLAG,
            variable_ref="hospitalized",
            expected=True,
        ),
        actions=(
            ActionSpec(
                action_id="act-ceftriaxone",
                action_type=ActionType.PRESCRIBE,
                target_text="ceftriaxone",
                alternative_group="nac-inpatient",
            ),
        ),
        exceptions=(
            Condition(
                kind=ConditionKind.FLAG,
                variable_ref="pregnancy",
                expected=True,
            ),
        ),
        evidence_bindings=(
            EvidenceBinding(
                claim_path="/condition/operand",
                evidence_class=EvidenceClass.SOURCE_STATED,
                source_span_refs=("span-3",),
                exact_quote="BUN > 30",
            ),
        ),
        ambiguity_flags=("conflicting flowchart threshold",),
    )
    assert len(rule.actions) == 1
    assert len(rule.exceptions) == 1
    assert len(rule.evidence_bindings) == 1


def test_candidate_rule_rejects_bad_revision() -> None:
    with pytest.raises(ValueError, match="revision"):
        make_rule(revision=0)
    with pytest.raises(ValueError, match="revision"):
        make_rule(revision="1")  # type: ignore[arg-type]


def test_candidate_rule_rejects_empty_identifier() -> None:
    with pytest.raises(ValueError, match="candidate_id"):
        make_rule(candidate_id="")
    with pytest.raises(ValueError, match="protocol_version_id"):
        make_rule(protocol_version_id="bad id")


def test_candidate_rule_cannot_supersede_itself_at_revision_one() -> None:
    with pytest.raises(ValueError, match="supersed"):
        make_rule(supersedes_candidate_id="cand-nac-001")


def test_candidate_rule_supersession_creates_new_revision() -> None:
    original = make_rule()
    successor = make_rule(
        candidate_id="cand-nac-001",
        revision=2,
        supersedes_candidate_id="cand-nac-001",
        candidate_state=CandidateState.SUPERSEDED,
    )
    assert successor.revision == REVISION_TWO
    assert original.is_current_revision(REVISION_ONE, original.content_hash or "")
    assert not original.is_current_revision(REVISION_TWO, successor.content_hash or "")


def test_candidate_rule_is_current_revision_detects_stale() -> None:
    rule = make_rule()
    assert rule.is_current_revision(REVISION_ONE, rule.content_hash or "")
    assert not rule.is_current_revision(REVISION_TWO, rule.content_hash or "")
    assert not rule.is_current_revision(REVISION_ONE, "0" * SHA256_LENGTH)
