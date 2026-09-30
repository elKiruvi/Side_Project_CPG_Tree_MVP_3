"""Deterministic YAML serialization for the DocumentMap model.

Serialization is explicit: only YAML-safe primitives are produced, enums are
serialized as their string values, and no ``!!python/object`` tags are used.
It is a reproducibility/debugging utility for intermediate artifacts
(``data/02_intermediate/``); the in-memory ``DocumentMap`` remains the
canonical documentary structure.
"""

# ruff: noqa: TRY004

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import yaml

from cpg_tree.extraction.document import (
    DocumentElement,
    DocumentMap,
    ElementKind,
    ExtractionNotice,
    ExtractionNoticeSeverity,
    PageMap,
)
from cpg_tree.extraction.model import ExtractionStatus
from cpg_tree.extraction.runs import (
    ExtractionChannel,
    ExtractionRun,
    ExtractionRunStatus,
    ToolVersion,
)
from cpg_tree.extraction.spans import SourceSpan, SpanQualityFlag, SpanRepresentation
from cpg_tree.knowledge.documents import SourceDocument


def dump_document_map(document_map: DocumentMap) -> str:
    """Serialize a DocumentMap into deterministic YAML text."""
    return str(yaml.safe_dump(_map_to_dict(document_map), sort_keys=False, allow_unicode=True))


def load_document_map(text: str) -> DocumentMap:
    """Deserialize YAML text produced by dump_document_map back into a map."""
    data = yaml.safe_load(text)
    if not isinstance(data, Mapping):
        raise ValueError("document map YAML root must be a mapping")
    document_data = data.get("document")
    run_data = data.get("run")
    if not isinstance(document_data, Mapping) or not isinstance(run_data, Mapping):
        raise ValueError("document map YAML requires 'document' and 'run' mappings")
    spans_raw = data.get("spans")
    spans = (
        {str(key): _span_from_dict(entry) for key, entry in _as_mapping(spans_raw, "spans").items()}
        if spans_raw is not None
        else {}
    )
    pages = tuple(_page_from_dict(raw) for raw in _as_list(data.get("pages"), "pages"))
    notices = tuple(_notice_from_dict(raw) for raw in _as_list(data.get("notices"), "notices"))
    return DocumentMap(
        document=_document_from_dict(document_data),
        run=_run_from_dict(run_data),
        pages=pages,
        spans=spans,
        notices=notices,
    )


def _map_to_dict(document_map: DocumentMap) -> dict[str, Any]:
    return {
        "document": _document_to_dict(document_map.document),
        "run": _run_to_dict(document_map.run),
        "pages": [_page_to_dict(page) for page in document_map.pages],
        "spans": {span_id: _span_to_dict(span) for span_id, span in document_map.spans.items()},
        "notices": [_notice_to_dict(notice) for notice in document_map.notices],
    }


def _document_to_dict(document: SourceDocument) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "document_id": document.document_id,
        "filename": document.filename,
        "sha256": document.sha256,
        "file_format": document.file_format,
    }
    if document.byte_size is not None:
        payload["byte_size"] = document.byte_size
    if document.media_type is not None:
        payload["media_type"] = document.media_type
    if document.page_count is not None:
        payload["page_count"] = document.page_count
    if document.protocol_id is not None:
        payload["protocol_id"] = document.protocol_id
    if document.protocol_version is not None:
        payload["protocol_version"] = document.protocol_version
    if document.approval_date is not None:
        payload["approval_date"] = document.approval_date
    return payload


def _document_from_dict(data: Mapping[str, Any]) -> SourceDocument:
    return SourceDocument(
        document_id=data.get("document_id"),
        filename=data.get("filename"),
        sha256=data.get("sha256"),
        file_format=data.get("file_format", "pdf"),
        byte_size=data.get("byte_size"),
        media_type=data.get("media_type"),
        page_count=data.get("page_count"),
        protocol_id=data.get("protocol_id"),
        protocol_version=data.get("protocol_version"),
        approval_date=data.get("approval_date"),
    )


def _run_to_dict(run: ExtractionRun) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": run.run_id,
        "document_id": run.document_id,
        "status": run.status.value,
        "started_at": run.started_at,
        "configuration_hash": run.configuration_hash,
        "channels": [_channel_to_dict(channel) for channel in run.channels],
    }
    if run.completed_at is not None:
        payload["completed_at"] = run.completed_at
    if run.tool_versions:
        payload["tool_versions"] = [
            {"tool": tool.tool, "version": tool.version} for tool in run.tool_versions
        ]
    if run.warnings:
        payload["warnings"] = list(run.warnings)
    return payload


def _run_from_dict(data: Mapping[str, Any]) -> ExtractionRun:
    channels_raw = data.get("channels")
    return ExtractionRun(
        run_id=data.get("run_id"),
        document_id=data.get("document_id"),
        status=ExtractionRunStatus(data.get("status")),
        started_at=data.get("started_at"),
        completed_at=data.get("completed_at"),
        configuration_hash=data.get("configuration_hash"),
        channels=tuple(_channel_from_dict(raw) for raw in _as_list(channels_raw, "channels")),
        tool_versions=tuple(
            ToolVersion(tool=raw.get("tool"), version=raw.get("version"))
            for raw in _as_list(data.get("tool_versions"), "tool_versions")
        ),
        warnings=tuple(_as_list(data.get("warnings"), "warnings")),
    )


def _channel_to_dict(channel: ExtractionChannel) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": channel.name,
        "representation": channel.representation.value,
        "status": channel.status.value,
    }
    if channel.notes is not None:
        payload["notes"] = channel.notes
    return payload


def _channel_from_dict(data: Mapping[str, Any]) -> ExtractionChannel:
    return ExtractionChannel(
        name=data.get("name"),
        representation=SpanRepresentation(data.get("representation")),
        status=ExtractionRunStatus(data.get("status")),
        notes=data.get("notes"),
    )


def _page_to_dict(page: PageMap) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "page": page.page,
        "text": page.text,
        "elements": [_element_to_dict(element) for element in page.elements],
        "status": page.status.value,
    }
    if page.width is not None:
        payload["width"] = page.width
    if page.height is not None:
        payload["height"] = page.height
    payload["image_count"] = page.image_count
    return payload


def _page_from_dict(data: Mapping[str, Any]) -> PageMap:
    return PageMap(
        page=data.get("page"),
        text=data.get("text"),
        elements=tuple(
            _element_from_dict(raw) for raw in _as_list(data.get("elements"), "elements")
        ),
        width=data.get("width"),
        height=data.get("height"),
        image_count=data.get("image_count", 0),
        status=ExtractionStatus(data.get("status")),
    )


def _element_to_dict(element: DocumentElement) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "element_id": element.element_id,
        "page": element.page,
        "kind": element.kind.value,
        "order_index": element.order_index,
        "span_id": element.span_id,
    }
    if element.bbox is not None:
        payload["bbox"] = list(element.bbox)
    if element.text is not None:
        payload["text"] = element.text
    if element.section_path:
        payload["section_path"] = list(element.section_path)
    if element.parent_element_id is not None:
        payload["parent_element_id"] = element.parent_element_id
    return payload


def _element_from_dict(data: Mapping[str, Any]) -> DocumentElement:
    bbox = data.get("bbox")
    return DocumentElement(
        element_id=data.get("element_id"),
        page=data.get("page"),
        kind=ElementKind(data.get("kind")),
        order_index=data.get("order_index"),
        span_id=data.get("span_id"),
        bbox=tuple(bbox) if bbox is not None else None,
        text=data.get("text"),
        section_path=tuple(_as_list(data.get("section_path"), "section_path")),
        parent_element_id=data.get("parent_element_id"),
    )


_SPAN_OPTIONAL_TEXT_FIELDS = (
    "section_path",
    "extracted_text_exact",
    "normalized_text",
    "text_sha256",
    "char_start",
    "char_end",
    "table_locator",
    "page_image_sha256",
)


def _span_to_dict(span: SourceSpan) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "span_id": span.span_id,
        "document_id": span.document_id,
        "extraction_run_id": span.extraction_run_id,
        "page": span.page,
        "representation": span.representation.value,
        "extraction_method": span.extraction_method,
    }
    for field_name in _SPAN_OPTIONAL_TEXT_FIELDS:
        value = getattr(span, field_name)
        if value is not None:
            payload[field_name] = value
    if span.bbox is not None:
        payload["bbox"] = list(span.bbox)
    if span.quality_flags:
        payload["quality_flags"] = [flag.value for flag in span.quality_flags]
    return payload


def _span_from_dict(data: Mapping[str, Any]) -> SourceSpan:
    bbox = data.get("bbox")
    return SourceSpan(
        span_id=data.get("span_id"),
        document_id=data.get("document_id"),
        extraction_run_id=data.get("extraction_run_id"),
        page=data.get("page"),
        representation=SpanRepresentation(data.get("representation")),
        extraction_method=data.get("extraction_method"),
        section_path=data.get("section_path"),
        extracted_text_exact=data.get("extracted_text_exact"),
        normalized_text=data.get("normalized_text"),
        text_sha256=data.get("text_sha256"),
        char_start=data.get("char_start"),
        char_end=data.get("char_end"),
        bbox=tuple(bbox) if bbox is not None else None,
        table_locator=data.get("table_locator"),
        page_image_sha256=data.get("page_image_sha256"),
        quality_flags=tuple(
            SpanQualityFlag(value) for value in _as_list(data.get("quality_flags"), "quality_flags")
        ),
    )


def _notice_to_dict(notice: ExtractionNotice) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": notice.code,
        "severity": notice.severity.value,
        "message": notice.message,
    }
    if notice.page is not None:
        payload["page"] = notice.page
    return payload


def _notice_from_dict(data: Mapping[str, Any]) -> ExtractionNotice:
    return ExtractionNotice(
        code=data.get("code"),
        severity=ExtractionNoticeSeverity(data.get("severity")),
        message=data.get("message"),
        page=data.get("page"),
    )


def _as_list(raw: object, field_name: str) -> tuple[Any, ...]:
    """Require a list-like value, so strings are never silently split."""
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise ValueError(f"{field_name} must be a list; got {type(raw).__name__}")
    return tuple(raw)


def _as_mapping(raw: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"{field_name} must be a mapping; got {type(raw).__name__}")
    return raw
