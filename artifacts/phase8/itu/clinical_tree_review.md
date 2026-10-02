# Árbol clínico candidato — Infección del tracto urinario en adultos (CT-PL-197 v06)

> ⚠️ **PENDIENTE DE VALIDACIÓN CLÍNICA**
>
> Este árbol fue generado a partir del protocolo institucional y aún no ha sido
> aprobado por personal clínico. No sustituye el juicio clínico ni debe usarse
> como soporte de decisiones asistenciales. Aprobación clínica actual: **0**.

Este documento acompaña el árbol visual y sirve como lista de verificación
para su revisión médica. Las preguntas marcan los puntos en los que el
protocolo tiene ambigüedades, conflictos entre fuentes o asociaciones de
tabla pendientes de verificar.

## Cómo revisar este árbol

1. Abra `clinical_tree.html` en un navegador (no requiere instalación).
2. Recorra el árbol de arriba hacia abajo. Haga clic en cada caja para ver la
   condición, la acción propuesta, la página del protocolo y la evidencia.
   Haga clic en las flechas para ver la relación.
3. Use las preguntas de este documento como lista de verificación.
4. Cuando tenga dudas sobre un punto, consulte la página citada del protocolo.
5. Registre sus decisiones y correcciones en el formato de revisión
   (`review_template.json` del paquete de revisión, con sus instrucciones).
6. Nada de lo que ve está aprobado todavía: su revisión decide qué se corrige
   y qué puede llegar a aprobarse.

## Visualización

- Árbol interactivo: [clinical_tree.html](clinical_tree.html)
- Árbol en SVG: [clinical_tree.svg](clinical_tree.svg)
- Vista imprimible (PDF desde el navegador): [print_view.html](print_view.html)

## Resumen

- Reglas candidatas: **38** (revisables 38/38)
- Relaciones candidatas: **46** (revisables 46/46)
- Issues abiertos: **7**
- Elementos bloqueados (pendientes de revisión): **3** reglas y **1** relación
- Aprobación clínica: **0**

### Cobertura de la revisión

El árbol principal dibuja **35** de las 38 reglas candidatas. Las tres
restantes aparecen en la sección «Componentes fuera de la vía principal» del
HTML: las dos definiciones no equivalentes de ITU complicada
(`itu-r03-complicated-structural-definition`,
`itu-r06-complicated-beyond-bladder-definition`) y la mención pediátrica
(`itu-r25-pediatric-hospitalization-source`). De las 46 relaciones, **43** se
dibujan como flechas y **3** son relaciones de apoyo o contexto (sección
«Relaciones contextuales»). El embarazo es un subflujo contextual con sus
propias raíces de etapa, no una etapa obligatoria para todo paciente.
**Ningún candidato queda fuera de la revisión**: el HTML incluye un
inventario completo de las 38 reglas y 46 relaciones.

## Flujo clínico propuesto

1. **Clasificación:** bacteriuria asintomática (sin síntomas atribuibles)
   frente a ITU sintomática; ITU baja o ITU alta (pielonefritis). Las dos
   definiciones de ITU complicada permanecen como componentes separados por
   resolver.
2. **Diagnóstico en urgencias:** citoquímico de orina (con su excepción),
   Gram de orina sin centrifugar y urocultivo (con su excepción). La muestra
   se toma antes de la primera dosis de antibiótico; en sonda permanente, de
   sonda recién insertada. Los tres umbrales de positividad del cultivo
   permanecen con su contexto.
3. **Sangre e imágenes:** hemocultivos en pielonefritis con fiebre,
   hipotermia o choque; imagen urgente con sus cuatro contextos y modalidad
   según la alteración sospechada (estructural o funcional); ecografía renal
   en embarazo con sus indicaciones.
4. **Disposición:** hospitalización por indicaciones alternativas; la rama
   «ITU alta ambulatoria» queda BLOQUEADA por conflicto con la indicación de
   hospitalización.
5. **Tratamiento:** por contexto (ITU baja, ITU alta ambulatoria/hospitalaria,
   riesgo de BGN resistente con o sin choque, embarazo), con ajuste según
   urocultivo y antibiograma.
6. **Transición:** paso a vía oral y/o egreso con un solo conjunto de
   criterios (relación ambigua por resolver).

## Preguntas críticas antes de aprobar el árbol

### Pregunta 1 — ITU alta: hospitalización frente a manejo ambulatorio

**Contexto clínico:** el protocolo lista «ITU alta» entre las indicaciones de
hospitalización, pero la tabla de tratamiento incluye una fila separada de
«ITU alta ambulatoria». El árbol conserva ambas: la rama ambulatoria está
BLOQUEADA y marcada como conflicto.

**Pregunta para el revisor:** ¿Cómo debe interpretarse esta combinación en
el árbol definitivo?

- [ ] Toda ITU alta requiere hospitalización
- [ ] Existe un subconjunto de ITU alta que puede manejarse ambulatoriamente
      (especifique los criterios: __________)
- [ ] La hospitalización depende de criterios adicionales (¿cuáles? __________)
- [ ] El protocolo contiene una inconsistencia que debe corregirse
- [ ] Otra interpretación: __________

**Elementos relacionados:** Regla `itu-r29-upper-outpatient-treatment` ·
Relación `itu-rel-23` (BLOQUEADA) · Regla `itu-r24-hospitalization` · Issue
`itu-issue-upper-hospital-outpatient` · Fuente: página 3 y tabla página 4.

### Pregunta 2 — Definición de ITU complicada

**Contexto clínico:** el documento contiene dos formulaciones no
equivalentes: (1) ITU en presencia de alteraciones estructurales o
funcionales de la vía urinaria; (2) infección con compromiso más allá de la
vejiga (pielonefritis, ITU febril o bacteriémica, asociada a catéter,
prostatitis).

**Pregunta para el revisor:** ¿Cuál definición debe utilizar el árbol?

- [ ] Primera definición (alteración estructural/funcional)
- [ ] Segunda definición (compromiso más allá de la vejiga)
- [ ] Se aplican en contextos diferentes (especifique: __________)
- [ ] Deben combinarse (definición final: __________)
- [ ] El protocolo requiere corrección

**Elementos relacionados:** Reglas
`itu-r03-complicated-structural-definition` y
`itu-r06-complicated-beyond-bladder-definition` · Issue
`itu-issue-complicated-definitions` · Fuente: página 1.

### Pregunta 3 — Mención pediátrica en protocolo de adultos

**Contexto clínico:** el protocolo es de adultos, pero conserva
«Pielonefritis aguda en pacientes pediátricos» entre las indicaciones de
hospitalización. El árbol la mantiene fuera de la vía principal.

**Pregunta para el revisor:** ¿Debe este criterio eliminarse del árbol de
adultos por estar fuera del alcance del protocolo actual?

- [ ] Sí, eliminar del árbol de adultos
- [ ] No, mantener como paso normal
- [ ] Mantener únicamente como nota/contexto
- [ ] Otro: __________

**Elementos relacionados:** Regla `itu-r25-pediatric-hospitalization-source`
· Issue `itu-issue-pediatric-adult-scope` · Fuente: página 3.

### Pregunta 4 — Paso a vía oral frente a egreso

**Contexto clínico:** el protocolo titula «Indicaciones para paso a terapia
oral y/o egreso» con un solo conjunto de criterios. El árbol los modela como
una única decisión ambigua.

**Pregunta para el revisor:** ¿Estos criterios significan que…?

- [ ] Los mismos criterios permiten tanto paso a vía oral como egreso
- [ ] Paso a vía oral y egreso son decisiones diferentes (especifique la
      relación: __________)
- [ ] El paso a vía oral ocurre antes del egreso
- [ ] Depende de otros criterios (¿cuáles? __________)
- [ ] El protocolo requiere aclaración

**Elementos relacionados:** Regla `itu-r26-oral-step-or-discharge` · Issue
`itu-issue-oral-discharge` · Fuente: página 3 y página 4.

### Pregunta 5 — Lógica de la lista de hospitalización

**Contexto clínico:** la sección de hospitalización lista varias
indicaciones (choque séptico, intolerancia oral, ITU alta, descompensación,
germen resistente sin opción ambulatoria, deterioro renal, absceso, soporte
social). El árbol las trata como alternativas (basta una).

**Pregunta para el revisor:** ¿Basta UNA sola indicación de la lista para
hospitalizar, o algunas requieren combinarse?

- [ ] Confirmar: basta una indicación
- [ ] Algunas requieren combinación (especifique: __________)

**Elementos relacionados:** Regla `itu-r24-hospitalization` · Issue
`itu-issue-hospital-list-operator` · Fuente: página 3.

### Pregunta 6 — Secuencia de imagen urgente

**Contexto clínico:** el protocolo define primero cuándo pedir imagen urgente
(choque séptico, falla renal aguda, complicación local, fiebre persistente
tras 72 h de antibiótico correcto) y luego la modalidad según la alteración
sospechada: estructural → urotomografía; funcional/vaciamiento → ecografía
con residuo posmiccional; absceso/nefritis local → TC con contraste.

**Pregunta para el revisor:** ¿La secuencia propuesta (indicación de imagen →
tipo de alteración sospechada → selección del estudio) refleja el manejo
previsto?

- [ ] Confirmar secuencia
- [ ] Corregir: __________

**Elementos relacionados:** Reglas `itu-r18-urgent-imaging`,
`itu-r19-contrast-ct`, `itu-r20-uro-ct`, `itu-r21-functional-ultrasound` ·
Fuente: página 3.

### Pregunta 7 — Factores de riesgo de BGN resistente

**Contexto clínico:** la rama de tratamiento hospitalario distingue «sin
factores de riesgo para BGN resistentes» de «con factores de riesgo»,
definidos como: hospitalización > 48 horas en los últimos 3 meses,
antibióticos en los últimos 90 días y colonización por germen BLEE.

**Pregunta para el revisor:** ¿Estos tres factores están completos y definen
correctamente la rama terapéutica?

- [ ] Confirmar factores actuales
- [ ] Falta incorporar: __________
- [ ] Reestructurar la rama

**Elementos relacionados:** Reglas `itu-r30` a `itu-r32` · Fuente: página 4
(notas al pie).

### Pregunta 8 — El choque como modificador del tratamiento

**Contexto clínico:** la tabla contiene notas como «Evitar en choque»
(amikacina) y «Administrar empíricamente si hay choque» (meropenem). El árbol
separa la rama con choque de la rama sin choque.

**Pregunta para el revisor:** ¿El choque debe representarse como una decisión
explícita que cambia la selección del antibiótico?

- [ ] Confirmar representación actual
- [ ] El choque modifica algo distinto (especifique: __________)

**Elementos relacionados:** Reglas `itu-r31-upper-inpatient-resistant-no-shock`
y `itu-r32-upper-inpatient-resistant-shock` · Fuente: página 4.

### Pregunta 9 — Tratamiento de bacteriuria asintomática

**Contexto clínico:** el árbol restringe el tratamiento de la bacteriuria
asintomática exactamente a dos contextos: embarazo y procedimiento invasivo
de vías urinarias con riesgo de sangrado o disrupción del uroepitelio.

**Pregunta para el revisor:** ¿El tratamiento debe restringirse exactamente a
esos dos contextos, o el protocolo prevé alguna población adicional?

- [ ] Confirmar: solo embarazo y procedimiento invasivo de riesgo
- [ ] Agregar población (especifique, citando el protocolo: __________)

**Elementos relacionados:** Regla `itu-r23-asb-treatment-eligibility` ·
Fuente: página 3 y notas página 4.

### Pregunta 10 — El embarazo como subflujo contextual

**Contexto clínico:** el árbol mantiene el embarazo como un subflujo
contextual separado (bacteriuria asintomática, ITU baja, ITU alta con
tratamiento y prevención), en lugar de incluirlo en el flujo general.

**Pregunta para el revisor:** ¿El embarazo debe permanecer como vía
contextual separada del flujo general de adultos?

- [ ] Confirmar subflujo contextual
- [ ] Integrar al flujo general (especifique cómo: __________)

**Elementos relacionados:** Reglas `itu-r33` a `itu-r37` · Fuente: tabla de
embarazo, páginas 4–5.

### Pregunta 11 — Alineación de la tabla de embarazo (páginas 4–5)

**Contexto clínico:** la tabla de embarazo continúa entre las páginas 4 y 5 y
varias asociaciones permanecen inciertas. Verifique puntualmente:

**Pregunta para el revisor:**

- [ ] La terapia preventiva corresponde a la condición correcta (ITU baja con
      recurrencia; ITU alta)
- [ ] Las opciones preventivas (nitrofurantoína, cefalexina, TMP-SMX,
      fosfomicina semanal) están asociadas a la fila correcta
- [ ] Las restricciones gestacionales (primer trimestre, hasta semana 34,
      cambio en semana 34) están unidas al medicamento correcto
- [ ] Hay errores que debo corregir: __________

**Elementos relacionados:** Reglas `itu-r35-pregnancy-lower-prevention` y
`itu-r37-pregnancy-upper-prevention` (PENDIENTES DE REVISIÓN) · Issue
`itu-issue-pregnancy-cross-page` · Fuente: páginas 4–5.

### Pregunta 12 — Ajuste por cultivo como paso obligatorio

**Contexto clínico:** el protocolo indica que la terapia empírica siempre
debe ajustarse según urocultivo y antibiograma. El árbol conecta todas las
ramas de tratamiento empírico con el ajuste por cultivo.

**Pregunta para el revisor:** ¿El ajuste según cultivo y antibiograma debe
ser un paso de reevaluación obligatorio para todas las ramas de tratamiento
empírico?

- [ ] Confirmar: obligatorio para todas las ramas
- [ ] Solo para algunas ramas (¿cuáles? __________)
- [ ] Opcional

**Elementos relacionados:** Regla `itu-r38-adjust-to-culture` · Relaciones
`itu-rel-30` a `itu-rel-38`, `itu-rel-45`, `itu-rel-46` · Fuente: página 5
(nota 1).

## Preguntas de precisión / mejora

### Pregunta 13 — Operador de los criterios de transición

**Contexto clínico:** dentro del conjunto de criterios de «paso a vía oral
y/o egreso» se incluye «SatO2 > 90 % o PaO2 > 60» junto a los demás
criterios tratados como simultáneos.

**Pregunta para el revisor:** ¿La saturación y la PaO2 son alternativas entre
sí y simultáneas con el resto de los criterios, tal como está modelado?

- [ ] Confirmar
- [ ] Corregir: __________

**Elementos relacionados:** Regla `itu-r26-oral-step-or-discharge` · Issue
`itu-issue-transition-list-operator` · Fuente: página 3 y página 4.

### Pregunta 14 — Umbrales de positividad del urocultivo

**Pregunta para el revisor:** ¿Los tres umbrales (≥ 100 000 UFC en micción
espontánea; ≥ 1 000 UFC en contexto sintomático; ≥ 100 UFC en sonda recién
insertada) están correctamente asignados a su contexto?

- [ ] Confirmar
- [ ] Corregir asignación: __________

**Elementos relacionados:** Reglas `itu-r11`, `itu-r12`, `itu-r13` · Fuente:
página 3.

## Elementos bloqueados

Los siguientes elementos permanecen **PENDIENTES DE REVISIÓN** (marcados con
⚠ y borde rojo discontinuo). No significan rechazo:

- `itu-r29-upper-outpatient-treatment` y su relación `itu-rel-23` — conflicto
  con la indicación de hospitalización de la ITU alta (Pregunta 1).
- `itu-r25-pediatric-hospitalization-source` — fuera del alcance adulto
  (Pregunta 3).
- `itu-r35-pregnancy-lower-prevention` y `itu-r37-pregnancy-upper-prevention`
  — alineación de la tabla de embarazo pendiente (Pregunta 11).

## Evidencia y trazabilidad

Cada caja del árbol indica la página del protocolo de la que proviene. Al
hacer clic en una caja o flecha se muestra la cita textual (cuando existe) y
el identificador técnico con su huella de contenido, que permite rastrear el
elemento hasta el protocolo original. La tabla de embarazo se trata como una
sola unidad entre las páginas 4 y 5; las asociaciones inciertas se marcan
para revisión manual.

## Cómo reportar correcciones

Use el formato de revisión del paquete (fase 7):
`review_template.json` junto con `review_instructions.md`. Para cada regla o
relación marque: Confirmar, Corregir (con la corrección propuesta), Rechazar,
Necesita aclaración o Diferir. Si falta una decisión o una rama en el árbol,
regístrela como contenido faltante. Sus decisiones se registran tal cual las
envía y no se modifican automáticamente.

Estado: **AWAITING_CLINICAL_REVIEW** · Aprobación clínica: **NO**.
