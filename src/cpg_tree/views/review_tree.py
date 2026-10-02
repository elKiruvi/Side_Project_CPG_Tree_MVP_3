"""Preliminary review-tree projection for Candidate Graphs (Phase 5).

This module is a pure presentation layer for candidate artifacts. It projects a
canonical ``CandidateGraph`` into a review-oriented static diagram WITHOUT
changing graph semantics:

- Only canonical ``FLOW`` and ``BRANCH`` relations are drawn as pathway arrows.
- Contextual relations (``SUPPORTS``, ``REFERENCE``, ``BRANCH_CONTEXT``,
  ``EXCEPTION_CONTEXT``, ``COMPOSITION``, ``DECLARES_ACTION``) are listed in a
  separate section and are never rendered as sequence.
- No edge is invented; unreachable rules and disconnected components stay
  visible as review items.
- Candidate states (``PROPOSED`` / ``BLOCKED``), unresolved Issues, evidence
  (page and span ids), and uncertainty markers are visibly distinguished.

The projection reads an optional sidecar manifest that declares stage roots and
display notes. The manifest is presentation metadata only: it contains no
conditions, thresholds, actions, or clinical content.

Output is deterministic: identical graph + manifest + code produce byte-
identical HTML and SVG (no timestamps, no randomness, stable ordering).
"""

# ruff: noqa: TRY004
# Complexity suppressions: the projection builder and renderers are long but
# linear, deterministic presentation code; splitting them into micro-functions
# would scatter the layout constants without improving reviewability.
# ruff: noqa: C901, PLR0912, PLR0915

from __future__ import annotations

import html
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from cpg_tree.candidates.enums import CandidateState, RelationType
from cpg_tree.candidates.graph import CandidateGraph
from cpg_tree.candidates.relations import CandidateRelation
from cpg_tree.candidates.rules import CandidateRule
from cpg_tree.views.expression import render_operand

PROJECTION_SCHEMA = "projection-v1"

_SEQUENTIAL_TYPES = (RelationType.FLOW, RelationType.BRANCH)

_NODE_W = 268.0
_NODE_H = 176.0
_H_GAP = 96.0
_V_GAP = 26.0
_MARGIN = 46.0

_ACTION_WRAP = 42
_ACTION_LINES = 4
_CONDITION_WRAP = 38
_CONDITION_LINES = 2


@dataclass(frozen=True, slots=True)
class StageRoot:
    """One projection root: a rule id with a display stage label."""

    rule_id: str
    label: str


@dataclass(frozen=True, slots=True)
class ProjectionManifest:
    """Presentation-only projection configuration for one protocol."""

    protocol_version_id: str
    stages: tuple[StageRoot, ...]
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.stages:
            raise ValueError("ProjectionManifest requires at least one stage root")
        seen: set[str] = set()
        for stage in self.stages:
            if stage.rule_id in seen:
                raise ValueError(f"duplicate projection root {stage.rule_id!r}")
            seen.add(stage.rule_id)
            if not stage.label:
                raise ValueError("ProjectionManifest stage labels must not be empty")


def load_projection_manifest(path: Path) -> ProjectionManifest:
    """Load a projection manifest from YAML with strict validation."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError(f"{path.name} root must be a mapping")
    if raw.get("schema") != PROJECTION_SCHEMA:
        raise ValueError(f"{path.name} requires schema {PROJECTION_SCHEMA!r}")
    protocol_version_id = raw.get("protocol_version_id")
    if not isinstance(protocol_version_id, str) or not protocol_version_id:
        raise ValueError(f"{path.name} requires a protocol_version_id")
    stages_raw = raw.get("stages")
    if not isinstance(stages_raw, list) or not stages_raw:
        raise ValueError(f"{path.name} requires a non-empty 'stages' list")
    stages: list[StageRoot] = []
    for entry in stages_raw:
        if not isinstance(entry, Mapping):
            raise ValueError(f"{path.name} stage entries must be mappings")
        label = entry.get("label")
        roots = entry.get("roots")
        if not isinstance(label, str) or not label:
            raise ValueError(f"{path.name} stage labels must be non-empty strings")
        if not isinstance(roots, list):
            raise ValueError(f"{path.name} stage 'roots' must be a list")
        for root in roots:
            if not isinstance(root, str) or not root:
                raise ValueError(f"{path.name} stage roots must be non-empty strings")
            stages.append(StageRoot(rule_id=root, label=label))
    notes_raw = raw.get("notes", ())
    if not isinstance(notes_raw, list) or not all(isinstance(item, str) for item in notes_raw):
        raise ValueError(f"{path.name} 'notes' must be a list of strings")
    return ProjectionManifest(
        protocol_version_id=protocol_version_id,
        stages=tuple(stages),
        notes=tuple(notes_raw),
    )


@dataclass(frozen=True, slots=True)
class _NodeView:
    rule: CandidateRule
    level: int
    index: int
    is_root: bool
    stage_label: str | None
    issue_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _EdgeView:
    relation: CandidateRelation
    target_ref: str
    backward: bool


@dataclass(frozen=True, slots=True)
class _Projection:
    manifest: ProjectionManifest
    nodes: tuple[_NodeView, ...]
    edges: tuple[_EdgeView, ...]
    orphan_edges: tuple[CandidateRelation, ...]
    disconnected: tuple[CandidateRule, ...]
    contextual: tuple[CandidateRelation, ...]


def _build_projection(graph: CandidateGraph, manifest: ProjectionManifest) -> _Projection:
    if manifest.protocol_version_id != graph.protocol_version_id:
        raise ValueError(
            f"manifest protocol {manifest.protocol_version_id!r} does not match "
            f"graph protocol {graph.protocol_version_id!r}"
        )
    rules = {rule.candidate_id: rule for rule in graph.rules}
    unknown_roots = [stage.rule_id for stage in manifest.stages if stage.rule_id not in rules]
    if unknown_roots:
        raise ValueError(f"projection roots reference unknown rules: {sorted(unknown_roots)}")
    sequential = [
        relation for relation in graph.relations if relation.relation_type in _SEQUENTIAL_TYPES
    ]
    sequential.sort(key=lambda relation: relation.candidate_relation_id)
    contextual = sorted(
        (
            relation
            for relation in graph.relations
            if relation.relation_type not in _SEQUENTIAL_TYPES
        ),
        key=lambda relation: relation.candidate_relation_id,
    )
    adjacency: dict[str, list[tuple[CandidateRelation, str]]] = {rule_id: [] for rule_id in rules}
    for relation in sequential:
        adjacency.setdefault(relation.source_ref, []).extend(
            (relation, target) for target in relation.target_refs
        )
    for targets in adjacency.values():
        targets.sort(key=lambda item: (item[1], item[0].candidate_relation_id))

    levels: dict[str, int] = {}
    node_order: list[tuple[str, str | None]] = []
    roots = tuple((stage.rule_id, stage.label) for stage in manifest.stages)
    cursor = 0
    for rule_id, stage_label in roots:
        if rule_id not in levels:
            levels[rule_id] = 0
            node_order.append((rule_id, stage_label))
    while cursor < len(node_order):
        rule_id, _ = node_order[cursor]
        cursor += 1
        for _, target in adjacency.get(rule_id, ()):
            candidate = levels[rule_id] + 1
            if target not in levels:
                levels[target] = candidate
                node_order.append((target, None))
            elif candidate < levels[target]:
                levels[target] = candidate
    for _ in range(max(levels.values(), default=0) + 1):
        changed = False
        for rule_id, _ in node_order:
            for _, target in adjacency.get(rule_id, ()):
                if levels[target] > levels[rule_id] + 1:
                    levels[target] = levels[rule_id] + 1
                    changed = True
        if not changed:
            break

    stage_by_root = dict(roots)
    column: dict[int, list[str]] = {}
    for rule_id, _ in node_order:
        column.setdefault(levels[rule_id], []).append(rule_id)
    for entries in column.values():
        entries.sort()
    nodes: list[_NodeView] = []
    positions: dict[str, tuple[int, int]] = {}
    for level in sorted(column):
        for index, rule_id in enumerate(column[level]):
            positions[rule_id] = (level, index)
            nodes.append(
                _NodeView(
                    rule=rules[rule_id],
                    level=level,
                    index=index,
                    is_root=rule_id in stage_by_root,
                    stage_label=stage_by_root.get(rule_id),
                    issue_ids=_rule_issue_ids(graph, rule_id),
                )
            )
    nodes.sort(key=lambda node: (node.level, node.index))

    edges: list[_EdgeView] = []
    orphan_edges: list[CandidateRelation] = []
    seen_edges: set[tuple[str, str]] = set()
    sequential_adjacency: dict[str, set[str]] = {rule_id: set() for rule_id in rules}
    for relation in sequential:
        sequential_adjacency.setdefault(relation.source_ref, set()).update(relation.target_refs)
    for relation in sequential:
        for target in relation.target_refs:
            pair = (relation.candidate_relation_id, target)
            if pair in seen_edges:
                continue
            seen_edges.add(pair)
            if relation.source_ref not in positions or target not in positions:
                orphan_edges.append(relation)
                continue
            backward = _can_reach(sequential_adjacency, target, relation.source_ref)
            edges.append(_EdgeView(relation=relation, target_ref=target, backward=backward))
    edges.sort(key=lambda edge: edge.relation.candidate_relation_id)
    orphan_edges.sort(key=lambda relation: relation.candidate_relation_id)

    disconnected = tuple(
        sorted(
            (rule for rule in graph.rules if rule.candidate_id not in positions),
            key=lambda rule: rule.candidate_id,
        )
    )
    return _Projection(
        manifest=manifest,
        nodes=tuple(nodes),
        edges=tuple(edges),
        orphan_edges=tuple(orphan_edges),
        disconnected=disconnected,
        contextual=tuple(contextual),
    )


def _can_reach(adjacency: dict[str, set[str]], start: str, goal: str) -> bool:
    seen: set[str] = set()
    frontier = [start]
    while frontier:
        current = frontier.pop()
        if current == goal:
            return True
        if current in seen:
            continue
        seen.add(current)
        frontier.extend(sorted(adjacency.get(current, ())))
    return False


def _rule_issue_ids(graph: CandidateGraph, rule_id: str) -> tuple[str, ...]:
    return tuple(sorted(issue.issue_id for issue in graph.issues if rule_id in issue.related_ids))


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


def _truncate_lines(text: str, width: int, max_lines: int) -> list[str]:
    lines = _wrap(text, width)
    if len(lines) <= max_lines:
        return lines
    kept = lines[:max_lines]
    kept[-1] = f"{kept[-1][: width - 1]}…"
    return kept


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _node_short_label(rule: CandidateRule) -> str:
    target = rule.actions[0].target_text if rule.actions else "(no action)"
    assert target is not None
    return target


def _svg_esc(value: str) -> str:
    return _esc(value)


def _rule_evidence_lines(graph: CandidateGraph, rule: CandidateRule) -> list[str]:
    spans: set[str] = set()
    pages: set[int] = set()
    for binding in rule.evidence_bindings:
        spans.update(binding.source_span_refs)
    for action in rule.actions:
        for binding in action.evidence_bindings:
            spans.update(binding.source_span_refs)
    for span_id in sorted(spans):
        span = next((item for item in graph.source_spans if item.span_id == span_id), None)
        if span is not None:
            pages.add(span.page)
    page_text = f"p.{','.join(str(page) for page in sorted(pages))}" if pages else "no page"
    span_text = f"{len(spans)} span(s)" if spans else "no span evidence"
    return [page_text, span_text]


def _render_svg_map(graph: CandidateGraph, manifest: ProjectionManifest) -> str:
    projection = _build_projection(graph, manifest)
    width = max((projection.nodes), key=lambda n: n.level).level if projection.nodes else 0
    max_rows = max((node.index for node in projection.nodes), default=0)
    total_w = _MARGIN * 2 + (width + 1) * (_NODE_W + _H_GAP) - _H_GAP
    total_h = _MARGIN * 2 + (max_rows + 1) * (_NODE_H + _V_GAP) - _V_GAP
    positions = {
        node.rule.candidate_id: (
            _MARGIN + node.level * (_NODE_W + _H_GAP),
            _MARGIN + node.index * (_NODE_H + _V_GAP),
        )
        for node in projection.nodes
    }
    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w:.0f} {total_h:.0f}" '
        f'width="{total_w:.0f}" height="{total_h:.0f}" role="img" '
        f'aria-label="Candidate pathway projection">'
    )
    parts.append(
        "<style>"
        ".pnode { fill: #ffffff; stroke-width: 1.6; }"
        ".pnode.proposed { stroke: #0f4c81; }"
        ".pnode.blocked { stroke: #b3261e; }"
        ".pnode.root { stroke-width: 2.6; }"
        ".pnode-head { font: 600 12px ui-monospace, Menlo, monospace; }"
        ".pnode-action { font: 12px sans-serif; }"
        ".pnode-condition { font: 10px ui-monospace, Menlo, monospace; fill: #6b7280; }"
        ".pnode-meta { font: 10px sans-serif; fill: #6b7280; }"
        ".pnode-badge { font: 600 10px sans-serif; }"
        ".pnode-badge.proposed { fill: #0f4c81; }"
        ".pnode-badge.blocked { fill: #b3261e; }"
        ".pnode-stage { font: 600 10px sans-serif; fill: #7a4a9e; }"
        ".pedge { fill: none; stroke-width: 1.5; }"
        ".pedge.flow { stroke: #0f4c81; }"
        ".pedge.branch { stroke: #374151; }"
        ".pedge.blocked { stroke: #b3261e; stroke-dasharray: 7 5; }"
        ".pedge.cycle { stroke-dasharray: 3 4; }"
        ".pedge-label { font: 10px sans-serif; fill: #374151; }"
        ".pedge-label.blocked { fill: #b3261e; }"
        "</style>"
    )
    parts.append("<defs>")
    parts.append(
        '<marker id="arrow-accent" markerWidth="8" markerHeight="8" refX="7" refY="4" '
        'orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#0f4c81"/></marker>'
    )
    parts.append(
        '<marker id="arrow-ink" markerWidth="8" markerHeight="8" refX="7" refY="4" '
        'orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#374151"/></marker>'
    )
    parts.append(
        '<marker id="arrow-blocked" markerWidth="8" markerHeight="8" refX="7" refY="4" '
        'orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#b3261e"/></marker>'
    )
    parts.append("</defs>")
    for node in projection.nodes:
        x, y = positions[node.rule.candidate_id]
        rule = node.rule
        state_cls = "blocked" if rule.candidate_state is CandidateState.BLOCKED else "proposed"
        root_cls = " root" if node.is_root else ""
        parts.append(f'<g id="n-{_svg_esc(rule.candidate_id)}">')
        parts.append(
            f'<rect class="pnode {state_cls}{root_cls}" x="{x:.0f}" y="{y:.0f}" '
            f'width="{_NODE_W:.0f}" height="{_NODE_H:.0f}" rx="7"/>'
        )
        lines: list[tuple[str, str]] = []
        lines.append((f"pnode-head {state_cls}", rule.candidate_id))
        action_lines = _truncate_lines(_node_short_label(rule), _ACTION_WRAP, _ACTION_LINES)
        for line in action_lines:
            lines.append(("pnode-action", line))
        try:
            condition_text = render_operand(rule.condition)
        except ValueError:
            condition_text = "(condition not renderable)"
        for line in _truncate_lines(condition_text, _CONDITION_WRAP, _CONDITION_LINES):
            lines.append(("pnode-condition", line))
        evidence_lines = _rule_evidence_lines(graph, rule)
        meta_bits: list[str] = []
        if node.issue_ids:
            meta_bits.append(f"{len(node.issue_ids)} issue(s)")
        meta_bits.extend(evidence_lines)
        lines.append(("pnode-meta", " · ".join(meta_bits)))
        text_y = y + 18.0
        for cls, line in lines:
            parts.append(
                f'<text class="{cls}" x="{x + 10:.0f}" y="{text_y:.0f}">{_svg_esc(line)}</text>'
            )
            text_y += 16.0 if cls.startswith("pnode-head") else 14.0
        badge = rule.candidate_state.value
        parts.append(
            f'<text class="pnode-badge {state_cls}" x="{x + _NODE_W - 10:.0f}" y="{y + 14:.0f}" '
            f'text-anchor="end">{_svg_esc(badge)}</text>'
        )
        if node.is_root and node.stage_label:
            parts.append(
                f'<text class="pnode-stage" x="{x + 10:.0f}" y="{y + _NODE_H - 8:.0f}">'
                f"stage: {_svg_esc(node.stage_label)}</text>"
            )
        parts.append("</g>")
    for edge in projection.edges:
        source = edge.relation.source_ref
        target = edge.target_ref
        sx, sy = positions[source]
        tx, ty = positions[target]
        start = (sx + _NODE_W, sy + _NODE_H / 2)
        end = (tx, ty + _NODE_H / 2)
        blocked = edge.relation.candidate_state is CandidateState.BLOCKED
        flow = edge.relation.relation_type is RelationType.FLOW
        classes = ["pedge"]
        classes.append("flow" if flow else "branch")
        if blocked:
            classes.append("blocked")
        if edge.backward:
            classes.append("cycle")
        marker = "arrow-blocked" if blocked else ("arrow-accent" if flow else "arrow-ink")
        control_dx = (end[0] - start[0]) / 2
        control = (start[0] + control_dx, start[1])
        path = (
            f"M {start[0]:.0f} {start[1]:.0f} "
            f"C {control[0]:.0f} {start[1]:.0f} {control[0]:.0f} {end[1]:.0f} "
            f"{end[0]:.0f} {end[1]:.0f}"
        )
        label_bits = []
        if edge.relation.branch_label:
            label_bits.append(edge.relation.branch_label)
        if blocked:
            label_bits.append("BLOCKED")
        if edge.backward:
            label_bits.append("loop")
        parts.append(
            f'<path id="e-{_svg_esc(edge.relation.candidate_relation_id)}" class="{" ".join(classes)}" '
            f'd="{path}" marker-end="url(#{marker})"/>'
        )
        if label_bits:
            label_text = " · ".join(label_bits)
            lx = control[0]
            ly = (start[1] + end[1]) / 2 - 6
            parts.append(
                f'<text class="pedge-label{" blocked" if blocked else ""}" '
                f'x="{lx:.0f}" y="{ly:.0f}" text-anchor="middle">{_svg_esc(label_text)}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


def render_review_tree_svg(graph: CandidateGraph, manifest: ProjectionManifest) -> str:
    """Render the sequential pathway projection as a standalone SVG document."""
    return _render_svg_map(graph, manifest)


def render_review_tree_html(graph: CandidateGraph, manifest: ProjectionManifest) -> str:
    """Render the full deterministic review document (HTML) for one protocol."""
    projection = _build_projection(graph, manifest)
    parts: list[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="en"><head><meta charset="utf-8">')
    parts.append(f"<title>Candidate review tree — {_esc(graph.protocol_version_id)}</title>")
    parts.append(_HTML_CSS)
    parts.append("</head><body>")
    parts.append('<header class="review-header">')
    parts.append(f"<h1>Candidate review tree — {_esc(graph.protocol_version_id)}</h1>")
    proposed = sum(rule.candidate_state is CandidateState.PROPOSED for rule in graph.rules)
    blocked = sum(rule.candidate_state is CandidateState.BLOCKED for rule in graph.rules)
    parts.append(
        '<p class="meta">'
        f"{len(graph.rules)} candidate rules · {len(graph.relations)} candidate relations · "
        f"{len(graph.issues)} open issues · {proposed} PROPOSED · {blocked} BLOCKED · "
        f"document {_esc(graph.document_id)}"
        "</p>"
    )
    parts.append(
        '<p class="derived">PRELIMINARY REVIEW PROJECTION — NOT CLINICALLY APPROVED. '
        "The canonical CandidateGraph remains the source of truth; this page is a derived "
        "review view. Only canonical FLOW/BRANCH relations are drawn as pathway arrows.</p>"
    )
    parts.append("</header>")
    parts.append("<main>")
    parts.append('<section class="legend"><strong>Legend.</strong> ')
    parts.append(
        '<span class="chip proposed">PROPOSED</span> candidate pending review · '
        '<span class="chip blocked">BLOCKED</span> candidate blocked by unresolved evidence '
        "· solid arrows are canonical FLOW (dark blue) or BRANCH (dark) relations · "
        '<span class="chip edge-blocked">dashed red</span> blocked relation · '
        '<span class="chip cycle">dotted</span> reassessment/loop annotation · '
        '<span class="chip stage">stage</span> projection root declared in the manifest · '
        "<strong>ⓘ</strong> node carries open Issues (see Issues section).</section>"
    )
    if manifest.notes:
        parts.append('<section class="notes"><h3>Projection notes</h3><ul>')
        for note in manifest.notes:
            parts.append(f"<li>{_esc(note)}</li>")
        parts.append("</ul></section>")
    parts.append('<section class="map-wrap">')
    parts.append(
        '<h2 class="domain">Sequential pathway projection '
        '<span class="count">(canonical FLOW/BRANCH edges only; no invented edges)</span></h2>'
    )
    parts.append(_render_svg_map(graph, manifest))
    parts.append("</section>")
    parts.append(
        '<section class="contextual"><h2 class="domain">Contextual relations '
        '<span class="count">(not clinical sequence; never drawn as pathway arrows)</span></h2>'
    )
    if projection.contextual:
        parts.append(
            "<table><thead><tr><th>Relation</th><th>Type</th><th>From</th>"
            "<th>To</th><th>Label</th><th>Evidence</th></tr></thead><tbody>"
        )
        for relation in projection.contextual:
            targets = ", ".join(relation.target_refs)
            quote = _first_quote(relation)
            parts.append(
                f"<tr><td>{_esc(relation.candidate_relation_id)}</td>"
                f"<td>{_esc(relation.relation_type.value)}</td>"
                f"<td>{_esc(relation.source_ref)}</td><td>{_esc(targets)}</td>"
                f"<td>{_esc(relation.branch_label or '—')}</td>"
                f"<td>{_esc(quote)}</td></tr>"
            )
        parts.append("</tbody></table>")
    else:
        parts.append('<p class="map-note">No contextual relations.</p>')
    parts.append("</section>")
    parts.append(
        '<section class="disconnected"><h2 class="domain">Disconnected / non-sequential '
        'components <span class="count">(visible review items; no connector was invented)</span></h2>'
    )
    if projection.disconnected:
        parts.append("<ul>")
        for rule in projection.disconnected:
            state = rule.candidate_state.value
            issues = _rule_issue_ids(graph, rule.candidate_id)
            issue_text = f" — linked issues: {', '.join(issues)}" if issues else ""
            parts.append(
                f"<li><code>{_esc(rule.candidate_id)}</code> "
                f'<span class="chip {"blocked" if state == "BLOCKED" else "proposed"}">{_esc(state)}</span> '
                f"{_esc(_node_short_label(rule))}{_esc(issue_text)}</li>"
            )
        parts.append("</ul>")
    else:
        parts.append('<p class="map-note">Every rule participates in a sequential relation.</p>')
    if projection.orphan_edges:
        parts.append(
            '<p class="map-note"><strong>Sequential relations not drawn in the map</strong> '
            "(one endpoint is unreachable from the declared stage roots):</p><ul>"
        )
        for relation in projection.orphan_edges:
            targets = ", ".join(relation.target_refs)
            parts.append(
                f"<li><code>{_esc(relation.candidate_relation_id)}</code> "
                f"{_esc(relation.relation_type.value)} {_esc(relation.source_ref)} → "
                f"{_esc(targets)}</li>"
            )
        parts.append("</ul>")
    parts.append("</section>")
    parts.append('<section class="issues"><h2 class="domain">Unresolved Issues</h2>')
    if graph.issues:
        parts.append("<ul>")
        for issue in sorted(graph.issues, key=lambda item: item.issue_id):
            related = ", ".join(issue.related_ids) or "—"
            parts.append(
                f"<li><strong>{_esc(issue.issue_id)}</strong> "
                f"[{_esc(issue.category.value)} · {_esc(issue.severity.value)}] "
                f"{_esc(issue.description)} <em>related: {_esc(related)}</em></li>"
            )
        parts.append("</ul>")
    else:
        parts.append('<p class="map-note">No open Issues.</p>')
    parts.append("</section>")
    parts.append(
        '<section class="evidence"><h2 class="domain">Evidence reference '
        '<span class="count">(page and span ids per rule; see candidate_graph.json for quotes)</span></h2>'
    )
    parts.append(
        "<table><thead><tr><th>Rule</th><th>State</th><th>Action</th>"
        "<th>Page(s)</th><th>Span ids</th></tr></thead><tbody>"
    )
    for rule in sorted(graph.rules, key=lambda item: item.candidate_id):
        span_ids: set[str] = set()
        for binding in rule.evidence_bindings:
            span_ids.update(binding.source_span_refs)
        for action in rule.actions:
            for binding in action.evidence_bindings:
                span_ids.update(binding.source_span_refs)
        pages: set[int] = set()
        for span_id in span_ids:
            span = next((item for item in graph.source_spans if item.span_id == span_id), None)
            if span is not None:
                pages.add(span.page)
        page_text = ", ".join(str(page) for page in sorted(pages)) or "—"
        span_text = ", ".join(sorted(span_ids)) or "—"
        parts.append(
            f"<tr><td>{_esc(rule.candidate_id)}</td>"
            f"<td>{_esc(rule.candidate_state.value)}</td>"
            f"<td>{_esc(_node_short_label(rule))}</td>"
            f"<td>{_esc(page_text)}</td><td>{_esc(span_text)}</td></tr>"
        )
    parts.append("</tbody></table></section>")
    parts.append(
        '<footer class="derived">Candidate review projection generated by '
        "cpg_tree.views.review_tree. Nothing here is clinically approved; review and "
        "adjudication are human responsibilities.</footer>"
    )
    parts.append("</main></body></html>")
    return "".join(parts)


def _first_quote(relation: CandidateRelation) -> str:
    for binding in relation.evidence_bindings:
        quote = binding.exact_quote
        if quote:
            return str(quote)
    return "—"


_HTML_CSS = """
<style>
:root { --ink: #1f2937; --muted: #6b7280; --line: #d1d5db; --bg: #f6f7f9;
        --card: #ffffff; --accent: #0f4c81; --blocked: #b3261e; --stage: #7a4a9e; }
* { box-sizing: border-box; }
body { margin: 0; color: var(--ink); background: var(--bg);
       font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
       line-height: 1.45; }
header.review-header { background: var(--accent); color: #fff; padding: 1.4rem 2rem; }
header.review-header h1 { margin: 0 0 .3rem 0; font-size: 1.35rem; }
header.review-header .meta { font-size: .9rem; opacity: .95; margin: 0; }
header.review-header .derived { margin: .7rem 0 0 0; font-size: .78rem; opacity: .85; }
main { max-width: 1240px; margin: 0 auto; padding: 1rem 1.6rem 2rem 1.6rem; }
section.legend, section.notes, section.map-wrap, section.contextual, section.disconnected,
section.issues, section.evidence { background: var(--card); border: 1px solid var(--line);
  border-radius: 6px; padding: .9rem 1.1rem; margin: 0 0 1rem 0; font-size: .85rem; }
section.map-wrap svg { display: block; margin: .4rem auto 0 auto; max-width: 100%; height: auto; }
h2.domain { border-bottom: 2px solid var(--accent); padding-bottom: .25rem;
            margin: 0 0 .7rem 0; font-size: 1.05rem; }
h2.domain .count { color: var(--muted); font-weight: normal; font-size: .78rem; }
.chip { display: inline-block; border-radius: 10px; padding: .02rem .5rem; font-size: .7rem;
        font-weight: 600; border: 1px solid var(--line); }
.chip.proposed { color: var(--accent); border-color: var(--accent); }
.chip.blocked { color: var(--blocked); border-color: var(--blocked); }
.chip.edge-blocked { color: var(--blocked); border-color: var(--blocked);
                     border-style: dashed; }
.chip.cycle { color: var(--muted); border-style: dotted; }
.chip.stage { color: var(--stage); border-color: var(--stage); }
table { border-collapse: collapse; width: 100%; font-size: .8rem; }
th, td { border: 1px solid var(--line); padding: .3rem .5rem; text-align: left;
         vertical-align: top; }
th { background: #eef3f8; }
ul { margin: .3rem 0 0 0; padding-left: 1.2rem; }
p.map-note { font-size: .8rem; color: var(--muted); margin: .2rem 0; }
footer.derived { font-size: .75rem; color: var(--muted); padding: .4rem 1.6rem 1.2rem 1.6rem; }
</style>
"""
