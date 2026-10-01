"""Structural checks for committed Phase 4 candidate artifacts.

These tests deliberately do not assert that any clinical recommendation is
correct. They verify serialization, reference closure, evidence integrity, and
the deterministic structural findings used to prepare human review.
"""

from pathlib import Path

import pytest

from cpg_tree.candidates.graph import FindingSeverity, validate_candidate_graph
from cpg_tree.candidates.graph_serialization import dump_candidate_graph, load_candidate_graph

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = (
    ROOT / "artifacts/phase4/nac/candidate_graph.json",
    ROOT / "artifacts/phase4/itu/candidate_graph.json",
)


@pytest.mark.parametrize("path", ARTIFACTS, ids=("nac", "itu"))
def test_phase4_candidate_graph_round_trip(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    graph = load_candidate_graph(text)

    assert dump_candidate_graph(graph) == text
    assert graph.rules
    assert graph.relations
    assert graph.issues


@pytest.mark.parametrize("path", ARTIFACTS, ids=("nac", "itu"))
def test_phase4_candidate_graph_has_no_structural_errors(path: Path) -> None:
    graph = load_candidate_graph(path.read_text(encoding="utf-8"))

    assert validate_candidate_graph(graph) == graph.findings
    assert not [item for item in graph.findings if item.severity is FindingSeverity.ERROR]


@pytest.mark.parametrize("path", ARTIFACTS, ids=("nac", "itu"))
def test_phase4_exact_quotes_resolve_to_cited_spans(path: Path) -> None:
    graph = load_candidate_graph(path.read_text(encoding="utf-8"))
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
