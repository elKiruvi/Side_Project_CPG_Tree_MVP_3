"""Tests for SourceDocument identity validation."""

from __future__ import annotations

import pytest

from cpg_tree.knowledge import (
    ProtocolVersion,
    SourceDocument,
    dump_package,
    load_package,
)

VALID_SHA256 = "3a1654757801b7b618661f846f8335ced6fb9e388891d6bca96f1cd81d6f5882"
PAGE_COUNT = 7


def test_source_document_construction() -> None:
    document = SourceDocument(
        document_id="doc-3a1654757801b7b6",
        filename="protocol.pdf",
        sha256=VALID_SHA256,
        byte_size=1089336,
    )
    assert document.document_id == "doc-3a1654757801b7b6"
    assert document.file_format == "pdf"


def test_source_document_requires_identifier() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        SourceDocument(document_id="", filename="x.pdf", sha256=VALID_SHA256)


def test_source_document_requires_filename() -> None:
    with pytest.raises(ValueError, match="filename"):
        SourceDocument(document_id="doc-3a1654757801b7b6", filename="", sha256=VALID_SHA256)


@pytest.mark.parametrize(
    "invalid_sha256",
    ["abc", "Z" * 64, VALID_SHA256[:-1], VALID_SHA256 + "0"],
)
def test_source_document_rejects_invalid_sha256(invalid_sha256: str) -> None:
    with pytest.raises(ValueError, match="64-character"):
        SourceDocument(
            document_id="doc-3a1654757801b7b6",
            filename="x.pdf",
            sha256=invalid_sha256,
        )


def test_source_document_rejects_negative_byte_size() -> None:
    with pytest.raises(ValueError, match="not be negative"):
        SourceDocument(
            document_id="doc-3a1654757801b7b6",
            filename="x.pdf",
            sha256=VALID_SHA256,
            byte_size=-1,
        )


def test_source_document_allows_unknown_byte_size() -> None:
    document = SourceDocument(
        document_id="doc-3a1654757801b7b6",
        filename="x.pdf",
        sha256=VALID_SHA256,
    )
    assert document.byte_size is None


def test_source_document_registration_fields_default_to_none() -> None:
    document = SourceDocument(
        document_id="doc-3a1654757801b7b6",
        filename="x.pdf",
        sha256=VALID_SHA256,
    )
    assert document.media_type is None
    assert document.page_count is None
    assert document.protocol_id is None
    assert document.protocol_version is None
    assert document.approval_date is None


def test_source_document_accepts_registration_metadata() -> None:
    document = SourceDocument(
        document_id="doc-3a1654757801b7b6",
        filename="CT-PL-193_v09.pdf",
        sha256=VALID_SHA256,
        media_type="application/pdf",
        page_count=7,
        protocol_id="CT-PL-193",
        protocol_version="v09",
        approval_date="2024-08-12",
    )
    assert document.page_count == PAGE_COUNT
    assert document.protocol_id == "CT-PL-193"


def test_source_document_rejects_invalid_page_count() -> None:
    with pytest.raises(ValueError, match="page_count"):
        SourceDocument(
            document_id="doc-3a1654757801b7b6",
            filename="x.pdf",
            sha256=VALID_SHA256,
            page_count=0,
        )


def test_source_document_rejects_invalid_registration_fields() -> None:
    with pytest.raises(ValueError, match="media_type"):
        SourceDocument(
            document_id="doc-3a1654757801b7b6",
            filename="x.pdf",
            sha256=VALID_SHA256,
            media_type="",
        )
    with pytest.raises(ValueError, match="protocol_id"):
        SourceDocument(
            document_id="doc-3a1654757801b7b6",
            filename="x.pdf",
            sha256=VALID_SHA256,
            protocol_id="bad id",
        )
    with pytest.raises(ValueError, match="approval_date"):
        SourceDocument(
            document_id="doc-3a1654757801b7b6",
            filename="x.pdf",
            sha256=VALID_SHA256,
            approval_date="not-a-date",
        )


def test_source_document_registration_metadata_survives_package_round_trip(
    synthetic_package: ProtocolVersion,
) -> None:
    registered = SourceDocument(
        document_id="doc-3a1654757801b7b6",
        filename="CT-PL-193_v09.pdf",
        sha256=VALID_SHA256,
        media_type="application/pdf",
        page_count=7,
        protocol_id="CT-PL-193",
        protocol_version="v09",
        approval_date="2024-08-12",
    )
    package = ProtocolVersion(
        protocol=synthetic_package.protocol,
        version=synthetic_package.version,
        documents={"doc-3a1654757801b7b6": registered},
    )
    loaded = load_package(dump_package(package))
    reloaded = loaded.documents["doc-3a1654757801b7b6"]
    assert reloaded == registered
    assert reloaded.protocol_version == "v09"
    assert reloaded.approval_date == "2024-08-12"
