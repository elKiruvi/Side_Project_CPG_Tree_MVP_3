# CT-PL-193 v9 (NAC) — Phase 5 Review Summary

Status: preliminary review projection of the reconciled Candidate Graph. Nothing
here is clinically approved. The canonical artifact is
`artifacts/phase5/nac/candidate_graph.json`; `review_tree.html` and
`review_tree.svg` are deterministic projections of it.

## Proposed stage roots (projection anchors, not invented edges)

1. **Diagnostic imaging** — `nac-r01-chest-radiograph`
2. **Laboratory workup (suspected pneumonia)** — `nac-r06-basic-laboratory`
3. **Hospitalization, severity and microbiology** — `nac-r18-hospitalization`
4. **Empirical treatment (visual evidence, BLOCKED)** — `nac-r21` … `nac-r25`

The laboratory stage is linked to the hospitalization stage only by a canonical
`SUPPORTS` relation ("para definir la necesidad de hospitalización"); no
sequential edge was invented. The treatment stage is linked to hospitalization
only by `BRANCH_CONTEXT` relations because the page 5 table evidence remains
visual and uncertain.

## Main pathway (top to bottom in the projection)

1. Lower-respiratory signs or symptoms trigger chest radiography (`r01`).
2. A compatible picture plus a new infiltrate supports the classification of
   pneumonia (`r02`); a negative initial radiograph plus high suspicion triggers
   repeat radiography at 48 hours (`r03`); inconclusive radiography with high
   probability triggers CT only when diagnosis is a priority or a listed
   complication is suspected (`r04`).
3. Suspected pneumonia triggers CBC and BUN for the hospitalization assessment
   (`r06`); the hospitalization decision (`r18`) follows when any listed
   indication applies.
4. Hospitalization adds CRP, creatinine, lactate, sodium (`r07`), sputum
   Gram/culture (`r12`), FilmArray (`r14`), and conditional blood cultures
   under the compound criteria (`r11`). Severe contexts escalate labs (`r08`,
   `r09`). ICU/UCE has two distinct qualification routes: direct severe
   indications (`r19`) or three or more of the nine listed criteria (`r20`).
5. Empirical treatment is selected by risk context (`r21`–`r25`, all BLOCKED
   pending visual-table verification) and adjusted when molecular or culture
   results are available (`r26`, BLOCKED).
6. Discharge requires the composite eligibility state (`r27`), followed by
   relapse-warning education (`r28`) and internal-medicine follow-up at four
   weeks (`r29`).

## Side branches and contexts

- Pleural branch: qualifying presumed parapneumonic effusion → diagnostic
  thoracentesis (`r17`) with accompanying serum tests (`r10`).
- FilmArray branch: deep-sample panel (`r15`) versus nasopharyngeal panel
  (`r16`).
- Sputum branch: induced sputum when spontaneous collection is impossible
  (`r13`).
- Febrile-neutropenia CT (`r05`) is an independent disconnected context; the
  source does not connect it to the radiography pathway.

## Phase 5 relation decisions

- 33 relations reviewed: 31 kept, 2 retyped, 0 removed, 0 added, 0 blocked.
- `nac-rel-18` and `nac-rel-19` became condition-labelled `BRANCH` relations
  ("molecular result available" / "culture result available") so that
  result-guided adjustment is not rendered as unconditional sequence.

## Unresolved Issues (all open)

- `nac-issue-visual-treatment` (BLOCKING): page 5 treatment tables were manually
  inspected but lack reliable native-text spans.
- `nac-issue-flowchart` (BLOCKING): page 6 is visual-only; it did not define
  canonical flow.
- `nac-issue-bun-conflict` (BLOCKING): narrative BUN >30 versus flowchart
  BUN >20.
- `nac-issue-icu-modalities` (BLOCKING): narrative ICU criteria versus flowchart
  major/minor structure.
- `nac-issue-risk-definitions` (BLOCKING): MRSA/P. aeruginosa/resistant
  Enterobacterales risk activation is incompletely operationalized.
- `nac-issue-table-footnotes` (BLOCKING): footnote/merged-cell alignment.
- `nac-issue-discharge-and` (NON-BLOCKING): discharge list interpreted as AND.

## Disconnected components and why

- `nac-r05-ct-neutropenia` — independent CT entry context for febrile
  neutropenia; no source-defined connection to the radiography pathway.
- `nac-r06-basic-laboratory` — participates only in contextual relations by
  design; it is anchored as a stage root in the projection instead of receiving
  a fabricated sequential edge.

## What clinicians should review

1. The pathway stage order (imaging/labs/hospitalization/treatment/discharge).
2. The BLOCKED treatment table transcription and footnotes.
3. The BUN and ICU source conflicts.
4. The nested blood-culture criteria structure.
5. The discharge AND interpretation.
6. Whether the treatment→discharge FLOW edges apply to every hospitalized
   context, including ICU.
