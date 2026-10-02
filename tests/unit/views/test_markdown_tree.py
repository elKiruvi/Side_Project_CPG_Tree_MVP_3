"""Generic tests for the clinician Markdown tree renderer (synthetic data).

Verifies deterministic generation, the single pending-validation warning,
absence of review questions, no invented sequential edges, BLOCKED/conflict
visibility, and complete rule/relation traceability. No clinical correctness
is asserted.
"""

from __future__ import annotations

import hashlib

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
from cpg_tree.candidates.issues import Issue
from cpg_tree.candidates.observations import Observation
from cpg_tree.candidates.relations import CandidateRelation
from cpg_tree.candidates.rules import CandidateRule
from cpg_tree.candidates.variables import VariableSpec
from cpg_tree.extraction.spans import SourceSpan, SpanRepresentation
from cpg_tree.knowledge.conditions import Condition
from cpg_tree.knowledge.enums import ActionType, ConditionKind, VariableType
from cpg_tree.views.clinical_tree import (
    CANDIDATE_BANNER,
    QuestionRef,
    StageAnchor,
    VisualizationManifest,
)
from cpg_tree.views.markdown_tree import render_clinical_tree_markdown

_PROTOCOL = "SYN-999-v1"
_SEQUENTIAL_EDGE_COUNT = 2


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


def _rule(rule_id: str, state: CandidateState = CandidateState.PROPOSED) -> CandidateRule:
    action = ActionSpec(
        action_id=f"act-{rule_id}",
        action_type=ActionType.DECISION,
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
) -> CandidateGraph:
    rules = (
        _rule(
            "rule-a",
            state=CandidateState.BLOCKED if blocked_rule == "rule-a" else CandidateState.PROPOSED,
        ),
        _rule("rule-b"),
        _rule("rule-c"),
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
        generation_run_id="run-synthetic-phase8md",
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


def _manifest() -> VisualizationManifest:
    return VisualizationManifest(
        protocol_version_id=_PROTOCOL,
        visualization_mode="candidate",
        review_status="AWAITING_CLINICAL_REVIEW",
        clinical_approval=False,
        stages=(StageAnchor("rule-a", "Etapa de prueba"),),
        node_labels={
            "rule-a": "Regla A",
            "rule-b": "Regla B",
            "rule-c": "Regla C",
        },
        branch_labels={
            "rel-flow": "Sí",
            "rel-branch": "Con condición",
            "rel-sup": "Apoya",
        },
        question_map=(QuestionRef("Pregunta 1", ("rule-a",)),),
    )


def test_markdown_tree_is_deterministic() -> None:
    graph = _graph()
    assert render_clinical_tree_markdown(graph, _manifest()) == render_clinical_tree_markdown(
        graph, _manifest()
    )


def test_markdown_tree_has_single_candidate_warning() -> None:
    text = render_clinical_tree_markdown(_graph(), _manifest())
    assert text.count("PENDIENTE DE VALIDACIÓN CLÍNICA") == 1
    assert f"> ⚠️ **{CANDIDATE_BANNER}**" in text


def test_markdown_tree_contains_no_review_questions() -> None:
    text = render_clinical_tree_markdown(_graph(), _manifest())
    assert "Preguntas" not in text
    assert "- [ ]" not in text
    assert "## Pregunta" not in text
    assert "Cómo reportar" not in text


def test_markdown_tree_never_invents_sequential_edges() -> None:
    text = render_clinical_tree_markdown(_graph(), _manifest())
    assert text.count("├─") == _SEQUENTIAL_EDGE_COUNT
    assert "rel-sup" in text.split("## CONTEXTO")[1]
    assert "rel-sup" not in text.split("## CONTEXTO")[0]


def test_blocked_elements_visible_in_markdown() -> None:
    text = render_clinical_tree_markdown(
        _graph(blocked_rule="rule-a", blocked_relation="rel-flow"), _manifest()
    )
    assert "⚠ PENDIENTE" in text
    assert "BLOQUEADA" in text


def test_markdown_tree_covers_every_rule_and_relation() -> None:
    graph = _graph()
    text = render_clinical_tree_markdown(graph, _manifest())
    for rule in graph.rules:
        assert f"rule:{rule.candidate_id}" in text
    for relation in graph.relations:
        assert f"rel:{relation.candidate_relation_id}" in text


def test_markdown_tree_supports_issues_without_resolving_them() -> None:
    graph = _graph()
    graph = CandidateGraph(
        graph_id=graph.graph_id,
        generation_run_id=graph.generation_run_id,
        protocol_version_id=graph.protocol_version_id,
        document_id=graph.document_id,
        extraction_run_id=graph.extraction_run_id,
        observations=graph.observations,
        variables=graph.variables,
        rules=graph.rules,
        relations=graph.relations,
        issues=(
            Issue(
                issue_id="issue-x",
                category=IssueCategory.SOURCE_CONFLICT,
                severity=IssueSeverity.BLOCKING,
                description="conflicto de fuentes",
                related_ids=("rule-b",),
            ),
        ),
        source_spans=graph.source_spans,
        attempts=(),
    )
    text = render_clinical_tree_markdown(graph, _manifest())
    assert "⚠ CONFLICTO" in text
