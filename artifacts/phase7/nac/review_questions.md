# Preguntas para el revisor clínico — Neumonía adquirida en comunidad (CT-PL-193 v9)

Esta vía de manejo fue generada con ayuda de inteligencia artificial a partir
del protocolo institucional. Pasó validación estructural y de trazabilidad,
pero **NO ha sido aprobada clínicamente**. Sus respuestas decidirán qué puede
convertirse en conocimiento clínico aprobado.

Marque cada pregunta como **correcta / incorrecta / requiere cambios / necesita
aclaración / diferir**. Para registrar sus decisiones use
`review_template.json` y siga `review_instructions.md`.

## 1. Diagnóstico por imagen

1. ¿La indicación de radiografía de tórax en pacientes con signos o síntomas
   respiratorios bajos está bien representada? (referencia técnica:
   `nac-r01-chest-radiograph`)
2. ¿Es correcto que un infiltrado de nueva aparición junto con un cuadro
   clínico compatible respalde el diagnóstico? (`nac-r02-diagnostic-support`)
3. ¿Debe repetirse la radiografía a las 48 horas cuando la radiografía inicial
   es normal pero la sospecha clínica de neumonía es alta?
   (`nac-r03-repeat-radiograph`)
4. ¿La tomografía de tórax queda correctamente restringida a: alta
   probabilidad clínica, radiografía no concluyente y prioridad diagnóstica o
   sospecha de complicación (neumonía necrosante, absceso, empiema tabicado)?
   (`nac-r04-ct-inconclusive`)
5. En neutropenia febril con síntomas respiratorios bajos, ¿es correcta la
   solicitud de tomografía simple en todos los pacientes?
   (`nac-r05-ct-neutropenia`)

## 2. Laboratorio y microbiología

6. ¿Hemoleucograma y nitrógeno ureico en todo paciente con sospecha de
   neumonía, para definir hospitalización, es lo correcto?
   (`nac-r06-basic-laboratory`)
7. Al hospitalizar, ¿se deben añadir PCR, creatinina, lactato y sodio; y en
   choque séptico/sepsis grave/falla orgánica múltiple, pruebas de
   coagulación, transaminasas, bilirrubinas y gases arteriales?
   (`nac-r07`, `nac-r08`, `nac-r09`)
8. **Hemocultivos.** La regla modelada es: paciente hospitalizado por
   neumonía Y (BUN > 30 mg/dL O PCR > 15 mg/dL O leucocitos > 15.000 O al
   menos DOS de: presión diastólica < 60 mmHg, frecuencia cardiaca > 120 lpm,
   frecuencia respiratoria > 30 rpm, dolor pleurítico). ¿Es esta la
   interpretación correcta del protocolo? ¿Deben tomarse antes de la primera
   dosis de antibiótico intravenoso y con dos frascos aerobios y uno
   anaerobio? (`nac-r11-blood-cultures`)
9. ¿Gram y cultivo de esputo en todo paciente con neumonía e indicación de
   hospitalización, con esputo inducido si no puede recolectarse
   espontáneamente? (`nac-r12`, `nac-r13`)
10. ¿La prueba molecular tipo FilmArray en todo paciente adulto con
    diagnóstico confirmado e indicación de hospitalización es la práctica
    institucional? (`nac-r14`, `nac-r15`, `nac-r16`)
11. ¿Todo derrame pleural unilateral de más de 1 cm, de presunto origen
    paraneumónico, debe llevarse a toracentesis diagnóstica con estudio
    citoquímico, LDH, proteínas, Gram y cultivo? (`nac-r17`, `nac-r10`)

## 3. Hospitalización y UCI/UCE

12. ¿Las indicaciones de hospitalización están bien representadas como
    alternativas independientes (descompensación de enfermedad de base,
    inmunosupresión, sospecha de gérmenes resistentes, intolerancia a la vía
    oral, sepsis o choque pulmonar, compromiso multilobar o derrame pleural,
    CURB-65 ≥ 2, factores sociales, requerimiento de oxígeno)?
    (`nac-r18-hospitalization`)
13. ¿La UCI/UCE es una decisión SEPARADA de la hospitalización, con
    indicaciones directas (insuficiencia respiratoria, choque séptico,
    lactato > 2, falla renal con terapia de reemplazo, falla orgánica
    multisistémica)? (`nac-r19-icu-direct`)
14. ¿Es correcta la segunda vía de ingreso a UCI/UCE: tres o más de los nueve
    criterios listados (BUN > 30, FR > 30, hipotensión que requiera líquidos
    agresivos, infiltrados multilobares, PaO2/FiO2 < 250, confusión,
    hipotermia, plaquetas < 100.000, leucocitos < 4.000)?
    (`nac-r20-icu-three-criteria`)
15. **Conflicto de fuentes:** la narrativa usa BUN > 30 mientras el
    flujograma de la página 6 muestra BUN > 20; además la estructura de
    criterios de UCI difiere entre narrativa y flujograma. ¿Cuál
    representación debe prevalecer en la vía clínica?

## 4. Tratamiento antibiótico (tabla de la página 5 — fuente visual)

16. La tabla de tratamiento se transcribió manualmente porque no tiene texto
    recuperable. Verifique fila por fila: contextos de riesgo (sin factores
    de riesgo; riesgo de Pseudomonas/enterobacterias resistentes; riesgo de
    MRSA; contexto posviral/MRSA), alternativas, dosis, intervalos y
    duración. (`nac-r21` a `nac-r25`, todos BLOQUEADOS)
17. ¿La activación de los factores de riesgo para MRSA, Pseudomonas y
    enterobacterias resistentes está completa o faltan criterios?
18. ¿Las notas al pie y las celdas combinadas de la tabla modifican la fila
    que parece que modifican?
19. ¿Es correcto ajustar siempre el tratamiento según la prueba molecular o
    el cultivo? (`nac-r26-adjust-to-results`, BLOQUEADO)

## 5. Egreso y seguimiento

20. Los criterios de egreso se modelaron como UN solo requisito conjunto:
    48 horas afebril, TAS > 90, FC < 100, FR < 24, SatO2 > 90% o PO2 > 60,
    tolerancia a la vía oral, comorbilidades compensadas, tratamiento
    ambulatorio asegurado y condiciones sociales adecuadas. ¿Debe leerse así
    (todos juntos) o algunos criterios son alternativas?
    (`nac-r27-discharge`)
21. ¿Al egreso se deben explicar los signos de recaída (fiebre, disnea, dolor
    torácico) y programar revisión con medicina interna a las 4 semanas?
    (`nac-r28`, `nac-r29`)

## 6. Preguntas generales sobre la vía

22. ¿La secuencia global (imagen → laboratorio → hospitalización →
    severidad/UCI → tratamiento → egreso → seguimiento) corresponde a la
    práctica del protocolo institucional?
23. ¿Falta algún paso, rama o excepción en la vía propuesta? Si es así,
    regístrelo como retroalimentación de contenido faltante.
24. ¿Alguna flecha o conexión entre decisiones no corresponde a la práctica
    clínica real?
