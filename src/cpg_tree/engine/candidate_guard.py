"""Fail-closed boundary between candidate knowledge and clinical execution.

Candidate knowledge (``CandidateGraph``) may be visualized and reviewed but
must never flow into the deterministic clinical-rule engine as if it were
approved. ``ApprovedKnowledgePackage`` (or the legacy reviewed
``ProtocolVersion``) is the only executable knowledge.

This guard is called by the engine's public entry point so that any future
bridge that accidentally forwards candidate objects fails closed at runtime,
independently of static typing.
"""

from __future__ import annotations

from typing import Any


def reject_candidate_graph(value: Any) -> None:
    """Raise ``TypeError`` when the value is candidate knowledge.

    Uses an import inside the function to avoid coupling the engine's import
    graph to the candidate layer until the guard actually runs.
    """
    from cpg_tree.candidates.graph import CandidateGraph  # noqa: PLC0415

    if isinstance(value, CandidateGraph):
        raise TypeError(
            "CandidateGraph is not approved clinical knowledge and must never "
            "be executed by the deterministic engine; it may only be visualized "
            "and reviewed"
        )


__all__ = ["reject_candidate_graph"]
