"""Deterministic JSON serialization for reviewable Candidate Graph artifacts."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from cpg_tree.candidates.graph import CandidateGraph
from cpg_tree.llm.attempts import GenerationAttempt


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
