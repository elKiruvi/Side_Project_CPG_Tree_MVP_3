"""Candidate pipeline contracts: evidence-bound, pre-approval artifacts.

This package defines the domain contracts of the MVP 3 candidate pipeline:
evidence bindings, observations, variable/action specifications, candidate
rules and relations, Issues, and stable content hashing.

Layer discipline (binding decision):

- Candidates are untrusted by construction and can never carry approval.
  There is no ``APPROVED`` candidate state; approval exists only in the
  review layer (``cpg_tree.review``) and produces immutable snapshots
  (``cpg_tree.knowledge.approved``).
- The canonical clinical expression AST is reused from
  ``cpg_tree.knowledge.conditions``; it is not duplicated here.
- ``cpg_tree.llm.schemas`` holds the Pydantic wire schemas for untrusted
  structured LLM outputs; the dataclasses here are the validated internal
  domain models. Phase 3/4 converters map wire items onto these contracts.
- ``EvidenceClass`` here intentionally mirrors ``reconciliation``'s enum
  (temporary coexistence); the reconciliation layer is adapted onto this
  package in Phase 5.

Nothing in this package evaluates clinical logic or implies approval.
"""

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
from cpg_tree.candidates.expressions import ClinicalExpression, Condition, LogicalExpression
from cpg_tree.candidates.hashing import (
    hash_canonical_dict,
    sha256_hex,
    stable_json_dumps,
    validate_sha256_hex,
)
from cpg_tree.candidates.issues import Issue
from cpg_tree.candidates.observations import Observation
from cpg_tree.candidates.relations import CandidateRelation, compute_candidate_relation_content_hash
from cpg_tree.candidates.rules import CandidateRule, compute_candidate_rule_content_hash
from cpg_tree.candidates.variables import VariableSpec

__all__ = [
    "ActionSpec",
    "CandidateRelation",
    "CandidateRule",
    "CandidateState",
    "ClinicalExpression",
    "Condition",
    "EvidenceBinding",
    "EvidenceClass",
    "Issue",
    "IssueCategory",
    "IssueSeverity",
    "IssueStatus",
    "LogicalExpression",
    "Observation",
    "ObservationKind",
    "RelationType",
    "VariableSpec",
    "compute_candidate_relation_content_hash",
    "compute_candidate_rule_content_hash",
    "hash_canonical_dict",
    "sha256_hex",
    "stable_json_dumps",
    "validate_sha256_hex",
]
