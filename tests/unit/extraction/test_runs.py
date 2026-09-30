"""Tests for the ExtractionRun domain contract."""

from __future__ import annotations

import pytest

from cpg_tree.extraction import (
    ExtractionChannel,
    ExtractionRun,
    ExtractionRunStatus,
    SpanRepresentation,
    ToolVersion,
)

CONFIG_HASH = "a" * 64
TWO_CHANNELS = 2


def make_run(**overrides: object) -> ExtractionRun:
    fields: dict[str, object] = {
        "run_id": "run-1",
        "document_id": "doc-abc",
        "status": ExtractionRunStatus.COMPLETE,
        "started_at": "2026-09-29T10:00:00",
        "completed_at": "2026-09-29T10:00:05",
        "configuration_hash": CONFIG_HASH,
        "channels": (
            ExtractionChannel(
                name="pypdf-text",
                representation=SpanRepresentation.TEXT,
                status=ExtractionRunStatus.COMPLETE,
            ),
        ),
    }
    fields.update(overrides)
    return ExtractionRun(**fields)  # type: ignore[arg-type]


def test_extraction_run_construction() -> None:
    run = make_run()
    assert run.run_id == "run-1"
    assert run.status is ExtractionRunStatus.COMPLETE
    assert run.completed_at is not None


def test_started_run_cannot_have_completed_at() -> None:
    with pytest.raises(ValueError, match="STARTED"):
        make_run(status=ExtractionRunStatus.STARTED, completed_at="2026-09-29T10:00:05")


@pytest.mark.parametrize(
    "status",
    [ExtractionRunStatus.COMPLETE, ExtractionRunStatus.PARTIAL, ExtractionRunStatus.FAILED],
)
def test_finished_run_requires_completed_at(status: ExtractionRunStatus) -> None:
    with pytest.raises(ValueError, match="completed_at"):
        make_run(status=status, completed_at=None)


def test_extraction_run_requires_channels() -> None:
    with pytest.raises(ValueError, match="channels"):
        make_run(channels=())


def test_extraction_run_rejects_bad_configuration_hash() -> None:
    with pytest.raises(ValueError, match="configuration_hash"):
        make_run(configuration_hash="not-a-hash")


def test_extraction_run_rejects_bad_started_at() -> None:
    with pytest.raises(ValueError, match="started_at"):
        make_run(started_at="2026-09-29")


def test_partial_run_records_failed_channels_without_dropping_them() -> None:
    run = make_run(
        status=ExtractionRunStatus.PARTIAL,
        channels=(
            ExtractionChannel(
                name="pypdf-text",
                representation=SpanRepresentation.TEXT,
                status=ExtractionRunStatus.COMPLETE,
            ),
            ExtractionChannel(
                name="pymupdf-layout",
                representation=SpanRepresentation.PAGE_LAYOUT,
                status=ExtractionRunStatus.FAILED,
                notes="layout extraction raised",
            ),
        ),
        tool_versions=(
            ToolVersion(tool="pypdf", version="6.19.0"),
            ToolVersion(tool="pymupdf", version="1.26.0"),
        ),
        warnings=("one channel failed",),
    )
    assert len(run.channels) == TWO_CHANNELS
    assert run.channels[1].status is ExtractionRunStatus.FAILED
    assert run.warnings == ("one channel failed",)


def test_tool_version_requires_tool_and_version() -> None:
    with pytest.raises(ValueError, match="tool"):
        ToolVersion(tool="", version="1.0")
    with pytest.raises(ValueError, match="version"):
        ToolVersion(tool="pypdf", version="")
