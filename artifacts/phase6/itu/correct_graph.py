"""Phase 6 integrity correction for the CT-PL-197 v06 (ITU) candidate graph.

Phase 6 validation found one technical metadata defect in the Phase 5 artifact:
the BLOCKED relation ``itu-rel-23`` (outpatient upper UTI) had no linked Issue
explaining its block. This module links the existing upper-UTI conflict Issue
to that relation and regenerates the review-bound graph and visuals.

This is a pure metadata-integrity correction: no clinical content (conditions,
actions, relations, thresholds, states) changes.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from cpg_tree.candidates.graph import validate_candidate_graph
from cpg_tree.candidates.graph_serialization import load_candidate_graph, write_candidate_graph
from cpg_tree.views.review_tree import (
    load_projection_manifest,
    render_review_tree_html,
    render_review_tree_svg,
)

ROOT = Path(__file__).resolve().parents[3]
PHASE5_DIR = ROOT / "artifacts/phase5/itu"
OUT_DIR = Path(__file__).parent

_BLOCKED_RELATION = "itu-rel-23"
_EXPLANATORY_ISSUE = "itu-issue-upper-hospital-outpatient"


def correct() -> None:
    """Apply the metadata-linkage correction and write review-bound artifacts."""
    graph = load_candidate_graph((PHASE5_DIR / "candidate_graph.json").read_text(encoding="utf-8"))
    issues = tuple(
        replace(
            issue,
            related_ids=(*issue.related_ids, _BLOCKED_RELATION),
        )
        if issue.issue_id == _EXPLANATORY_ISSUE and _BLOCKED_RELATION not in issue.related_ids
        else issue
        for issue in graph.issues
    )
    graph = replace(graph, issues=issues)
    graph = replace(graph, findings=validate_candidate_graph(graph))

    manifest = load_projection_manifest(PHASE5_DIR / "projection.yaml")
    json_path = OUT_DIR / "candidate_graph.json"
    if json_path.exists():
        json_path.unlink()
    write_candidate_graph(graph, json_path)
    (OUT_DIR / "review_tree.html").write_text(
        render_review_tree_html(graph, manifest), encoding="utf-8"
    )
    (OUT_DIR / "review_tree.svg").write_text(
        render_review_tree_svg(graph, manifest), encoding="utf-8"
    )
    print(f"corrected ITU: linked {_EXPLANATORY_ISSUE} to {_BLOCKED_RELATION}")


if __name__ == "__main__":
    correct()
