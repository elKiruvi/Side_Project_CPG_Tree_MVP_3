# CT-PL-193 v9 (NAC) — Phase 5 reconciliation report

Generated deterministically by the Phase 5 reconcile module. This is a semantic review record of relation-level decisions; the CandidateGraph remains canonical and no candidate was promoted to approved knowledge.

## Counts

- CandidateRules: 29 (unchanged from Phase 4)
- initial CandidateRelations: 33
- final CandidateRelations: 33
- relations kept: 31
- relations retyped: 2
- relations retargeted: 0
- relations removed: 0
- relations added: 0
- relations blocked: 0
- open Issues: 7
- structural findings: 2 (errors: 0, warnings: 2)
- sequential back edges (cycle annotations): 0

## Relation decisions

- **nac-rel-18** — RETYPE FLOW→BRANCH: Adjustment is conditioned on a molecular result being available; a condition-labelled BRANCH preserves that instead of unconditional FLOW.
- **nac-rel-19** — RETYPE SUPPORTS→BRANCH: Culture results condition the adjustment step; the relation becomes a condition-labelled BRANCH matching the molecular channel.
- **nac-rel-01** — KEEP: source: compatible picture plus new infiltrate supports pneumonia classification.
- **nac-rel-02** — KEEP: source: negative initial radiograph plus high suspicion requires repeating radiography at 48 hours.
- **nac-rel-03** — KEEP: source: inconclusive radiograph with high probability and priority/complication criteria selects CT.
- **nac-rel-04** — KEEP: laboratory workup runs parallel to imaging for suspected pneumonia; contextual by design, not a sequential step.
- **nac-rel-05** — KEEP: source states labs are requested 'para definir la necesidad de hospitalización'; SUPPORTS (informs a decision) is the correct type.
- **nac-rel-06** — KEEP: source: added laboratories apply 'en pacientes con indicación de hospitalización'.
- **nac-rel-07** — KEEP: source: sputum Gram/culture applies to patients with diagnosis AND hospitalization indication.
- **nac-rel-08** — KEEP: source: FilmArray applies to confirmed pneumonia with hospitalization indication.
- **nac-rel-09** — KEEP: source: hemocultures apply to hospitalized patients meeting the compound severity criteria.
- **nac-rel-10** — KEEP: source: severe contexts (shock/severe sepsis/multiorgan failure) escalate the hospitalized laboratory panel.
- **nac-rel-10a** — KEEP: source: desaturation independently triggers arterial blood gases.
- **nac-rel-11** — KEEP: ICU/UCE direct indications are a separate severity decision below hospital-level management; BRANCH preserves that.
- **nac-rel-12** — KEEP: the three-of-nine criteria pathway is a distinct ICU/UCE qualification mechanism; BRANCH preserves it separately.
- **nac-rel-13** — KEEP: treatment context hangs off the hospitalization decision as BRANCH_CONTEXT; visual table evidence must not become confident flow.
- **nac-rel-14** — KEEP: treatment context hangs off the hospitalization decision as BRANCH_CONTEXT; visual table evidence must not become confident flow.
- **nac-rel-15** — KEEP: treatment context hangs off the hospitalization decision as BRANCH_CONTEXT; visual table evidence must not become confident flow.
- **nac-rel-16** — KEEP: treatment context hangs off the hospitalization decision as BRANCH_CONTEXT; visual table evidence must not become confident flow.
- **nac-rel-17** — KEEP: treatment context hangs off the hospitalization decision as BRANCH_CONTEXT; visual table evidence must not become confident flow.
- **nac-rel-20** — KEEP: after inpatient empirical treatment the discharge criteria are assessed; the discharge-plan section supports the continuation.
- **nac-rel-21** — KEEP: after inpatient empirical treatment the discharge criteria are assessed; the discharge-plan section supports the continuation.
- **nac-rel-22** — KEEP: after inpatient empirical treatment the discharge criteria are assessed; the discharge-plan section supports the continuation.
- **nac-rel-23** — KEEP: after inpatient empirical treatment the discharge criteria are assessed; the discharge-plan section supports the continuation.
- **nac-rel-24** — KEEP: after inpatient empirical treatment the discharge criteria are assessed; the discharge-plan section supports the continuation.
- **nac-rel-25** — KEEP: source: 'Al momento del alta se indicarán al paciente los signos y síntomas que sugieren recaída'.
- **nac-rel-26** — KEEP: source: 'cita de revisión con medicina interna a las 4 semanas del alta'.
- **nac-rel-27** — KEEP: repeat radiography supports/confirms the diagnosis; SUPPORTS is the correct contextual type.
- **nac-rel-28** — KEEP: serum LDH/total proteins accompany thoracentesis interpretation; condition-labelled BRANCH is appropriate.
- **nac-rel-29** — KEEP: induced sputum applies when spontaneous collection is impossible; condition-labelled BRANCH.
- **nac-rel-30** — KEEP: deep-sample FilmArray panel is the first option when there is no SARS-CoV-2 suspicion; condition-labelled BRANCH.
- **nac-rel-31** — KEEP: nasopharyngeal panel applies when the patient does not expectorate; condition-labelled BRANCH.
- **nac-rel-32** — KEEP: qualifying presumed parapneumonic effusion selects the pleural study; condition-labelled BRANCH.
