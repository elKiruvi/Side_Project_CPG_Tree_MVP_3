"""Clinician-friendly Markdown tree projection (presentation only).

Renders a ``CandidateGraph`` plus a ``VisualizationManifest`` into a plain
Unicode/Markdown clinical pathway readable in any Markdown viewer (no Mermaid
dependency). The output contains ONLY the candidate tree plus a one-line
pending-validation warning: no review questions, no methodology, no
architecture.

Semantics rules:

- Every branch arrow shown corresponds to a canonical FLOW/BRANCH relation.
- Contextual relations appear in a separate CONTEXTO block and are never
  drawn as sequential arrows.
- Compound conditions stay compound; no artificial decision chain is created.
- BLOCKED/out-of-scope/conflicting elements stay visible with ⚠ markers.
- Traceability ids are emitted as HTML comments (invisible when rendered),
  never as primary content.
- The renderer is generic: per-protocol presentation comes from the manifest.
"""

# ruff: noqa: C901, PLR0912

from __future__ import annotations

from cpg_tree.candidates.enums import CandidateState, RelationType
from cpg_tree.candidates.graph import CandidateGraph
from cpg_tree.candidates.relations import CandidateRelation
from cpg_tree.candidates.rules import CandidateRule
from cpg_tree.views.clinical_tree import (
    CANDIDATE_BANNER,
    VisualizationManifest,
    _relation_type_es,
)
from cpg_tree.views.coverage_audit import CoverageAudit, RuleCoverage, audit_visualization_coverage

_SEQUENTIAL = (RelationType.FLOW, RelationType.BRANCH)
_COLLAPSE_THRESHOLD = 2


def render_clinical_tree_markdown(graph: CandidateGraph, manifest: VisualizationManifest) -> str:
    """Render the complete candidate tree as clinician-readable Markdown."""
    audit = audit_visualization_coverage(graph, manifest)
    rules = {rule.candidate_id: rule for rule in graph.rules}
    sequential = [relation for relation in graph.relations if relation.relation_type in _SEQUENTIAL]
    adjacency: dict[str, list[tuple[CandidateRelation, str]]] = {rule_id: [] for rule_id in rules}
    for relation in sequential:
        adjacency.setdefault(relation.source_ref, []).extend(
            (relation, target) for target in relation.target_refs
        )
    groups: list[tuple[str, list[str]]] = []
    group_by_label: dict[str, int] = {}
    for anchor in manifest.stages:
        if anchor.label not in group_by_label:
            group_by_label[anchor.label] = len(groups)
            groups.append((anchor.label, []))
        groups[group_by_label[anchor.label]][1].append(anchor.rule_id)
    staged: dict[str, int] = {}
    for group_id, (_, roots) in enumerate(groups):
        for root in roots:
            frontier = [root]
            while frontier:
                current = frontier.pop(0)
                if current in staged or current not in rules:
                    continue
                staged[current] = group_id
                frontier.extend(target for _, target in adjacency.get(current, ()))

    lines = [
        "# Árbol clínico candidato — " + graph.protocol_version_id.replace("-v", " v"),
        "",
        f"> ⚠️ **{CANDIDATE_BANNER}**",
        "",
    ]
    for group_id, (label, roots) in enumerate(groups, start=1):
        stage_rules = {rule_id for rule_id, index in staged.items() if index == group_id - 1}
        if not stage_rules:
            continue
        lines.append(f"## ETAPA {group_id} — {label.upper()}")
        lines.append("")
        for root in roots:
            if root not in stage_rules:
                continue
            lines.extend(_entry_box(root, graph, manifest))
            lines.append("")
        stage_groups: dict[tuple[str, str], list[tuple[CandidateRelation, str]]] = {}
        for source in stage_rules:
            for relation, target in adjacency.get(source, ()):
                if target in stage_rules:
                    key = (target, relation.branch_label or "")
                    stage_groups.setdefault(key, []).append((relation, source))
        collapsed = {
            key for key, entries in stage_groups.items() if len(entries) > _COLLAPSE_THRESHOLD
        }
        stage_seen: set[str] = set()
        for root in roots:
            if root not in stage_rules:
                continue
            lines.extend(
                _render_branch_tree(
                    root, graph, manifest, stage_rules, adjacency, collapsed, stage_seen
                )
            )
        lines.extend(_render_collapsed(stage_groups, collapsed, graph, manifest))
        lines.append("")
    lines.extend(_render_context_section(graph, manifest))
    lines.extend(_render_disconnected_section(graph, manifest, audit))
    blocked = sum(rule.candidate_state is CandidateState.BLOCKED for rule in graph.rules)
    blocked_relations = sum(
        relation.candidate_state is CandidateState.BLOCKED for relation in graph.relations
    )
    lines.extend(
        [
            "---",
            "",
            f"Reglas candidatas: {len(graph.rules)} · Relaciones: {len(graph.relations)} · "
            f"Pendientes de revisión: {blocked} reglas y {blocked_relations} relaciones · "
            "Aprobación clínica: 0.",
        ]
    )
    return "\n".join(lines) + "\n"


def _entry_box(rule_id: str, graph: CandidateGraph, manifest: VisualizationManifest) -> list[str]:
    title = _status_marker(rule_id, graph) + _label(rule_id, graph, manifest)
    return _box(title)


def _render_branch_tree(  # noqa: PLR0913, PLR0917
    rule_id: str,
    graph: CandidateGraph,
    manifest: VisualizationManifest,
    stage_rules: set[str],
    adjacency: dict[str, list[tuple[CandidateRelation, str]]],
    collapsed: set[tuple[str, str]],
    seen: set[str],
) -> list[str]:
    if rule_id in seen or rule_id not in stage_rules:
        return []
    seen.add(rule_id)
    lines: list[str] = []
    label = _label(rule_id, graph, manifest)
    marker = _status_marker(rule_id, graph)
    outgoing = adjacency.get(rule_id, ())
    if outgoing or rule_id in _stage_roots(manifest):
        lines.append(f"• {marker}**{label}** <!-- rule:{rule_id} -->")
    groups: dict[tuple[str, str], list[tuple[CandidateRelation, str]]] = {}
    for relation, target in outgoing:
        key = (target, relation.branch_label or "")
        groups.setdefault(key, []).append((relation, target))
    for (target, branch_label), entries in sorted(
        groups.items(), key=lambda item: (item[0][0], item[0][1])
    ):
        edge_label = manifest.branch_labels.get(
            entries[0][0].candidate_relation_id, branch_label or "—"
        )
        for relation, _ in entries:
            lines.append(f"    <!-- rel:{relation.candidate_relation_id} -->")
        if (target, branch_label) in collapsed:
            continue
        target_marker = _status_marker(target, graph)
        target_label = _label(target, graph, manifest)
        blocked_mark = (
            " ⚠ BLOQUEADA"
            if any(relation.candidate_state is CandidateState.BLOCKED for relation, _ in entries)
            else ""
        )
        lines.append(
            f"    ├─ [{edge_label}] → {target_marker}**{target_label}**{blocked_mark}"
            f" <!-- rule:{target} -->"
        )
    for child in sorted({target for _, target in outgoing if target in stage_rules}):
        lines.extend(
            _render_branch_tree(child, graph, manifest, stage_rules, adjacency, collapsed, seen)
        )
    return lines


def _stage_roots(manifest: VisualizationManifest) -> set[str]:
    return {anchor.rule_id for anchor in manifest.stages}


def _render_collapsed(
    stage_groups: dict[tuple[str, str], list[tuple[CandidateRelation, str]]],
    collapsed: set[tuple[str, str]],
    graph: CandidateGraph,
    manifest: VisualizationManifest,
) -> list[str]:
    lines: list[str] = []
    for (target, branch_label), entries in sorted(stage_groups.items()):
        if (target, branch_label) not in collapsed:
            continue
        if not entries:
            continue
        edge_label = manifest.branch_labels.get(
            entries[0][0].candidate_relation_id, branch_label or "—"
        )
        marker = _status_marker(target, graph)
        label = _label(target, graph, manifest)
        blocked_mark = (
            " ⚠ BLOQUEADA"
            if any(relation.candidate_state is CandidateState.BLOCKED for relation, _ in entries)
            else ""
        )
        relation_ids = ",".join(sorted(relation.candidate_relation_id for relation, _ in entries))
        lines.append(
            f"└─ [{edge_label}] → {marker}**{label}**{blocked_mark} "
            "<!-- rel:" + relation_ids + " --> <!-- rule:" + target + " -->"
        )
    return lines


def _render_context_section(graph: CandidateGraph, manifest: VisualizationManifest) -> list[str]:
    contextual = sorted(
        (relation for relation in graph.relations if relation.relation_type not in _SEQUENTIAL),
        key=lambda item: item.candidate_relation_id,
    )
    if not contextual:
        return []
    lines = ["## CONTEXTO (relaciones no secuenciales)", ""]
    for relation in contextual:
        source_label = _label(relation.source_ref, graph, manifest)
        target_labels = ", ".join(
            _label(target, graph, manifest) for target in relation.target_refs
        )
        note = manifest.branch_labels.get(
            relation.candidate_relation_id, relation.branch_label or "—"
        )
        lines.append(
            f"- {source_label} —[{_relation_type_es(relation.relation_type.value)}]→ "
            f"{target_labels} · {note} <!-- rel:{relation.candidate_relation_id} -->"
        )
    lines.append("")
    return lines


def _render_disconnected_section(
    graph: CandidateGraph, manifest: VisualizationManifest, audit: CoverageAudit
) -> list[str]:
    disconnected = [
        entry
        for entry in audit.rule_entries
        if entry.classification
        in {
            RuleCoverage.DISCONNECTED_REVIEW_ITEM,
            RuleCoverage.OUT_OF_SCOPE,
        }
    ]
    if not disconnected:
        return []
    lines = ["## FUERA DE LA VÍA PRINCIPAL", ""]
    for entry in disconnected:
        label = _label(entry.rule_id, graph, manifest)
        rule = _rule_by_id(graph, entry.rule_id)
        state = rule.candidate_state.value if rule is not None else "PROPOSED"
        if entry.classification is RuleCoverage.OUT_OF_SCOPE:
            title = "⚠ FUERA DE ALCANCE (protocolo adulto) — " + label
        elif state == "BLOCKED":
            title = "⚠ PENDIENTE DE REVISIÓN — " + label
        else:
            title = "⚠ CONTEXTO INDEPENDIENTE — " + label
        lines.extend(_box(title))
        lines.append(f"<!-- rule:{entry.rule_id} -->")
        lines.append("")
    return lines


def _label(rule_id: str, graph: CandidateGraph, manifest: VisualizationManifest) -> str:
    rule = _rule_by_id(graph, rule_id)
    if rule is not None:
        return str(manifest.node_labels.get(rule_id, _fallback(rule)))
    return rule_id


def _fallback(rule: CandidateRule) -> str:
    if rule.actions and rule.actions[0].target_text:
        return str(rule.actions[0].target_text)
    return str(rule.candidate_id)


def _rule_by_id(graph: CandidateGraph, rule_id: str) -> CandidateRule | None:
    return next((rule for rule in graph.rules if rule.candidate_id == rule_id), None)


def _status_marker(rule_id: str, graph: CandidateGraph) -> str:
    rule = _rule_by_id(graph, rule_id)
    if rule is None:
        return ""
    issues = {issue.category.value: issue for issue in graph.issues if rule_id in issue.related_ids}
    if rule.candidate_state is CandidateState.BLOCKED:
        return "⚠ PENDIENTE — "
    if "OUT_OF_SCOPE" in issues:
        return "⚠ FUERA DE ALCANCE — "
    if "SOURCE_CONFLICT" in issues:
        return "⚠ CONFLICTO — "
    return ""


def _box(text: str, *, max_width: int = 66) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if not lines:
        lines = [""]
    width = max(len(line) for line in lines)
    top = "┌" + "─" * (width + 2) + "┐"
    bottom = "└" + "─" * (width + 2) + "┘"
    return [top, *(f"│ {line:<{width}} │" for line in lines), bottom]
