"""Source ingestion and extraction layer.

The pipeline is protocol-agnostic: it fingerprints document bytes, extracts
page-level text, and produces a page-level fragment inventory. It never
interprets clinical content, tables, or images.

``SourceSpan`` and ``ExtractionRun`` are the Phase 1 domain contracts for the
multichannel source inventory (Phase 2); they are pipeline evidence, not
clinical knowledge.
"""

from cpg_tree.extraction.artifacts import write_artifacts
from cpg_tree.extraction.extractor import (
    count_embedded_images,
    document_id_from_sha256,
    extract_pdf,
    fingerprint_bytes,
)
from cpg_tree.extraction.model import (
    ExtractionRecord,
    ExtractionResult,
    ExtractionStatus,
    PageExtraction,
)
from cpg_tree.extraction.runs import (
    ExtractionChannel,
    ExtractionRun,
    ExtractionRunStatus,
    ToolVersion,
)
from cpg_tree.extraction.sectioning import detect_section
from cpg_tree.extraction.spans import SourceSpan, SpanQualityFlag, SpanRepresentation

__all__ = [
    "ExtractionChannel",
    "ExtractionRecord",
    "ExtractionResult",
    "ExtractionRun",
    "ExtractionRunStatus",
    "ExtractionStatus",
    "PageExtraction",
    "SourceSpan",
    "SpanQualityFlag",
    "SpanRepresentation",
    "ToolVersion",
    "count_embedded_images",
    "detect_section",
    "document_id_from_sha256",
    "extract_pdf",
    "fingerprint_bytes",
    "write_artifacts",
]
