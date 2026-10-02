"""Integration validation of committed Phase 8A clinician visualizations.

Verifies candidate mode, warning banner, traceability, graph/visual parity
(no invented edges), portable relative paths, artifact hashes, protocol
isolation, no bundled PDFs, and zero real approvals. No clinical correctness
is asserted.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

import pytest

from cpg_tree.candidates.graph_serialization import dump_candidate_graph, load_candidate_graph
from cpg_tree.views.clinical_tree import (
    CANDIDATE_BANNER,
    load_visualization_manifest,
    render_clinical_tree_html,
    render_clinical_tree_svg,
    render_print_view_html,
)
from cpg_tree.views.coverage_audit import audit_visualization_coverage
from cpg_tree.views.visualization_package import VISUALIZATION_MANIFEST_SCHEMA

ROOT = Path(__file__).resolve().parents[3]
PHASE6 = {"nac": ROOT / "artifacts/phase6/nac", "itu": ROOT / "artifacts/phase6/itu"}
PHASE8 = {"nac": ROOT / "artifacts/phase8/nac", "itu": ROOT / "artifacts/phase8/itu"}

EXPECTED_RULES = {"nac": 29, "itu": 38}
EXPECTED_RELATIONS = {"nac": 33, "itu": 46}
EXPECTED_DRAWN_NODES = {"nac": 28, "itu": 35}
EXPECTED_DRAWN_EDGES = {"nac": 25, "itu": 43}
MIN_CRITICAL_QUESTIONS = 8


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_phase8_artifacts_exist_and_render_deterministically(name: str) -> None:
    graph = load_candidate_graph(
        (PHASE6[name] / "candidate_graph.json").read_text(encoding="utf-8")
    )
    manifest = load_visualization_manifest(PHASE8[name] / "visualization.yaml")
    assert render_clinical_tree_html(graph, manifest) == (
        PHASE8[name] / "clinical_tree.html"
    ).read_text(encoding="utf-8")
    assert render_clinical_tree_svg(graph, manifest) == (
        PHASE8[name] / "clinical_tree.svg"
    ).read_text(encoding="utf-8")
    assert render_print_view_html(graph, manifest) == (PHASE8[name] / "print_view.html").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_machine_manifest_fields(name: str) -> None:
    graph = load_candidate_graph(
        (PHASE6[name] / "candidate_graph.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (PHASE8[name] / "visualization_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["schema_version"] == VISUALIZATION_MANIFEST_SCHEMA
    assert manifest["protocol_version_id"] == graph.protocol_version_id
    assert manifest["visualization_mode"] == "candidate"
    assert manifest["review_status"] == "AWAITING_CLINICAL_REVIEW"
    assert manifest["clinical_approval"] is False
    assert (
        manifest["candidate_graph_sha256"]
        == hashlib.sha256(dump_candidate_graph(graph).encode("utf-8")).hexdigest()
    )
    sequential_ids = {
        relation.candidate_relation_id
        for relation in graph.relations
        if relation.relation_type.value in {"FLOW", "BRANCH"}
    }
    assert set(manifest["rendered_node_ids"]) <= {rule.candidate_id for rule in graph.rules}
    assert set(manifest["rendered_relation_ids"]) <= sequential_ids
    assert manifest["issue_ids"] == sorted(issue.issue_id for issue in graph.issues)
    assert (
        manifest["html_sha256"]
        == hashlib.sha256((PHASE8[name] / "clinical_tree.html").read_bytes()).hexdigest()
    )
    assert (
        manifest["svg_sha256"]
        == hashlib.sha256((PHASE8[name] / "clinical_tree.svg").read_bytes()).hexdigest()
    )
    for artifact_path in manifest["artifacts"].values():
        assert not Path(artifact_path).is_absolute()
        assert ".." not in Path(artifact_path).parts


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_candidate_warning_visible_in_all_views(name: str) -> None:
    html_text = (PHASE8[name] / "clinical_tree.html").read_text(encoding="utf-8")
    print_text = (PHASE8[name] / "print_view.html").read_text(encoding="utf-8")
    for text in (html_text, print_text):
        assert CANDIDATE_BANNER in text
        assert "no ha sido aprobado por personal clínico" in text
    assert html_text.index(CANDIDATE_BANNER) < html_text.index("<main>")


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_graph_visual_parity_no_invented_edges(name: str) -> None:
    graph = load_candidate_graph(
        (PHASE6[name] / "candidate_graph.json").read_text(encoding="utf-8")
    )
    svg_text = (PHASE8[name] / "clinical_tree.svg").read_text(encoding="utf-8")
    node_ids = set(re.findall(r'id="n-([^"]+)"', svg_text))
    edge_ids = set(re.findall(r'id="e-([^"]+)"', svg_text))
    assert node_ids <= {rule.candidate_id for rule in graph.rules}
    sequential_ids = {
        relation.candidate_relation_id
        for relation in graph.relations
        if relation.relation_type.value in {"FLOW", "BRANCH"}
    }
    contextual_ids = {
        relation.candidate_relation_id
        for relation in graph.relations
        if relation.relation_type.value not in {"FLOW", "BRANCH"}
    }
    assert edge_ids <= sequential_ids
    assert not edge_ids & contextual_ids
    for relation in graph.relations:
        if relation.candidate_relation_id in sequential_ids:
            assert f'data-content-hash="{relation.content_hash}"' in svg_text


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_blocked_and_issue_rendering_present(name: str) -> None:
    graph = load_candidate_graph(
        (PHASE6[name] / "candidate_graph.json").read_text(encoding="utf-8")
    )
    svg_text = (PHASE8[name] / "clinical_tree.svg").read_text(encoding="utf-8")
    html_text = (PHASE8[name] / "clinical_tree.html").read_text(encoding="utf-8")
    if any(rule.candidate_state.value == "BLOCKED" for rule in graph.rules):
        assert "bloqueado" in svg_text
        assert "Requiere revisión" in svg_text
    for issue in graph.issues:
        assert issue.issue_id in html_text
    assert "no se inventan alternativas" in html_text


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_phase8_portability_and_relocation(name: str) -> None:
    manifest = json.loads(
        (PHASE8[name] / "visualization_manifest.json").read_text(encoding="utf-8")
    )
    text = json.dumps(manifest)
    assert "/home/" not in text
    with tempfile.TemporaryDirectory() as tmp:
        relocated_root = Path(tmp) / "checkout"
        shutil.copytree(ROOT / "artifacts", relocated_root / "artifacts")
        relocated_manifest = json.loads(
            (relocated_root / "artifacts/phase8" / name / "visualization_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        for artifact_path in relocated_manifest["artifacts"].values():
            assert (relocated_root / Path(artifact_path)).exists()


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_phase8_no_pdfs_and_protocol_isolation(name: str) -> None:
    foreign = "itu-" if name == "nac" else "nac-"
    assert not list((PHASE8[name]).rglob("*.pdf"))
    html_text = (PHASE8[name] / "clinical_tree.html").read_text(encoding="utf-8")
    assert foreign not in html_text
    bundle = PHASE8[name] / "clinician_bundle"
    assert (bundle / "index.html").exists()
    assert (bundle / "clinical_tree.svg").exists()
    assert (bundle / "README.txt").exists()
    assert not list(bundle.rglob("*.pdf"))


def test_real_approvals_remain_zero() -> None:
    for name in ("nac", "itu"):
        manifest = json.loads(
            (PHASE8[name] / "visualization_manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["clinical_approval"] is False
        review_manifest = json.loads(
            (ROOT / f"artifacts/phase7/{name}/review_manifest.json").read_text(encoding="utf-8")
        )
        assert review_manifest["approved_rules"] == 0
        assert review_manifest["approved_relations"] == 0
        assert review_manifest["approved_knowledge_packages"] == 0


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_coverage_audit_every_candidate_reviewable(name: str) -> None:
    graph = load_candidate_graph(
        (PHASE6[name] / "candidate_graph.json").read_text(encoding="utf-8")
    )
    manifest = load_visualization_manifest(PHASE8[name] / "visualization.yaml")
    audit = audit_visualization_coverage(graph, manifest)
    assert audit.rule_reviewable_count == EXPECTED_RULES[name]
    assert audit.relation_reviewable_count == EXPECTED_RELATIONS[name]
    assert audit.drawn_rule_count == EXPECTED_DRAWN_NODES[name]
    assert audit.drawn_relation_count == EXPECTED_DRAWN_EDGES[name]
    assert {entry.rule_id for entry in audit.rule_entries} == {
        rule.candidate_id for rule in graph.rules
    }
    assert {entry.relation_id for entry in audit.relation_entries} == {
        relation.candidate_relation_id for relation in graph.relations
    }
    assert all(entry.reviewable_in for entry in audit.rule_entries)
    assert all(entry.reviewable_in for entry in audit.relation_entries)


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_html_inventory_covers_every_candidate(name: str) -> None:
    graph = load_candidate_graph(
        (PHASE6[name] / "candidate_graph.json").read_text(encoding="utf-8")
    )
    html_text = (PHASE8[name] / "clinical_tree.html").read_text(encoding="utf-8")
    inventory = html_text.split("Inventario completo de candidatos")[1]
    for rule in graph.rules:
        assert rule.candidate_id in inventory
    for relation in graph.relations:
        assert relation.candidate_relation_id in inventory


@pytest.mark.parametrize("name", ("nac", "itu"))
def test_clinical_tree_review_markdown_present_and_warning_visible(name: str) -> None:
    review_md = (PHASE8[name] / "clinical_tree_review.md").read_text(encoding="utf-8")
    normalized = " ".join(review_md.split())
    assert "PENDIENTE DE VALIDACIÓN CLÍNICA" in normalized
    assert "no ha sido" in normalized
    assert "aprobado por personal clínico" in normalized
    assert "Aprobación clínica" in review_md
    assert f"Reglas candidatas: **{EXPECTED_RULES[name]}**" in review_md
    assert f"Relaciones candidatas: **{EXPECTED_RELATIONS[name]}**" in review_md
    assert "## Preguntas críticas antes de aprobar el árbol" in review_md
    assert "## Preguntas de precisión / mejora" in review_md
    assert "## Cómo reportar correcciones" in review_md
    critical_questions = review_md.split("## Preguntas críticas antes de aprobar el árbol")[
        1
    ].split("## Preguntas de precisión / mejora")[0]
    assert critical_questions.count("### Pregunta") >= MIN_CRITICAL_QUESTIONS
    bundle_copy = PHASE8[name] / "clinician_bundle" / "clinical_tree_review.md"
    assert bundle_copy.exists()
    assert bundle_copy.read_text(encoding="utf-8") == review_md


def test_no_raster_artifacts_anywhere_in_phase8() -> None:
    assert not list((ROOT / "artifacts").rglob("*.png"))
    assert not list((ROOT / "artifacts").rglob("*.jpg"))
    assert not list((ROOT / "artifacts").rglob("*.jpeg"))
    assert not list((ROOT / "artifacts").rglob("*.bmp"))
    for name in ("nac", "itu"):
        text = (PHASE8[name] / "visualization_manifest.json").read_text(encoding="utf-8")
        assert "png" not in text.lower()
