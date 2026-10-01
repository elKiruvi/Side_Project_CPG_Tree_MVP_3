# CT-PL-193 v9 NAC Candidate Graph Review

Status: candidate knowledge authored by the OpenCode agent (`openai/gpt-5.6-sol`), not clinically approved.

## Inventory

- CandidateRules: 29
- CandidateRelations: 33
- Variables: 63
- Observations: 29
- Issues: 7 open (6 blocking, 1 non-blocking)
- Source: CT-PL-193, version 9, approved 2024-08-12, pages 1-7

## Proposed pathway

1. **Entry and imaging (page 3):** lower-respiratory signs or symptoms lead to chest radiography (`nac-r01`). A compatible clinical picture plus a new infiltrate supports pneumonia classification (`nac-r02`). A negative initial radiograph plus high suspicion leads to repeat radiography at 48 hours (`nac-r03`). High clinical probability with an inconclusive radiograph leads to CT only when diagnosis is a priority or a listed complication is suspected (`nac-r04`). Febrile neutropenia plus lower-respiratory symptoms is preserved as a separate CT entry context (`nac-r05`), not forced behind another rule.
2. **Progressive laboratory workup (page 3):** suspected pneumonia triggers CBC and BUN for hospitalization assessment (`nac-r06`). Hospitalization indication adds CRP, creatinine, lactate, and sodium (`nac-r07`). Shock, severe sepsis, or multiorgan failure adds coagulation, liver tests, bilirubin, and arterial gases (`nac-r08`); desaturation separately triggers arterial gases (`nac-r09`). Pleural effusion with thoracentesis indication adds serum LDH and total proteins (`nac-r10`).
3. **Hospital microbiology (pages 3-4):** blood cultures use the source's nested logic: hospitalized pneumonia AND (any of BUN >30, CRP >15, leukocytes >15000 OR at least two of DBP <60, HR >120, RR >30, pleuritic pain). Sampling precedes the first IV antibiotic and includes two blood-culture samples plus one anaerobic bottle (`nac-r11`). Hospitalized pneumonia also leads to sputum Gram/culture (`nac-r12`), induced sputum when spontaneous collection is impossible (`nac-r13`), and FilmArray (`nac-r14`) with deep-sample and nasopharyngeal branches (`nac-r15`, `nac-r16`).
4. **Pleural branch (page 4):** a unilateral presumed parapneumonic effusion over 1 cm without another apparent cause leads to diagnostic thoracentesis and the listed pleural studies (`nac-r17`), with serum tests supporting interpretation (`nac-r10`).
5. **Disposition (page 4):** any listed hospitalization indication is represented as an alternative trigger (`nac-r18`), not one giant AND. ICU/UCE has two separate routes: any direct severe indication (`nac-r19`) OR at least three of the nine listed criteria (`nac-r20`).
6. **Treatment (page 5, visual inspection):** five context-specific empirical-treatment candidates preserve alternatives, combinations, dose/interval summaries, duration, and footnote uncertainty (`nac-r21` through `nac-r25`). They remain `BLOCKED` because the source table has no reliable native-text span and its merged cells/footnotes require clinical verification. Molecular/culture-guided adjustment is a later candidate (`nac-r26`).
7. **Discharge and follow-up (pages 5-6):** discharge is represented as one conjunctive eligibility state containing 48 hours afebrile, hemodynamic thresholds, oxygenation, oral tolerance, compensated comorbidities, outpatient antibiotic availability, and social conditions (`nac-r27`). At discharge, educate about fever, dyspnea, and chest pain (`nac-r28`) and schedule internal-medicine review four weeks later (`nac-r29`).

## Relationship interpretation

- `FLOW` and `BRANCH` encode only clinically meaningful progression or an explicit conditional continuation.
- `SUPPORTS` is used where a test informs a later decision without being a workflow transition.
- `BRANCH_CONTEXT` is used for parallel suspicion workup and visually inspected treatment contexts; it is not execution order.
- Medication alternatives remain inside actions and are never represented as sequential edges.
- No negative branch was invented where the source gives no alternative.

## Open Issues

1. `nac-issue-visual-treatment` (blocking): page 5 treatment tables were manually inspected but lack reliable native-text spans.
2. `nac-issue-flowchart` (blocking): page 6 is visual-only and was not used to manufacture canonical flow.
3. `nac-issue-bun-conflict` (blocking): narrative BUN >30 conflicts with visually inspected flowchart BUN >20.
4. `nac-issue-icu-modalities` (blocking): narrative ICU/UCE structure differs from the flowchart's major/minor presentation.
5. `nac-issue-risk-definitions` (blocking): MRSA, *P. aeruginosa*, and resistant-Enterobacterales risk activation is incompletely operationalized.
6. `nac-issue-table-footnotes` (blocking): table footnote and merged-cell associations need line-by-line review.
7. `nac-issue-discharge-and` (non-blocking): the discharge paragraph was interpreted as conjunctive, but the source does not publish a formal operator.

## Structural review

- All rule, action, variable, relation, observation, issue, and span references resolve.
- All non-visual exact quotes match their cited native extraction spans.
- All rules, actions, variables, and relations have evidence bindings.
- No inferred or unresolved evidence class is used for a `FLOW` or `BRANCH` edge.
- The validator intentionally reports two disconnected rules: `nac-r05-ct-neutropenia` is an independent CT entry context, and `nac-r06-basic-laboratory` is parallel suspicion-stage assessment connected contextually rather than by a fabricated sequence.
- Clinical correctness and the treatment-table transcription remain pending human review.
