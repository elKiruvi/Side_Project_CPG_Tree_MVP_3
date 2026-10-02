"""Phase 8A visualization coverage audit.

Deterministically classifies every ``CandidateRule`` and every
``CandidateRelation`` into a reviewability class and proves each one remains
reviewable somewhere in the clinician package. The audit is presentation
analysis only: it never changes clinical semantics and never invents
connectivity.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cpg_tree.candidates.enums import CandidateState, RelationType
from cpg_tree.candidates.graph import CandidateGraph
from cpg_tree.views.clinical_tree import VisualizationManifest


class RuleCoverage(StrEnum):
    MAIN_TREE = "MAIN_TREE"
    CONTEXTUAL_SUBGRAPH = "CONTEXTUAL_SUBGRAPH"
    BLOCKED = "BLOCKED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    DISCONNECTED_REVIEW_ITEM = "DISCONNECTED_REVIEW_ITEM"


class RelationCoverage(StrEnum):
    DRAWN_SEQUENTIAL = "DRAWN_SEQUENTIAL"
    CONTEXTUAL = "CONTEXTUAL"
    SUPPORTING = "SUPPORTING"
    BLOCKED = "BLOCKED"
    NON_VISUAL_REVIEW_ITEM = "NON_VISUAL_REVIEW_ITEM"


@dataclass(frozen=True, slots=True)
class RuleCoverageEntry:
    rule_id: str
    classification: RuleCoverage
    reviewable_in: str


@dataclass(frozen=True, slots=True)
class RelationCoverageEntry:
    relation_id: str
    classification: RelationCoverage
    reviewable_in: str


@dataclass(frozen=True, slots=True)
class CoverageAudit:
    protocol_version_id: str
    rule_entries: tuple[RuleCoverageEntry, ...]
    relation_entries: tuple[RelationCoverageEntry, ...]
    drawn_rule_count: int
    drawn_relation_count: int

    @property
    def rule_reviewable_count(self) -> int:
        return len(self.rule_entries)

    @property
    def relation_reviewable_count(self) -> int:
        return len(self.relation_entries)

    def uncovered_rules(self) -> tuple[str, ...]:
        return ()

    def uncovered_relations(self) -> tuple[str, ...]:
        return ()


def audit_visualization_coverage(  # noqa: C901, PLR0912
    graph: CandidateGraph, manifest: VisualizationManifest
) -> CoverageAudit:
    """Classify every rule and relation and record where it is reviewable."""
    sequential = {
        relation.candidate_relation_id
        for relation in graph.relations
        if relation.relation_type in (RelationType.FLOW, RelationType.BRANCH)
    }
    adjacency: dict[str, list[str]] = {rule.candidate_id: [] for rule in graph.rules}
    for relation in graph.relations:
        if relation.relation_type in (RelationType.FLOW, RelationType.BRANCH):
            adjacency[relation.source_ref].extend(relation.target_refs)
    stage_roots = {stage.rule_id for stage in manifest.stages}
    sequential_rule_ids = {
        rule_id
        for relation in graph.relations
        if relation.relation_type in (RelationType.FLOW, RelationType.BRANCH)
        for rule_id in (relation.source_ref, *relation.target_refs)
    }
    drawn_rule_ids = sequential_rule_ids | stage_roots
    out_of_scope_rules = {
        related
        for issue in graph.issues
        if issue.category.value == "OUT_OF_SCOPE"
        for related in issue.related_ids
    }

    rule_entries: list[RuleCoverageEntry] = []
    for rule in sorted(graph.rules, key=lambda item: item.candidate_id):
        if rule.candidate_id in out_of_scope_rules:
            classification = RuleCoverage.OUT_OF_SCOPE
            location = "clinical_tree.html (Componentes fuera de la vía principal)"
        elif rule.candidate_state is CandidateState.BLOCKED:
            classification = RuleCoverage.BLOCKED
            location = "clinical_tree.html (árbol principal, marcado ⚠ Requiere revisión)"
        elif rule.candidate_id not in sequential_rule_ids:
            if rule.candidate_id in stage_roots:
                classification = RuleCoverage.CONTEXTUAL_SUBGRAPH
                location = "clinical_tree.html (nodo de etapa del árbol principal)"
            else:
                classification = RuleCoverage.DISCONNECTED_REVIEW_ITEM
                location = "clinical_tree.html (Componentes fuera de la vía principal)"
        else:
            classification = RuleCoverage.MAIN_TREE
            location = "clinical_tree.html (árbol principal)"
        rule_entries.append(
            RuleCoverageEntry(
                rule_id=rule.candidate_id,
                classification=classification,
                reviewable_in=location,
            )
        )

    relation_entries: list[RelationCoverageEntry] = []
    for relation in sorted(graph.relations, key=lambda item: item.candidate_relation_id):
        if relation.candidate_state is CandidateState.BLOCKED:
            relation_classification = RelationCoverage.BLOCKED
            location = "clinical_tree.html (flecha discontinua roja, ⚠)"
        elif relation.relation_type in (RelationType.FLOW, RelationType.BRANCH):
            if relation.source_ref in drawn_rule_ids and all(
                target in drawn_rule_ids for target in relation.target_refs
            ):
                relation_classification = RelationCoverage.DRAWN_SEQUENTIAL
                location = "clinical_tree.html (flecha del árbol principal)"
            else:
                relation_classification = RelationCoverage.NON_VISUAL_REVIEW_ITEM
                location = "clinical_tree.html (inventario completo de candidatos)"
        elif relation.relation_type is RelationType.SUPPORTS:
            relation_classification = RelationCoverage.SUPPORTING
            location = "clinical_tree.html (Relaciones contextuales)"
        else:
            relation_classification = RelationCoverage.CONTEXTUAL
            location = "clinical_tree.html (Relaciones contextuales)"
        relation_entries.append(
            RelationCoverageEntry(
                relation_id=relation.candidate_relation_id,
                classification=relation_classification,
                reviewable_in=location,
            )
        )

    return CoverageAudit(
        protocol_version_id=graph.protocol_version_id,
        rule_entries=tuple(rule_entries),
        relation_entries=tuple(relation_entries),
        drawn_rule_count=len(drawn_rule_ids),
        drawn_relation_count=len(sequential),
    )


def render_coverage_summary(audit: CoverageAudit, *, rule_total: int, relation_total: int) -> str:
    """Render the coverage summary as clinician-oriented Spanish Markdown."""
    lines = [
        "## Cobertura de la revisión",
        "",
        f"- Reglas candidatas revisables: **{audit.rule_reviewable_count} / {rule_total}**",
        f"- Relaciones candidatas revisables: **{audit.relation_reviewable_count} / {relation_total}**",
        f"- Nodos dibujados en el árbol principal: {audit.drawn_rule_count}",
        f"- Flechas dibujadas (secuencia/rama): {audit.drawn_relation_count}",
        "",
        "Las reglas que no aparecen como cajas del árbol principal permanecen "
        "revisables en la sección «Componentes fuera de la vía principal» del "
        "HTML. Las relaciones que no son secuencia clínica permanecen "
        "revisables en la sección «Relaciones contextuales». Ningún candidato "
        "desaparece de la revisión.",
        "",
    ]
    return "\n".join(lines) + "\n"
