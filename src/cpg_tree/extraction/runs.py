"""ExtractionRun: reproducible record of one multichannel extraction execution.

An ``ExtractionRun`` is a pipeline artifact, not clinical knowledge. It
documents which tools and channels produced the ``SourceSpan`` inventory for
one document so that every span can be traced back to a reproducible
execution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from cpg_tree.extraction.spans import SpanRepresentation
from cpg_tree.knowledge._validation import validate_identifier, validate_iso_datetime

_SHA256_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")


class ExtractionRunStatus(StrEnum):
    """Lifecycle status of one extraction run."""

    STARTED = "STARTED"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ToolVersion:
    """Identity and version of one tool used during the run."""

    tool: str
    version: str

    def __post_init__(self) -> None:
        if not self.tool:
            raise ValueError("ToolVersion.tool must not be empty")
        if not self.version:
            raise ValueError("ToolVersion.version must not be empty")


@dataclass(frozen=True, slots=True)
class ExtractionChannel:
    """One evidence channel of the run and its completion state.

    Channels are never silently dropped: a channel that produced nothing or
    failed is recorded with its own status, not deleted from the record.
    """

    name: str
    representation: SpanRepresentation
    status: ExtractionRunStatus
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("ExtractionChannel.name must not be empty")
        if self.notes is not None and not self.notes:
            raise ValueError("ExtractionChannel.notes must not be empty when set")


@dataclass(frozen=True, slots=True)
class ExtractionRun:
    """Reproducibility record of one multichannel extraction execution.

    ``configuration_hash`` binds the run to the canonical serialization of the
    extraction configuration (defined by the Phase 2 pipeline). A finished run
    (``COMPLETE``, ``PARTIAL``, or ``FAILED``) always carries ``completed_at``;
    a ``STARTED`` run never does.
    """

    run_id: str
    document_id: str
    status: ExtractionRunStatus
    started_at: str
    configuration_hash: str
    channels: tuple[ExtractionChannel, ...]
    completed_at: str | None = None
    tool_versions: tuple[ToolVersion, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_identifier(self.run_id, "ExtractionRun.run_id")
        validate_identifier(self.document_id, "ExtractionRun.document_id")
        validate_iso_datetime(self.started_at, "ExtractionRun.started_at")
        if _SHA256_PATTERN.fullmatch(self.configuration_hash) is None:
            raise ValueError("ExtractionRun.configuration_hash must be a 64-character hex digest")
        if not self.channels:
            raise ValueError("ExtractionRun.channels must not be empty")
        if self.completed_at is None and self.status is not ExtractionRunStatus.STARTED:
            raise ValueError(f"{self.status.value} runs require ExtractionRun.completed_at")
        if self.completed_at is not None and self.status is ExtractionRunStatus.STARTED:
            raise ValueError("STARTED runs must not set ExtractionRun.completed_at")
        if self.completed_at is not None:
            validate_iso_datetime(self.completed_at, "ExtractionRun.completed_at")
        for warning in self.warnings:
            if not warning:
                raise ValueError("ExtractionRun.warnings entries must not be empty")
