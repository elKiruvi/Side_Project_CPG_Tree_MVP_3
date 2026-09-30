"""Structured document extraction over PyMuPDF.

This module is the Phase 2 extraction backend: it converts a source PDF into
a deterministic ``DocumentMap`` (document, run, pages, elements, spans,
notices) using PyMuPDF's layout information. It records WHAT IS PRESENT — text
blocks, headings, lists, tables, cells, figures, captions — with positions.
It never interprets clinical meaning and never invents content.

Design decisions (documented, deterministic):

- Page text is constructed by joining the exact text of text-bearing spans in
  element order, so every text-bearing span is an exact substring of the page
  text and span ``char_start``/``char_end`` are offsets into it.
- Element order per page: text blocks in PyMuPDF reading order, then tables
  (their cells immediately after the table element), then figures in image
  inventory order. Visual elements are never interleaved arbitrarily.
- Text blocks fully inside a detected table are removed from the block
  inventory so table content is represented once, by the cell spans.
- Tables are detected with two strategies ("lines" then "text"); "lines"
  results are preferred and overlapping "text" results are discarded.
- Text-strategy tables carry ``TABLE_ALIGNMENT_UNCERTAIN``.
- Figures carry ``VISUAL_ONLY`` and, when extractable, the SHA-256 of the
  embedded image bytes; figure transcription remains a future human step.
- A possible cross-page table continuation is flagged (never joined) when one
  page ends with a table and the next begins with one.
- There is no OCR in this phase; native text extraction is the only text
  channel. No LLM is involved anywhere.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any, Final

import pymupdf

from cpg_tree.extraction.document import (
    DocumentElement,
    DocumentMap,
    ElementKind,
    ExtractionNotice,
    ExtractionNoticeSeverity,
    PageMap,
)
from cpg_tree.extraction.extractor import fingerprint_bytes
from cpg_tree.extraction.model import ExtractionStatus
from cpg_tree.extraction.runs import (
    ExtractionChannel,
    ExtractionRun,
    ExtractionRunStatus,
    ToolVersion,
)
from cpg_tree.extraction.spans import SourceSpan, SpanQualityFlag, SpanRepresentation
from cpg_tree.knowledge.documents import SourceDocument

_HAS_LETTER: Final = re.compile(r"[^\W\d_]", re.UNICODE)
_LIST_ITEM_PATTERN: Final = re.compile(
    r"^\s*(?:[\u2022\u2023\u25cf\u25e6*\-\u2013]|\d+[.)]|[a-z][.)])\s+\S"
)
_BULLET_START: Final = re.compile(r"^\s*[\u2022\u2023\u25cf\u25e6*\-\u2013]")
_HEADING_MAX_LENGTH: Final = 100
_HEADING_MIN_LENGTH: Final = 2
_HEADING_SIZE_RATIO: Final = 1.25
_HEADING_LEVEL_SIZE_RATIO: Final = 1.15
_CAPTION_DISTANCE: Final = 25.0
_CAPTION_MIN_OVERLAP: Final = 0.3
_TABLE_OVERLAP_RATIO: Final = 0.3
_TABLE_MAX_ROWS_TEXT_STRATEGY: Final = 40
_TABLE_MAX_COLUMNS_TEXT_STRATEGY: Final = 12
_TEXT_TABLE_MAX_WIDTH_RATIO: Final = 0.75
_TEXT_TABLE_MAX_HEIGHT_RATIO: Final = 0.45
_TEXT_TABLE_MAX_AREA_RATIO: Final = 0.25
_DEFAULT_SPARSE_THRESHOLD: Final = 100
_CONFIG_HASH_PREFIX_LENGTH: Final = 16
_BBOX_LENGTH: Final = 4
_CROSS_PAGE_TABLE_TOP_RATIO: Final = 0.30

type _Quad = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class _TextLine:
    bbox: _Quad
    text: str
    max_font_size: float
    order: int


@dataclass(frozen=True, slots=True)
class _IdContext:
    page_number: int
    document_id: str
    run_id: str

    def element_id(self, order_index: int) -> str:
        return f"{self.document_id}-p{self.page_number:03d}-e{order_index:03d}"


@dataclass
class _SectionState:
    """Documentary heading chain carried across pages."""

    chain: tuple[str, ...] = ()
    last_heading_size: float | None = None

    def record_heading(self, line: _TextLine) -> None:
        title = line.text.strip()
        if (
            self.last_heading_size is not None
            and line.max_font_size > self.last_heading_size * _HEADING_LEVEL_SIZE_RATIO
        ):
            self.chain = (title,)
        else:
            self.chain = (*self.chain, title)
        self.last_heading_size = line.max_font_size


@dataclass(frozen=True, slots=True)
class _TableHit:
    bbox: _Quad
    strategy: str
    rows: tuple[tuple[str | None, ...], ...]
    cells: tuple[_Quad | None, ...] = ()


def extract_document_map(
    path: str | Path,
    *,
    extracted_at: str | None = None,
    sparse_threshold: int = _DEFAULT_SPARSE_THRESHOLD,
) -> DocumentMap:
    """Extract a source PDF into a deterministic, validated ``DocumentMap``.

    Repeated extraction of the same bytes with the same backend version and
    configuration produces an equal map when ``extracted_at`` is fixed.
    Timestamps are run stamps, never content identity. A file that cannot be
    opened raises ``ValueError``; per-page failures are recorded explicitly
    (``EXTRACTION_ERROR`` pages, notices, ``PARTIAL``/``FAILED`` run).
    """
    pdf_path = Path(path)
    data = pdf_path.read_bytes()
    sha256 = fingerprint_bytes(data)
    document_id = f"doc-{sha256[:16]}"
    stamp = extracted_at if extracted_at is not None else _now_iso()
    config = _build_config(sparse_threshold)
    configuration_hash = fingerprint_bytes(_stable_config_json(config).encode("utf-8"))
    run_id = f"run-{document_id}-{configuration_hash[:_CONFIG_HASH_PREFIX_LENGTH]}"

    document = SourceDocument(
        document_id=document_id,
        filename=pdf_path.name,
        sha256=sha256,
        file_format="pdf",
        byte_size=len(data),
    )

    try:
        with pymupdf.open(pdf_path) as doc:
            pages, spans, notices = _extract_pages(doc, document_id, run_id, sparse_threshold)
    except pymupdf.FileDataError as exc:
        raise ValueError(f"cannot open {pdf_path.name} as a PDF document") from exc

    status = _run_status(pages)
    run = ExtractionRun(
        run_id=run_id,
        document_id=document_id,
        status=status,
        started_at=stamp,
        completed_at=stamp,
        configuration_hash=configuration_hash,
        channels=(
            ExtractionChannel(
                name="pymupdf-layout",
                representation=SpanRepresentation.PAGE_LAYOUT,
                status=status,
            ),
        ),
        tool_versions=(ToolVersion(tool="pymupdf", version=pymupdf.__version__),),
        warnings=tuple(
            f"[{notice.severity.value}] {notice.code}: {notice.message}" for notice in notices
        ),
    )
    return DocumentMap(
        document=document,
        run=run,
        pages=pages,
        spans=spans,
        notices=notices,
    )


def _build_config(sparse_threshold: int) -> dict[str, Any]:
    return {
        "schema": "document-map-v1",
        "backend": "pymupdf",
        "backend_version": pymupdf.__version__,
        "sparse_threshold": sparse_threshold,
        "heading_size_ratio": _HEADING_SIZE_RATIO,
        "caption_distance": _CAPTION_DISTANCE,
    }


def _stable_config_json(config: dict[str, Any]) -> str:
    return json.dumps(config, sort_keys=True, separators=(",", ":"))


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _run_status(pages: tuple[PageMap, ...]) -> ExtractionRunStatus:
    if not pages:
        return ExtractionRunStatus.FAILED
    if all(page.status is ExtractionStatus.EXTRACTION_ERROR for page in pages):
        return ExtractionRunStatus.FAILED
    if any(page.status is ExtractionStatus.EXTRACTION_ERROR for page in pages):
        return ExtractionRunStatus.PARTIAL
    return ExtractionRunStatus.COMPLETE


def _extract_pages(
    doc: pymupdf.Document,
    document_id: str,
    run_id: str,
    sparse_threshold: int,
) -> tuple[tuple[PageMap, ...], dict[str, SourceSpan], tuple[ExtractionNotice, ...]]:
    pages: list[PageMap] = []
    spans: dict[str, SourceSpan] = {}
    notices: list[ExtractionNotice] = []
    section_state = _SectionState()
    previous_ended_with_table = False
    for page_number in range(1, doc.page_count + 1):
        page = doc[page_number - 1]
        context = _IdContext(page_number=page_number, document_id=document_id, run_id=run_id)
        try:
            page_map, page_spans, page_notices, ends_with_table = _extract_page(
                page=page,
                context=context,
                sparse_threshold=sparse_threshold,
                section_state=section_state,
                previous_ended_with_table=previous_ended_with_table,
            )
        except Exception as exc:
            pages.append(
                PageMap(
                    page=page_number,
                    text="",
                    elements=(),
                    status=ExtractionStatus.EXTRACTION_ERROR,
                )
            )
            notices.append(
                ExtractionNotice(
                    code="PAGE_EXTRACTION_ERROR",
                    severity=ExtractionNoticeSeverity.ERROR,
                    message=f"page {page_number} extraction failed: {exc}",
                    page=page_number,
                )
            )
            previous_ended_with_table = False
            continue
        pages.append(page_map)
        spans.update(page_spans)
        notices.extend(page_notices)
        previous_ended_with_table = ends_with_table
    return tuple(pages), spans, tuple(notices)


def _extract_page(
    *,
    page: pymupdf.Page,
    context: _IdContext,
    sparse_threshold: int,
    section_state: _SectionState,
    previous_ended_with_table: bool,
) -> tuple[
    PageMap,
    dict[str, SourceSpan],
    list[ExtractionNotice],
    bool,
]:
    width = float(page.rect.width)
    height = float(page.rect.height)
    images = _inventory_images(page)
    tables = _detect_tables(page)
    lines = _read_text_lines(page)
    kept_lines = [line for line in lines if not _inside_any_table(line.bbox, tables)]
    median_size = _median_font_size(kept_lines)

    notices: list[ExtractionNotice] = []
    elements: list[DocumentElement] = []
    page_spans: dict[str, SourceSpan] = {}

    _append_text_line_elements(
        elements,
        page_spans,
        context=context,
        kept_lines=kept_lines,
        median_size=median_size,
        images=images,
        section_state=section_state,
    )
    _append_table_elements(
        elements,
        page_spans,
        notices,
        context=context,
        tables=tables,
        height=height,
        section_path=section_state.chain,
        previous_ended_with_table=previous_ended_with_table,
    )
    _append_figure_elements(
        elements,
        page_spans,
        notices,
        context=context,
        images=images,
        page=page,
        section_path=section_state.chain,
    )

    page_text, char_offsets = _build_page_text(elements, page_spans)
    for span in page_spans.values():
        offsets = char_offsets.get(span.span_id)
        if offsets is not None:
            object.__setattr__(span, "char_start", offsets[0])
            object.__setattr__(span, "char_end", offsets[1])

    status = _status_for(len(page_text), sparse_threshold)
    ends_with_table = bool(elements) and elements[-1].kind is ElementKind.TABLE_CELL
    return (
        PageMap(
            page=context.page_number,
            text=page_text,
            elements=tuple(elements),
            width=width,
            height=height,
            image_count=len(images),
            status=status,
        ),
        page_spans,
        notices,
        ends_with_table,
    )


def _append_text_line_elements(  # noqa: PLR0913 — accumulates shared page state
    elements: list[DocumentElement],
    page_spans: dict[str, SourceSpan],
    *,
    context: _IdContext,
    kept_lines: Sequence[_TextLine],
    median_size: float | None,
    images: list[dict[str, Any]],
    section_state: _SectionState,
) -> None:
    for line in kept_lines:
        kind, is_heading = _classify_line(line, median_size)
        if kind is ElementKind.TEXT and _caption_owner(line, images) is not None:
            kind = ElementKind.CAPTION
        if is_heading:
            section_state.record_heading(line)
        span = _make_text_span(context, len(elements), kind, line)
        elements.append(
            _make_element(
                span,
                kind=kind,
                order_index=len(elements),
                section_path=section_state.chain,
            )
        )
        page_spans[span.span_id] = span


def _append_table_elements(  # noqa: PLR0913 — accumulates shared page state
    elements: list[DocumentElement],
    page_spans: dict[str, SourceSpan],
    notices: list[ExtractionNotice],
    *,
    context: _IdContext,
    tables: Sequence[_TableHit],
    height: float,
    section_path: tuple[str, ...],
    previous_ended_with_table: bool,
) -> None:
    for table_sequence, table in enumerate(tables, start=1):
        flags: tuple[SpanQualityFlag, ...] = (
            (SpanQualityFlag.TABLE_ALIGNMENT_UNCERTAIN,) if table.strategy == "text" else ()
        )
        if (
            previous_ended_with_table
            and table_sequence == 1
            and table.bbox[1] <= height * _CROSS_PAGE_TABLE_TOP_RATIO
        ):
            flags += (SpanQualityFlag.CROSS_PAGE_CONTINUATION,)
            notices.append(
                ExtractionNotice(
                    code="POSSIBLE_CROSS_PAGE_TABLE",
                    severity=ExtractionNoticeSeverity.WARNING,
                    message=(
                        f"page {context.page_number} has a table among its first elements "
                        "right after a table-ended page; possible cross-page continuation "
                        "(parts are preserved separately, never joined)"
                    ),
                    page=context.page_number,
                )
            )
        table_span = _make_table_span(context, len(elements), table, table_sequence, flags)
        elements.append(
            _make_element(
                table_span,
                kind=ElementKind.TABLE,
                order_index=len(elements),
                section_path=section_path,
            )
        )
        page_spans[table_span.span_id] = table_span
        for row_index, row in enumerate(table.rows):
            for column_index, cell_text in enumerate(row):
                if not cell_text:
                    continue
                cell_bbox = _cell_bbox(table, row_index, column_index)
                cell_span = _make_cell_span(
                    context,
                    len(elements),
                    table=table,
                    table_sequence=table_sequence,
                    row_index=row_index,
                    column_index=column_index,
                    cell_bbox=cell_bbox,
                    cell_text=cell_text,
                )
                elements.append(
                    _make_element(
                        cell_span,
                        kind=ElementKind.TABLE_CELL,
                        order_index=len(elements),
                        section_path=section_path,
                        parent_element_id=table_span.span_id,
                    )
                )
                page_spans[cell_span.span_id] = cell_span


def _append_figure_elements(  # noqa: PLR0913 — accumulates shared page state
    elements: list[DocumentElement],
    page_spans: dict[str, SourceSpan],
    notices: list[ExtractionNotice],
    *,
    context: _IdContext,
    images: list[dict[str, Any]],
    page: pymupdf.Page,
    section_path: tuple[str, ...],
) -> None:
    for image_index, image in enumerate(images):
        image_sha256 = _hash_image(page, image["xref"])
        figure_span = _make_figure_span(context, len(elements), _image_bbox(image), image_sha256)
        elements.append(
            _make_element(
                figure_span,
                kind=ElementKind.FIGURE,
                order_index=len(elements),
                section_path=section_path,
            )
        )
        page_spans[figure_span.span_id] = figure_span
        if image_sha256 is None:
            notices.append(
                ExtractionNotice(
                    code="IMAGE_BYTES_UNREADABLE",
                    severity=ExtractionNoticeSeverity.WARNING,
                    message=(
                        f"page {context.page_number} figure {image_index + 1} present but "
                        "its embedded bytes could not be read"
                    ),
                    page=context.page_number,
                )
            )


def _inventory_images(page: pymupdf.Page) -> list[dict[str, Any]]:
    info_entries = [dict(info) for info in page.get_image_info()]
    xrefs = [xref for xref, *_ in page.get_images()]
    for index, entry in enumerate(info_entries):
        entry["xref"] = xrefs[index] if index < len(xrefs) else None
    return info_entries


def _image_bbox(image: dict[str, Any]) -> _Quad | None:
    bbox = image.get("bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) == _BBOX_LENGTH:
        return (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    return None


def _hash_image(page: pymupdf.Page, xref: object) -> str | None:
    if not isinstance(xref, int):
        return None
    try:
        return hashlib.sha256(page.parent.extract_image(xref)["image"]).hexdigest()
    except Exception:
        return None


def _read_text_lines(page: pymupdf.Page) -> tuple[_TextLine, ...]:
    """Read text lines in PyMuPDF reading order, with bboxes and font sizes.

    Lines (not blocks) are the canonical text granularity: these documents
    lay out full pages in single text frames, so block-level splitting would
    merge unrelated documentary elements.
    """
    lines: list[_TextLine] = []
    page_dict = page.get_text("dict")
    for block in page_dict.get("blocks", ()):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", ()):
            spans = line.get("spans", ())
            text = "".join(span.get("text", "") for span in spans)
            if not text or not text.strip():
                continue
            bbox = line.get("bbox")
            if not isinstance(bbox, (list, tuple)) or len(bbox) != _BBOX_LENGTH:
                continue
            max_font_size = max(
                (
                    float(span["size"])
                    for span in spans
                    if isinstance(span.get("size"), (int, float))
                ),
                default=0.0,
            )
            lines.append(
                _TextLine(
                    bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
                    text=text,
                    max_font_size=max_font_size,
                    order=len(lines),
                )
            )
    return tuple(lines)


def _median_font_size(lines: Sequence[_TextLine]) -> float | None:
    sizes = [line.max_font_size for line in lines if line.max_font_size > 0]
    if not sizes:
        return None
    return float(median(sizes))


def _detect_tables(page: pymupdf.Page) -> tuple[_TableHit, ...]:
    accepted: list[_TableHit] = []
    for strategy in ("lines", "text"):
        try:
            found = page.find_tables(strategy=strategy).tables
        except Exception:
            found = []
        for table in found:
            if strategy == "text" and (
                table.row_count > _TABLE_MAX_ROWS_TEXT_STRATEGY
                or table.col_count > _TABLE_MAX_COLUMNS_TEXT_STRATEGY
                or not _text_table_bounded(table, page)
            ):
                continue
            bbox = table.bbox
            hit_bbox = (
                float(bbox[0]),
                float(bbox[1]),
                float(bbox[2]),
                float(bbox[3]),
            )
            if any(
                _overlaps(hit_bbox, existing.bbox, _TABLE_OVERLAP_RATIO) for existing in accepted
            ):
                continue
            rows = tuple(
                tuple(str(cell) if cell is not None else None for cell in row)
                for row in table.extract()
            )
            cells = tuple(
                (float(c[0]), float(c[1]), float(c[2]), float(c[3]))
                for c in table.cells
                if len(c) == _BBOX_LENGTH
            )
            accepted.append(
                _TableHit(bbox=hit_bbox, strategy=strategy, rows=rows, cells=tuple(cells))
            )
    return tuple(accepted)


def _inside_any_table(block_bbox: _Quad, tables: tuple[_TableHit, ...]) -> bool:
    return any(_overlaps(block_bbox, table.bbox, _TABLE_OVERLAP_RATIO) for table in tables)


def _text_table_bounded(table: pymupdf.table.Table, page: pymupdf.Page) -> bool:
    """Reject text-strategy tables that span most of the page.

    The text strategy guesses column breaks and frequently produces huge
    false-positive tables over narrative text. Only compact, clearly bounded
    tables are accepted; everything else stays generic text.
    """
    bbox = table.bbox
    width_ratio: float = (bbox[2] - bbox[0]) / page.rect.width
    height_ratio: float = (bbox[3] - bbox[1]) / page.rect.height
    area_ratio: float = width_ratio * height_ratio
    return (
        width_ratio <= _TEXT_TABLE_MAX_WIDTH_RATIO
        and height_ratio <= _TEXT_TABLE_MAX_HEIGHT_RATIO
        and area_ratio <= _TEXT_TABLE_MAX_AREA_RATIO
    )


def _overlaps(first: _Quad, second: _Quad, ratio: float) -> bool:
    intersection_x = max(0.0, min(first[2], second[2]) - max(first[0], second[0]))
    intersection_y = max(0.0, min(first[3], second[3]) - max(first[1], second[1]))
    intersection_area = intersection_x * intersection_y
    if intersection_area <= 0:
        return False
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    return first_area > 0 and intersection_area / first_area >= ratio


def _classify_line(line: _TextLine, median_size: float | None) -> tuple[ElementKind, bool]:
    stripped = line.text.strip()
    is_heading = _is_heading(line, median_size)
    if is_heading:
        return ElementKind.HEADING, True
    if _LIST_ITEM_PATTERN.match(line.text):
        return ElementKind.LIST_ITEM, False
    if not stripped:
        return ElementKind.UNKNOWN, False
    return ElementKind.TEXT, False


def _is_heading(line: _TextLine, median_size: float | None) -> bool:
    stripped = line.text.strip()
    if _BULLET_START.match(stripped) or "\n" in stripped:
        return False
    if not _HEADING_MIN_LENGTH <= len(stripped) <= _HEADING_MAX_LENGTH:
        return False
    if _HAS_LETTER.search(stripped) is None:
        return False
    if not any(character.islower() for character in stripped):
        return True
    return median_size is not None and line.max_font_size >= median_size * _HEADING_SIZE_RATIO


def _caption_owner(line: _TextLine, images: list[dict[str, Any]]) -> int | None:
    for index, image in enumerate(images):
        image_bbox = _image_bbox(image)
        if image_bbox is None:
            continue
        below_image = (
            line.bbox[1] >= image_bbox[3] and line.bbox[1] - image_bbox[3] <= _CAPTION_DISTANCE
        )
        horizontal_overlap = min(line.bbox[2], image_bbox[2]) - max(line.bbox[0], image_bbox[0])
        image_width = image_bbox[2] - image_bbox[0]
        if (
            below_image
            and image_width > 0
            and horizontal_overlap / image_width >= _CAPTION_MIN_OVERLAP
        ):
            return index
    return None


def _representation_for(kind: ElementKind) -> SpanRepresentation:
    if kind is ElementKind.LIST_ITEM:
        return SpanRepresentation.LIST
    return SpanRepresentation.TEXT


def _make_span(  # noqa: PLR0913 — primitive span constructor for one documentary element
    context: _IdContext,
    *,
    order_index: int,
    representation: SpanRepresentation,
    extraction_method: str,
    bbox: _Quad | None,
    text: str | None,
    quality_flags: tuple[SpanQualityFlag, ...] = (),
    table_locator: str | None = None,
    page_image_sha256: str | None = None,
) -> SourceSpan:
    text_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest() if text is not None else None
    return SourceSpan(
        span_id=context.element_id(order_index),
        document_id=context.document_id,
        extraction_run_id=context.run_id,
        page=context.page_number,
        representation=representation,
        extraction_method=extraction_method,
        extracted_text_exact=text,
        text_sha256=text_sha256,
        bbox=bbox,
        table_locator=table_locator,
        page_image_sha256=page_image_sha256,
        quality_flags=quality_flags,
    )


def _make_element(
    span: SourceSpan,
    *,
    kind: ElementKind,
    order_index: int,
    section_path: tuple[str, ...],
    parent_element_id: str | None = None,
) -> DocumentElement:
    return DocumentElement(
        element_id=span.span_id,
        page=span.page,
        kind=kind,
        order_index=order_index,
        span_id=span.span_id,
        bbox=span.bbox,
        text=span.extracted_text_exact,
        section_path=section_path,
        parent_element_id=parent_element_id,
    )


def _make_text_span(
    context: _IdContext, order_index: int, kind: ElementKind, line: _TextLine
) -> SourceSpan:
    return _make_span(
        context,
        order_index=order_index,
        representation=_representation_for(kind),
        extraction_method="pymupdf-text",
        bbox=line.bbox,
        text=line.text,
    )


def _make_table_span(
    context: _IdContext,
    order_index: int,
    table: _TableHit,
    table_sequence: int,
    flags: tuple[SpanQualityFlag, ...],
) -> SourceSpan:
    return _make_span(
        context,
        order_index=order_index,
        representation=SpanRepresentation.TABLE,
        extraction_method=f"pymupdf-find-tables:{table.strategy}",
        bbox=table.bbox,
        text=None,
        quality_flags=flags,
        table_locator=f"page {context.page_number} table {table_sequence}",
    )


def _make_cell_span(  # noqa: PLR0913 — cell provenance requires row/column context
    context: _IdContext,
    order_index: int,
    *,
    table: _TableHit,
    table_sequence: int,
    row_index: int,
    column_index: int,
    cell_bbox: _Quad | None,
    cell_text: str,
) -> SourceSpan:
    return _make_span(
        context,
        order_index=order_index,
        representation=SpanRepresentation.TABLE,
        extraction_method=f"pymupdf-find-tables:{table.strategy}",
        bbox=cell_bbox,
        text=cell_text,
        table_locator=(
            f"page {context.page_number} table {table_sequence} "
            f"cell r{row_index + 1}c{column_index + 1}"
        ),
    )


def _make_figure_span(
    context: _IdContext,
    order_index: int,
    bbox: _Quad | None,
    image_sha256: str | None,
) -> SourceSpan:
    return _make_span(
        context,
        order_index=order_index,
        representation=SpanRepresentation.IMAGE,
        extraction_method="pymupdf-image",
        bbox=bbox,
        text=None,
        quality_flags=(SpanQualityFlag.VISUAL_ONLY,),
        page_image_sha256=image_sha256,
    )


def _build_page_text(
    elements: list[DocumentElement],
    page_spans: dict[str, SourceSpan],
) -> tuple[str, dict[str, tuple[int, int]]]:
    text_parts: list[str] = []
    offsets: dict[str, tuple[int, int]] = {}
    cursor = 0
    for element in elements:
        span = page_spans[element.span_id]
        if span.extracted_text_exact is None:
            continue
        text_parts.append(span.extracted_text_exact)
        offsets[span.span_id] = (cursor, cursor + len(span.extracted_text_exact))
        cursor += len(span.extracted_text_exact) + 1
    return "\n".join(text_parts), offsets


def _cell_bbox(table: _TableHit, row_index: int, column_index: int) -> _Quad | None:
    column_count = max((len(row) for row in table.rows), default=0)
    cell_index = row_index * column_count + column_index
    if cell_index < len(table.cells):
        return table.cells[cell_index]
    return None


def _status_for(char_count: int, sparse_threshold: int) -> ExtractionStatus:
    if char_count == 0:
        return ExtractionStatus.NO_TEXT
    if char_count <= sparse_threshold:
        return ExtractionStatus.SPARSE_TEXT
    return ExtractionStatus.OK
