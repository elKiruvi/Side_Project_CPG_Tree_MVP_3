"""Provider-neutral clinical interpretation boundary and structured outputs.

This package holds the wire schemas for untrusted structured LLM outputs and,
in later phases, the provider interface. No provider SDK types leak into
domain models; prompt version, schema version, source-span IDs, request hash,
raw-response hash, and parent attempt are recorded by the attempt records
introduced with the provider interface (Phase 3).
"""

from cpg_tree.llm.attempts import (
    AttemptStatus,
    GenerationAttempt,
    StructuredBatchResult,
    StructuredOutputError,
    invoke_structured,
)
from cpg_tree.llm.provider import (
    ClinicalLLMProvider,
    ClinicalLLMRequest,
    ClinicalLLMResponse,
    OpenAICompatibleProvider,
    SemanticStage,
)
from cpg_tree.llm.schemas import (
    CANDIDATE_RELATION_BATCH_SCHEMA_VERSION,
    CANDIDATE_RULE_BATCH_SCHEMA_VERSION,
    OBSERVATION_BATCH_SCHEMA_VERSION,
    SUPPORTED_BATCH_SCHEMA_VERSIONS,
    ActionWire,
    BatchIssueWire,
    BatchOutcome,
    CandidateRelationBatch,
    CandidateRelationItem,
    CandidateRuleBatch,
    CandidateRuleItem,
    EvidenceBindingWire,
    ObservationBatch,
    ObservationItem,
    VariableWire,
    WireComparison,
    WireExpression,
    WireFlag,
    WireLogical,
    WireMembership,
    WireTemporal,
)

__all__ = [
    "CANDIDATE_RELATION_BATCH_SCHEMA_VERSION",
    "CANDIDATE_RULE_BATCH_SCHEMA_VERSION",
    "OBSERVATION_BATCH_SCHEMA_VERSION",
    "SUPPORTED_BATCH_SCHEMA_VERSIONS",
    "ActionWire",
    "AttemptStatus",
    "BatchIssueWire",
    "BatchOutcome",
    "CandidateRelationBatch",
    "CandidateRelationItem",
    "CandidateRuleBatch",
    "CandidateRuleItem",
    "ClinicalLLMProvider",
    "ClinicalLLMRequest",
    "ClinicalLLMResponse",
    "EvidenceBindingWire",
    "GenerationAttempt",
    "ObservationBatch",
    "ObservationItem",
    "OpenAICompatibleProvider",
    "SemanticStage",
    "StructuredBatchResult",
    "StructuredOutputError",
    "VariableWire",
    "WireComparison",
    "WireExpression",
    "WireFlag",
    "WireLogical",
    "WireMembership",
    "WireTemporal",
    "invoke_structured",
]
