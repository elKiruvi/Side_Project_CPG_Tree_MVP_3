# Árbol clínico candidato — CT-PL-193 v9

> ⚠️ **ÁRBOL CANDIDATO — PENDIENTE DE VALIDACIÓN CLÍNICA**

## ETAPA 1 — DIAGNÓSTICO POR IMAGEN

┌────────────────────────────────┐
│ Solicitar radiografía de tórax │
└────────────────────────────────┘

• **Solicitar radiografía de tórax** <!-- rule:nac-r01-chest-radiograph -->
    <!-- rel:nac-rel-01 -->
    ├─ [Cuadro compatible e infiltrado nuevo] → **Diagnóstico de neumonía respaldado** <!-- rule:nac-r02-diagnostic-support -->
    <!-- rel:nac-rel-02 -->
    ├─ [Radiografía inicial normal y sospecha alta] → **Repetir radiografía a las 48 horas** <!-- rule:nac-r03-repeat-radiograph -->
    <!-- rel:nac-rel-03 -->
    ├─ [Radiografía no concluyente con indicación de TC] → **Tomografía de tórax en contextos específicos** <!-- rule:nac-r04-ct-inconclusive -->
• **Diagnóstico de neumonía respaldado** <!-- rule:nac-r02-diagnostic-support -->
    <!-- rel:nac-rel-32 -->
    ├─ [Derrame parapneumónico calificado] → **Toracentesis y estudio del líquido pleural** <!-- rule:nac-r17-pleural-study -->
• **Toracentesis y estudio del líquido pleural** <!-- rule:nac-r17-pleural-study -->
    <!-- rel:nac-rel-28 -->
    ├─ [Con indicación de toracentesis] → **LDH y proteínas en suero (derrame pleural)** <!-- rule:nac-r10-pleural-serum-tests -->

## ETAPA 2 — LABORATORIO EN SOSPECHA DE NEUMONÍA

┌───────────────────────────────────────────────────┐
│ Hemoleucograma y BUN para decidir hospitalización │
└───────────────────────────────────────────────────┘

• **Hemoleucograma y BUN para decidir hospitalización** <!-- rule:nac-r06-basic-laboratory -->

## ETAPA 3 — HOSPITALIZACIÓN, SEVERIDAD Y MICROBIOLOGÍA

┌──────────────────────────────────────────┐
│ Hospitalizar (indicaciones alternativas) │
└──────────────────────────────────────────┘

• **Hospitalizar (indicaciones alternativas)** <!-- rule:nac-r18-hospitalization -->
    <!-- rel:nac-rel-06 -->
    ├─ [Con indicación de hospitalización] → **Añadir PCR, creatinina, lactato y sodio** <!-- rule:nac-r07-hospital-laboratory -->
    <!-- rel:nac-rel-09 -->
    ├─ [Hospitalizado y cumple criterios de hemocultivo] → ⚠ CONFLICTO — **Hemocultivos según criterios compuestos** <!-- rule:nac-r11-blood-cultures -->
    <!-- rel:nac-rel-07 -->
    ├─ [Con indicación de hospitalización] → **Gram y cultivo de esputo** <!-- rule:nac-r12-sputum-culture -->
    <!-- rel:nac-rel-08 -->
    ├─ [Diagnóstico confirmado y hospitalización] → **Panel molecular respiratorio (FilmArray)** <!-- rule:nac-r14-filmarray -->
    <!-- rel:nac-rel-11 -->
    ├─ [Indicación directa de UCI/UCE] → ⚠ CONFLICTO — **UCI/UCE por indicación directa** <!-- rule:nac-r19-icu-direct -->
    <!-- rel:nac-rel-12 -->
    ├─ [Cumple 3 o más criterios] → ⚠ CONFLICTO — **UCI/UCE si cumple 3 o más de 9 criterios** <!-- rule:nac-r20-icu-three-criteria -->
• **Añadir PCR, creatinina, lactato y sodio** <!-- rule:nac-r07-hospital-laboratory -->
    <!-- rel:nac-rel-10 -->
    ├─ [Contexto grave] → **Coagulación, transaminasas, bilirrubinas y gases** <!-- rule:nac-r08-severe-laboratory -->
    <!-- rel:nac-rel-10a -->
    ├─ [Desaturación] → **Gases arteriales por desaturación** <!-- rule:nac-r09-desaturation-abg -->
• **Gram y cultivo de esputo** <!-- rule:nac-r12-sputum-culture -->
    <!-- rel:nac-rel-29 -->
    ├─ [No puede recolectarse espontáneamente] → **Esputo inducido** <!-- rule:nac-r13-induced-sputum -->
    <!-- rel:nac-rel-19 -->
    ├─ [Resultado de cultivo disponible] → ⚠ PENDIENTE — **Ajustar según prueba molecular o cultivo** <!-- rule:nac-r26-adjust-to-results -->
• **Panel molecular respiratorio (FilmArray)** <!-- rule:nac-r14-filmarray -->
    <!-- rel:nac-rel-30 -->
    ├─ [Muestra profunda disponible, sin sospecha de SARS-CoV-2] → **Panel de neumonía con muestra profunda** <!-- rule:nac-r15-deep-filmarray -->
    <!-- rel:nac-rel-31 -->
    ├─ [El paciente no expectora] → **Panel respiratorio por hisopado nasofaríngeo** <!-- rule:nac-r16-nasopharyngeal-panel -->
    <!-- rel:nac-rel-18 -->
    ├─ [Resultado molecular disponible] → ⚠ PENDIENTE — **Ajustar según prueba molecular o cultivo** <!-- rule:nac-r26-adjust-to-results -->

## ETAPA 4 — TRATAMIENTO EMPÍRICO (EVIDENCIA VISUAL)

┌──────────────────────────────────────────────────┐
│ ⚠ PENDIENTE — Tratamiento sin factores de riesgo │
└──────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ ⚠ PENDIENTE — Tratamiento con riesgo de Pseudomonas/resistentes │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│ ⚠ PENDIENTE — Tratamiento con riesgo de MRSA y otros │
└──────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────┐
│ ⚠ PENDIENTE — Tratamiento con solo riesgo de MRSA │
└───────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ ⚠ PENDIENTE — Tratamiento en contexto posviral/MRSA │
└─────────────────────────────────────────────────────┘

• ⚠ PENDIENTE — **Tratamiento sin factores de riesgo** <!-- rule:nac-r21-treatment-no-risk -->
    <!-- rel:nac-rel-20 -->
• **Egreso si cumple todos los criterios** <!-- rule:nac-r27-discharge -->
    <!-- rel:nac-rel-25 -->
    ├─ [Al momento del alta] → **Educar sobre signos de recaída** <!-- rule:nac-r28-discharge-education -->
    <!-- rel:nac-rel-26 -->
    ├─ [A las 4 semanas del alta] → **Revisión con medicina interna a las 4 semanas** <!-- rule:nac-r29-follow-up -->
• ⚠ PENDIENTE — **Tratamiento con riesgo de Pseudomonas/resistentes** <!-- rule:nac-r22-treatment-pseudomonas -->
    <!-- rel:nac-rel-21 -->
• ⚠ PENDIENTE — **Tratamiento con riesgo de MRSA y otros** <!-- rule:nac-r23-treatment-mrsa-combined -->
    <!-- rel:nac-rel-22 -->
• ⚠ PENDIENTE — **Tratamiento con solo riesgo de MRSA** <!-- rule:nac-r24-treatment-mrsa-only -->
    <!-- rel:nac-rel-23 -->
• ⚠ PENDIENTE — **Tratamiento en contexto posviral/MRSA** <!-- rule:nac-r25-treatment-postviral -->
    <!-- rel:nac-rel-24 -->
└─ [Criterios de egreso valorados después del tratamiento] → **Egreso si cumple todos los criterios** <!-- rel:nac-rel-20,nac-rel-21,nac-rel-22,nac-rel-23,nac-rel-24 --> <!-- rule:nac-r27-discharge -->

## CONTEXTO (relaciones no secuenciales)

- Solicitar radiografía de tórax —[Contexto de rama]→ Hemoleucograma y BUN para decidir hospitalización · Estudio paralelo en sospecha de neumonía <!-- rel:nac-rel-04 -->
- Hemoleucograma y BUN para decidir hospitalización —[Apoya]→ Hospitalizar (indicaciones alternativas) · Resultados para definir hospitalización <!-- rel:nac-rel-05 -->
- Hospitalizar (indicaciones alternativas) —[Contexto de rama]→ Tratamiento sin factores de riesgo · Contexto de tratamiento (tabla visual) <!-- rel:nac-rel-13 -->
- Hospitalizar (indicaciones alternativas) —[Contexto de rama]→ Tratamiento con riesgo de Pseudomonas/resistentes · Contexto de tratamiento (tabla visual) <!-- rel:nac-rel-14 -->
- Hospitalizar (indicaciones alternativas) —[Contexto de rama]→ Tratamiento con riesgo de MRSA y otros · Contexto de tratamiento (tabla visual) <!-- rel:nac-rel-15 -->
- Hospitalizar (indicaciones alternativas) —[Contexto de rama]→ Tratamiento con solo riesgo de MRSA · Contexto de tratamiento (tabla visual) <!-- rel:nac-rel-16 -->
- Hospitalizar (indicaciones alternativas) —[Contexto de rama]→ Tratamiento en contexto posviral/MRSA · Contexto de tratamiento (tabla visual) <!-- rel:nac-rel-17 -->
- Repetir radiografía a las 48 horas —[Apoya]→ Diagnóstico de neumonía respaldado · La radiografía repetida respalda el diagnóstico <!-- rel:nac-rel-27 -->

## FUERA DE LA VÍA PRINCIPAL

┌────────────────────────────────────────────────────────────────────┐
│ ⚠ CONTEXTO INDEPENDIENTE — Tomografía simple en neutropenia febril │
└────────────────────────────────────────────────────────────────────┘
<!-- rule:nac-r05-ct-neutropenia -->

---

Reglas candidatas: 29 · Relaciones: 33 · Pendientes de revisión: 6 reglas y 0 relaciones · Aprobación clínica: 0.
