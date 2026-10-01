"""Author the CT-PL-197 v06 Candidate Graph from the reviewed source PDF.

This module contains protocol-specific candidate knowledge. It does not parse
clinical meaning and nothing it emits is clinically approved.
"""

# ruff: noqa: PLR0913, PLR0917

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

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
from cpg_tree.candidates.graph import CandidateGraph, validate_candidate_graph
from cpg_tree.candidates.graph_serialization import write_candidate_graph
from cpg_tree.candidates.issues import Issue
from cpg_tree.candidates.observations import Observation
from cpg_tree.candidates.relations import CandidateRelation
from cpg_tree.candidates.rules import CandidateRule
from cpg_tree.candidates.variables import VariableSpec
from cpg_tree.extraction.layout import extract_document_map
from cpg_tree.knowledge.conditions import Condition, LogicalExpression
from cpg_tree.knowledge.enums import (
    ActionType,
    ComparisonOperator,
    ConditionKind,
    LogicalOperator,
    VariableType,
)

ROOT = Path(__file__).resolve().parents[3]
PDF = next((ROOT / "data/01_raw").glob("CT-PL-197*.pdf"))
OUT = Path(__file__).with_name("candidate_graph.json")
PROTOCOL_VERSION_ID = "CT-PL-197-v06"
DOCUMENT_ID = "doc-800af94bc0654138"


def _span(page: int, element: int) -> str:
    return f"{DOCUMENT_ID}-p{page:03d}-e{element:03d}"


def _binding(
    path: str,
    spans: tuple[str, ...],
    quote: str | None,
    transformation: str = "Structured from source wording; pending clinical review.",
) -> EvidenceBinding:
    return EvidenceBinding(
        claim_path=path,
        evidence_class=EvidenceClass.NORMALIZED,
        source_span_refs=spans,
        exact_quote=quote,
        transformation=transformation,
    )


def _flag(variable_ref: str, expected: bool = True) -> Condition:
    return Condition(kind=ConditionKind.FLAG, variable_ref=variable_ref, expected=expected)


def _cmp(variable_ref: str, operator: ComparisonOperator, operand: int | float) -> Condition:
    return Condition(
        kind=ConditionKind.COMPARISON,
        variable_ref=variable_ref,
        operator=operator,
        operand=operand,
    )


def _and(*operands: Condition | LogicalExpression) -> LogicalExpression:
    return LogicalExpression(operator=LogicalOperator.AND, operands=operands)


def _or(*operands: Condition | LogicalExpression) -> LogicalExpression:
    return LogicalExpression(operator=LogicalOperator.OR, operands=operands)


class _Author:
    def __init__(self) -> None:
        self.observations: list[Observation] = []
        self.variables: dict[str, VariableSpec] = {}
        self.rules: list[CandidateRule] = []
        self.relations: list[CandidateRelation] = []
        self.issues: list[Issue] = []

    def variable(
        self,
        variable_id: str,
        label: str,
        spans: tuple[str, ...],
        quote: str,
        value_type: VariableType = VariableType.BOOLEAN,
        unit: str | None = None,
    ) -> None:
        if variable_id not in self.variables:
            self.variables[variable_id] = VariableSpec(
                variable_id=variable_id,
                label=label,
                value_type=value_type,
                unit=unit,
                evidence_bindings=(_binding("/label", spans, quote),),
            )

    def rule(
        self,
        rule_id: str,
        condition: Condition | LogicalExpression,
        action_type: ActionType,
        target: str,
        condition_spans: tuple[str, ...],
        condition_quote: str,
        *,
        action_spans: tuple[str, ...] | None = None,
        action_quote: str | None = None,
        exceptions: tuple[Condition | LogicalExpression, ...] = (),
        exception_quote: str | None = None,
        action_fields: dict[str, object] | None = None,
        state: CandidateState = CandidateState.PROPOSED,
        flags: tuple[str, ...] = (),
        statement_kind: str = "recommendation",
    ) -> None:
        observation_id = f"obs-{rule_id}"
        action_id = f"act-{rule_id}"
        evidence_spans = action_spans or condition_spans
        evidence_quote = action_quote if action_quote is not None else condition_quote
        self.observations.append(
            Observation(
                observation_id=observation_id,
                kind=ObservationKind.RECOMMENDATION,
                span_refs=tuple(dict.fromkeys((*condition_spans, *evidence_spans))),
                exact_quote=condition_quote,
                subject_text=rule_id,
                predicate_text="supports candidate decision",
                object_text=target,
            )
        )
        self.rules.append(
            CandidateRule(
                candidate_id=rule_id,
                revision=1,
                protocol_version_id=PROTOCOL_VERSION_ID,
                condition=condition,
                actions=(
                    ActionSpec(
                        action_id=action_id,
                        action_type=action_type,
                        target_text=target,
                        evidence_bindings=(
                            _binding("/target_text", evidence_spans, evidence_quote),
                        ),
                        **dict(action_fields or {}),
                    ),
                ),
                exceptions=exceptions,
                observation_refs=(observation_id,),
                modality="protocol recommendation",
                statement_kind=statement_kind,
                evidence_class=EvidenceClass.NORMALIZED,
                evidence_bindings=(
                    _binding("/condition", condition_spans, condition_quote),
                    *(
                        (_binding("/exceptions/0", condition_spans, exception_quote),)
                        if exceptions
                        else ()
                    ),
                ),
                ambiguity_flags=flags,
                candidate_state=state,
            )
        )

    def relation(
        self,
        relation_id: str,
        source: str,
        target: str,
        relation_type: RelationType,
        spans: tuple[str, ...],
        quote: str,
        label: str | None = None,
        temporal: str | None = None,
    ) -> None:
        self.relations.append(
            CandidateRelation(
                candidate_relation_id=relation_id,
                revision=1,
                source_ref=source,
                target_refs=(target,),
                relation_type=relation_type,
                branch_label=label,
                temporal_qualifier=temporal,
                observation_refs=(f"obs-{source}",),
                evidence_class=EvidenceClass.NORMALIZED,
                evidence_bindings=(_binding("/target_refs/0", spans, quote),),
            )
        )


def build_graph() -> CandidateGraph:  # noqa: PLR0915
    """Build the independently authored ITU candidate graph."""
    author = _Author()

    # Definitions remain overlapping classifications, not one exclusive enum.
    definitions = tuple(_span(1, item) for item in range(12, 34))
    for variable_id, label, quote in (
        (
            "itu_significant_bacteriuria",
            "Significant bacteriuria",
            "Recuento significativo de colonias bacterianas",
        ),
        (
            "itu_attributable_symptoms_absent",
            "No signs or symptoms attributable to UTI",
            "sin signos o síntomas atribuibles a ITU",
        ),
        (
            "itu_attributable_symptoms_present",
            "Signs or symptoms attributable to UTI",
            "con signos o síntomas atribuibles a ITU",
        ),
        (
            "itu_structural_or_functional_abnormality",
            "Structural or functional urinary-tract abnormality",
            "alteraciones estructurales o",
        ),
        (
            "itu_lower_definition_features",
            "Acute bladder/urethral infection with lower-UTI definition features",
            "Infección aguda de la vejiga y/o la uretra",
        ),
        (
            "itu_upper_definition_features",
            "Acute kidney infection with significant bacteriuria",
            "Infección aguda del riñón acompañada por bacteriuria",
        ),
        (
            "itu_beyond_bladder_context",
            "Infection extends beyond the bladder or is febrile, bacteremic, catheter-associated, or prostatitis",
            "compromiso más allá de la vejiga",
        ),
    ):
        author.variable(variable_id, label, definitions, quote)
    author.rule(
        "itu-r01-asymptomatic-bacteriuria-classification",
        _and(_flag("itu_significant_bacteriuria"), _flag("itu_attributable_symptoms_absent")),
        ActionType.CLASSIFY,
        "Classify as asymptomatic bacteriuria",
        definitions,
        "Bacteriuria asintomática: Recuento significativo de colonias bacterianas",
    )
    author.rule(
        "itu-r02-symptomatic-uti-classification",
        _and(_flag("itu_significant_bacteriuria"), _flag("itu_attributable_symptoms_present")),
        ActionType.CLASSIFY,
        "Classify as urinary tract infection",
        definitions,
        "Infección del tracto urinario: Recuento significativo de colonias bacterianas",
    )
    author.rule(
        "itu-r03-complicated-structural-definition",
        _and(
            _flag("itu_attributable_symptoms_present"),
            _flag("itu_structural_or_functional_abnormality"),
        ),
        ActionType.CLASSIFY,
        "Classify under the structural/functional complicated-UTI definition",
        definitions,
        "Infección del tracto urinario complicada: ITU que ocurre en presencia de alteraciones estructurales o",
        flags=("Non-equivalent complicated-UTI definitions retained separately",),
    )
    author.rule(
        "itu-r04-lower-uti-classification",
        _flag("itu_lower_definition_features"),
        ActionType.CLASSIFY,
        "Classify as lower UTI",
        definitions,
        "Infección del tracto urinario bajo (cistitis y uretritis)",
    )
    author.rule(
        "itu-r05-upper-uti-classification",
        _flag("itu_upper_definition_features"),
        ActionType.CLASSIFY,
        "Classify as upper UTI / pyelonephritis",
        definitions,
        "Infección del tracto urinario alto (pielonefritis)",
    )
    author.rule(
        "itu-r06-complicated-beyond-bladder-definition",
        _flag("itu_beyond_bladder_context"),
        ActionType.CLASSIFY,
        "Classify under the beyond-bladder complicated-UTI definition",
        definitions,
        "ITU complicada: infección en mujeres u hombres, con compromiso más allá de la vejiga",
        flags=("Non-equivalent complicated-UTI definitions retained separately",),
    )

    # Emergency diagnostic testing with distinct exceptions.
    urinalysis = tuple(_span(2, item) for item in range(38, 52))
    for variable_id, label, quote in (
        (
            "itu_suspected_in_emergency",
            "Suspected UTI in emergency care",
            "urgencias con sospecha de ITU",
        ),
        (
            "itu_woman_first_episode_typical",
            "Woman with first episode and typical symptoms",
            "mujeres con primer episodio y síntomas típicos",
        ),
        ("itu_dipstick_normal", "Urine dipstick is normal", "resultado normal"),
        ("itu_low_clinical_suspicion", "Low clinical suspicion", "baja sospecha clínica"),
    ):
        author.variable(variable_id, label, urinalysis, quote)
    author.rule(
        "itu-r07-urinalysis",
        _flag("itu_suspected_in_emergency"),
        ActionType.REQUEST_TEST,
        "Obtain urine cytochemistry",
        urinalysis,
        "Se debe realizar citoquímico de orina a todo paciente en el servicio de ",
        exceptions=(_flag("itu_woman_first_episode_typical"),),
        exception_quote="excepto mujeres con primer episodio y síntomas típicos",
    )
    author.rule(
        "itu-r08-normal-dipstick",
        _and(_flag("itu_dipstick_normal"), _flag("itu_low_clinical_suspicion")),
        ActionType.CLASSIFY,
        "Exclude UTI diagnosis",
        urinalysis,
        "un resultado normal en pacientes con baja sospecha clínica descarta ",
    )

    gram = (_span(3, 2), _span(3, 3))
    author.variable(
        "itu_emergency_patient",
        "Patient in emergency care",
        gram,
        "pacientes en el servicio de urgencias",
    )
    author.rule(
        "itu-r09-urine-gram",
        _flag("itu_emergency_patient"),
        ActionType.REQUEST_TEST,
        "Obtain Gram stain of uncentrifuged urine to guide empirical treatment",
        gram,
        "debe realizarse en todos los pacientes en el servicio de urgencias",
    )

    culture = tuple(_span(3, item) for item in range(4, 16))
    for variable_id, label, quote, value_type, unit in (
        (
            "itu_culture_indicated_context",
            "Any UTI/bacteriuria evaluation context",
            "Debe solicitarse en todos los casos",
            VariableType.BOOLEAN,
            None,
        ),
        (
            "itu_premenopausal_first_uncomplicated_lower",
            "Premenopausal woman with first uncomplicated lower-UTI episode",
            "primer episodio de ITU baja no complicada en mujer premenopáusica",
            VariableType.BOOLEAN,
            None,
        ),
        (
            "itu_spontaneous_sample_colonies",
            "Colonies in appropriately obtained spontaneous urine",
            "micción",
            VariableType.NUMERIC,
            "CFU",
        ),
        (
            "itu_symptomatic_sample_colonies",
            "Colonies in patient with otherwise unexplained symptoms",
            "paciente con síntomas no explicados",
            VariableType.NUMERIC,
            "CFU",
        ),
        (
            "itu_new_catheter_sample_colonies",
            "Colonies in newly inserted catheter sample",
            "sonda vesical recién",
            VariableType.NUMERIC,
            "CFU",
        ),
        (
            "itu_permanent_catheter_user",
            "Permanent urinary catheter user",
            "usuarios de sonda vesical permanente",
            VariableType.BOOLEAN,
            None,
        ),
    ):
        author.variable(variable_id, label, culture, quote, value_type, unit)
    author.rule(
        "itu-r10-urine-culture",
        _flag("itu_culture_indicated_context"),
        ActionType.REQUEST_TEST,
        "Obtain urine culture for bacteriuria confirmation and antimicrobial susceptibility",
        culture,
        "Debe solicitarse en todos los casos",
        exceptions=(_flag("itu_premenopausal_first_uncomplicated_lower"),),
        exception_quote="excepto primer episodio de ITU baja no complicada en mujer premenopáusica",
    )
    author.rule(
        "itu-r11-culture-positive-spontaneous",
        _cmp("itu_spontaneous_sample_colonies", ComparisonOperator.GE, 100000),
        ActionType.CLASSIFY,
        "Classify spontaneous urine culture as positive",
        culture,
        "el crecimiento de ≥105 UFC de una bacteria en una muestra de orina obtenida de forma adecuada por micción ",
    )
    author.rule(
        "itu-r12-culture-positive-symptomatic",
        _cmp("itu_symptomatic_sample_colonies", ComparisonOperator.GE, 1000),
        ActionType.CLASSIFY,
        "Classify culture as positive in symptomatic context",
        culture,
        "con un crecimiento ≥103 UFC en un paciente con síntomas no explicados por otra patología",
    )
    author.rule(
        "itu-r13-culture-positive-new-catheter",
        _cmp("itu_new_catheter_sample_colonies", ComparisonOperator.GE, 100),
        ActionType.CLASSIFY,
        "Classify newly inserted catheter urine culture as positive",
        culture,
        "crecimiento de ≥102 UFC de una bacteria en una muestra de orina obtenida a través de una sonda vesical recién ",
    )
    author.rule(
        "itu-r14-sample-before-antibiotic",
        _flag("itu_culture_indicated_context"),
        ActionType.REQUEST_TEST,
        "Collect urine sample before first antibiotic dose",
        culture,
        "Toma de la muestra: debe tomarse antes de la primera dosis de antibiótico",
    )
    author.rule(
        "itu-r15-permanent-catheter-sampling",
        _flag("itu_permanent_catheter_user"),
        ActionType.REQUEST_TEST,
        "Replace catheter and collect urine from the newly inserted catheter after discarding the initial 15-30 mL",
        culture,
        "en todos los casos de usuarios de sonda vesical permanente ",
    )

    blood = tuple(_span(3, item) for item in range(16, 23))
    for variable_id, label, quote in (
        (
            "itu_hospitalized",
            "Patient with UTI is hospitalized",
            "paciente con ITU que sea hospitalizado",
        ),
        ("itu_pyelonephritis", "Acute pyelonephritis", "pielonefritis aguda"),
        ("itu_fever", "Fever", "fiebre"),
        ("itu_hypothermia", "Hypothermia", "hipotermia"),
        ("itu_septic_shock", "Septic shock", "choque séptico"),
    ):
        author.variable(variable_id, label, blood, quote)
    author.rule(
        "itu-r16-hospital-blood-tests",
        _flag("itu_hospitalized"),
        ActionType.REQUEST_TEST,
        "Obtain CBC, ionogram, renal function, and C-reactive protein",
        blood,
        "En todo paciente con ITU que sea hospitalizado debe obtenerse muestra de sangre",
    )
    author.rule(
        "itu-r17-blood-cultures",
        _and(
            _flag("itu_pyelonephritis"),
            _or(_flag("itu_fever"), _flag("itu_hypothermia"), _flag("itu_septic_shock")),
        ),
        ActionType.REQUEST_TEST,
        "Obtain blood cultures",
        blood,
        "Los hemocultivos deben solicitarse en todos los casos de pielonefritis aguda que cursan con fiebre",
    )

    # Imaging is a nested decision: urgency first, then modality by suspected abnormality.
    imaging = tuple(_span(3, item) for item in range(23, 33))
    for variable_id, label, quote in (
        ("itu_acute_renal_failure", "Acute renal failure", "falla renal aguda"),
        (
            "itu_local_complication",
            "Clinical evidence of local complication",
            "clínica de complicación local",
        ),
        (
            "itu_fever_persistent_72h_correct_treatment",
            "Fever persists after 72 hours of correct antibiotic treatment",
            "persistente después de 72 horas de tratamiento antibiótico correcto",
        ),
        (
            "itu_small_abscess_or_local_nephritis_suspected",
            "Small abscess or local nephritis suspected",
            "pequeños abscesos y áreas de nefritis local",
        ),
        (
            "itu_structural_abnormality_suspected",
            "Structural urinary abnormality including stones suspected",
            "sospecha de alteración estructural",
        ),
        (
            "itu_functional_abnormality_suspected",
            "Functional abnormality, inadequate emptying, or obstruction suspected",
            "sospecha una alteración funcional",
        ),
        ("itu_pregnant", "Pregnancy", "mujeres embarazadas"),
        (
            "itu_more_than_one_episode_in_pregnancy",
            "More than one UTI episode during pregnancy",
            "más de un episodio de",
        ),
        (
            "itu_stone_suspected_by_hematuria_or_pain",
            "Stone suspected from hematuria and/or pain",
            "sospecha de litiasis por hematuria y/o dolor",
        ),
    ):
        author.variable(variable_id, label, imaging, quote)
    author.rule(
        "itu-r18-urgent-imaging",
        _and(
            _flag("itu_attributable_symptoms_present"),
            _or(
                _flag("itu_septic_shock"),
                _flag("itu_acute_renal_failure"),
                _flag("itu_local_complication"),
                _flag("itu_fever_persistent_72h_correct_treatment"),
            ),
        ),
        ActionType.REQUEST_TEST,
        "Obtain urgent urinary ultrasound or contrast CT",
        imaging,
        "La realización urgente de ecografía o la tomografía (TC) con contraste está indicada",
    )
    author.rule(
        "itu-r19-contrast-ct",
        _flag("itu_small_abscess_or_local_nephritis_suspected"),
        ActionType.REQUEST_TEST,
        "Obtain contrast CT",
        imaging,
        "Se hará TC con contraste cuando se busquen ",
    )
    author.rule(
        "itu-r20-uro-ct",
        _flag("itu_structural_abnormality_suspected"),
        ActionType.REQUEST_TEST,
        "Obtain CT urography",
        imaging,
        "en los casos de sospecha de alteración estructural",
    )
    author.rule(
        "itu-r21-functional-ultrasound",
        _flag("itu_functional_abnormality_suspected"),
        ActionType.REQUEST_TEST,
        "Obtain urinary-tract ultrasound with post-void residual measurement",
        imaging,
        "se sospecha una alteración funcional",
    )
    author.rule(
        "itu-r22-pregnancy-ultrasound",
        _and(
            _flag("itu_pregnant"),
            _or(
                _flag("itu_pyelonephritis"),
                _flag("itu_more_than_one_episode_in_pregnancy"),
                _flag("itu_stone_suspected_by_hematuria_or_pain"),
            ),
        ),
        ActionType.REQUEST_TEST,
        "Obtain renal ultrasound",
        imaging,
        "En las mujeres embarazadas se hará ecografía renal",
    )

    # Treatment eligibility and disposition.
    asb = tuple(_span(3, item) for item in range(35, 40))
    author.variable(
        "itu_invasive_urinary_procedure_disruption_risk",
        "Invasive urinary procedure with bleeding or uroepithelial-disruption risk",
        asb,
        "Procedimiento invasivo de vías urinarias con riesgo de sangrado o disrupción del uroepitelio",
    )
    author.rule(
        "itu-r23-asb-treatment-eligibility",
        _and(
            _flag("itu_significant_bacteriuria"),
            _flag("itu_attributable_symptoms_absent"),
            _or(_flag("itu_pregnant"), _flag("itu_invasive_urinary_procedure_disruption_risk")),
        ),
        ActionType.DECISION,
        "Treat asymptomatic bacteriuria",
        asb,
        "Indicaciones de tratamiento de bacteriuria asintomática",
    )

    hospitalization = tuple(_span(3, item) for item in range(40, 59))
    hospital_vars = (
        ("itu_oral_intolerance", "Oral intolerance", "Intolerancia a la vía oral"),
        ("itu_upper_uti", "Upper UTI", "ITU alta"),
        (
            "itu_decompensated_underlying_disease",
            "Underlying disease decompensated because of UTI",
            "Descompensación de la enfermedad de base secundaria a la ITU",
        ),
        (
            "itu_resistant_no_outpatient_option",
            "Resistant organism with no outpatient antibiotic option",
            "germen resistente sin opción de tratamiento antibiótico",
        ),
        (
            "itu_renal_deterioration",
            "Renal function deterioration associated with UTI",
            "Deterioro de la función renal asociado a la ITU",
        ),
        (
            "itu_renal_or_pararenal_abscess",
            "Renal or pararenal abscess",
            "Absceso renal/pararrenal",
        ),
        (
            "itu_inadequate_social_support",
            "Inadequate social support for outpatient therapy",
            "Inadecuado soporte social",
        ),
    )
    for variable_id, label, quote in hospital_vars:
        author.variable(variable_id, label, hospitalization, quote)
    author.rule(
        "itu-r24-hospitalization",
        _or(_flag("itu_septic_shock"), *(_flag(item[0]) for item in hospital_vars)),
        ActionType.ADMIT,
        "Admit to hospital",
        hospitalization,
        "Indicaciones de hospitalización en pacientes con ITU",
        flags=("Upper-UTI indication conflicts with outpatient upper-UTI treatment row",),
    )
    author.variable(
        "itu_pediatric_acute_pyelonephritis",
        "Acute pyelonephritis in a pediatric patient",
        hospitalization,
        "Pielonefritis aguda en pacientes pediátricos",
    )
    author.rule(
        "itu-r25-pediatric-hospitalization-source",
        _flag("itu_pediatric_acute_pyelonephritis"),
        ActionType.ADMIT,
        "Hospitalize",
        hospitalization,
        "Pielonefritis aguda en pacientes pediátricos",
        state=CandidateState.BLOCKED,
        flags=("Outside declared adult scope",),
    )

    transition = tuple(_span(3, item) for item in range(59, 64)) + tuple(
        _span(4, item) for item in range(3, 16)
    )
    for variable_id, label, quote, value_type, unit in (
        (
            "itu_afebrile_duration",
            "Afebrile duration",
            "48 horas afebril",
            VariableType.DURATION,
            "hours",
        ),
        (
            "itu_systolic_bp",
            "Systolic blood pressure",
            "TAS > 90 mmHg",
            VariableType.NUMERIC,
            "mmHg",
        ),
        ("itu_heart_rate", "Heart rate", "FC < 100 lpm", VariableType.NUMERIC, "beats/min"),
        (
            "itu_respiratory_rate",
            "Respiratory rate",
            "FR < 24 rpm",
            VariableType.NUMERIC,
            "breaths/min",
        ),
        ("itu_oxygen_saturation", "Oxygen saturation", "Sat O2 > 90%", VariableType.NUMERIC, "%"),
        ("itu_pao2", "PaO2", "PaO2 > 60", VariableType.NUMERIC, "mmHg"),
        (
            "itu_oral_tolerance",
            "Oral tolerance",
            "Tolerancia a la vía oral",
            VariableType.BOOLEAN,
            None,
        ),
        (
            "itu_comorbidities_compensated",
            "Comorbidities compensated",
            "Comorbilidades compensadas",
            VariableType.BOOLEAN,
            None,
        ),
        (
            "itu_outpatient_treatment_assured",
            "Outpatient treatment assured",
            "Se ha asegurado el tratamiento ambulatorio",
            VariableType.BOOLEAN,
            None,
        ),
        (
            "itu_social_conditions_allow",
            "Social conditions allow outpatient transition/discharge",
            "Lo permiten las condiciones sociales",
            VariableType.BOOLEAN,
            None,
        ),
    ):
        author.variable(variable_id, label, transition, quote, value_type, unit)
    transition_condition = _and(
        _cmp("itu_afebrile_duration", ComparisonOperator.GE, 48),
        _cmp("itu_systolic_bp", ComparisonOperator.GT, 90),
        _cmp("itu_heart_rate", ComparisonOperator.LT, 100),
        _cmp("itu_respiratory_rate", ComparisonOperator.LT, 24),
        _or(
            _cmp("itu_oxygen_saturation", ComparisonOperator.GT, 90),
            _cmp("itu_pao2", ComparisonOperator.GT, 60),
        ),
        _flag("itu_oral_tolerance"),
        _flag("itu_comorbidities_compensated"),
        _flag("itu_outpatient_treatment_assured"),
        _flag("itu_social_conditions_allow"),
    )
    author.rule(
        "itu-r26-oral-step-or-discharge",
        transition_condition,
        ActionType.DECISION,
        "Eligible for oral therapy transition and/or discharge",
        transition,
        "Indicaciones para paso a terapia oral y/o egreso",
        flags=(
            "Source does not distinguish oral switch from discharge",
            "List interpreted as conjunctive eligibility state",
        ),
    )

    # General treatment table. Each row keeps alternatives, dose, route, interval, duration, and footnotes together.
    general_table = tuple(_span(4, item) for item in range(16, 49))
    author.variable(
        "itu_lower_treatment_context",
        "Lower UTI, complicated or uncomplicated",
        general_table,
        "ITU baja (complicada o no\ncomplicada)",
    )
    author.rule(
        "itu-r27-lower-treatment",
        _flag("itu_lower_treatment_context"),
        ActionType.PRESCRIBE,
        "Choose one: nitrofurantoin 100 mg PO every 6 hours for 5 days; cephalexin 500 mg PO every 6 hours for 5 days; or fosfomycin 3 g PO once (prefer fosfomycin for recurrent UTI or antimicrobial exposure in the last 90 days)",
        (_span(4, 29),),
        "ITU baja (complicada o no\ncomplicada)",
        action_spans=(_span(4, 30), _span(4, 31), _span(4, 32), _span(4, 17), _span(4, 18)),
        action_quote="Nitrofurantoína o\nCefalexina o\nFosfomicina*",
    )
    author.rule(
        "itu-r28-asb-treatment",
        _and(
            _flag("itu_significant_bacteriuria"),
            _flag("itu_attributable_symptoms_absent"),
            _or(_flag("itu_pregnant"), _flag("itu_invasive_urinary_procedure_disruption_risk")),
        ),
        ActionType.PRESCRIBE,
        "Choose one: nitrofurantoin 100 mg PO every 6 hours for 5 days; cephalexin 500 mg PO every 6 hours for 5 days; or fosfomycin 3 g PO once, only in the source-listed treatment-eligible contexts",
        (_span(4, 33), _span(4, 19), _span(4, 20)),
        "Bacteriuria asintomática**",
        action_spans=(_span(4, 34), _span(4, 35), _span(4, 36)),
        action_quote="Nitrofurantoína o\nCefalexina o\nFosfomicina*",
    )
    author.variable(
        "itu_upper_outpatient_context",
        "Upper UTI managed as outpatient",
        general_table,
        "ITU alta ambulatoria",
    )
    author.rule(
        "itu-r29-upper-outpatient-treatment",
        _flag("itu_upper_outpatient_context"),
        ActionType.PRESCRIBE,
        "Cephalexin 500 mg PO every 6 hours for 5-7 days; reassess with urine culture at 48 hours for adjustment",
        (_span(4, 37),),
        "ITU alta ambulatoria",
        action_spans=(_span(4, 38), _span(4, 39), _span(4, 40)),
        action_quote="500 mg VO cada 6 horas",
        flags=("Conflicts with upper UTI listed as hospitalization indication",),
    )
    author.variable(
        "itu_upper_inpatient_no_resistant_risk",
        "Hospitalized upper UTI without resistant Gram-negative risk factors",
        general_table,
        "ITU alta hospitalaria sin FR\npara BGN resistentes",
    )
    author.rule(
        "itu-r30-upper-inpatient-no-resistant-risk",
        _flag("itu_upper_inpatient_no_resistant_risk"),
        ActionType.PRESCRIBE,
        "Choose cefazolin 1 g IV every 8 hours or amikacin 15 mg/kg IV daily for 7 days",
        (_span(4, 41),),
        "ITU alta hospitalaria sin FR\npara BGN resistentes",
        action_spans=(_span(4, 42), _span(4, 43), _span(4, 44)),
        action_quote="Cefazolina o\nAmikacina",
    )
    author.variable(
        "itu_resistant_gn_risk",
        "Resistant Gram-negative risk: hospitalization >48 hours in last 3 months, antibiotics in last 90 days, or ESBL colonization",
        general_table,
        "FR BGN resistentes: hospitalización > 48 horas en los últimos 3 meses",
    )
    author.rule(
        "itu-r31-upper-inpatient-resistant-no-shock",
        _and(
            _flag("itu_upper_uti"),
            _flag("itu_hospitalized"),
            _flag("itu_resistant_gn_risk"),
            _flag("itu_septic_shock", False),
        ),
        ActionType.PRESCRIBE,
        "Choose piperacillin/tazobactam 4.5 g IV every 8 hours or amikacin 15 mg/kg IV daily for 7 days; amikacin is avoided in shock",
        (_span(4, 45), _span(4, 21), _span(4, 22)),
        "ITU alta hospitalaria con FR\npara BGN resistentes***",
        action_spans=(_span(4, 46), _span(4, 47), _span(4, 48)),
        action_quote="Piperacilina tazobactam o\nAmikacina2 o\nMeropenem3",
    )
    author.rule(
        "itu-r32-upper-inpatient-resistant-shock",
        _and(
            _flag("itu_upper_uti"),
            _flag("itu_hospitalized"),
            _flag("itu_resistant_gn_risk"),
            _flag("itu_septic_shock"),
        ),
        ActionType.PRESCRIBE,
        "Administer meropenem 1 g IV every 8 hours empirically for 7 days",
        (_span(4, 45), _span(4, 48)),
        "ITU alta hospitalaria con FR\npara BGN resistentes***",
        action_spans=(_span(4, 46), _span(4, 47), _span(4, 48)),
        action_quote="3 Administrar empíricamente\nsi hay choque",
    )

    # Pregnancy table is one cross-page clinical context.
    pregnancy_table = tuple(_span(4, item) for item in range(49, 75)) + tuple(
        _span(5, item) for item in range(11, 34)
    )
    author.variable(
        "itu_pregnant_asb",
        "Pregnant patient with asymptomatic bacteriuria",
        pregnancy_table,
        "Bacteriuria\nasintomática",
    )
    author.rule(
        "itu-r33-pregnancy-asb-treatment",
        _flag("itu_pregnant_asb"),
        ActionType.PRESCRIBE,
        "Choose nitrofurantoin 100 mg every 6 hours for 5 days, cephalexin 500 mg every 6 hours for 5 days, or fosfomycin 3 g once; table states no control culture and no preventive therapy",
        (_span(4, 61),),
        "Bacteriuria\nasintomática",
        action_spans=tuple(_span(4, item) for item in range(62, 67)),
        action_quote="Nitrofurantoína\nCefalexina\nFosfomicina3",
    )
    author.variable(
        "itu_pregnant_lower", "Pregnant patient with lower UTI", pregnancy_table, "ITU baja"
    )
    author.rule(
        "itu-r34-pregnancy-lower-treatment",
        _flag("itu_pregnant_lower"),
        ActionType.PRESCRIBE,
        "Choose nitrofurantoin 100 mg every 6 hours for 5 days, cephalexin 500 mg every 6 hours for 5 days, or fosfomycin 3 g once; table states no control culture",
        (_span(4, 67),),
        "ITU baja",
        action_spans=(_span(4, 68), _span(4, 69), _span(4, 70), _span(4, 71)),
        action_quote="Nitrofurantoína\no\nCefalexina o\nFosfomicina 3",
    )
    author.variable(
        "itu_recurrent_infection_in_pregnancy",
        "Recurrent UTI during pregnancy",
        pregnancy_table,
        "Sólo si hay\nrecurrencia",
    )
    author.rule(
        "itu-r35-pregnancy-lower-prevention",
        _and(_flag("itu_pregnant_lower"), _flag("itu_recurrent_infection_in_pregnancy")),
        ActionType.PRESCRIBE,
        "Preventive therapy options listed: nitrofurantoin 100 mg daily, cephalexin 500 mg daily, TMP-SMX 480 mg daily, or fosfomycin 3 g weekly; gestational restrictions require review",
        (_span(4, 72),),
        "Sólo si hay\nrecurrencia\nde la\ninfección",
        action_spans=(_span(4, 73), _span(4, 74), _span(5, 23), _span(5, 24), _span(5, 25)),
        action_quote="Nitrofurantoína\n100 mg cada día",
        state=CandidateState.BLOCKED,
        flags=("Cross-page preventive-option and gestational-note alignment requires review",),
    )
    author.variable(
        "itu_pregnant_upper", "Pregnant patient with upper UTI", pregnancy_table, "ITU alta"
    )
    author.rule(
        "itu-r36-pregnancy-upper-treatment",
        _flag("itu_pregnant_upper"),
        ActionType.PRESCRIBE,
        "For 7 days choose cefazolin 1 g IV every 8 hours without resistant Gram-negative risk; piperacillin/tazobactam 4.5 g IV every 8 hours with risk and no shock; or meropenem 1 g IV every 8 hours with risk and shock",
        (_span(5, 26), _span(5, 8), _span(5, 9), _span(5, 10)),
        "ITU alta",
        action_spans=(_span(5, 27), _span(5, 28), _span(5, 29)),
        action_quote="Cefazolina* o\nPiperacilina\ntazobactam** o\nMeropenem***",
    )
    author.rule(
        "itu-r37-pregnancy-upper-prevention",
        _flag("itu_pregnant_upper"),
        ActionType.PRESCRIBE,
        "Preventive therapy is indicated; select nitrofurantoin, cephalexin, TMP-SMX, or weekly fosfomycin from culture/susceptibility, applying the stated gestational restrictions and possible week-34 change",
        (_span(5, 31),),
        "Sí",
        action_spans=(_span(5, 32), _span(5, 33), _span(5, 3), _span(5, 6), _span(5, 7)),
        action_quote="Nitrofurantoína\n100 mg cada día",
        state=CandidateState.BLOCKED,
        flags=("Gestational restriction alignment requires clinical review",),
    )
    author.variable(
        "itu_culture_and_antibiogram_available",
        "Urine culture and antibiogram results available",
        (_span(5, 2),),
        "resultados de urocultivo y antibiograma",
    )
    author.rule(
        "itu-r38-adjust-to-culture",
        _flag("itu_culture_and_antibiogram_available"),
        ActionType.PRESCRIBE,
        "Adjust empirical therapy according to urine culture and antibiogram",
        (_span(5, 2),),
        "Siempre debe ajustarse según resultados de urocultivo y antibiograma",
    )

    # Sequential and contextual relationships authored from clinical meaning.
    author.relation(
        "itu-rel-01",
        "itu-r01-asymptomatic-bacteriuria-classification",
        "itu-r23-asb-treatment-eligibility",
        RelationType.BRANCH,
        asb,
        "Indicaciones de tratamiento de bacteriuria asintomática",
        "pregnancy or qualifying invasive urinary procedure",
    )
    author.relation(
        "itu-rel-02",
        "itu-r23-asb-treatment-eligibility",
        "itu-r28-asb-treatment",
        RelationType.FLOW,
        (_span(4, 19), _span(4, 20)),
        "Recordar su tratamiento sólo en gestantes o pacientes quienes serán sometidos a procedimientos ",
    )
    author.relation(
        "itu-rel-03",
        "itu-r02-symptomatic-uti-classification",
        "itu-r04-lower-uti-classification",
        RelationType.BRANCH,
        definitions,
        "Infección del tracto urinario bajo",
        "lower features",
    )
    author.relation(
        "itu-rel-04",
        "itu-r02-symptomatic-uti-classification",
        "itu-r05-upper-uti-classification",
        RelationType.BRANCH,
        definitions,
        "Infección del tracto urinario alto",
        "upper features",
    )
    author.relation(
        "itu-rel-05",
        "itu-r02-symptomatic-uti-classification",
        "itu-r07-urinalysis",
        RelationType.BRANCH,
        urinalysis,
        "urgencias con sospecha de ITU",
        "emergency diagnostic workup",
    )
    author.relation(
        "itu-rel-06",
        "itu-r02-symptomatic-uti-classification",
        "itu-r09-urine-gram",
        RelationType.BRANCH,
        gram,
        "todos los pacientes en el servicio de urgencias",
        "emergency diagnostic workup",
    )
    author.relation(
        "itu-rel-07",
        "itu-r02-symptomatic-uti-classification",
        "itu-r10-urine-culture",
        RelationType.BRANCH_CONTEXT,
        culture,
        "Debe solicitarse en todos los casos",
        "culture unless its distinct exception applies",
    )
    author.relation(
        "itu-rel-08",
        "itu-r10-urine-culture",
        "itu-r14-sample-before-antibiotic",
        RelationType.FLOW,
        culture,
        "debe tomarse antes de la primera dosis de antibiótico",
        temporal="before first antibiotic dose",
    )
    author.relation(
        "itu-rel-09",
        "itu-r10-urine-culture",
        "itu-r15-permanent-catheter-sampling",
        RelationType.BRANCH,
        culture,
        "usuarios de sonda vesical permanente",
        "permanent catheter user",
    )
    author.relation(
        "itu-rel-10",
        "itu-r10-urine-culture",
        "itu-r11-culture-positive-spontaneous",
        RelationType.BRANCH,
        culture,
        "micción ",
        "appropriately obtained spontaneous sample",
    )
    author.relation(
        "itu-rel-11",
        "itu-r10-urine-culture",
        "itu-r12-culture-positive-symptomatic",
        RelationType.BRANCH,
        culture,
        "paciente con síntomas no explicados",
        "symptomatic context",
    )
    author.relation(
        "itu-rel-12",
        "itu-r15-permanent-catheter-sampling",
        "itu-r13-culture-positive-new-catheter",
        RelationType.FLOW,
        culture,
        "sonda vesical recién ",
    )
    author.relation(
        "itu-rel-13",
        "itu-r05-upper-uti-classification",
        "itu-r17-blood-cultures",
        RelationType.BRANCH,
        blood,
        "pielonefritis aguda que cursan con fiebre",
        "fever, hypothermia, or septic shock",
    )
    author.relation(
        "itu-rel-14",
        "itu-r05-upper-uti-classification",
        "itu-r18-urgent-imaging",
        RelationType.BRANCH,
        imaging,
        "persistente después de 72 horas de tratamiento antibiótico correcto",
        "urgent-imaging context",
    )
    author.relation(
        "itu-rel-15",
        "itu-r18-urgent-imaging",
        "itu-r19-contrast-ct",
        RelationType.BRANCH,
        imaging,
        "pequeños abscesos y áreas de nefritis local",
        "small abscess/local nephritis suspected",
    )
    author.relation(
        "itu-rel-16",
        "itu-r18-urgent-imaging",
        "itu-r20-uro-ct",
        RelationType.BRANCH,
        imaging,
        "sospecha de alteración estructural",
        "structural abnormality suspected",
    )
    author.relation(
        "itu-rel-17",
        "itu-r18-urgent-imaging",
        "itu-r21-functional-ultrasound",
        RelationType.BRANCH,
        imaging,
        "sospecha una alteración funcional",
        "functional abnormality suspected",
    )
    author.relation(
        "itu-rel-18",
        "itu-r05-upper-uti-classification",
        "itu-r24-hospitalization",
        RelationType.BRANCH,
        hospitalization,
        "ITU alta  ",
        "source-listed hospitalization indication",
    )
    author.relation(
        "itu-rel-19",
        "itu-r24-hospitalization",
        "itu-r16-hospital-blood-tests",
        RelationType.FLOW,
        blood,
        "paciente con ITU que sea hospitalizado",
    )
    author.relation(
        "itu-rel-20",
        "itu-r24-hospitalization",
        "itu-r30-upper-inpatient-no-resistant-risk",
        RelationType.BRANCH,
        (_span(4, 41),),
        "ITU alta hospitalaria sin FR\npara BGN resistentes",
        "upper UTI without resistant Gram-negative risk",
    )
    author.relation(
        "itu-rel-21",
        "itu-r24-hospitalization",
        "itu-r31-upper-inpatient-resistant-no-shock",
        RelationType.BRANCH,
        (_span(4, 45),),
        "ITU alta hospitalaria con FR\npara BGN resistentes***",
        "resistant Gram-negative risk without shock",
    )
    author.relation(
        "itu-rel-22",
        "itu-r24-hospitalization",
        "itu-r32-upper-inpatient-resistant-shock",
        RelationType.BRANCH,
        (_span(4, 48),),
        "Administrar empíricamente\nsi hay choque",
        "resistant Gram-negative risk with shock",
    )
    author.relation(
        "itu-rel-23",
        "itu-r05-upper-uti-classification",
        "itu-r29-upper-outpatient-treatment",
        RelationType.BRANCH,
        (_span(4, 37),),
        "ITU alta ambulatoria",
        "source also names outpatient upper UTI; conflict unresolved",
    )
    author.relation(
        "itu-rel-24",
        "itu-r04-lower-uti-classification",
        "itu-r27-lower-treatment",
        RelationType.BRANCH,
        (_span(4, 29),),
        "ITU baja (complicada o no\ncomplicada)",
        "lower UTI",
    )
    author.relation(
        "itu-rel-25",
        "itu-r22-pregnancy-ultrasound",
        "itu-r36-pregnancy-upper-treatment",
        RelationType.BRANCH_CONTEXT,
        pregnancy_table,
        "ITU alta",
        "pregnant upper-UTI context",
    )
    author.relation(
        "itu-rel-26",
        "itu-r01-asymptomatic-bacteriuria-classification",
        "itu-r33-pregnancy-asb-treatment",
        RelationType.BRANCH,
        (_span(4, 61),),
        "Bacteriuria\nasintomática",
        "pregnancy",
    )
    author.relation(
        "itu-rel-27",
        "itu-r04-lower-uti-classification",
        "itu-r34-pregnancy-lower-treatment",
        RelationType.BRANCH,
        (_span(4, 67),),
        "ITU baja",
        "pregnancy",
    )
    author.relation(
        "itu-rel-28",
        "itu-r34-pregnancy-lower-treatment",
        "itu-r35-pregnancy-lower-prevention",
        RelationType.BRANCH,
        (_span(4, 72),),
        "Sólo si hay\nrecurrencia",
        "recurrent infection",
    )
    author.relation(
        "itu-rel-29",
        "itu-r36-pregnancy-upper-treatment",
        "itu-r37-pregnancy-upper-prevention",
        RelationType.FLOW,
        (_span(5, 31),),
        "Sí",
    )
    for ordinal, rule_id in enumerate(
        (
            "itu-r27-lower-treatment",
            "itu-r28-asb-treatment",
            "itu-r29-upper-outpatient-treatment",
            "itu-r30-upper-inpatient-no-resistant-risk",
            "itu-r31-upper-inpatient-resistant-no-shock",
            "itu-r32-upper-inpatient-resistant-shock",
            "itu-r33-pregnancy-asb-treatment",
            "itu-r34-pregnancy-lower-treatment",
            "itu-r36-pregnancy-upper-treatment",
        ),
        start=30,
    ):
        author.relation(
            f"itu-rel-{ordinal:02d}",
            rule_id,
            "itu-r38-adjust-to-culture",
            RelationType.FLOW,
            (_span(5, 2),),
            "Siempre debe ajustarse según resultados de urocultivo y antibiograma",
            "culture/antibiogram available",
        )
    author.relation(
        "itu-rel-39",
        "itu-r30-upper-inpatient-no-resistant-risk",
        "itu-r26-oral-step-or-discharge",
        RelationType.FLOW,
        transition,
        "paso a terapia oral y/o egreso",
        "all listed criteria met",
    )
    author.relation(
        "itu-rel-40",
        "itu-r31-upper-inpatient-resistant-no-shock",
        "itu-r26-oral-step-or-discharge",
        RelationType.FLOW,
        transition,
        "paso a terapia oral y/o egreso",
        "all listed criteria met",
    )
    author.relation(
        "itu-rel-41",
        "itu-r32-upper-inpatient-resistant-shock",
        "itu-r26-oral-step-or-discharge",
        RelationType.FLOW,
        transition,
        "paso a terapia oral y/o egreso",
        "all listed criteria met",
    )
    author.relation(
        "itu-rel-42",
        "itu-r05-upper-uti-classification",
        "itu-r22-pregnancy-ultrasound",
        RelationType.BRANCH,
        imaging,
        "mujeres embarazadas se hará ecografía renal",
        "pregnancy",
    )
    author.relation(
        "itu-rel-43",
        "itu-r07-urinalysis",
        "itu-r08-normal-dipstick",
        RelationType.BRANCH,
        urinalysis,
        "resultado normal en pacientes con baja sospecha clínica descarta ",
        "normal dipstick and low suspicion",
    )

    author.issues.extend(
        (
            Issue(
                "itu-issue-complicated-definitions",
                IssueCategory.SOURCE_CONFLICT,
                IssueSeverity.BLOCKING,
                "The protocol contains two non-equivalent complicated-UTI definitions: structural/functional abnormality and infection beyond the bladder with listed syndromes/contexts. They remain separate candidates.",
                (
                    "itu-r03-complicated-structural-definition",
                    "itu-r06-complicated-beyond-bladder-definition",
                ),
            ),
            Issue(
                "itu-issue-upper-hospital-outpatient",
                IssueCategory.SOURCE_CONFLICT,
                IssueSeverity.BLOCKING,
                "Upper UTI is an explicit hospitalization indication, while the treatment table explicitly contains outpatient upper UTI. Both branches are retained without universalizing either.",
                ("itu-r24-hospitalization", "itu-r29-upper-outpatient-treatment"),
            ),
            Issue(
                "itu-issue-pediatric-adult-scope",
                IssueCategory.OUT_OF_SCOPE,
                IssueSeverity.BLOCKING,
                "The adult protocol retains pediatric acute-pyelonephritis hospitalization language. It is preserved as a blocked source candidate, not applied to adults.",
                ("itu-r25-pediatric-hospitalization-source",),
            ),
            Issue(
                "itu-issue-oral-discharge",
                IssueCategory.AMBIGUITY,
                IssueSeverity.BLOCKING,
                "The source labels one criteria set 'oral therapy transition and/or discharge'; it does not establish that oral switch and discharge are equivalent decisions.",
                ("itu-r26-oral-step-or-discharge",),
            ),
            Issue(
                "itu-issue-pregnancy-cross-page",
                IssueCategory.TABLE_ALIGNMENT,
                IssueSeverity.BLOCKING,
                "The pregnancy table continues from page 4 to page 5. The continuation is treated as one context, but preventive-option and gestational-note alignment requires clinical verification.",
                (
                    "itu-r35-pregnancy-lower-prevention",
                    "itu-r37-pregnancy-upper-prevention",
                    _span(5, 11),
                ),
            ),
            Issue(
                "itu-issue-hospital-list-operator",
                IssueCategory.AMBIGUITY,
                IssueSeverity.NON_BLOCKING,
                "Hospitalization bullets were interpreted as alternative indications; the source does not publish a formal global operator.",
                ("itu-r24-hospitalization",),
            ),
            Issue(
                "itu-issue-transition-list-operator",
                IssueCategory.AMBIGUITY,
                IssueSeverity.NON_BLOCKING,
                "Oral-step/discharge bullets were interpreted as conjunctive eligibility, with oxygen saturation OR PaO2 preserved; the source does not publish a formal global operator.",
                ("itu-r26-oral-step-or-discharge",),
            ),
        )
    )

    document_map = extract_document_map(PDF, extracted_at="2026-10-01T00:00:00+00:00")
    used_span_ids = {
        ref
        for item in (*author.variables.values(), *author.rules, *author.relations)
        for binding in getattr(item, "evidence_bindings", ())
        for ref in binding.source_span_refs
    }
    used_span_ids.update(ref for item in author.observations for ref in item.span_refs)
    used_span_ids.update(
        related
        for issue in author.issues
        for related in issue.related_ids
        if related.startswith(f"{DOCUMENT_ID}-")
    )
    graph = CandidateGraph(
        graph_id="candidate-graph-ct-pl-197-v06-phase4",
        generation_run_id="phase4-opencode-ct-pl-197-v06",
        protocol_version_id=PROTOCOL_VERSION_ID,
        document_id=DOCUMENT_ID,
        extraction_run_id=document_map.run.run_id,
        observations=tuple(author.observations),
        variables=tuple(author.variables.values()),
        rules=tuple(author.rules),
        relations=tuple(author.relations),
        issues=tuple(author.issues),
        source_spans=tuple(document_map.spans[item] for item in sorted(used_span_ids)),
        attempts=(),
    )
    return replace(graph, findings=validate_candidate_graph(graph))


if __name__ == "__main__":
    if OUT.exists():
        OUT.unlink()
    graph = build_graph()
    write_candidate_graph(graph, OUT)
    print(
        f"wrote {OUT}: {len(graph.rules)} rules, {len(graph.relations)} relations, {len(graph.issues)} issues"
    )
