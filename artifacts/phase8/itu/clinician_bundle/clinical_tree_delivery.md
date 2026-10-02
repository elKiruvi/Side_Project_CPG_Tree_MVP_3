# Árbol clínico candidato — CT-PL-197 v06

> ⚠️ **ÁRBOL CANDIDATO — PENDIENTE DE VALIDACIÓN CLÍNICA**

## ETAPA 1 — BACTERIURIA ASINTOMÁTICA

┌──────────────────────────┐
│ Bacteriuria asintomática │
└──────────────────────────┘

• **Bacteriuria asintomática** <!-- rule:itu-r01-asymptomatic-bacteriuria-classification -->
    <!-- rel:itu-rel-01 -->
    ├─ [Embarazo o procedimiento invasivo de riesgo] → **Tratar bacteriuria asintomática solo en embarazo o procedimiento de riesgo** <!-- rule:itu-r23-asb-treatment-eligibility -->
    <!-- rel:itu-rel-26 -->
    ├─ [Embarazo] → **Embarazo: bacteriuria asintomática** <!-- rule:itu-r33-pregnancy-asb-treatment -->
• **Tratar bacteriuria asintomática solo en embarazo o procedimiento de riesgo** <!-- rule:itu-r23-asb-treatment-eligibility -->
    <!-- rel:itu-rel-02 -->
    ├─ [Elegibilidad definida] → **Tratamiento de bacteriuria asintomática** <!-- rule:itu-r28-asb-treatment -->
• **Tratamiento de bacteriuria asintomática** <!-- rule:itu-r28-asb-treatment -->
    <!-- rel:itu-rel-31 -->
    ├─ [Resultado de cultivo y antibiograma disponible] → **Ajustar según urocultivo y antibiograma** <!-- rule:itu-r38-adjust-to-culture -->
• **Embarazo: bacteriuria asintomática** <!-- rule:itu-r33-pregnancy-asb-treatment -->
    <!-- rel:itu-rel-36 -->
    ├─ [Resultado de cultivo y antibiograma disponible] → **Ajustar según urocultivo y antibiograma** <!-- rule:itu-r38-adjust-to-culture -->

## ETAPA 2 — ITU SINTOMÁTICA (CLASIFICACIÓN Y DIAGNÓSTICO)

┌─────────────────┐
│ ITU sintomática │
└─────────────────┘

• **ITU sintomática** <!-- rule:itu-r02-symptomatic-uti-classification -->
    <!-- rel:itu-rel-03 -->
    ├─ [Características de ITU baja] → **ITU baja** <!-- rule:itu-r04-lower-uti-classification -->
    <!-- rel:itu-rel-04 -->
    ├─ [Características de ITU alta] → **ITU alta (pielonefritis)** <!-- rule:itu-r05-upper-uti-classification -->
    <!-- rel:itu-rel-05 -->
    ├─ [Estudio en urgencias (con excepción)] → **Citoquímico de orina (excepto primer episodio típico)** <!-- rule:itu-r07-urinalysis -->
    <!-- rel:itu-rel-06 -->
    ├─ [Todos los pacientes de urgencias] → **Gram de orina sin centrifugar** <!-- rule:itu-r09-urine-gram -->
    <!-- rel:itu-rel-07 -->
    ├─ [Cultivo indicado (salvo excepción)] → **Urocultivo (excepto primer episodio no complicado)** <!-- rule:itu-r10-urine-culture -->
    <!-- rel:itu-rel-14 -->
    ├─ [Contexto de imagen urgente] → **Imagen urgente (ecografía o TC con contraste)** <!-- rule:itu-r18-urgent-imaging -->
    <!-- rel:itu-rel-42 -->
    ├─ [Embarazo con indicación de ecografía] → **Ecografía renal en embarazo** <!-- rule:itu-r22-pregnancy-ultrasound -->
• **ITU baja** <!-- rule:itu-r04-lower-uti-classification -->
    <!-- rel:itu-rel-24 -->
    ├─ [ITU baja] → **Tratamiento de ITU baja** <!-- rule:itu-r27-lower-treatment -->
    <!-- rel:itu-rel-27 -->
    ├─ [Embarazo] → **Embarazo: ITU baja** <!-- rule:itu-r34-pregnancy-lower-treatment -->
• **Tratamiento de ITU baja** <!-- rule:itu-r27-lower-treatment -->
    <!-- rel:itu-rel-30 -->
    ├─ [Resultado de cultivo y antibiograma disponible] → **Ajustar según urocultivo y antibiograma** <!-- rule:itu-r38-adjust-to-culture -->
• **Embarazo: ITU baja** <!-- rule:itu-r34-pregnancy-lower-treatment -->
    <!-- rel:itu-rel-28 -->
    ├─ [Solo si hay recurrencia] → ⚠ PENDIENTE — **Embarazo: prevención si hay recurrencia** <!-- rule:itu-r35-pregnancy-lower-prevention -->
    <!-- rel:itu-rel-37 -->
    ├─ [Resultado de cultivo y antibiograma disponible] → **Ajustar según urocultivo y antibiograma** <!-- rule:itu-r38-adjust-to-culture -->
• ⚠ PENDIENTE — **Embarazo: prevención si hay recurrencia** <!-- rule:itu-r35-pregnancy-lower-prevention -->
    <!-- rel:itu-rel-46 -->
    ├─ [Decisión según cultivos y sensibilidad] → **Ajustar según urocultivo y antibiograma** <!-- rule:itu-r38-adjust-to-culture -->
• **ITU alta (pielonefritis)** <!-- rule:itu-r05-upper-uti-classification -->
    <!-- rel:itu-rel-13 -->
    ├─ [Fiebre, hipotermia o choque] → **Hemocultivos (pielonefritis con fiebre, hipotermia o choque)** <!-- rule:itu-r17-blood-cultures -->
    <!-- rel:itu-rel-18 -->
    ├─ [Indicación de hospitalización según protocolo] → ⚠ CONFLICTO — **Hospitalizar (indicaciones alternativas)** <!-- rule:itu-r24-hospitalization -->
    <!-- rel:itu-rel-23 -->
    ├─ [ITU alta ambulatoria (CONFLICTO por resolver)] → ⚠ CONFLICTO — **ITU alta ambulatoria (en conflicto con hospitalización)** ⚠ BLOQUEADA <!-- rule:itu-r29-upper-outpatient-treatment -->
• ⚠ CONFLICTO — **Hospitalizar (indicaciones alternativas)** <!-- rule:itu-r24-hospitalization -->
    <!-- rel:itu-rel-19 -->
    ├─ [Paciente hospitalizado] → **Hemoleucograma, ionograma, función renal y PCR** <!-- rule:itu-r16-hospital-blood-tests -->
    <!-- rel:itu-rel-20 -->
    ├─ [Sin factores de riesgo de BGN resistente] → **ITU alta hospitalaria sin riesgo de BGN resistente** <!-- rule:itu-r30-upper-inpatient-no-resistant-risk -->
    <!-- rel:itu-rel-21 -->
    ├─ [Con riesgo de BGN resistente, sin choque] → **ITU alta con riesgo de BGN resistente, sin choque** <!-- rule:itu-r31-upper-inpatient-resistant-no-shock -->
    <!-- rel:itu-rel-22 -->
    ├─ [Con riesgo de BGN resistente y choque] → **ITU alta con riesgo de BGN resistente y choque** <!-- rule:itu-r32-upper-inpatient-resistant-shock -->
• **ITU alta hospitalaria sin riesgo de BGN resistente** <!-- rule:itu-r30-upper-inpatient-no-resistant-risk -->
    <!-- rel:itu-rel-39 -->
    <!-- rel:itu-rel-33 -->
    ├─ [Resultado de cultivo y antibiograma disponible] → **Ajustar según urocultivo y antibiograma** <!-- rule:itu-r38-adjust-to-culture -->
• **ITU alta con riesgo de BGN resistente, sin choque** <!-- rule:itu-r31-upper-inpatient-resistant-no-shock -->
    <!-- rel:itu-rel-40 -->
    <!-- rel:itu-rel-34 -->
    ├─ [Resultado de cultivo y antibiograma disponible] → **Ajustar según urocultivo y antibiograma** <!-- rule:itu-r38-adjust-to-culture -->
• **ITU alta con riesgo de BGN resistente y choque** <!-- rule:itu-r32-upper-inpatient-resistant-shock -->
    <!-- rel:itu-rel-41 -->
    <!-- rel:itu-rel-35 -->
    ├─ [Resultado de cultivo y antibiograma disponible] → **Ajustar según urocultivo y antibiograma** <!-- rule:itu-r38-adjust-to-culture -->
• ⚠ CONFLICTO — **ITU alta ambulatoria (en conflicto con hospitalización)** <!-- rule:itu-r29-upper-outpatient-treatment -->
    <!-- rel:itu-rel-32 -->
    ├─ [Resultado de cultivo y antibiograma disponible] → **Ajustar según urocultivo y antibiograma** <!-- rule:itu-r38-adjust-to-culture -->
• **Citoquímico de orina (excepto primer episodio típico)** <!-- rule:itu-r07-urinalysis -->
    <!-- rel:itu-rel-43 -->
    ├─ [Tirilla normal y baja sospecha] → **Tirilla normal y baja sospecha descartan el diagnóstico** <!-- rule:itu-r08-normal-dipstick -->
• **Urocultivo (excepto primer episodio no complicado)** <!-- rule:itu-r10-urine-culture -->
    <!-- rel:itu-rel-10 -->
    ├─ [Muestra espontánea adecuada] → **Positivo con 100 000 UFC o más (micción espontánea)** <!-- rule:itu-r11-culture-positive-spontaneous -->
    <!-- rel:itu-rel-11 -->
    ├─ [Contexto sintomático] → **Positivo con 1 000 UFC o más (síntomas sin otra causa)** <!-- rule:itu-r12-culture-positive-symptomatic -->
    <!-- rel:itu-rel-08 -->
    ├─ [Antes de la primera dosis de antibiótico] → **Tomar muestra antes de la primera dosis de antibiótico** <!-- rule:itu-r14-sample-before-antibiotic -->
    <!-- rel:itu-rel-09 -->
    ├─ [Usuario de sonda permanente] → **Sonda nueva en usuarios de sonda permanente** <!-- rule:itu-r15-permanent-catheter-sampling -->
• **Sonda nueva en usuarios de sonda permanente** <!-- rule:itu-r15-permanent-catheter-sampling -->
    <!-- rel:itu-rel-12 -->
    ├─ [Muestra por sonda recién insertada] → **Positivo con 100 UFC o más (sonda recién insertada)** <!-- rule:itu-r13-culture-positive-new-catheter -->
• **Imagen urgente (ecografía o TC con contraste)** <!-- rule:itu-r18-urgent-imaging -->
    <!-- rel:itu-rel-15 -->
    ├─ [Sospecha de absceso o nefritis local] → **TC con contraste (abscesos pequeños o nefritis local)** <!-- rule:itu-r19-contrast-ct -->
    <!-- rel:itu-rel-16 -->
    ├─ [Sospecha de alteración estructural] → **Urotomografía (alteración estructural)** <!-- rule:itu-r20-uro-ct -->
    <!-- rel:itu-rel-17 -->
    ├─ [Sospecha de alteración funcional] → **Ecografía con residuo posmiccional (alteración funcional)** <!-- rule:itu-r21-functional-ultrasound -->
└─ [Se cumplen todos los criterios] → **Paso a vía oral y/o egreso (ambiguo)** <!-- rel:itu-rel-39,itu-rel-40,itu-rel-41 --> <!-- rule:itu-r26-oral-step-or-discharge -->

## ETAPA 3 — EMBARAZO — ITU ALTA (TRATAMIENTO Y PREVENCIÓN)

┌───────────────────────────────────┐
│ Embarazo: tratamiento de ITU alta │
└───────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ ⚠ PENDIENTE — Embarazo: terapia preventiva de ITU alta │
└────────────────────────────────────────────────────────┘

• **Embarazo: tratamiento de ITU alta** <!-- rule:itu-r36-pregnancy-upper-treatment -->
    <!-- rel:itu-rel-38 -->
    ├─ [Resultado de cultivo y antibiograma disponible] → **Ajustar según urocultivo y antibiograma** <!-- rule:itu-r38-adjust-to-culture -->
• ⚠ PENDIENTE — **Embarazo: terapia preventiva de ITU alta** <!-- rule:itu-r37-pregnancy-upper-prevention -->
    <!-- rel:itu-rel-45 -->
    ├─ [Decisión según cultivos y sensibilidad] → **Ajustar según urocultivo y antibiograma** <!-- rule:itu-r38-adjust-to-culture -->

## CONTEXTO (relaciones no secuenciales)

- Ecografía renal en embarazo —[Contexto de rama]→ Embarazo: tratamiento de ITU alta · Contexto de embarazo (ITU alta) <!-- rel:itu-rel-25 -->
- Embarazo: tratamiento de ITU alta —[Contexto de rama]→ Embarazo: terapia preventiva de ITU alta · Contexto de embarazo (ITU alta) <!-- rel:itu-rel-29 -->
- Gram de orina sin centrifugar —[Apoya]→ Tratamiento de ITU baja, ITU alta ambulatoria (en conflicto con hospitalización), ITU alta hospitalaria sin riesgo de BGN resistente, ITU alta con riesgo de BGN resistente, sin choque, ITU alta con riesgo de BGN resistente y choque · El Gram orienta el tratamiento empírico <!-- rel:itu-rel-44 -->

## FUERA DE LA VÍA PRINCIPAL

┌─────────────────────────────────────────────────────────┐
│ ⚠ CONTEXTO INDEPENDIENTE — Definición de ITU complicada │
│ (estructural/funcional)                                 │
└─────────────────────────────────────────────────────────┘
<!-- rule:itu-r03-complicated-structural-definition -->

┌───────────────────────────────────────────────────────────────────┐
│ ⚠ CONTEXTO INDEPENDIENTE — Definición de ITU complicada (más allá │
│ de la vejiga)                                                     │
└───────────────────────────────────────────────────────────────────┘
<!-- rule:itu-r06-complicated-beyond-bladder-definition -->

┌───────────────────────────────────────────────────────────────────┐
│ ⚠ FUERA DE ALCANCE (protocolo adulto) — Mención pediátrica (fuera │
│ del alcance adulto)                                               │
└───────────────────────────────────────────────────────────────────┘
<!-- rule:itu-r25-pediatric-hospitalization-source -->

---

Reglas candidatas: 38 · Relaciones: 46 · Pendientes de revisión: 3 reglas y 1 relaciones · Aprobación clínica: 0.
