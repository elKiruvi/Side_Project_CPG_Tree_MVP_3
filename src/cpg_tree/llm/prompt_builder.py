"""Prompt loading and deterministic full-document context construction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from cpg_tree.candidates.hashing import stable_json_dumps
from cpg_tree.extraction.document import DocumentMap
from cpg_tree.llm.provider import SemanticStage

_PROMPT_FILES = {
    SemanticStage.OBSERVATIONS: ("observations-v1.md", "observations-v1"),
    SemanticStage.RULES: ("rules-v1.md", "rules-v1"),
    SemanticStage.RELATIONS: ("relations-v1.md", "relations-v1"),
    SemanticStage.RECONCILIATION: ("reconciliation-v1.md", "reconciliation-v1"),
}


@dataclass(frozen=True, slots=True)
class PromptArtifact:
    """Rendered prompt and its version identifier."""

    text: str
    version: str


def build_prompt(
    stage: SemanticStage,
    document_map: DocumentMap,
    *,
    prior_batches: tuple[tuple[str, BaseModel], ...] = (),
) -> PromptArtifact:
    """Build one semantic-pass prompt with full traceable document context."""
    filename, version = _PROMPT_FILES[stage]
    instructions = (Path(__file__).with_name("prompts") / filename).read_text(encoding="utf-8")
    context: dict[str, Any] = {
        "document": _document_context(document_map),
        "prior_batches": {
            name: batch.model_dump(mode="json", exclude_none=True) for name, batch in prior_batches
        },
        "response_contract": {
            "run_id": "must equal the request id supplied below",
            "segment_id": "document-full",
            "strict": True,
        },
    }
    return PromptArtifact(
        text=f"{instructions.rstrip()}\n\nDOCUMENTARY CONTEXT (JSON):\n{stable_json_dumps(context)}",
        version=version,
    )


def _document_context(document_map: DocumentMap) -> dict[str, Any]:
    document = document_map.document
    pages: list[dict[str, Any]] = []
    for page in document_map.pages:
        elements: list[dict[str, Any]] = []
        for element in page.elements:
            span = document_map.spans[element.span_id]
            elements.append(
                {
                    "span_id": span.span_id,
                    "kind": element.kind.value,
                    "representation": span.representation.value,
                    "section_path": list(element.section_path),
                    "text": span.extracted_text_exact,
                    "table_locator": span.table_locator,
                    "quality_flags": [flag.value for flag in span.quality_flags],
                    "bbox": list(span.bbox) if span.bbox is not None else None,
                }
            )
        pages.append({"page": page.page, "status": page.status.value, "elements": elements})
    return {
        "document_id": document.document_id,
        "protocol_id": document.protocol_id,
        "protocol_version": document.protocol_version,
        "filename": document.filename,
        "sha256": document.sha256,
        "extraction_run_id": document_map.run.run_id,
        "extraction_notices": [
            {
                "code": notice.code,
                "severity": notice.severity.value,
                "message": notice.message,
                "page": notice.page,
            }
            for notice in document_map.notices
        ],
        "pages": pages,
    }
