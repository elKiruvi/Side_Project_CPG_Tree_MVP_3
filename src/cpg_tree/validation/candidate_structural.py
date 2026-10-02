"""Deterministic structural validation for Candidate Graphs (Phase 6).

This module validates the TECHNICAL integrity of candidate artifacts. It never
performs clinical interpretation: it does not judge thresholds, medications,
AND/OR choices, or whether two rules should be connected. It reports problems;
it never repairs clinical meaning and never creates edges, rules, or Issues.

The validator covers:

- identity and protocol/document consistency;
- provenance (evidence bindings, span references, exact quotes, claim paths);
- ClinicalExpression structural invariants (including N-of-M);
- CandidateRelation structural invariants;
- state invariants (PROPOSED/BLOCKED only; no approved artifacts);
- reachability, disconnected components, entry points, terminal nodes, cycles;
- projection parity (review visuals must map back to canonical objects);
- review-readiness classification.

``READY_FOR_CLINICAL_REVIEW`` means "structurally trustworthy and reviewable".
It is NOT clinical validation and NOT approval: unresolved clinical ambiguity
with intact structure remains ready for review, because that ambiguity is
exactly what the clinician must examine.
"""

# ruff: noqa: C901

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from cpg_tree.candidates.actions import ActionSpec
from cpg_tree.candidates.enums import CandidateState, EvidenceClass, RelationType
from cpg_tree.candidates.evidence import EvidenceBinding
from cpg_tree.candidates.graph import CandidateGraph
from cpg_tree.candidates.graph_serialization import dump_candidate_graph
from cpg_tree.candidates.relations import CandidateRelation
from cpg_tree.candidates.rules import CandidateRule
from cpg_tree.candidates.variables import VariableSpec
from cpg_tree.extraction.spans import SpanQualityFlag
from cpg_tree.knowledge.conditions import Condition, LogicalOperand
from cpg_tree.knowledge.enums import ConditionKind, VariableType
from cpg_tree.validation.model import FindingSeverity, ValidationFinding, finding_sort_key
from cpg_tree.views.review_tree import (
    ProjectionManifest,
    render_review_tree_html,
    render_review_tree_svg,
)

_SEQUENTIAL_TYPES = (RelationType.FLOW, RelationType.BRANCH)

READY_FOR_CLINICAL_REVIEW = "READY_FOR_CLINICAL_REVIEW"
NOT_READY_FOR_CLINICAL_REVIEW = "NOT_READY_FOR_CLINICAL_REVIEW"


class ComponentClassification(StrEnum):
    """Why a disconnected component is not part of the main pathway."""

    ENTRY_COMPONENT = "ENTRY_COMPONENT"
    ISOLATED_CONTEXT = "ISOLATED_CONTEXT"
    UNREACHABLE_PATHWAY = "UNREACHABLE_PATHWAY"


@dataclass(frozen=True, slots=True)
class ComponentInfo:
    """One disconnected component with its deterministic classification."""

    component_id: int
    rule_ids: tuple[str, ...]
    classification: ComponentClassification
    note: str


@dataclass(frozen=True, slots=True)
class CycleInfo:
    """One detected sequential cycle for review (not automatically fatal)."""

    relation_ids: tuple[str, ...]
    rule_ids: tuple[str, ...]
    note: str


@dataclass(frozen=True, slots=True)
class CandidateStructureReport:
    """Deterministic structural validation outcome for one candidate graph."""

    protocol_version_id: str
    graph_id: str
    findings: tuple[ValidationFinding, ...]
    rule_count: int
    relation_count: int
    issue_count: int
    blocked_rule_count: int
    blocked_relation_count: int
    entry_points: tuple[str, ...]
    terminal_nodes: tuple[str, ...]
    disconnected_components: tuple[ComponentInfo, ...]
    cycles: tuple[CycleInfo, ...]
    provenance_status: str
    projection_parity_status: str
    review_readiness: str
    graph_content_hash: str

    @property
    def error_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity is FindingSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity is FindingSeverity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity is FindingSeverity.INFO)


def validate_candidate_structure(
    graph: CandidateGraph,
    manifest: ProjectionManifest | None = None,
    *,
    artifact_files: Mapping[str, Path] | None = None,
) -> CandidateStructureReport:
    """Run the complete deterministic structural validation.

    ``manifest`` enables entry-point and projection checks; ``artifact_files``
    (keys: html, svg, questions) enables visual parity and review-readiness
    checks against committed artifacts.
    """
    findings: list[ValidationFinding] = []
    findings.extend(_identity_findings(graph))
    findings.extend(_provenance_findings(graph))
    findings.extend(_expression_findings(graph))
    findings.extend(_relation_findings(graph))
    findings.extend(_state_findings(graph))
    entry_points, terminals, components, cycles = _topology(graph, manifest)
    findings.extend(_topology_findings(graph, manifest, entry_points, components, cycles))
    findings.extend(_projection_findings(graph, manifest, artifact_files))
    findings.extend(_review_packet_findings(graph, manifest, artifact_files))

    findings = sorted(set(findings), key=finding_sort_key)
    provenance_status = _status(findings, "PROVENANCE")
    parity_status = _parity_status(findings, artifact_files)
    review_readiness = _review_readiness(findings, artifact_files, parity_status)
    return CandidateStructureReport(
        protocol_version_id=graph.protocol_version_id,
        graph_id=graph.graph_id,
        findings=tuple(findings),
        rule_count=len(graph.rules),
        relation_count=len(graph.relations),
        issue_count=len(graph.issues),
        blocked_rule_count=sum(
            rule.candidate_state is CandidateState.BLOCKED for rule in graph.rules
        ),
        blocked_relation_count=sum(
            relation.candidate_state is CandidateState.BLOCKED for relation in graph.relations
        ),
        entry_points=tuple(sorted(entry_points)),
        terminal_nodes=tuple(sorted(terminals)),
        disconnected_components=components,
        cycles=cycles,
        provenance_status=provenance_status,
        projection_parity_status=parity_status,
        review_readiness=review_readiness,
        graph_content_hash=_graph_content_hash(graph),
    )


# --------------------------------------------------------------------------
# Identity


def _identity_findings(graph: CandidateGraph) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for rule in graph.rules:
        if rule.protocol_version_id != graph.protocol_version_id:
            findings.append(
                ValidationFinding(
                    code="IDENTITY_PROTOCOL_MISMATCH",
                    severity=FindingSeverity.ERROR,
                    message=(
                        f"rule {rule.candidate_id} declares protocol "
                        f"{rule.protocol_version_id!r} inside graph "
                        f"{graph.protocol_version_id!r}"
                    ),
                    path=f"/rules/{rule.candidate_id}/protocol_version_id",
                    related_ids=(rule.candidate_id,),
                )
            )
    for span in graph.source_spans:
        if span.document_id != graph.document_id:
            findings.append(
                ValidationFinding(
                    code="IDENTITY_DOCUMENT_MISMATCH",
                    severity=FindingSeverity.ERROR,
                    message=(
                        f"span {span.span_id} belongs to document {span.document_id!r} "
                        f"but the graph declares {graph.document_id!r}"
                    ),
                    path=f"/source_spans/{span.span_id}/document_id",
                    related_ids=(span.span_id,),
                )
            )
    return findings


# --------------------------------------------------------------------------
# Provenance


def _provenance_findings(graph: CandidateGraph) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    span_texts = {span.span_id: span for span in graph.source_spans}
    for variable in graph.variables:
        _check_bindings(
            findings,
            variable.evidence_bindings,
            f"/variables/{variable.variable_id}",
            span_texts,
            resolver=lambda path, variable=variable: _resolve_variable_path(variable, path),
        )
    for rule in graph.rules:
        _check_bindings(
            findings,
            rule.evidence_bindings,
            f"/rules/{rule.candidate_id}",
            span_texts,
            resolver=lambda path, rule=rule: _resolve_rule_path(rule, path),
        )
        for action in rule.actions:
            _check_bindings(
                findings,
                action.evidence_bindings,
                f"/rules/{rule.candidate_id}/actions/{action.action_id}",
                span_texts,
                resolver=lambda path, action=action: _resolve_action_path(action, path),
            )
    for relation in graph.relations:
        _check_bindings(
            findings,
            relation.evidence_bindings,
            f"/relations/{relation.candidate_relation_id}",
            span_texts,
            resolver=lambda path, relation=relation: _resolve_relation_path(relation, path),
        )
    return findings


def _check_bindings(
    findings: list[ValidationFinding],
    bindings: tuple[EvidenceBinding, ...],
    path_prefix: str,
    span_texts: dict[str, Any],
    resolver: Any,
) -> None:
    if not bindings:
        findings.append(
            ValidationFinding(
                code="PROVENANCE_EVIDENCE_BINDING_MISSING",
                severity=FindingSeverity.ERROR,
                message="no field-level evidence binding is present",
                path=f"{path_prefix}/evidence_bindings",
            )
        )
        return
    for index, binding in enumerate(bindings):
        binding_path = f"{path_prefix}/evidence_bindings/{index}"
        unknown_spans = [ref for ref in binding.source_span_refs if ref not in span_texts]
        if unknown_spans:
            findings.append(
                ValidationFinding(
                    code="PROVENANCE_SPAN_REFERENCE_UNKNOWN",
                    severity=FindingSeverity.ERROR,
                    message=f"evidence cites unknown spans: {sorted(unknown_spans)}",
                    path=f"{binding_path}/source_span_refs",
                )
            )
        if binding.exact_quote is not None:
            combined = "\n".join(
                span_texts[ref].extracted_text_exact or ""
                for ref in binding.source_span_refs
                if ref in span_texts
            )
            if not any(
                span_texts[ref].extracted_text_exact
                for ref in binding.source_span_refs
                if ref in span_texts
            ):
                findings.append(
                    ValidationFinding(
                        code="PROVENANCE_QUOTE_UNVERIFIABLE_VISUAL",
                        severity=FindingSeverity.INFO,
                        message=(
                            "exact quote cites visual-only span(s); the quote cannot be "
                            "verified against native text and remains manually transcribed"
                        ),
                        path=f"{binding_path}/exact_quote",
                    )
                )
            elif binding.exact_quote not in combined:
                findings.append(
                    ValidationFinding(
                        code="PROVENANCE_QUOTE_NOT_FOUND",
                        severity=FindingSeverity.ERROR,
                        message="exact quote was not found in the cited span text",
                        path=f"{binding_path}/exact_quote",
                    )
                )
        try:
            resolved = resolver(binding.claim_path)
        except (ValueError, IndexError) as exc:
            findings.append(
                ValidationFinding(
                    code="PROVENANCE_CLAIM_PATH_UNRESOLVED",
                    severity=FindingSeverity.ERROR,
                    message=f"claim path {binding.claim_path!r} does not resolve: {exc}",
                    path=f"{binding_path}/claim_path",
                )
            )
        else:
            if not resolved:
                findings.append(
                    ValidationFinding(
                        code="PROVENANCE_CLAIM_PATH_UNRESOLVED",
                        severity=FindingSeverity.ERROR,
                        message=(
                            f"claim path {binding.claim_path!r} points to no real claim property"
                        ),
                        path=f"{binding_path}/claim_path",
                    )
                )
        for ref in binding.source_span_refs:
            if ref not in span_texts:
                continue
            if SpanQualityFlag.VISUAL_ONLY in span_texts[ref].quality_flags:
                findings.append(
                    ValidationFinding(
                        code="PROVENANCE_VISUAL_EVIDENCE_LABELLED",
                        severity=FindingSeverity.INFO,
                        message="binding cites visual-only evidence; it is not native text",
                        path=f"{binding_path}/source_span_refs",
                        related_ids=(ref,),
                    )
                )


def _resolve_variable_path(variable: VariableSpec, path: str) -> bool:
    segments = _segments(path)
    if not segments:
        return False
    if segments[0] == "label":
        return len(segments) == 1 and bool(variable.label)
    if segments[0] == "unit":
        return len(segments) == 1 and variable.unit is not None
    if segments[0] == "value_type":
        return len(segments) == 1
    if (
        segments[0] == "allowed_values"
        and len(segments) == _INDEXED_PATH_LENGTH
        and variable.allowed_values
    ):
        return int(segments[1]) < len(variable.allowed_values)
    return False


def _resolve_action_path(action: ActionSpec, path: str) -> bool:
    segments = _segments(path)
    if not segments:
        return False
    head = segments[0]
    if head in {
        "target_text",
        "dose_value",
        "dose_unit",
        "route",
        "frequency",
        "duration",
        "timing",
        "alternative_group",
    }:
        return len(segments) == 1 and getattr(action, head) is not None
    if head == "qualifiers" and len(segments) == _INDEXED_PATH_LENGTH:
        return int(segments[1]) < len(action.qualifiers)
    return False


def _resolve_rule_path(rule: CandidateRule, path: str) -> bool:  # noqa: PLR0911
    segments = _segments(path)
    if not segments:
        return False
    if segments[0] == "condition":
        return _resolve_expression_path(rule.condition, segments[1:])
    if segments[0] == "applies_to":
        return rule.applies_to is not None and _resolve_expression_path(
            rule.applies_to, segments[1:]
        )
    if segments[0] == "exceptions" and len(segments) >= _INDEXED_PATH_LENGTH:
        index = int(segments[1])
        if index >= len(rule.exceptions):
            return False
        return _resolve_expression_path(rule.exceptions[index], segments[2:])
    if segments[0] == "actions" and len(segments) >= _INDEXED_PATH_LENGTH:
        index = int(segments[1])
        if index >= len(rule.actions):
            return False
        return _resolve_action_path(rule.actions[index], "/" + "/".join(segments[2:]))
    return False


def _resolve_relation_path(relation: CandidateRelation, path: str) -> bool:
    segments = _segments(path)
    if not segments:
        return False
    if segments[0] == "source_ref":
        return len(segments) == 1
    if segments[0] == "target_refs" and len(segments) == _INDEXED_PATH_LENGTH:
        return int(segments[1]) < len(relation.target_refs)
    if segments[0] == "branch_label":
        return len(segments) == 1 and relation.branch_label is not None
    if segments[0] == "temporal_qualifier":
        return len(segments) == 1 and relation.temporal_qualifier is not None
    return False


def _resolve_expression_path(expression: LogicalOperand, segments: list[str]) -> bool:  # noqa: PLR0911
    if not segments:
        return True
    head = segments[0]
    rest = segments[1:]
    if isinstance(expression, Condition):
        if head == "variable_ref":
            return not rest
        if head == "operator":
            return not rest and expression.operator is not None
        if head == "operand":
            return not rest and expression.operand is not None
        if head == "values":
            return not rest or (len(rest) == 1 and int(rest[0]) < len(expression.values or ()))
        if head == "expected":
            return not rest and expression.expected is not None
        return False
    if head == "operands":
        if not rest:
            return False
        index = int(rest[0])
        if index >= len(expression.operands):
            return False
        return _resolve_expression_path(expression.operands[index], rest[1:])
    if head == "threshold":
        return not rest and expression.threshold is not None
    return False


def _segments(path: str) -> list[str]:
    return [segment for segment in path.split("/") if segment]


_INDEXED_PATH_LENGTH = 2


# --------------------------------------------------------------------------
# Expressions


def _expression_findings(graph: CandidateGraph) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    variables = {variable.variable_id: variable for variable in graph.variables}
    for rule in graph.rules:
        expressions: list[tuple[str, LogicalOperand]] = [("condition", rule.condition)]
        if rule.applies_to is not None:
            expressions.append(("applies_to", rule.applies_to))
        for exception in rule.exceptions:
            expressions.append(("exceptions", exception))
        for label, expression in expressions:
            _validate_expression(
                findings, expression, f"/rules/{rule.candidate_id}/{label}", variables
            )
    return findings


def _validate_expression(
    findings: list[ValidationFinding],
    expression: LogicalOperand,
    path: str,
    variables: dict[str, VariableSpec],
) -> None:
    if isinstance(expression, Condition):
        variable = variables.get(expression.variable_ref)
        if variable is not None:
            if expression.kind is ConditionKind.COMPARISON and variable.value_type not in {
                VariableType.NUMERIC,
                VariableType.DURATION,
            }:
                findings.append(
                    ValidationFinding(
                        code="EXPRESSION_VARIABLE_TYPE_MISMATCH",
                        severity=FindingSeverity.WARNING,
                        message=(
                            f"COMPARISON condition references {expression.variable_ref!r} "
                            f"of type {variable.value_type.value}"
                        ),
                        path=f"{path}/kind",
                        related_ids=(expression.variable_ref,),
                    )
                )
            if (
                expression.kind is ConditionKind.MEMBERSHIP
                and variable.value_type is not VariableType.CATEGORICAL
            ):
                findings.append(
                    ValidationFinding(
                        code="EXPRESSION_VARIABLE_TYPE_MISMATCH",
                        severity=FindingSeverity.WARNING,
                        message=(
                            f"MEMBERSHIP condition references {expression.variable_ref!r} "
                            f"of type {variable.value_type.value}"
                        ),
                        path=f"{path}/kind",
                        related_ids=(expression.variable_ref,),
                    )
                )
            if (
                expression.kind is ConditionKind.FLAG
                and variable.value_type is not VariableType.BOOLEAN
            ):
                findings.append(
                    ValidationFinding(
                        code="EXPRESSION_VARIABLE_TYPE_MISMATCH",
                        severity=FindingSeverity.WARNING,
                        message=(
                            f"FLAG condition references {expression.variable_ref!r} "
                            f"of type {variable.value_type.value}"
                        ),
                        path=f"{path}/kind",
                        related_ids=(expression.variable_ref,),
                    )
                )
        return
    if not expression.operands:
        findings.append(
            ValidationFinding(
                code="EXPRESSION_EMPTY_OPERANDS",
                severity=FindingSeverity.ERROR,
                message=f"{expression.operator.value} expression has no operands",
                path=f"{path}/operands",
            )
        )
        return
    if len(expression.operands) == 1 and expression.operator.value not in {"NOT"}:
        findings.append(
            ValidationFinding(
                code="EXPRESSION_DEGENERATE_OPERATOR",
                severity=FindingSeverity.WARNING,
                message=f"{expression.operator.value} expression has a single operand",
                path=f"{path}/operands",
            )
        )
    if expression.operator.value == "AT_LEAST_N":
        threshold = expression.threshold
        if threshold is None or not 1 <= threshold <= len(expression.operands):
            findings.append(
                ValidationFinding(
                    code="EXPRESSION_INVALID_N_OF_M",
                    severity=FindingSeverity.ERROR,
                    message=(
                        f"AT_LEAST_N threshold {threshold!r} is invalid for "
                        f"{len(expression.operands)} operands"
                    ),
                    path=f"{path}/threshold",
                )
            )
    for index, operand in enumerate(expression.operands):
        _validate_expression(findings, operand, f"{path}/operands/{index}", variables)


# --------------------------------------------------------------------------
# Relations and state


def _relation_findings(graph: CandidateGraph) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    issue_rule_ids = {rule_id for issue in graph.issues for rule_id in issue.related_ids}
    seen_pairs: set[tuple[str, tuple[str, ...], str]] = set()
    for relation in graph.relations:
        path = f"/relations/{relation.candidate_relation_id}"
        if not relation.evidence_bindings:
            findings.append(
                ValidationFinding(
                    code="PROVENANCE_EVIDENCE_BINDING_MISSING",
                    severity=FindingSeverity.ERROR,
                    message="relation has no evidence binding",
                    path=f"{path}/evidence_bindings",
                    related_ids=(relation.candidate_relation_id,),
                )
            )
        if relation.relation_type in _SEQUENTIAL_TYPES and relation.evidence_class in {
            EvidenceClass.INFERRED,
            EvidenceClass.UNRESOLVED,
        }:
            findings.append(
                ValidationFinding(
                    code="RELATION_SEQUENTIAL_EVIDENCE_UNRESOLVED",
                    severity=FindingSeverity.ERROR,
                    message=(
                        f"{relation.relation_type.value} cannot rely on "
                        f"{relation.evidence_class.value} evidence"
                    ),
                    path=f"{path}/evidence_class",
                    related_ids=(relation.candidate_relation_id,),
                )
            )
        if relation.relation_type is RelationType.BRANCH and not relation.branch_label:
            findings.append(
                ValidationFinding(
                    code="RELATION_BRANCH_LABEL_MISSING",
                    severity=FindingSeverity.WARNING,
                    message="BRANCH relation has no condition label",
                    path=f"{path}/branch_label",
                    related_ids=(relation.candidate_relation_id,),
                )
            )
        pair = (relation.source_ref, relation.target_refs, relation.relation_type.value)
        if pair in seen_pairs:
            findings.append(
                ValidationFinding(
                    code="RELATION_DUPLICATE_ENDPOINTS",
                    severity=FindingSeverity.WARNING,
                    message="duplicate relation with identical endpoints and type",
                    path=path,
                    related_ids=(relation.candidate_relation_id,),
                )
            )
        seen_pairs.add(pair)
        if (
            relation.candidate_state is CandidateState.BLOCKED
            and relation.candidate_relation_id not in issue_rule_ids
        ):
            findings.append(
                ValidationFinding(
                    code="STATE_BLOCKED_WITHOUT_ISSUE",
                    severity=FindingSeverity.WARNING,
                    message="BLOCKED relation has no linked Issue explaining the block",
                    path=f"{path}/candidate_state",
                    related_ids=(relation.candidate_relation_id,),
                )
            )
    return findings


def _state_findings(graph: CandidateGraph) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    issue_rule_ids = {rule_id for issue in graph.issues for rule_id in issue.related_ids}
    for rule in graph.rules:
        if (
            rule.candidate_state is CandidateState.BLOCKED
            and rule.candidate_id not in issue_rule_ids
        ):
            findings.append(
                ValidationFinding(
                    code="STATE_BLOCKED_WITHOUT_ISSUE",
                    severity=FindingSeverity.WARNING,
                    message="BLOCKED rule has no linked Issue explaining the block",
                    path=f"/rules/{rule.candidate_id}/candidate_state",
                    related_ids=(rule.candidate_id,),
                )
            )
    for issue in graph.issues:
        blocking_on_proposed = [
            related
            for related in issue.related_ids
            if related
            in {
                rule.candidate_id
                for rule in graph.rules
                if rule.candidate_state is CandidateState.PROPOSED
            }
        ]
        if blocking_on_proposed and issue.severity.value == "BLOCKING":
            findings.append(
                ValidationFinding(
                    code="STATE_BLOCKING_ISSUE_ON_PROPOSED",
                    severity=FindingSeverity.INFO,
                    message=(
                        f"blocking Issue {issue.issue_id} qualifies PROPOSED "
                        f"candidate(s) {sorted(blocking_on_proposed)}; the conflict "
                        "remains reviewable"
                    ),
                    path=f"/issues/{issue.issue_id}",
                    related_ids=(issue.issue_id,),
                )
            )
    findings.append(
        ValidationFinding(
            code="STATE_NO_APPROVED_ARTIFACTS",
            severity=FindingSeverity.INFO,
            message="no candidate carries an approved state; no approved artifact exists",
            path="/",
        )
    )
    return findings


# --------------------------------------------------------------------------
# Topology


def _topology(
    graph: CandidateGraph, manifest: ProjectionManifest | None
) -> tuple[set[str], set[str], tuple[ComponentInfo, ...], tuple[CycleInfo, ...]]:
    adjacency: dict[str, list[str]] = {rule.candidate_id: [] for rule in graph.rules}
    for relation in graph.relations:
        if relation.relation_type in _SEQUENTIAL_TYPES:
            adjacency[relation.source_ref].extend(relation.target_refs)

    if manifest is not None:
        entry_points = {stage.rule_id for stage in manifest.stages}
    else:
        has_in = {target for values in adjacency.values() for target in values}
        entry_points = {rule_id for rule_id in adjacency if rule_id not in has_in}

    reachable: set[str] = set()
    frontier = sorted(entry_points)
    while frontier:
        current = frontier.pop(0)
        if current in reachable:
            continue
        reachable.add(current)
        frontier.extend(target for target in adjacency.get(current, ()) if target not in reachable)

    components = _disconnected_components(graph, adjacency, entry_points)
    cycles = _detect_cycles(graph, adjacency)
    terminals = {rule_id for rule_id in adjacency if not adjacency[rule_id]}
    return entry_points, terminals, components, cycles


def _disconnected_components(
    graph: CandidateGraph, adjacency: dict[str, list[str]], entry_points: set[str]
) -> tuple[ComponentInfo, ...]:
    sequential_ids = {
        rule_id
        for relation in graph.relations
        if relation.relation_type in _SEQUENTIAL_TYPES
        for rule_id in (relation.source_ref, *relation.target_refs)
    }
    components: list[ComponentInfo] = []
    component_id = 1
    for rule in sorted(graph.rules, key=lambda item: item.candidate_id):
        rule_id = rule.candidate_id
        if rule_id in sequential_ids:
            continue
        if rule_id in entry_points:
            classification = ComponentClassification.ENTRY_COMPONENT
            note = "declared stage root without sequential edges (projection anchor)"
        else:
            classification = ComponentClassification.ISOLATED_CONTEXT
            note = (
                "rule participates in no sequential relation; intentionally "
                "contextual/conflicting/blocked"
            )
        components.append(
            ComponentInfo(
                component_id=component_id,
                rule_ids=(rule_id,),
                classification=classification,
                note=note,
            )
        )
        component_id += 1
    # Sequential sub-components without any declared entry point.
    anchored = set(entry_points)
    reachable_from_anchors: set[str] = set()
    frontier = sorted(anchored)
    while frontier:
        current = frontier.pop(0)
        if current in reachable_from_anchors:
            continue
        reachable_from_anchors.add(current)
        frontier.extend(adjacency.get(current, ()))
    unreachable = sorted(sequential_ids - reachable_from_anchors)
    if unreachable:
        components.append(
            ComponentInfo(
                component_id=component_id,
                rule_ids=tuple(unreachable),
                classification=ComponentClassification.UNREACHABLE_PATHWAY,
                note=(
                    "sequential sub-component unreachable from any declared entry "
                    "point; inspect stage roots or relation anchors"
                ),
            )
        )
    return tuple(components)


def _detect_cycles(graph: CandidateGraph, adjacency: dict[str, list[str]]) -> tuple[CycleInfo, ...]:
    relation_by_pair: dict[tuple[str, str], str] = {}
    for relation in graph.relations:
        if relation.relation_type in _SEQUENTIAL_TYPES:
            for target in relation.target_refs:
                relation_by_pair[(relation.source_ref, target)] = relation.candidate_relation_id
    cycle_relations: list[str] = []
    for (source, target), relation_id in sorted(relation_by_pair.items()):
        if _can_reach(adjacency, target, source):
            cycle_relations.append(relation_id)
    if not cycle_relations:
        return ()
    involved_rules = sorted(
        {
            rule_id
            for relation in graph.relations
            if relation.candidate_relation_id in cycle_relations
            for rule_id in (relation.source_ref, *relation.target_refs)
        }
    )
    return (
        CycleInfo(
            relation_ids=tuple(sorted(cycle_relations)),
            rule_ids=tuple(involved_rules),
            note=(
                "cycle detected in sequential relations; classify as reassessment "
                "loop or incorrect relation during clinical review"
            ),
        ),
    )


def _can_reach(adjacency: dict[str, list[str]], start: str, goal: str) -> bool:
    seen: set[str] = set()
    frontier = [start]
    while frontier:
        current = frontier.pop()
        if current == goal:
            return True
        if current in seen:
            continue
        seen.add(current)
        frontier.extend(adjacency.get(current, ()))
    return False


def _topology_findings(
    graph: CandidateGraph,
    manifest: ProjectionManifest | None,
    entry_points: set[str],
    components: tuple[ComponentInfo, ...],
    cycles: tuple[CycleInfo, ...],
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    if manifest is not None:
        rule_ids = {rule.candidate_id for rule in graph.rules}
        unknown = [stage.rule_id for stage in manifest.stages if stage.rule_id not in rule_ids]
        for root in unknown:
            findings.append(
                ValidationFinding(
                    code="ENTRY_POINT_UNKNOWN_RULE",
                    severity=FindingSeverity.ERROR,
                    message=f"projection root references unknown rule {root!r}",
                    path=f"/entry_points/{root}",
                    related_ids=(root,),
                )
            )
        if manifest.protocol_version_id != graph.protocol_version_id:
            findings.append(
                ValidationFinding(
                    code="ENTRY_POINT_PROTOCOL_MISMATCH",
                    severity=FindingSeverity.ERROR,
                    message=(
                        f"manifest protocol {manifest.protocol_version_id!r} does not "
                        f"match graph protocol {graph.protocol_version_id!r}"
                    ),
                    path="/entry_points",
                )
            )
    for root in sorted(entry_points):
        findings.append(
            ValidationFinding(
                code="TOPOLOGY_ENTRY_POINT",
                severity=FindingSeverity.INFO,
                message=f"entry point: {root}",
                path=f"/entry_points/{root}",
                related_ids=(root,),
            )
        )
    for component in components:
        severity = (
            FindingSeverity.ERROR
            if component.classification is ComponentClassification.UNREACHABLE_PATHWAY
            and _component_expected_in_pathway(graph, component)
            else FindingSeverity.WARNING
        )
        findings.append(
            ValidationFinding(
                code="TOPOLOGY_DISCONNECTED_COMPONENT",
                severity=severity,
                message=(
                    f"disconnected component [{component.classification.value}]: "
                    f"{', '.join(component.rule_ids)} — {component.note}"
                ),
                path=f"/components/{component.component_id}",
                related_ids=component.rule_ids,
            )
        )
    for cycle in cycles:
        findings.append(
            ValidationFinding(
                code="TOPOLOGY_CYCLE_DETECTED",
                severity=FindingSeverity.WARNING,
                message=(
                    f"cycle detected via relations {', '.join(cycle.relation_ids)}; "
                    "classify as reassessment loop or incorrect relation"
                ),
                path="/cycles",
                related_ids=cycle.relation_ids,
            )
        )
    for relation in graph.relations:
        if relation.relation_type in _SEQUENTIAL_TYPES:
            findings.append(
                ValidationFinding(
                    code="RELATION_SEQUENTIAL_LISTED",
                    severity=FindingSeverity.INFO,
                    message=(
                        f"{relation.relation_type.value} {relation.source_ref} → "
                        f"{', '.join(relation.target_refs)}"
                    ),
                    path=f"/relations/{relation.candidate_relation_id}",
                    related_ids=(relation.candidate_relation_id,),
                )
            )
    return findings


def _component_expected_in_pathway(graph: CandidateGraph, component: ComponentInfo) -> bool:
    # No artifact metadata currently marks a component as "must be in the main
    # pathway" beyond declared stage roots, which are entry points themselves.
    return False


# --------------------------------------------------------------------------
# Projection parity and review packet


def _projection_findings(
    graph: CandidateGraph,
    manifest: ProjectionManifest | None,
    artifact_files: Mapping[str, Path] | None,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    if manifest is None:
        return findings
    try:
        rendered_html = render_review_tree_html(graph, manifest)
        rendered_svg = render_review_tree_svg(graph, manifest)
    except ValueError as exc:
        findings.append(
            ValidationFinding(
                code="PROJECTION_RENDER_FAILED",
                severity=FindingSeverity.ERROR,
                message=f"review projection cannot be generated: {exc}",
                path="/projection",
            )
        )
        return findings
    drawn_node_ids = _extract_ids(rendered_svg, "n-")
    drawn_edge_ids = _extract_ids(rendered_svg, "e-")
    if artifact_files and artifact_files.get("svg") is not None:
        svg_path = artifact_files["svg"]
        if svg_path.exists():
            committed_svg = svg_path.read_text(encoding="utf-8")
            drawn_node_ids |= _extract_ids(committed_svg, "n-")
            drawn_edge_ids |= _extract_ids(committed_svg, "e-")
    rule_ids = {rule.candidate_id for rule in graph.rules}
    sequential_ids = {
        relation.candidate_relation_id
        for relation in graph.relations
        if relation.relation_type in _SEQUENTIAL_TYPES
    }
    for node_id in sorted(drawn_node_ids - rule_ids):
        findings.append(
            ValidationFinding(
                code="PROJECTION_NODE_UNKNOWN",
                severity=FindingSeverity.ERROR,
                message=f"visual node {node_id!r} maps to no canonical rule",
                path=f"/projection/nodes/{node_id}",
            )
        )
    for edge_id in sorted(drawn_edge_ids - sequential_ids):
        findings.append(
            ValidationFinding(
                code="PROJECTION_EDGE_UNKNOWN",
                severity=FindingSeverity.ERROR,
                message=f"visual edge {edge_id!r} maps to no canonical sequential relation",
                path=f"/projection/edges/{edge_id}",
            )
        )
    contextual_ids = {
        relation.candidate_relation_id
        for relation in graph.relations
        if relation.relation_type not in _SEQUENTIAL_TYPES
    }
    for edge_id in sorted(drawn_edge_ids & contextual_ids):
        findings.append(
            ValidationFinding(
                code="PROJECTION_CONTEXTUAL_DRAWN_AS_SEQUENCE",
                severity=FindingSeverity.ERROR,
                message=(
                    f"contextual relation {edge_id!r} is drawn as a pathway arrow; "
                    "contextual relations must never become sequence"
                ),
                path=f"/projection/edges/{edge_id}",
            )
        )
    if artifact_files:
        html_file = artifact_files.get("html")
        svg_file = artifact_files.get("svg")
        if html_file is not None:
            _compare_artifact(findings, rendered_html, html_file, "/projection/artifacts/html")
        if svg_file is not None:
            _compare_artifact(findings, rendered_svg, svg_file, "/projection/artifacts/svg")
    return findings


def _extract_ids(text: str, prefix: str) -> set[str]:
    result: set[str] = set()
    marker = f'id="{prefix}'
    position = 0
    while True:
        start = text.find(marker, position)
        if start == -1:
            return result
        end = text.find('"', start + len(marker))
        if end == -1:
            return result
        result.add(text[start + len(marker) : end])
        position = end + 1


def _compare_artifact(
    findings: list[ValidationFinding],
    rendered: str,
    path: Path,
    finding_path: str,
) -> None:
    if not path.exists():
        findings.append(
            ValidationFinding(
                code="PROJECTION_ARTIFACT_MISSING",
                severity=FindingSeverity.ERROR,
                message=f"review artifact {path.name} does not exist",
                path=finding_path,
            )
        )
        return
    committed = path.read_text(encoding="utf-8")
    if not committed.strip():
        findings.append(
            ValidationFinding(
                code="PROJECTION_ARTIFACT_EMPTY",
                severity=FindingSeverity.ERROR,
                message=f"review artifact {path.name} is empty",
                path=finding_path,
            )
        )
        return
    if committed != rendered:
        findings.append(
            ValidationFinding(
                code="PROJECTION_PARITY_MISMATCH",
                severity=FindingSeverity.ERROR,
                message=(
                    f"review artifact {path.name} does not match the canonical "
                    "projection; regenerate or fix the artifact"
                ),
                path=finding_path,
            )
        )


def _review_packet_findings(
    graph: CandidateGraph,
    manifest: ProjectionManifest | None,
    artifact_files: Mapping[str, Path] | None,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    if artifact_files is None:
        return findings
    questions = artifact_files.get("questions")
    if questions is not None and (
        not questions.exists() or not questions.read_text(encoding="utf-8").strip()
    ):
        findings.append(
            ValidationFinding(
                code="REVIEW_QUESTIONS_MISSING",
                severity=FindingSeverity.ERROR,
                message="clinical review questions artifact is missing or empty",
                path="/review_packet/questions",
            )
        )
    html_path = artifact_files.get("html")
    if html_path is not None and html_path.exists():
        text = html_path.read_text(encoding="utf-8")
        if graph.protocol_version_id not in text:
            findings.append(
                ValidationFinding(
                    code="REVIEW_ARTIFACT_PROTOCOL_IDENTITY_MISSING",
                    severity=FindingSeverity.ERROR,
                    message="review HTML does not carry the protocol identity",
                    path="/review_packet/html",
                )
            )
        if "NOT CLINICALLY APPROVED" not in text:
            findings.append(
                ValidationFinding(
                    code="REVIEW_ARTIFACT_DISCLAIMER_MISSING",
                    severity=FindingSeverity.ERROR,
                    message="review HTML lacks the not-clinically-approved disclaimer",
                    path="/review_packet/html",
                )
            )
        missing_issues = [issue.issue_id for issue in graph.issues if issue.issue_id not in text]
        if missing_issues:
            findings.append(
                ValidationFinding(
                    code="REVIEW_ARTIFACT_ISSUE_INVISIBLE",
                    severity=FindingSeverity.WARNING,
                    message=f"review HTML does not expose Issues: {sorted(missing_issues)}",
                    path="/review_packet/html",
                    related_ids=tuple(sorted(missing_issues)),
                )
            )
        blocked_rules = sum(rule.candidate_state is CandidateState.BLOCKED for rule in graph.rules)
        blocked_relations = sum(
            relation.candidate_state is CandidateState.BLOCKED for relation in graph.relations
        )
        if blocked_rules + blocked_relations > 0 and "BLOCKED" not in text:
            findings.append(
                ValidationFinding(
                    code="REVIEW_ARTIFACT_BLOCKED_INVISIBLE",
                    severity=FindingSeverity.WARNING,
                    message="review HTML does not visibly mark blocked candidates",
                    path="/review_packet/html",
                )
            )
    return findings


# --------------------------------------------------------------------------
# Status aggregation


def _status(findings: list[ValidationFinding], code_prefix: str) -> str:
    failed = any(
        finding.code.startswith(code_prefix) and finding.severity is FindingSeverity.ERROR
        for finding in findings
    )
    return "FAILED" if failed else "PASSED"


def _parity_status(
    findings: list[ValidationFinding], artifact_files: Mapping[str, Path] | None
) -> str:
    if artifact_files is None:
        return "NOT_APPLICABLE"
    failed = any(
        finding.code.startswith("PROJECTION") and finding.severity is FindingSeverity.ERROR
        for finding in findings
    )
    return "FAILED" if failed else "PASSED"


def _review_readiness(
    findings: list[ValidationFinding],
    artifact_files: Mapping[str, Path] | None,
    parity_status: str,
) -> str:
    errors = [finding for finding in findings if finding.severity is FindingSeverity.ERROR]
    approved_states = any(
        finding.code == "STATE_NO_APPROVED_ARTIFACTS" and finding.severity is FindingSeverity.ERROR
        for finding in findings
    )
    if errors or approved_states:
        return NOT_READY_FOR_CLINICAL_REVIEW
    if artifact_files is None or parity_status != "PASSED":
        return NOT_READY_FOR_CLINICAL_REVIEW
    return READY_FOR_CLINICAL_REVIEW


def _graph_content_hash(graph: CandidateGraph) -> str:
    return hashlib.sha256(dump_candidate_graph(graph).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Deterministic report serialization


def report_to_dict(report: CandidateStructureReport) -> dict[str, Any]:
    """Convert a structural report into deterministic JSON-safe primitives."""
    return {
        "protocol_version_id": report.protocol_version_id,
        "graph_id": report.graph_id,
        "rule_count": report.rule_count,
        "relation_count": report.relation_count,
        "issue_count": report.issue_count,
        "blocked_rule_count": report.blocked_rule_count,
        "blocked_relation_count": report.blocked_relation_count,
        "error_count": report.error_count,
        "warning_count": report.warning_count,
        "info_count": report.info_count,
        "entry_points": sorted(report.entry_points),
        "terminal_nodes": sorted(report.terminal_nodes),
        "disconnected_components": [
            {
                "component_id": component.component_id,
                "rule_ids": sorted(component.rule_ids),
                "classification": component.classification.value,
                "note": component.note,
            }
            for component in sorted(
                report.disconnected_components, key=lambda item: item.component_id
            )
        ],
        "cycles": [
            {
                "relation_ids": sorted(cycle.relation_ids),
                "rule_ids": sorted(cycle.rule_ids),
                "note": cycle.note,
            }
            for cycle in report.cycles
        ],
        "provenance_status": report.provenance_status,
        "projection_parity_status": report.projection_parity_status,
        "review_readiness": report.review_readiness,
        "graph_content_hash": report.graph_content_hash,
        "findings": [
            {
                "code": finding.code,
                "severity": finding.severity.value,
                "message": finding.message,
                **({"path": finding.path} if finding.path is not None else {}),
                **({"related_ids": sorted(finding.related_ids)} if finding.related_ids else {}),
            }
            for finding in sorted(report.findings, key=finding_sort_key)
        ],
    }


def dump_candidate_structure_report(report: CandidateStructureReport) -> str:
    """Serialize a structural report deterministically."""
    return (
        json.dumps(
            report_to_dict(report),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
