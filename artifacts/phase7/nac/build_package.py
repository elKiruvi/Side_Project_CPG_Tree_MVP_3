"""Build the CT-PL-193 v9 (NAC) Phase 7A clinical review package.

Path configuration only; all package logic is generic
(``cpg_tree.review.package`` / ``package_validation``).
"""

from __future__ import annotations

from pathlib import Path

from cpg_tree.review.package import build_review_package
from cpg_tree.review.package_validation import validate_review_package
from cpg_tree.validation.review_packet import load_packet_graph

ROOT = Path(__file__).resolve().parents[3]
PHASE5_DIR = ROOT / "artifacts/phase5/nac"
PHASE6_DIR = ROOT / "artifacts/phase6/nac"
PHASE7_DIR = Path(__file__).parent


def main() -> None:
    graph = load_packet_graph(PHASE6_DIR / "candidate_graph.json")
    build_review_package(
        graph=graph,
        phase5_dir=PHASE5_DIR,
        phase6_dir=PHASE6_DIR,
        phase7_dir=PHASE7_DIR,
        review_questions_path=PHASE7_DIR / "review_questions.md",
        project_root=ROOT,
    )
    findings = validate_review_package(PHASE7_DIR, graph, project_root=ROOT)
    errors = [finding.code for finding in findings if finding.severity.value == "ERROR"]
    print(f"wrote NAC review package: {len(findings)} findings, errors: {errors}")


if __name__ == "__main__":
    main()
