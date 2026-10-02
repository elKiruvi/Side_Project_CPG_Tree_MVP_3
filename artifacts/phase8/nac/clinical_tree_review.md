# Árbol clínico candidato — Neumonía adquirida en comunidad (CT-PL-193 v9)

> ⚠️ **PENDIENTE DE VALIDACIÓN CLÍNICA**
>
> Este árbol fue generado a partir del protocolo institucional y aún no ha sido
> aprobado por personal clínico. No sustituye el juicio clínico ni debe usarse
> como soporte de decisiones asistenciales. Aprobación clínica actual: **0**.

Este documento acompaña el árbol visual y sirve como lista de verificación
para su revisión médica. Las preguntas marcan los puntos en los que el
protocolo tiene ambigüedades, conflictos entre fuentes o evidencia visual
pendiente de verificar.

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

- Reglas candidatas: **29** (revisables 29/29)
- Relaciones candidatas: **33** (revisables 33/33)
- Issues abiertos: **7**
- Elementos bloqueados (pendientes de revisión): **6** reglas de tratamiento
- Aprobación clínica: **0**

### Cobertura de la revisión

El árbol principal dibuja **28** de las 29 reglas candidatas. La regla
restante (`nac-r05-ct-neutropenia`, tomografía en neutropenia febril) aparece
en la sección «Componentes fuera de la vía principal» del HTML porque el
protocolo la define como un contexto independiente, sin conexión textual con
la vía radiográfica. De las 33 relaciones, **25** se dibujan como flechas de
secuencia o rama y **8** son relaciones de apoyo o contexto (se muestran en
la sección «Relaciones contextuales»). **Ningún candidato queda fuera de la
revisión**: el HTML incluye un inventario completo de las 29 reglas y 33
relaciones.

## Flujo clínico propuesto

1. **Imagen:** ante signos o síntomas respiratorios bajos se solicita
   radiografía de tórax. Cuadro compatible más infiltrado nuevo respaldan el
   diagnóstico. Radiografía normal con sospecha alta → repetir a las 48 h.
   Tomografía solo en contextos específicos (alta probabilidad con
   radiografía no concluyente y prioridad diagnóstica o sospecha de
   complicación; y en neutropenia febril como contexto independiente).
2. **Laboratorio:** hemoleucograma y BUN en toda sospecha; al hospitalizar se
   añaden PCR, creatinina, lactato y sodio, con escalamiento en contextos
   graves y gases arteriales en desaturación.
3. **Microbiología hospitalaria:** hemocultivos bajo criterios compuestos,
   Gram/cultivo de esputo (inducido si es necesario) y panel molecular
   respiratorio; estudio de líquido pleural en derrame calificado.
4. **Disposición:** hospitalización por cualquiera de las indicaciones
   alternativas; la UCI/UCE es una decisión separada con dos vías (criterios
   directos o 3 o más de 9 criterios).
5. **Tratamiento:** antibiótico empírico por categoría de riesgo (tabla de la
   página 5, evidencia visual — pendiente de verificación), con ajuste según
   prueba molecular o cultivo.
6. **Egreso y seguimiento:** criterios de egreso conjuntos; al alta, educar
   sobre signos de recaída y programar revisión con medicina interna a las 4
   semanas.

## Preguntas críticas antes de aprobar el árbol

### Pregunta 1 — Discrepancia del umbral de BUN

**Contexto clínico:** el texto narrativo del protocolo usa BUN > 30 mg/dL
para los hemocultivos y los criterios de UCI/UCE, mientras que el flujograma
del propio protocolo (página 6) presenta un umbral diferente.

**Pregunta para el revisor:** ¿Cuál umbral debe considerarse válido para el
árbol clínico definitivo?

- [ ] Mantener BUN > 30 mg/dL (texto narrativo)
- [ ] Utilizar el valor del flujograma
- [ ] Ambos corresponden a contextos diferentes (especifique: __________)
- [ ] Otro: __________

**Elementos relacionados:** Regla `nac-r11-blood-cultures` · Regla
`nac-r20-icu-three-criteria` · Issue `nac-issue-bun-conflict` · Fuente:
páginas 3–4 y 6.

### Pregunta 2 — Vías de ingreso a UCI/UCE

**Contexto clínico:** el protocolo define indicaciones graves directas y, por
separado, un grupo en el que se ingresa si se cumplen 3 o más criterios de
una lista de nueve. El árbol las representa como dos vías alternativas.

**Pregunta para el revisor:** ¿El ingreso a UCI/UCE debe representarse como
dos vías alternativas: (1) presencia de un criterio grave directo, (2)
cumplimiento de 3 o más criterios del segundo grupo?

- [ ] Sí, como está propuesto
- [ ] No, la lógica es otra (especifique: __________)
- [ ] Requiere modificación: __________

**Elementos relacionados:** Reglas `nac-r19-icu-direct` y
`nac-r20-icu-three-criteria` · Issue `nac-issue-icu-modalities` · Fuente:
página 4 y flujograma página 6.

### Pregunta 3 — Relación entre hospitalización y UCI/UCE

**Contexto clínico:** el árbol muestra la evaluación de UCI/UCE como una
decisión que parte del nodo de hospitalización, sin obligar a que todo
hospitalizado siga los criterios de UCI.

**Pregunta para el revisor:** ¿La evaluación de UCI/UCE debe ocurrir: solo
después de decidir hospitalización, de forma independiente cuando existan
criterios graves, o bajo otra relación?

- [ ] Confirmar propuesta: rama condicionada desde hospitalización
- [ ] Evaluación independiente cuando existan criterios graves
- [ ] Otra relación: __________

**Elementos relacionados:** Relaciones `nac-rel-11` y `nac-rel-12` ·
Reglas `nac-r18-hospitalization`, `nac-r19-icu-direct`,
`nac-r20-icu-three-criteria` · Fuente: página 4.

### Pregunta 4 — Lógica compuesta de hemocultivos

**Contexto clínico:** el árbol modela: paciente hospitalizado Y (BUN > 30 O
PCR > 15 O leucocitos > 15.000 O al menos DOS de: diastólica < 60 mmHg, FC >
120 lpm, FR > 30 rpm, dolor pleurítico), tomados antes de la primera dosis de
antibiótico intravenoso.

**Pregunta para el revisor:** ¿Es esta la lectura correcta de los criterios
del protocolo (un criterio del primer grupo o dos del segundo)?

- [ ] Confirmar lógica propuesta
- [ ] Corregir operadores o grupos (especifique: __________)

**Elementos relacionados:** Regla `nac-r11-blood-cultures` · Fuente:
página 3.

### Pregunta 5 — Separación de las categorías terapéuticas

**Contexto clínico:** la tabla de tratamiento de la página 5 es de origen
visual (sin texto recuperable) y su transcripción permanece pendiente. El
árbol separa «sin factores de riesgo» de las categorías con factores de
riesgo (Pseudomonas/resistentes, MRSA, posviral).

**Pregunta para el revisor:** ¿La clasificación terapéutica propuesta separa
correctamente «NAC sin factores de riesgo» de las categorías con factores de
riesgo?

- [ ] Confirmar
- [ ] Corregir categorías (especifique: __________)

**Elementos relacionados:** Reglas `nac-r21-treatment-no-risk` a
`nac-r25-treatment-postviral` (todas PENDIENTES DE REVISIÓN) · Issue
`nac-issue-visual-treatment` · Fuente: página 5 (evidencia visual).

### Pregunta 6 — Asociación de notas al pie de la tabla

**Pregunta para el revisor:** ¿Cada nota al pie está asociada a la opción
terapéutica correcta (dosis, intervalo, duración, alternativa)?

- [ ] Confirmar asociaciones
- [ ] Corregir asociación: __________

**Elementos relacionados:** Issue `nac-issue-table-footnotes` · Fuente:
página 5 (evidencia visual, requiere revisión manual).

### Pregunta 7 — Factores de riesgo de gérmenes resistentes

**Contexto clínico:** el protocolo nombra ramas por riesgo de MRSA,
*Pseudomonas aeruginosa* y enterobacterias resistentes sin definir
completamente los criterios que las activan.

**Pregunta para el revisor:** ¿El protocolo define suficientemente los
factores de riesgo que determinan estas ramas terapéuticas?

- [ ] Sí, las condiciones actuales del árbol son suficientes
- [ ] No, falta incorporar: __________
- [ ] Debe eliminarse o reestructurarse esta rama

**Elementos relacionados:** Reglas `nac-r22` a `nac-r25` · Issue
`nac-issue-risk-definitions` · Fuente: página 5.

### Pregunta 8 — Operador de los criterios de egreso

**Contexto clínico:** el párrafo de egreso lista: 48 h afebril, estabilidad
hemodinámica (TAS > 90, FC < 100, FR < 24), saturación > 90 % o PaO2 > 60,
tolerancia oral, comorbilidades compensadas, tratamiento ambulatorio
asegurado y condiciones sociales adecuadas. El árbol los trata como un solo
requisito conjunto (todos simultáneamente).

**Pregunta para el revisor:** ¿Todos los criterios deben cumplirse
simultáneamente, o la lógica prevista es otra (por ejemplo, algunos son
alternativos)?

- [ ] Confirmar: todos simultáneamente
- [ ] Corregir operador: __________

**Elementos relacionados:** Regla `nac-r27-discharge` · Issue
`nac-issue-discharge-and` · Fuente: página 5.

### Pregunta 9 — Educación y seguimiento obligatorios al alta

**Pregunta para el revisor:** ¿La educación sobre signos de recaída (fiebre,
disnea, dolor torácico) y el control por medicina interna a las 4 semanas
deben ser pasos obligatorios para todo paciente que llega al egreso en esta
vía?

- [ ] Confirmar ambos como obligatorios
- [ ] Solo educación / solo seguimiento
- [ ] Opcionales según el paciente

**Elementos relacionados:** Reglas `nac-r28-discharge-education` y
`nac-r29-follow-up` · Fuente: página 6.

### Pregunta 10 — Tomografía en neutropenia febril

**Contexto clínico:** la recomendación de tomografía simple en neutropenia
febril con síntomas respiratorios bajos aparece como contexto independiente,
sin conexión con la vía diagnóstica principal.

**Pregunta para el revisor:** ¿Debe este contexto: permanecer independiente,
conectarse a la vía diagnóstica principal, o excluirse de este árbol de
adultos?

- [ ] Mantener como rama contextual independiente
- [ ] Conectar a la vía principal (especifique dónde: __________)
- [ ] Excluir del árbol

**Elementos relacionados:** Regla `nac-r05-ct-neutropenia` · Fuente:
página 3.

## Preguntas de precisión / mejora

### Pregunta 11 — Alcance de la radiografía repetida a las 48 h

**Pregunta para el revisor:** ¿La repetición de la radiografía a las 48 horas
aplica tanto al paciente ambulatorio como al hospitalizado?

- [ ] Confirmar: ambos
- [ ] Solo ambulatorio / solo hospitalizado

**Elementos relacionados:** Regla `nac-r03-repeat-radiograph` · Fuente:
página 3.

### Pregunta 12 — Agrupación de la indicación de tomografía

**Pregunta para el revisor:** ¿La tomografía debe exigir: alta probabilidad
clínica, radiografía no concluyente Y (prioridad diagnóstica O sospecha de
complicación), tal como está modelado?

- [ ] Confirmar agrupación
- [ ] Corregir: __________

**Elementos relacionados:** Regla `nac-r04-ct-inconclusive` · Fuente:
página 3.

## Elementos bloqueados

Las siguientes reglas permanecen **PENDIENTES DE REVISIÓN** (marcadas con ⚠ y
borde rojo discontinuo en el árbol). No significan rechazo: requieren que un
revisor verifique su contenido contra la tabla original:

- `nac-r21-treatment-no-risk` — tratamiento sin factores de riesgo
- `nac-r22-treatment-pseudomonas` — riesgo de Pseudomonas/resistentes
- `nac-r23-treatment-mrsa-combined` — riesgo de MRSA más otros riesgos
- `nac-r24-treatment-mrsa-only` — solo riesgo de MRSA
- `nac-r25-treatment-postviral` — contexto posviral/MRSA
- `nac-r26-adjust-to-results` — ajuste según prueba molecular o cultivo

## Evidencia y trazabilidad

Cada caja del árbol indica la página del protocolo de la que proviene. Al
hacer clic en una caja o flecha se muestra la cita textual (cuando existe) y
el identificador técnico con su huella de contenido, que permite rastrear el
elemento hasta el protocolo original. Los elementos con evidencia únicamente
visual (tabla de tratamiento, página 5) se marcan como «Evidencia visual —
requiere revisión manual».

## Cómo reportar correcciones

Use el formato de revisión del paquete (fase 7):
`review_template.json` junto con `review_instructions.md`. Para cada regla o
relación marque: Confirmar, Corregir (con la corrección propuesta), Rechazar,
Necesita aclaración o Diferir. Si falta una decisión o una rama en el árbol,
regístrela como contenido faltante. Sus decisiones se registran tal cual las
envía y no se modifican automáticamente.

Estado: **AWAITING_CLINICAL_REVIEW** · Aprobación clínica: **NO**.
