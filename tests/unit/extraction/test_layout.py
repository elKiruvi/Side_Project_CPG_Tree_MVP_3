"""Tests for the structured extraction pipeline over synthetic PDFs."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from unit.extraction.layout_fixtures import (
    build_empty_page_pdf,
    build_heading_pdf,
    build_image_pdf,
    build_list_pdf,
    build_table_pdf,
    build_text_pdf,
)

from cpg_tree.extraction import (
    DocumentMap,
    ElementKind,
    ExtractionRunStatus,
    ExtractionStatus,
    SpanQualityFlag,
    SpanRepresentation,
    extract_document_map,
)

FIXED_TIMESTAMP = "2026-09-29T10:00:00+00:00"
TWO_PAGES = 2
FIRST_PAGE = 1


@pytest.fixture
def two_page_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "sample.pdf"
    build_text_pdf(path, [["linea uno de texto", "linea dos"], ["pagina dos"]])
    return path


def test_document_map_page_count(two_page_pdf: Path) -> None:
    document_map = extract_document_map(two_page_pdf, extracted_at=FIXED_TIMESTAMP)
    assert len(document_map.pages) == TWO_PAGES
    assert [page.page for page in document_map.pages] == [1, TWO_PAGES]


def test_document_map_identity_and_run(two_page_pdf: Path) -> None:
    document_map = extract_document_map(two_page_pdf, extracted_at=FIXED_TIMESTAMP)
    assert document_map.document.document_id.startswith("doc-")
    assert document_map.run.document_id == document_map.document.document_id
    assert document_map.run.status is ExtractionRunStatus.COMPLETE
    assert document_map.run.run_id.startswith("run-doc-")
    assert any(tool.tool == "pymupdf" for tool in document_map.run.tool_versions)


def test_span_ids_are_deterministic_and_content_addressed(two_page_pdf: Path) -> None:
    first = extract_document_map(two_page_pdf, extracted_at=FIXED_TIMESTAMP)
    second = extract_document_map(two_page_pdf, extracted_at=FIXED_TIMESTAMP)
    assert first == second
    assert tuple(first.spans) == tuple(second.spans)


def test_repeated_run_with_same_config_keeps_run_id(two_page_pdf: Path) -> None:
    first = extract_document_map(two_page_pdf, extracted_at=FIXED_TIMESTAMP)
    second = extract_document_map(two_page_pdf, extracted_at=FIXED_TIMESTAMP)
    assert first.run.run_id == second.run.run_id
    assert first.run.configuration_hash == second.run.configuration_hash


def test_every_text_span_is_exact_substring_with_offsets(two_page_pdf: Path) -> None:
    document_map = extract_document_map(two_page_pdf, extracted_at=FIXED_TIMESTAMP)
    for page in document_map.pages:
        for element in page.elements:
            span = document_map.spans[element.span_id]
            if span.extracted_text_exact is None:
                continue
            assert span.char_start is not None
            assert span.char_end is not None
            assert page.text[span.char_start : span.char_end] == span.extracted_text_exact


def test_span_integrity_hash_matches_exact_text(two_page_pdf: Path) -> None:
    document_map = extract_document_map(two_page_pdf, extracted_at=FIXED_TIMESTAMP)
    for span in document_map.spans.values():
        if span.extracted_text_exact is not None:
            assert span.text_sha256 is not None
            assert span.has_exact_text is True


def test_headings_detected_by_uppercase_and_size(tmp_path: Path) -> None:
    path = tmp_path / "heading.pdf"
    build_heading_pdf(path)
    document_map = extract_document_map(path, extracted_at=FIXED_TIMESTAMP)
    headings = [
        element.text for element in document_map.elements() if element.kind is ElementKind.HEADING
    ]
    assert headings == ["RECOMENDACIONES PARA EL DIAGNOSTICO"]


def test_section_paths_follow_heading_chain(tmp_path: Path) -> None:
    path = tmp_path / "heading.pdf"
    build_heading_pdf(path)
    document_map = extract_document_map(path, extracted_at=FIXED_TIMESTAMP)
    body = [element for element in document_map.elements() if element.kind is ElementKind.TEXT]
    assert body
    assert body[0].section_path == ("RECOMENDACIONES PARA EL DIAGNOSTICO",)


def test_list_items_are_classified(tmp_path: Path) -> None:
    path = tmp_path / "list.pdf"
    build_list_pdf(path)
    document_map = extract_document_map(path, extracted_at=FIXED_TIMESTAMP)
    kinds = [element.kind for element in document_map.elements()]
    assert kinds == [ElementKind.LIST_ITEM] * 4


def test_figure_with_caption_and_image_hash(tmp_path: Path) -> None:
    path = tmp_path / "image.pdf"
    build_image_pdf(path)
    document_map = extract_document_map(path, extracted_at=FIXED_TIMESTAMP)
    figures = [element for element in document_map.elements() if element.kind is ElementKind.FIGURE]
    captions = [
        element for element in document_map.elements() if element.kind is ElementKind.CAPTION
    ]
    assert len(figures) == 1
    assert len(captions) == 1
    figure_span = document_map.spans[figures[0].span_id]
    assert figure_span.representation is SpanRepresentation.IMAGE
    assert figure_span.page_image_sha256 is not None
    assert SpanQualityFlag.VISUAL_ONLY in figure_span.quality_flags
    assert captions[0].text == "Figura 1. Flujograma de manejo"


def test_table_with_cells_and_no_duplicated_text(tmp_path: Path) -> None:
    path = tmp_path / "table.pdf"
    build_table_pdf(path)
    document_map = extract_document_map(path, extracted_at=FIXED_TIMESTAMP)
    tables = [element for element in document_map.elements() if element.kind is ElementKind.TABLE]
    cells = [
        element for element in document_map.elements() if element.kind is ElementKind.TABLE_CELL
    ]
    assert len(tables) == 1
    assert {cell.text for cell in cells} == {"Medicamento", "Dosis", "Ceftriaxona", "1 g"}
    assert all(cell.parent_element_id == tables[0].element_id for cell in cells)
    table_span = document_map.spans[tables[0].span_id]
    assert table_span.representation is SpanRepresentation.TABLE
    assert table_span.table_locator == "page 1 table 1"


def test_table_text_not_duplicated_as_text_blocks(tmp_path: Path) -> None:
    path = tmp_path / "table.pdf"
    build_table_pdf(path)
    document_map = extract_document_map(path, extracted_at=FIXED_TIMESTAMP)
    text_elements = [
        element for element in document_map.elements() if element.kind is ElementKind.TEXT
    ]
    assert [element.text for element in text_elements] == [
        "Parrafo posterior a la tabla con texto normal."
    ]


def test_bboxes_are_ordered_and_inside_page(tmp_path: Path) -> None:
    path = tmp_path / "table.pdf"
    build_table_pdf(path)
    document_map = extract_document_map(path, extracted_at=FIXED_TIMESTAMP)
    page = document_map.pages[0]
    assert page.width is not None and page.height is not None
    for element in page.elements:
        assert element.bbox is not None
        x0, y0, x1, y1 = element.bbox
        assert 0 <= x0 <= x1 <= page.width
        assert 0 <= y0 <= y1 <= page.height


def test_empty_page_is_preserved_with_no_text_status(tmp_path: Path) -> None:
    path = tmp_path / "empty.pdf"
    build_empty_page_pdf(path)
    document_map = extract_document_map(path, extracted_at=FIXED_TIMESTAMP)
    assert len(document_map.pages) == 1
    assert document_map.pages[0].status is ExtractionStatus.NO_TEXT
    assert document_map.pages[0].elements == ()
    assert document_map.run.status is ExtractionRunStatus.COMPLETE


def test_corrupt_file_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"this is not a pdf at all")
    with pytest.raises(ValueError, match="cannot open"):
        extract_document_map(path, extracted_at=FIXED_TIMESTAMP)


def test_sparse_page_status(tmp_path: Path) -> None:
    path = tmp_path / "sparse.pdf"
    build_text_pdf(path, [["tiny"]])
    document_map = extract_document_map(path, extracted_at=FIXED_TIMESTAMP)
    assert document_map.pages[0].status is ExtractionStatus.SPARSE_TEXT


def test_clean_document_has_no_notices(tmp_path: Path) -> None:
    path = tmp_path / "text.pdf"
    build_text_pdf(path, [["alpha", "beta"]])
    document_map = extract_document_map(path, extracted_at=FIXED_TIMESTAMP)
    assert document_map.notices == ()
    assert document_map.run.warnings == ()


def test_page_text_is_constructed_from_spans(tmp_path: Path) -> None:
    path = tmp_path / "text.pdf"
    build_text_pdf(path, [["alpha", "beta"]])
    document_map = extract_document_map(path, extracted_at=FIXED_TIMESTAMP)
    assert document_map.pages[0].text == "alpha\nbeta"


def test_map_is_frozen_and_rejects_mutation(tmp_path: Path) -> None:
    path = tmp_path / "text.pdf"
    build_text_pdf(path, [["alpha"]])
    document_map = extract_document_map(path, extracted_at=FIXED_TIMESTAMP)
    with pytest.raises(FrozenInstanceError):
        document_map.pages = ()  # type: ignore[misc]
    assert isinstance(document_map, DocumentMap)
