"""Deterministic JSON serialization for reviewable Candidate Graph artifacts."""

# ruff: noqa: TRY004

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from cpg_tree.candidates.actions import ActionSpec
from cpg_tree.candidates.enums import (
    CandidateState,
    EvidenceClass,
    IssueCategory,
    IssueSeverity,
    IssueStatus,
    ObservationKind,
    RelationType,
)
from cpg_tree.candidates.evidence import EvidenceBinding
from cpg_tree.candidates.graph import (
    CandidateGraph,
    FindingSeverity,
    StructuralFinding,
)
from cpg_tree.candidates.issues import Issue
from cpg_tree.candidates.observations import Observation
from cpg_tree.candidates.relations import CandidateRelation
from cpg_tree.candidates.rules import CandidateRule
from cpg_tree.candidates.variables import VariableSpec
from cpg_tree.extraction.spans import SourceSpan, SpanQualityFlag, SpanRepresentation
from cpg_tree.knowledge.conditions import Condition, LogicalExpression, LogicalOperand
from cpg_tree.knowledge.enums import (
    ActionType,
    ComparisonOperator,
    ConditionKind,
    LogicalOperator,
    TemporalOperator,
    VariableType,
)
from cpg_tree.llm.attempts import AttemptStatus, GenerationAttempt


def candidate_graph_to_dict(graph: CandidateGraph) -> dict[str, Any]:
    """Convert a Candidate Graph to JSON-safe explicit primitives."""
    value = _jsonable(graph)
    if not isinstance(value, dict):
        raise TypeError("CandidateGraph serialization root must be a mapping")
    return value


def dump_candidate_graph(graph: CandidateGraph) -> str:
    """Serialize a Candidate Graph deterministically for review."""
    return (
        json.dumps(
            candidate_graph_to_dict(graph),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def load_candidate_graph(text: str) -> CandidateGraph:
    """Load the deterministic JSON representation back into domain contracts."""
    raw = json.loads(text)
    data = _mapping(raw, "CandidateGraph")
    return CandidateGraph(
        graph_id=data["graph_id"],
        generation_run_id=data["generation_run_id"],
        protocol_version_id=data["protocol_version_id"],
        document_id=data["document_id"],
        extraction_run_id=data["extraction_run_id"],
        observations=tuple(_observation(item) for item in _items(data, "observations")),
        variables=tuple(_variable(item) for item in _items(data, "variables")),
        rules=tuple(_rule(item) for item in _items(data, "rules")),
        relations=tuple(_relation(item) for item in _items(data, "relations")),
        issues=tuple(_issue(item) for item in _items(data, "issues")),
        source_spans=tuple(_source_span(item) for item in _items(data, "source_spans")),
        attempts=tuple(_attempt(item) for item in _items(data, "attempts")),
        findings=tuple(_finding(item) for item in _items(data, "findings")),
        schema_version=data["schema_version"],
    )


def write_candidate_graph(graph: CandidateGraph, path: Path) -> Path:
    """Write a reviewable candidate artifact; callers choose an ignored run path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(dump_candidate_graph(graph))
    return path


def dump_generation_attempts(attempts: tuple[GenerationAttempt, ...]) -> str:
    """Serialize quarantined attempts when no Candidate Graph can be produced."""
    return (
        json.dumps(
            {"status": "QUARANTINED", "attempts": _jsonable(attempts)},
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def write_generation_quarantine(attempts: tuple[GenerationAttempt, ...], path: Path) -> Path:
    """Persist a failed run without overwriting prior audit history."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(dump_generation_attempts(attempts))
    return path


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _jsonable(getattr(value, item.name))
            for item in fields(value)
            if getattr(value, item.name) is not None
        }
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _binding(raw: object) -> EvidenceBinding:
    data = _mapping(raw, "EvidenceBinding")
    return EvidenceBinding(
        claim_path=data["claim_path"],
        evidence_class=EvidenceClass(data["evidence_class"]),
        source_span_refs=tuple(data.get("source_span_refs", ())),
        exact_quote=data.get("exact_quote"),
        transformation=data.get("transformation"),
    )


def _expression(raw: object) -> LogicalOperand:
    data = _mapping(raw, "ClinicalExpression")
    if "kind" in data:
        return Condition(
            kind=ConditionKind(data["kind"]),
            variable_ref=data["variable_ref"],
            operator=(
                ComparisonOperator(data["operator"]) if data.get("operator") is not None else None
            ),
            operand=data.get("operand"),
            values=tuple(data["values"]) if data.get("values") is not None else None,
            expected=data.get("expected"),
            temporal_operator=(
                TemporalOperator(data["temporal_operator"])
                if data.get("temporal_operator") is not None
                else None
            ),
            duration_value=data.get("duration_value"),
            duration_unit=data.get("duration_unit"),
        )
    return LogicalExpression(
        operator=LogicalOperator(data["operator"]),
        operands=tuple(_expression(item) for item in _items(data, "operands")),
        threshold=data.get("threshold"),
    )


def _observation(raw: object) -> Observation:
    data = _mapping(raw, "Observation")
    return Observation(
        observation_id=data["observation_id"],
        kind=ObservationKind(data["kind"]),
        span_refs=tuple(data["span_refs"]),
        exact_quote=data.get("exact_quote"),
        subject_text=data.get("subject_text"),
        predicate_text=data.get("predicate_text"),
        object_text=data.get("object_text"),
        negated=data.get("negated", False),
        generation_attempt_id=data.get("generation_attempt_id"),
        issue_ids=tuple(data.get("issue_ids", ())),
    )


def _variable(raw: object) -> VariableSpec:
    data = _mapping(raw, "VariableSpec")
    allowed = data.get("allowed_values")
    return VariableSpec(
        variable_id=data["variable_id"],
        label=data["label"],
        value_type=VariableType(data["value_type"]),
        unit=data.get("unit"),
        allowed_values=tuple(allowed) if allowed is not None else None,
        evidence_bindings=tuple(_binding(item) for item in _items(data, "evidence_bindings")),
    )


def _action(raw: object) -> ActionSpec:
    data = _mapping(raw, "ActionSpec")
    return ActionSpec(
        action_id=data["action_id"],
        action_type=ActionType(data["action_type"]),
        target_text=data.get("target_text"),
        dose_value=data.get("dose_value"),
        dose_unit=data.get("dose_unit"),
        route=data.get("route"),
        frequency=data.get("frequency"),
        duration=data.get("duration"),
        timing=data.get("timing"),
        alternative_group=data.get("alternative_group"),
        qualifiers=tuple(data.get("qualifiers", ())),
        evidence_bindings=tuple(_binding(item) for item in _items(data, "evidence_bindings")),
    )


def _rule(raw: object) -> CandidateRule:
    data = _mapping(raw, "CandidateRule")
    applies_to = data.get("applies_to")
    return CandidateRule(
        candidate_id=data["candidate_id"],
        revision=data["revision"],
        protocol_version_id=data["protocol_version_id"],
        condition=_expression(data["condition"]),
        evidence_class=EvidenceClass(data["evidence_class"]),
        observation_refs=tuple(data.get("observation_refs", ())),
        applies_to=_expression(applies_to) if applies_to is not None else None,
        actions=tuple(_action(item) for item in _items(data, "actions")),
        exceptions=tuple(_expression(item) for item in _items(data, "exceptions")),
        modality=data.get("modality"),
        statement_kind=data.get("statement_kind"),
        evidence_bindings=tuple(_binding(item) for item in _items(data, "evidence_bindings")),
        ambiguity_flags=tuple(data.get("ambiguity_flags", ())),
        candidate_state=CandidateState(data["candidate_state"]),
        generation_attempt_id=data.get("generation_attempt_id"),
        supersedes_candidate_id=data.get("supersedes_candidate_id"),
        content_hash=data.get("content_hash"),
    )


def _relation(raw: object) -> CandidateRelation:
    data = _mapping(raw, "CandidateRelation")
    return CandidateRelation(
        candidate_relation_id=data["candidate_relation_id"],
        revision=data["revision"],
        source_ref=data["source_ref"],
        target_refs=tuple(data["target_refs"]),
        relation_type=RelationType(data["relation_type"]),
        evidence_class=EvidenceClass(data["evidence_class"]),
        observation_refs=tuple(data.get("observation_refs", ())),
        branch_label=data.get("branch_label"),
        temporal_qualifier=data.get("temporal_qualifier"),
        evidence_bindings=tuple(_binding(item) for item in _items(data, "evidence_bindings")),
        candidate_state=CandidateState(data["candidate_state"]),
        generation_attempt_id=data.get("generation_attempt_id"),
        content_hash=data.get("content_hash"),
    )


def _issue(raw: object) -> Issue:
    data = _mapping(raw, "Issue")
    return Issue(
        issue_id=data["issue_id"],
        category=IssueCategory(data["category"]),
        severity=IssueSeverity(data["severity"]),
        description=data["description"],
        related_ids=tuple(data.get("related_ids", ())),
        status=IssueStatus(data["status"]),
        generation_attempt_id=data.get("generation_attempt_id"),
    )


def _source_span(raw: object) -> SourceSpan:
    data = _mapping(raw, "SourceSpan")
    bbox = data.get("bbox")
    return SourceSpan(
        span_id=data["span_id"],
        document_id=data["document_id"],
        extraction_run_id=data["extraction_run_id"],
        page=data["page"],
        representation=SpanRepresentation(data["representation"]),
        extraction_method=data["extraction_method"],
        section_path=data.get("section_path"),
        extracted_text_exact=data.get("extracted_text_exact"),
        normalized_text=data.get("normalized_text"),
        text_sha256=data.get("text_sha256"),
        char_start=data.get("char_start"),
        char_end=data.get("char_end"),
        bbox=tuple(bbox) if bbox is not None else None,
        table_locator=data.get("table_locator"),
        page_image_sha256=data.get("page_image_sha256"),
        quality_flags=tuple(SpanQualityFlag(item) for item in data.get("quality_flags", ())),
    )


def _attempt(raw: object) -> GenerationAttempt:
    data = _mapping(raw, "GenerationAttempt")
    return GenerationAttempt(
        attempt_id=data["attempt_id"],
        request_id=data["request_id"],
        parent_attempt_id=data.get("parent_attempt_id"),
        provider=data["provider"],
        model=data["model"],
        model_version=data.get("model_version"),
        prompt_version=data["prompt_version"],
        schema_version=data["schema_version"],
        temperature=data["temperature"],
        reasoning_effort=data.get("reasoning_effort"),
        input_span_ids=tuple(data["input_span_ids"]),
        input_hash=data["input_hash"],
        raw_response=data.get("raw_response"),
        raw_response_hash=data.get("raw_response_hash"),
        status=AttemptStatus(data["status"]),
        validation_errors=tuple(data["validation_errors"]),
        started_at=data["started_at"],
        completed_at=data["completed_at"],
        usage=tuple(tuple(item) for item in data.get("usage", ())),
    )


def _finding(raw: object) -> StructuralFinding:
    data = _mapping(raw, "StructuralFinding")
    return StructuralFinding(
        code=data["code"],
        severity=FindingSeverity(data["severity"]),
        path=data["path"],
        message=data["message"],
    )


def _mapping(raw: object, label: str) -> Mapping[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return raw


def _items(data: Mapping[str, Any], key: str) -> tuple[object, ...]:
    raw = data.get(key, ())
    if not isinstance(raw, list):
        raise ValueError(f"{key} must be a list")
    return tuple(raw)
