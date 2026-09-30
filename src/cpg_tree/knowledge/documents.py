"""Source document identity for the provenance chain."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from cpg_tree.knowledge._validation import validate_identifier, validate_iso_date

_SHA256_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")
_MIN_SIZE: Final = 0
_MIN_PAGE_COUNT: Final = 1


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """Immutable identity and registration metadata of a raw source document.

    Identity is content-addressed: ``document_id`` derives from the SHA-256
    of the exact document bytes, so identical bytes always produce the same
    identity and any byte change produces a new one. The filename is recorded
    for human reference only; it is never part of the identity.

    The optional registration fields (``media_type``, ``page_count``,
    ``protocol_id``, ``protocol_version``, ``approval_date``) record document
    metadata required by the MVP 3 pipeline. They never participate in
    content identity: a registered document with missing metadata is still
    the same source bytes.
    """

    document_id: str
    filename: str
    sha256: str
    file_format: str = "pdf"
    byte_size: int | None = None
    media_type: str | None = None
    page_count: int | None = None
    protocol_id: str | None = None
    protocol_version: str | None = None
    approval_date: str | None = None

    def __post_init__(self) -> None:
        validate_identifier(self.document_id, "SourceDocument.document_id")
        if not self.filename:
            raise ValueError("SourceDocument.filename must not be empty")
        if _SHA256_PATTERN.fullmatch(self.sha256) is None:
            raise ValueError("SourceDocument.sha256 must be a 64-character hex digest")
        if self.byte_size is not None and self.byte_size < _MIN_SIZE:
            raise ValueError("SourceDocument.byte_size must not be negative")
        if self.media_type is not None and not self.media_type:
            raise ValueError("SourceDocument.media_type must not be empty when set")
        if self.page_count is not None and self.page_count < _MIN_PAGE_COUNT:
            raise ValueError("SourceDocument.page_count must be positive when set")
        if self.protocol_id is not None:
            validate_identifier(self.protocol_id, "SourceDocument.protocol_id")
        if self.protocol_version is not None and not self.protocol_version:
            raise ValueError("SourceDocument.protocol_version must not be empty when set")
        if self.approval_date is not None:
            validate_iso_date(self.approval_date, "SourceDocument.approval_date")
