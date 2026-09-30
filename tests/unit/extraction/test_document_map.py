"""Tests for DocumentMap structural invariants and YAML serialization."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from unit.extraction.layout_fixtures import build_text_pdf

from cpg_tree.extraction import (
    DocumentElement,
    DocumentMap,
    ElementKind,
    ExtractionNotice,
    ExtractionNoticeSeverity,
    ExtractionRun,
    ExtractionRunStatus,
    PageMap,
    SourceSpan,
    SpanRepresentation,
    dump_document_map,
    extract_document_map,
    load_document_map,
)
from cpg_tree.extraction.runs import ExtractionChannel
from cpg_tree.knowledge import SourceDocument

FIXED_TIMESTAMP = "2026-09-29T10:00:00+00:00"
VALID_SHA256 = "3a1654757801b7b618661f846f8335ced6fb9e388891d6bca96f1cd81d6f5882"


def _document(document_id: str = "doc-abc123") -> SourceDocument:
    return SourceDocument(
        document_id=document_id,
        filename="sample.pdf",
        sha256=VALID_SHA256,
    )


def _run(document_id: str = "doc-abc123") -> ExtractionRun:
    return ExtractionRun(
        run_id="run-1",
        document_id=document_id,
        status=ExtractionRunStatus.COMPLETE,
        started_at=FIXED_TIMESTAMP,
        completed_at=FIXED_TIMESTAMP,
        configuration_hash="a" * 64,
        channels=(
            ExtractionChannel(
                name="pymupdf-layout",
                representation=SpanRepresentation.PAGE_LAYOUT,
                status=ExtractionRunStatus.COMPLETE,
            ),
        ),
    )


def _span(span_id: str, page: int, text: str, run_id: str = "run-1") -> SourceSpan:
    return SourceSpan(
        span_id=span_id,
        document_id="doc-abc123",
        extraction_run_id=run_id,
        page=page,
        representation=SpanRepresentation.TEXT,
        extraction_method="pymupdf-text",
        extracted_text_exact=text,
        text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _element(element_id: str, page: int, order_index: int, span_id: str) -> DocumentElement:
    return DocumentElement(
        element_id=element_id,
        page=page,
        kind=ElementKind.TEXT,
        order_index=order_index,
        span_id=span_id,
        text="texto",
    )


def _build_map(**overrides: object) -> DocumentMap:
    span_a = _span("doc-abc123-p001-e000", 1, "texto")
    span_b = _span("doc-abc123-p001-e001", 1, "texto")
    fields: dict[str, object] = {
        "document": _document(),
        "run": _run(),
        "pages": (
            PageMap(
                page=1,
                text="texto\ntexto",
                elements=(
                    _element("doc-abc123-p001-e000", 1, 0, "doc-abc123-p001-e000"),
                    _element("doc-abc123-p001-e001", 1, 1, "doc-abc123-p001-e001"),
                ),
            ),
        ),
        "spans": {span_a.span_id: span_a, span_b.span_id: span_b},
    }
    fields.update(overrides)
    return DocumentMap(**fields)  # type: ignore[arg-type]


def test_document_map_rejects_run_document_mismatch() -> None:
    with pytest.raises(ValueError, match="document ids"):
        _build_map(run=_run(document_id="doc-other"))


def test_document_map_rejects_unknown_span_reference() -> None:
    span_a = _span("doc-abc123-p001-e000", 1, "texto")
    fields = {
        "pages": (
            PageMap(
                page=1,
                text="texto",
                elements=(_element("doc-abc123-p001-e000", 1, 0, "doc-abc123-p001-e999"),),
            ),
        ),
        "spans": {span_a.span_id: span_a},
    }
    with pytest.raises(ValueError, match="unknown span"):
        _build_map(**fields)


def test_document_map_rejects_duplicate_element_ids() -> None:
    span_a = _span("doc-abc123-p001-e000", 1, "texto")
    fields = {
        "pages": (
            PageMap(
                page=1,
                text="texto\ntexto",
                elements=(
                    _element("doc-abc123-p001-e000", 1, 0, "doc-abc123-p001-e000"),
                    _element("doc-abc123-p001-e000", 1, 1, "doc-abc123-p001-e000"),
                ),
            ),
        ),
        "spans": {span_a.span_id: span_a},
    }
    with pytest.raises(ValueError, match="duplicate element"):
        _build_map(**fields)


def test_document_map_rejects_non_consecutive_pages() -> None:
    span_a = _span("doc-abc123-p002-e000", 2, "texto")
    fields = {
        "pages": (
            PageMap(
                page=2,
                text="texto",
                elements=(_element("doc-abc123-p002-e000", 2, 0, "doc-abc123-p002-e000"),),
            ),
        ),
        "spans": {span_a.span_id: span_a},
    }
    with pytest.raises(ValueError, match="consecutive"):
        _build_map(**fields)


def test_page_map_requires_contiguous_order_indices() -> None:
    with pytest.raises(ValueError, match="order_index"):
        PageMap(
            page=1,
            text="texto",
            elements=(_element("doc-abc123-p001-e000", 1, 5, "doc-abc123-p001-e000"),),
        )


def test_element_parent_must_be_same_page() -> None:
    parent = _element("doc-abc123-p001-e000", 1, 0, "doc-abc123-p001-e000")
    child = DocumentElement(
        element_id="doc-abc123-p001-e001",
        page=1,
        kind=ElementKind.TABLE_CELL,
        order_index=1,
        span_id="doc-abc123-p001-e001",
        text="celda",
        parent_element_id=parent.element_id,
    )
    span_a = _span("doc-abc123-p001-e000", 1, "texto")
    span_b = _span("doc-abc123-p001-e001", 1, "celda")
    fields = {
        "pages": (
            PageMap(
                page=1,
                text="texto\ncelda",
                elements=(parent, child),
            ),
        ),
        "spans": {span_a.span_id: span_a, span_b.span_id: span_b},
    }
    built = _build_map(**fields)
    assert built.pages[0].elements[1].parent_element_id == parent.element_id


def test_notice_requires_code_and_message() -> None:
    with pytest.raises(ValueError, match="code"):
        ExtractionNotice(code="", severity=ExtractionNoticeSeverity.WARNING, message="x")
    with pytest.raises(ValueError, match="message"):
        ExtractionNotice(code="C1", severity=ExtractionNoticeSeverity.WARNING, message="")


def test_extracted_map_round_trips_through_yaml(tmp_path: Path) -> None:
    path = tmp_path / "sample.pdf"
    build_text_pdf(path, [["alpha", "beta"], ["gamma"]])
    document_map = extract_document_map(path, extracted_at=FIXED_TIMESTAMP)
    reloaded = load_document_map(dump_document_map(document_map))
    assert reloaded == document_map


def test_serialization_is_byte_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "sample.pdf"
    build_text_pdf(path, [["alpha", "beta"]])
    first = dump_document_map(extract_document_map(path, extracted_at=FIXED_TIMESTAMP))
    second = dump_document_map(extract_document_map(path, extracted_at=FIXED_TIMESTAMP))
    assert first == second


def test_load_rejects_non_mapping_root() -> None:
    with pytest.raises(ValueError, match="mapping"):
        load_document_map("- just\n- a\n- list\n")


def test_load_rejects_missing_sections() -> None:
    with pytest.raises(ValueError, match="document"):
        load_document_map("spans: {}\n")
