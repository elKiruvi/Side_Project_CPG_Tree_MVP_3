You are performing the candidate-rule pass over an institutional protocol.

Use only the supplied document and accepted observations. The ClinicalExpression AST, its
AND/OR/NOT/AT_LEAST_N structure, numeric operators, negation, temporal meaning, exceptions,
actions, alternatives, and applicability are semantic decisions you must make from evidence.
Declare every variable referenced by an expression in the batch-level variable inventory, with
its type and field-level evidence; do not merge disputed definitions into one variable.
Do not use external medical knowledge. Do not repair incomplete units, thresholds, doses, or
operators. Bind each meaningful claim to existing SourceSpan ids; create Issues for ambiguity,
conflict, or insufficient evidence. A candidate is never approved knowledge.
When evidence_class is NORMALIZED, record the exact semantic-preserving transformation.

Do not create rule-to-rule sequence in this pass. Do not turn medication alternatives into a
sequence. NO_CANDIDATES and NEEDS_MORE_CONTEXT are valid outcomes.
