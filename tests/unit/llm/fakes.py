"""Deterministic provider and DocumentMap fixtures for semantic-pipeline tests."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field

from cpg_tree.candidates.hashing import sha256_hex
from cpg_tree.extraction.document import DocumentElement, DocumentMap, ElementKind, PageMap
from cpg_tree.extraction.runs import ExtractionChannel, ExtractionRun, ExtractionRunStatus
from cpg_tree.extraction.spans import SourceSpan, SpanRepresentation
from cpg_tree.knowledge.documents import SourceDocument
from cpg_tree.llm.provider import ClinicalLLMRequest, ClinicalLLMResponse


@dataclass(slots=True)
class FakeClinicalLLMProvider:
    """Queue structured payloads or raw strings without network access."""

    responses: deque[dict[str, object] | str]
    requests: list[ClinicalLLMRequest] = field(default_factory=list)
    provider_id: str = "fake"
    model_id: str = "fake-model-v1"

    def generate(self, request: ClinicalLLMRequest) -> ClinicalLLMResponse:
        self.requests.append(request)
        if not self.responses:
            raise RuntimeError("fake provider response queue exhausted")
        value = self.responses.popleft()
        if isinstance(value, str):
            return ClinicalLLMResponse(content=value, model_version="fixture-1")
        payload = dict(value)
        payload["run_id"] = request.request_id
        payload.setdefault("segment_id", "document-full")
        return ClinicalLLMResponse(
            content=json.dumps(payload),
            model_version="fixture-1",
            usage={"total_tokens": 1},
        )


def build_document_map() -> DocumentMap:
    """Build a two-span source with enough context for an LLM-authored flow."""
    document_id = "doc-test"
    run_id = "extract-test"
    texts = ("BUN > 30", "If elevated, admit patient")
    spans: dict[str, SourceSpan] = {}
    elements: list[DocumentElement] = []
    page_text = "\n".join(texts)
    offset = 0
    for index, text in enumerate(texts):
        span_id = f"span-{index + 1}"
        spans[span_id] = SourceSpan(
            span_id=span_id,
            document_id=document_id,
            extraction_run_id=run_id,
            page=1,
            representation=SpanRepresentation.TEXT,
            extraction_method="fixture",
            extracted_text_exact=text,
            text_sha256=sha256_hex(text),
            char_start=offset,
            char_end=offset + len(text),
        )
        elements.append(
            DocumentElement(
                element_id=f"element-{index + 1}",
                page=1,
                kind=ElementKind.TEXT,
                order_index=index,
                span_id=span_id,
                text=text,
            )
        )
        offset += len(text) + 1
    return DocumentMap(
        document=SourceDocument(
            document_id=document_id,
            filename="fixture.pdf",
            sha256="a" * 64,
            page_count=1,
            protocol_id="TEST",
            protocol_version="1",
        ),
        run=ExtractionRun(
            run_id=run_id,
            document_id=document_id,
            status=ExtractionRunStatus.COMPLETE,
            started_at="2026-01-01T00:00:00+00:00",
            completed_at="2026-01-01T00:00:00+00:00",
            configuration_hash="b" * 64,
            channels=(
                ExtractionChannel(
                    name="fixture",
                    representation=SpanRepresentation.TEXT,
                    status=ExtractionRunStatus.COMPLETE,
                ),
            ),
        ),
        pages=(PageMap(page=1, text=page_text, elements=tuple(elements)),),
        spans=spans,
    )
