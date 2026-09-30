"""Structured document model: DocumentMap, PageMap, and document elements.

This module defines the Phase 2 documentary layer. A ``DocumentMap`` records
WHAT IS PRESENT IN THE DOCUMENT — pages, layout blocks, headings, lists,
tables, table cells, figures, captions, and the ``SourceSpan`` inventory that
backs them. It never interprets clinical meaning, sequence, or rules.

Coordinate convention: bounding boxes use PyMuPDF's page coordinate system —
origin at the TOP-LEFT corner, y increasing DOWNWARD, units in PDF points,
always satisfying x0 <= x1 and y0 <= y1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from cpg_tree.extraction.model import ExtractionStatus
from cpg_tree.extraction.runs import ExtractionRun
from cpg_tree.extraction.spans import SourceSpan
from cpg_tree.knowledge._validation import validate_identifier
from cpg_tree.knowledge.documents import SourceDocument

_FIRST_PAGE: Final = 1
_FIRST_ORDER_INDEX: Final = 0
_BBOX_LENGTH: Final = 4


class ElementKind(StrEnum):
    """Documentary category of one element.

    Classification is heuristic and generic. ``UNKNOWN`` is the fallback when
    no category can be assigned confidently; fidelity is preferred over false
    precision. Footnotes are not distinguished yet: the backend cannot detect
    them reliably, so they remain ``TEXT``.
    """

    TEXT = "TEXT"
    HEADING = "HEADING"
    LIST_ITEM = "LIST_ITEM"
    TABLE = "TABLE"
    TABLE_CELL = "TABLE_CELL"
    FIGURE = "FIGURE"
    CAPTION = "CAPTION"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class DocumentElement:
    """One documentary element on a page.

    ``span_id`` anchors the element to the ``SourceSpan`` carrying its
    extracted evidence. ``text`` mirrors the span's exact text (``None`` for
    elements without extractable text, such as ``TABLE`` and ``FIGURE``).
    ``section_path`` is the documentary heading chain that encloses the
    element — documentary structure only, never clinical flow.
    ``parent_element_id`` nests cells under their table.
    """

    element_id: str
    page: int
    kind: ElementKind
    order_index: int
    span_id: str
    bbox: tuple[float, float, float, float] | None = None
    text: str | None = None
    section_path: tuple[str, ...] = ()
    parent_element_id: str | None = None

    def __post_init__(self) -> None:
        validate_identifier(self.element_id, "DocumentElement.element_id")
        if self.page < _FIRST_PAGE:
            raise ValueError("DocumentElement.page must be positive")
        if self.order_index < _FIRST_ORDER_INDEX:
            raise ValueError("DocumentElement.order_index must not be negative")
        validate_identifier(self.span_id, "DocumentElement.span_id")
        if (
            self.text is None
            and self.kind is not ElementKind.TABLE
            and self.kind is not ElementKind.FIGURE
        ):
            raise ValueError(f"{self.kind.value} elements require text; got None")
        if self.text is not None and not self.text:
            raise ValueError("DocumentElement.text must not be empty when set")
        if self.parent_element_id is not None:
            validate_identifier(self.parent_element_id, "DocumentElement.parent_element_id")
        for title in self.section_path:
            if not title:
                raise ValueError("DocumentElement.section_path entries must not be empty")
        if self.bbox is not None and len(self.bbox) != _BBOX_LENGTH:
            raise ValueError("DocumentElement.bbox must have exactly 4 coordinates")


@dataclass(frozen=True, slots=True)
class PageMap:
    """Documentary inventory of one page.

    ``text`` is the page's recovered text, built by joining the exact text of
    every text-bearing span in element order; every text-bearing span of the
    page is therefore an exact substring of ``text``, and ``char_start`` /
    ``char_end`` on spans are offsets into ``text``.
    """

    page: int
    text: str
    elements: tuple[DocumentElement, ...]
    width: float | None = None
    height: float | None = None
    image_count: int = 0
    status: ExtractionStatus = ExtractionStatus.OK

    def __post_init__(self) -> None:
        if self.page < _FIRST_PAGE:
            raise ValueError("PageMap.page must be positive")
        if self.image_count < 0:
            raise ValueError("PageMap.image_count must not be negative")
        if self.status is ExtractionStatus.NO_TEXT and self.text:
            raise ValueError("NO_TEXT status requires empty page text")
        if not self.text and self.status not in (
            ExtractionStatus.NO_TEXT,
            ExtractionStatus.EXTRACTION_ERROR,
        ):
            raise ValueError("empty page text requires NO_TEXT or EXTRACTION_ERROR status")
        order_indices = [element.order_index for element in self.elements]
        if order_indices != sorted(order_indices):
            raise ValueError("PageMap.elements must be ordered by order_index")
        if order_indices != list(range(len(order_indices))):
            raise ValueError("PageMap element order_index values must be contiguous from 0")
        for element in self.elements:
            if element.page != self.page:
                raise ValueError("PageMap.elements entries must belong to this page")


class ExtractionNoticeSeverity(StrEnum):
    """Severity of a technical extraction notice.

    Technical notices are about the extraction process (unreadable regions,
    uncertain table recovery, possible cross-page continuations). They are
    deliberately separate from clinical ``Issue`` objects in the candidate
    layer.
    """

    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass(frozen=True, slots=True)
class ExtractionNotice:
    """One explicit, machine-readable technical extraction notice."""

    code: str
    severity: ExtractionNoticeSeverity
    message: str
    page: int | None = None

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("ExtractionNotice.code must not be empty")
        if not self.message:
            raise ValueError("ExtractionNotice.message must not be empty")
        if self.page is not None and self.page < _FIRST_PAGE:
            raise ValueError("ExtractionNotice.page must be positive when set")


@dataclass(frozen=True, slots=True)
class DocumentMap:
    """Structured, validated documentary representation of one source file.

    This is the canonical Phase 2 output: document identity, the
    ``ExtractionRun`` that produced it, per-page structure, the citable
    ``SourceSpan`` inventory, and explicit technical notices. Failures are
    recorded explicitly; content is never silently omitted.
    """

    document: SourceDocument
    run: ExtractionRun
    pages: tuple[PageMap, ...]
    spans: dict[str, SourceSpan] = field(default_factory=dict)
    notices: tuple[ExtractionNotice, ...] = ()

    def __post_init__(self) -> None:
        if self.run.document_id != self.document.document_id:
            raise ValueError("DocumentMap document and run document ids must match")
        if [page.page for page in self.pages] != list(range(_FIRST_PAGE, len(self.pages) + 1)):
            raise ValueError("DocumentMap.pages must be consecutive starting at 1")
        self._check_spans()
        self._check_elements()

    def _check_spans(self) -> None:
        for span_id, span in self.spans.items():
            if span.span_id != span_id:
                raise ValueError(
                    f"DocumentMap.spans key {span_id!r} does not match span_id {span.span_id!r}"
                )
            if span.document_id != self.document.document_id:
                raise ValueError(f"span {span_id!r} must reference the map document")
            if span.extraction_run_id != self.run.run_id:
                raise ValueError(f"span {span_id!r} must reference the map run")

    def _check_elements(self) -> None:
        element_ids: dict[str, DocumentElement] = {}
        for page in self.pages:
            for element in page.elements:
                if element.element_id in element_ids:
                    raise ValueError(f"duplicate element id {element.element_id!r}")
                element_ids[element.element_id] = element
                if element.span_id not in self.spans:
                    raise ValueError(
                        f"element {element.element_id!r} references unknown span {element.span_id!r}"
                    )
                span = self.spans[element.span_id]
                if span.page != element.page:
                    raise ValueError(
                        f"element {element.element_id!r} and its span disagree on the page"
                    )
                if element.parent_element_id is not None:
                    parent = element_ids.get(element.parent_element_id)
                    if parent is None:
                        raise ValueError(
                            f"element {element.element_id!r} references unknown parent "
                            f"{element.parent_element_id!r}"
                        )
                    if parent.page != element.page:
                        raise ValueError(
                            f"element {element.element_id!r} and its parent disagree on the page"
                        )

    def elements(self) -> tuple[DocumentElement, ...]:
        """Return all elements across pages in deterministic page/order_index order."""
        return tuple(element for page in self.pages for element in page.elements)

    def pages_with_text(self) -> tuple[PageMap, ...]:
        """Return pages whose status indicates recovered text."""
        return tuple(page for page in self.pages if page.status is ExtractionStatus.OK)
