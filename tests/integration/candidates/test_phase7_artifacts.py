"""Integration validation of committed Phase 7A clinical review packages.

Verifies package integrity, portability, hash binding, protocol isolation,
AWAITING_CLINICAL_REVIEW status, zero approvals, and reviewer-facing
artifacts. No clinical approval is asserted; the packages await real review.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cpg_tree.candidates.graph_serialization import dump_candidate_graph, load_candidate_graph
from cpg_tree.review.package import AWAITING_CLINICAL_REVIEW
from cpg_tree.review.package_validation import validate_review_package

ROOT = Path(__file__).resolve().parents[3]
PHASE6 = {"nac": ROOT / "artifacts/phase6/nac", "itu": ROOT / "artifacts/phase6/itu"}
PHASE7 = {"nac": ROOT / "artifacts/phase7/nac", "itu": ROOT / "artifacts/phase7/itu"}

ENUM_SMELLS = ("CandidateRelationType", "CandidateRuleType", "RelationType.")

MIN_CLINICIAN_QUESTIONS_LENGTH = 500


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_phase7_package_validates_without_errors(name: str) -> None:
    graph = load_candidate_graph(
        (PHASE6[name] / "candidate_graph.json").read_text(encoding="utf-8")
    )
    findings = validate_review_package(PHASE7[name], graph, project_root=ROOT)
    assert not [finding for finding in findings if finding.severity.value == "ERROR"]


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_phase7_package_status_and_zero_approvals(name: str) -> None:
    manifest = json.loads((PHASE7[name] / "review_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == AWAITING_CLINICAL_REVIEW
    assert manifest["approved_rules"] == 0
    assert manifest["approved_relations"] == 0
    assert manifest["approved_knowledge_packages"] == 0
    assert manifest["approval_policy"] == "policy_pending"


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_phase7_package_binds_exact_graph_and_artifacts(name: str) -> None:
    graph = load_candidate_graph(
        (PHASE6[name] / "candidate_graph.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((PHASE7[name] / "review_manifest.json").read_text(encoding="utf-8"))
    graph_hash = hashlib.sha256(dump_candidate_graph(graph).encode("utf-8")).hexdigest()
    assert manifest["graph_content_hash"] == graph_hash
    assert manifest["protocol_version_id"] == graph.protocol_version_id
    for entry in manifest["bundle_files"]:
        path_obj = Path(entry["path"])
        assert not path_obj.is_absolute()
        assert ".." not in path_obj.parts
        target = ROOT / path_obj
        assert target.exists()
        assert entry["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_phase7_template_covers_every_candidate(name: str) -> None:
    graph = load_candidate_graph(
        (PHASE6[name] / "candidate_graph.json").read_text(encoding="utf-8")
    )
    template = json.loads((PHASE7[name] / "review_template.json").read_text(encoding="utf-8"))
    assert template["schema"] == "review-submission-v1"
    catalog = {(entry["item_type"], entry["item_id"]): entry for entry in template["catalog"]}
    for rule in graph.rules:
        entry = catalog[("RULE", rule.candidate_id)]
        assert entry["content_hash"] == rule.content_hash
        assert entry["candidate_revision"] == rule.revision
    for relation in graph.relations:
        entry = catalog[("RELATION", relation.candidate_relation_id)]
        assert entry["content_hash"] == relation.content_hash
    assert template["decisions"] == []
    assert template["feedback"] == []


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_phase7_reviewer_facing_artifacts_present(name: str) -> None:
    bundle = PHASE7[name] / "review_bundle"
    assert (bundle / "index.html").exists()
    assert (bundle / "review_tree.html").exists()
    assert (bundle / "review_instructions.md").exists()
    questions = (bundle / "review_questions.md").read_text(encoding="utf-8")
    assert len(questions) > MIN_CLINICIAN_QUESTIONS_LENGTH
    assert "NO ha sido aprobada clínicamente" in questions
    for smell in ENUM_SMELLS:
        assert smell not in questions
    evidence = (bundle / "evidence.md").read_text(encoding="utf-8")
    assert "VISUAL SOURCE / MANUAL REVIEW REQUIRED" in evidence
    assert not list(bundle.rglob("*.pdf"))


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_phase7_packages_are_protocol_isolated(name: str) -> None:
    foreign = "itu-" if name == "nac" else "nac-"
    bundle = PHASE7[name] / "review_bundle"
    manifest_text = (PHASE7[name] / "review_manifest.json").read_text(encoding="utf-8")
    assert foreign not in manifest_text
    questions = (bundle / "review_questions.md").read_text(encoding="utf-8")
    assert foreign not in questions


def test_real_approval_counts_are_zero() -> None:
    for name in ("nac", "itu"):
        manifest = json.loads((PHASE7[name] / "review_manifest.json").read_text(encoding="utf-8"))
        assert manifest["approved_rules"] == 0
        assert manifest["approved_relations"] == 0
        assert manifest["approved_knowledge_packages"] == 0
        graph = load_candidate_graph(
            (PHASE6[name] / "candidate_graph.json").read_text(encoding="utf-8")
        )
        assert {rule.candidate_state.value for rule in graph.rules} <= {
            "PROPOSED",
            "BLOCKED",
        }
