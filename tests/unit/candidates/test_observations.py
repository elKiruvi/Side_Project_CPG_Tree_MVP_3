"""Tests for the Observation domain contract."""

from __future__ import annotations

import pytest

from cpg_tree.candidates import Observation, ObservationKind


def test_observation_construction() -> None:
    observation = Observation(
        observation_id="obs-nac-001",
        kind=ObservationKind.RECOMMENDATION,
        span_refs=("span-p3-4",),
        exact_quote="Se recomienda repetir la radiografía en 48 horas",
    )
    assert observation.observation_id == "obs-nac-001"
    assert observation.negated is False
    assert observation.issue_ids == ()


def test_observation_requires_span_refs() -> None:
    with pytest.raises(ValueError, match="span_refs"):
        Observation(
            observation_id="obs-1",
            kind=ObservationKind.DEFINITION,
            span_refs=(),
        )


def test_observation_records_negation() -> None:
    observation = Observation(
        observation_id="obs-2",
        kind=ObservationKind.TABLE_ROW,
        span_refs=("span-9",),
        subject_text="Gram stain",
        predicate_text="is indicated",
        object_text="in emergency care",
        negated=True,
    )
    assert observation.negated is True


def test_observation_is_not_executable() -> None:
    observation = Observation(
        observation_id="obs-3",
        kind=ObservationKind.RECOMMENDATION,
        span_refs=("span-1",),
        exact_quote="ingresar al paciente",
    )
    assert not hasattr(observation, "condition")
    assert not hasattr(observation, "evaluate")


def test_observation_links_issues_by_id() -> None:
    observation = Observation(
        observation_id="obs-4",
        kind=ObservationKind.EXPLICIT_RELATION,
        span_refs=("span-2", "span-3"),
        issue_ids=("issue-conflict-1",),
    )
    assert observation.issue_ids == ("issue-conflict-1",)


def test_observation_requires_identifier() -> None:
    with pytest.raises(ValueError, match="observation_id"):
        Observation(
            observation_id="has space",
            kind=ObservationKind.HEADING,
            span_refs=("span-1",),
        )
