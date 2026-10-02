"""Phase 5 semantic reconciliation for the CT-PL-193 v9 (NAC) candidate graph.

This module records the OpenCode agent's per-relation semantic review of the
Phase 4 NAC CandidateRelations. It loads the Phase 4 graph, applies the
decisions below, re-runs deterministic structural validation, and writes the
Phase 5 artifacts. It is protocol-specific candidate knowledge: nothing here
is generic engine code and nothing is clinically approved.

Review principles applied:
- FLOW/BRANCH only where the source supports clinical progression or a
  condition-labelled alternative.
- Contextual relations (BRANCH_CONTEXT/SUPPORTS) never become pathway arrows.
- Treatment-table content remains BLOCKED; no uncertain table association is
  promoted to a confident FLOW.
- Disconnected components stay disconnected; no connector is invented.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from artifacts.phase5._mechanics import (
    edit_relation,
    load_candidate_graph,
    rebuild,
    write_outputs,
)
from cpg_tree.candidates.enums import RelationType
from cpg_tree.candidates.graph import CandidateGraph

ROOT = Path(__file__).resolve().parents[3]
PHASE4_JSON = ROOT / "artifacts/phase4/nac/candidate_graph.json"
OUT_DIR = Path(__file__).parent


def reconcile() -> CandidateGraph:
    """Apply the NAC relation-level semantic decisions and rebuild the graph."""
    graph = load_candidate_graph(PHASE4_JSON.read_text(encoding="utf-8"))
    initial_relations = len(graph.relations)
    relations = {relation.candidate_relation_id: relation for relation in graph.relations}

    decisions: list[tuple[str, str, str]] = []
    kept: dict[str, str] = {}

    # --- Changed relations -------------------------------------------------
    # nac-rel-18: FilmArray -> adjust-to-results.
    # The continuation only exists when a molecular result is available; the
    # condition-labelled alternative is a BRANCH, not unconditional FLOW.
    relations["nac-rel-18"] = edit_relation(
        relations["nac-rel-18"],
        relation_type=RelationType.BRANCH,
        branch_label="molecular result available",
    )
    decisions.append(
        (
            "nac-rel-18",
            "RETYPE FLOW→BRANCH",
            "Adjustment is conditioned on a molecular result being available; a "
            "condition-labelled BRANCH preserves that instead of unconditional FLOW.",
        )
    )
    # nac-rel-19: sputum culture -> adjust-to-results. Same reasoning; the two
    # result channels now use the same semantics.
    relations["nac-rel-19"] = edit_relation(
        relations["nac-rel-19"],
        relation_type=RelationType.BRANCH,
        branch_label="culture result available",
    )
    decisions.append(
        (
            "nac-rel-19",
            "RETYPE SUPPORTS→BRANCH",
            "Culture results condition the adjustment step; the relation becomes a "
            "condition-labelled BRANCH matching the molecular channel.",
        )
    )

    # --- Kept relations (semantic review passed) ---------------------------
    kept.update(
        {
            "nac-rel-01": "source: compatible picture plus new infiltrate supports "
            "pneumonia classification.",
            "nac-rel-02": "source: negative initial radiograph plus high suspicion "
            "requires repeating radiography at 48 hours.",
            "nac-rel-03": "source: inconclusive radiograph with high probability and "
            "priority/complication criteria selects CT.",
            "nac-rel-04": "laboratory workup runs parallel to imaging for suspected "
            "pneumonia; contextual by design, not a sequential step.",
            "nac-rel-05": "source states labs are requested 'para definir la necesidad "
            "de hospitalización'; SUPPORTS (informs a decision) is the correct type.",
            "nac-rel-06": "source: added laboratories apply 'en pacientes con indicación "
            "de hospitalización'.",
            "nac-rel-07": "source: sputum Gram/culture applies to patients with "
            "diagnosis AND hospitalization indication.",
            "nac-rel-08": "source: FilmArray applies to confirmed pneumonia with "
            "hospitalization indication.",
            "nac-rel-09": "source: hemocultures apply to hospitalized patients meeting "
            "the compound severity criteria.",
            "nac-rel-10": "source: severe contexts (shock/severe sepsis/multiorgan "
            "failure) escalate the hospitalized laboratory panel.",
            "nac-rel-10a": "source: desaturation independently triggers arterial blood gases.",
            "nac-rel-11": "ICU/UCE direct indications are a separate severity decision "
            "below hospital-level management; BRANCH preserves that.",
            "nac-rel-12": "the three-of-nine criteria pathway is a distinct ICU/UCE "
            "qualification mechanism; BRANCH preserves it separately.",
            "nac-rel-13": "treatment context hangs off the hospitalization decision as "
            "BRANCH_CONTEXT; visual table evidence must not become confident flow.",
            "nac-rel-14": "treatment context hangs off the hospitalization decision as "
            "BRANCH_CONTEXT; visual table evidence must not become confident flow.",
            "nac-rel-15": "treatment context hangs off the hospitalization decision as "
            "BRANCH_CONTEXT; visual table evidence must not become confident flow.",
            "nac-rel-16": "treatment context hangs off the hospitalization decision as "
            "BRANCH_CONTEXT; visual table evidence must not become confident flow.",
            "nac-rel-17": "treatment context hangs off the hospitalization decision as "
            "BRANCH_CONTEXT; visual table evidence must not become confident flow.",
            "nac-rel-20": "after inpatient empirical treatment the discharge criteria "
            "are assessed; the discharge-plan section supports the continuation.",
            "nac-rel-21": "after inpatient empirical treatment the discharge criteria "
            "are assessed; the discharge-plan section supports the continuation.",
            "nac-rel-22": "after inpatient empirical treatment the discharge criteria "
            "are assessed; the discharge-plan section supports the continuation.",
            "nac-rel-23": "after inpatient empirical treatment the discharge criteria "
            "are assessed; the discharge-plan section supports the continuation.",
            "nac-rel-24": "after inpatient empirical treatment the discharge criteria "
            "are assessed; the discharge-plan section supports the continuation.",
            "nac-rel-25": "source: 'Al momento del alta se indicarán al paciente los "
            "signos y síntomas que sugieren recaída'.",
            "nac-rel-26": "source: 'cita de revisión con medicina interna a las 4 "
            "semanas del alta'.",
            "nac-rel-27": "repeat radiography supports/confirms the diagnosis; "
            "SUPPORTS is the correct contextual type.",
            "nac-rel-28": "serum LDH/total proteins accompany thoracentesis "
            "interpretation; condition-labelled BRANCH is appropriate.",
            "nac-rel-29": "induced sputum applies when spontaneous collection is "
            "impossible; condition-labelled BRANCH.",
            "nac-rel-30": "deep-sample FilmArray panel is the first option when there "
            "is no SARS-CoV-2 suspicion; condition-labelled BRANCH.",
            "nac-rel-31": "nasopharyngeal panel applies when the patient does not "
            "expectorate; condition-labelled BRANCH.",
            "nac-rel-32": "qualifying presumed parapneumonic effusion selects the "
            "pleural study; condition-labelled BRANCH.",
        }
    )

    new_relations = tuple(relations[relation.candidate_relation_id] for relation in graph.relations)
    graph = rebuild(replace(graph, relations=new_relations))

    write_outputs(
        graph=graph,
        out_dir=OUT_DIR,
        protocol_name="CT-PL-193 v9 (NAC)",
        initial_relations=initial_relations,
        decisions=tuple(decisions),
        kept_rationales=kept,
    )
    return graph


if __name__ == "__main__":
    result = reconcile()
    print(
        f"reconciled NAC: {len(result.rules)} rules, "
        f"{len(result.relations)} relations, {len(result.issues)} issues"
    )
