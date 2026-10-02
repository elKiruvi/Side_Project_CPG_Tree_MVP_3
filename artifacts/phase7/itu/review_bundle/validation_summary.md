# Structural validation — CT-PL-197-v06

Candidate review packet (Phase 6). This report covers TECHNICAL validation only. Clinical questions live in `clinical_review_questions.md` and must be answered by qualified reviewers; nothing here is clinically approved.

## Summary

- graph: `candidate-graph-ct-pl-197-v06-phase4`
- rules: 38 · relations: 46 · issues: 7
- blocked: 3 rules · 1 relations
- structural errors: **0** · warnings: 3 · info: 51
- provenance: PASSED
- projection parity: PASSED
- review readiness: **READY_FOR_CLINICAL_REVIEW**
- graph content hash: `710791a089dda66d17c8d1b5e745d3205586d77df543995cc7e5f3a4ddefa8e3`

> READY_FOR_CLINICAL_REVIEW does not mean CLINICALLY_VALID or APPROVED. It means the artifact is structurally trustworthy and ready for human review.

## Errors

- none

## Warnings

- **TOPOLOGY_DISCONNECTED_COMPONENT** disconnected component [ISOLATED_CONTEXT]: itu-r03-complicated-structural-definition — rule participates in no sequential relation; intentionally contextual/conflicting/blocked (/components/1)
- **TOPOLOGY_DISCONNECTED_COMPONENT** disconnected component [ISOLATED_CONTEXT]: itu-r06-complicated-beyond-bladder-definition — rule participates in no sequential relation; intentionally contextual/conflicting/blocked (/components/2)
- **TOPOLOGY_DISCONNECTED_COMPONENT** disconnected component [ISOLATED_CONTEXT]: itu-r25-pediatric-hospitalization-source — rule participates in no sequential relation; intentionally contextual/conflicting/blocked (/components/3)

## Disconnected components

- [ISOLATED_CONTEXT] itu-r03-complicated-structural-definition — rule participates in no sequential relation; intentionally contextual/conflicting/blocked
- [ISOLATED_CONTEXT] itu-r06-complicated-beyond-bladder-definition — rule participates in no sequential relation; intentionally contextual/conflicting/blocked
- [ISOLATED_CONTEXT] itu-r25-pediatric-hospitalization-source — rule participates in no sequential relation; intentionally contextual/conflicting/blocked

## Cycles

- none detected

## Entry points

- itu-r01-asymptomatic-bacteriuria-classification
- itu-r02-symptomatic-uti-classification
- itu-r36-pregnancy-upper-treatment
- itu-r37-pregnancy-upper-prevention

## Terminal nodes

- itu-r03-complicated-structural-definition
- itu-r06-complicated-beyond-bladder-definition
- itu-r08-normal-dipstick
- itu-r09-urine-gram
- itu-r11-culture-positive-spontaneous
- itu-r12-culture-positive-symptomatic
- itu-r13-culture-positive-new-catheter
- itu-r14-sample-before-antibiotic
- itu-r16-hospital-blood-tests
- itu-r17-blood-cultures
- itu-r19-contrast-ct
- itu-r20-uro-ct
- itu-r21-functional-ultrasound
- itu-r22-pregnancy-ultrasound
- itu-r25-pediatric-hospitalization-source
- itu-r26-oral-step-or-discharge
- itu-r38-adjust-to-culture
## Questions requiring clinical judgment

See `clinical_review_questions.md` in the same Phase 5 artifact directory. Software cannot answer those questions.

## Technical traceability

Full machine-readable details: `validation_report.json`. Exact candidate hashes and artifact hashes: `review_manifest.json`.
