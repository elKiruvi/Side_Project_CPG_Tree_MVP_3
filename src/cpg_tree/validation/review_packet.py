"""Phase 6 review-packet builder for candidate graphs.

Builds a consolidated, hash-bound clinical review packet per protocol:

- ``validation_report.json`` — deterministic machine-readable structural report;
- ``validation_report.md`` — human-readable summary distinguishing technical
  validation from questions requiring clinical judgment;
- ``review_manifest.json`` — binding metadata (graph revision, content hashes,
  artifact hashes, document identity) so future review decisions can be tied
  to the exact graph version a clinician inspected.

The packet POINTS to the Phase 5 review artifacts (tree, summary, questions)
rather than duplicating them. Nothing here performs clinical interpretation,
and nothing is approved by generating a packet.
"""

# ruff: noqa: PLR0913

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from cpg_tree.candidates.graph import CandidateGraph
from cpg_tree.candidates.graph_serialization import dump_candidate_graph, load_candidate_graph
from cpg_tree.validation.candidate_structural import (
    NOT_READY_FOR_CLINICAL_REVIEW,
    CandidateStructureReport,
    dump_candidate_structure_report,
    validate_candidate_structure,
)
from cpg_tree.validation.model import FindingSeverity
from cpg_tree.views.review_tree import ProjectionManifest

_PHASE5_REVIEW_ARTIFACTS = (
    "projection.yaml",
    "reconciliation_report.md",
    "review_summary.md",
    "clinical_review_questions.md",
)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    """Return the SHA-256 of UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_review_packet(
    *,
    graph: CandidateGraph,
    manifest: ProjectionManifest,
    graph_json_path: Path,
    review_visuals: tuple[tuple[str, Path], ...],
    phase5_dir: Path,
    questions_path: Path,
    packet_dir: Path,
    project_root: Path,
    document_sha256: str | None = None,
) -> CandidateStructureReport:
    """Validate and write the review packet for one protocol.

    ``graph_json_path`` is the review-bound canonical graph artifact;
    ``review_visuals`` are the review-tree SVG/HTML artifacts bound to that
    exact graph; ``phase5_dir`` points at the unchanged Phase 5 review
    documents; ``project_root`` is the repository root used to persist all
    artifact paths as portable, repository-relative strings (never
    machine-specific absolute paths). ``document_sha256`` is the SHA-256 of
    the original source PDF when locally available.
    """
    html_path = dict(review_visuals).get("review_tree.html")
    svg_path = dict(review_visuals).get("review_tree.svg")
    artifact_files = {
        "html": html_path,
        "svg": svg_path,
        "questions": questions_path,
    }
    report = validate_candidate_structure(graph, manifest, artifact_files=artifact_files)
    report_json = dump_candidate_structure_report(report)
    report_hash = sha256_text(report_json)

    packet_dir.mkdir(parents=True, exist_ok=True)
    (packet_dir / "validation_report.json").write_text(report_json, encoding="utf-8")
    (packet_dir / "validation_report.md").write_text(
        _render_report_markdown(report), encoding="utf-8"
    )

    manifest_data = _manifest_payload(
        graph=graph,
        report=report,
        report_hash=report_hash,
        graph_json_path=graph_json_path,
        review_visuals=review_visuals,
        phase5_dir=phase5_dir,
        questions_path=questions_path,
        project_root=project_root,
        document_sha256=document_sha256,
    )
    (packet_dir / "review_manifest.json").write_text(
        json.dumps(manifest_data, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return report


def _relative_path(path: Path, project_root: Path) -> str:
    """Return the repository-relative POSIX string for a path, fail-closed.

    Absolute or out-of-tree paths raise ValueError: manifests must never
    persist machine-specific locations.
    """
    root = project_root.resolve()
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"artifact path {resolved} is outside the project root {root}; "
            "review manifests must use repository-relative paths"
        ) from exc
    return relative.as_posix()


def _manifest_payload(
    *,
    graph: CandidateGraph,
    report: CandidateStructureReport,
    report_hash: str,
    graph_json_path: Path,
    review_visuals: tuple[tuple[str, Path], ...],
    phase5_dir: Path,
    questions_path: Path,
    project_root: Path,
    document_sha256: str | None,
) -> dict[str, Any]:
    bound_artifacts = [
        {
            "name": name,
            "path": _relative_path(path, project_root),
            "sha256": sha256_file(path),
        }
        for name, path in review_visuals
    ] + [
        {
            "name": "candidate_graph.json",
            "path": _relative_path(graph_json_path, project_root),
            "sha256": sha256_file(graph_json_path),
        }
    ]
    phase5_artifacts = [
        {
            "name": name,
            "path": _relative_path(phase5_dir / name, project_root),
            "sha256": sha256_file(phase5_dir / name),
        }
        for name in _PHASE5_REVIEW_ARTIFACTS
    ]
    return {
        "schema": "review-manifest-v1",
        "protocol_version_id": graph.protocol_version_id,
        "graph_id": graph.graph_id,
        "generation_run_id": graph.generation_run_id,
        "document_id": graph.document_id,
        "document_sha256": document_sha256,
        "graph_content_hash": report.graph_content_hash,
        "graph_dump_hash": sha256_text(dump_candidate_graph(graph)),
        "candidate_hashes": {
            rule.candidate_id: rule.content_hash
            for rule in sorted(graph.rules, key=lambda item: item.candidate_id)
        },
        "relation_hashes": {
            relation.candidate_relation_id: relation.content_hash
            for relation in sorted(graph.relations, key=lambda item: item.candidate_relation_id)
        },
        "review_readiness": report.review_readiness,
        "provenance_status": report.provenance_status,
        "projection_parity_status": report.projection_parity_status,
        "structural_error_count": report.error_count,
        "structural_warning_count": report.warning_count,
        "validation_report_sha256": report_hash,
        "review_bound_artifacts": bound_artifacts,
        "phase5_review_artifacts": phase5_artifacts,
        "clinical_review_questions": _relative_path(questions_path, project_root),
        "note": (
            "Candidate review packet. READY_FOR_CLINICAL_REVIEW means structurally "
            "trustworthy and reviewable; it is NOT clinical validation or approval."
        ),
    }


def _render_report_markdown(report: CandidateStructureReport) -> str:  # noqa: PLR0912
    lines = [
        f"# Structural validation — {report.protocol_version_id}",
        "",
        "Candidate review packet (Phase 6). This report covers TECHNICAL "
        "validation only. Clinical questions live in "
        "`clinical_review_questions.md` and must be answered by qualified "
        "reviewers; nothing here is clinically approved.",
        "",
        "## Summary",
        "",
        f"- graph: `{report.graph_id}`",
        f"- rules: {report.rule_count} · relations: {report.relation_count} · "
        f"issues: {report.issue_count}",
        f"- blocked: {report.blocked_rule_count} rules · {report.blocked_relation_count} relations",
        f"- structural errors: **{report.error_count}** · warnings: "
        f"{report.warning_count} · info: {report.info_count}",
        f"- provenance: {report.provenance_status}",
        f"- projection parity: {report.projection_parity_status}",
        f"- review readiness: **{report.review_readiness}**",
        f"- graph content hash: `{report.graph_content_hash}`",
        "",
    ]
    if report.review_readiness != NOT_READY_FOR_CLINICAL_REVIEW:
        lines.append(
            "> READY_FOR_CLINICAL_REVIEW does not mean CLINICALLY_VALID or "
            "APPROVED. It means the artifact is structurally trustworthy and "
            "ready for human review."
        )
    else:
        lines.append(
            "> NOT_READY_FOR_CLINICAL_REVIEW: structural errors or missing "
            "review artifacts must be fixed before the packet is sent to "
            "reviewers."
        )
    lines.extend(["", "## Errors", ""])
    errors = [finding for finding in report.findings if finding.severity is FindingSeverity.ERROR]
    if errors:
        for finding in errors:
            lines.append(f"- **{finding.code}** {finding.message} ({finding.path or '-'})")
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    warnings = [
        finding for finding in report.findings if finding.severity is FindingSeverity.WARNING
    ]
    if warnings:
        for finding in warnings:
            lines.append(f"- **{finding.code}** {finding.message} ({finding.path or '-'})")
    else:
        lines.append("- none")
    lines.extend(["", "## Disconnected components", ""])
    if report.disconnected_components:
        for component in report.disconnected_components:
            lines.append(
                f"- [{component.classification.value}] "
                f"{', '.join(component.rule_ids)} — {component.note}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Cycles", ""])
    if report.cycles:
        for cycle in report.cycles:
            lines.append(
                f"- relations {', '.join(cycle.relation_ids)} (rules {', '.join(cycle.rule_ids)})"
            )
    else:
        lines.append("- none detected")
    lines.extend(["", "## Entry points", ""])
    lines.extend(f"- {entry}" for entry in report.entry_points or ("- none",))
    lines.extend(["", "## Terminal nodes", ""])
    lines.extend(f"- {terminal}" for terminal in report.terminal_nodes or ("- none",))
    lines.extend(
        [
            "## Questions requiring clinical judgment",
            "",
            "See `clinical_review_questions.md` in the same Phase 5 artifact "
            "directory. Software cannot answer those questions.",
            "",
            "## Technical traceability",
            "",
            "Full machine-readable details: `validation_report.json`. Exact "
            "candidate hashes and artifact hashes: `review_manifest.json`.",
        ]
    )
    return "\n".join(lines).rstrip("\n") + "\n"


def load_packet_graph(path: Path) -> CandidateGraph:
    """Load the canonical candidate graph JSON for packet building."""
    return load_candidate_graph(path.read_text(encoding="utf-8"))
