"""Generic tests for the Phase 5 review-tree projection renderer.

These tests exercise deterministic, protocol-agnostic projection mechanics.
They deliberately assert no clinical content: no rule-to-rule medical
connections are encoded here, only renderer behavior.
"""

from __future__ import annotations

import hashlib

import pytest

from cpg_tree.candidates.actions import ActionSpec
from cpg_tree.candidates.enums import (
    CandidateState,
    EvidenceClass,
    ObservationKind,
    RelationType,
)
from cpg_tree.candidates.evidence import EvidenceBinding
from cpg_tree.candidates.graph import CandidateGraph
from cpg_tree.candidates.observations import Observation
from cpg_tree.candidates.relations import CandidateRelation
from cpg_tree.candidates.rules import CandidateRule
from cpg_tree.candidates.variables import VariableSpec
from cpg_tree.extraction.spans import SourceSpan, SpanRepresentation
from cpg_tree.knowledge.conditions import Condition
from cpg_tree.knowledge.enums import ActionType, ConditionKind, VariableType
from cpg_tree.views.review_tree import (
    ProjectionManifest,
    StageRoot,
    render_review_tree_html,
    render_review_tree_svg,
)

_PROTOCOL = "SYN-999-v1"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _span(span_id: str, page: int = 1, text: str = "Evidence text.") -> SourceSpan:
    return SourceSpan(
        span_id=span_id,
        document_id="doc-synthetic",
        extraction_run_id="run-synthetic",
        page=page,
        representation=SpanRepresentation.TEXT,
        extraction_method="test",
        extracted_text_exact=text,
        text_sha256=_sha(text),
    )


def _binding(claim_path: str, span_id: str) -> EvidenceBinding:
    return EvidenceBinding(
        claim_path=claim_path,
        evidence_class=EvidenceClass.NORMALIZED,
        source_span_refs=(span_id,),
        exact_quote="Evidence text.",
    )


def _rule(
    rule_id: str,
    action_text: str | None = None,
    *,
    state: CandidateState = CandidateState.PROPOSED,
) -> CandidateRule:
    target = action_text or f"{rule_id} action"
    action = ActionSpec(
        action_id=f"act-{rule_id}",
        action_type=ActionType.DECISION,
        target_text=target,
        evidence_bindings=(_binding("/target_text", f"span-{rule_id}"),),
    )
    return CandidateRule(
        candidate_id=rule_id,
        revision=1,
        protocol_version_id=_PROTOCOL,
        condition=Condition(kind=ConditionKind.FLAG, variable_ref="var-a", expected=True),
        actions=(action,),
        observation_refs=(f"obs-{rule_id}",),
        evidence_class=EvidenceClass.NORMALIZED,
        evidence_bindings=(_binding("/condition", f"span-{rule_id}"),),
        candidate_state=state,
    )


def _relation(  # noqa: PLR0913
    relation_id: str,
    source: str,
    target: str,
    relation_type: RelationType,
    *,
    label: str | None = None,
    state: CandidateState = CandidateState.PROPOSED,
) -> CandidateRelation:
    return CandidateRelation(
        candidate_relation_id=relation_id,
        revision=1,
        source_ref=source,
        target_refs=(target,),
        relation_type=relation_type,
        branch_label=label,
        observation_refs=(f"obs-{source}",),
        evidence_class=EvidenceClass.NORMALIZED,
        evidence_bindings=(_binding("/target_refs/0", f"span-{source}"),),
        candidate_state=state,
    )


def _graph(
    relations: tuple[CandidateRelation, ...],
    *,
    extra_rules: tuple[CandidateRule, ...] = (),
) -> CandidateGraph:
    rules = tuple(_rule(rule_id) for rule_id in ("rule-a", "rule-b", "rule-c")) + extra_rules
    spans = (
        *(_span(f"span-{rule.candidate_id}") for rule in rules),
        _span("span-var-a", text="variable evidence"),
    )
    observations = tuple(
        Observation(
            observation_id=f"obs-{rule.candidate_id}",
            kind=ObservationKind.RECOMMENDATION,
            span_refs=(f"span-{rule.candidate_id}",),
            exact_quote="Evidence text.",
        )
        for rule in rules
    )
    variables = (
        VariableSpec(
            variable_id="var-a",
            label="synthetic flag",
            value_type=VariableType.BOOLEAN,
            evidence_bindings=(_binding("/label", "span-var-a"),),
        ),
    )
    return CandidateGraph(
        graph_id="graph-synthetic",
        generation_run_id="run-synthetic-phase5",
        protocol_version_id=_PROTOCOL,
        document_id="doc-synthetic",
        extraction_run_id="run-synthetic",
        observations=observations,
        variables=variables,
        rules=rules,
        relations=relations,
        issues=(),
        source_spans=spans,
        attempts=(),
    )


def _manifest(roots: tuple[str, ...] = ("rule-a",)) -> ProjectionManifest:
    return ProjectionManifest(
        protocol_version_id=_PROTOCOL,
        stages=tuple(StageRoot(rule_id=root, label=f"stage {root}") for root in roots),
    )


def _sequential_svg_map(html_text: str) -> str:
    return html_text.split('<section class="map-wrap">')[1].split("</section>", maxsplit=1)[0]


def test_html_rendering_is_deterministic() -> None:
    graph = _graph(
        (
            _relation("rel-flow-1", "rule-a", "rule-b", RelationType.FLOW),
            _relation("rel-sup-1", "rule-a", "rule-c", RelationType.SUPPORTS),
        )
    )
    manifest = _manifest()
    assert render_review_tree_html(graph, manifest) == render_review_tree_html(graph, manifest)
    assert render_review_tree_svg(graph, manifest) == render_review_tree_svg(graph, manifest)


def test_contextual_relations_are_never_pathway_arrows() -> None:
    graph = _graph(
        (
            _relation("rel-flow-1", "rule-a", "rule-b", RelationType.FLOW),
            _relation("rel-sup-1", "rule-a", "rule-c", RelationType.SUPPORTS),
        )
    )
    manifest = _manifest()
    html_text = render_review_tree_html(graph, manifest)
    svg_text = render_review_tree_svg(graph, manifest)
    svg_map = _sequential_svg_map(html_text)

    assert "rel-flow-1" in svg_map
    assert "rel-sup-1" not in svg_map
    assert "rel-sup-1" not in svg_text
    assert "rel-sup-1" in html_text.split('<section class="contextual">')[1]


def test_blocked_sequential_edge_is_rendered_as_dashed_blocked() -> None:
    graph = _graph(
        (
            _relation(
                "rel-blocked-1",
                "rule-a",
                "rule-c",
                RelationType.BRANCH,
                label="conflicting alternative",
                state=CandidateState.BLOCKED,
            ),
        )
    )
    manifest = _manifest()
    svg_text = render_review_tree_svg(graph, manifest)
    assert "BLOCKED" in svg_text
    assert "pedge.blocked" in svg_text
    assert "conflicting alternative" in svg_text


def test_disconnected_rule_is_listed_but_not_drawn() -> None:
    extra = (_rule("rule-d"),)
    graph = _graph(
        (_relation("rel-flow-1", "rule-a", "rule-b", RelationType.FLOW),),
        extra_rules=extra,
    )
    manifest = _manifest()
    html_text = render_review_tree_html(graph, manifest)
    svg_text = render_review_tree_svg(graph, manifest)

    disconnected = html_text.split('<section class="disconnected">')[1]
    assert "rule-d" in disconnected
    assert 'id="n-rule-d"' not in svg_text


def test_cycle_edge_is_annotated_as_loop() -> None:
    graph = _graph(
        (
            _relation("rel-forward", "rule-a", "rule-b", RelationType.FLOW),
            _relation("rel-back", "rule-b", "rule-a", RelationType.FLOW),
        )
    )
    manifest = _manifest()
    svg_text = render_review_tree_svg(graph, manifest)
    assert "loop" in svg_text


def test_dynamic_text_is_html_escaped() -> None:
    extra = (_rule("rule-d", action_text="alert('<script>&')"),)
    graph = _graph((), extra_rules=extra)
    manifest = _manifest()
    html_text = render_review_tree_html(graph, manifest)
    assert "&lt;script&gt;" in html_text
    assert "<script>" not in html_text


def test_unknown_projection_root_raises() -> None:
    graph = _graph((_relation("rel-flow-1", "rule-a", "rule-b", RelationType.FLOW),))
    manifest = _manifest(roots=("rule-missing",))
    with pytest.raises(ValueError, match="unknown rules"):
        render_review_tree_html(graph, manifest)


def test_protocol_mismatch_between_manifest_and_graph_raises() -> None:
    graph = _graph((_relation("rel-flow-1", "rule-a", "rule-b", RelationType.FLOW),))
    manifest = ProjectionManifest(
        protocol_version_id="OTHER-001-v1",
        stages=(StageRoot(rule_id="rule-a", label="stage"),),
    )
    with pytest.raises(ValueError, match="does not match"):
        render_review_tree_html(graph, manifest)


def test_unreachable_sequential_component_is_reported_as_orphan_edges() -> None:
    extra = (_rule("rule-e"), _rule("rule-x"))
    graph = _graph(
        (
            _relation("rel-flow-1", "rule-a", "rule-b", RelationType.FLOW),
            _relation("rel-orphan-1", "rule-e", "rule-x", RelationType.FLOW),
        ),
        extra_rules=extra,
    )
    manifest = _manifest()
    html_text = render_review_tree_html(graph, manifest)
    svg_text = render_review_tree_svg(graph, manifest)

    assert "Sequential relations not drawn in the map" in html_text
    assert "rel-orphan-1" in html_text.split("Sequential relations not drawn in the map")[1]
    assert "rule-e" in html_text.split('<section class="disconnected">')[1]
    assert "rule-x" in html_text.split('<section class="disconnected">')[1]
    assert "rel-orphan-1" not in svg_text


def test_blocked_and_proposed_states_are_visually_distinguished() -> None:
    extra = (_rule("rule-d", state=CandidateState.BLOCKED),)
    graph = _graph(
        (_relation("rel-flow-1", "rule-a", "rule-b", RelationType.FLOW),),
        extra_rules=extra,
    )
    manifest = _manifest()
    html_text = render_review_tree_html(graph, manifest)
    assert "BLOCKED" in html_text
    assert "PROPOSED" in html_text
