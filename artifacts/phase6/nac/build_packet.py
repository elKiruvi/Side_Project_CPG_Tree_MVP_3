"""Build the CT-PL-193 v9 (NAC) Phase 6 validation packet.

Path configuration only; all validation logic is generic
(``cpg_tree.validation.candidate_structural`` / ``review_packet``). The packet
binds the Phase 6 integrity-corrected graph and regenerated visuals, and points
to the unchanged Phase 5 review documents.
"""

from __future__ import annotations

from pathlib import Path

from cpg_tree.extraction.layout import fingerprint_bytes
from cpg_tree.validation.review_packet import build_review_packet, load_packet_graph
from cpg_tree.views.review_tree import load_projection_manifest

ROOT = Path(__file__).resolve().parents[3]
PHASE5_DIR = ROOT / "artifacts/phase5/nac"
PHASE6_DIR = Path(__file__).parent
SOURCE_PDF = next((ROOT / "data/01_raw").glob("CT-PL-193*.pdf"))


def main() -> None:
    graph = load_packet_graph(PHASE6_DIR / "candidate_graph.json")
    manifest = load_projection_manifest(PHASE5_DIR / "projection.yaml")
    document_sha256 = fingerprint_bytes(SOURCE_PDF.read_bytes()) if SOURCE_PDF.exists() else None
    report = build_review_packet(
        graph=graph,
        manifest=manifest,
        graph_json_path=PHASE6_DIR / "candidate_graph.json",
        review_visuals=(
            ("review_tree.html", PHASE6_DIR / "review_tree.html"),
            ("review_tree.svg", PHASE6_DIR / "review_tree.svg"),
        ),
        phase5_dir=PHASE5_DIR,
        questions_path=PHASE5_DIR / "clinical_review_questions.md",
        packet_dir=PHASE6_DIR,
        project_root=ROOT,
        document_sha256=document_sha256,
    )
    print(
        f"wrote NAC packet: {report.error_count} errors, {report.warning_count} warnings, "
        f"{report.review_readiness}"
    )


if __name__ == "__main__":
    main()
