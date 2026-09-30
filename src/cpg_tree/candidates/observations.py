"""Observation: evidence-bound atomic source statements.

An ``Observation`` records what was identified in the source material without
claiming approved computable semantics. It is not a clinical rule and it is
not executable. It retains provenance (span references and the exact quote)
so every later artifact can trace back through the evidence chain.
"""

from __future__ import annotations

from dataclasses import dataclass

from cpg_tree.candidates.enums import ObservationKind
from cpg_tree.knowledge._validation import validate_identifier


@dataclass(frozen=True, slots=True)
class Observation:
    """One evidence-bound atomic statement identified from source material.

    ``span_refs`` identify ``SourceSpan`` entries and must not be empty: an
    observation without a citable source region is not an observation.
    ``issue_ids`` reference ``Issue`` entries that qualify this observation.
    """

    observation_id: str
    kind: ObservationKind
    span_refs: tuple[str, ...]
    exact_quote: str | None = None
    subject_text: str | None = None
    predicate_text: str | None = None
    object_text: str | None = None
    negated: bool = False
    generation_attempt_id: str | None = None
    issue_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_identifier(self.observation_id, "Observation.observation_id")
        if not self.span_refs:
            raise ValueError("Observation.span_refs must not be empty")
        for ref in self.span_refs:
            validate_identifier(ref, "Observation.span_refs entry")
        if self.exact_quote is not None and not self.exact_quote:
            raise ValueError("Observation.exact_quote must not be empty when set")
        if self.generation_attempt_id is not None:
            validate_identifier(self.generation_attempt_id, "Observation.generation_attempt_id")
        for issue_id in self.issue_ids:
            validate_identifier(issue_id, "Observation.issue_ids entry")
