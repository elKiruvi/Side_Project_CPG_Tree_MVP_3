"""Tests for the SourceSpan domain contract."""

from __future__ import annotations

import hashlib

import pytest

from cpg_tree.extraction import SourceSpan, SpanQualityFlag, SpanRepresentation

SPAN_PAGE = 3
TWO_FLAGS = 2


def make_span(**overrides: object) -> SourceSpan:
    fields: dict[str, object] = {
        "span_id": "span-1",
        "document_id": "doc-abc",
        "extraction_run_id": "run-1",
        "page": 3,
        "representation": SpanRepresentation.TEXT,
        "extraction_method": "pypdf-text",
    }
    fields.update(overrides)
    return SourceSpan(**fields)  # type: ignore[arg-type]


def test_source_span_requires_minimal_fields() -> None:
    span = make_span()
    assert span.page == SPAN_PAGE
    assert span.extracted_text_exact is None
    assert span.text_sha256 is None
    assert span.quality_flags == ()


def test_source_span_derives_text_hash_from_exact_text() -> None:
    text = "BUN > 30 mg/dL"
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
    span = make_span(extracted_text_exact=text, text_sha256=expected)
    assert span.text_sha256 == expected
    assert span.has_exact_text is True


def test_source_span_rejects_mismatched_text_hash() -> None:
    text = "BUN > 30 mg/dL"
    wrong = "0" * 64
    with pytest.raises(ValueError, match="text_sha256"):
        make_span(extracted_text_exact=text, text_sha256=wrong)


def test_source_span_rejects_text_hash_without_text() -> None:
    with pytest.raises(ValueError, match="text_sha256"):
        make_span(text_sha256="0" * 64)


def test_source_span_rejects_text_without_hash() -> None:
    with pytest.raises(ValueError, match="text_sha256"):
        make_span(extracted_text_exact="some text", text_sha256=None)


@pytest.mark.parametrize("invalid_page", [0, -1])
def test_source_span_requires_positive_page(invalid_page: int) -> None:
    with pytest.raises(ValueError, match="page"):
        make_span(page=invalid_page)


def test_source_span_offsets_must_come_in_pairs() -> None:
    with pytest.raises(ValueError, match="char_start"):
        make_span(char_start=10)
    with pytest.raises(ValueError, match="char_start"):
        make_span(char_end=10)


def test_source_span_rejects_inverted_offsets() -> None:
    with pytest.raises(ValueError, match="char_start"):
        make_span(char_start=20, char_end=10)


def test_source_span_accepts_ordered_offsets() -> None:
    span = make_span(char_start=0, char_end=25)
    assert (span.char_start, span.char_end) == (0, 25)


def test_source_span_bbox_requires_four_ordered_coordinates() -> None:
    with pytest.raises(ValueError, match="bbox"):
        make_span(bbox=(0.0, 1.0, 2.0))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="bbox"):
        make_span(bbox=(2.0, 0.0, 1.0, 1.0))
    span = make_span(bbox=(0.0, 0.0, 100.0, 50.0))
    assert span.bbox == (0.0, 0.0, 100.0, 50.0)


def test_source_span_visual_only_span_may_carry_normalized_text_without_exact_text() -> None:
    span = make_span(
        representation=SpanRepresentation.DIAGRAM,
        normalized_text="clinical flowchart pending transcription",
        quality_flags=(SpanQualityFlag.VISUAL_ONLY,),
    )
    assert span.extracted_text_exact is None
    assert span.normalized_text is not None


def test_source_span_rejects_bad_page_image_hash() -> None:
    with pytest.raises(ValueError, match="page_image_sha256"):
        make_span(page_image_sha256="not-a-hash")


def test_source_span_accepts_table_locator_and_flags() -> None:
    span = make_span(
        representation=SpanRepresentation.TABLE,
        table_locator="page 4 table 2 row 3",
        quality_flags=(
            SpanQualityFlag.TABLE_ALIGNMENT_UNCERTAIN,
            SpanQualityFlag.CROSS_PAGE_CONTINUATION,
        ),
    )
    assert span.table_locator == "page 4 table 2 row 3"
    assert len(span.quality_flags) == TWO_FLAGS


def test_source_span_rejects_empty_extraction_method() -> None:
    with pytest.raises(ValueError, match="extraction_method"):
        make_span(extraction_method="")
