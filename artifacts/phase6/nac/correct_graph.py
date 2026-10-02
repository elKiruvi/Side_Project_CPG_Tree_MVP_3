"""Phase 6 integrity correction for the CT-PL-193 v9 (NAC) candidate graph.

Phase 6 validation found one technical metadata defect in the Phase 5 artifact:
the BLOCKED rule ``nac-r26-adjust-to-results`` had no linked Issue explaining
its block. This module links the existing visual-evidence Issue to that rule
and regenerates the review-bound graph and visuals.

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
PHASE5_DIR = ROOT / "artifacts/phase5/nac"
OUT_DIR = Path(__file__).parent

_BLOCKED_RULE = "nac-r26-adjust-to-results"
_EXPLANATORY_ISSUE = "nac-issue-visual-treatment"


def correct() -> None:
    """Apply the metadata-linkage correction and write review-bound artifacts."""
    graph = load_candidate_graph((PHASE5_DIR / "candidate_graph.json").read_text(encoding="utf-8"))
    issues = tuple(
        replace(
            issue,
            related_ids=(*issue.related_ids, _BLOCKED_RULE),
        )
        if issue.issue_id == _EXPLANATORY_ISSUE and _BLOCKED_RULE not in issue.related_ids
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
    print(f"corrected NAC: linked {_EXPLANATORY_ISSUE} to {_BLOCKED_RULE}")


if __name__ == "__main__":
    correct()
