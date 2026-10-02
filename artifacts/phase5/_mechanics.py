"""Generic mechanics for Phase 5 semantic reconciliation of candidate graphs.

This module contains ONLY mechanical helpers (relation editing, output writing,
report generation). All clinical decisions live in the protocol-specific
``reconcile_graph.py`` modules beside it. Nothing here interprets clinical
meaning.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from cpg_tree.candidates.enums import CandidateState, EvidenceClass, RelationType
from cpg_tree.candidates.evidence import EvidenceBinding
from cpg_tree.candidates.graph import CandidateGraph, validate_candidate_graph
from cpg_tree.candidates.graph_serialization import load_candidate_graph, write_candidate_graph
from cpg_tree.candidates.relations import CandidateRelation
from cpg_tree.views.review_tree import (
    ProjectionManifest,
    load_projection_manifest,
    render_review_tree_html,
    render_review_tree_svg,
)

_SEQUENTIAL_TYPES = (RelationType.FLOW, RelationType.BRANCH)


def edit_relation(  # noqa: PLR0913
    relation: CandidateRelation,
    *,
    relation_type: RelationType | None = None,
    source_ref: str | None = None,
    target_refs: tuple[str, ...] | None = None,
    branch_label: str | None = None,
    temporal_qualifier: str | None = None,
    observation_refs: tuple[str, ...] | None = None,
    candidate_state: CandidateState | None = None,
) -> CandidateRelation:
    """Return an edited copy of a candidate relation with a fresh content hash."""
    changes: dict[str, object] = {}
    if relation_type is not None:
        changes["relation_type"] = relation_type
    if source_ref is not None:
        changes["source_ref"] = source_ref
    if target_refs is not None:
        changes["target_refs"] = target_refs
    if branch_label is not None:
        changes["branch_label"] = branch_label
    if temporal_qualifier is not None:
        changes["temporal_qualifier"] = temporal_qualifier
    if observation_refs is not None:
        changes["observation_refs"] = observation_refs
    if candidate_state is not None:
        changes["candidate_state"] = candidate_state
    changes["content_hash"] = None
    return replace(relation, **changes)


def add_relation(  # noqa: PLR0913
    *,
    relation_id: str,
    source: str,
    targets: tuple[str, ...],
    relation_type: RelationType,
    spans: tuple[str, ...],
    quote: str,
    label: str | None = None,
    temporal: str | None = None,
) -> CandidateRelation:
    """Build a new source-supported candidate relation with evidence."""
    return CandidateRelation(
        candidate_relation_id=relation_id,
        revision=1,
        source_ref=source,
        target_refs=targets,
        relation_type=relation_type,
        branch_label=label,
        temporal_qualifier=temporal,
        observation_refs=(f"obs-{source}",),
        evidence_class=EvidenceClass.NORMALIZED,
        evidence_bindings=(
            EvidenceBinding(
                claim_path="/target_refs/0",
                evidence_class=EvidenceClass.NORMALIZED,
                source_span_refs=spans,
                exact_quote=quote,
                transformation="Structured from source wording; pending clinical review.",
            ),
        ),
    )


def rebuild(graph: CandidateGraph) -> CandidateGraph:
    """Re-run deterministic structural validation after semantic edits."""
    return replace(graph, findings=validate_candidate_graph(graph))


def sequential_relation_ids(graph: CandidateGraph) -> tuple[str, ...]:
    """Sequential (pathway) relation ids, sorted."""
    return tuple(
        sorted(
            relation.candidate_relation_id
            for relation in graph.relations
            if relation.relation_type in _SEQUENTIAL_TYPES
        )
    )


def count_back_edges(graph: CandidateGraph, roots: tuple[str, ...]) -> int:
    """Count sequential edges that close a cycle (target can reach source).

    A nonzero count indicates a reassessment loop structure for review. This is
    a presentation heuristic, never a clinical decision.
    """
    adjacency: dict[str, set[str]] = {}
    for relation in graph.relations:
        if relation.relation_type not in _SEQUENTIAL_TYPES:
            continue
        adjacency.setdefault(relation.source_ref, set()).update(relation.target_refs)
    back_edges = 0
    for relation in graph.relations:
        if relation.relation_type not in _SEQUENTIAL_TYPES:
            continue
        for target in relation.target_refs:
            if _can_reach(adjacency, target, relation.source_ref):
                back_edges += 1
    return back_edges


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


def write_outputs(  # noqa: PLR0913
    *,
    graph: CandidateGraph,
    out_dir: Path,
    protocol_name: str,
    initial_relations: int,
    decisions: tuple[tuple[str, str, str], ...],
    kept_rationales: dict[str, str],
) -> None:
    """Write the reconciled JSON, review visuals, and reconciliation report."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "candidate_graph.json"
    if json_path.exists():
        json_path.unlink()
    write_candidate_graph(graph, json_path)

    manifest = load_projection_manifest(out_dir / "projection.yaml")
    html_path = out_dir / "review_tree.html"
    svg_path = out_dir / "review_tree.svg"
    html_path.write_text(render_review_tree_html(graph, manifest), encoding="utf-8")
    svg_path.write_text(render_review_tree_svg(graph, manifest), encoding="utf-8")

    roots = tuple(stage.rule_id for stage in manifest.stages)
    changed_ids = {decision[0] for decision in decisions if decision[1] != "KEEP"}
    kept = len(kept_rationales)
    retyped = sum(1 for decision in decisions if "RETYPE" in decision[1])
    retargeted = sum(1 for decision in decisions if "RETARGET" in decision[1])
    removed = sum(1 for decision in decisions if decision[1] == "REMOVE")
    blocked = sum(
        1 for relation in graph.relations if relation.candidate_state is CandidateState.BLOCKED
    )
    added = len(graph.relations) - (initial_relations - removed)
    report_lines = [
        f"# {protocol_name} — Phase 5 reconciliation report",
        "",
        "Generated deterministically by the Phase 5 reconcile module. This is a "
        "semantic review record of relation-level decisions; the CandidateGraph "
        "remains canonical and no candidate was promoted to approved knowledge.",
        "",
        "## Counts",
        "",
        f"- CandidateRules: {len(graph.rules)} (unchanged from Phase 4)",
        f"- initial CandidateRelations: {initial_relations}",
        f"- final CandidateRelations: {len(graph.relations)}",
        f"- relations kept: {kept}",
        f"- relations retyped: {retyped}",
        f"- relations retargeted: {retargeted}",
        f"- relations removed: {removed}",
        f"- relations added: {added}",
        f"- relations blocked: {blocked}",
        f"- open Issues: {len(graph.issues)}",
        f"- structural findings: {len(graph.findings)} "
        f"(errors: {sum(1 for item in graph.findings if item.severity.value == 'ERROR')}, "
        f"warnings: {sum(1 for item in graph.findings if item.severity.value == 'WARNING')})",
        f"- sequential back edges (cycle annotations): {count_back_edges(graph, roots)}",
        "",
        "## Relation decisions",
        "",
    ]
    for relation_id, action, rationale in decisions:
        report_lines.append(f"- **{relation_id}** — {action}: {rationale}")
    for relation in sorted(graph.relations, key=lambda item: item.candidate_relation_id):
        if (
            relation.candidate_relation_id in changed_ids
            or relation.candidate_relation_id in kept_rationales
        ):
            continue
        report_lines.append(
            f"- **{relation.candidate_relation_id}** — ADD: {_relation_summary(relation)}"
        )
    for relation_id in sorted(kept_rationales):
        report_lines.append(f"- **{relation_id}** — KEEP: {kept_rationales[relation_id]}")
    (out_dir / "reconciliation_report.md").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8"
    )


def _relation_summary(relation: CandidateRelation) -> str:
    targets = ", ".join(relation.target_refs)
    return (
        f"{relation.relation_type.value} {relation.source_ref} → {targets} "
        f"(label: {relation.branch_label or '—'})"
    )


__all__ = [
    "ProjectionManifest",
    "add_relation",
    "count_back_edges",
    "edit_relation",
    "load_candidate_graph",
    "rebuild",
    "sequential_relation_ids",
    "write_outputs",
]
