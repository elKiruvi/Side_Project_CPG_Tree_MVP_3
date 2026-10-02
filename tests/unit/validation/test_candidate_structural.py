"""Generic structural-validation tests using synthetic candidate graphs.

These tests exercise deterministic, protocol-agnostic validation mechanics.
No clinical content is encoded here: no medical threshold, medication, or
rule-to-rule connection is asserted.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from cpg_tree.candidates.actions import ActionSpec
from cpg_tree.candidates.enums import (
    CandidateState,
    EvidenceClass,
    IssueCategory,
    IssueSeverity,
    ObservationKind,
    RelationType,
)
from cpg_tree.candidates.evidence import EvidenceBinding
from cpg_tree.candidates.graph import CandidateGraph
from cpg_tree.candidates.graph_serialization import dump_candidate_graph, load_candidate_graph
from cpg_tree.candidates.issues import Issue
from cpg_tree.candidates.observations import Observation
from cpg_tree.candidates.relations import CandidateRelation
from cpg_tree.candidates.rules import CandidateRule
from cpg_tree.candidates.variables import VariableSpec
from cpg_tree.extraction.spans import SourceSpan, SpanRepresentation
from cpg_tree.knowledge.conditions import Condition, LogicalExpression
from cpg_tree.knowledge.enums import ActionType, ConditionKind, LogicalOperator, VariableType
from cpg_tree.validation.candidate_structural import (
    NOT_READY_FOR_CLINICAL_REVIEW,
    READY_FOR_CLINICAL_REVIEW,
    CandidateStructureReport,
    dump_candidate_structure_report,
    validate_candidate_structure,
)
from cpg_tree.validation.model import FindingSeverity
from cpg_tree.validation.review_packet import build_review_packet, sha256_file
from cpg_tree.views.review_tree import (
    ProjectionManifest,
    StageRoot,
    render_review_tree_html,
    render_review_tree_svg,
)

_PROTOCOL = "SYN-999-v1"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _span(span_id: str, document_id: str = "doc-synthetic") -> SourceSpan:
    text = f"Evidence for {span_id}."
    return SourceSpan(
        span_id=span_id,
        document_id=document_id,
        extraction_run_id="run-synthetic",
        page=1,
        representation=SpanRepresentation.TEXT,
        extraction_method="test",
        extracted_text_exact=text,
        text_sha256=_sha(text),
    )


def _binding(claim_path: str, span_id: str, quote: str | None = None) -> EvidenceBinding:
    span = _span(span_id)
    return EvidenceBinding(
        claim_path=claim_path,
        evidence_class=EvidenceClass.NORMALIZED,
        source_span_refs=(span_id,),
        exact_quote=quote if quote is not None else span.extracted_text_exact,
    )


def _flag(var: str = "var-a", expected: bool = True) -> Condition:
    return Condition(kind=ConditionKind.FLAG, variable_ref=var, expected=expected)


def _rule(  # noqa: PLR0913
    rule_id: str,
    condition: Condition | LogicalExpression,
    *,
    state: CandidateState = CandidateState.PROPOSED,
    protocol_version_id: str = _PROTOCOL,
    action_text: str | None = None,
    condition_bindings: tuple[EvidenceBinding, ...] | None = None,
) -> CandidateRule:
    target = action_text or f"{rule_id} action"
    action = ActionSpec(
        action_id=f"act-{rule_id}",
        action_type=ActionType.DECISION,
        target_text=target,
        evidence_bindings=(_binding("/target_text", f"span-{rule_id}"),),
    )
    return CandidateRule(
        candidate_id=rule_id,
        revision=1,
        protocol_version_id=protocol_version_id,
        condition=condition,
        actions=(action,),
        observation_refs=(f"obs-{rule_id}",),
        evidence_class=EvidenceClass.NORMALIZED,
        evidence_bindings=condition_bindings or (_binding("/condition", f"span-{rule_id}"),),
        candidate_state=state,
    )


def _relation(  # noqa: PLR0913
    relation_id: str,
    source: str,
    target: str,
    relation_type: RelationType,
    *,
    label: str | None = None,
    state: CandidateState = CandidateState.PROPOSED,
    evidence_class: EvidenceClass = EvidenceClass.NORMALIZED,
    evidence: tuple[EvidenceBinding, ...] | None = None,
) -> CandidateRelation:
    return CandidateRelation(
        candidate_relation_id=relation_id,
        revision=1,
        source_ref=source,
        target_refs=(target,),
        relation_type=relation_type,
        branch_label=label,
        observation_refs=(f"obs-{source}",),
        evidence_class=evidence_class,
        evidence_bindings=evidence or (_binding("/target_refs/0", f"span-{source}"),),
        candidate_state=state,
    )


def _graph(
    rules: tuple[CandidateRule, ...],
    relations: tuple[CandidateRelation, ...],
    *,
    issues: tuple[Issue, ...] = (),
    extra_spans: tuple[SourceSpan, ...] = (),
    extra_variables: tuple[VariableSpec, ...] = (),
) -> CandidateGraph:
    span_map = {
        span.span_id: span
        for span in (
            *(_span(f"span-{rule.candidate_id}") for rule in rules),
            *(_span(f"span-{variable.variable_id}") for variable in extra_variables),
            _span("span-var-a"),
            *extra_spans,
        )
    }
    spans = tuple(span_map.values())
    observations = tuple(
        Observation(
            observation_id=f"obs-{rule.candidate_id}",
            kind=ObservationKind.RECOMMENDATION,
            span_refs=(f"span-{rule.candidate_id}",),
            exact_quote=spans[0].extracted_text_exact,
        )
        for rule in rules
    )
    variables = (
        VariableSpec(
            variable_id="var-a",
            label="synthetic flag",
            value_type=VariableType.BOOLEAN,
            evidence_bindings=(_binding("/label", "span-var-a"),),
        ),
        *extra_variables,
    )
    return CandidateGraph(
        graph_id="graph-synthetic",
        generation_run_id="run-synthetic-phase6",
        protocol_version_id=_PROTOCOL,
        document_id="doc-synthetic",
        extraction_run_id="run-synthetic",
        observations=observations,
        variables=variables,
        rules=rules,
        relations=relations,
        issues=issues,
        source_spans=spans,
        attempts=(),
    )


def _manifest(roots: tuple[str, ...] = ("rule-a",)) -> ProjectionManifest:
    return ProjectionManifest(
        protocol_version_id=_PROTOCOL,
        stages=tuple(StageRoot(rule_id=root, label=f"stage {root}") for root in roots),
    )


def _errors(report: CandidateStructureReport) -> set[str]:
    return {
        finding.code for finding in report.findings if finding.severity is FindingSeverity.ERROR
    }


def _warnings(report: CandidateStructureReport) -> set[str]:
    return {
        finding.code for finding in report.findings if finding.severity is FindingSeverity.WARNING
    }


def _base() -> CandidateGraph:
    return _graph(
        (
            _rule("rule-a", _flag()),
            _rule("rule-b", _flag()),
            _rule("rule-c", _flag()),
        ),
        (
            _relation("rel-flow-1", "rule-a", "rule-b", RelationType.FLOW),
            _relation("rel-sup-1", "rule-a", "rule-c", RelationType.SUPPORTS),
        ),
    )


# --- Identity and fail-closed deserialization ---------------------------------


def test_tampered_json_fails_closed() -> None:
    text = dump_candidate_graph(_base())
    tampered = text.replace('"rule-b"', '"rule-missing"', 1)
    with pytest.raises(ValueError):
        load_candidate_graph(tampered)


def test_cross_protocol_rule_identity_is_error() -> None:
    graph = _graph(
        (_rule("rule-a", _flag(), protocol_version_id="OTHER-001-v1"),),
        (),
    )
    report = validate_candidate_structure(graph)
    assert "IDENTITY_PROTOCOL_MISMATCH" in _errors(report)
    assert report.review_readiness is NOT_READY_FOR_CLINICAL_REVIEW


def test_cross_document_span_is_error() -> None:
    graph = _graph(
        (_rule("rule-a", _flag()),),
        (),
        extra_spans=(_span("span-rule-a", document_id="doc-foreign"),),
    )
    report = validate_candidate_structure(graph)
    assert "IDENTITY_DOCUMENT_MISMATCH" in _errors(report)


# --- Provenance ---------------------------------------------------------------


def test_invalid_claim_path_is_error() -> None:
    rule = _rule("rule-a", _flag(), condition_bindings=(_binding("/nonsense", "span-rule-a"),))
    graph = _graph((rule,), ())
    report = validate_candidate_structure(graph)
    assert "PROVENANCE_CLAIM_PATH_UNRESOLVED" in _errors(report)
    assert report.provenance_status == "FAILED"


def test_malformed_exact_quote_is_error() -> None:
    rule = _rule(
        "rule-a",
        _flag(),
        condition_bindings=(_binding("/condition", "span-rule-a", quote="not in the span"),),
    )
    graph = _graph((rule,), ())
    report = validate_candidate_structure(graph)
    assert "PROVENANCE_QUOTE_NOT_FOUND" in _errors(report)


def test_valid_provenance_passes() -> None:
    report = validate_candidate_structure(_base())
    assert report.provenance_status == "PASSED"
    assert "PROVENANCE_QUOTE_NOT_FOUND" not in _errors(report)


# --- Expression invariants ----------------------------------------------------


def test_valid_n_of_m_accepted() -> None:
    condition = LogicalExpression(
        operator=LogicalOperator.AT_LEAST_N,
        operands=(_flag(), _flag(), _flag(), _flag()),
        threshold=3,
    )
    graph = _graph((_rule("rule-a", condition),), ())
    report = validate_candidate_structure(graph)
    assert "EXPRESSION_INVALID_N_OF_M" not in _errors(report)


def test_impossible_n_of_m_fails_at_construction() -> None:
    with pytest.raises(ValueError):
        LogicalExpression(
            operator=LogicalOperator.AT_LEAST_N,
            operands=(_flag(), _flag(), _flag()),
            threshold=4,
        )


def test_empty_expression_fails_at_construction() -> None:
    with pytest.raises(ValueError):
        LogicalExpression(operator=LogicalOperator.AND, operands=())


def test_degenerate_single_operand_and_is_warning() -> None:
    condition = LogicalExpression(operator=LogicalOperator.AND, operands=(_flag(),))
    graph = _graph((_rule("rule-a", condition),), ())
    report = validate_candidate_structure(graph)
    assert "EXPRESSION_DEGENERATE_OPERATOR" in _warnings(report)


# --- Relations and states -----------------------------------------------------


def test_sequential_relation_with_inferred_evidence_is_error() -> None:
    graph = _graph(
        (_rule("rule-a", _flag()), _rule("rule-b", _flag())),
        (
            _relation(
                "rel-bad",
                "rule-a",
                "rule-b",
                RelationType.FLOW,
                evidence_class=EvidenceClass.INFERRED,
            ),
        ),
    )
    report = validate_candidate_structure(graph)
    assert "RELATION_SEQUENTIAL_EVIDENCE_UNRESOLVED" in _errors(report)


def test_blocked_without_issue_is_warning() -> None:
    graph = _graph(
        (_rule("rule-a", _flag(), state=CandidateState.BLOCKED),),
        (),
    )
    report = validate_candidate_structure(graph)
    assert "STATE_BLOCKED_WITHOUT_ISSUE" in _warnings(report)


def test_blocked_with_linked_issue_is_clean() -> None:
    graph = _graph(
        (_rule("rule-a", _flag(), state=CandidateState.BLOCKED),),
        (),
        issues=(
            Issue(
                issue_id="issue-a",
                category=IssueCategory.EXTRACTION_LIMITATION,
                severity=IssueSeverity.BLOCKING,
                description="block reason",
                related_ids=("rule-a",),
            ),
        ),
    )
    report = validate_candidate_structure(graph)
    assert "STATE_BLOCKED_WITHOUT_ISSUE" not in _warnings(report)


def test_branch_without_label_is_warning() -> None:
    graph = _graph(
        (_rule("rule-a", _flag()), _rule("rule-b", _flag())),
        (_relation("rel-branch", "rule-a", "rule-b", RelationType.BRANCH),),
    )
    report = validate_candidate_structure(graph)
    assert "RELATION_BRANCH_LABEL_MISSING" in _warnings(report)


# --- Topology -----------------------------------------------------------------


def test_disconnected_contextual_component_is_warning() -> None:
    graph = _graph(
        (_rule("rule-a", _flag()), _rule("rule-b", _flag()), _rule("rule-d", _flag())),
        (_relation("rel-flow-1", "rule-a", "rule-b", RelationType.FLOW),),
    )
    report = validate_candidate_structure(graph)
    assert "TOPOLOGY_DISCONNECTED_COMPONENT" in _warnings(report)
    assert any("rule-d" in component.rule_ids for component in report.disconnected_components)


def test_unreachable_sequential_component_is_warning() -> None:
    graph = _graph(
        (
            _rule("rule-a", _flag()),
            _rule("rule-b", _flag()),
            _rule("rule-e", _flag()),
            _rule("rule-x", _flag()),
        ),
        (
            _relation("rel-flow-1", "rule-a", "rule-b", RelationType.FLOW),
            _relation("rel-orphan", "rule-e", "rule-x", RelationType.FLOW),
        ),
    )
    report = validate_candidate_structure(graph, _manifest(roots=("rule-a",)))
    assert "TOPOLOGY_DISCONNECTED_COMPONENT" in _warnings(report)
    assert any(
        component.classification.value == "UNREACHABLE_PATHWAY"
        for component in report.disconnected_components
    )


def test_cycle_is_detected_not_fatal() -> None:
    graph = _graph(
        (_rule("rule-a", _flag()), _rule("rule-b", _flag())),
        (
            _relation("rel-forward", "rule-a", "rule-b", RelationType.FLOW),
            _relation("rel-back", "rule-b", "rule-a", RelationType.FLOW),
        ),
    )
    report = validate_candidate_structure(graph)
    assert "TOPOLOGY_CYCLE_DETECTED" in _warnings(report)
    assert report.cycles
    assert "IDENTITY_PROTOCOL_MISMATCH" not in _errors(report)


def test_multiple_roots_and_terminals_reported() -> None:
    graph = _graph(
        (_rule("rule-a", _flag()), _rule("rule-b", _flag()), _rule("rule-c", _flag())),
        (
            _relation("rel-flow-1", "rule-a", "rule-b", RelationType.FLOW),
            _relation("rel-sup-1", "rule-a", "rule-c", RelationType.SUPPORTS),
        ),
    )
    report = validate_candidate_structure(graph, _manifest(roots=("rule-a", "rule-c")))
    assert report.entry_points == ("rule-a", "rule-c")
    assert "rule-b" in report.terminal_nodes


def test_unknown_entry_point_is_error() -> None:
    report = validate_candidate_structure(_base(), _manifest(roots=("rule-missing",)))
    assert "ENTRY_POINT_UNKNOWN_RULE" in _errors(report)


# --- Projection parity and review readiness -----------------------------------


def _write_artifacts(tmp_path: Path) -> tuple[Path, Path, Path]:
    graph = _base()
    manifest = _manifest()
    html_path = tmp_path / "review_tree.html"
    svg_path = tmp_path / "review_tree.svg"
    questions_path = tmp_path / "questions.md"
    html_path.write_text(render_review_tree_html(graph, manifest), encoding="utf-8")
    svg_path.write_text(render_review_tree_svg(graph, manifest), encoding="utf-8")
    questions_path.write_text("# Clinical review questions\n\n1. Example?\n", encoding="utf-8")
    return html_path, svg_path, questions_path


def test_review_readiness_pass() -> None:

    with tempfile.TemporaryDirectory() as tmp:
        html_path, svg_path, questions_path = _write_artifacts(Path(tmp))
        report = validate_candidate_structure(
            _base(),
            _manifest(),
            artifact_files={
                "html": html_path,
                "svg": svg_path,
                "questions": questions_path,
            },
        )
    assert report.projection_parity_status == "PASSED"
    assert report.review_readiness is READY_FOR_CLINICAL_REVIEW


def test_review_readiness_fail_on_projection_drift() -> None:

    with tempfile.TemporaryDirectory() as tmp:
        html_path, svg_path, questions_path = _write_artifacts(Path(tmp))
        html_path.write_text("tampered visual", encoding="utf-8")
        report = validate_candidate_structure(
            _base(),
            _manifest(),
            artifact_files={
                "html": html_path,
                "svg": svg_path,
                "questions": questions_path,
            },
        )
    assert "PROJECTION_PARITY_MISMATCH" in _errors(report)
    assert report.projection_parity_status == "FAILED"
    assert report.review_readiness is NOT_READY_FOR_CLINICAL_REVIEW


def test_contextual_relation_drawn_as_sequence_is_error() -> None:

    with tempfile.TemporaryDirectory() as tmp:
        html_path, svg_path, questions_path = _write_artifacts(Path(tmp))
        tampered = svg_path.read_text(encoding="utf-8").replace(
            'id="e-rel-flow-1"', 'id="e-rel-flow-1"/><path id="e-rel-sup-1"'
        )
        svg_path.write_text(tampered, encoding="utf-8")
        report = validate_candidate_structure(
            _base(),
            _manifest(),
            artifact_files={
                "html": html_path,
                "svg": svg_path,
                "questions": questions_path,
            },
        )
    assert "PROJECTION_CONTEXTUAL_DRAWN_AS_SEQUENCE" in _errors(report)


def test_report_serialization_is_deterministic() -> None:
    report = validate_candidate_structure(_base())
    assert dump_candidate_structure_report(report) == dump_candidate_structure_report(report)
    payload = json.loads(dump_candidate_structure_report(report))
    assert payload["rule_count"] == len(_base().rules)
    assert payload["review_readiness"] in {
        READY_FOR_CLINICAL_REVIEW,
        NOT_READY_FOR_CLINICAL_REVIEW,
    }


def test_review_packet_binds_hashes() -> None:

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        graph = _base()
        manifest = _manifest()
        graph_json = root / "candidate_graph.json"
        graph_json.write_text(dump_candidate_graph(graph), encoding="utf-8")
        html = root / "review_tree.html"
        svg = root / "review_tree.svg"
        html.write_text(render_review_tree_html(graph, manifest), encoding="utf-8")
        svg.write_text(render_review_tree_svg(graph, manifest), encoding="utf-8")
        questions = root / "questions.md"
        questions.write_text("# questions\n", encoding="utf-8")
        phase5 = root / "phase5"
        phase5.mkdir()
        for name in (
            "projection.yaml",
            "reconciliation_report.md",
            "review_summary.md",
            "clinical_review_questions.md",
        ):
            (phase5 / name).write_text(f"{name}\n", encoding="utf-8")
        packet = root / "packet"
        report = build_review_packet(
            graph=graph,
            manifest=manifest,
            graph_json_path=graph_json,
            review_visuals=(("review_tree.html", html), ("review_tree.svg", svg)),
            phase5_dir=phase5,
            questions_path=questions,
            packet_dir=packet,
            project_root=root,
        )
        manifest_data = json.loads((packet / "review_manifest.json").read_text(encoding="utf-8"))
        report_json_path = packet / "validation_report.json"
        assert manifest_data["schema"] == "review-manifest-v1"
        assert manifest_data["graph_content_hash"] == report.graph_content_hash
        assert manifest_data["validation_report_sha256"] == sha256_file(report_json_path)
        assert manifest_data["candidate_hashes"] == {
            rule.candidate_id: rule.content_hash for rule in graph.rules
        }
        for artifact in manifest_data["review_bound_artifacts"]:
            assert artifact["sha256"] == sha256_file(root / Path(artifact["path"]))
        for artifact in manifest_data["phase5_review_artifacts"]:
            assert artifact["sha256"] == sha256_file(root / Path(artifact["path"]))


def test_review_packet_paths_are_relative_and_relocatable() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        graph = _base()
        manifest = _manifest()
        graph_json = root / "candidate_graph.json"
        graph_json.write_text(dump_candidate_graph(graph), encoding="utf-8")
        html = root / "review_tree.html"
        svg = root / "review_tree.svg"
        html.write_text(render_review_tree_html(graph, manifest), encoding="utf-8")
        svg.write_text(render_review_tree_svg(graph, manifest), encoding="utf-8")
        questions = root / "questions.md"
        questions.write_text("# questions\n", encoding="utf-8")
        phase5 = root / "phase5"
        phase5.mkdir()
        for name in (
            "projection.yaml",
            "reconciliation_report.md",
            "review_summary.md",
            "clinical_review_questions.md",
        ):
            (phase5 / name).write_text(f"{name}\n", encoding="utf-8")
        build_review_packet(
            graph=graph,
            manifest=manifest,
            graph_json_path=graph_json,
            review_visuals=(("review_tree.html", html), ("review_tree.svg", svg)),
            phase5_dir=phase5,
            questions_path=questions,
            packet_dir=root / "packet",
            project_root=root,
        )
        manifest_data = json.loads(
            (root / "packet" / "review_manifest.json").read_text(encoding="utf-8")
        )
        stored_paths = (
            [artifact["path"] for artifact in manifest_data["review_bound_artifacts"]]
            + [artifact["path"] for artifact in manifest_data["phase5_review_artifacts"]]
            + [manifest_data["clinical_review_questions"]]
        )
        assert stored_paths
        for stored in stored_paths:
            assert not Path(stored).is_absolute()
            assert ".." not in Path(stored).parts
        relocated = Path(tmp) / "other-checkout"
        shutil.copytree(root, relocated, dirs_exist_ok=True)
        relocated_manifest = json.loads(
            (relocated / "packet" / "review_manifest.json").read_text(encoding="utf-8")
        )
        for artifact in relocated_manifest["review_bound_artifacts"]:
            assert artifact["sha256"] == sha256_file(relocated / Path(artifact["path"]))
        for artifact in relocated_manifest["phase5_review_artifacts"]:
            assert artifact["sha256"] == sha256_file(relocated / Path(artifact["path"]))
        assert (relocated / Path(relocated_manifest["clinical_review_questions"])).is_file()


def test_review_packet_rejects_paths_outside_project_root() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "repo"
        root.mkdir()
        graph = _base()
        manifest = _manifest()
        graph_json = root / "candidate_graph.json"
        graph_json.write_text(dump_candidate_graph(graph), encoding="utf-8")
        html = root / "review_tree.html"
        svg = root / "review_tree.svg"
        html.write_text(render_review_tree_html(graph, manifest), encoding="utf-8")
        svg.write_text(render_review_tree_svg(graph, manifest), encoding="utf-8")
        questions = root / "questions.md"
        questions.write_text("# questions\n", encoding="utf-8")
        phase5 = root / "phase5"
        phase5.mkdir()
        for name in (
            "projection.yaml",
            "reconciliation_report.md",
            "review_summary.md",
            "clinical_review_questions.md",
        ):
            (phase5 / name).write_text(f"{name}\n", encoding="utf-8")
        outside = Path(tmp) / "outside.html"
        outside.write_text("outside\n", encoding="utf-8")
        with pytest.raises(ValueError, match="outside the project root"):
            build_review_packet(
                graph=graph,
                manifest=manifest,
                graph_json_path=graph_json,
                review_visuals=(("review_tree.html", outside), ("review_tree.svg", svg)),
                phase5_dir=phase5,
                questions_path=questions,
                packet_dir=root / "packet",
                project_root=root,
            )


def test_no_approved_candidate_state_reported() -> None:
    report = validate_candidate_structure(_base())
    assert any(finding.code == "STATE_NO_APPROVED_ARTIFACTS" for finding in report.findings)
