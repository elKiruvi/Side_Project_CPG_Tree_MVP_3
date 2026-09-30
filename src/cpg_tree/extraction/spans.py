"""SourceSpan: the smallest independently citable region of a source document.

A ``SourceSpan`` is a product of one ``ExtractionRun`` (Phase 2). It is
evidence infrastructure, not clinical content: it records where text was
found, how it was recovered, and whether the recovery is trustworthy. It
never interprets clinical meaning.

Span-level identity is assigned by the extraction pipeline (deterministic
``span_id``), and the ``text_sha256`` binds the span to its exact extracted
text so that every later citation can be verified against immutable evidence.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from cpg_tree.knowledge._validation import validate_identifier

_SHA256_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")
_FIRST_PAGE: Final = 1
_BBOX_LENGTH: Final = 4


class SpanRepresentation(StrEnum):
    """How the span content is represented in the source.

    Distinguishes recoverable text (``TEXT``, ``LIST``), structural text
    (``TABLE``, ``FOOTNOTE``), and visual-only evidence (``DIAGRAM``,
    ``IMAGE``, ``PAGE_LAYOUT``) that exists in the source even when no text
    layer was recovered.
    """

    TEXT = "TEXT"
    LIST = "LIST"
    TABLE = "TABLE"
    FOOTNOTE = "FOOTNOTE"
    DIAGRAM = "DIAGRAM"
    IMAGE = "IMAGE"
    PAGE_LAYOUT = "PAGE_LAYOUT"


class SpanQualityFlag(StrEnum):
    """Extraction-quality caveats attached to a span.

    A flag is a machine-readable warning about the recovery process; it never
    silently downgrades the span to absent content.
    """

    OCR = "OCR"
    UNCERTAIN_READING_ORDER = "UNCERTAIN_READING_ORDER"
    TABLE_ALIGNMENT_UNCERTAIN = "TABLE_ALIGNMENT_UNCERTAIN"
    VISUAL_ONLY = "VISUAL_ONLY"
    CROSS_PAGE_CONTINUATION = "CROSS_PAGE_CONTINUATION"


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """Immutable, citable source region produced by an extraction run.

    ``extracted_text_exact`` is the verbatim recovered text; ``normalized_text``
    may hold a normalized or manually transcribed view (for example for
    visual-only evidence). ``text_sha256`` is derived from
    ``extracted_text_exact`` when text is present, and must be ``None`` when no
    exact text exists. ``char_start``/``char_end`` are offsets into the
    document text and are both present or both absent.
    """

    span_id: str
    document_id: str
    extraction_run_id: str
    page: int
    representation: SpanRepresentation
    extraction_method: str
    section_path: str | None = None
    extracted_text_exact: str | None = None
    normalized_text: str | None = None
    text_sha256: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    table_locator: str | None = None
    page_image_sha256: str | None = None
    quality_flags: tuple[SpanQualityFlag, ...] = ()

    def __post_init__(self) -> None:
        validate_identifier(self.span_id, "SourceSpan.span_id")
        validate_identifier(self.document_id, "SourceSpan.document_id")
        validate_identifier(self.extraction_run_id, "SourceSpan.extraction_run_id")
        if self.page < _FIRST_PAGE:
            raise ValueError("SourceSpan.page must be positive")
        if not self.extraction_method:
            raise ValueError("SourceSpan.extraction_method must not be empty")
        if self.section_path is not None and not self.section_path:
            raise ValueError("SourceSpan.section_path must not be empty when set")
        self._validate_text_consistency()
        self._validate_offsets()
        self._validate_bbox()
        if self.table_locator is not None and not self.table_locator:
            raise ValueError("SourceSpan.table_locator must not be empty when set")
        if (
            self.page_image_sha256 is not None
            and _SHA256_PATTERN.fullmatch(self.page_image_sha256) is None
        ):
            raise ValueError("SourceSpan.page_image_sha256 must be a 64-character hex digest")

    def _validate_text_consistency(self) -> None:
        if (self.extracted_text_exact is None) != (self.text_sha256 is None):
            raise ValueError(
                "SourceSpan.text_sha256 must be present exactly when extracted_text_exact is"
            )
        if self.extracted_text_exact is not None and self.text_sha256 is not None:
            computed = hashlib.sha256(self.extracted_text_exact.encode("utf-8")).hexdigest()
            if computed != self.text_sha256:
                raise ValueError("SourceSpan.text_sha256 must match the extracted text")

    def _validate_offsets(self) -> None:
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError("SourceSpan.char_start and char_end must be set together")
        if (
            self.char_start is not None
            and self.char_end is not None
            and (self.char_start < 0 or self.char_end < self.char_start)
        ):
            raise ValueError("SourceSpan.char_start/char_end must satisfy 0 <= start <= end")

    def _validate_bbox(self) -> None:
        if self.bbox is None:
            return
        if len(self.bbox) != _BBOX_LENGTH:
            raise ValueError("SourceSpan.bbox must have exactly 4 coordinates")
        if self.bbox[2] < self.bbox[0] or self.bbox[3] < self.bbox[1]:
            raise ValueError("SourceSpan.bbox coordinates must be ordered (x0 <= x1, y0 <= y1)")

    @property
    def has_exact_text(self) -> bool:
        """True when the span carries verbatim extracted text."""
        return self.extracted_text_exact is not None
