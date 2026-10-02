"""Deterministic ingestion of returned clinical review submissions.

A submission is a human-editable JSON file (``review-submission-v1``) that
reviewers return. Ingestion validates it fail-closed against an exact
candidate graph:

- known candidate id, subject type, and exact content hash;
- known protocol (no cross-protocol decisions);
- known reviewer (when a registry is configured);
- valid verdict and ISO timestamp;
- non-stale revision binding;
- well-formed MODIFY payloads (REQUEST_CHANGES requires rationale or a
  proposed correction);
- valid missing-content feedback records.

Nothing here mutates candidates. ``REQUEST_CHANGES`` never replaces content;
it only records the requested correction. Import is append-only: records are
appended to a JSONL history and duplicate decision ids are rejected.
"""

# ruff: noqa: TRY004

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cpg_tree.candidates.graph import CandidateGraph
from cpg_tree.candidates.relations import CandidateRelation
from cpg_tree.candidates.rules import CandidateRule
from cpg_tree.review.feedback import ReviewFeedback, ReviewFeedbackType
from cpg_tree.review.model import ChecklistAnswer, ReviewDecision, ReviewSubjectType, ReviewVerdict
from cpg_tree.review.reviewer import ReviewerRegistry
from cpg_tree.validation.model import FindingSeverity, ValidationFinding, finding_sort_key

REVIEW_SUBMISSION_SCHEMA = "review-submission-v1"


@dataclass(frozen=True, slots=True)
class ReviewSubmission:
    """Validated result of ingesting one reviewer submission file."""

    protocol_version_id: str
    reviewer_id: str
    decisions: tuple[ReviewDecision, ...]
    feedback: tuple[ReviewFeedback, ...]
    findings: tuple[ValidationFinding, ...]

    @property
    def error_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity is FindingSeverity.ERROR)

    @property
    def is_valid(self) -> bool:
        return self.error_count == 0


def load_review_submission(
    path: Path,
    graph: CandidateGraph,
    *,
    reviewers: ReviewerRegistry | None = None,
) -> ReviewSubmission:
    """Parse and validate a returned review submission fail-closed."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError(f"{path.name} root must be a mapping")
    return parse_review_submission(raw, graph, reviewers=reviewers)


def parse_review_submission(
    data: Mapping[str, Any],
    graph: CandidateGraph,
    *,
    reviewers: ReviewerRegistry | None = None,
) -> ReviewSubmission:
    """Validate submission data against one exact candidate graph."""
    findings: list[ValidationFinding] = []
    protocol_version_id = _require_str(data, "protocol_version_id", findings, "submission")
    if protocol_version_id and protocol_version_id != graph.protocol_version_id:
        findings.append(
            ValidationFinding(
                code="REVIEW_PROTOCOL_MISMATCH",
                severity=FindingSeverity.ERROR,
                message=(
                    f"submission protocol {protocol_version_id!r} does not match "
                    f"graph protocol {graph.protocol_version_id!r}"
                ),
                path="/protocol_version_id",
            )
        )
    schema = _require_str(data, "schema", findings, "submission")
    if schema and schema != REVIEW_SUBMISSION_SCHEMA:
        findings.append(
            ValidationFinding(
                code="REVIEW_SUBMISSION_SCHEMA_INVALID",
                severity=FindingSeverity.ERROR,
                message=f"unsupported submission schema {schema!r}",
                path="/schema",
            )
        )
    reviewer_id = _require_str(data, "reviewer_id", findings, "submission")
    if reviewer_id and reviewers is not None and not reviewers.contains(reviewer_id):
        findings.append(
            ValidationFinding(
                code="REVIEW_UNKNOWN_REVIEWER",
                severity=FindingSeverity.ERROR,
                message=f"reviewer {reviewer_id!r} is not in the reviewer registry",
                path="/reviewer_id",
            )
        )
    rules = {rule.candidate_id: rule for rule in graph.rules}
    relations = {relation.candidate_relation_id: relation for relation in graph.relations}
    decisions = _parse_decisions(data, findings, rules, relations)
    feedback = _parse_feedback(data, findings, protocol_version_id or "", reviewer_id or "")
    findings = sorted(set(findings), key=finding_sort_key)
    return ReviewSubmission(
        protocol_version_id=protocol_version_id or "",
        reviewer_id=reviewer_id or "",
        decisions=decisions,
        feedback=feedback,
        findings=tuple(findings),
    )


def _parse_decisions(  # noqa: C901
    data: Mapping[str, Any],
    findings: list[ValidationFinding],
    rules: dict[str, CandidateRule],
    relations: dict[str, CandidateRelation],
) -> tuple[ReviewDecision, ...]:
    raw_decisions = data.get("decisions", [])
    if not isinstance(raw_decisions, list):
        findings.append(
            ValidationFinding(
                code="REVIEW_DECISIONS_MALFORMED",
                severity=FindingSeverity.ERROR,
                message="'decisions' must be a list",
                path="/decisions",
            )
        )
        return ()
    accepted: list[ReviewDecision] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(raw_decisions):
        path = f"/decisions/{index}"
        if not isinstance(entry, Mapping):
            findings.append(
                ValidationFinding(
                    code="REVIEW_DECISION_MALFORMED",
                    severity=FindingSeverity.ERROR,
                    message="decision entry must be a mapping",
                    path=path,
                )
            )
            continue
        decision_id = _require_str(entry, "decision_id", findings, path)
        if decision_id and decision_id in seen_ids:
            findings.append(
                ValidationFinding(
                    code="REVIEW_DECISION_DUPLICATE_ID",
                    severity=FindingSeverity.ERROR,
                    message=f"duplicate decision id {decision_id!r}",
                    path=f"{path}/decision_id",
                )
            )
        if decision_id:
            seen_ids.add(decision_id)
        subject_raw = _require_str(entry, "subject_type", findings, path)
        subject_type = _subject_type(subject_raw, findings, path)
        candidate_id = _require_str(entry, "candidate_id", findings, path)
        target = _target(subject_type, candidate_id, rules, relations)
        revision = _require_int(entry, "candidate_revision", findings, path)
        content_hash = _require_str(entry, "candidate_content_hash", findings, path)
        verdict = _verdict(_require_str(entry, "verdict", findings, path), findings, path)
        reviewed_at = _require_str(entry, "reviewed_at", findings, path)
        reviewer_id = _require_str(entry, "reviewer_id", findings, path)
        if target is None and subject_type is not None and candidate_id:
            findings.append(
                ValidationFinding(
                    code="REVIEW_UNKNOWN_CANDIDATE",
                    severity=FindingSeverity.ERROR,
                    message=f"unknown candidate {candidate_id!r} for {subject_type.value}",
                    path=f"{path}/candidate_id",
                    related_ids=(candidate_id,),
                )
            )
        if (
            target is not None
            and revision is not None
            and content_hash
            and target.is_current_revision(revision, content_hash) is False
        ):
            findings.append(
                ValidationFinding(
                    code="REVIEW_STALE_CANDIDATE_BINDING",
                    severity=FindingSeverity.ERROR,
                    message=(
                        f"decision references revision {revision} / hash "
                        f"{(content_hash or '')[:12]}… but the current candidate hash is "
                        f"{(target.content_hash or '')[:12]}…; the decision is STALE"
                    ),
                    path=f"{path}/candidate_content_hash",
                    related_ids=(candidate_id or "",),
                )
            )
        if verdict is ReviewVerdict.REQUEST_CHANGES:
            corrections = entry.get("proposed_corrections", [])
            rationale = entry.get("rationale")
            if not isinstance(corrections, list) or not all(
                isinstance(item, str) and item for item in corrections
            ):
                findings.append(
                    ValidationFinding(
                        code="REVIEW_MODIFY_PAYLOAD_MALFORMED",
                        severity=FindingSeverity.ERROR,
                        message=(
                            "REQUEST_CHANGES requires non-empty 'proposed_corrections' "
                            "string list and a non-empty 'rationale'"
                        ),
                        path=f"{path}/proposed_corrections",
                    )
                )
            elif not rationale:
                findings.append(
                    ValidationFinding(
                        code="REVIEW_MODIFY_PAYLOAD_MALFORMED",
                        severity=FindingSeverity.ERROR,
                        message="REQUEST_CHANGES requires a non-empty 'rationale'",
                        path=f"{path}/rationale",
                    )
                )
        if _decision_has_error(findings, path, decision_id or ""):
            continue
        try:
            decision = _decision_from_entry(
                entry,
                subject_type,
                candidate_id,
                revision,
                content_hash,
                verdict,
                reviewer_id,
                reviewed_at,
            )
        except ValueError as exc:
            findings.append(
                ValidationFinding(
                    code="REVIEW_DECISION_INVALID",
                    severity=FindingSeverity.ERROR,
                    message=str(exc),
                    path=path,
                )
            )
            continue
        accepted.append(decision)
    return tuple(accepted)


def _decision_has_error(findings: list[ValidationFinding], path: str, decision_id: str) -> bool:
    return any(
        finding.path is not None
        and finding.path.startswith(path)
        and finding.severity is FindingSeverity.ERROR
        for finding in findings
    )


def _decision_from_entry(  # noqa: PLR0913, PLR0917
    entry: Mapping[str, Any],
    subject_type: ReviewSubjectType | None,
    candidate_id: str | None,
    revision: int | None,
    content_hash: str | None,
    verdict: ReviewVerdict | None,
    reviewer_id: str | None,
    reviewed_at: str | None,
) -> ReviewDecision:
    checklist_raw = entry.get("checklist_answers", [])
    checklist = tuple(
        ChecklistAnswer(
            question=_require_str_inline(item, "question"),
            answer=_require_str_inline(item, "answer"),
        )
        for item in checklist_raw
        if isinstance(item, Mapping)
    )
    corrections = entry.get("proposed_corrections", [])
    supersedes = entry.get("supersedes_decision_id")
    return ReviewDecision(
        decision_id=str(entry["decision_id"]),
        subject_type=subject_type or ReviewSubjectType.RULE,
        candidate_id=candidate_id or "",
        candidate_revision=revision or 1,
        candidate_content_hash=content_hash or "",
        verdict=verdict or ReviewVerdict.ABSTAIN,
        reviewer_id=reviewer_id or "",
        reviewed_at=reviewed_at or "",
        rationale=entry.get("rationale") if entry.get("rationale") else None,
        checklist_answers=checklist,
        proposed_corrections=tuple(corrections) if isinstance(corrections, list) else (),
        supersedes_decision_id=supersedes if isinstance(supersedes, str) and supersedes else None,
    )


def _require_str_inline(item: Mapping[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"checklist answer requires non-empty {key!r}")
    return value


def _parse_feedback(
    data: Mapping[str, Any],
    findings: list[ValidationFinding],
    protocol_version_id: str,
    reviewer_id: str,
) -> tuple[ReviewFeedback, ...]:
    raw_feedback = data.get("feedback", [])
    if not isinstance(raw_feedback, list):
        findings.append(
            ValidationFinding(
                code="REVIEW_FEEDBACK_MALFORMED",
                severity=FindingSeverity.ERROR,
                message="'feedback' must be a list",
                path="/feedback",
            )
        )
        return ()
    accepted: list[ReviewFeedback] = []
    for index, entry in enumerate(raw_feedback):
        path = f"/feedback/{index}"
        if not isinstance(entry, Mapping):
            findings.append(
                ValidationFinding(
                    code="REVIEW_FEEDBACK_MALFORMED",
                    severity=FindingSeverity.ERROR,
                    message="feedback entry must be a mapping",
                    path=path,
                )
            )
            continue
        feedback_id = _require_str(entry, "feedback_id", findings, path)
        type_raw = _require_str(entry, "feedback_type", findings, path)
        try:
            feedback_type = ReviewFeedbackType(type_raw) if type_raw else None
        except ValueError:
            findings.append(
                ValidationFinding(
                    code="REVIEW_FEEDBACK_TYPE_INVALID",
                    severity=FindingSeverity.ERROR,
                    message=f"unknown feedback type {type_raw!r}",
                    path=f"{path}/feedback_type",
                )
            )
            continue
        reviewed_at = _require_str(entry, "reviewed_at", findings, path)
        description = _require_str(entry, "description", findings, path)
        try:
            accepted.append(
                ReviewFeedback(
                    feedback_id=feedback_id or "",
                    feedback_type=feedback_type or ReviewFeedbackType.MISSING_RULE,
                    description=description or "",
                    reviewer_id=reviewer_id,
                    reviewed_at=reviewed_at or "",
                    protocol_version_id=protocol_version_id,
                    proposed_content=entry.get("proposed_content")
                    if entry.get("proposed_content")
                    else None,
                    related_ids=tuple(entry["related_ids"])
                    if isinstance(entry.get("related_ids"), list)
                    else (),
                    evidence_reference=entry.get("evidence_reference")
                    if entry.get("evidence_reference")
                    else None,
                )
            )
        except ValueError as exc:
            findings.append(
                ValidationFinding(
                    code="REVIEW_FEEDBACK_INVALID",
                    severity=FindingSeverity.ERROR,
                    message=str(exc),
                    path=path,
                )
            )
    return tuple(accepted)


def _require_str(
    data: Mapping[str, Any], key: str, findings: list[ValidationFinding], path: str
) -> str | None:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        findings.append(
            ValidationFinding(
                code="REVIEW_FIELD_MISSING",
                severity=FindingSeverity.ERROR,
                message=f"required non-empty string field {key!r} is missing",
                path=f"{path}/{key}",
            )
        )
        return None
    return value


def _require_int(
    data: Mapping[str, Any], key: str, findings: list[ValidationFinding], path: str
) -> int | None:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        findings.append(
            ValidationFinding(
                code="REVIEW_FIELD_MISSING",
                severity=FindingSeverity.ERROR,
                message=f"required integer field {key!r} is missing",
                path=f"{path}/{key}",
            )
        )
        return None
    return value


def _subject_type(
    value: str | None, findings: list[ValidationFinding], path: str
) -> ReviewSubjectType | None:
    if value is None:
        return None
    try:
        return ReviewSubjectType(value)
    except ValueError:
        findings.append(
            ValidationFinding(
                code="REVIEW_SUBJECT_TYPE_INVALID",
                severity=FindingSeverity.ERROR,
                message=f"unknown subject type {value!r}",
                path=f"{path}/subject_type",
            )
        )
        return None


def _verdict(
    value: str | None, findings: list[ValidationFinding], path: str
) -> ReviewVerdict | None:
    if value is None:
        return None
    try:
        return ReviewVerdict(value)
    except ValueError:
        findings.append(
            ValidationFinding(
                code="REVIEW_VERDICT_INVALID",
                severity=FindingSeverity.ERROR,
                message=f"unknown verdict {value!r}",
                path=f"{path}/verdict",
            )
        )
        return None


def _target(
    subject_type: ReviewSubjectType | None,
    candidate_id: str | None,
    rules: dict[str, CandidateRule],
    relations: dict[str, CandidateRelation],
) -> CandidateRule | CandidateRelation | None:
    if subject_type is None or not candidate_id:
        return None
    if subject_type is ReviewSubjectType.RULE:
        return rules.get(candidate_id)
    return relations.get(candidate_id)


def decision_to_dict(decision: ReviewDecision) -> dict[str, Any]:
    """Serialize one validated decision deterministically."""
    payload: dict[str, Any] = {
        "decision_id": decision.decision_id,
        "subject_type": decision.subject_type.value,
        "candidate_id": decision.candidate_id,
        "candidate_revision": decision.candidate_revision,
        "candidate_content_hash": decision.candidate_content_hash,
        "verdict": decision.verdict.value,
        "reviewer_id": decision.reviewer_id,
        "reviewed_at": decision.reviewed_at,
    }
    if decision.rationale is not None:
        payload["rationale"] = decision.rationale
    if decision.checklist_answers:
        payload["checklist_answers"] = [
            {"question": answer.question, "answer": answer.answer}
            for answer in decision.checklist_answers
        ]
    if decision.proposed_corrections:
        payload["proposed_corrections"] = list(decision.proposed_corrections)
    if decision.supersedes_decision_id is not None:
        payload["supersedes_decision_id"] = decision.supersedes_decision_id
    return payload


def dump_review_decisions(decisions: tuple[ReviewDecision, ...]) -> str:
    """Serialize validated decisions as deterministic JSON."""
    return (
        json.dumps(
            [decision_to_dict(decision) for decision in decisions],
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def append_review_records(path: Path, records: tuple[ReviewDecision | ReviewFeedback, ...]) -> Path:
    """Append validated review records to a JSONL history, fail-closed.

    Existing records are never overwritten. If any incoming record id already
    exists in the history, the append fails without writing anything.
    """
    existing_ids = _existing_record_ids(path)
    incoming_ids = [
        record.decision_id if isinstance(record, ReviewDecision) else record.feedback_id
        for record in records
    ]
    duplicates = sorted(set(incoming_ids) & existing_ids)
    if duplicates:
        raise ValueError(f"append-only review history already contains ids: {duplicates}")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        for record in records:
            if isinstance(record, ReviewDecision):
                payload: dict[str, Any] = {
                    "kind": "decision",
                    **decision_to_dict(record),
                }
            else:
                payload = {
                    "kind": "feedback",
                    "feedback_id": record.feedback_id,
                    "feedback_type": record.feedback_type.value,
                    "description": record.description,
                    "reviewer_id": record.reviewer_id,
                    "reviewed_at": record.reviewed_at,
                    "protocol_version_id": record.protocol_version_id,
                    **(
                        {"proposed_content": record.proposed_content}
                        if record.proposed_content is not None
                        else {}
                    ),
                    **({"related_ids": list(record.related_ids)} if record.related_ids else {}),
                    **(
                        {"evidence_reference": record.evidence_reference}
                        if record.evidence_reference is not None
                        else {}
                    ),
                }
            stream.write(
                json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n"
            )
    return path


def load_review_records(path: Path) -> tuple[ReviewDecision, ...]:
    """Load validated decision records from the JSONL history."""
    if not path.exists():
        return ()
    decisions: list[ReviewDecision] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("kind") != "decision":
            continue
        checklist_raw = entry.get("checklist_answers", [])
        decisions.append(
            ReviewDecision(
                decision_id=entry["decision_id"],
                subject_type=ReviewSubjectType(entry["subject_type"]),
                candidate_id=entry["candidate_id"],
                candidate_revision=entry["candidate_revision"],
                candidate_content_hash=entry["candidate_content_hash"],
                verdict=ReviewVerdict(entry["verdict"]),
                reviewer_id=entry["reviewer_id"],
                reviewed_at=entry["reviewed_at"],
                rationale=entry.get("rationale"),
                checklist_answers=tuple(
                    ChecklistAnswer(question=item["question"], answer=item["answer"])
                    for item in checklist_raw
                ),
                proposed_corrections=tuple(entry.get("proposed_corrections", ())),
                supersedes_decision_id=entry.get("supersedes_decision_id"),
            )
        )
    return tuple(decisions)


def _existing_record_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        record_id = entry.get("decision_id") or entry.get("feedback_id")
        if record_id:
            ids.add(str(record_id))
    return ids
