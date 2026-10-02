"""Phase 5 semantic reconciliation for the CT-PL-197 v06 (ITU) candidate graph.

This module records the OpenCode agent's per-relation semantic review of the
Phase 4 ITU CandidateRelations. It is protocol-specific candidate knowledge:
nothing here is generic engine code and nothing is clinically approved.

Review principles applied:
- FLOW/BRANCH only where the source supports clinical progression or a
  condition-labelled alternative.
- The upper-UTI hospitalization/outpatient contradiction stays visible: the
  conflicting outpatient branch is BLOCKED, not deleted.
- Pregnancy is a contextual subgraph; it is not attached as unconditional FLOW.
- Culture-guided adjustment and prevention are condition-labelled BRANCH
  relations, never unconditional sequence.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from artifacts.phase5._mechanics import (
    add_relation,
    edit_relation,
    load_candidate_graph,
    rebuild,
    write_outputs,
)
from cpg_tree.candidates.enums import CandidateState, RelationType
from cpg_tree.candidates.graph import CandidateGraph

ROOT = Path(__file__).resolve().parents[3]
PHASE4_JSON = ROOT / "artifacts/phase4/itu/candidate_graph.json"
OUT_DIR = Path(__file__).parent

_SYMPTOMATIC = "itu-r02-symptomatic-uti-classification"
_SYMPTOMATIC_OBS = "obs-itu-r02-symptomatic-uti-classification"


def reconcile() -> CandidateGraph:
    """Apply the ITU relation-level semantic decisions and rebuild the graph."""
    graph = load_candidate_graph(PHASE4_JSON.read_text(encoding="utf-8"))
    initial_relations = len(graph.relations)
    relations = {relation.candidate_relation_id: relation for relation in graph.relations}

    decisions: list[tuple[str, str, str]] = []
    kept: dict[str, str] = {}

    # --- Retargeted relations ----------------------------------------------
    # itu-rel-14: urgent imaging. The source conditions urgent imaging on
    # "pacientes con infección urinaria y choque séptico... falla renal aguda,
    # clínica de complicación local o fiebre persistente..." — i.e. symptomatic
    # UTI with listed triggers, not only classified upper UTI. Anchor at the
    # symptomatic-UTI classification rule.
    relations["itu-rel-14"] = edit_relation(
        relations["itu-rel-14"],
        source_ref=_SYMPTOMATIC,
        observation_refs=(_SYMPTOMATIC_OBS,),
        branch_label=(
            "urgent-imaging context (shock, acute renal failure, local "
            "complication, or fever persisting after 72 h of correct therapy)"
        ),
    )
    decisions.append(
        (
            "itu-rel-14",
            "RETARGET r05→r02",
            "The source conditions urgent imaging on symptomatic UTI plus listed "
            "triggers, not on the upper-UTI classification alone.",
        )
    )
    # itu-rel-42: pregnancy ultrasound. The source lists pyelonephritis, more
    # than one pregnancy episode, and stone suspicion as pregnancy ultrasound
    # indications; anchoring at symptomatic UTI covers all of them.
    relations["itu-rel-42"] = edit_relation(
        relations["itu-rel-42"],
        source_ref=_SYMPTOMATIC,
        observation_refs=(_SYMPTOMATIC_OBS,),
        branch_label="pregnancy with listed ultrasound indications",
    )
    decisions.append(
        (
            "itu-rel-42",
            "RETARGET r05→r02",
            "Pregnancy ultrasound indications (pyelonephritis, more than one "
            "episode, stone suspicion) are pregnancy-UTI contexts, anchored at the "
            "symptomatic classification.",
        )
    )

    # --- Blocked relation ----------------------------------------------------
    # itu-rel-23: outpatient upper UTI directly contradicts the hospitalization
    # bullet "ITU alta". Keep the branch visible but BLOCKED; clinical review
    # must adjudicate.
    relations["itu-rel-23"] = edit_relation(
        relations["itu-rel-23"],
        candidate_state=CandidateState.BLOCKED,
    )
    decisions.append(
        (
            "itu-rel-23",
            "BLOCK",
            "Outpatient upper-UTI treatment contradicts the upper-UTI "
            "hospitalization indication; the branch stays visible as BLOCKED "
            "instead of being silently deleted.",
        )
    )

    # --- Retyped relations ---------------------------------------------------
    # itu-rel-07: urine culture is a diagnostic pathway step with its own
    # exception, exactly like urinalysis and Gram; Phase 4 typed it as context.
    relations["itu-rel-07"] = edit_relation(
        relations["itu-rel-07"],
        relation_type=RelationType.BRANCH,
        branch_label="culture indicated unless its distinct exception applies",
    )
    decisions.append(
        (
            "itu-rel-07",
            "RETYPE BRANCH_CONTEXT→BRANCH",
            "Urine culture is a diagnostic decision with its own source-defined "
            "exception, matching the urinalysis and Gram branches; it belongs in "
            "the pathway, not as a floating context.",
        )
    )
    # itu-rel-29: prevention is a parallel table column conditioned on the same
    # pregnant upper-UTI context, not a step after treatment.
    relations["itu-rel-29"] = edit_relation(
        relations["itu-rel-29"],
        relation_type=RelationType.BRANCH_CONTEXT,
        branch_label="pregnant upper-UTI context",
    )
    decisions.append(
        (
            "itu-rel-29",
            "RETYPE FLOW→BRANCH_CONTEXT",
            "Preventive therapy is a parallel column of the pregnancy table "
            "conditioned on the same context, not a sequential step after "
            "treatment.",
        )
    )
    # itu-rel-30..38: culture/antibiogram availability conditions the
    # adjustment step; these are condition-labelled BRANCH relations.
    for rel_id in (
        "itu-rel-30",
        "itu-rel-31",
        "itu-rel-32",
        "itu-rel-33",
        "itu-rel-34",
        "itu-rel-35",
        "itu-rel-36",
        "itu-rel-37",
        "itu-rel-38",
    ):
        relations[rel_id] = edit_relation(
            relations[rel_id],
            relation_type=RelationType.BRANCH,
            branch_label="culture/antibiogram available",
        )
        decisions.append(
            (
                rel_id,
                "RETYPE FLOW→BRANCH",
                "Adjustment of empirical therapy is conditioned on culture and "
                "antibiogram availability; a condition-labelled BRANCH replaces "
                "unconditional FLOW.",
            )
        )
    # itu-rel-39..41: transition to oral-step/discharge eligibility only
    # exists when the listed criteria are met.
    for rel_id in ("itu-rel-39", "itu-rel-40", "itu-rel-41"):
        relations[rel_id] = edit_relation(
            relations[rel_id],
            relation_type=RelationType.BRANCH,
            branch_label="all listed criteria met",
        )
        decisions.append(
            (
                rel_id,
                "RETYPE FLOW→BRANCH",
                "Oral-step/discharge eligibility is conditioned on the listed "
                "criteria; the label is part of the BRANCH semantics.",
            )
        )

    # --- Kept relations (semantic review passed) -----------------------------
    kept.update(
        {
            "itu-rel-01": "source: asymptomatic-bacteriuria treatment eligibility "
            "is restricted to pregnancy or a qualifying invasive urinary procedure.",
            "itu-rel-02": "source: the eligibility decision leads to the table "
            "treatment alternatives.",
            "itu-rel-03": "source: lower-UTI definition features classify lower UTI.",
            "itu-rel-04": "source: upper-UTI definition features classify upper UTI.",
            "itu-rel-05": "source: emergency cytochemistry applies to suspected "
            "UTI except women with a first typical episode.",
            "itu-rel-06": "source: Gram stain applies to every emergency patient.",
            "itu-rel-08": "source: the sample must be taken before the first antibiotic dose.",
            "itu-rel-09": "source: permanent-catheter users need a newly inserted "
            "catheter and initial-volume discard.",
            "itu-rel-10": "source: >=100,000 CFU threshold applies to appropriately "
            "obtained spontaneous urine.",
            "itu-rel-11": "source: >=1,000 CFU threshold applies to the "
            "otherwise-unexplained symptomatic context.",
            "itu-rel-12": "source: the newly inserted catheter threshold follows "
            "the catheter sampling rule.",
            "itu-rel-13": "source: blood cultures apply to acute pyelonephritis "
            "with fever, hypothermia, or septic shock.",
            "itu-rel-15": "source: suspected small abscess/local nephritis selects contrast CT.",
            "itu-rel-16": "source: suspected structural abnormality selects CT urography.",
            "itu-rel-17": "source: suspected functional/emptying/obstructive "
            "abnormality selects ultrasound with post-void residual.",
            "itu-rel-18": "source: upper UTI is an explicit hospitalization "
            "indication bullet; the branch stays active and the conflict is "
            "handled by the BLOCKED outpatient relation.",
            "itu-rel-19": "source: every hospitalized ITU patient gets CBC, "
            "ionogram, renal function, and CRP.",
            "itu-rel-20": "source: hospitalized upper UTI without resistant "
            "Gram-negative risk selects the first table row.",
            "itu-rel-21": "source: resistant Gram-negative risk without shock "
            "selects the second table row; amikacin is avoided in shock.",
            "itu-rel-22": "source: resistant Gram-negative risk with shock "
            "selects meropenem empirically.",
            "itu-rel-24": "source: lower UTI selects the lower treatment row.",
            "itu-rel-25": "pregnancy upper treatment shares the pregnant upper-UTI "
            "context with the ultrasound rule; contextual by design.",
            "itu-rel-26": "source: pregnancy conditions the asymptomatic-"
            "bacteriuria pregnancy table row.",
            "itu-rel-27": "source: pregnancy conditions the lower-UTI pregnancy table row.",
            "itu-rel-28": "source: prevention in pregnancy lower UTI applies only "
            "when there is recurrence.",
            "itu-rel-43": "source: a normal dipstick plus low clinical suspicion "
            "rules out the diagnosis.",
        }
    )

    # --- Added relations -----------------------------------------------------
    added_relations = (
        add_relation(
            relation_id="itu-rel-44",
            source="itu-r09-urine-gram",
            targets=(
                "itu-r27-lower-treatment",
                "itu-r29-upper-outpatient-treatment",
                "itu-r30-upper-inpatient-no-resistant-risk",
                "itu-r31-upper-inpatient-resistant-no-shock",
                "itu-r32-upper-inpatient-resistant-shock",
            ),
            relation_type=RelationType.SUPPORTS,
            spans=("doc-800af94bc0654138-p003-e002", "doc-800af94bc0654138-p003-e003"),
            quote="guiar el tratamiento empírico",
            label="Gram informs empirical treatment choice",
        ),
        add_relation(
            relation_id="itu-rel-45",
            source="itu-r37-pregnancy-upper-prevention",
            targets=("itu-r38-adjust-to-culture",),
            relation_type=RelationType.BRANCH,
            spans=("doc-800af94bc0654138-p005-e003",),
            quote="La decisión se toma con base en los cultivos y pruebas de sensibilidad",
            label="culture/susceptibility available",
        ),
        add_relation(
            relation_id="itu-rel-46",
            source="itu-r35-pregnancy-lower-prevention",
            targets=("itu-r38-adjust-to-culture",),
            relation_type=RelationType.BRANCH,
            spans=("doc-800af94bc0654138-p005-e003",),
            quote="La decisión se toma con base en los cultivos y pruebas de sensibilidad",
            label="culture/susceptibility available",
        ),
    )

    new_relations = (
        tuple(relations[relation.candidate_relation_id] for relation in graph.relations)
        + added_relations
    )
    graph = rebuild(replace(graph, relations=new_relations))

    write_outputs(
        graph=graph,
        out_dir=OUT_DIR,
        protocol_name="CT-PL-197 v06 (ITU)",
        initial_relations=initial_relations,
        decisions=tuple(decisions),
        kept_rationales=kept,
    )
    return graph


if __name__ == "__main__":
    result = reconcile()
    print(
        f"reconciled ITU: {len(result.rules)} rules, "
        f"{len(result.relations)} relations, {len(result.issues)} issues"
    )
