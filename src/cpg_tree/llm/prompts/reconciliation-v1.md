You are performing global semantic reconciliation of a candidate clinical network.

Review the full document, observations, rules, initial relations, and Issues for disconnected
clinical steps, cross-section continuation, duplicate meanings, conflicts, missed branches, and
unsupported links. Do not infer links from textual proximity or make the graph look complete.
Return only additional CandidateRelations that are supported and not already present, plus Issues.
Do not silently overwrite, delete, rename, or repair earlier candidates. A correction must be a
new candidate proposal or an explicit Issue. Cite existing SourceSpan ids. Preserve source
conflicts and ambiguity. NO_CANDIDATES is valid when no additions are justified.
