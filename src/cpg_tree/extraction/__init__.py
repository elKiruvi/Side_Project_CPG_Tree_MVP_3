"""Source ingestion and extraction layer.

The pipeline is protocol-agnostic: it fingerprints document bytes, extracts
page-level text, and produces a structured documentary inventory. It never
interprets clinical content, tables, or images.

``SourceSpan`` and ``ExtractionRun`` are the Phase 1 domain contracts for the
multichannel source inventory; ``DocumentMap`` (Phase 2) is the structured,
validated documentary representation that later phases cite as evidence.
"""

from cpg_tree.extraction.artifacts import write_artifacts, write_document_map_artifacts
from cpg_tree.extraction.document import (
    DocumentElement,
    DocumentMap,
    ElementKind,
    ExtractionNotice,
    ExtractionNoticeSeverity,
    PageMap,
)
from cpg_tree.extraction.extractor import (
    count_embedded_images,
    document_id_from_sha256,
    extract_pdf,
    fingerprint_bytes,
)
from cpg_tree.extraction.layout import extract_document_map
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
from cpg_tree.extraction.serialization import dump_document_map, load_document_map
from cpg_tree.extraction.spans import SourceSpan, SpanQualityFlag, SpanRepresentation

__all__ = [
    "DocumentElement",
    "DocumentMap",
    "ElementKind",
    "ExtractionChannel",
    "ExtractionNotice",
    "ExtractionNoticeSeverity",
    "ExtractionRecord",
    "ExtractionResult",
    "ExtractionRun",
    "ExtractionRunStatus",
    "ExtractionStatus",
    "PageExtraction",
    "PageMap",
    "SourceSpan",
    "SpanQualityFlag",
    "SpanRepresentation",
    "ToolVersion",
    "count_embedded_images",
    "detect_section",
    "document_id_from_sha256",
    "dump_document_map",
    "extract_document_map",
    "extract_pdf",
    "fingerprint_bytes",
    "load_document_map",
    "write_artifacts",
    "write_document_map_artifacts",
]
