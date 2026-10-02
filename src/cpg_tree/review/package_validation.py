"""Deterministic validation of Phase 7 clinical review packages.

Checks package-manifest integrity, candidate and relation hashes, review-tree
binding, portable repository-relative paths, protocol isolation, absence of
bundled source PDFs, AWAITING_CLINICAL_REVIEW status, and zero real
approvals. Validation reports problems; it never mutates the package.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from cpg_tree.candidates.graph import CandidateGraph
from cpg_tree.review.package import AWAITING_CLINICAL_REVIEW, REVIEW_PACKAGE_SCHEMA
from cpg_tree.validation.model import FindingSeverity, ValidationFinding, finding_sort_key


def validate_review_package(  # noqa: C901, PLR0912, PLR0915
    package_dir: Path,
    graph: CandidateGraph,
    *,
    project_root: Path,
) -> tuple[ValidationFinding, ...]:
    """Validate a Phase 7 review package against its canonical graph."""
    manifest_path = package_dir / "review_manifest.json"
    findings: list[ValidationFinding] = []
    if not manifest_path.exists():
        return (
            ValidationFinding(
                code="REVIEW_PACKAGE_MANIFEST_MISSING",
                severity=FindingSeverity.ERROR,
                message=f"{manifest_path.name} does not exist",
                path="/review_manifest.json",
            ),
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return (
            ValidationFinding(
                code="REVIEW_PACKAGE_MANIFEST_INVALID",
                severity=FindingSeverity.ERROR,
                message=f"review manifest is not valid JSON: {exc}",
                path="/review_manifest.json",
            ),
        )
    if not isinstance(manifest, Mapping):
        findings.append(
            ValidationFinding(
                code="REVIEW_PACKAGE_MANIFEST_INVALID",
                severity=FindingSeverity.ERROR,
                message="review manifest root must be a mapping",
                path="/review_manifest.json",
            )
        )
        return tuple(findings)
    if manifest.get("schema") != REVIEW_PACKAGE_SCHEMA:
        findings.append(
            ValidationFinding(
                code="REVIEW_PACKAGE_SCHEMA_INVALID",
                severity=FindingSeverity.ERROR,
                message=f"unsupported review package schema {manifest.get('schema')!r}",
                path="/schema",
            )
        )
    if manifest.get("protocol_version_id") != graph.protocol_version_id:
        findings.append(
            ValidationFinding(
                code="REVIEW_PACKAGE_PROTOCOL_MISMATCH",
                severity=FindingSeverity.ERROR,
                message=(
                    f"package protocol {manifest.get('protocol_version_id')!r} does not "
                    f"match graph protocol {graph.protocol_version_id!r}"
                ),
                path="/protocol_version_id",
            )
        )
    if manifest.get("status") != AWAITING_CLINICAL_REVIEW:
        findings.append(
            ValidationFinding(
                code="REVIEW_PACKAGE_STATUS_INVALID",
                severity=FindingSeverity.ERROR,
                message=(
                    f"real review packages must be {AWAITING_CLINICAL_REVIEW} until decisions exist"
                ),
                path="/status",
            )
        )
    for key in ("approved_rules", "approved_relations", "approved_knowledge_packages"):
        if manifest.get(key) != 0:
            findings.append(
                ValidationFinding(
                    code="REVIEW_PACKAGE_UNEXPECTED_APPROVAL",
                    severity=FindingSeverity.ERROR,
                    message=f"package declares non-zero {key!r} without real clinical review",
                    path=f"/{key}",
                )
            )
    bundle_files = manifest.get("bundle_files")
    if not isinstance(bundle_files, list) or not bundle_files:
        findings.append(
            ValidationFinding(
                code="REVIEW_PACKAGE_BUNDLE_MISSING",
                severity=FindingSeverity.ERROR,
                message="review manifest requires a non-empty 'bundle_files' list",
                path="/bundle_files",
            )
        )
        bundle_files = []
    for entry in bundle_files:
        if not isinstance(entry, Mapping):
            findings.append(
                ValidationFinding(
                    code="REVIEW_PACKAGE_BUNDLE_ENTRY_INVALID",
                    severity=FindingSeverity.ERROR,
                    message="bundle file entry must be a mapping",
                    path="/bundle_files",
                )
            )
            continue
        stored_path = entry.get("path")
        if not isinstance(stored_path, str) or not stored_path:
            findings.append(
                ValidationFinding(
                    code="REVIEW_PACKAGE_PATH_MISSING",
                    severity=FindingSeverity.ERROR,
                    message="bundle file entry requires a 'path' string",
                    path="/bundle_files/path",
                )
            )
            continue
        path_obj = Path(stored_path)
        if path_obj.is_absolute():
            findings.append(
                ValidationFinding(
                    code="REVIEW_PACKAGE_PATH_NOT_PORTABLE",
                    severity=FindingSeverity.ERROR,
                    message=(
                        f"persisted path {stored_path!r} is absolute; review packages "
                        "must use repository-relative paths"
                    ),
                    path="/bundle_files/path",
                )
            )
            continue
        if ".." in path_obj.parts:
            findings.append(
                ValidationFinding(
                    code="REVIEW_PACKAGE_PATH_NOT_PORTABLE",
                    severity=FindingSeverity.ERROR,
                    message=f"persisted path {stored_path!r} escapes the repository root",
                    path="/bundle_files/path",
                )
            )
            continue
        resolved = project_root / path_obj
        if not resolved.exists():
            findings.append(
                ValidationFinding(
                    code="REVIEW_PACKAGE_BUNDLE_FILE_MISSING",
                    severity=FindingSeverity.ERROR,
                    message=f"bundle file {stored_path!r} does not exist",
                    path="/bundle_files/path",
                )
            )
            continue
        if entry.get("sha256") != hashlib.sha256(resolved.read_bytes()).hexdigest():
            findings.append(
                ValidationFinding(
                    code="REVIEW_PACKAGE_HASH_MISMATCH",
                    severity=FindingSeverity.ERROR,
                    message=f"bundle file {stored_path!r} hash does not match the manifest",
                    path="/bundle_files/sha256",
                )
            )
    pdf_files = sorted((package_dir).rglob("*.pdf"))
    if pdf_files:
        findings.append(
            ValidationFinding(
                code="REVIEW_PACKAGE_SOURCE_PDF_BUNDLED",
                severity=FindingSeverity.ERROR,
                message=f"source PDFs must not be bundled: {[p.name for p in pdf_files]}",
                path="/bundle_files",
            )
        )
    template_path = manifest.get("review_template")
    if isinstance(template_path, str) and template_path:
        template_obj = Path(template_path)
        if template_obj.is_absolute() or ".." in template_obj.parts:
            findings.append(
                ValidationFinding(
                    code="REVIEW_PACKAGE_PATH_NOT_PORTABLE",
                    severity=FindingSeverity.ERROR,
                    message=f"review_template path {template_path!r} is not portable",
                    path="/review_template",
                )
            )
        elif not (project_root / template_obj).exists():
            findings.append(
                ValidationFinding(
                    code="REVIEW_PACKAGE_TEMPLATE_MISSING",
                    severity=FindingSeverity.ERROR,
                    message=f"review template {template_path!r} does not exist",
                    path="/review_template",
                )
            )
    else:
        findings.append(
            ValidationFinding(
                code="REVIEW_PACKAGE_TEMPLATE_MISSING",
                severity=FindingSeverity.ERROR,
                message="review manifest requires a 'review_template' path",
                path="/review_template",
            )
        )
    return tuple(sorted(set(findings), key=finding_sort_key))
