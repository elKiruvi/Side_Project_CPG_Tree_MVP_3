# CT-PL-197 v06 (ITU) — Phase 5 Review Summary

Status: preliminary review projection of the reconciled Candidate Graph. Nothing
here is clinically approved. The canonical artifact is
`artifacts/phase5/itu/candidate_graph.json`; `review_tree.html` and
`review_tree.svg` are deterministic projections of it.

## Proposed stage roots (projection anchors, not invented edges)

1. **Asymptomatic bacteriuria context** — `itu-r01`
2. **Symptomatic UTI (classification and diagnostics)** — `itu-r02`
3. **Pregnancy upper-UTI treatment and prevention** — `itu-r36`, `itu-r37`

The pregnancy upper stage connects to the pregnancy ultrasound rule only
through a `BRANCH_CONTEXT` relation; no unconditional FLOW was invented. The
outpatient upper-UTI branch is rendered as a BLOCKED dashed edge because it
contradicts the upper-UTI hospitalization bullet.

## Main pathway

1. Significant bacteriuria without attributable symptoms classifies
   asymptomatic bacteriuria (`r01`); with attributable symptoms it classifies
   UTI (`r02`). Lower (`r04`) and upper (`r05`) classifications branch by their
   source definitions. The two complicated-UTI definitions (`r03`, `r06`)
   remain separate conflicting contexts.
2. Symptomatic UTI leads to emergency cytochemistry except in women with a
   first typical episode (`r07`), universal emergency Gram stain (`r09`), and
   urine culture except for a first uncomplicated lower-UTI episode in a
   premenopausal woman (`r10`). A normal dipstick with low suspicion rules the
   diagnosis out (`r08`).
3. Sampling precedes the first antibiotic dose (`r14`); permanent-catheter
   users require a newly inserted catheter (`r15`). Culture positivity keeps
   its three scoped thresholds (`r11`, `r12`, `r13`).
4. Pyelonephritis with fever, hypothermia, or shock triggers blood cultures
   (`r17`). Urgent imaging is anchored at symptomatic UTI with shock, acute
   renal failure, local complication, or fever persisting after 72 hours of
   correct therapy (`r18`); the modality branches on the suspected abnormality
   (`r19` contrast CT, `r20` CT urography, `r21` functional ultrasound).
   Pregnancy adds its own ultrasound indications (`r22`).
5. Asymptomatic-bacteriuria treatment is restricted to pregnancy or a
   qualifying invasive urinary procedure (`r23` → `r28`).
6. Hospitalization uses alternative indications (`r24`); the pediatric bullet
   stays blocked out of scope (`r25`). Hospitalized patients get the blood
   panel (`r16`). Treatment branches by lower/outpatient/inpatient context and
   resistant Gram-negative risk with or without shock (`r27`–`r32`); pregnancy
   uses its own table (`r33`–`r37`). Empirical therapy is adjusted when culture
   and antibiogram are available (`r38`).
7. Oral-step/discharge eligibility is one ambiguous composite decision
   (`r26`), reached conditionally from the inpatient treatment branches.

## Phase 5 relation decisions

- 43 relations reviewed: 26 kept, 14 retyped, 2 retargeted, 0 removed,
  3 added, 1 blocked.
- `itu-rel-07` became BRANCH: urine culture is a diagnostic pathway step with
  its own exception, like urinalysis and Gram.
- `itu-rel-14` and `itu-rel-42` were re-anchored at the symptomatic-UTI
  classification because the source conditions urgent imaging and pregnancy
  ultrasound on symptomatic UTI contexts, not on upper UTI alone.
- `itu-rel-23` (outpatient upper UTI) is BLOCKED: it contradicts the
  hospitalization bullet and stays visible for adjudication.
- `itu-rel-29` became BRANCH_CONTEXT: prevention is a parallel table column,
  not a step after treatment.
- `itu-rel-30…38` and `itu-rel-39…41` became condition-labelled BRANCH
  relations (culture availability / criteria met).
- Added: `itu-rel-44` (Gram informs empirical treatment), `itu-rel-45` and
  `itu-rel-46` (prevention decisions are culture-based per footnote 2).

## Unresolved Issues (all open)

- `itu-issue-complicated-definitions` (BLOCKING): two non-equivalent
  complicated-UTI definitions remain separate.
- `itu-issue-upper-hospital-outpatient` (BLOCKING): upper UTI is both a
  hospitalization indication and an outpatient treatment row.
- `itu-issue-pediatric-adult-scope` (BLOCKING): pediatric statement inside the
  adult protocol.
- `itu-issue-oral-discharge` (BLOCKING): oral switch and discharge share one
  "and/or" criteria label.
- `itu-issue-pregnancy-cross-page` (BLOCKING): preventive-option and
  gestational-note alignment across pages 4–5.
- `itu-issue-hospital-list-operator` (NON-BLOCKING): hospitalization list
  interpreted as alternatives.
- `itu-issue-transition-list-operator` (NON-BLOCKING): transition list
  interpreted as conjunctive with oxygen OR PaO2.

## Disconnected components and why

- `itu-r03`, `itu-r06` — the two complicated-UTI definitions; kept disconnected
  so reviewers adjudicate them as conflicting classifications.
- `itu-r25` — pediatric hospitalization statement; blocked and out of the adult
  scope.

## What clinicians should review

1. The overlapping classification model (lower/upper/complicated/pregnancy are
   not mutually exclusive).
2. The BLOCKED outpatient upper-UTI branch versus the hospitalization bullet.
3. The pregnancy table continuation and its footnotes.
4. The distinct exceptions of urinalysis and urine culture.
5. The imaging nesting (urgent context → modality).
6. The oral-step/discharge ambiguity.
7. The culture-guided adjustment and prevention BRANCH relations.
