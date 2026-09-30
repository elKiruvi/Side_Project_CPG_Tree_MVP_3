"""Integration tests: structured extraction over the real source PDFs.

These tests exercise documentary fidelity only — what is present on each
page, never what the clinical content means. They skip when the raw PDFs are
not available locally (the clinical PDFs are source data and are never
committed to Git); the portable CI suite uses synthetic fixtures instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cpg_tree.extraction import (
    DocumentMap,
    ElementKind,
    ExtractionNotice,
    ExtractionRunStatus,
    SpanQualityFlag,
    extract_document_map,
)

RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "01_raw"

NAC_PAGE_COUNT = 7
ITU_PAGE_COUNT = 5
NAC_DOCUMENT_ID = "doc-3a1654757801b7b6"
ITU_DOCUMENT_ID = "doc-800af94bc0654138"
MIN_REAL_PDFS = 2

NAC_FIGURE_PAGES = {1, 2, 6}
PAGE_FOUR = 4
PAGE_FIVE = 5
ITU_FIGURE_PAGES = {1}
ITU_CROSS_PAGE_TABLE_PAGE = 5


def _raw_pdfs() -> list[Path]:
    return sorted(RAW_DIR.glob("CT-PL-19*.pdf"))


pytestmark = pytest.mark.skipif(
    len(_raw_pdfs()) < MIN_REAL_PDFS, reason="real source PDFs are not available locally"
)


def _map_for(path: Path) -> DocumentMap:
    return extract_document_map(path, extracted_at="2026-09-29T10:00:00+00:00")


@pytest.mark.parametrize(
    ("name_token", "expected_pages", "expected_document_id"),
    [("NAC", NAC_PAGE_COUNT, NAC_DOCUMENT_ID), ("ITU", ITU_PAGE_COUNT, ITU_DOCUMENT_ID)],
)
def test_real_documents_register_with_known_identity(
    name_token: str, expected_pages: int, expected_document_id: str
) -> None:
    pdf_path = next(path for path in _raw_pdfs() if name_token in path.name)
    document_map = _map_for(pdf_path)
    assert document_map.document.document_id == expected_document_id
    assert len(document_map.pages) == expected_pages
    assert document_map.run.status is ExtractionRunStatus.COMPLETE


@pytest.mark.parametrize("name_token", ["NAC", "ITU"])
def test_no_page_is_silently_lost(name_token: str) -> None:
    pdf_path = next(path for path in _raw_pdfs() if name_token in path.name)
    document_map = _map_for(pdf_path)
    for page in document_map.pages:
        assert page.elements != () or page.status.value == "NO_TEXT"
    assert all(notice.severity.value != "ERROR" for notice in document_map.notices)


@pytest.mark.parametrize("name_token", ["NAC", "ITU"])
def test_every_text_span_is_exact_substring_of_page_text(name_token: str) -> None:
    pdf_path = next(path for path in _raw_pdfs() if name_token in path.name)
    document_map = _map_for(pdf_path)
    for page in document_map.pages:
        for element in page.elements:
            span = document_map.spans[element.span_id]
            if span.extracted_text_exact is None:
                continue
            assert span.char_start is not None and span.char_end is not None
            assert page.text[span.char_start : span.char_end] == span.extracted_text_exact


@pytest.mark.parametrize("name_token", ["NAC", "ITU"])
def test_repeated_extraction_is_deterministic(name_token: str) -> None:
    pdf_path = next(path for path in _raw_pdfs() if name_token in path.name)
    first = _map_for(pdf_path)
    second = _map_for(pdf_path)
    assert first == second


def test_nac_documentary_structure() -> None:
    pdf_path = next(path for path in _raw_pdfs() if "NAC" in path.name)
    document_map = _map_for(pdf_path)
    figure_pages = {
        element.page for element in document_map.elements() if element.kind is ElementKind.FIGURE
    }
    assert figure_pages == NAC_FIGURE_PAGES
    assert any(element.kind is ElementKind.HEADING for element in document_map.elements())
    assert any(element.kind is ElementKind.TABLE for element in document_map.elements())
    headings = {
        element.text for element in document_map.elements() if element.kind is ElementKind.HEADING
    }
    assert any(
        heading is not None and "RECOMENDACIONES PARA EL DIAGNÓSTICO" in heading
        for heading in headings
    )
    figure_spans = [
        document_map.spans[element.span_id]
        for element in document_map.elements()
        if element.kind is ElementKind.FIGURE
    ]
    assert all(SpanQualityFlag.VISUAL_ONLY in span.quality_flags for span in figure_spans)


def test_nac_treatment_heading_is_exact_quoted() -> None:
    pdf_path = next(path for path in _raw_pdfs() if "NAC" in path.name)
    document_map = _map_for(pdf_path)
    quoted = [
        span.extracted_text_exact
        for span in document_map.spans.values()
        if span.extracted_text_exact is not None
        and "TRATAMIENTO ANTIBIÓTICO" in span.extracted_text_exact
    ]
    assert quoted, "the treatment heading must be recoverable as exact source text"


def test_itu_documentary_structure() -> None:
    pdf_path = next(path for path in _raw_pdfs() if "ITU" in path.name)
    document_map = _map_for(pdf_path)
    figure_pages = {
        element.page for element in document_map.elements() if element.kind is ElementKind.FIGURE
    }
    assert figure_pages == ITU_FIGURE_PAGES
    table_pages = {
        element.page for element in document_map.elements() if element.kind is ElementKind.TABLE
    }
    assert table_pages == {1, 4, 5}
    assert any(element.kind is ElementKind.HEADING for element in document_map.elements())


def test_itu_pregnancy_table_cross_page_continuation_is_marked() -> None:
    pdf_path = next(path for path in _raw_pdfs() if "ITU" in path.name)
    document_map = _map_for(pdf_path)
    notices = [
        notice for notice in document_map.notices if notice.code == "POSSIBLE_CROSS_PAGE_TABLE"
    ]
    assert notices, "the page 4-5 table continuation must be recorded explicitly"
    assert any(notice.page == ITU_CROSS_PAGE_TABLE_PAGE for notice in notices)
    flagged = [
        span
        for span in document_map.spans.values()
        if SpanQualityFlag.CROSS_PAGE_CONTINUATION in span.quality_flags
    ]
    assert flagged, "the continued table part must carry the CROSS_PAGE_CONTINUATION flag"


def test_itu_treatment_and_pregnancy_tables_share_pages_4_5() -> None:
    pdf_path = next(path for path in _raw_pdfs() if "ITU" in path.name)
    document_map = _map_for(pdf_path)
    page_four_cells = [
        span
        for page in document_map.pages
        if page.page == PAGE_FOUR
        for element in page.elements
        if element.kind is ElementKind.TABLE_CELL
        for span in [document_map.spans[element.span_id]]
    ]
    page_five_cells = [
        span
        for page in document_map.pages
        if page.page == PAGE_FIVE
        for element in page.elements
        if element.kind is ElementKind.TABLE_CELL
        for span in [document_map.spans[element.span_id]]
    ]
    assert len(page_four_cells) > 0
    assert len(page_five_cells) > 0


def test_notices_are_typed_extraction_notices() -> None:
    for name_token in ("NAC", "ITU"):
        pdf_path = next(path for path in _raw_pdfs() if name_token in path.name)
        document_map = _map_for(pdf_path)
        for notice in document_map.notices:
            assert isinstance(notice, ExtractionNotice)
            assert notice.code
