"""Phase 8 visualization package writer.

Writes the clinician-facing candidate visualization bundle (interactive HTML,
standalone SVG, print view, portable visualization manifest) for one protocol.
All persisted paths are repository-relative. Nothing here changes clinical
semantics or approves anything.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from cpg_tree.candidates.graph import CandidateGraph
from cpg_tree.candidates.graph_serialization import dump_candidate_graph
from cpg_tree.views.clinical_tree import (
    AWAITING_CLINICAL_REVIEW,
    CANDIDATE_MODE,
    VisualizationManifest,
    render_clinical_tree_html,
    render_clinical_tree_svg,
    render_print_view_html,
)

VISUALIZATION_MANIFEST_SCHEMA = "visualization-manifest-v1"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, project_root: Path) -> str:
    root = project_root.resolve()
    resolved = path.resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"artifact path {resolved} is outside the project root {root}") from exc


def write_visualization_package(  # noqa: PLR0913
    *,
    graph: CandidateGraph,
    manifest: VisualizationManifest,
    out_dir: Path,
    project_root: Path,
    phase7_review_manifest_path: Path,
    phase6_review_manifest_path: Path,
    readme_md: str,
    readme_txt: str,
) -> dict[str, Any]:
    """Write the Phase 8 clinician bundle and return the machine manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    html_text = render_clinical_tree_html(graph, manifest)
    svg_text = render_clinical_tree_svg(graph, manifest)
    print_text = render_print_view_html(graph, manifest)
    (out_dir / "clinical_tree.html").write_text(html_text, encoding="utf-8")
    (out_dir / "clinical_tree.svg").write_text(svg_text, encoding="utf-8")
    (out_dir / "print_view.html").write_text(print_text, encoding="utf-8")
    (out_dir / "README.md").write_text(readme_md, encoding="utf-8")

    bundle = out_dir / "clinician_bundle"
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "index.html").write_text(html_text, encoding="utf-8")
    (bundle / "clinical_tree.svg").write_text(svg_text, encoding="utf-8")
    (bundle / "README.txt").write_text(readme_txt, encoding="utf-8")
    review_md_path = out_dir / "clinical_tree_review.md"
    if review_md_path.exists():
        (bundle / "clinical_tree_review.md").write_bytes(review_md_path.read_bytes())
    delivery_md_path = out_dir / "clinical_tree_delivery.md"
    if delivery_md_path.exists():
        (bundle / "clinical_tree_delivery.md").write_bytes(delivery_md_path.read_bytes())

    phase6_manifest = json.loads(phase6_review_manifest_path.read_text(encoding="utf-8"))
    node_ids, relation_ids, issue_ids = _rendered_inventory(svg_text, graph)
    machine_manifest: dict[str, Any] = {
        "schema_version": VISUALIZATION_MANIFEST_SCHEMA,
        "protocol_version_id": graph.protocol_version_id,
        "document_sha256": phase6_manifest.get("document_sha256"),
        "candidate_graph_sha256": sha256_text(dump_candidate_graph(graph)),
        "visualization_mode": CANDIDATE_MODE,
        "review_status": AWAITING_CLINICAL_REVIEW,
        "clinical_approval": False,
        "rendered_node_ids": node_ids,
        "rendered_relation_ids": relation_ids,
        "issue_ids": issue_ids,
        "html_sha256": sha256_file(out_dir / "clinical_tree.html"),
        "svg_sha256": sha256_file(out_dir / "clinical_tree.svg"),
        "print_html_sha256": sha256_file(out_dir / "print_view.html"),
        "source_review_manifest_sha256": sha256_file(phase7_review_manifest_path),
        "artifacts": {
            "clinical_tree.html": _relative(out_dir / "clinical_tree.html", project_root),
            "clinical_tree.svg": _relative(out_dir / "clinical_tree.svg", project_root),
            "print_view.html": _relative(out_dir / "print_view.html", project_root),
            "clinical_tree_review.md": _relative(review_md_path, project_root),
            "clinical_tree_delivery.md": _relative(delivery_md_path, project_root),
            "clinician_bundle": _relative(bundle, project_root),
        },
        "note": (
            "CANDIDATE visualization. ÁRBOL CANDIDATO — PENDIENTE DE VALIDACIÓN "
            "CLÍNICA. clinical_approval: false."
        ),
    }
    (out_dir / "visualization_manifest.json").write_text(
        json.dumps(machine_manifest, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return machine_manifest


def _rendered_inventory(
    svg_text: str, graph: CandidateGraph
) -> tuple[list[str], list[str], list[str]]:
    sequential_ids = {
        relation.candidate_relation_id
        for relation in graph.relations
        if relation.relation_type.value in {"FLOW", "BRANCH"}
    }
    node_ids: set[str] = set()
    relation_ids: set[str] = set()
    for prefix, target in (("n-", node_ids), ("e-", relation_ids)):
        marker = f'id="{prefix}'
        position = 0
        while True:
            start = svg_text.find(marker, position)
            if start == -1:
                break
            end = svg_text.find('"', start + len(marker))
            if end == -1:
                break
            target.add(svg_text[start + len(marker) : end])
            position = end + 1
    unknown_nodes = sorted(node_ids - {rule.candidate_id for rule in graph.rules})
    unknown_edges = sorted(relation_ids - sequential_ids)
    if unknown_nodes:
        raise ValueError(f"visualization references unknown nodes: {unknown_nodes}")
    if unknown_edges:
        raise ValueError(f"visualization references unknown sequential relations: {unknown_edges}")
    return sorted(node_ids), sorted(relation_ids), sorted(issue.issue_id for issue in graph.issues)
