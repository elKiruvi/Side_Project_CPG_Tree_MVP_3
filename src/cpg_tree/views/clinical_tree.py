"""Clinician-facing candidate tree visualization (Phase 8A).

The renderer is a pure presentation layer over a ``CandidateGraph`` (and, via
a separate entry point, over an ``ApprovedKnowledgePackage``). It never
invents rules, edges, branches, operators, or approvals. Candidate output is
always prominently labelled:

    ÁRBOL CANDIDATO — PENDIENTE DE VALIDACIÓN CLÍNICA

Design:

- The layout core consumes a small intermediate projection model, so the same
  deterministic layered layout serves both candidate and approved rendering.
- Only canonical FLOW/BRANCH relations are drawn as pathway arrows.
  Contextual relations are listed in a separate section.
- BLOCKED candidates use warning styling plus a text label (never color
  alone); Issues get visible markers and an inspection panel.
- Node/edge ids and content hashes are embedded as data attributes for
  traceability and parity validation.
- The HTML is a single self-contained static document with minimal vanilla
  JavaScript (review/pathway modes, node details, filters). No backend, no
  framework, no external resources.
"""

# ruff: noqa: C901, PLR0912, PLR0915, TRY004

from __future__ import annotations

import html
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from cpg_tree.candidates.enums import CandidateState, RelationType
from cpg_tree.candidates.graph import CandidateGraph
from cpg_tree.candidates.relations import CandidateRelation
from cpg_tree.candidates.rules import CandidateRule
from cpg_tree.extraction.spans import SpanQualityFlag
from cpg_tree.knowledge.approved import ApprovedKnowledgePackage
from cpg_tree.knowledge.enums import ActionType
from cpg_tree.views.expression import render_operand

VISUALIZATION_SCHEMA = "visualization-v1"
CANDIDATE_MODE = "candidate"
AWAITING_CLINICAL_REVIEW = "AWAITING_CLINICAL_REVIEW"

CANDIDATE_BANNER = "ÁRBOL CANDIDATO — PENDIENTE DE VALIDACIÓN CLÍNICA"
CANDIDATE_DISCLAIMER = (
    "Este árbol fue generado a partir del protocolo institucional y aún no ha "
    "sido aprobado por personal clínico."
)

_NODE_W = 252.0
_NODE_H = 168.0
_H_GAP = 92.0
_V_GAP = 24.0
_MARGIN = 44.0
_SVG_HEADER_H = 84.0

_ACTION_KIND: dict[ActionType, str] = {
    ActionType.DECISION: "Decisión",
    ActionType.CLASSIFY: "Decisión",
    ActionType.REQUEST_TEST: "Diagnóstico",
    ActionType.PRESCRIBE: "Tratamiento",
    ActionType.ADMIT: "Disposición",
    ActionType.DISCHARGE: "Disposición",
    ActionType.FOLLOW_UP: "Seguimiento",
    ActionType.EDUCATE: "Seguimiento",
    ActionType.RESTRICTION: "Contexto",
}


@dataclass(frozen=True, slots=True)
class StageAnchor:
    """Projection root: rule id plus Spanish stage label."""

    rule_id: str
    label: str


@dataclass(frozen=True, slots=True)
class QuestionRef:
    """Presentation mapping: a Phase 7 review question and related node ids."""

    label: str
    related: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VisualizationManifest:
    """Presentation-only configuration for one clinician visualization."""

    protocol_version_id: str
    visualization_mode: str
    review_status: str
    clinical_approval: bool
    stages: tuple[StageAnchor, ...]
    node_labels: Mapping[str, str]
    branch_labels: Mapping[str, str]
    question_map: tuple[QuestionRef, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.visualization_mode != CANDIDATE_MODE:
            raise ValueError("Phase 8A manifests must declare visualization_mode 'candidate'")
        if self.clinical_approval:
            raise ValueError("candidate visualizations must declare clinical_approval: false")
        if not self.stages:
            raise ValueError("VisualizationManifest requires stage roots")


def load_visualization_manifest(path: Path) -> VisualizationManifest:
    """Load and validate a visualization manifest (strict, deterministic)."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError(f"{path.name} root must be a mapping")
    if raw.get("schema") != VISUALIZATION_SCHEMA:
        raise ValueError(f"{path.name} requires schema {VISUALIZATION_SCHEMA!r}")
    stages_raw = raw.get("stages")
    stages: list[StageAnchor] = []
    if isinstance(stages_raw, list):
        for entry in stages_raw:
            if not isinstance(entry, Mapping):
                raise ValueError(f"{path.name} stage entries must be mappings")
            label = entry.get("label")
            roots = entry.get("roots")
            if not isinstance(label, str) or not isinstance(roots, list):
                raise ValueError(f"{path.name} stage entries require label and roots")
            for root in roots:
                if isinstance(root, str) and root:
                    stages.append(StageAnchor(rule_id=root, label=label))
    node_labels = raw.get("node_labels", {})
    branch_labels = raw.get("branch_labels", {})
    if not isinstance(node_labels, Mapping) or not isinstance(branch_labels, Mapping):
        raise ValueError(f"{path.name} node_labels/branch_labels must be mappings")
    question_map: list[QuestionRef] = []
    for entry in raw.get("question_map", []) or []:
        if not isinstance(entry, Mapping):
            raise ValueError(f"{path.name} question_map entries must be mappings")
        label = entry.get("label")
        related = entry.get("related", [])
        if isinstance(label, str) and isinstance(related, list):
            question_map.append(
                QuestionRef(
                    label=label, related=tuple(item for item in related if isinstance(item, str))
                )
            )
    notes = raw.get("notes", [])
    return VisualizationManifest(
        protocol_version_id=raw.get("protocol_version_id", ""),
        visualization_mode=raw.get("visualization_mode", ""),
        review_status=raw.get("review_status", ""),
        clinical_approval=bool(raw.get("clinical_approval", False)),
        stages=tuple(stages),
        node_labels={str(key): str(value) for key, value in node_labels.items()},
        branch_labels={str(key): str(value) for key, value in branch_labels.items()},
        question_map=tuple(question_map),
        notes=tuple(str(item) for item in notes if isinstance(item, str)),
    )


@dataclass(frozen=True, slots=True)
class _NodeV:
    node_id: str
    content_hash: str
    kind_es: str
    label_es: str
    condition_text: str
    state: str
    issue_ids: tuple[str, ...]
    pages: tuple[int, ...]
    quotes: tuple[str, ...]
    visual_evidence: bool
    level: int
    index: int
    is_root: bool
    stage_label: str | None


@dataclass(frozen=True, slots=True)
class _EdgeV:
    edge_id: str
    content_hash: str
    source: str
    target: str
    label_es: str
    kind_es: str
    blocked: bool
    cycle: bool


@dataclass(frozen=True, slots=True)
class _Layout:
    nodes: tuple[_NodeV, ...]
    edges: tuple[_EdgeV, ...]
    contextual: tuple[tuple[str, str, str, str, str], ...]  # id, source, targets, type_es, label
    disconnected: tuple[tuple[str, str, str], ...]  # id, label_es, state
    issues: tuple[tuple[str, str, str, str], ...]  # id, category_es, description, related


def _rule_issue_ids(graph: CandidateGraph, rule_id: str) -> tuple[str, ...]:
    return tuple(sorted(issue.issue_id for issue in graph.issues if rule_id in issue.related_ids))


def _fallback_label(rule: CandidateRule) -> str:
    if rule.actions and rule.actions[0].target_text:
        return str(rule.actions[0].target_text)
    return str(rule.candidate_id)


def _issue_category_es(category: str) -> str:
    return {
        "SOURCE_CONFLICT": "Conflicto entre fuentes",
        "AMBIGUITY": "Ambigüedad",
        "MISSING_EVIDENCE": "Evidencia faltante",
        "EXTRACTION_LIMITATION": "Limitación de extracción",
        "SOURCE_CONTENT_ABSENT": "Contenido ausente",
        "TABLE_ALIGNMENT": "Alineación de tabla",
        "NEGATION_UNCERTAIN": "Negación incierta",
        "UNIT_UNCERTAIN": "Unidad incierta",
        "RELATION_UNCERTAIN": "Relación incierta",
        "OUT_OF_SCOPE": "Fuera de alcance",
    }.get(category, category)


def _build_candidate_layout(graph: CandidateGraph, manifest: VisualizationManifest) -> _Layout:
    rules = {rule.candidate_id: rule for rule in graph.rules}
    unknown_roots = [stage.rule_id for stage in manifest.stages if stage.rule_id not in rules]
    if unknown_roots:
        raise ValueError(f"unknown stage roots: {sorted(unknown_roots)}")
    sequential = sorted(
        (
            relation
            for relation in graph.relations
            if relation.relation_type in (RelationType.FLOW, RelationType.BRANCH)
        ),
        key=lambda relation: relation.candidate_relation_id,
    )
    adjacency: dict[str, list[tuple[CandidateRelation, str]]] = {rule_id: [] for rule_id in rules}
    for relation in sequential:
        adjacency.setdefault(relation.source_ref, []).extend(
            (relation, target) for target in relation.target_refs
        )
    levels: dict[str, int] = {}
    node_order: list[str] = []
    roots = tuple(stage.rule_id for stage in manifest.stages)
    for rule_id in roots:
        if rule_id not in levels:
            levels[rule_id] = 0
            node_order.append(rule_id)
    cursor = 0
    while cursor < len(node_order):
        current = node_order[cursor]
        cursor += 1
        for _, target in adjacency.get(current, ()):
            candidate = levels[current] + 1
            if target not in levels:
                levels[target] = candidate
                node_order.append(target)
            elif candidate < levels[target]:
                levels[target] = candidate
    for _ in range(max(levels.values(), default=0) + 1):
        changed = False
        for rule_id in node_order:
            for _, target in adjacency.get(rule_id, ()):
                if levels[target] > levels[rule_id] + 1:
                    levels[target] = levels[rule_id] + 1
                    changed = True
        if not changed:
            break
    columns: dict[int, list[str]] = {}
    for rule_id in node_order:
        columns.setdefault(levels[rule_id], []).append(rule_id)
    for entries in columns.values():
        entries.sort()
    positions = {
        rule_id: (level, index)
        for level, entries in columns.items()
        for index, rule_id in enumerate(entries)
    }
    stage_by_root = {stage.rule_id: stage.label for stage in manifest.stages}
    nodes: list[_NodeV] = []
    for rule_id, (level, index) in sorted(positions.items(), key=lambda item: item[1]):
        rule = rules[rule_id]
        pages, quotes, visual = _rule_evidence(graph, rule)
        label_es = manifest.node_labels.get(rule_id, _fallback_label(rule))
        kind_es = (
            _ACTION_KIND.get(rule.actions[0].action_type, "Acción") if rule.actions else "Decisión"
        )
        try:
            condition_text = render_operand(rule.condition)
        except ValueError:
            condition_text = "(condición no representable)"
        nodes.append(
            _NodeV(
                node_id=rule_id,
                content_hash=rule.content_hash or "",
                kind_es=kind_es,
                label_es=label_es,
                condition_text=condition_text,
                state=rule.candidate_state.value,
                issue_ids=_rule_issue_ids(graph, rule_id),
                pages=tuple(sorted(pages)),
                quotes=quotes,
                visual_evidence=visual,
                level=level,
                index=index,
                is_root=rule_id in stage_by_root,
                stage_label=stage_by_root.get(rule_id),
            )
        )
    edges: list[_EdgeV] = []
    seen: set[tuple[str, str]] = set()
    for relation in sequential:
        for target in relation.target_refs:
            pair = (relation.candidate_relation_id, target)
            if pair in seen or relation.source_ref not in positions or target not in positions:
                continue
            seen.add(pair)
            label_es = manifest.branch_labels.get(
                relation.candidate_relation_id, relation.branch_label or "—"
            )
            edges.append(
                _EdgeV(
                    edge_id=relation.candidate_relation_id,
                    content_hash=relation.content_hash or "",
                    source=relation.source_ref,
                    target=target,
                    label_es=label_es,
                    kind_es="Secuencia" if relation.relation_type is RelationType.FLOW else "Rama",
                    blocked=relation.candidate_state is CandidateState.BLOCKED,
                    cycle=_can_reach(adjacency, target, relation.source_ref),
                )
            )
    contextual: list[tuple[str, str, str, str, str]] = []
    for relation in sorted(
        (
            item
            for item in graph.relations
            if item.relation_type not in (RelationType.FLOW, RelationType.BRANCH)
        ),
        key=lambda item: item.candidate_relation_id,
    ):
        contextual.append(
            (
                relation.candidate_relation_id,
                relation.source_ref,
                ", ".join(relation.target_refs),
                _relation_type_es(relation.relation_type.value),
                manifest.branch_labels.get(
                    relation.candidate_relation_id, relation.branch_label or "—"
                ),
            )
        )
    disconnected: list[tuple[str, str, str]] = []
    for rule in sorted(graph.rules, key=lambda item: item.candidate_id):
        if rule.candidate_id not in positions:
            disconnected.append(
                (
                    rule.candidate_id,
                    manifest.node_labels.get(rule.candidate_id, _fallback_label(rule)),
                    rule.candidate_state.value,
                )
            )
    issues = tuple(
        (
            issue.issue_id,
            _issue_category_es(issue.category.value),
            issue.description,
            ", ".join(issue.related_ids),
        )
        for issue in sorted(graph.issues, key=lambda item: item.issue_id)
    )
    return _Layout(
        nodes=tuple(nodes),
        edges=tuple(edges),
        contextual=tuple(contextual),
        disconnected=tuple(disconnected),
        issues=issues,
    )


def _rule_evidence(
    graph: CandidateGraph, rule: CandidateRule
) -> tuple[set[int], tuple[str, ...], bool]:
    spans: set[str] = set()
    for binding in rule.evidence_bindings:
        spans.update(binding.source_span_refs)
    for action in rule.actions:
        for binding in action.evidence_bindings:
            spans.update(binding.source_span_refs)
    pages: set[int] = set()
    quotes: list[str] = []
    visual = False
    for span_id in sorted(spans):
        span = next((item for item in graph.source_spans if item.span_id == span_id), None)
        if span is None:
            continue
        pages.add(span.page)
        if SpanQualityFlag.VISUAL_ONLY in span.quality_flags:
            visual = True
            quotes.append(f"[Evidencia visual — requiere revisión manual] p.{span.page}")
        else:
            text = span.extracted_text_exact or ""
            quotes.append(f"p.{span.page}: “{text[:220]}”")
    return pages, tuple(quotes), visual


def _relation_type_es(relation_type: str) -> str:
    return {
        "SUPPORTS": "Apoya",
        "REFERENCE": "Referencia",
        "BRANCH_CONTEXT": "Contexto de rama",
        "EXCEPTION_CONTEXT": "Contexto de excepción",
        "COMPOSITION": "Composición",
        "DECLARES_ACTION": "Declara acción",
    }.get(relation_type, relation_type)


def _can_reach(
    adjacency: dict[str, list[tuple[CandidateRelation, str]]], start: str, goal: str
) -> bool:
    seen: set[str] = set()
    frontier = [start]
    while frontier:
        current = frontier.pop()
        if current == goal:
            return True
        if current in seen:
            continue
        seen.add(current)
        frontier.extend(target for _, target in adjacency.get(current, ()))
    return False


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _truncate(text: str, width: int, max_lines: int) -> list[str]:
    lines = _wrap(text, width)
    if len(lines) <= max_lines:
        return lines
    kept = lines[:max_lines]
    kept[-1] = f"{kept[-1][: width - 1]}…"
    return kept


def render_clinical_tree_svg(graph: CandidateGraph, manifest: VisualizationManifest) -> str:
    """Render the candidate pathway as a standalone SVG (Spanish labels)."""
    layout = _build_candidate_layout(graph, manifest)
    positions = {
        node.node_id: (
            _MARGIN + node.level * (_NODE_W + _H_GAP),
            _MARGIN + _SVG_HEADER_H + node.index * (_NODE_H + _V_GAP),
        )
        for node in layout.nodes
    }
    max_level = max((node.level for node in layout.nodes), default=0)
    max_rows = max((node.index for node in layout.nodes), default=0)
    width = _MARGIN * 2 + (max_level + 1) * (_NODE_W + _H_GAP) - _H_GAP
    height = _MARGIN * 2 + _SVG_HEADER_H + (max_rows + 1) * (_NODE_H + _V_GAP) - _V_GAP
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'width="{width:.0f}" height="{height:.0f}" role="img" '
        'aria-label="Árbol candidato — pendiente de validación clínica">',
        "<style>",
        ".aviso-titulo { font: 800 15px sans-serif; fill: #b3261e; }",
        ".aviso-texto { font: 11.5px sans-serif; fill: #374151; }",
        ".node { fill: #ffffff; stroke-width: 1.6; }",
        ".node.propuesto { stroke: #0f4c81; }",
        ".node.bloqueado { stroke: #b3261e; stroke-dasharray: 8 5; }",
        ".node.raiz { stroke-width: 2.6; }",
        ".node-tipo { font: 700 10px sans-serif; letter-spacing: .05em; text-transform: uppercase; }",
        ".node-tipo.propuesto { fill: #0f4c81; }",
        ".node-tipo.bloqueado { fill: #b3261e; }",
        ".node-titulo { font: 600 12.5px sans-serif; fill: #1f2937; }",
        ".node-condicion { font: 10px ui-monospace, Menlo, monospace; fill: #6b7280; }",
        ".node-meta { font: 10px sans-serif; fill: #6b7280; }",
        ".node-alerta { font: 700 11px sans-serif; fill: #b3261e; }",
        ".edge { fill: none; stroke-width: 1.5; }",
        ".edge.secuencia { stroke: #0f4c81; }",
        ".edge.rama { stroke: #374151; }",
        ".edge.bloqueada { stroke: #b3261e; stroke-dasharray: 7 5; }",
        ".edge.ciclo { stroke-dasharray: 3 4; }",
        ".edge-etiqueta { font: 10px sans-serif; fill: #374151; }",
        ".edge-etiqueta.bloqueada { fill: #b3261e; }",
        ".etapa { font: 700 10px sans-serif; fill: #7a4a9e; }",
        "</style>",
        "<defs>",
        '<marker id="arrow-accent" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#0f4c81"/></marker>',
        '<marker id="arrow-ink" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#374151"/></marker>',
        '<marker id="arrow-blocked" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#b3261e"/></marker>',
        "</defs>",
        '<g class="aviso">',
        f'<text class="aviso-titulo" x="{_MARGIN:.0f}" y="26">{CANDIDATE_BANNER}</text>',
        f'<text class="aviso-texto" x="{_MARGIN:.0f}" y="46">{CANDIDATE_DISCLAIMER}</text>',
        f'<text class="aviso-texto" x="{_MARGIN:.0f}" y="64">Protocolo {graph.protocol_version_id} · '
        f"estado: AWAITING_CLINICAL_REVIEW · aprobación clínica: NO</text>",
        "</g>",
    ]
    for node in layout.nodes:
        x, y = positions[node.node_id]
        state_class = "bloqueado" if node.state == "BLOCKED" else "propuesto"
        root_class = " raiz" if node.is_root else ""
        parts.append(
            f'<g id="n-{html.escape(node.node_id, quote=True)}" '
            f'data-candidate-id="{html.escape(node.node_id, quote=True)}" '
            f'data-content-hash="{node.content_hash}">'
        )
        parts.append(
            f'<rect class="node {state_class}{root_class}" x="{x:.0f}" y="{y:.0f}" '
            f'width="{_NODE_W:.0f}" height="{_NODE_H:.0f}" rx="7"/>'
        )
        text_y = y + 18.0
        parts.append(
            f'<text class="node-tipo {state_class}" x="{x + 10:.0f}" y="{text_y:.0f}">'
            f"{html.escape(node.kind_es, quote=True)} · "
            f"{html.escape('PENDIENTE' if node.state == 'BLOCKED' else 'PROPUESTO', quote=True)}</text>"
        )
        text_y += 15.0
        for line in _truncate(node.label_es, 34, 3):
            parts.append(
                f'<text class="node-titulo" x="{x + 10:.0f}" y="{text_y:.0f}">{html.escape(line, quote=True)}</text>'
            )
            text_y += 14.0
        for line in _truncate(node.condition_text, 32, 2):
            parts.append(
                f'<text class="node-condicion" x="{x + 10:.0f}" y="{text_y:.0f}">{html.escape(line, quote=True)}</text>'
            )
            text_y += 12.0
        meta = f"p.{','.join(str(p) for p in node.pages)}" if node.pages else "sin página"
        if node.issue_ids:
            meta += f" · {len(node.issue_ids)} pendiente(s) de revisión"
        parts.append(
            f'<text class="node-meta" x="{x + 10:.0f}" y="{y + _NODE_H - 18:.0f}">{html.escape(meta, quote=True)}</text>'
        )
        if node.state == "BLOCKED" or node.issue_ids:
            parts.append(
                f'<text class="node-alerta" x="{x + 10:.0f}" y="{y + _NODE_H - 6:.0f}">⚠ Requiere revisión</text>'
            )
        if node.is_root and node.stage_label:
            parts.append(
                f'<text class="etapa" x="{x + 10:.0f}" y="{y + 14:.0f}">Etapa: {html.escape(node.stage_label, quote=True)}</text>'
            )
        parts.append("</g>")
    for edge in layout.edges:
        sx, sy = positions[edge.source]
        tx, ty = positions[edge.target]
        start = (sx + _NODE_W, sy + _NODE_H / 2)
        end = (tx, ty + _NODE_H / 2)
        classes = ["edge", "secuencia" if edge.kind_es == "Secuencia" else "rama"]
        if edge.blocked:
            classes.append("bloqueada")
        if edge.cycle:
            classes.append("ciclo")
        marker = (
            "arrow-blocked"
            if edge.blocked
            else ("arrow-accent" if edge.kind_es == "Secuencia" else "arrow-ink")
        )
        control = (start[0] + (end[0] - start[0]) / 2, start[1])
        parts.append(
            f'<path id="e-{html.escape(edge.edge_id, quote=True)}" class="{" ".join(classes)}" '
            f'data-relation-id="{html.escape(edge.edge_id, quote=True)}" data-content-hash="{edge.content_hash}" '
            f'd="M {start[0]:.0f} {start[1]:.0f} C {control[0]:.0f} {start[1]:.0f} {control[0]:.0f} {end[1]:.0f} '
            f'{end[0]:.0f} {end[1]:.0f}" marker-end="url(#{marker})"/>'
        )
        bits = [edge.label_es]
        if edge.blocked:
            bits.append("BLOQUEADA — requiere revisión")
        if edge.cycle:
            bits.append("bucle")
        parts.append(
            f'<text class="edge-etiqueta{" bloqueada" if edge.blocked else ""}" '
            f'x="{control[0]:.0f}" y="{(start[1] + end[1]) / 2 - 6:.0f}" text-anchor="middle">'
            f"{html.escape(' · '.join(bits), quote=True)}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def render_clinical_tree_html(graph: CandidateGraph, manifest: VisualizationManifest) -> str:
    """Render the interactive self-contained clinician HTML (candidate mode)."""
    layout = _build_candidate_layout(graph, manifest)
    svg = render_clinical_tree_svg(graph, manifest)
    details = _details_payload(graph, manifest, layout)
    parts = [
        "<!DOCTYPE html>",
        '<html lang="es"><head><meta charset="utf-8">',
        f"<title>Árbol candidato — {graph.protocol_version_id}</title>",
        _HTML_CSS,
        _HTML_JS,
        '</head><body class="mode-review">',
        '<header class="banner">',
        f"<h1>{CANDIDATE_BANNER}</h1>",
        f"<p>{CANDIDATE_DISCLAIMER}</p>",
        '<p class="meta">Protocolo '
        f"{html.escape(graph.protocol_version_id, quote=True)} · documento "
        f"{html.escape(graph.document_id, quote=True)} · estado: AWAITING_CLINICAL_REVIEW · "
        f"aprobación clínica: NO</p>",
        "</header>",
        '<main><section class="controls" id="controls">',
        '<div class="modes">',
        '<button data-mode="review" class="active" aria-pressed="true">Modo revisión</button>',
        '<button data-mode="pathway" aria-pressed="false">Modo vía</button>',
        "</div>",
        '<div class="filters">',
        '<label><input type="checkbox" id="filter-blocked" checked> Mostrar pendientes de revisión</label>',
        '<label><input type="checkbox" id="filter-issues" checked> Mostrar conflictos/Issues</label>',
        "</div>",
        "</section>",
        '<section class="legend" aria-label="Leyenda"><h2>Leyenda</h2><ul>',
        '<li class="li-propuesto">Propuesto — candidato pendiente de revisión</li>',
        '<li class="li-bloqueado">Pendiente de revisión — evidencia sin resolver (NO significa rechazado)</li>',
        '<li class="li-secuencia">Flecha continua — secuencia propuesta</li>',
        '<li class="li-rama">Flecha con etiqueta — rama condicionada (solo la rama definida por el protocolo; no se inventan alternativas)</li>',
        '<li class="li-bloqueada">Flecha discontinua roja — relación pendiente de revisión / conflicto</li>',
        '<li class="li-etapa">Etapa — ancla de proyección (solo presentación)</li>',
        "</ul></section>",
        '<div class="layout"><section class="map" aria-label="Árbol clínico candidato">',
        '<div class="map-toolbar">',
        '<button id="zoom-in" aria-label="Acercar">+</button>',
        '<button id="zoom-out" aria-label="Alejar">-</button>',
        "</div>",
        '<div class="svg-wrap" id="svg-wrap">',
        svg,
        "</div>",
        "</section>",
        '<aside class="details" id="details" aria-live="polite">',
        "<h2>Detalle del elemento</h2>",
        '<p id="details-empty">Seleccione un nodo (caja) del árbol para ver su '
        "condición, acción, evidencia e Issues. Seleccione una flecha para ver "
        "la relación.</p>",
        '<div id="details-content" hidden></div>',
        "</aside></div>",
        _contextual_section(layout),
        _disconnected_section(layout),
        _issues_section(layout),
        _inventory_section(graph, manifest, layout),
        _questions_section(manifest),
        '<footer class="disclaimer">',
        "<p>ÁRBOL CANDIDATO — PENDIENTE DE VALIDACIÓN CLÍNICA. Este árbol fue "
        "generado a partir del protocolo institucional y aún no ha sido aprobado "
        "por personal clínico. No sustituye el juicio clínico ni debe usarse "
        "como soporte de decisiones asistenciales.</p>",
        "</footer></main>",
        '<script type="application/json" id="details-data">',
        details,
        "</script>",
        "</body></html>",
    ]
    return "\n".join(parts) + "\n"


def _details_payload(
    graph: CandidateGraph, manifest: VisualizationManifest, layout: _Layout
) -> str:
    node_details = {
        node.node_id: {
            "tipo": "Regla candidata",
            "elemento": node.node_id,
            "estado": node.state,
            "clase": node.kind_es,
            "condicion": node.condition_text,
            "accion": _action_text(graph, node.node_id),
            "pagina": ", ".join(str(p) for p in node.pages) or "—",
            "evidencia": list(node.quotes),
            "evidencia_visual": node.visual_evidence,
            "issues": list(node.issue_ids),
            "hash": node.content_hash,
            "preguntas": _questions_for(manifest, node.node_id),
        }
        for node in layout.nodes
    }
    edge_details = {
        edge.edge_id: {
            "tipo": "Relación candidata",
            "elemento": edge.edge_id,
            "estado": "BLOQUEADA" if edge.blocked else "PROPUESTA",
            "clase": edge.kind_es,
            "condicion": edge.label_es,
            "accion": f"{edge.source} → {edge.target}",
            "pagina": "—",
            "evidencia": [],
            "evidencia_visual": False,
            "issues": [],
            "hash": edge.content_hash,
            "preguntas": _questions_for(manifest, edge.edge_id),
        }
        for edge in layout.edges
    }
    return json.dumps(
        {"nodes": node_details, "edges": edge_details},
        ensure_ascii=False,
        sort_keys=True,
    )


def _action_text(graph: CandidateGraph, rule_id: str) -> str:
    rule = next((item for item in graph.rules if item.candidate_id == rule_id), None)
    if rule is None or not rule.actions:
        return "—"
    return rule.actions[0].target_text or "—"


def _questions_for(manifest: VisualizationManifest, related: str) -> list[str]:
    return [question.label for question in manifest.question_map if related in question.related]


def _contextual_section(layout: _Layout) -> str:
    parts = [
        '<section class="contextual"><h2>Relaciones contextuales '
        '<span class="sub">(no son secuencia clínica)</span></h2>',
    ]
    if layout.contextual:
        parts.append(
            "<table><thead><tr><th>Relación</th><th>Origen</th><th>Destino</th>"
            "<th>Tipo</th><th>Nota</th></tr></thead><tbody>"
        )
        for relation_id, source, targets, type_es, label in layout.contextual:
            parts.append(
                f"<tr><td>{html.escape(relation_id, quote=True)}</td>"
                f"<td>{html.escape(source, quote=True)}</td>"
                f"<td>{html.escape(targets, quote=True)}</td>"
                f"<td>{html.escape(type_es, quote=True)}</td>"
                f"<td>{html.escape(label, quote=True)}</td></tr>"
            )
        parts.append("</tbody></table>")
    else:
        parts.append("<p>No hay relaciones contextuales.</p>")
    parts.append("</section>")
    return "".join(parts)


def _disconnected_section(layout: _Layout) -> str:
    parts = [
        '<section class="contextual"><h2>Componentes fuera de la vía principal '
        '<span class="sub">(sin conexión inventada)</span></h2><ul>'
    ]
    for node_id, label_es, state in layout.disconnected:
        badge = "Pendiente de revisión" if state == "BLOCKED" else "Propuesto"
        parts.append(
            f"<li><code>{html.escape(node_id, quote=True)}</code> — "
            f"{html.escape(label_es, quote=True)} "
            f'<span class="badge {state.lower()}">{html.escape(badge, quote=True)}</span></li>'
        )
    if not layout.disconnected:
        parts.append("<li>Ninguno.</li>")
    parts.append("</ul></section>")
    return "".join(parts)


def _issues_section(layout: _Layout) -> str:
    parts = [
        '<section class="contextual"><h2>Issues — puntos que requieren revisión clínica</h2><ul>'
    ]
    for issue_id, category_es, description, related in layout.issues:
        parts.append(
            f"<li><strong>{html.escape(issue_id, quote=True)}</strong> "
            f"[{html.escape(category_es, quote=True)}] "
            f"{html.escape(description, quote=True)} "
            f"<em>relacionado con: {html.escape(related, quote=True)}</em></li>"
        )
    if not layout.issues:
        parts.append("<li>Ninguno.</li>")
    parts.append("</ul></section>")
    return "".join(parts)


def _inventory_section(
    graph: CandidateGraph, manifest: VisualizationManifest, layout: _Layout
) -> str:
    """Full candidate inventory: every rule and relation stays reviewable."""
    drawn_ids = {node.node_id for node in layout.nodes}
    parts = [
        '<section class="contextual"><h2>Inventario completo de candidatos '
        '<span class="sub">(ningún candidato queda fuera de la revisión)</span></h2>',
        "<table><thead><tr><th>Regla</th><th>Descripción</th><th>Estado</th>"
        "<th>Ubicación</th><th>Issues</th></tr></thead><tbody>",
    ]
    for rule in sorted(graph.rules, key=lambda item: item.candidate_id):
        state_es = (
            "Pendiente de revisión" if rule.candidate_state.value == "BLOCKED" else "Propuesto"
        )
        location = (
            "Árbol principal"
            if rule.candidate_id in drawn_ids
            else "Componentes fuera de la vía principal"
        )
        issues = ", ".join(_rule_issue_ids(graph, rule.candidate_id)) or "—"
        parts.append(
            f"<tr><td><code>{html.escape(rule.candidate_id, quote=True)}</code></td>"
            f"<td>{html.escape(manifest.node_labels.get(rule.candidate_id, _fallback_label(rule)), quote=True)}</td>"
            f'<td><span class="badge {rule.candidate_state.value.lower()}">{html.escape(state_es, quote=True)}</span></td>'
            f"<td>{html.escape(location, quote=True)}</td>"
            f"<td>{html.escape(issues, quote=True)}</td></tr>"
        )
    parts.append("</tbody></table>")
    parts.append(
        "<table><thead><tr><th>Relación</th><th>Origen → destino</th><th>Tipo</th>"
        "<th>Estado</th><th>Ubicación</th></tr></thead><tbody>"
    )
    sequential_ids = {
        relation.candidate_relation_id
        for relation in graph.relations
        if relation.relation_type in (RelationType.FLOW, RelationType.BRANCH)
    }
    for relation in sorted(graph.relations, key=lambda item: item.candidate_relation_id):
        if relation.candidate_state is CandidateState.BLOCKED:
            state_es = "Pendiente de revisión"
        else:
            state_es = "Propuesta"
        if relation.candidate_relation_id in sequential_ids:
            location = "Flecha del árbol principal"
            type_es = "Secuencia" if relation.relation_type is RelationType.FLOW else "Rama"
        else:
            location = "Relaciones contextuales"
            type_es = _relation_type_es(relation.relation_type.value)
        label = manifest.branch_labels.get(
            relation.candidate_relation_id, relation.branch_label or "—"
        )
        parts.append(
            f"<tr><td><code>{html.escape(relation.candidate_relation_id, quote=True)}</code></td>"
            f"<td>{html.escape(f'{relation.source_ref} → ' + ', '.join(relation.target_refs), quote=True)}</td>"
            f"<td>{html.escape(type_es, quote=True)}"
            f"{' · ' + html.escape(label, quote=True) if label else ''}</td>"
            f'<td><span class="badge {relation.candidate_state.value.lower()}">{html.escape(state_es, quote=True)}</span></td>'
            f"<td>{html.escape(location, quote=True)}</td></tr>"
        )
    parts.append("</tbody></table></section>")
    return "".join(parts)


def _questions_section(manifest: VisualizationManifest) -> str:
    if not manifest.question_map:
        return ""
    parts = [
        '<section class="contextual"><h2>Preguntas para el revisor clínico</h2><p>'
        "Las preguntas completas están en el paquete de revisión (fase 7): "
        "<code>review_questions.md</code>. Las siguientes preguntas están "
        "asociadas a elementos concretos del árbol:</p><ul>"
    ]
    for question in manifest.question_map:
        parts.append(
            f"<li>{html.escape(question.label, quote=True)} "
            f'<span class="sub">({html.escape(", ".join(question.related), quote=True)})</span></li>'
        )
    parts.append("</ul></section>")
    return "".join(parts)


def render_print_view_html(graph: CandidateGraph, manifest: VisualizationManifest) -> str:
    """Render a print-friendly static view (browser → Print → PDF)."""
    layout = _build_candidate_layout(graph, manifest)
    svg = render_clinical_tree_svg(graph, manifest)
    parts = [
        "<!DOCTYPE html>",
        '<html lang="es"><head><meta charset="utf-8">',
        f"<title>Árbol candidato (impresión) — {graph.protocol_version_id}</title>",
        _PRINT_CSS,
        "</head><body>",
        '<header class="banner">',
        f"<h1>{CANDIDATE_BANNER}</h1>",
        f"<p>{CANDIDATE_DISCLAIMER}</p>",
        "</header>",
        '<section class="map">',
        "<h2>Árbol clínico candidato</h2>",
        '<div class="svg-wrap">' + svg + "</div>",
        "</section>",
        _contextual_section(layout),
        _disconnected_section(layout),
        _issues_section(layout),
        _questions_section(manifest),
        "</body></html>",
    ]
    return "\n".join(parts) + "\n"


def render_approved_clinical_tree_svg(
    package: ApprovedKnowledgePackage, manifest: VisualizationManifest
) -> str:
    """Render an approved package with the same layout core (future Phase 8B).

    Used with synthetic fixtures only in this phase; no real approved
    knowledge exists.
    """
    nodes: list[_NodeV] = []
    adjacency: dict[str, list[str]] = {rule_id: [] for rule_id in package.rules}
    positions: dict[str, tuple[int, int]] = {}
    # Deterministic layering from manifest stage roots.
    levels: dict[str, int] = {}
    order: list[str] = []
    for stage in manifest.stages:
        if stage.rule_id in package.rules and stage.rule_id not in levels:
            levels[stage.rule_id] = 0
            order.append(stage.rule_id)
    for relation in package.relations.values():
        if relation.source_ref in package.rules:
            adjacency[relation.source_ref].extend(relation.target_refs)
    cursor = 0
    while cursor < len(order):
        current = order[cursor]
        cursor += 1
        for target in adjacency.get(current, ()):
            candidate = levels[current] + 1
            if target not in levels:
                levels[target] = candidate
                order.append(target)
            elif candidate < levels[target]:
                levels[target] = candidate
    columns: dict[int, list[str]] = {}
    for rule_id in order:
        columns.setdefault(levels[rule_id], []).append(rule_id)
    for entries in columns.values():
        entries.sort()
    for level, entries in columns.items():
        for index, rule_id in enumerate(entries):
            positions[rule_id] = (level, index)
    for rule_id, (level, index) in sorted(positions.items(), key=lambda item: item[1]):
        rule = package.rules[rule_id]
        action = rule.actions[0] if rule.actions else None
        label_es = manifest.node_labels.get(
            rule_id,
            action.target_text if action is not None and action.target_text else rule_id,
        )
        kind_es = _ACTION_KIND.get(action.action_type, "Acción") if action else "Decisión"
        nodes.append(
            _NodeV(
                node_id=rule_id,
                content_hash=rule.approved_content_hash or "",
                kind_es=kind_es,
                label_es=label_es,
                condition_text=_render_condition_text(rule.condition),
                state="APPROVED",
                issue_ids=(),
                pages=(),
                quotes=(),
                visual_evidence=False,
                level=level,
                index=index,
                is_root=rule_id in {stage.rule_id for stage in manifest.stages},
                stage_label=next(
                    (stage.label for stage in manifest.stages if stage.rule_id == rule_id), None
                ),
            )
        )
    edges: list[_EdgeV] = []
    for relation in package.relations.values():
        if relation.source_ref not in positions or any(
            target not in positions for target in relation.target_refs
        ):
            continue
        for target in relation.target_refs:
            edges.append(
                _EdgeV(
                    edge_id=relation.approved_relation_id,
                    content_hash=relation.approved_content_hash or "",
                    source=relation.source_ref,
                    target=target,
                    label_es=manifest.branch_labels.get(
                        relation.approved_relation_id, relation.branch_label or "—"
                    ),
                    kind_es="Secuencia" if relation.relation_type is RelationType.FLOW else "Rama",
                    blocked=False,
                    cycle=False,
                )
            )
    return _render_svg_from_parts(nodes, edges, positions)


def _render_condition_text(expression: object) -> str:
    try:
        return str(render_operand(expression))  # type: ignore[arg-type]
    except ValueError:
        return "(condición no representable)"


def _render_svg_from_parts(
    nodes: list[_NodeV], edges: list[_EdgeV], positions: dict[str, tuple[int, int]]
) -> str:
    max_level = max((node.level for node in nodes), default=0)
    max_rows = max((node.index for node in nodes), default=0)
    width = _MARGIN * 2 + (max_level + 1) * (_NODE_W + _H_GAP) - _H_GAP
    height = _MARGIN * 2 + (max_rows + 1) * (_NODE_H + _V_GAP) - _V_GAP
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'width="{width:.0f}" height="{height:.0f}">',
        "<style>",
        ".node { fill: #ffffff; stroke: #0f4c81; stroke-width: 1.6; }",
        ".node-titulo { font: 600 12.5px sans-serif; fill: #1f2937; }",
        ".node-condicion { font: 10px ui-monospace, Menlo, monospace; fill: #6b7280; }",
        ".node-tipo { font: 700 10px sans-serif; fill: #0f4c81; }",
        ".edge { fill: none; stroke: #0f4c81; stroke-width: 1.5; }",
        ".edge-etiqueta { font: 10px sans-serif; fill: #374151; }",
        "</style>",
        '<defs><marker id="arrow-accent" markerWidth="8" markerHeight="8" refX="7" refY="4" '
        'orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#0f4c81"/></marker></defs>',
    ]
    for node in nodes:
        x, y = positions[node.node_id]
        parts.append(f'<g id="n-{html.escape(node.node_id, quote=True)}">')
        parts.append(
            f'<rect class="node" x="{x:.0f}" y="{y:.0f}" width="{_NODE_W:.0f}" '
            f'height="{_NODE_H:.0f}" rx="7"/>'
        )
        text_y = y + 18.0
        parts.append(
            f'<text class="node-tipo" x="{x + 10:.0f}" y="{text_y:.0f}">'
            f"{html.escape(node.kind_es, quote=True)} · APROBADO</text>"
        )
        text_y += 15.0
        for line in _truncate(node.label_es, 34, 3):
            parts.append(
                f'<text class="node-titulo" x="{x + 10:.0f}" y="{text_y:.0f}">{html.escape(line, quote=True)}</text>'
            )
            text_y += 14.0
        for line in _truncate(node.condition_text, 32, 2):
            parts.append(
                f'<text class="node-condicion" x="{x + 10:.0f}" y="{text_y:.0f}">{html.escape(line, quote=True)}</text>'
            )
            text_y += 12.0
        parts.append("</g>")
    for edge in edges:
        sx, sy = positions[edge.source]
        tx, ty = positions[edge.target]
        start = (sx + _NODE_W, sy + _NODE_H / 2)
        end = (tx, ty + _NODE_H / 2)
        control = (start[0] + (end[0] - start[0]) / 2, start[1])
        parts.append(
            f'<path id="e-{html.escape(edge.edge_id, quote=True)}" class="edge" '
            f'd="M {start[0]:.0f} {start[1]:.0f} C {control[0]:.0f} {start[1]:.0f} '
            f'{control[0]:.0f} {end[1]:.0f} {end[0]:.0f} {end[1]:.0f}" marker-end="url(#arrow-accent)"/>'
        )
        parts.append(
            f'<text class="edge-etiqueta" x="{control[0]:.0f}" y="{(start[1] + end[1]) / 2 - 6:.0f}" '
            f'text-anchor="middle">{html.escape(edge.label_es, quote=True)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


_HTML_CSS = """
<style>
:root { --ink: #1f2937; --muted: #6b7280; --line: #d1d5db; --bg: #f6f7f9;
        --card: #ffffff; --accent: #0f4c81; --alert: #b3261e; --stage: #7a4a9e; }
* { box-sizing: border-box; }
body { margin: 0; color: var(--ink); background: var(--bg);
       font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
       line-height: 1.45; }
header.banner { background: var(--alert); color: #fff; padding: 1.2rem 1.8rem; }
header.banner h1 { margin: 0 0 .25rem 0; font-size: 1.3rem; }
header.banner p { margin: .15rem 0; }
header.banner .meta { font-size: .85rem; opacity: .95; }
main { max-width: 1400px; margin: 0 auto; padding: 1rem 1.4rem 2rem 1.4rem; }
section.controls, section.legend, section.map, aside.details, section.contextual,
footer.disclaimer { background: var(--card); border: 1px solid var(--line);
  border-radius: 6px; padding: .8rem 1rem; margin: 0 0 .9rem 0; }
section.controls { display: flex; gap: 1.4rem; align-items: center; flex-wrap: wrap; }
.modes button { border: 1px solid var(--line); background: var(--card); color: var(--ink);
  padding: .35rem .9rem; border-radius: 6px; cursor: pointer; font-size: .9rem; }
.modes button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.filters label { margin-right: 1rem; font-size: .85rem; }
.layout { display: grid; grid-template-columns: minmax(0, 1fr) 330px; gap: .9rem; }
aside.details { min-height: 260px; }
aside.details h2 { margin-top: 0; font-size: 1rem; }
aside.details .kv { font-size: .84rem; margin: .3rem 0; }
aside.details .kv strong { display: inline-block; min-width: 90px; color: var(--muted); }
aside.details ul { margin: .2rem 0 0 0; padding-left: 1.1rem; font-size: .82rem; }
aside.details .state-pill { font-weight: 700; }
aside.details .state-pill.BLOCKED, aside.details .state-pill.BLOQUEADA { color: var(--alert); }
aside.details .state-pill.PROPOSED, aside.details .state-pill.PROPUESTA { color: var(--accent); }
aside.details .alert-note { color: var(--alert); font-weight: 700; font-size: .82rem; }
.map-toolbar { margin-bottom: .3rem; }
.map-toolbar button { border: 1px solid var(--line); background: var(--card);
  padding: .15rem .6rem; border-radius: 4px; cursor: pointer; }
.svg-wrap { overflow: auto; max-width: 100%; border: 1px solid var(--line); border-radius: 4px; }
.svg-wrap svg { display: block; width: var(--zoom, 100%); min-width: 700px; height: auto; }
body.mode-pathway .node.hide-context { opacity: .35; }
body.mode-review .node { opacity: 1; }
.node.muted { opacity: .25; }
.node.focus { stroke-width: 3.5; }
h2 .sub { font-size: .78rem; color: var(--muted); font-weight: normal; }
section.contextual { font-size: .85rem; }
section.contextual table { border-collapse: collapse; width: 100%; font-size: .8rem; }
section.contextual th, section.contextual td { border: 1px solid var(--line);
  padding: .25rem .45rem; text-align: left; vertical-align: top; }
section.contextual th { background: #eef3f8; }
.badge { display: inline-block; border-radius: 10px; padding: .02rem .5rem;
  font-size: .7rem; font-weight: 600; border: 1px solid var(--line); }
.badge.blocked { color: var(--alert); border-color: var(--alert); }
.badge.proposed { color: var(--accent); border-color: var(--accent); }
li.li-propuesto, li.li-bloqueado, li.li-secuencia, li.li-rama, li.li-bloqueada,
li.li-etapa { list-style: none; padding-left: 1.4rem; position: relative; }
li.li-propuesto::before { content: "■"; color: var(--accent); position: absolute; left: 0; }
li.li-bloqueado::before, li.li-bloqueada::before { content: "⚠"; color: var(--alert); position: absolute; left: 0; }
li.li-secuencia::before { content: "→"; color: var(--accent); position: absolute; left: 0; }
li.li-rama::before { content: "⇢"; color: var(--muted); position: absolute; left: 0; }
li.li-etapa::before { content: "◈"; color: var(--stage); position: absolute; left: 0; }
footer.disclaimer { font-size: .82rem; color: var(--muted); border-color: var(--alert); }
</style>
"""

_HTML_JS = """
<script>
(function () {
  "use strict";
  var data = null;
  function loadData() {
    var node = document.getElementById("details-data");
    if (node) { data = JSON.parse(node.textContent); }
  }
  function showDetails(item) {
    if (!data) { loadData(); }
    var info = data[item.kind][item.id];
    var empty = document.getElementById("details-empty");
    var content = document.getElementById("details-content");
    if (!info) { if (empty) { empty.hidden = false; } if (content) { content.hidden = true; } return; }
    if (empty) { empty.hidden = true; }
    if (!content) { return; }
    var htmlParts = [];
    htmlParts.push('<p class="kv"><strong>Elemento</strong> ' + info.elemento + "</p>");
    htmlParts.push('<p class="kv"><strong>Tipo</strong> ' + info.tipo + " — " + info.clase + "</p>");
    htmlParts.push('<p class="kv"><strong>Estado</strong> <span class="state-pill ' +
      info.estado + '">' + info.estado + "</span></p>");
    htmlParts.push('<p class="kv"><strong>Condición</strong> <code>' + info.condicion + "</code></p>");
    htmlParts.push('<p class="kv"><strong>Acción</strong> ' + info.accion + "</p>");
    htmlParts.push('<p class="kv"><strong>Página</strong> ' + info.pagina + "</p>");
    htmlParts.push('<p class="kv"><strong>ID</strong> <code>' + info.elemento + "</code></p>");
    htmlParts.push('<p class="kv"><strong>Hash</strong> <code>' + info.hash.slice(0, 16) + "…</code></p>");
    if (info.estado === "BLOCKED" || info.estado === "BLOQUEADA") {
      htmlParts.push('<p class="alert-note">⚠ Pendiente de revisión: evidencia sin resolver. No significa rechazado.</p>');
    }
    if (info.evidencia && info.evidencia.length) {
      htmlParts.push("<p class=\"kv\"><strong>Evidencia</strong></p><ul>");
      info.evidencia.forEach(function (quote) {
        htmlParts.push("<li>" + quote.replace(/&/g, "&amp;").replace(/</g, "&lt;") + "</li>");
      });
      htmlParts.push("</ul>");
    }
    if (info.evidencia_visual) {
      htmlParts.push('<p class="alert-note">Evidencia visual — requiere revisión manual.</p>');
    }
    if (info.issues && info.issues.length) {
      htmlParts.push("<p class=\"kv\"><strong>Issues</strong> " + info.issues.join(", ") + "</p>");
    }
    if (info.preguntas && info.preguntas.length) {
      htmlParts.push("<p class=\"kv\"><strong>Preguntas del revisor</strong></p><ul>");
      info.preguntas.forEach(function (question) {
        htmlParts.push("<li>" + question.replace(/&/g, "&amp;").replace(/</g, "&lt;") + "</li>");
      });
      htmlParts.push("</ul>");
    }
    content.innerHTML = htmlParts.join("");
    content.hidden = false;
  }
  document.addEventListener("click", function (event) {
    var target = event.target.closest ? event.target.closest("g[id^='n-'], path[id^='e-']") : null;
    document.querySelectorAll(".node.focus, path.focus").forEach(function (el) {
      el.classList.remove("focus");
    });
    if (!target) { return; }
    if (target.id.indexOf("n-") === 0) {
      var rect = target.querySelector("rect");
      if (rect) { rect.classList.add("focus"); }
      showDetails({ kind: "nodes", id: target.id.slice(2) });
    } else if (target.id.indexOf("e-") === 0) {
      target.classList.add("focus");
      showDetails({ kind: "edges", id: target.id.slice(2) });
    }
  });
  document.querySelectorAll(".modes button").forEach(function (button) {
    button.addEventListener("click", function () {
      document.querySelectorAll(".modes button").forEach(function (item) {
        item.classList.remove("active");
        item.setAttribute("aria-pressed", "false");
      });
      button.classList.add("active");
      button.setAttribute("aria-pressed", "true");
      document.body.className = "mode-" + button.getAttribute("data-mode");
    });
  });
  var zoom = 100;
  var wrap = document.getElementById("svg-wrap");
  function applyZoom() { if (wrap) { wrap.style.setProperty("--zoom", zoom + "%"); } }
  var zoomIn = document.getElementById("zoom-in");
  var zoomOut = document.getElementById("zoom-out");
  if (zoomIn) { zoomIn.addEventListener("click", function () { zoom = Math.min(zoom + 15, 200); applyZoom(); }); }
  if (zoomOut) { zoomOut.addEventListener("click", function () { zoom = Math.max(zoom - 15, 50); applyZoom(); }); }
})();
</script>
"""

_PRINT_CSS = """
<style>
* { box-sizing: border-box; }
body { margin: 0; color: #1f2937;
  font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif; line-height: 1.4; }
header.banner { background: #b3261e; color: #fff; padding: .9rem 1.2rem; }
header.banner h1 { margin: 0 0 .2rem 0; font-size: 1.2rem; }
section.map, section.contextual { margin: .6rem 1rem; padding: .5rem .8rem;
  border: 1px solid #d1d5db; border-radius: 6px; }
section.map h2, section.contextual h2 { font-size: 1rem; margin: .4rem 0; }
.svg-wrap svg { width: 100%; height: auto; }
section.contextual table { border-collapse: collapse; width: 100%; font-size: .8rem; }
section.contextual th, section.contextual td { border: 1px solid #d1d5db;
  padding: .2rem .4rem; text-align: left; }
section.contextual { break-inside: avoid; }
@page { size: landscape; margin: 10mm; }
@media print {
  body { background: #ffffff; }
  section.map, section.contextual { border: none; margin: 0; }
  .svg-wrap { page-break-inside: avoid; }
}
</style>
"""
