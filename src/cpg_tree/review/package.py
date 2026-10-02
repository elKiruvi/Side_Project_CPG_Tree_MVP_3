"""Phase 7A clinical review package builder.

Builds a self-contained, portable review package for one protocol: a review
bundle a clinician can open without Python, plus a canonical decision
template and a hash-bound review manifest. The bundle consumes the exact
Phase 6 review-bound artifacts (same graph hash and visual bytes), so the
tree a clinician reviews is verifiably the validated candidate graph.

All persisted paths are repository-relative (portable across checkouts and
CI runners). Nothing here performs clinical interpretation, and nothing is
approved by building a package.
"""

# ruff: noqa: PLR0913

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any

from cpg_tree.candidates.graph import CandidateGraph
from cpg_tree.candidates.graph_serialization import dump_candidate_graph
from cpg_tree.extraction.spans import SpanQualityFlag

REVIEW_PACKAGE_SCHEMA = "review-package-v1"
AWAITING_CLINICAL_REVIEW = "AWAITING_CLINICAL_REVIEW"

_BUNDLE_FILES = (
    "index.html",
    "review_tree.html",
    "review_tree.svg",
    "review_summary.md",
    "clinical_review_questions.md",
    "review_questions.md",
    "validation_summary.md",
    "review_instructions.md",
    "evidence.md",
)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, project_root: Path) -> str:
    root = project_root.resolve()
    resolved = path.resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"artifact path {resolved} is outside the project root {root}") from exc


def _copy(name: str, source: Path, bundle: Path, project_root: Path) -> str:
    (bundle / name).write_bytes(source.read_bytes())
    return _relative(bundle / name, project_root)


def build_review_package(
    *,
    graph: CandidateGraph,
    phase5_dir: Path,
    phase6_dir: Path,
    phase7_dir: Path,
    review_questions_path: Path,
    project_root: Path,
) -> dict[str, Any]:
    """Build the review package and return the manifest payload."""
    bundle = phase7_dir / "review_bundle"
    bundle.mkdir(parents=True, exist_ok=True)

    bound: dict[str, str] = {}
    bound["review_tree.html"] = _copy(
        "review_tree.html", phase6_dir / "review_tree.html", bundle, project_root
    )
    bound["review_tree.svg"] = _copy(
        "review_tree.svg", phase6_dir / "review_tree.svg", bundle, project_root
    )
    bound["review_summary.md"] = _copy(
        "review_summary.md", phase5_dir / "review_summary.md", bundle, project_root
    )
    bound["clinical_review_questions.md"] = _copy(
        "clinical_review_questions.md",
        phase5_dir / "clinical_review_questions.md",
        bundle,
        project_root,
    )
    bound["review_questions.md"] = _copy(
        "review_questions.md", review_questions_path, bundle, project_root
    )
    bound["validation_summary.md"] = _copy(
        "validation_summary.md", phase6_dir / "validation_report.md", bundle, project_root
    )
    (bundle / "review_instructions.md").write_text(_INSTRUCTIONS_TEMPLATE, encoding="utf-8")
    bound["review_instructions.md"] = _relative(bundle / "review_instructions.md", project_root)
    (bundle / "evidence.md").write_text(_render_evidence(graph), encoding="utf-8")
    bound["evidence.md"] = _relative(bundle / "evidence.md", project_root)
    (bundle / "index.html").write_text(
        _render_index(graph, phase6_dir / "review_manifest.json"), encoding="utf-8"
    )
    bound["index.html"] = _relative(bundle / "index.html", project_root)

    template_path = phase7_dir / "review_template.json"
    template_path.write_text(_render_template(graph), encoding="utf-8")

    phase6_manifest = json.loads((phase6_dir / "review_manifest.json").read_text(encoding="utf-8"))
    manifest_payload: dict[str, Any] = {
        "schema": REVIEW_PACKAGE_SCHEMA,
        "protocol_version_id": graph.protocol_version_id,
        "document_id": graph.document_id,
        "document_sha256": phase6_manifest.get("document_sha256"),
        "status": AWAITING_CLINICAL_REVIEW,
        "approval_policy": "policy_pending",
        "approved_rules": 0,
        "approved_relations": 0,
        "approved_knowledge_packages": 0,
        "review_package_version": 1,
        "graph_content_hash": hashlib.sha256(
            dump_candidate_graph(graph).encode("utf-8")
        ).hexdigest(),
        "phase6_validation_report_sha256": phase6_manifest.get("validation_report_sha256"),
        "bundle_index": _relative(bundle / "index.html", project_root),
        "review_template": _relative(template_path, project_root),
        "bundle_files": [
            {"name": name, "path": bound[name], "sha256": sha256_file(bundle / name)}
            for name in _BUNDLE_FILES
        ],
        "note": (
            "Clinical review package. AWAITING_CLINICAL_REVIEW means no real "
            "reviewer decision exists yet; the candidates are NOT approved."
        ),
    }
    manifest_path = phase7_dir / "review_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return manifest_payload


def _render_template(graph: CandidateGraph) -> str:
    catalog: list[dict[str, Any]] = []
    for rule in sorted(graph.rules, key=lambda item: item.candidate_id):
        catalog.append(
            {
                "item_type": "RULE",
                "item_id": rule.candidate_id,
                "label": rule.actions[0].target_text if rule.actions else "",
                "candidate_revision": rule.revision,
                "content_hash": rule.content_hash or "",
                "state": rule.candidate_state.value,
                "issues": _rule_issue_ids(graph, rule.candidate_id),
            }
        )
    for relation in sorted(graph.relations, key=lambda item: item.candidate_relation_id):
        catalog.append(
            {
                "item_type": "RELATION",
                "item_id": relation.candidate_relation_id,
                "label": (
                    f"{relation.relation_type.value} {relation.source_ref} → "
                    f"{', '.join(relation.target_refs)}"
                    f"{' [' + relation.branch_label + ']' if relation.branch_label else ''}"
                ),
                "candidate_revision": relation.revision,
                "content_hash": relation.content_hash or "",
                "state": relation.candidate_state.value,
                "issues": _rule_issue_ids(graph, relation.candidate_relation_id),
            }
        )
    payload: dict[str, Any] = {
        "schema": "review-submission-v1",
        "protocol_version_id": graph.protocol_version_id,
        "reviewer_id": "<reviewer_id>",
        "display_name": "<display name>",
        "role": "<role>",
        "catalog": catalog,
        "decisions": [],
        "feedback": [],
    }
    return json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n"


def _rule_issue_ids(graph: CandidateGraph, related: str) -> list[str]:
    return sorted(issue.issue_id for issue in graph.issues if related in issue.related_ids)


def _render_evidence(graph: CandidateGraph) -> str:
    lines = [
        f"# Evidence index — {graph.protocol_version_id}",
        "",
        "Evidence references per candidate. Quotes marked [VISUAL SOURCE / "
        "MANUAL REVIEW REQUIRED] come from visual-only source regions and are "
        "not native extracted text.",
        "",
    ]
    for rule in sorted(graph.rules, key=lambda item: item.candidate_id):
        lines.append(f"## Rule {rule.candidate_id}")
        lines.append("")
        lines.append(f"- Action: {rule.actions[0].target_text if rule.actions else '—'}")
        spans = sorted(
            {ref for binding in rule.evidence_bindings for ref in binding.source_span_refs}
            | {
                ref
                for action in rule.actions
                for binding in action.evidence_bindings
                for ref in binding.source_span_refs
            }
        )
        for span_id in spans:
            span = next((item for item in graph.source_spans if item.span_id == span_id), None)
            if span is None:
                continue
            visual = (
                " [VISUAL SOURCE / MANUAL REVIEW REQUIRED]"
                if (SpanQualityFlag.VISUAL_ONLY in span.quality_flags)
                else ""
            )
            quote = (span.extracted_text_exact or span.normalized_text or "—")[:240]
            lines.append(f"- page {span.page}, `{span.span_id}`{visual}: “{quote}”")
        lines.append("")
    for relation in sorted(graph.relations, key=lambda item: item.candidate_relation_id):
        lines.append(f"## Relation {relation.candidate_relation_id}")
        lines.append("")
        lines.append(
            f"- {relation.relation_type.value} {relation.source_ref} → "
            f"{', '.join(relation.target_refs)}"
            f"{' [' + relation.branch_label + ']' if relation.branch_label else ''}"
        )
        for binding in relation.evidence_bindings:
            for span_id in sorted(binding.source_span_refs):
                span = next((item for item in graph.source_spans if item.span_id == span_id), None)
                if span is None:
                    continue
                quote = (span.extracted_text_exact or span.normalized_text or "—")[:240]
                lines.append(f"- page {span.page}, `{span.span_id}`: “{quote}”")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def _render_index(graph: CandidateGraph, phase6_manifest_path: Path) -> str:
    phase6_manifest = json.loads(phase6_manifest_path.read_text(encoding="utf-8"))
    readiness = phase6_manifest.get("review_readiness", "—")
    lines = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f"<title>Clinical review package — {graph.protocol_version_id}</title>",
        _INDEX_CSS,
        "</head><body>",
        f"<header><h1>Clinical review package — {graph.protocol_version_id}</h1>",
        "<p>AI-generated candidate pathway. Structurally validated; "
        "<strong>NOT clinically approved</strong>.</p></header>",
        "<main>",
        "<section class='status'><h2>Status</h2><ul>",
        "<li>Review status: AWAITING_CLINICAL_REVIEW</li>",
        f"<li>Structural validation: {html.escape(readiness)}</li>",
        "<li>Real approval count: 0</li>",
        "</ul></section>",
        "<section class='links'><h2>Review material</h2><ul>",
        "<li><a href='review_tree.html'>Review tree (main visual)</a></li>",
        "<li><a href='review_tree.svg'>Review tree (SVG)</a></li>",
        "<li><a href='review_summary.md'>Pathway summary</a></li>",
        "<li><a href='review_questions.md'>Questions for reviewers (plain language)</a></li>",
        "<li><a href='clinical_review_questions.md'>Detailed clinical questions</a></li>",
        "<li><a href='validation_summary.md'>Technical validation summary</a></li>",
        "<li><a href='evidence.md'>Evidence index (page and source quotes)</a></li>",
        "<li><a href='review_instructions.md'>How to record your review</a></li>",
        "</ul></section>",
        "<section class='note'><h2>Important</h2><p>",
        "This package presents candidate rules and pathways produced with AI "
        "assistance. They have passed structural and provenance validation but "
        "have NOT been clinically approved. Your review decisions determine "
        "what may later become approved clinical knowledge.</p></section>",
        "</main></body></html>",
    ]
    return "\n".join(lines) + "\n"


_INDEX_CSS = """
<style>
:root { --ink: #1f2937; --muted: #6b7280; --line: #d1d5db; --bg: #f6f7f9;
        --card: #ffffff; --accent: #0f4c81; }
body { margin: 0; color: var(--ink); background: var(--bg);
       font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
header { background: var(--accent); color: #fff; padding: 1.4rem 2rem; }
header p { margin: .4rem 0 0 0; }
main { max-width: 960px; margin: 0 auto; padding: 1rem 2rem 2rem 2rem; }
section { background: var(--card); border: 1px solid var(--line); border-radius: 6px;
          padding: 1rem 1.2rem; margin: 0 0 1rem 0; }
h2 { margin-top: 0; }
a { color: var(--accent); }
</style>
"""


_INSTRUCTIONS_TEMPLATE = """# How to review this clinical pathway

## What you are reviewing

- This pathway was produced with AI assistance from the institutional
  protocol. It is a CANDIDATE pathway: it has passed structural and
  provenance validation but has NOT been clinically approved.
- Review the rules, logical operators, thresholds, treatments, branches,
  sequence, missing steps, and conflicts against the protocol you know.

## Before you start

1. Open `review_tree.html` — it is the main visual of the candidate pathway.
2. Read `review_summary.md` for the proposed pathway narrative.
3. Answer the questions in `review_questions.md`.
4. Use `evidence.md` to check the exact source page and text for each item.
   Items marked VISUAL SOURCE / MANUAL REVIEW REQUIRED come from figures or
   tables that could not be read as text and need your own verification.

## What the status labels mean

- PROPOSED — candidate content pending your review.
- BLOCKED — candidate content with unresolved evidence; review it and tell us
  how to resolve it.
- Issues — known conflicts or uncertainties; your input decides them.

## How to record your review

Use the file `review_template.json` (one per reviewer). For each rule or
relationship you reviewed, add an entry under `decisions` with:

- `decision_id`: any unique short id, e.g. `rev1-r18`.
- `subject_type`: `RULE` or `RELATION`.
- `item_id`: the rule or relationship id from the catalog.
- `candidate_revision` and `content_hash`: copy them from the catalog entry —
  never change them.
- `verdict`: one of
  - `APPROVE` — I agree with this item as written;
  - `REJECT` — this item is wrong and must not become clinical knowledge;
  - `REQUEST_CHANGES` — the idea is acceptable but must change; put the
    requested correction under `proposed_corrections` and explain under
    `rationale`;
  - `NEEDS_CLARIFICATION` — I need more context to decide;
  - `DEFER` — not my area; someone else should decide;
  - `ABSTAIN` — no position.
- `reviewer_id`, `reviewed_at` (ISO date), and any comments.

If something is MISSING from the pathway, add an entry under `feedback` with
a `feedback_type` such as `MISSING_RULE`, `MISSING_RELATION`, `MISSING_BRANCH`,
`MISSING_CONDITION`, `MISSING_ACTION`, or `MISSING_EVIDENCE`, and describe
what is missing under `description` (and `proposed_content` if you can).

Do not edit any other file in this package. Return the completed template to
the project team. Your decisions are recorded exactly as submitted and never
silently changed.
"""
