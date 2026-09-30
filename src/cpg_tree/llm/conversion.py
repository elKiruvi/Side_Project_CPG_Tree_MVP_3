"""Strict conversion from untrusted LLM wire batches to candidate domain models."""

from __future__ import annotations

from collections.abc import Iterable

from cpg_tree.candidates import (
    ActionSpec,
    CandidateRelation,
    CandidateRule,
    EvidenceBinding,
    EvidenceClass,
    Issue,
    IssueCategory,
    IssueSeverity,
    Observation,
    ObservationKind,
    RelationType,
    VariableSpec,
)
from cpg_tree.candidates.expressions import ClinicalExpression
from cpg_tree.extraction.document import DocumentMap
from cpg_tree.knowledge.conditions import Condition, LogicalExpression
from cpg_tree.knowledge.enums import (
    ActionType,
    ComparisonOperator,
    ConditionKind,
    LogicalOperator,
    TemporalOperator,
    VariableType,
)
from cpg_tree.llm.schemas import (
    ActionWire,
    BatchIssueWire,
    BatchOutcome,
    CandidateRelationBatch,
    CandidateRelationItem,
    CandidateRuleBatch,
    CandidateRuleItem,
    EvidenceBindingWire,
    ObservationBatch,
    VariableWire,
    WireComparison,
    WireExpression,
    WireFlag,
    WireLogical,
    WireMembership,
    WireTemporal,
)


def validate_observation_batch(batch: ObservationBatch, document_map: DocumentMap) -> None:
    """Reject invented span ids, unsupported quotes, and duplicate identifiers."""
    _require_usable_outcome(batch.outcome)
    _require_unique((item.observation_id for item in batch.items), "observation ids")
    _require_unique((item.issue_id for item in batch.issues), "issue ids")
    issue_ids = {item.issue_id for item in batch.issues}
    for item in batch.items:
        _validate_span_refs(item.span_refs, document_map)
        if item.exact_quote is None:
            raise ValueError("observations require an exact_quote from their SourceSpans")
        _validate_quote(item.exact_quote, item.span_refs, document_map)
        unknown_issues = set(item.issue_ids) - issue_ids
        if unknown_issues:
            raise ValueError(f"observation references unknown issue ids: {sorted(unknown_issues)}")
    for issue in batch.issues:
        _validate_issue_related_ids(
            issue, document_map, {item.observation_id for item in batch.items}
        )
    observations_from_batch(batch, generation_attempt_id="attempt-validation")


def observations_from_batch(
    batch: ObservationBatch, *, generation_attempt_id: str
) -> tuple[tuple[Observation, ...], tuple[Issue, ...]]:
    """Convert one already validated observation batch."""
    observations = tuple(
        Observation(
            observation_id=item.observation_id,
            kind=ObservationKind(item.kind),
            span_refs=item.span_refs,
            exact_quote=item.exact_quote,
            subject_text=item.subject_text,
            predicate_text=item.predicate_text,
            object_text=item.object_text,
            negated=item.negated,
            generation_attempt_id=generation_attempt_id,
            issue_ids=item.issue_ids,
        )
        for item in batch.items
    )
    return observations, tuple(
        _issue_from_wire(issue, generation_attempt_id) for issue in batch.issues
    )


def validate_rule_batch(
    batch: CandidateRuleBatch,
    document_map: DocumentMap,
    observation_ids: set[str],
    protocol_version_id: str,
) -> None:
    """Reject unsupported rule evidence and unknown observation references."""
    _require_usable_outcome(batch.outcome)
    _require_unique((item.candidate_id for item in batch.items), "candidate rule ids")
    _require_unique((item.variable_id for item in batch.variables), "variable ids")
    _require_unique((item.issue_id for item in batch.issues), "issue ids")
    action_ids: list[str] = []
    candidate_ids = {item.candidate_id for item in batch.items}
    variable_ids = {item.variable_id for item in batch.variables}
    variable_types = {item.variable_id: item.value_type for item in batch.variables}
    _validate_variable_wires(batch.variables, document_map)
    for item in batch.items:
        action_ids.extend(
            _validate_rule_item(item, document_map, observation_ids, variable_ids, variable_types)
        )
    _require_unique(action_ids, "action ids")
    known = candidate_ids | set(action_ids) | observation_ids | variable_ids
    for issue in batch.issues:
        _validate_issue_related_ids(issue, document_map, known)
    rules_from_batch(
        batch,
        protocol_version_id=protocol_version_id,
        generation_attempt_id="attempt-validation",
    )


def _validate_variable_wires(
    variables: tuple[VariableWire, ...], document_map: DocumentMap
) -> None:
    for variable in variables:
        _validate_bindings(
            variable.evidence_bindings,
            document_map,
            claim_root=variable.model_dump(mode="json"),
        )
        _require_binding_coverage(
            variable.evidence_bindings,
            _variable_claim_paths(variable),
            f"variable {variable.variable_id!r}",
        )


def _validate_rule_item(
    item: CandidateRuleItem,
    document_map: DocumentMap,
    observation_ids: set[str],
    variable_ids: set[str],
    variable_types: dict[str, str],
) -> tuple[str, ...]:
    unknown = set(item.observation_refs) - observation_ids
    if unknown:
        raise ValueError(f"candidate rule references unknown observations: {sorted(unknown)}")
    _validate_bindings(
        item.evidence_bindings, document_map, claim_root=item.model_dump(mode="json")
    )
    _require_binding_coverage(
        item.evidence_bindings,
        _rule_claim_paths(item),
        f"candidate rule {item.candidate_id!r}",
    )
    for action in item.actions:
        _validate_bindings(
            action.evidence_bindings,
            document_map,
            claim_root=action.model_dump(mode="json"),
        )
        _require_binding_coverage(
            action.evidence_bindings,
            _action_claim_paths(action),
            f"action {action.action_id!r}",
        )
    expressions = (item.condition, *(item.exceptions))
    if item.applies_to is not None:
        expressions = (*expressions, item.applies_to)
    unknown_variables = set().union(*(_wire_variable_refs(value) for value in expressions))
    unknown_variables -= variable_ids
    if unknown_variables:
        raise ValueError(
            f"candidate rule references unknown variables: {sorted(unknown_variables)}"
        )
    for expression in expressions:
        _validate_expression_types(expression, variable_types)
    return tuple(action.action_id for action in item.actions)


def rules_from_batch(
    batch: CandidateRuleBatch,
    *,
    protocol_version_id: str,
    generation_attempt_id: str,
) -> tuple[tuple[VariableSpec, ...], tuple[CandidateRule, ...], tuple[Issue, ...]]:
    """Convert one already validated candidate-rule batch."""
    rules = tuple(
        CandidateRule(
            candidate_id=item.candidate_id,
            revision=1,
            protocol_version_id=protocol_version_id,
            condition=_expression_from_wire(item.condition),
            evidence_class=EvidenceClass(item.evidence_class),
            observation_refs=item.observation_refs,
            applies_to=(
                _expression_from_wire(item.applies_to) if item.applies_to is not None else None
            ),
            actions=tuple(_action_from_wire(action) for action in item.actions),
            exceptions=tuple(_expression_from_wire(item) for item in item.exceptions),
            modality=item.modality,
            statement_kind=item.statement_kind,
            evidence_bindings=tuple(
                _binding_from_wire(binding) for binding in item.evidence_bindings
            ),
            ambiguity_flags=item.ambiguity_flags,
            generation_attempt_id=generation_attempt_id,
        )
        for item in batch.items
    )
    variables = tuple(_variable_from_wire(variable) for variable in batch.variables)
    return (
        variables,
        rules,
        tuple(_issue_from_wire(issue, generation_attempt_id) for issue in batch.issues),
    )


def validate_relation_batch(  # noqa: PLR0913
    batch: CandidateRelationBatch,
    document_map: DocumentMap,
    observation_ids: set[str],
    endpoint_ids: set[str],
    *,
    existing_relation_ids: set[str] | None = None,
    existing_relation_hashes: set[str] | None = None,
) -> None:
    """Reject invented endpoints/evidence without interpreting relationship meaning."""
    _require_usable_outcome(batch.outcome)
    relation_ids = [item.candidate_relation_id for item in batch.items]
    _require_unique(relation_ids, "candidate relation ids")
    _require_unique((item.issue_id for item in batch.issues), "issue ids")
    if existing_relation_ids and set(relation_ids) & existing_relation_ids:
        raise ValueError("reconciliation must not overwrite existing candidate relations")
    for item in batch.items:
        unknown_endpoints = ({item.source_ref} | set(item.target_refs)) - endpoint_ids
        if unknown_endpoints:
            raise ValueError(f"relation references unknown endpoints: {sorted(unknown_endpoints)}")
        unknown_observations = set(item.observation_refs) - observation_ids
        if unknown_observations:
            raise ValueError(
                f"relation references unknown observations: {sorted(unknown_observations)}"
            )
        _validate_bindings(
            item.evidence_bindings, document_map, claim_root=item.model_dump(mode="json")
        )
        _require_binding_coverage(
            item.evidence_bindings,
            _relation_claim_paths(item),
            f"candidate relation {item.candidate_relation_id!r}",
        )
    known = endpoint_ids | observation_ids | set(relation_ids) | (existing_relation_ids or set())
    for issue in batch.issues:
        _validate_issue_related_ids(issue, document_map, known)
    converted, _ = relations_from_batch(batch, generation_attempt_id="attempt-validation")
    content_hashes = [item.content_hash for item in converted]
    _require_unique((item for item in content_hashes if item is not None), "relation contents")
    if existing_relation_hashes and set(content_hashes) & existing_relation_hashes:
        raise ValueError("reconciliation must not duplicate existing relation content")


def relations_from_batch(
    batch: CandidateRelationBatch, *, generation_attempt_id: str
) -> tuple[tuple[CandidateRelation, ...], tuple[Issue, ...]]:
    """Convert one already validated candidate-relation batch."""
    relations = tuple(
        CandidateRelation(
            candidate_relation_id=item.candidate_relation_id,
            revision=1,
            source_ref=item.source_ref,
            target_refs=item.target_refs,
            relation_type=RelationType(item.relation_type),
            evidence_class=EvidenceClass(item.evidence_class),
            observation_refs=item.observation_refs,
            branch_label=item.branch_label,
            temporal_qualifier=item.temporal_qualifier,
            evidence_bindings=tuple(
                _binding_from_wire(binding) for binding in item.evidence_bindings
            ),
            generation_attempt_id=generation_attempt_id,
        )
        for item in batch.items
    )
    return relations, tuple(
        _issue_from_wire(issue, generation_attempt_id) for issue in batch.issues
    )


def _expression_from_wire(expression: WireExpression) -> ClinicalExpression:
    if isinstance(expression, WireComparison):
        return Condition(
            kind=ConditionKind.COMPARISON,
            variable_ref=expression.variable_ref,
            operator=ComparisonOperator(expression.operator),
            operand=expression.operand,
        )
    if isinstance(expression, WireMembership):
        return Condition(
            kind=ConditionKind.MEMBERSHIP,
            variable_ref=expression.variable_ref,
            values=expression.values,
        )
    if isinstance(expression, WireFlag):
        return Condition(
            kind=ConditionKind.FLAG,
            variable_ref=expression.variable_ref,
            expected=expression.expected,
        )
    if isinstance(expression, WireTemporal):
        return Condition(
            kind=ConditionKind.TEMPORAL,
            variable_ref=expression.variable_ref,
            temporal_operator=TemporalOperator(expression.temporal_operator),
            duration_value=expression.duration_value,
            duration_unit=expression.duration_unit,
        )
    if isinstance(expression, WireLogical):
        return LogicalExpression(
            operator=LogicalOperator(expression.operator),
            operands=tuple(_expression_from_wire(operand) for operand in expression.operands),
            threshold=expression.threshold,
        )
    raise TypeError(f"unsupported wire expression {type(expression).__name__}")


def _binding_from_wire(binding: EvidenceBindingWire) -> EvidenceBinding:
    return EvidenceBinding(
        claim_path=binding.claim_path,
        evidence_class=EvidenceClass(binding.evidence_class),
        source_span_refs=binding.source_span_refs,
        exact_quote=binding.exact_quote,
        transformation=binding.transformation,
    )


def _action_from_wire(action: ActionWire) -> ActionSpec:
    return ActionSpec(
        action_id=action.action_id,
        action_type=ActionType(action.action_type),
        target_text=action.target_text,
        dose_value=action.dose_value,
        dose_unit=action.dose_unit,
        route=action.route,
        frequency=action.frequency,
        duration=action.duration,
        timing=action.timing,
        alternative_group=action.alternative_group,
        qualifiers=action.qualifiers,
        evidence_bindings=tuple(
            _binding_from_wire(binding) for binding in action.evidence_bindings
        ),
    )


def _variable_from_wire(variable: VariableWire) -> VariableSpec:
    return VariableSpec(
        variable_id=variable.variable_id,
        label=variable.label,
        value_type=VariableType(variable.value_type),
        unit=variable.unit,
        allowed_values=variable.allowed_values,
        evidence_bindings=tuple(
            _binding_from_wire(binding) for binding in variable.evidence_bindings
        ),
    )


def _issue_from_wire(issue: BatchIssueWire, generation_attempt_id: str) -> Issue:
    return Issue(
        issue_id=issue.issue_id,
        category=IssueCategory(issue.category),
        severity=IssueSeverity(issue.severity),
        description=issue.description,
        related_ids=issue.related_ids,
        generation_attempt_id=generation_attempt_id,
    )


def _require_usable_outcome(outcome: BatchOutcome) -> None:
    if outcome in {BatchOutcome.FAILED, BatchOutcome.NEEDS_MORE_CONTEXT}:
        raise ValueError(f"batch outcome {outcome.value} is not an accepted semantic result")


def _validate_bindings(
    bindings: tuple[EvidenceBindingWire, ...],
    document_map: DocumentMap,
    *,
    claim_root: object,
) -> None:
    for binding in bindings:
        _resolve_claim_path(claim_root, binding.claim_path)
        _validate_span_refs(binding.source_span_refs, document_map)
        if binding.evidence_class != "UNRESOLVED" and binding.exact_quote is None:
            raise ValueError(
                f"evidence binding {binding.claim_path!r} requires exact_quote unless unresolved"
            )
        _validate_quote(binding.exact_quote, binding.source_span_refs, document_map)


def _validate_span_refs(span_refs: tuple[str, ...], document_map: DocumentMap) -> None:
    unknown = set(span_refs) - set(document_map.spans)
    if unknown:
        raise ValueError(f"output references nonexistent SourceSpan ids: {sorted(unknown)}")


def _validate_quote(
    quote: str | None, span_refs: tuple[str, ...], document_map: DocumentMap
) -> None:
    if quote is None:
        return
    text = "\n".join(
        document_map.spans[ref].extracted_text_exact or ""
        for ref in span_refs
        if ref in document_map.spans
    )
    if quote not in text:
        raise ValueError(f"exact_quote is not present in its referenced SourceSpans: {quote!r}")


def _validate_issue_related_ids(
    issue: BatchIssueWire, document_map: DocumentMap, known_ids: set[str]
) -> None:
    allowed = (
        known_ids
        | set(document_map.spans)
        | {
            document_map.document.document_id,
            document_map.run.run_id,
        }
    )
    unknown = set(issue.related_ids) - allowed
    if unknown:
        raise ValueError(f"issue references unknown ids: {sorted(unknown)}")


def _require_unique(values: Iterable[str], label: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        raise ValueError(f"duplicate {label}: {sorted(duplicates)}")


def _wire_variable_refs(expression: WireExpression) -> set[str]:
    if isinstance(expression, WireLogical):
        return set().union(*(_wire_variable_refs(item) for item in expression.operands))
    return {expression.variable_ref}


def _validate_expression_types(expression: WireExpression, variable_types: dict[str, str]) -> None:
    if isinstance(expression, WireLogical):
        for operand in expression.operands:
            _validate_expression_types(operand, variable_types)
        return
    expected = {
        WireComparison: "NUMERIC",
        WireMembership: "CATEGORICAL",
        WireFlag: "BOOLEAN",
        WireTemporal: "DURATION",
    }[type(expression)]
    actual = variable_types[expression.variable_ref]
    if actual != expected:
        raise ValueError(
            f"{expression.kind} expression requires {expected} variable; "
            f"{expression.variable_ref!r} is {actual}"
        )


def _resolve_claim_path(root: object, claim_path: str) -> object:
    current = root
    for raw_part in claim_path.removeprefix("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise ValueError(f"claim_path does not resolve in its semantic object: {claim_path!r}")
    return current


def _require_binding_coverage(
    bindings: tuple[EvidenceBindingWire, ...], required_paths: set[str], label: str
) -> None:
    _require_unique((binding.claim_path for binding in bindings), f"{label} claim paths")
    bound_paths = {binding.claim_path for binding in bindings}
    missing = required_paths - bound_paths
    if missing:
        raise ValueError(f"{label} has unbound clinical fields: {sorted(missing)}")


def _expression_claim_paths(expression: WireExpression, prefix: str) -> set[str]:
    paths = {f"{prefix}/operator"}
    if isinstance(expression, WireLogical):
        if expression.threshold is not None:
            paths.add(f"{prefix}/threshold")
        for index, operand in enumerate(expression.operands):
            paths.update(_expression_claim_paths(operand, f"{prefix}/operands/{index}"))
        return paths
    paths = {f"{prefix}/variable_ref"}
    if isinstance(expression, WireComparison):
        paths.update({f"{prefix}/operator", f"{prefix}/operand"})
    elif isinstance(expression, WireMembership):
        paths.add(f"{prefix}/values")
    elif isinstance(expression, WireFlag):
        paths.add(f"{prefix}/expected")
    elif isinstance(expression, WireTemporal):
        paths.update(
            {
                f"{prefix}/temporal_operator",
                f"{prefix}/duration_value",
                f"{prefix}/duration_unit",
            }
        )
    return paths


def _rule_claim_paths(item: CandidateRuleItem) -> set[str]:
    paths = _expression_claim_paths(item.condition, "/condition")
    if item.applies_to is not None:
        paths.update(_expression_claim_paths(item.applies_to, "/applies_to"))
    for index, exception in enumerate(item.exceptions):
        paths.update(_expression_claim_paths(exception, f"/exceptions/{index}"))
    for field_name in ("modality", "statement_kind"):
        if getattr(item, field_name) is not None:
            paths.add(f"/{field_name}")
    return paths


def _variable_claim_paths(variable: VariableWire) -> set[str]:
    paths = {"/label", "/value_type"}
    if variable.unit is not None:
        paths.add("/unit")
    if variable.allowed_values is not None:
        paths.add("/allowed_values")
    return paths


def _action_claim_paths(action: ActionWire) -> set[str]:
    paths = {"/action_type"}
    for field_name in (
        "target_text",
        "dose_value",
        "dose_unit",
        "route",
        "frequency",
        "duration",
        "timing",
        "alternative_group",
    ):
        if getattr(action, field_name) is not None:
            paths.add(f"/{field_name}")
    if action.qualifiers:
        paths.add("/qualifiers")
    return paths


def _relation_claim_paths(item: CandidateRelationItem) -> set[str]:
    paths = {"/source_ref", "/target_refs", "/relation_type"}
    if item.branch_label is not None:
        paths.add("/branch_label")
    if item.temporal_qualifier is not None:
        paths.add("/temporal_qualifier")
    return paths
