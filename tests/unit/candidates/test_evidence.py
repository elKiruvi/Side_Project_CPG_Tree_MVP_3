"""Tests for EvidenceBinding and field-level evidence classes."""

from __future__ import annotations

import pytest

from cpg_tree.candidates import EvidenceBinding, EvidenceClass


def test_evidence_binding_construction() -> None:
    binding = EvidenceBinding(
        claim_path="/condition/operands/1/value",
        evidence_class=EvidenceClass.SOURCE_STATED,
        source_span_refs=("span-5",),
        exact_quote="BUN > 30 mg/dL",
    )
    assert binding.claim_path == "/condition/operands/1/value"
    assert binding.exact_quote == "BUN > 30 mg/dL"


def test_evidence_binding_claim_path_must_be_absolute() -> None:
    with pytest.raises(ValueError, match="claim_path"):
        EvidenceBinding(
            claim_path="condition/operands/0",
            evidence_class=EvidenceClass.SOURCE_STATED,
            source_span_refs=("span-1",),
        )


def test_evidence_binding_requires_spans_unless_unresolved() -> None:
    with pytest.raises(ValueError, match="source span"):
        EvidenceBinding(
            claim_path="/condition/value",
            evidence_class=EvidenceClass.EXTRACTED,
        )
    binding = EvidenceBinding(
        claim_path="/condition/value",
        evidence_class=EvidenceClass.UNRESOLVED,
    )
    assert binding.source_span_refs == ()


def test_evidence_binding_rejects_invalid_span_ref() -> None:
    with pytest.raises(ValueError, match="source_span_refs"):
        EvidenceBinding(
            claim_path="/condition/value",
            evidence_class=EvidenceClass.EXTRACTED,
            source_span_refs=("has space",),
        )


def test_evidence_binding_transformation_documents_normalization() -> None:
    binding = EvidenceBinding(
        claim_path="/actions/0/dose_value",
        evidence_class=EvidenceClass.NORMALIZED,
        source_span_refs=("span-7",),
        exact_quote="500 mg",
        transformation="unit normalized to milligrams",
    )
    assert binding.transformation == "unit normalized to milligrams"


def test_evidence_binding_rejects_empty_quote() -> None:
    with pytest.raises(ValueError, match="exact_quote"):
        EvidenceBinding(
            claim_path="/condition/value",
            evidence_class=EvidenceClass.EXTRACTED,
            source_span_refs=("span-1",),
            exact_quote="",
        )
