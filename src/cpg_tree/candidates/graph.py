"""Candidate Graph aggregate assembled only from LLM-proposed candidate artifacts."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from cpg_tree.candidates.enums import EvidenceClass, RelationType
from cpg_tree.candidates.evidence import EvidenceBinding
from cpg_tree.candidates.issues import Issue
from cpg_tree.candidates.observations import Observation
from cpg_tree.candidates.relations import CandidateRelation
from cpg_tree.candidates.rules import CandidateRule
from cpg_tree.candidates.variables import VariableSpec
from cpg_tree.extraction.spans import SourceSpan
from cpg_tree.knowledge._validation import validate_identifier
from cpg_tree.llm.attempts import GenerationAttempt

CANDIDATE_GRAPH_SCHEMA_VERSION = "candidate-graph-v1"


class FindingSeverity(StrEnum):
    """Technical severity of one deterministic structural finding."""

    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass(frozen=True, slots=True)
class StructuralFinding:
    """A reproducible structural finding, never a clinical adjudication."""

    code: str
    severity: FindingSeverity
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class CandidateGraph:
    """Typed candidate aggregate; it does not manufacture generic graph nodes."""

    graph_id: str
    generation_run_id: str
    protocol_version_id: str
    document_id: str
    extraction_run_id: str
    observations: tuple[Observation, ...]
    variables: tuple[VariableSpec, ...]
    rules: tuple[CandidateRule, ...]
    relations: tuple[CandidateRelation, ...]
    issues: tuple[Issue, ...]
    source_spans: tuple[SourceSpan, ...]
    attempts: tuple[GenerationAttempt, ...]
    findings: tuple[StructuralFinding, ...] = ()
    schema_version: str = CANDIDATE_GRAPH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for value, label in (
            (self.graph_id, "CandidateGraph.graph_id"),
            (self.generation_run_id, "CandidateGraph.generation_run_id"),
            (self.protocol_version_id, "CandidateGraph.protocol_version_id"),
            (self.document_id, "CandidateGraph.document_id"),
            (self.extraction_run_id, "CandidateGraph.extraction_run_id"),
        ):
            validate_identifier(value, label)
        if self.schema_version != CANDIDATE_GRAPH_SCHEMA_VERSION:
            raise ValueError(f"unsupported CandidateGraph schema {self.schema_version!r}")
        self._validate_ids_and_references()

    def _validate_ids_and_references(self) -> None:
        ids = _collect_graph_ids(self)
        all_ids = _require_distinct_entity_ids(ids)
        _validate_observation_refs(self, ids)
        _validate_rule_refs(self, ids)
        _validate_relation_refs(self, ids)
        for issue in self.issues:
            _require_subset(
                issue.related_ids,
                all_ids | {self.document_id, self.extraction_run_id},
                "issue related ids",
            )
            _require_optional(issue.generation_attempt_id, ids.attempts, "issue attempt")
        _require_unique_relation_content(self.relations)


@dataclass(frozen=True, slots=True)
class _GraphIds:
    observations: set[str]
    variables: set[str]
    rules: set[str]
    actions: set[str]
    relations: set[str]
    issues: set[str]
    spans: set[str]
    attempts: set[str]


def _collect_graph_ids(graph: CandidateGraph) -> _GraphIds:
    return _GraphIds(
        observations=_unique_ids(
            (item.observation_id for item in graph.observations), "observation"
        ),
        variables=_unique_ids((item.variable_id for item in graph.variables), "variable"),
        rules=_unique_ids((item.candidate_id for item in graph.rules), "candidate rule"),
        actions=_unique_ids(
            (action.action_id for rule in graph.rules for action in rule.actions), "action"
        ),
        relations=_unique_ids(
            (item.candidate_relation_id for item in graph.relations), "candidate relation"
        ),
        issues=_unique_ids((item.issue_id for item in graph.issues), "issue"),
        spans=_unique_ids((item.span_id for item in graph.source_spans), "source span"),
        attempts=_unique_ids((item.attempt_id for item in graph.attempts), "attempt"),
    )


def _require_distinct_entity_ids(ids: _GraphIds) -> set[str]:
    all_ids: set[str] = set()
    for group in (
        ids.observations,
        ids.variables,
        ids.rules,
        ids.actions,
        ids.relations,
        ids.issues,
        ids.spans,
    ):
        overlap = all_ids & group
        if overlap:
            raise ValueError(f"CandidateGraph ids collide across entity types: {sorted(overlap)}")
        all_ids.update(group)
    return all_ids


def _validate_observation_refs(graph: CandidateGraph, ids: _GraphIds) -> None:
    for observation in graph.observations:
        _require_subset(observation.span_refs, ids.spans, "observation span refs")
        _require_subset(observation.issue_ids, ids.issues, "observation issue refs")
        _require_optional(observation.generation_attempt_id, ids.attempts, "observation attempt")


def _validate_rule_refs(graph: CandidateGraph, ids: _GraphIds) -> None:
    for rule in graph.rules:
        _require_subset(rule.observation_refs, ids.observations, "rule observation refs")
        _require_optional(rule.generation_attempt_id, ids.attempts, "rule attempt")
        _validate_bindings(rule.evidence_bindings, ids.spans)
        for action in rule.actions:
            _validate_bindings(action.evidence_bindings, ids.spans)
        _require_subset(_expression_variable_refs(rule.condition), ids.variables, "rule variables")
        if rule.applies_to is not None:
            _require_subset(
                _expression_variable_refs(rule.applies_to),
                ids.variables,
                "applicability variables",
            )
        for exception in rule.exceptions:
            _require_subset(
                _expression_variable_refs(exception), ids.variables, "exception variables"
            )
    for variable in graph.variables:
        _validate_bindings(variable.evidence_bindings, ids.spans)


def _validate_relation_refs(graph: CandidateGraph, ids: _GraphIds) -> None:
    endpoint_ids = ids.rules | ids.actions
    for relation in graph.relations:
        _require_subset(
            (relation.source_ref, *relation.target_refs), endpoint_ids, "relation endpoints"
        )
        _require_subset(relation.observation_refs, ids.observations, "relation observation refs")
        _require_optional(relation.generation_attempt_id, ids.attempts, "relation attempt")
        _validate_bindings(relation.evidence_bindings, ids.spans)


def _require_unique_relation_content(relations: tuple[CandidateRelation, ...]) -> None:
    content_hashes: set[str] = set()
    for relation in relations:
        if relation.content_hash is None:
            raise ValueError("CandidateRelation content hash must be populated")
        if relation.content_hash in content_hashes:
            raise ValueError("CandidateGraph contains duplicate relation content")
        content_hashes.add(relation.content_hash)


def validate_candidate_graph(graph: CandidateGraph) -> tuple[StructuralFinding, ...]:
    """Report structural anomalies without changing or clinically interpreting the graph."""
    findings: list[StructuralFinding] = []
    findings.extend(_missing_evidence_findings(graph))
    sequential_refs = _relation_findings(graph, findings)
    findings.extend(_disconnected_rule_findings(graph, sequential_refs))
    return tuple(findings)


def _missing_evidence_findings(graph: CandidateGraph) -> list[StructuralFinding]:
    findings: list[StructuralFinding] = []
    for index, variable in enumerate(graph.variables):
        if not variable.evidence_bindings:
            findings.append(
                StructuralFinding(
                    code="VARIABLE_EVIDENCE_BINDING_MISSING",
                    severity=FindingSeverity.ERROR,
                    path=f"/variables/{index}/evidence_bindings",
                    message="VariableSpec has no field-level evidence binding.",
                )
            )
    for index, rule in enumerate(graph.rules):
        if not rule.evidence_bindings:
            findings.append(
                StructuralFinding(
                    code="RULE_EVIDENCE_BINDING_MISSING",
                    severity=FindingSeverity.ERROR,
                    path=f"/rules/{index}/evidence_bindings",
                    message="CandidateRule has no field-level evidence binding.",
                )
            )
        for action_index, action in enumerate(rule.actions):
            if not action.evidence_bindings:
                findings.append(
                    StructuralFinding(
                        code="ACTION_EVIDENCE_BINDING_MISSING",
                        severity=FindingSeverity.ERROR,
                        path=f"/rules/{index}/actions/{action_index}/evidence_bindings",
                        message="ActionSpec has no field-level evidence binding.",
                    )
                )
    return findings


def _relation_findings(graph: CandidateGraph, findings: list[StructuralFinding]) -> set[str]:
    sequential_refs: set[str] = set()
    for index, relation in enumerate(graph.relations):
        if not relation.evidence_bindings:
            findings.append(
                StructuralFinding(
                    code="RELATION_EVIDENCE_BINDING_MISSING",
                    severity=FindingSeverity.ERROR,
                    path=f"/relations/{index}/evidence_bindings",
                    message="CandidateRelation has no field-level evidence binding.",
                )
            )
        if relation.relation_type in {RelationType.FLOW, RelationType.BRANCH}:
            sequential_refs.add(relation.source_ref)
            sequential_refs.update(relation.target_refs)
            if relation.evidence_class in {EvidenceClass.INFERRED, EvidenceClass.UNRESOLVED}:
                findings.append(
                    StructuralFinding(
                        code="SEQUENTIAL_RELATION_EVIDENCE_UNRESOLVED",
                        severity=FindingSeverity.ERROR,
                        path=f"/relations/{index}/evidence_class",
                        message="FLOW/BRANCH cannot silently rely on inferred or unresolved evidence.",
                    )
                )
    return sequential_refs


def _disconnected_rule_findings(
    graph: CandidateGraph, sequential_refs: set[str]
) -> list[StructuralFinding]:
    findings: list[StructuralFinding] = []
    for index, rule in enumerate(graph.rules):
        if rule.candidate_id not in sequential_refs and len(graph.rules) > 1:
            findings.append(
                StructuralFinding(
                    code="RULE_DISCONNECTED_FROM_SEQUENTIAL_GRAPH",
                    severity=FindingSeverity.WARNING,
                    path=f"/rules/{index}",
                    message="Rule has no LLM-proposed FLOW or BRANCH relation; no edge was invented.",
                )
            )
    return findings


def _unique_ids(values: Iterable[str], label: str) -> set[str]:
    result: set[str] = set()
    for value in values:
        if value in result:
            raise ValueError(f"duplicate {label} id {value!r}")
        result.add(value)
    return result


def _require_subset(values: tuple[str, ...], known: set[str], label: str) -> None:
    unknown = set(values) - known
    if unknown:
        raise ValueError(f"unknown {label}: {sorted(unknown)}")


def _require_optional(value: str | None, known: set[str], label: str) -> None:
    if value is not None and value not in known:
        raise ValueError(f"unknown {label}: {value!r}")


def _validate_bindings(bindings: tuple[EvidenceBinding, ...], span_ids: set[str]) -> None:
    for binding in bindings:
        _require_subset(binding.source_span_refs, span_ids, "evidence span refs")


def _expression_variable_refs(expression: object) -> tuple[str, ...]:
    variable_ref = getattr(expression, "variable_ref", None)
    if isinstance(variable_ref, str):
        return (variable_ref,)
    operands = getattr(expression, "operands", ())
    return tuple(ref for operand in operands for ref in _expression_variable_refs(operand))
