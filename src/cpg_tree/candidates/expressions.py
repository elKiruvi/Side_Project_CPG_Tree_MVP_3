"""ClinicalExpression: the canonical clinical expression AST.

The canonical AST lives in ``cpg_tree.knowledge.conditions`` (``Condition``
and ``LogicalExpression``) and is reused verbatim by the candidate pipeline:
conditions are not duplicated into a wire representation. This module only
declares the pipeline-wide name for the contract.

The AST already supports comparison, membership, flag, and temporal atomic
predicates plus AND/OR/NOT/AT_LEAST_N composites. Additional operators
(e.g. NOT_IN, BETWEEN, PRESENT, ABSENT) are deliberately deferred until
candidate extraction (Phase 4) demonstrates a concrete need; they are then
added to the canonical AST and its deterministic evaluator together.
"""

from cpg_tree.knowledge.conditions import Condition, LogicalExpression, LogicalOperand

type ClinicalExpression = LogicalOperand
"""A clinical condition or logical composite: ``Condition | LogicalExpression``."""

__all__ = [
    "ClinicalExpression",
    "Condition",
    "LogicalExpression",
    "LogicalOperand",
]
