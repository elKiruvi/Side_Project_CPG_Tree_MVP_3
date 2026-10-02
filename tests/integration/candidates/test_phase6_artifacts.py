"""Integration validation of committed Phase 6 review packets.

These tests bind the Phase 6 packets to the Phase 5 candidate graphs, verify
the integrity corrections, manifest hash bindings, and review-readiness
status. They do not assert clinical correctness.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cpg_tree.candidates.enums import CandidateState
from cpg_tree.candidates.graph_serialization import dump_candidate_graph, load_candidate_graph
from cpg_tree.validation.candidate_structural import (
    READY_FOR_CLINICAL_REVIEW,
    dump_candidate_structure_report,
    validate_candidate_structure,
)
from cpg_tree.validation.review_packet import sha256_file
from cpg_tree.views.review_tree import load_projection_manifest

ROOT = Path(__file__).resolve().parents[3]
PHASE5 = {"nac": ROOT / "artifacts/phase5/nac", "itu": ROOT / "artifacts/phase5/itu"}
PHASE6 = {"nac": ROOT / "artifacts/phase6/nac", "itu": ROOT / "artifacts/phase6/itu"}

KNOWN_DOCUMENT_SHA256 = {
    "nac": "3a1654757801b7b618661f846f8335ced6fb9e388891d6bca96f1cd81d6f5882",
    "itu": "800af94bc0654138a8e213cd1e42ad2e6021a955226a142b36c5b3f24e24777a",
}

NAC_WARNING_COUNT = 2
ITU_WARNING_COUNT = 3


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_phase6_graph_round_trips_and_validates(name: str) -> None:
    graph = load_candidate_graph(
        (PHASE6[name] / "candidate_graph.json").read_text(encoding="utf-8")
    )
    assert dump_candidate_graph(graph) == (PHASE6[name] / "candidate_graph.json").read_text(
        encoding="utf-8"
    )
    manifest = load_projection_manifest(PHASE5[name] / "projection.yaml")
    report = validate_candidate_structure(
        graph,
        manifest,
        artifact_files={
            "html": PHASE6[name] / "review_tree.html",
            "svg": PHASE6[name] / "review_tree.svg",
            "questions": PHASE5[name] / "clinical_review_questions.md",
        },
    )
    assert report.error_count == 0
    assert report.provenance_status == "PASSED"
    assert report.projection_parity_status == "PASSED"
    assert report.review_readiness is READY_FOR_CLINICAL_REVIEW


def test_phase6_integrity_corrections_applied() -> None:
    nac = load_candidate_graph((PHASE6["nac"] / "candidate_graph.json").read_text(encoding="utf-8"))
    itu = load_candidate_graph((PHASE6["itu"] / "candidate_graph.json").read_text(encoding="utf-8"))
    nac_issue = next(
        issue for issue in nac.issues if issue.issue_id == "nac-issue-visual-treatment"
    )
    itu_issue = next(
        issue for issue in itu.issues if issue.issue_id == "itu-issue-upper-hospital-outpatient"
    )
    assert "nac-r26-adjust-to-results" in nac_issue.related_ids
    assert "itu-rel-23" in itu_issue.related_ids


def test_phase6_report_artifacts_are_deterministic() -> None:
    for name in ("nac", "itu"):
        graph = load_candidate_graph(
            (PHASE6[name] / "candidate_graph.json").read_text(encoding="utf-8")
        )
        manifest = load_projection_manifest(PHASE5[name] / "projection.yaml")
        report = validate_candidate_structure(
            graph,
            manifest,
            artifact_files={
                "html": PHASE6[name] / "review_tree.html",
                "svg": PHASE6[name] / "review_tree.svg",
                "questions": PHASE5[name] / "clinical_review_questions.md",
            },
        )
        committed = (PHASE6[name] / "validation_report.json").read_text(encoding="utf-8")
        assert dump_candidate_structure_report(report) == committed


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_review_manifest_binds_hashes(name: str) -> None:
    manifest_data = json.loads((PHASE6[name] / "review_manifest.json").read_text(encoding="utf-8"))
    graph = load_candidate_graph(
        (PHASE6[name] / "candidate_graph.json").read_text(encoding="utf-8")
    )

    assert manifest_data["schema"] == "review-manifest-v1"
    assert manifest_data["protocol_version_id"] == graph.protocol_version_id
    assert manifest_data["document_sha256"] == KNOWN_DOCUMENT_SHA256[name]
    assert manifest_data["document_id"] == graph.document_id
    assert manifest_data["candidate_hashes"] == {
        rule.candidate_id: rule.content_hash for rule in graph.rules
    }
    assert manifest_data["relation_hashes"] == {
        relation.candidate_relation_id: relation.content_hash for relation in graph.relations
    }
    assert manifest_data["validation_report_sha256"] == sha256_file(
        PHASE6[name] / "validation_report.json"
    )
    for artifact in manifest_data["review_bound_artifacts"]:
        assert artifact["sha256"] == sha256_file(ROOT / Path(artifact["path"]))
    for artifact in manifest_data["phase5_review_artifacts"]:
        assert artifact["sha256"] == sha256_file(ROOT / Path(artifact["path"]))
    assert (ROOT / Path(manifest_data["clinical_review_questions"])).is_file()


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_review_manifest_paths_are_portable(name: str) -> None:
    manifest_data = json.loads((PHASE6[name] / "review_manifest.json").read_text(encoding="utf-8"))
    stored_paths = (
        [artifact["path"] for artifact in manifest_data["review_bound_artifacts"]]
        + [artifact["path"] for artifact in manifest_data["phase5_review_artifacts"]]
        + [manifest_data["clinical_review_questions"]]
    )
    assert stored_paths
    for stored in stored_paths:
        assert not Path(stored).is_absolute()
        assert ".." not in Path(stored).parts
        assert (ROOT / Path(stored)).exists()
    for artifact in manifest_data["phase5_review_artifacts"]:
        assert artifact["sha256"] == sha256_file(Path(artifact["path"]))


def test_phase6_no_candidate_approved_and_protocol_isolated() -> None:
    for name, foreign in (("nac", "itu-"), ("itu", "nac-")):
        graph = load_candidate_graph(
            (PHASE6[name] / "candidate_graph.json").read_text(encoding="utf-8")
        )
        assert {rule.candidate_state for rule in graph.rules} <= {
            CandidateState.PROPOSED,
            CandidateState.BLOCKED,
        }
        html_text = (PHASE6[name] / "review_tree.html").read_text(encoding="utf-8")
        assert foreign not in html_text
        assert "NOT CLINICALLY APPROVED" in html_text


def test_expected_warning_counts() -> None:
    nac = json.loads((PHASE6["nac"] / "validation_report.json").read_text(encoding="utf-8"))
    itu = json.loads((PHASE6["itu"] / "validation_report.json").read_text(encoding="utf-8"))
    assert nac["warning_count"] == NAC_WARNING_COUNT
    assert itu["warning_count"] == ITU_WARNING_COUNT
    assert all(item["severity"] != "ERROR" for item in nac["findings"])
    assert all(item["severity"] != "ERROR" for item in itu["findings"])
    assert nac["cycles"] == []
    assert itu["cycles"] == []
