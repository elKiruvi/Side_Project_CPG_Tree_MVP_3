# CT-PL-197 v06 ITU Candidate Graph Review

Status: candidate knowledge authored by the OpenCode agent (`openai/gpt-5.6-sol`), not clinically approved.

## Inventory

- CandidateRules: 38
- CandidateRelations: 43
- Variables: 60
- Observations: 38
- Issues: 7 open (5 blocking, 2 non-blocking)
- Source: CT-PL-197, version 06, approved 2025-09-30, pages 1-5

## Proposed pathway

1. **Overlapping entry classifications (pages 1-2):** significant bacteriuria without attributable symptoms supports asymptomatic-bacteriuria classification (`itu-r01`); significant bacteriuria with attributable symptoms supports UTI (`itu-r02`). Lower (`itu-r04`) and upper (`itu-r05`) classifications branch by their source definitions. The structural/functional complicated definition (`itu-r03`) and beyond-bladder/listed-syndrome definition (`itu-r06`) remain separate contextual candidates, not one canonical Boolean.
2. **Emergency urine testing (pages 2-3):** suspected UTI in emergency care leads to urine cytochemistry except in women with a first episode and typical symptoms (`itu-r07`). A normal dipstick plus low suspicion supports excluding the diagnosis (`itu-r08`). Uncentrifuged urine Gram stain applies to all emergency patients (`itu-r09`).
3. **Culture and sampling (page 3):** urine culture is broadly requested except for a first uncomplicated lower-UTI episode in a premenopausal woman (`itu-r10`). The three positivity rules retain their scopes: spontaneous urine at >=100,000 CFU (`itu-r11`), otherwise-unexplained symptomatic context at >=1,000 CFU (`itu-r12`), and newly inserted catheter sample at >=100 CFU (`itu-r13`). Sampling occurs before the first antibiotic dose (`itu-r14`); permanent-catheter users require a newly inserted catheter and initial-volume discard (`itu-r15`).
4. **Blood testing (page 3):** hospitalization triggers CBC, ionogram, renal function, and CRP (`itu-r16`). Acute pyelonephritis with fever, hypothermia, or septic shock triggers blood cultures (`itu-r17`).
5. **Nested imaging (page 3):** UTI with shock, acute renal failure, local complication, or fever persisting after 72 hours of correct therapy triggers urgent ultrasound or contrast CT (`itu-r18`). Suspected small abscess/local nephritis selects contrast CT (`itu-r19`); suspected structural abnormality selects CT urography (`itu-r20`); suspected functional/emptying/obstructive abnormality selects ultrasound with post-void residual (`itu-r21`). Pregnancy plus pyelonephritis, more than one pregnancy UTI, or stone suspicion triggers renal ultrasound (`itu-r22`).
6. **Asymptomatic bacteriuria treatment (pages 3-4):** treatment eligibility is restricted to pregnancy or an invasive urinary procedure with bleeding/uroepithelial-disruption risk (`itu-r23`). The table alternatives and durations are applied only after that eligibility (`itu-r28`); there is no universal asymptomatic-bacteriuria treatment rule.
7. **Hospitalization (page 3):** shock, oral intolerance, upper UTI, decompensated underlying disease, resistant organism without an outpatient option, renal deterioration, renal/pararenal abscess, or inadequate social support are represented as alternative indications (`itu-r24`). The pediatric pyelonephritis bullet is preserved separately as blocked/out-of-scope (`itu-r25`).
8. **General treatment table (page 4):** lower UTI alternatives retain dose, route, interval, duration, and the fosfomycin footnote (`itu-r27`). Outpatient upper UTI with cephalexin and 48-hour culture reassessment remains visible (`itu-r29`) despite the hospitalization conflict. Inpatient upper UTI is divided by resistant Gram-negative risk and shock (`itu-r30` to `itu-r32`), preserving the amikacin and meropenem footnotes.
9. **Pregnancy table (pages 4-5):** the page break is treated as one table context. Pregnancy asymptomatic bacteriuria (`itu-r33`), lower UTI (`itu-r34`), recurrence-dependent prevention (`itu-r35`), upper UTI empirical selection by resistance/shock qualifiers (`itu-r36`), and upper-UTI prevention (`itu-r37`) retain dose/duration/follow-up/prevention dimensions. Preventive options with difficult gestational-note alignment remain blocked.
10. **Adjustment and transition (pages 3-5):** empirical treatment flows to culture/antibiogram adjustment (`itu-r38`). The shared criteria for “oral therapy and/or discharge” are one composite candidate (`itu-r26`) with oxygen saturation OR PaO2 nested inside the broader AND; the graph does not assert that oral switch equals discharge.

## Relationship interpretation

- `FLOW` represents explicit temporal continuation such as pre-antibiotic sampling, culture-guided adjustment, or later oral/discharge eligibility.
- `BRANCH` represents a source-conditioned pathway choice, including lower/upper classification, culture threshold scope, imaging modality, disposition, and treatment context.
- `BRANCH_CONTEXT` is used where pregnancy or diagnostic context is shared but no sequence is asserted.
- `SUPPORTS` is not used as a substitute for workflow order.
- Alternative antibiotics remain together inside one treatment decision and are not converted into medication sequences.
- No negative destination was invented when the source did not provide one.

## Open Issues

1. `itu-issue-complicated-definitions` (blocking): two non-equivalent complicated-UTI formulations remain separate.
2. `itu-issue-upper-hospital-outpatient` (blocking): upper UTI is both a hospitalization indication and an outpatient treatment row.
3. `itu-issue-pediatric-adult-scope` (blocking): a pediatric hospitalization statement remains in the adult protocol.
4. `itu-issue-oral-discharge` (blocking): oral switch and discharge share one “and/or” criteria label and cannot be equated safely.
5. `itu-issue-pregnancy-cross-page` (blocking): preventive-option and gestational-note alignment across pages 4-5 needs clinical review.
6. `itu-issue-hospital-list-operator` (non-blocking): hospitalization bullets were interpreted as alternatives without a formal source operator.
7. `itu-issue-transition-list-operator` (non-blocking): transition bullets were interpreted as conjunctive eligibility without a formal source operator.

## Structural review

- All entity and relation references resolve.
- Every exact quote matches its cited native `SourceSpan`.
- Every variable, rule, action, and relation has field evidence.
- Urinalysis and urine-culture exceptions are represented independently and bind to their own text.
- The pregnancy table is cited across both pages and preserves the extraction continuation flag.
- No inferred or unresolved evidence class is used for a sequential edge.
- Validator warnings for `itu-r03`, `itu-r06`, and `itu-r25` are intentional: the two complicated definitions are contextual/conflicting classifications, and the pediatric statement is blocked outside scope. No connector was invented to hide those components.
- Clinical correctness, list operators, conflicts, and table-footnote applicability remain pending human review.
