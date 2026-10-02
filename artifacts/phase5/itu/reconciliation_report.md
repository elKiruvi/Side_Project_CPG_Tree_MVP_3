# CT-PL-197 v06 (ITU) — Phase 5 reconciliation report

Generated deterministically by the Phase 5 reconcile module. This is a semantic review record of relation-level decisions; the CandidateGraph remains canonical and no candidate was promoted to approved knowledge.

## Counts

- CandidateRules: 38 (unchanged from Phase 4)
- initial CandidateRelations: 43
- final CandidateRelations: 46
- relations kept: 26
- relations retyped: 14
- relations retargeted: 2
- relations removed: 0
- relations added: 3
- relations blocked: 1
- open Issues: 7
- structural findings: 3 (errors: 0, warnings: 3)
- sequential back edges (cycle annotations): 0

## Relation decisions

- **itu-rel-14** — RETARGET r05→r02: The source conditions urgent imaging on symptomatic UTI plus listed triggers, not on the upper-UTI classification alone.
- **itu-rel-42** — RETARGET r05→r02: Pregnancy ultrasound indications (pyelonephritis, more than one episode, stone suspicion) are pregnancy-UTI contexts, anchored at the symptomatic classification.
- **itu-rel-23** — BLOCK: Outpatient upper-UTI treatment contradicts the upper-UTI hospitalization indication; the branch stays visible as BLOCKED instead of being silently deleted.
- **itu-rel-07** — RETYPE BRANCH_CONTEXT→BRANCH: Urine culture is a diagnostic decision with its own source-defined exception, matching the urinalysis and Gram branches; it belongs in the pathway, not as a floating context.
- **itu-rel-29** — RETYPE FLOW→BRANCH_CONTEXT: Preventive therapy is a parallel column of the pregnancy table conditioned on the same context, not a sequential step after treatment.
- **itu-rel-30** — RETYPE FLOW→BRANCH: Adjustment of empirical therapy is conditioned on culture and antibiogram availability; a condition-labelled BRANCH replaces unconditional FLOW.
- **itu-rel-31** — RETYPE FLOW→BRANCH: Adjustment of empirical therapy is conditioned on culture and antibiogram availability; a condition-labelled BRANCH replaces unconditional FLOW.
- **itu-rel-32** — RETYPE FLOW→BRANCH: Adjustment of empirical therapy is conditioned on culture and antibiogram availability; a condition-labelled BRANCH replaces unconditional FLOW.
- **itu-rel-33** — RETYPE FLOW→BRANCH: Adjustment of empirical therapy is conditioned on culture and antibiogram availability; a condition-labelled BRANCH replaces unconditional FLOW.
- **itu-rel-34** — RETYPE FLOW→BRANCH: Adjustment of empirical therapy is conditioned on culture and antibiogram availability; a condition-labelled BRANCH replaces unconditional FLOW.
- **itu-rel-35** — RETYPE FLOW→BRANCH: Adjustment of empirical therapy is conditioned on culture and antibiogram availability; a condition-labelled BRANCH replaces unconditional FLOW.
- **itu-rel-36** — RETYPE FLOW→BRANCH: Adjustment of empirical therapy is conditioned on culture and antibiogram availability; a condition-labelled BRANCH replaces unconditional FLOW.
- **itu-rel-37** — RETYPE FLOW→BRANCH: Adjustment of empirical therapy is conditioned on culture and antibiogram availability; a condition-labelled BRANCH replaces unconditional FLOW.
- **itu-rel-38** — RETYPE FLOW→BRANCH: Adjustment of empirical therapy is conditioned on culture and antibiogram availability; a condition-labelled BRANCH replaces unconditional FLOW.
- **itu-rel-39** — RETYPE FLOW→BRANCH: Oral-step/discharge eligibility is conditioned on the listed criteria; the label is part of the BRANCH semantics.
- **itu-rel-40** — RETYPE FLOW→BRANCH: Oral-step/discharge eligibility is conditioned on the listed criteria; the label is part of the BRANCH semantics.
- **itu-rel-41** — RETYPE FLOW→BRANCH: Oral-step/discharge eligibility is conditioned on the listed criteria; the label is part of the BRANCH semantics.
- **itu-rel-44** — ADD: SUPPORTS itu-r09-urine-gram → itu-r27-lower-treatment, itu-r29-upper-outpatient-treatment, itu-r30-upper-inpatient-no-resistant-risk, itu-r31-upper-inpatient-resistant-no-shock, itu-r32-upper-inpatient-resistant-shock (label: Gram informs empirical treatment choice)
- **itu-rel-45** — ADD: BRANCH itu-r37-pregnancy-upper-prevention → itu-r38-adjust-to-culture (label: culture/susceptibility available)
- **itu-rel-46** — ADD: BRANCH itu-r35-pregnancy-lower-prevention → itu-r38-adjust-to-culture (label: culture/susceptibility available)
- **itu-rel-01** — KEEP: source: asymptomatic-bacteriuria treatment eligibility is restricted to pregnancy or a qualifying invasive urinary procedure.
- **itu-rel-02** — KEEP: source: the eligibility decision leads to the table treatment alternatives.
- **itu-rel-03** — KEEP: source: lower-UTI definition features classify lower UTI.
- **itu-rel-04** — KEEP: source: upper-UTI definition features classify upper UTI.
- **itu-rel-05** — KEEP: source: emergency cytochemistry applies to suspected UTI except women with a first typical episode.
- **itu-rel-06** — KEEP: source: Gram stain applies to every emergency patient.
- **itu-rel-08** — KEEP: source: the sample must be taken before the first antibiotic dose.
- **itu-rel-09** — KEEP: source: permanent-catheter users need a newly inserted catheter and initial-volume discard.
- **itu-rel-10** — KEEP: source: >=100,000 CFU threshold applies to appropriately obtained spontaneous urine.
- **itu-rel-11** — KEEP: source: >=1,000 CFU threshold applies to the otherwise-unexplained symptomatic context.
- **itu-rel-12** — KEEP: source: the newly inserted catheter threshold follows the catheter sampling rule.
- **itu-rel-13** — KEEP: source: blood cultures apply to acute pyelonephritis with fever, hypothermia, or septic shock.
- **itu-rel-15** — KEEP: source: suspected small abscess/local nephritis selects contrast CT.
- **itu-rel-16** — KEEP: source: suspected structural abnormality selects CT urography.
- **itu-rel-17** — KEEP: source: suspected functional/emptying/obstructive abnormality selects ultrasound with post-void residual.
- **itu-rel-18** — KEEP: source: upper UTI is an explicit hospitalization indication bullet; the branch stays active and the conflict is handled by the BLOCKED outpatient relation.
- **itu-rel-19** — KEEP: source: every hospitalized ITU patient gets CBC, ionogram, renal function, and CRP.
- **itu-rel-20** — KEEP: source: hospitalized upper UTI without resistant Gram-negative risk selects the first table row.
- **itu-rel-21** — KEEP: source: resistant Gram-negative risk without shock selects the second table row; amikacin is avoided in shock.
- **itu-rel-22** — KEEP: source: resistant Gram-negative risk with shock selects meropenem empirically.
- **itu-rel-24** — KEEP: source: lower UTI selects the lower treatment row.
- **itu-rel-25** — KEEP: pregnancy upper treatment shares the pregnant upper-UTI context with the ultrasound rule; contextual by design.
- **itu-rel-26** — KEEP: source: pregnancy conditions the asymptomatic-bacteriuria pregnancy table row.
- **itu-rel-27** — KEEP: source: pregnancy conditions the lower-UTI pregnancy table row.
- **itu-rel-28** — KEEP: source: prevention in pregnancy lower UTI applies only when there is recurrence.
- **itu-rel-43** — KEEP: source: a normal dipstick plus low clinical suspicion rules out the diagnosis.
