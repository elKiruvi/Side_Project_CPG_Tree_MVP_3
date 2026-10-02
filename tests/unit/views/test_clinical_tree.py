"""Generic Phase 8A clinician visualization tests (synthetic data only).

Tests cover candidate warning behavior, traceability, parity (no invented
edges), BLOCKED/Issue rendering, contextual-subgraph separation, print view,
approved-rendering boundary, engine candidate-safety, and deterministic
non-overlapping layout. No clinical correctness is asserted.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest
import yaml

from cpg_tree.candidates.actions import ActionSpec
from cpg_tree.candidates.enums import (
    CandidateState,
    EvidenceClass,
    IssueCategory,
    IssueSeverity,
    ObservationKind,
    RelationType,
)
from cpg_tree.candidates.evidence import EvidenceBinding
from cpg_tree.candidates.graph import CandidateGraph
from cpg_tree.candidates.graph_serialization import dump_candidate_graph
from cpg_tree.candidates.issues import Issue
from cpg_tree.candidates.observations import Observation
from cpg_tree.candidates.relations import CandidateRelation
from cpg_tree.candidates.rules import CandidateRule
from cpg_tree.candidates.variables import VariableSpec
from cpg_tree.engine import Case, evaluate_package
from cpg_tree.extraction.spans import SourceSpan, SpanRepresentation
from cpg_tree.knowledge.conditions import Condition
from cpg_tree.knowledge.enums import ActionType, ConditionKind, VariableType
from cpg_tree.review.compiler import compile_approved_package
from cpg_tree.review.model import ReviewDecision, ReviewSubjectType, ReviewVerdict
from cpg_tree.review.policy import ApprovalPolicy
from cpg_tree.views.clinical_tree import (
    CANDIDATE_BANNER,
    CANDIDATE_DISCLAIMER,
    QuestionRef,
    StageAnchor,
    VisualizationManifest,
    render_approved_clinical_tree_svg,
    render_clinical_tree_html,
    render_clinical_tree_svg,
    render_print_view_html,
)

_PROTOCOL = "SYN-999-v1"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _span(span_id: str) -> SourceSpan:
    text = f"Evidence for {span_id}."
    return SourceSpan(
        span_id=span_id,
        document_id="doc-synthetic",
        extraction_run_id="run-synthetic",
        page=1,
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
        exact_quote=f"Evidence for {span_id}.",
    )


def _rule(
    rule_id: str,
    action_type: ActionType = ActionType.DECISION,
    state: CandidateState = CandidateState.PROPOSED,
) -> CandidateRule:
    action = ActionSpec(
        action_id=f"act-{rule_id}",
        action_type=action_type,
        target_text=f"{rule_id} action",
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


def _relation(
    relation_id: str,
    source: str,
    target: str,
    relation_type: RelationType = RelationType.FLOW,
    state: CandidateState = CandidateState.PROPOSED,
) -> CandidateRelation:
    return CandidateRelation(
        candidate_relation_id=relation_id,
        revision=1,
        source_ref=source,
        target_refs=(target,),
        relation_type=relation_type,
        branch_label="condition label",
        observation_refs=(f"obs-{source}",),
        evidence_class=EvidenceClass.NORMALIZED,
        evidence_bindings=(_binding("/target_refs/0", f"span-{source}"),),
        candidate_state=state,
    )


def _graph(
    *,
    blocked_rule: str | None = None,
    blocked_relation: str | None = None,
    issues: tuple[Issue, ...] = (),
) -> CandidateGraph:
    rules = (
        _rule(
            "rule-a",
            state=CandidateState.BLOCKED if blocked_rule == "rule-a" else CandidateState.PROPOSED,
        ),
        _rule(
            "rule-b",
            state=CandidateState.BLOCKED if blocked_rule == "rule-b" else CandidateState.PROPOSED,
        ),
        _rule("rule-c", action_type=ActionType.PRESCRIBE),
    )
    relations = (
        _relation(
            "rel-flow",
            "rule-a",
            "rule-b",
            state=CandidateState.BLOCKED
            if blocked_relation == "rel-flow"
            else CandidateState.PROPOSED,
        ),
        _relation("rel-branch", "rule-b", "rule-c", RelationType.BRANCH),
        _relation("rel-sup", "rule-a", "rule-c", RelationType.SUPPORTS),
    )
    spans = (_span("span-rule-a"), _span("span-rule-b"), _span("span-rule-c"), _span("span-var-a"))
    observations = tuple(
        Observation(
            observation_id=f"obs-{rule.candidate_id}",
            kind=ObservationKind.RECOMMENDATION,
            span_refs=(f"span-{rule.candidate_id}",),
            exact_quote=f"Evidence for span-{rule.candidate_id}.",
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
        generation_run_id="run-synthetic-phase8",
        protocol_version_id=_PROTOCOL,
        document_id="doc-synthetic",
        extraction_run_id="run-synthetic",
        observations=observations,
        variables=variables,
        rules=rules,
        relations=relations,
        issues=issues,
        source_spans=spans,
        attempts=(),
    )


def _manifest_v2(
    *,
    node_labels: dict[str, str] | None = None,
    question_map: tuple[tuple[str, tuple[str, ...]], ...] = (),
) -> VisualizationManifest:
    return VisualizationManifest(
        protocol_version_id=_PROTOCOL,
        visualization_mode="candidate",
        review_status="AWAITING_CLINICAL_REVIEW",
        clinical_approval=False,
        stages=(StageAnchor("rule-a", "Etapa de prueba"),),
        node_labels=node_labels or {},
        branch_labels={"rel-flow": "Sí", "rel-branch": "Con condición"},
        question_map=question_map,
    )


def test_candidate_warning_is_prominent() -> None:
    html_text = render_clinical_tree_html(_graph(), _manifest_v2())
    assert CANDIDATE_BANNER in html_text
    assert CANDIDATE_DISCLAIMER in html_text
    assert "AWAITING_CLINICAL_REVIEW" in html_text
    assert "aprobación clínica: NO" in html_text
    banner_position = html_text.index(CANDIDATE_BANNER)
    assert banner_position < html_text.index("<main>")


def test_candidate_mode_never_claims_approval() -> None:
    html_text = render_clinical_tree_html(_graph(), _manifest_v2())
    assert "clínicamente aprobado" not in html_text.lower()
    assert "validado clínicamente" not in html_text.lower()


def test_rendering_is_deterministic() -> None:
    graph = _graph()
    manifest = _manifest_v2()
    assert render_clinical_tree_html(graph, manifest) == render_clinical_tree_html(graph, manifest)
    assert render_clinical_tree_svg(graph, manifest) == render_clinical_tree_svg(graph, manifest)
    assert render_print_view_html(graph, manifest) == render_print_view_html(graph, manifest)


def test_node_and_edge_traceability() -> None:
    graph = _graph()
    svg_text = render_clinical_tree_svg(graph, _manifest_v2())
    for rule in graph.rules:
        assert f'id="n-{rule.candidate_id}"' in svg_text
        assert f'data-candidate-id="{rule.candidate_id}"' in svg_text
        assert f'data-content-hash="{rule.content_hash}"' in svg_text
    for relation in graph.relations:
        if relation.relation_type in (RelationType.FLOW, RelationType.BRANCH):
            assert f'id="e-{relation.candidate_relation_id}"' in svg_text
            assert f'data-content-hash="{relation.content_hash}"' in svg_text


def test_contextual_relations_never_become_arrows() -> None:
    svg_text = render_clinical_tree_svg(_graph(), _manifest_v2())
    assert 'id="e-rel-flow"' in svg_text
    assert 'id="e-rel-branch"' in svg_text
    assert 'id="e-rel-sup"' not in svg_text
    html_text = render_clinical_tree_html(_graph(), _manifest_v2())
    assert "rel-sup" in html_text.split("Relaciones contextuales")[1]


def test_blocked_rule_and_edge_rendering() -> None:
    graph = _graph(blocked_rule="rule-a", blocked_relation="rel-flow")
    svg_text = render_clinical_tree_svg(graph, _manifest_v2())
    assert "bloqueado" in svg_text
    assert "Requiere revisión" in svg_text
    assert "BLOQUEADA — requiere revisión" in svg_text
    html_text = render_clinical_tree_html(graph, _manifest_v2())
    assert "NO significa rechazado" in html_text


def test_issue_rendering_and_question_association() -> None:
    graph = _graph(
        issues=(
            Issue(
                issue_id="issue-x",
                category=IssueCategory.SOURCE_CONFLICT,
                severity=IssueSeverity.BLOCKING,
                description="conflicto de fuentes",
                related_ids=("rule-b",),
            ),
        )
    )
    manifest = _manifest_v2(
        question_map=(QuestionRef(label="Pregunta 1 — ¿es correcto?", related=("rule-b",)),)
    )
    html_text = render_clinical_tree_html(graph, manifest)
    assert "issue-x" in html_text
    assert "conflicto de fuentes" in html_text
    assert "Conflicto entre fuentes" in html_text
    assert "Pregunta 1 — ¿es correcto?" in html_text
    svg_text = render_clinical_tree_svg(graph, manifest)
    assert "pendiente(s) de revisión" in svg_text


def test_print_view_generated_without_controls() -> None:
    print_text = render_print_view_html(_graph(), _manifest_v2())
    assert CANDIDATE_BANNER in print_text
    assert 'id="controls"' not in print_text
    assert "@media print" in print_text


def test_approved_renderer_boundary_synthetic() -> None:
    graph = _graph()
    decisions = tuple(
        ReviewDecision(
            decision_id=f"d-{item_id}",
            subject_type=subject,
            candidate_id=item_id,
            candidate_revision=1,
            candidate_content_hash=content_hash or "",
            verdict=ReviewVerdict.APPROVE,
            reviewer_id="rev-1",
            reviewed_at="2026-10-05T10:00:00Z",
        )
        for item_id, subject, content_hash in (
            (rule.candidate_id, ReviewSubjectType.RULE, rule.content_hash) for rule in graph.rules
        )
    ) + tuple(
        ReviewDecision(
            decision_id=f"d-{relation.candidate_relation_id}",
            subject_type=ReviewSubjectType.RELATION,
            candidate_id=relation.candidate_relation_id,
            candidate_revision=1,
            candidate_content_hash=relation.content_hash or "",
            verdict=ReviewVerdict.APPROVE,
            reviewer_id="rev-1",
            reviewed_at="2026-10-05T10:00:00Z",
        )
        for relation in graph.relations
    )
    package = compile_approved_package(
        graph, decisions, ApprovalPolicy(name="single", minimum_decisions=1)
    )
    svg_text = render_approved_clinical_tree_svg(package, _manifest_v2())
    assert "APROBADO" in svg_text
    assert CANDIDATE_BANNER not in svg_text
    assert "Requiere revisión" not in svg_text


def test_engine_rejects_candidate_graph_fail_closed() -> None:
    graph = _graph()
    case = Case({})
    with pytest.raises(TypeError, match="never be executed"):
        evaluate_package(graph, case)  # type: ignore[arg-type]


def test_layout_has_no_overlapping_nodes() -> None:
    svg_text = render_clinical_tree_svg(_graph(), _manifest_v2())
    rects = re.findall(
        r'<rect class="node[^"]*" x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"',
        svg_text,
    )
    boxes = [(float(x), float(y), float(w), float(h)) for x, y, w, h in rects]
    assert len(boxes) >= len(_graph().rules)
    for index, (x1, y1, w1, h1) in enumerate(boxes):
        for x2, y2, w2, h2 in boxes[index + 1 :]:
            assert x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1


def test_candidate_svg_contains_visible_warning_text() -> None:
    svg_text = render_clinical_tree_svg(_graph(), _manifest_v2())
    assert CANDIDATE_BANNER in svg_text
    assert CANDIDATE_DISCLAIMER in svg_text
    assert "aprobación clínica: NO" in svg_text
    assert '<text class="aviso-titulo"' in svg_text


def test_visualization_manifest_is_presentation_only() -> None:
    raw = yaml.safe_load(
        Path("artifacts/phase8/nac/visualization.yaml").read_text(encoding="utf-8")
    )
    allowed = {
        "schema",
        "protocol_version_id",
        "visualization_mode",
        "review_status",
        "clinical_approval",
        "stages",
        "node_labels",
        "branch_labels",
        "question_map",
        "notes",
    }
    assert set(raw) <= allowed
    manifest = _manifest_v2()
    graph = _graph()
    before = hashlib.sha256(dump_candidate_graph(graph).encode("utf-8")).hexdigest()
    render_clinical_tree_html(graph, manifest)
    render_clinical_tree_svg(graph, manifest)
    after = hashlib.sha256(dump_candidate_graph(graph).encode("utf-8")).hexdigest()
    assert before == after


def test_html_inventory_lists_every_rule_and_relation() -> None:
    graph = _graph()
    html_text = render_clinical_tree_html(graph, _manifest_v2())
    inventory = html_text.split("Inventario completo de candidatos")[1]
    for rule in graph.rules:
        assert rule.candidate_id in inventory
    for relation in graph.relations:
        assert relation.candidate_relation_id in inventory
