"""Structural checks for committed Phase 5 reconciled candidate artifacts.

These tests verify serialization, structural validity, provenance integrity,
protocol isolation, and deterministic visual outputs. They deliberately do not
assert clinical correctness: semantic decisions belong to candidate artifacts
and human review.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cpg_tree.candidates.enums import CandidateState, RelationType
from cpg_tree.candidates.graph import FindingSeverity, validate_candidate_graph
from cpg_tree.candidates.graph_serialization import dump_candidate_graph, load_candidate_graph
from cpg_tree.views.review_tree import (
    load_projection_manifest,
    render_review_tree_html,
    render_review_tree_svg,
)

ROOT = Path(__file__).resolve().parents[3]
PHASE5 = {
    "nac": ROOT / "artifacts/phase5/nac",
    "itu": ROOT / "artifacts/phase5/itu",
}

NAC_RULE_COUNT = 29
NAC_RELATION_COUNT = 33
ITU_RULE_COUNT = 38
ITU_RELATION_COUNT = 46


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_phase5_candidate_graph_round_trip(name: str) -> None:
    path = PHASE5[name] / "candidate_graph.json"
    text = path.read_text(encoding="utf-8")
    graph = load_candidate_graph(text)

    assert dump_candidate_graph(graph) == text
    assert graph.rules
    assert graph.relations


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_phase5_graph_has_no_structural_errors(name: str) -> None:
    graph = load_candidate_graph(
        (PHASE5[name] / "candidate_graph.json").read_text(encoding="utf-8")
    )

    assert validate_candidate_graph(graph) == graph.findings
    assert not [item for item in graph.findings if item.severity is FindingSeverity.ERROR]


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_phase5_exact_quotes_resolve_to_cited_spans(name: str) -> None:
    graph = load_candidate_graph(
        (PHASE5[name] / "candidate_graph.json").read_text(encoding="utf-8")
    )
    span_text = {span.span_id: span.extracted_text_exact or "" for span in graph.source_spans}
    entities = [
        *graph.variables,
        *graph.rules,
        *graph.relations,
        *(action for rule in graph.rules for action in rule.actions),
    ]
    for entity in entities:
        for binding in entity.evidence_bindings:
            if binding.exact_quote is None:
                continue
            cited_text = "\n".join(span_text[ref] for ref in binding.source_span_refs)
            assert binding.exact_quote in cited_text
    for observation in graph.observations:
        if observation.exact_quote is None:
            continue
        cited_text = "\n".join(span_text[ref] for ref in observation.span_refs)
        assert observation.exact_quote in cited_text


def test_nac_and_itu_remain_independent() -> None:
    nac = load_candidate_graph((PHASE5["nac"] / "candidate_graph.json").read_text(encoding="utf-8"))
    itu = load_candidate_graph((PHASE5["itu"] / "candidate_graph.json").read_text(encoding="utf-8"))

    assert nac.protocol_version_id == "CT-PL-193-v9"
    assert itu.protocol_version_id == "CT-PL-197-v06"
    assert nac.document_id != itu.document_id
    assert {rule.protocol_version_id for rule in nac.rules} == {"CT-PL-193-v9"}
    assert {rule.protocol_version_id for rule in itu.rules} == {"CT-PL-197-v06"}
    for graph, prefix in ((nac, "nac-"), (itu, "itu-")):
        for relation in graph.relations:
            for endpoint in (relation.source_ref, *relation.target_refs):
                assert endpoint.startswith(prefix) or endpoint.startswith(f"act-{prefix}")


def test_no_candidate_was_promoted_to_approved() -> None:
    for name in ("nac", "itu"):
        graph = load_candidate_graph(
            (PHASE5[name] / "candidate_graph.json").read_text(encoding="utf-8")
        )
        assert {rule.candidate_state for rule in graph.rules} <= {
            CandidateState.PROPOSED,
            CandidateState.BLOCKED,
        }


def test_nac_reconciliation_decisions() -> None:
    graph = load_candidate_graph(
        (PHASE5["nac"] / "candidate_graph.json").read_text(encoding="utf-8")
    )
    relations = {relation.candidate_relation_id: relation for relation in graph.relations}

    assert len(graph.rules) == NAC_RULE_COUNT
    assert len(graph.relations) == NAC_RELATION_COUNT
    assert relations["nac-rel-18"].relation_type is RelationType.BRANCH
    assert relations["nac-rel-19"].relation_type is RelationType.BRANCH
    assert all(relation.candidate_state is CandidateState.PROPOSED for relation in graph.relations)


def test_itu_reconciliation_decisions() -> None:
    graph = load_candidate_graph(
        (PHASE5["itu"] / "candidate_graph.json").read_text(encoding="utf-8")
    )
    relations = {relation.candidate_relation_id: relation for relation in graph.relations}

    assert len(graph.rules) == ITU_RULE_COUNT
    assert len(graph.relations) == ITU_RELATION_COUNT
    assert relations["itu-rel-07"].relation_type is RelationType.BRANCH
    assert relations["itu-rel-14"].source_ref == "itu-r02-symptomatic-uti-classification"
    assert relations["itu-rel-42"].source_ref == "itu-r02-symptomatic-uti-classification"
    assert relations["itu-rel-23"].candidate_state is CandidateState.BLOCKED
    assert relations["itu-rel-29"].relation_type is RelationType.BRANCH_CONTEXT
    assert relations["itu-rel-44"].relation_type is RelationType.SUPPORTS
    assert relations["itu-rel-44"].target_refs == (
        "itu-r27-lower-treatment",
        "itu-r29-upper-outpatient-treatment",
        "itu-r30-upper-inpatient-no-resistant-risk",
        "itu-r31-upper-inpatient-resistant-no-shock",
        "itu-r32-upper-inpatient-resistant-shock",
    )


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_review_visuals_are_deterministic_and_rendered(name: str) -> None:
    graph = load_candidate_graph(
        (PHASE5[name] / "candidate_graph.json").read_text(encoding="utf-8")
    )
    manifest = load_projection_manifest(PHASE5[name] / "projection.yaml")

    assert render_review_tree_html(graph, manifest) == (
        PHASE5[name] / "review_tree.html"
    ).read_text(encoding="utf-8")
    assert render_review_tree_svg(graph, manifest) == (PHASE5[name] / "review_tree.svg").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_review_visuals_are_protocol_isolated(name: str) -> None:
    html_text = (PHASE5[name] / "review_tree.html").read_text(encoding="utf-8")
    foreign = "itu-" if name == "nac" else "nac-"
    assert foreign not in html_text
    assert "NOT CLINICALLY APPROVED" in html_text
    assert "no connector was invented" in html_text
