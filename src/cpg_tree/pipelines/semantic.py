"""LLM-first orchestration from documentary evidence to a Candidate Graph."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from pydantic import BaseModel

from cpg_tree.candidates.graph import CandidateGraph, validate_candidate_graph
from cpg_tree.candidates.hashing import sha256_hex
from cpg_tree.candidates.issues import Issue
from cpg_tree.extraction.document import DocumentMap
from cpg_tree.knowledge._validation import validate_identifier
from cpg_tree.llm.attempts import (
    GenerationAttempt,
    StructuredBatchResult,
    StructuredOutputError,
    invoke_structured,
)
from cpg_tree.llm.conversion import (
    observations_from_batch,
    relations_from_batch,
    rules_from_batch,
    validate_observation_batch,
    validate_relation_batch,
    validate_rule_batch,
)
from cpg_tree.llm.prompt_builder import build_prompt
from cpg_tree.llm.provider import ClinicalLLMProvider, ClinicalLLMRequest, SemanticStage
from cpg_tree.llm.schemas import (
    CANDIDATE_RELATION_BATCH_SCHEMA_VERSION,
    CANDIDATE_RULE_BATCH_SCHEMA_VERSION,
    OBSERVATION_BATCH_SCHEMA_VERSION,
    CandidateRelationBatch,
    CandidateRuleBatch,
    ObservationBatch,
)


@dataclass(frozen=True, slots=True)
class SemanticPipelineConfig:
    """Provider-neutral generation settings and candidate identity context."""

    generation_run_id: str
    protocol_version_id: str
    temperature: float = 0.0
    reasoning_effort: str | None = None
    max_retries: int = 1

    def __post_init__(self) -> None:
        validate_identifier(self.generation_run_id, "SemanticPipelineConfig.generation_run_id")
        validate_identifier(self.protocol_version_id, "SemanticPipelineConfig.protocol_version_id")
        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative")


@dataclass(frozen=True, slots=True)
class SemanticPipelineResult:
    """Reviewable graph plus each accepted semantic response envelope."""

    graph: CandidateGraph
    observation_batch: ObservationBatch
    rule_batch: CandidateRuleBatch
    relation_batch: CandidateRelationBatch
    reconciliation_batch: CandidateRelationBatch


class SemanticPipelineError(RuntimeError):
    """A quarantined semantic failure with attempts from every completed stage."""

    def __init__(self, message: str, attempts: tuple[GenerationAttempt, ...]) -> None:
        super().__init__(message)
        self.attempts = attempts


def run_semantic_pipeline(
    document_map: DocumentMap,
    provider: ClinicalLLMProvider,
    config: SemanticPipelineConfig,
) -> SemanticPipelineResult:
    """Run four semantic passes; deterministic code only validates and compiles outputs."""
    _validate_protocol_version(document_map, config.protocol_version_id)
    span_ids = tuple(
        span.span_id
        for span in sorted(document_map.spans.values(), key=lambda item: (item.page, item.span_id))
    )
    attempts: list[GenerationAttempt] = []

    observation_result = _record_stage(
        attempts,
        lambda: _invoke_stage(
            provider,
            config,
            document_map,
            SemanticStage.OBSERVATIONS,
            ObservationBatch,
            OBSERVATION_BATCH_SCHEMA_VERSION,
            span_ids,
            validate=lambda batch: validate_observation_batch(batch, document_map),
        ),
    )
    observations, observation_issues = observations_from_batch(
        observation_result.batch,
        generation_attempt_id=observation_result.accepted_attempt_id,
    )
    observation_ids = {item.observation_id for item in observations}

    rule_result = _record_stage(
        attempts,
        lambda: _invoke_stage(
            provider,
            config,
            document_map,
            SemanticStage.RULES,
            CandidateRuleBatch,
            CANDIDATE_RULE_BATCH_SCHEMA_VERSION,
            span_ids,
            prior_batches=(("observations", observation_result.batch),),
            validate=lambda batch: validate_rule_batch(
                batch, document_map, observation_ids, config.protocol_version_id
            ),
        ),
    )
    variables, rules, rule_issues = rules_from_batch(
        rule_result.batch,
        protocol_version_id=config.protocol_version_id,
        generation_attempt_id=rule_result.accepted_attempt_id,
    )
    endpoint_ids = {item.candidate_id for item in rules}
    endpoint_ids.update(action.action_id for item in rules for action in item.actions)

    relation_result = _record_stage(
        attempts,
        lambda: _invoke_stage(
            provider,
            config,
            document_map,
            SemanticStage.RELATIONS,
            CandidateRelationBatch,
            CANDIDATE_RELATION_BATCH_SCHEMA_VERSION,
            span_ids,
            prior_batches=(
                ("observations", observation_result.batch),
                ("rules", rule_result.batch),
            ),
            validate=lambda batch: validate_relation_batch(
                batch, document_map, observation_ids, endpoint_ids
            ),
        ),
    )
    relations, relation_issues = relations_from_batch(
        relation_result.batch,
        generation_attempt_id=relation_result.accepted_attempt_id,
    )
    relation_ids = {item.candidate_relation_id for item in relations}
    relation_hashes = {item.content_hash for item in relations if item.content_hash is not None}

    reconciliation_result = _record_stage(
        attempts,
        lambda: _invoke_stage(
            provider,
            config,
            document_map,
            SemanticStage.RECONCILIATION,
            CandidateRelationBatch,
            CANDIDATE_RELATION_BATCH_SCHEMA_VERSION,
            span_ids,
            prior_batches=(
                ("observations", observation_result.batch),
                ("rules", rule_result.batch),
                ("relations", relation_result.batch),
            ),
            validate=lambda batch: validate_relation_batch(
                batch,
                document_map,
                observation_ids,
                endpoint_ids,
                existing_relation_ids=relation_ids,
                existing_relation_hashes=relation_hashes,
            ),
        ),
    )
    reconciled_relations, reconciliation_issues = relations_from_batch(
        reconciliation_result.batch,
        generation_attempt_id=reconciliation_result.accepted_attempt_id,
    )
    try:
        issues = _merge_issues(
            observation_issues,
            rule_issues,
            relation_issues,
            reconciliation_issues,
        )
        graph_id = (
            f"graph-"
            f"{sha256_hex(f'{document_map.document.document_id}|{config.generation_run_id}')[:20]}"
        )
        graph = CandidateGraph(
            graph_id=graph_id,
            generation_run_id=config.generation_run_id,
            protocol_version_id=config.protocol_version_id,
            document_id=document_map.document.document_id,
            extraction_run_id=document_map.run.run_id,
            observations=observations,
            variables=variables,
            rules=rules,
            relations=relations + reconciled_relations,
            issues=issues,
            source_spans=tuple(
                sorted(document_map.spans.values(), key=lambda item: (item.page, item.span_id))
            ),
            attempts=tuple(attempts),
        )
        graph = replace(graph, findings=validate_candidate_graph(graph))
    except ValueError as exc:
        raise SemanticPipelineError(str(exc), tuple(attempts)) from exc
    return SemanticPipelineResult(
        graph=graph,
        observation_batch=observation_result.batch,
        rule_batch=rule_result.batch,
        relation_batch=relation_result.batch,
        reconciliation_batch=reconciliation_result.batch,
    )


def _invoke_stage[BatchT: BaseModel](  # noqa: PLR0913, PLR0917
    provider: ClinicalLLMProvider,
    config: SemanticPipelineConfig,
    document_map: DocumentMap,
    stage: SemanticStage,
    batch_type: type[BatchT],
    schema_version: str,
    span_ids: tuple[str, ...],
    *,
    prior_batches: tuple[tuple[str, BaseModel], ...] = (),
    validate: Callable[[BatchT], None],
) -> StructuredBatchResult[BatchT]:
    prompt = build_prompt(stage, document_map, prior_batches=prior_batches)
    request_id = f"{config.generation_run_id}-{stage.value.lower()}"
    rendered_prompt = f"REQUEST ID: {request_id}\nSEGMENT ID: document-full\n\n{prompt.text}"
    request = ClinicalLLMRequest(
        request_id=request_id,
        stage=stage,
        prompt=rendered_prompt,
        prompt_version=prompt.version,
        schema_version=schema_version,
        response_schema=batch_type.model_json_schema(),
        input_span_ids=span_ids,
        input_hash=sha256_hex(rendered_prompt),
        temperature=config.temperature,
        reasoning_effort=config.reasoning_effort,
    )
    return invoke_structured(
        provider,
        request,
        batch_type,
        max_retries=config.max_retries,
        validate=validate,
    )


def _record_stage[BatchT: BaseModel](
    attempts: list[GenerationAttempt],
    invoke: Callable[[], StructuredBatchResult[BatchT]],
) -> StructuredBatchResult[BatchT]:
    try:
        result = invoke()
    except StructuredOutputError as exc:
        all_attempts = (*attempts, *exc.attempts)
        raise SemanticPipelineError(str(exc), all_attempts) from exc
    attempts.extend(result.attempts)
    return result


def _merge_issues(*groups: tuple[Issue, ...]) -> tuple[Issue, ...]:
    issues: list[Issue] = []
    seen: set[str] = set()
    for group in groups:
        for issue in group:
            if issue.issue_id in seen:
                raise ValueError(f"duplicate Issue id across semantic passes: {issue.issue_id!r}")
            seen.add(issue.issue_id)
            issues.append(issue)
    return tuple(issues)


def _validate_protocol_version(document_map: DocumentMap, protocol_version_id: str) -> None:
    document = document_map.document
    if document.protocol_id is None or document.protocol_version is None:
        raise ValueError(
            "DocumentMap source must register protocol_id and protocol_version before semantics"
        )
    version = document.protocol_version
    numeric_version = version[1:] if version.lower().startswith("v") else version
    normalized_version = numeric_version.zfill(2) if numeric_version.isdigit() else numeric_version
    expected = f"{document.protocol_id}-v{normalized_version}"
    if protocol_version_id != expected:
        raise ValueError(
            f"protocol_version_id {protocol_version_id!r} does not match document metadata "
            f"{expected!r}"
        )
