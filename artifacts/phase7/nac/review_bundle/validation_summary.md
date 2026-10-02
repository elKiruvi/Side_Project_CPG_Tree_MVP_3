# Structural validation — CT-PL-193-v9

Candidate review packet (Phase 6). This report covers TECHNICAL validation only. Clinical questions live in `clinical_review_questions.md` and must be answered by qualified reviewers; nothing here is clinically approved.

## Summary

- graph: `candidate-graph-ct-pl-193-v9-phase4`
- rules: 29 · relations: 33 · issues: 7
- blocked: 6 rules · 0 relations
- structural errors: **0** · warnings: 2 · info: 61
- provenance: PASSED
- projection parity: PASSED
- review readiness: **READY_FOR_CLINICAL_REVIEW**
- graph content hash: `7560e68617a69440e2b89bf486d22b7c537caa49bed9c3a99cdc05f4fe130d4c`

> READY_FOR_CLINICAL_REVIEW does not mean CLINICALLY_VALID or APPROVED. It means the artifact is structurally trustworthy and ready for human review.

## Errors

- none

## Warnings

- **TOPOLOGY_DISCONNECTED_COMPONENT** disconnected component [ISOLATED_CONTEXT]: nac-r05-ct-neutropenia — rule participates in no sequential relation; intentionally contextual/conflicting/blocked (/components/1)
- **TOPOLOGY_DISCONNECTED_COMPONENT** disconnected component [ENTRY_COMPONENT]: nac-r06-basic-laboratory — declared stage root without sequential edges (projection anchor) (/components/2)

## Disconnected components

- [ISOLATED_CONTEXT] nac-r05-ct-neutropenia — rule participates in no sequential relation; intentionally contextual/conflicting/blocked
- [ENTRY_COMPONENT] nac-r06-basic-laboratory — declared stage root without sequential edges (projection anchor)

## Cycles

- none detected

## Entry points

- nac-r01-chest-radiograph
- nac-r06-basic-laboratory
- nac-r18-hospitalization
- nac-r21-treatment-no-risk
- nac-r22-treatment-pseudomonas
- nac-r23-treatment-mrsa-combined
- nac-r24-treatment-mrsa-only
- nac-r25-treatment-postviral

## Terminal nodes

- nac-r03-repeat-radiograph
- nac-r04-ct-inconclusive
- nac-r05-ct-neutropenia
- nac-r06-basic-laboratory
- nac-r08-severe-laboratory
- nac-r09-desaturation-abg
- nac-r10-pleural-serum-tests
- nac-r11-blood-cultures
- nac-r13-induced-sputum
- nac-r15-deep-filmarray
- nac-r16-nasopharyngeal-panel
- nac-r19-icu-direct
- nac-r20-icu-three-criteria
- nac-r26-adjust-to-results
- nac-r28-discharge-education
- nac-r29-follow-up
## Questions requiring clinical judgment

See `clinical_review_questions.md` in the same Phase 5 artifact directory. Software cannot answer those questions.

## Technical traceability

Full machine-readable details: `validation_report.json`. Exact candidate hashes and artifact hashes: `review_manifest.json`.
