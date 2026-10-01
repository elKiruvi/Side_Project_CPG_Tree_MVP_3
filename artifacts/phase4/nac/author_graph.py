"""Author the CT-PL-193 v9 Candidate Graph from the reviewed source PDF.

This is protocol-specific candidate knowledge, not generic extraction logic. It is
kept beside the generated review artifact so the semantic choices are inspectable
and reproducible. Nothing in this module is clinically approved.
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
from cpg_tree.extraction.spans import SourceSpan, SpanQualityFlag, SpanRepresentation
from cpg_tree.knowledge.conditions import Condition, LogicalExpression
from cpg_tree.knowledge.enums import (
    ActionType,
    ComparisonOperator,
    ConditionKind,
    LogicalOperator,
    VariableType,
)

ROOT = Path(__file__).resolve().parents[3]
PDF = next((ROOT / "data/01_raw").glob("CT-PL-193*.pdf"))
OUT = Path(__file__).with_name("candidate_graph.json")
PROTOCOL_VERSION_ID = "CT-PL-193-v9"
DOCUMENT_ID = "doc-3a1654757801b7b6"
GENERATION_RUN_ID = "phase4-opencode-ct-pl-193-v9"
VISUAL_TREATMENT_SPAN_ID = f"{DOCUMENT_ID}-p005-manual-treatment-table"


def _span(page: int, element: int) -> str:
    return f"{DOCUMENT_ID}-p{page:03d}-e{element:03d}"


def _binding(
    path: str,
    spans: tuple[str, ...],
    quote: str | None = None,
    *,
    evidence_class: EvidenceClass = EvidenceClass.NORMALIZED,
    transformation: str | None = "Structured from source wording; pending clinical review.",
) -> EvidenceBinding:
    return EvidenceBinding(
        claim_path=path,
        evidence_class=evidence_class,
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


def _at_least(threshold: int, *operands: Condition) -> LogicalExpression:
    return LogicalExpression(
        operator=LogicalOperator.AT_LEAST_N,
        operands=operands,
        threshold=threshold,
    )


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
        quote: str | None,
        *,
        value_type: VariableType = VariableType.BOOLEAN,
        unit: str | None = None,
    ) -> None:
        if variable_id in self.variables:
            return
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
        spans: tuple[str, ...],
        quote: str | None,
        *,
        action_fields: dict[str, object] | None = None,
        condition_bindings: tuple[EvidenceBinding, ...] = (),
        state: CandidateState = CandidateState.PROPOSED,
        flags: tuple[str, ...] = (),
        statement_kind: str = "recommendation",
    ) -> None:
        observation_id = f"obs-{rule_id}"
        action_id = f"act-{rule_id}"
        self.observations.append(
            Observation(
                observation_id=observation_id,
                kind=ObservationKind.RECOMMENDATION,
                span_refs=spans,
                exact_quote=quote,
                subject_text=rule_id,
                predicate_text="supports candidate decision",
                object_text=target,
            )
        )
        fields = dict(action_fields or {})
        action = ActionSpec(
            action_id=action_id,
            action_type=action_type,
            target_text=target,
            evidence_bindings=(_binding("/target_text", spans, quote),),
            **fields,
        )
        self.rules.append(
            CandidateRule(
                candidate_id=rule_id,
                revision=1,
                protocol_version_id=PROTOCOL_VERSION_ID,
                condition=condition,
                actions=(action,),
                observation_refs=(observation_id,),
                modality="protocol recommendation",
                statement_kind=statement_kind,
                evidence_class=EvidenceClass.NORMALIZED,
                evidence_bindings=condition_bindings or (_binding("/condition", spans, quote),),
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
        quote: str | None,
        *,
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


def build_graph() -> CandidateGraph:  # noqa: C901, PLR0915
    """Build the independently authored NAC candidate graph."""
    author = _Author()

    # Imaging and diagnosis.
    imaging = (_span(3, 5), _span(3, 6), _span(3, 7), _span(3, 8), _span(3, 9))
    author.variable(
        "nac_lower_respiratory_features",
        "Lower respiratory signs or symptoms",
        imaging,
        "signos y síntomas respiratorios bajos",
    )
    author.variable(
        "nac_compatible_clinical_picture",
        "Clinical picture compatible with pneumonia",
        imaging,
        "cuadro clínico compatible",
    )
    author.variable(
        "nac_new_radiographic_infiltrate",
        "New pulmonary infiltrate on chest radiograph",
        imaging,
        "infiltrado pulmonar de reciente aparición",
    )
    author.variable(
        "nac_initial_radiograph_negative",
        "Initial chest radiograph has no findings",
        imaging,
        "radiografía inicial no muestre hallazgos",
    )
    author.variable(
        "nac_high_clinical_suspicion",
        "High clinical suspicion of pneumonia",
        imaging,
        "sospecha alta de neumonía",
    )
    author.rule(
        "nac-r01-chest-radiograph",
        _flag("nac_lower_respiratory_features"),
        ActionType.REQUEST_TEST,
        "Obtain chest radiograph",
        imaging,
        "La radiografía de tórax se hará en los pacientes con signos y síntomas respiratorios bajos",
    )
    author.rule(
        "nac-r02-diagnostic-support",
        _and(_flag("nac_compatible_clinical_picture"), _flag("nac_new_radiographic_infiltrate")),
        ActionType.CLASSIFY,
        "Diagnosis of pneumonia supported",
        imaging,
        "El diagnóstico de neumonía se basa en un cuadro clínico compatible asociado a un infiltrado pulmonar de reciente aparición",
    )
    author.rule(
        "nac-r03-repeat-radiograph",
        _and(_flag("nac_initial_radiograph_negative"), _flag("nac_high_clinical_suspicion")),
        ActionType.REQUEST_TEST,
        "Repeat chest radiograph",
        imaging,
        "En el caso que la radiografía inicial no muestre hallazgos pero exista una sospecha alta de neumonía ",
        action_fields={"timing": "48 hours"},
    )

    ct = (_span(3, 10), _span(3, 11), _span(3, 12))
    for variable_id, label, quote in (
        (
            "nac_high_clinical_probability",
            "High clinical probability of pneumonia",
            "alta probabilidad de neumonía por clínica",
        ),
        (
            "nac_radiograph_inconclusive",
            "Chest radiograph is inconclusive",
            "radiografía de tórax no concluyente",
        ),
        (
            "nac_diagnosis_priority",
            "Establishing diagnosis is a priority",
            "prioritario hacer el diagnóstico de neumonía",
        ),
        (
            "nac_complication_suspected",
            "Necrotizing pneumonia, lung abscess, or loculated empyema suspected",
            "se sospeche alguna complicación",
        ),
        ("nac_febrile_neutropenia", "Febrile neutropenia", "neutropenia febril"),
    ):
        author.variable(variable_id, label, ct, quote)
    author.rule(
        "nac-r04-ct-inconclusive",
        _and(
            _flag("nac_high_clinical_probability"),
            _flag("nac_radiograph_inconclusive"),
            _or(_flag("nac_diagnosis_priority"), _flag("nac_complication_suspected")),
        ),
        ActionType.REQUEST_TEST,
        "Obtain chest CT",
        ct,
        "Sólo está indicada en pacientes con alta probabilidad de neumonía por clínica, con radiografía de tórax no concluyente y en quien es ",
    )
    author.rule(
        "nac-r05-ct-neutropenia",
        _and(_flag("nac_febrile_neutropenia"), _flag("nac_lower_respiratory_features")),
        ActionType.REQUEST_TEST,
        "Obtain non-contrast chest CT",
        ct,
        "neutropenia febril se solicitará tomografía de tórax simple en todos los pacientes con sintomas respiratorios bajos. ",
    )

    # Progressive laboratory and microbiology workup.
    labs = tuple(_span(3, item) for item in range(13, 18))
    for variable_id, label, quote in (
        ("nac_suspected_pneumonia", "Suspected pneumonia", "sospecha de "),
        (
            "nac_hospitalization_indicated",
            "Hospitalization is indicated",
            "indicación de hospitalización",
        ),
        ("nac_septic_shock", "Septic shock", "choque séptico"),
        ("nac_severe_sepsis", "Severe sepsis", "sepsis grave"),
        ("nac_multiorgan_failure", "Multiple-organ failure", "falla orgánica múltiple"),
        ("nac_desaturation", "Desaturation", "desaturación"),
        (
            "nac_pleural_effusion_with_thoracentesis",
            "Pleural effusion with indication for thoracentesis",
            "derrame pleural e indicación de toracentesis",
        ),
    ):
        author.variable(variable_id, label, labs, quote)
    author.rule(
        "nac-r06-basic-laboratory",
        _flag("nac_suspected_pneumonia"),
        ActionType.REQUEST_TEST,
        "Obtain complete blood count and blood urea nitrogen to assess hospitalization need",
        labs,
        "Para definir la necesidad de hospitalización, se hará hemoleucograma y nitrógeno ureico en todo paciente con sospecha de ",
    )
    author.rule(
        "nac-r07-hospital-laboratory",
        _flag("nac_hospitalization_indicated"),
        ActionType.REQUEST_TEST,
        "Add C-reactive protein, creatinine, lactate, and sodium",
        labs,
        "En pacientes con indicación de hospitalización se adicionarán: proteína C reactiva, creatinina, lactato y sodio",
    )
    author.rule(
        "nac-r08-severe-laboratory",
        _or(_flag("nac_septic_shock"), _flag("nac_severe_sepsis"), _flag("nac_multiorgan_failure")),
        ActionType.REQUEST_TEST,
        "Add coagulation tests, AST, ALT, bilirubin, and arterial blood gases",
        labs,
        "En pacientes con choque séptico, sepsis grave ",
    )
    author.rule(
        "nac-r09-desaturation-abg",
        _flag("nac_desaturation"),
        ActionType.REQUEST_TEST,
        "Obtain arterial blood gases",
        labs,
        "También se solicitarán gases arteriales en pacientes ",
    )
    author.rule(
        "nac-r10-pleural-serum-tests",
        _flag("nac_pleural_effusion_with_thoracentesis"),
        ActionType.REQUEST_TEST,
        "Obtain serum lactate dehydrogenase and total proteins",
        labs,
        "se solicitarán además deshidrogenasa láctica y proteínas totales en suero",
    )

    blood = tuple(_span(3, item) for item in range(18, 23))
    for variable_id, label, quote, value_type, unit in (
        (
            "nac_hospitalized_for_pneumonia",
            "Hospitalized for pneumonia",
            "pacientes hospitalizados por neumonía",
            VariableType.BOOLEAN,
            None,
        ),
        ("nac_bun", "Blood urea nitrogen", "BUN", VariableType.NUMERIC, "mg/dL"),
        ("nac_crp", "C-reactive protein", "Proteína C Reactiva", VariableType.NUMERIC, "mg/dL"),
        ("nac_leukocytes", "Leukocyte count", "Leucocitosis", VariableType.NUMERIC, "cells/mm3"),
        (
            "nac_diastolic_bp",
            "Diastolic blood pressure",
            "Arterial Diastólica",
            VariableType.NUMERIC,
            "mmHg",
        ),
        ("nac_heart_rate", "Heart rate", "Frecuencia Cardiaca", VariableType.NUMERIC, "beats/min"),
        (
            "nac_respiratory_rate",
            "Respiratory rate",
            "Frecuencia Respiratoria",
            VariableType.NUMERIC,
            "breaths/min",
        ),
        ("nac_pleuritic_pain", "Pleuritic pain", "Dolor Pleurítico", VariableType.BOOLEAN, None),
    ):
        author.variable(variable_id, label, blood, quote, value_type=value_type, unit=unit)
    blood_condition = _and(
        _flag("nac_hospitalized_for_pneumonia"),
        _or(
            _cmp("nac_bun", ComparisonOperator.GT, 30),
            _cmp("nac_crp", ComparisonOperator.GT, 15),
            _cmp("nac_leukocytes", ComparisonOperator.GT, 15000),
            _at_least(
                2,
                _cmp("nac_diastolic_bp", ComparisonOperator.LT, 60),
                _cmp("nac_heart_rate", ComparisonOperator.GT, 120),
                _cmp("nac_respiratory_rate", ComparisonOperator.GT, 30),
                _flag("nac_pleuritic_pain"),
            ),
        ),
    )
    author.rule(
        "nac-r11-blood-cultures",
        blood_condition,
        ActionType.REQUEST_TEST,
        "Obtain two blood-culture bottle samples and one anaerobic-culture bottle sample before the first intravenous antibiotic dose",
        blood,
        "Hemocultivos: Deben tomarse en los pacientes hospitalizados por neumonía que presenten una de las siguientes condiciones, nitrógeno ureico en sangre (BUN) mayor ",
        condition_bindings=(
            _binding("/condition/operands/0", blood, "pacientes hospitalizados por neumonía"),
            _binding("/condition/operands/1/operands/0", blood, "a 30 mg/dL"),
            _binding("/condition/operands/1/operands/1", blood, "PCR) mayor a 15 mg/dL"),
            _binding("/condition/operands/1/operands/2", blood, "Leucocitosis mayor a 15000"),
            _binding(
                "/condition/operands/1/operands/3", blood, "dos de las siguientes condiciones"
            ),
        ),
        flags=("BUN threshold conflicts with visually inspected flowchart",),
    )

    sputum = (
        *(_span(3, item) for item in range(23, 31)),
        _span(4, 4),
        _span(4, 5),
        _span(4, 7),
    )
    author.variable(
        "nac_confirmed_pneumonia",
        "Confirmed pneumonia",
        sputum,
        "diagnóstico confirmado de neumonía",
    )
    author.variable(
        "nac_unable_spontaneous_sputum",
        "Unable to produce spontaneous sputum",
        sputum,
        "no pueden recoger la muestra de ",
    )
    author.variable(
        "nac_no_sars_cov2_suspicion",
        "No suspicion of SARS-CoV-2 pneumonia",
        sputum,
        "sin sospecha de neumonia por SARSCOV2",
    )
    author.variable(
        "nac_no_expectorated_sample",
        "Patient does not expectorate",
        sputum,
        "pacientes que no espectoran",
    )
    author.rule(
        "nac-r12-sputum-culture",
        _and(_flag("nac_confirmed_pneumonia"), _flag("nac_hospitalization_indicated")),
        ActionType.REQUEST_TEST,
        "Obtain sputum for Gram stain and culture",
        sputum,
        "muestras de esputo para tinción y cultivo en todo paciente con diagnóstico de neumonía e indicación de hospitalización",
    )
    author.rule(
        "nac-r13-induced-sputum",
        _flag("nac_unable_spontaneous_sputum"),
        ActionType.REQUEST_TEST,
        "Induce sputum with 3% hypertonic saline nebulization",
        sputum,
        "esputo inducido por nebulización de 15-20 minutos con solución salina hipertónica (3%)",
        action_fields={"duration": "15-20 minutes"},
    )
    author.rule(
        "nac-r14-filmarray",
        _and(_flag("nac_confirmed_pneumonia"), _flag("nac_hospitalization_indicated")),
        ActionType.REQUEST_TEST,
        "Request respiratory FilmArray molecular testing",
        sputum,
        "se debe solicitar en todo paciente adulto ",
    )
    author.rule(
        "nac-r15-deep-filmarray",
        _flag("nac_no_sars_cov2_suspicion"),
        ActionType.REQUEST_TEST,
        "Use pneumonia FilmArray panel (code 502828) as first option with deep respiratory sample",
        sputum,
        "Diagnóstico molecular para panel de neumonía filmarray (cod 502828): como primera opción",
    )
    author.rule(
        "nac-r16-nasopharyngeal-panel",
        _flag("nac_no_expectorated_sample"),
        ActionType.REQUEST_TEST,
        "Use respiratory pathogen panel (code 502162) from nasopharyngeal swab",
        sputum,
        "Diagnóstico molecular para patógenos respiratorios (cod 502162): muestra tomada de hisopado nasofaríngeo en pacientes que no espectoran",
    )

    pleural = (_span(4, 8), _span(4, 9), _span(4, 10))
    author.variable(
        "nac_parapneumonic_effusion_over_1cm",
        "Unilateral presumed parapneumonic effusion over 1 cm without apparent cause",
        pleural,
        "derrame pleural unilateral de más de 1 centímetro de espesor sin ",
    )
    author.rule(
        "nac-r17-pleural-study",
        _flag("nac_parapneumonic_effusion_over_1cm"),
        ActionType.REQUEST_TEST,
        "Perform diagnostic thoracentesis and pleural-fluid cytochemistry, LDH, total protein, Gram stain, and culture",
        pleural,
        "debe ser llevado a toracentesis diagnóstica",
    )

    # Disposition and severity.
    hospital = tuple(_span(4, item) for item in range(12, 22))
    hospital_vars = (
        (
            "nac_decompensated_comorbidity",
            "Decompensated underlying disease",
            "descompensación de enfermedad de base",
        ),
        ("nac_immunosuppressed", "Immunosuppression", "Pacientes inmunosuprimidos"),
        (
            "nac_resistant_organism_suspected",
            "Resistant organism suspected",
            "Sospecha de gérmenes resistentes",
        ),
        ("nac_oral_intolerance", "Oral intolerance", "Intolerancia a la vía oral"),
        (
            "nac_pulmonary_sepsis_or_shock",
            "Sepsis or shock of pulmonary origin",
            "Sepsis o choque de origen pulmonar",
        ),
        (
            "nac_multilobar_or_effusion",
            "Multilobar involvement or pleural effusion on chest radiograph",
            "Compromiso multilobar o derrame pleural",
        ),
        (
            "nac_social_barrier",
            "Social factors impair treatment adherence or follow-up",
            "Factores sociales",
        ),
        (
            "nac_supplemental_oxygen_required",
            "Supplemental oxygen required",
            "Requerimiento de oxigeno suplementario",
        ),
    )
    for variable_id, label, quote in hospital_vars:
        author.variable(variable_id, label, hospital, quote)
    author.variable(
        "nac_curb65",
        "CURB-65 score",
        hospital,
        "CURB-65",
        value_type=VariableType.NUMERIC,
        unit="points",
    )
    hospital_condition = _or(
        *(_flag(item[0]) for item in hospital_vars),
        _cmp("nac_curb65", ComparisonOperator.GE, 2),
    )
    author.rule(
        "nac-r18-hospitalization",
        hospital_condition,
        ActionType.ADMIT,
        "Admit to hospital",
        hospital,
        "Son indicaciones de hospitalización relacionadas con el diagnóstico de neumonía",
        flags=("List interpreted as alternative indications",),
    )

    icu = tuple(_span(4, item) for item in range(22, 35))
    direct_icu = (
        ("nac_respiratory_failure", "Respiratory failure", "Insuficiencia respiratoria"),
        (
            "nac_acute_renal_replacement",
            "Acute renal failure requiring renal replacement therapy",
            "falla renal aguda que requiere terapia de reemplazo renal",
        ),
    )
    for variable_id, label, quote in direct_icu:
        author.variable(variable_id, label, icu, quote)
    author.variable(
        "nac_lactate",
        "Serum lactate",
        icu,
        "lactato sérico",
        value_type=VariableType.NUMERIC,
        unit="mmol/L",
    )
    author.rule(
        "nac-r19-icu-direct",
        _or(
            _flag("nac_respiratory_failure"),
            _flag("nac_septic_shock"),
            _cmp("nac_lactate", ComparisonOperator.GT, 2),
            _flag("nac_acute_renal_replacement"),
            _flag("nac_multiorgan_failure"),
        ),
        ActionType.ADMIT,
        "Admit to ICU or intermediate care unit",
        icu,
        "Insuficiencia respiratoria, choque séptico o lactato sérico mayor de 2, falla renal aguda que requiere terapia de reemplazo renal o falla orgánica ",
    )
    for variable_id, label, quote, value_type, unit in (
        (
            "nac_aggressive_iv_fluids_for_hypotension",
            "Hypotension requiring aggressive intravenous fluids",
            "Hipotensión que requiera LEV agresivos",
            VariableType.BOOLEAN,
            None,
        ),
        (
            "nac_multilobar_infiltrates",
            "Multilobar infiltrates",
            "Infiltrados multilobares",
            VariableType.BOOLEAN,
            None,
        ),
        ("nac_pao2_fio2", "PaO2/FiO2 ratio", "PaO2/FiO2", VariableType.NUMERIC, None),
        ("nac_confusion", "Confusion", "Confusión", VariableType.BOOLEAN, None),
        ("nac_hypothermia", "Hypothermia", "Hipotermia", VariableType.BOOLEAN, None),
        ("nac_platelets", "Platelet count", "Plaquetas", VariableType.NUMERIC, "cells/mm3"),
    ):
        author.variable(variable_id, label, icu, quote, value_type=value_type, unit=unit)
    icu_minor = _at_least(
        3,
        _cmp("nac_bun", ComparisonOperator.GT, 30),
        _cmp("nac_respiratory_rate", ComparisonOperator.GT, 30),
        _flag("nac_aggressive_iv_fluids_for_hypotension"),
        _flag("nac_multilobar_infiltrates"),
        _cmp("nac_pao2_fio2", ComparisonOperator.LT, 250),
        _flag("nac_confusion"),
        _flag("nac_hypothermia"),
        _cmp("nac_platelets", ComparisonOperator.LT, 100000),
        _cmp("nac_leukocytes", ComparisonOperator.LT, 4000),
    )
    author.rule(
        "nac-r20-icu-three-criteria",
        icu_minor,
        ActionType.ADMIT,
        "Admit to ICU or intermediate care unit",
        icu,
        "Paciente que cumpla con 3 o más criterios de",
        flags=("Narrative criteria differ from visual flowchart",),
    )

    # Page 5 treatment content was manually inspected visually; candidates remain blocked.
    treatment_span = (VISUAL_TREATMENT_SPAN_ID,)
    treatment_rows = (
        (
            "nac-r21-treatment-no-risk",
            "nac_no_resistant_risk",
            "NAC without resistant-organism risk factors",
            "Cefuroxime 1500 mg IV every 8 hours OR ampicillin/sulbactam 3 g IV every 6 hours OR moxifloxacin 400 mg IV daily for 5-7 days",
        ),
        (
            "nac-r22-treatment-pseudomonas",
            "nac_pseudomonas_or_resistant_enterobacteria_risk",
            "Risk factors for P. aeruginosa or resistant Enterobacterales",
            "Piperacillin/tazobactam, cefepime, meropenem, or ceftazidime/avibactam according to the table, for 5-7 days",
        ),
        (
            "nac-r23-treatment-mrsa-combined",
            "nac_mrsa_and_other_resistant_risk",
            "Risk factors for MRSA plus P. aeruginosa or resistant Enterobacterales",
            "An antipseudomonal/resistant-Enterobacterales option plus linezolid or vancomycin according to the table, for 5-7 days",
        ),
        (
            "nac-r24-treatment-mrsa-only",
            "nac_mrsa_only_risk",
            "Risk factors for MRSA without P. aeruginosa or resistant Enterobacterales risk",
            "Cefuroxime or ampicillin/sulbactam plus linezolid or vancomycin according to the table, for 5-7 days",
        ),
        (
            "nac-r25-treatment-postviral",
            "nac_postviral_mrsa_context",
            "Postviral NAC with clinical/imaging MRSA suggestion or MRSA colonization",
            "Cefuroxime or ceftriaxone; ceftaroline is listed for selected coinfection context, for 5-7 days",
        ),
    )
    for rule_id, variable_id, label, target in treatment_rows:
        author.variable(variable_id, label, treatment_span, None)
        author.rule(
            rule_id,
            _flag(variable_id),
            ActionType.PRESCRIBE,
            target,
            treatment_span,
            None,
            state=CandidateState.BLOCKED,
            flags=(
                "Manual visual transcription",
                "Risk-factor activation not fully defined",
                "Table footnotes require clinical review",
            ),
        )
    author.variable(
        "nac_molecular_or_culture_result_available",
        "Molecular or culture result available",
        treatment_span,
        None,
    )
    author.rule(
        "nac-r26-adjust-to-results",
        _flag("nac_molecular_or_culture_result_available"),
        ActionType.PRESCRIBE,
        "Adjust antimicrobial treatment according to molecular testing or culture",
        treatment_span,
        None,
        state=CandidateState.BLOCKED,
        flags=("Manual visual transcription",),
    )

    discharge = tuple(_span(5, item) for item in range(2, 8))
    for variable_id, label, quote, value_type, unit in (
        (
            "nac_afebrile_duration",
            "Afebrile duration",
            "48 horas afebr",
            VariableType.DURATION,
            "hours",
        ),
        (
            "nac_systolic_bp",
            "Systolic blood pressure",
            "il, estable en",
            VariableType.NUMERIC,
            "mmHg",
        ),
        (
            "nac_oxygen_saturation",
            "Oxygen saturation",
            "saturación de oxígeno",
            VariableType.NUMERIC,
            "%",
        ),
        ("nac_pao2", "PaO2", "PO2", VariableType.NUMERIC, "mmHg"),
        ("nac_oral_tolerance", "Oral tolerance", "90, PO2 may", VariableType.BOOLEAN, None),
        (
            "nac_comorbidities_compensated",
            "Comorbidities compensated",
            "90, PO2 may",
            VariableType.BOOLEAN,
            None,
        ),
        (
            "nac_outpatient_antibiotic_assured",
            "Outpatient antibiotic administration assured",
            "tratamiento antibiótico ambulatorio",
            VariableType.BOOLEAN,
            None,
        ),
        (
            "nac_social_conditions_allow_discharge",
            "Social conditions allow discharge",
            "sociales lo p",
            VariableType.BOOLEAN,
            None,
        ),
    ):
        author.variable(variable_id, label, discharge, quote, value_type=value_type, unit=unit)
    discharge_condition = _and(
        _cmp("nac_afebrile_duration", ComparisonOperator.GE, 48),
        _cmp("nac_systolic_bp", ComparisonOperator.GT, 90),
        _cmp("nac_heart_rate", ComparisonOperator.LT, 100),
        _cmp("nac_respiratory_rate", ComparisonOperator.LT, 24),
        _cmp("nac_oxygen_saturation", ComparisonOperator.GT, 90),
        _cmp("nac_pao2", ComparisonOperator.GT, 60),
        _flag("nac_oral_tolerance"),
        _flag("nac_comorbidities_compensated"),
        _flag("nac_outpatient_antibiotic_assured"),
        _flag("nac_social_conditions_allow_discharge"),
    )
    author.rule(
        "nac-r27-discharge",
        discharge_condition,
        ActionType.DISCHARGE,
        "Discharge patient",
        discharge,
        "PLAN DE EGRESO. Se dará de alta el paciente cuando lleve 48 horas afebr",
        flags=("Criteria interpreted as a conjunctive eligibility state",),
    )
    follow = (_span(6, 3), _span(6, 4))
    author.variable(
        "nac_at_discharge", "Patient is being discharged", follow, "Al momento del alta"
    )
    author.rule(
        "nac-r28-discharge-education",
        _flag("nac_at_discharge"),
        ActionType.EDUCATE,
        "Explain relapse warning signs: fever, dyspnea, and chest pain",
        follow,
        "Al momento del alta se indicarán al paciente los signos y síntomas que sugieren recaída de la infección, específicamente fiebre, disnea, dolor torácico",
    )
    author.rule(
        "nac-r29-follow-up",
        _flag("nac_at_discharge"),
        ActionType.FOLLOW_UP,
        "Internal medicine review",
        follow,
        "revisión con medicina interna a las 4 semanas del alta. ",
        action_fields={"timing": "4 weeks after discharge"},
    )

    # Sequence and context are authored semantically, never from adjacency alone.
    author.relation(
        "nac-rel-01",
        "nac-r01-chest-radiograph",
        "nac-r02-diagnostic-support",
        RelationType.BRANCH,
        imaging,
        "cuadro clínico compatible asociado a un infiltrado pulmonar",
        label="compatible picture plus new infiltrate",
    )
    author.relation(
        "nac-rel-02",
        "nac-r01-chest-radiograph",
        "nac-r03-repeat-radiograph",
        RelationType.BRANCH,
        imaging,
        "radiografía inicial no muestre hallazgos pero exista una sospecha alta",
        label="negative initial radiograph and high suspicion",
        temporal="repeat at 48 hours",
    )
    author.relation(
        "nac-rel-03",
        "nac-r01-chest-radiograph",
        "nac-r04-ct-inconclusive",
        RelationType.BRANCH,
        ct,
        "radiografía de tórax no concluyente",
        label="inconclusive radiograph with CT indication",
    )
    author.relation(
        "nac-rel-04",
        "nac-r01-chest-radiograph",
        "nac-r06-basic-laboratory",
        RelationType.BRANCH_CONTEXT,
        labs,
        "sospecha de ",
        label="parallel workup for suspected pneumonia",
    )
    author.relation(
        "nac-rel-05",
        "nac-r06-basic-laboratory",
        "nac-r18-hospitalization",
        RelationType.SUPPORTS,
        labs,
        "Para definir la necesidad de hospitalización",
    )
    author.relation(
        "nac-rel-06",
        "nac-r18-hospitalization",
        "nac-r07-hospital-laboratory",
        RelationType.BRANCH,
        labs,
        "En pacientes con indicación de hospitalización",
        label="hospitalization indicated",
    )
    author.relation(
        "nac-rel-07",
        "nac-r18-hospitalization",
        "nac-r12-sputum-culture",
        RelationType.BRANCH,
        sputum,
        "diagnóstico de neumonía e indicación de hospitalización",
        label="hospitalization indicated",
    )
    author.relation(
        "nac-rel-08",
        "nac-r18-hospitalization",
        "nac-r14-filmarray",
        RelationType.BRANCH,
        sputum,
        "diagnóstico confirmado de neumonía e indicación de hospitalización",
        label="confirmed pneumonia and hospitalization indicated",
    )
    author.relation(
        "nac-rel-09",
        "nac-r18-hospitalization",
        "nac-r11-blood-cultures",
        RelationType.BRANCH,
        blood,
        "pacientes hospitalizados por neumonía que presenten",
        label="hospitalized and blood-culture criteria met",
    )
    author.relation(
        "nac-rel-10",
        "nac-r07-hospital-laboratory",
        "nac-r08-severe-laboratory",
        RelationType.BRANCH,
        labs,
        "choque séptico, sepsis grave ",
        label="severe context",
    )
    author.relation(
        "nac-rel-10a",
        "nac-r07-hospital-laboratory",
        "nac-r09-desaturation-abg",
        RelationType.BRANCH,
        labs,
        "gases arteriales en pacientes ",
        label="desaturation",
    )
    author.relation(
        "nac-rel-11",
        "nac-r18-hospitalization",
        "nac-r19-icu-direct",
        RelationType.BRANCH,
        icu,
        "INDICACIONES DE INGRESO A UCI-UCE",
        label="direct ICU/UCE indication",
    )
    author.relation(
        "nac-rel-12",
        "nac-r18-hospitalization",
        "nac-r20-icu-three-criteria",
        RelationType.BRANCH,
        icu,
        "Paciente que cumpla con 3 o más criterios",
        label="three or more listed criteria",
    )
    for ordinal, rule_id in enumerate(
        (
            "nac-r21-treatment-no-risk",
            "nac-r22-treatment-pseudomonas",
            "nac-r23-treatment-mrsa-combined",
            "nac-r24-treatment-mrsa-only",
            "nac-r25-treatment-postviral",
        ),
        start=13,
    ):
        author.relation(
            f"nac-rel-{ordinal:02d}",
            "nac-r18-hospitalization",
            rule_id,
            RelationType.BRANCH_CONTEXT,
            (_span(4, 35), *treatment_span),
            "TRATAMIENTO ANTIBIÓTICO EMPÍRICO: ",
            label="treatment context from visually inspected table",
        )
    author.relation(
        "nac-rel-18",
        "nac-r14-filmarray",
        "nac-r26-adjust-to-results",
        RelationType.FLOW,
        treatment_span,
        None,
        label="molecular result available",
    )
    author.relation(
        "nac-rel-19",
        "nac-r12-sputum-culture",
        "nac-r26-adjust-to-results",
        RelationType.SUPPORTS,
        treatment_span,
        None,
    )
    for ordinal, rule_id in enumerate(
        (
            "nac-r21-treatment-no-risk",
            "nac-r22-treatment-pseudomonas",
            "nac-r23-treatment-mrsa-combined",
            "nac-r24-treatment-mrsa-only",
            "nac-r25-treatment-postviral",
        ),
        start=20,
    ):
        author.relation(
            f"nac-rel-{ordinal:02d}",
            rule_id,
            "nac-r27-discharge",
            RelationType.FLOW,
            discharge,
            "PLAN DE EGRESO. Se dará de alta el paciente cuando",
            label="discharge criteria subsequently met",
        )
    author.relation(
        "nac-rel-25",
        "nac-r27-discharge",
        "nac-r28-discharge-education",
        RelationType.FLOW,
        follow,
        "Al momento del alta se indicarán al paciente",
        temporal="at discharge",
    )
    author.relation(
        "nac-rel-26",
        "nac-r27-discharge",
        "nac-r29-follow-up",
        RelationType.FLOW,
        follow,
        "revisión con medicina interna a las 4 semanas del alta. ",
        temporal="4 weeks after discharge",
    )
    author.relation(
        "nac-rel-27",
        "nac-r03-repeat-radiograph",
        "nac-r02-diagnostic-support",
        RelationType.SUPPORTS,
        imaging,
        "debe repetirse la radiografía de tórax en 48 horas",
    )
    author.relation(
        "nac-rel-28",
        "nac-r17-pleural-study",
        "nac-r10-pleural-serum-tests",
        RelationType.BRANCH,
        labs,
        "adecuada interpretación de los hallazgos en el líquido pleural ",
        label="thoracentesis indicated",
    )
    author.relation(
        "nac-rel-29",
        "nac-r12-sputum-culture",
        "nac-r13-induced-sputum",
        RelationType.BRANCH,
        sputum,
        "no pueden recoger la muestra de ",
        label="cannot produce spontaneous sample",
    )
    author.relation(
        "nac-rel-30",
        "nac-r14-filmarray",
        "nac-r15-deep-filmarray",
        RelationType.BRANCH,
        sputum,
        "como primera opción",
        label="deep sample available and no SARS-CoV-2 suspicion",
    )
    author.relation(
        "nac-rel-31",
        "nac-r14-filmarray",
        "nac-r16-nasopharyngeal-panel",
        RelationType.BRANCH,
        sputum,
        "pacientes que no espectoran",
        label="patient does not expectorate",
    )
    author.relation(
        "nac-rel-32",
        "nac-r02-diagnostic-support",
        "nac-r17-pleural-study",
        RelationType.BRANCH,
        pleural,
        "derrame pleural de presunto origen paraneumónico",
        label="qualifying presumed parapneumonic effusion",
    )

    visual_table = VISUAL_TREATMENT_SPAN_ID
    visual_flow = _span(6, 15)
    author.issues.extend(
        (
            Issue(
                "nac-issue-visual-treatment",
                IssueCategory.EXTRACTION_LIMITATION,
                IssueSeverity.BLOCKING,
                "Page 5 treatment tables are readable by direct visual inspection but lack reliable native-text SourceSpans. Treatment candidates are manual visual transcriptions and remain blocked pending source-region transcription and clinical review.",
                (
                    visual_table,
                    *[
                        item.candidate_id
                        for item in author.rules
                        if item.candidate_id.startswith("nac-r2")
                        and "treatment" in item.candidate_id
                    ],
                ),
            ),
            Issue(
                "nac-issue-flowchart",
                IssueCategory.EXTRACTION_LIMITATION,
                IssueSeverity.BLOCKING,
                "Page 6 flowchart is visual-only in the documentary layer. It was inspected for conflict detection but does not define canonical pathway edges.",
                (visual_flow,),
            ),
            Issue(
                "nac-issue-bun-conflict",
                IssueCategory.SOURCE_CONFLICT,
                IssueSeverity.BLOCKING,
                "Narrative blood-culture and ICU criteria use BUN >30, while the visually inspected flowchart shows BUN >20. Narrative candidates preserve >30; precedence requires clinical adjudication.",
                ("nac-r11-blood-cultures", "nac-r20-icu-three-criteria", visual_flow),
            ),
            Issue(
                "nac-issue-icu-modalities",
                IssueCategory.SOURCE_CONFLICT,
                IssueSeverity.BLOCKING,
                "Narrative ICU/UCE direct and three-of-nine criteria differ from the visual flowchart major/minor structure and thresholds. Narrative candidates are retained without resolving precedence.",
                ("nac-r19-icu-direct", "nac-r20-icu-three-criteria", visual_flow),
            ),
            Issue(
                "nac-issue-risk-definitions",
                IssueCategory.AMBIGUITY,
                IssueSeverity.BLOCKING,
                "The treatment table names MRSA, P. aeruginosa, and resistant-Enterobacterales risk contexts but does not fully operationalize all risk-factor activation criteria.",
                tuple(
                    item.candidate_id for item in author.rules if "treatment" in item.candidate_id
                ),
            ),
            Issue(
                "nac-issue-table-footnotes",
                IssueCategory.TABLE_ALIGNMENT,
                IssueSeverity.BLOCKING,
                "Page 5 merged cells, superscripts, shared comments, and footnotes require line-by-line clinical verification before treatment candidates can advance.",
                (visual_table,),
            ),
            Issue(
                "nac-issue-discharge-and",
                IssueCategory.AMBIGUITY,
                IssueSeverity.NON_BLOCKING,
                "The discharge paragraph reads as a combined eligibility state; the CandidateRule uses AND, but the source does not publish an explicit formal operator.",
                ("nac-r27-discharge",),
            ),
        )
    )

    document_map = extract_document_map(PDF, extracted_at="2026-10-01T00:00:00+00:00")
    used_span_ids = {
        ref
        for item in (
            *author.observations,
            *author.variables.values(),
            *author.rules,
            *author.relations,
        )
        for binding in getattr(item, "evidence_bindings", ())
        for ref in binding.source_span_refs
    }
    used_span_ids.update(ref for obs in author.observations for ref in obs.span_refs)
    used_span_ids.update(
        related
        for issue in author.issues
        for related in issue.related_ids
        if related.startswith(f"{DOCUMENT_ID}-")
    )
    visual_treatment_span = SourceSpan(
        span_id=VISUAL_TREATMENT_SPAN_ID,
        document_id=DOCUMENT_ID,
        extraction_run_id=document_map.run.run_id,
        page=5,
        representation=SpanRepresentation.TABLE,
        extraction_method="manual-visual-inspection-opencode",
        section_path="TRATAMIENTO ANTIBIÓTICO EMPÍRICO",
        normalized_text=(
            "Manual visual transcription summary: five treatment contexts were readable "
            "(no resistant risk; P. aeruginosa/resistant Enterobacterales risk; combined "
            "MRSA plus those risks; MRSA-only risk; postviral/MRSA context), with parallel "
            "antibiotic alternatives, doses, intervals, 5-7 day durations, and footnotes. "
            "Merged-cell and footnote alignment remains unresolved."
        ),
        table_locator="page 5 empirical antibiotic treatment tables",
        quality_flags=(
            SpanQualityFlag.VISUAL_ONLY,
            SpanQualityFlag.TABLE_ALIGNMENT_UNCERTAIN,
        ),
    )
    source_spans = tuple(
        visual_treatment_span if item == VISUAL_TREATMENT_SPAN_ID else document_map.spans[item]
        for item in sorted(used_span_ids)
    )
    graph = CandidateGraph(
        graph_id="candidate-graph-ct-pl-193-v9-phase4",
        generation_run_id=GENERATION_RUN_ID,
        protocol_version_id=PROTOCOL_VERSION_ID,
        document_id=DOCUMENT_ID,
        extraction_run_id=document_map.run.run_id,
        observations=tuple(author.observations),
        variables=tuple(author.variables.values()),
        rules=tuple(author.rules),
        relations=tuple(author.relations),
        issues=tuple(author.issues),
        source_spans=source_spans,
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
