# Delta de la llamada con Tomás Reyes · 2026-11-20

Fuente única de este documento: `llamadas/2026-11-20-tomas.md` (minutos entre corchetes).
Estado contra el que se compara: `README.md`, `docs/contexto.md` y `docs/decisiones.md` (kickoff del 12-nov-2026).

No se edita `docs/decisiones.md`. Los cambios a decisiones se **proponen** aquí (sección 2) y se aplican por PR.

---

## 1. Decisiones nuevas

| ID propuesto | Decisión | Cita |
|---|---|---|
| N1 | **El score ordena, no decide.** El sistema nunca descarta a un candidato por sí solo; el reclutador decide. | [03:57] «Solo ordena. El reclutador decide. Nunca queremos que el sistema descarte a nadie solo.» |
| N2 | **Entradas del score:** el CV y la descripción de la vacante. | [02:14] «El CV y la descripción de la vacante.» |
| N3 | **El CV se manda completo al modelo**, sin recortar ni anonimizar. | [02:14] «mándale el CV completo al modelo. Todo, con nombre, con todo. Probamos con un proveedor recortando cosas y el score salía malísimo.» |
| N4 | **La elección del proveedor de modelo la decide Víctor.** | [02:14] «que lo haga el proveedor que funcione mejor: OpenAI, Anthropic, el que sea. Eso decídelo tú.» |
| N5 | **El score siempre va con su explicación.** Un número solo no se considera entregable. | [00:16] «Y que le diga por qué, ¿eh? Porque un numerito solo no le sirve a nadie; los reclutadores no le creen.» |
| N6 | **Hito de negocio: demo con Northstar el 15-ene-2027.** Si Match funciona con sus vacantes, aunque sea básico, se firma la renovación. | [04:53] «Tenemos una demo con Northstar el quince de enero. Si para entonces tenemos Match funcionando con sus vacantes, aunque sea básico, firmamos la renovación.» |
| N7 | **Alcance mínimo de esa demo:** abrir una vacante y ver los candidatos ordenados con score y explicación. El resto puede esperar. | [05:09] «Que un reclutador abra una vacante, vea los candidatos ordenados con su score y su porqué. Lo demás puede esperar.» |
| N8 | **La UI nunca se bloquea esperando al modelo.** | [01:53] «Lo que no puede pasar es que la página se trabe esperando.» |
| N9 | **El aislamiento multiempresa se implementa en un solo lugar del código y con test.** Acordado en la llamada por las dos partes. | [03:25] Víctor: «Eso va con test y en un solo lugar del código.» → [03:29] Tomás: «Eso.» |

---

## 2. Delta contra `docs/decisiones.md`

### 2.1 Qué CONTRADICE lo ya decidido

**🔴 N3 + N4 contra D3 — bloqueante.** Es el punto más grave de la llamada.

- D3 (vigente): «los CVs y los datos personales de los candidatos **no salen de la infraestructura de Criba**. Ningún tercero los procesa. Es un compromiso contractual con los clientes enterprise y un control de SOC 2.» — Kickoff 12-nov, Priya Shah.
- Llamada [02:14]: «mándale el CV completo al modelo. Todo, con nombre, con todo. […] que lo haga el proveedor que funcione mejor: OpenAI, Anthropic, el que sea.»

OpenAI y Anthropic son terceros fuera de la infraestructura de Criba. Mandarles el CV completo con nombre es exactamente lo que D3 prohíbe. No se puede cumplir N3 y D3 a la vez.

Además, Tomás no menciona D3 en ningún momento de la llamada, así que no está claro si está cambiando la decisión a propósito o si no la tenía presente. **No se implementa ninguna de las dos opciones hasta que Tomás y Priya Shah resuelvan.** Ver issue `01`.

### 2.2 Qué cambia (matiz sobre lo ya decidido)

| Decisión vigente | Cambio que trae la llamada | Cita |
|---|---|---|
| D5 (**Calendario**: arranque 1-dic-2026, ~20 h/semana) | No se cambia el arranque, pero se le agrega un hito duro externo: 15-ene-2027. Con arranque el 1-dic y 20 h/semana, son ~6 semanas de calendario ≈ **120 h** para la demo, navidades incluidas. Ver riesgo R1. | [04:53] «Tenemos una demo con Northstar el quince de enero.» |
| D4 (**Multiempresa**: aislamiento total, filtrar por `empresa_id`) | No cambia; se refuerza y se le pone consecuencia de negocio explícita y una forma de implementarlo (un solo lugar + test, N9). | [03:03] «Si un reclutador de Meridian llega a ver un candidato de Northstar, Northstar nos cancela el contrato ese mismo día, y es nuestro cliente más grande.» |
| D1 (**módulo dentro de la plataforma actual**) | Se confirma por el uso descrito: el reclutador abre la vacante que ya existe y ahí ve el orden. No hay producto aparte. | [00:55] «Abren la vacante, ven quién va arriba y le escriben.» |

### 2.3 Qué se agrega (temas nuevos, sin decisión previa)

1. **Explicación obligatoria del score** (N5) — no estaba en el kickoff.
2. **Proveedor de modelo externo** como pieza de arquitectura (N3/N4) — el kickoff no hablaba de modelos.
3. **Bilingüe es/en** como condición real de los datos y de los usuarios. [02:37] «Y los CVs llegan en los dos idiomas, ¿eh? Meridian tiene operación en Monterrey y en Dallas: la mitad de sus candidatos manda el CV en español, y sus reclutadores de Monterrey trabajan en español. Northstar, todo en inglés.»
4. **Uso principal desde el celular.** [00:55] «la mayoría ni se sienta en la compu: revisan todo desde el celular, entre entrevista y entrevista, en el coche, donde sea.»
5. **Costo por score** como restricción de producto. [04:21] «Que no se dispare, eso sí. Si alguien sube mil CVs de golpe, no quiero una factura de miles de dólares.»
6. **Ley de Nueva York sobre herramientas automatizadas de contratación.** [03:29] «Northstar tiene hospitales en Nueva York, y allá hay una ley sobre herramientas automatizadas para contratar. La ciento cuarenta y cuatro, creo.»
7. **Borrado de datos de un candidato a petición suya.** [04:35] «un candidato nos escribió furioso pidiendo que borráramos todos sus datos. Nos tardamos dos semanas en encontrar dónde estaba todo.»
8. **Volumen por vacante** como caso de carga concreto: 500+ candidatos en una sola vacante. [00:16] «Una vacante de enfermería de Northstar recibió quinientos y pico la semana pasada.»

---

## 3. Requisitos explícitos

| # | Requisito | Cita |
|---|---|---|
| RE1 | Para cada vacante, la plataforma ordena a los candidatos con un score de qué tanto encaja cada uno. | [00:16] «que para cada vacante la plataforma le ordene los candidatos, con un score de qué tanto encaja cada uno.» |
| RE2 | Cada score va con una explicación de por qué. | [00:16] «Y que le diga por qué, ¿eh?» |
| RE3 | Entradas: CV + descripción de la vacante. | [02:14] «El CV y la descripción de la vacante.» |
| RE4 | El CV se manda completo, con nombre, sin recortar. | [02:14] «mándale el CV completo al modelo. Todo, con nombre, con todo.» |
| RE5 | Ninguna empresa cliente ve candidatos de otra. Nunca. | [03:03] «que ningún cliente vea candidatos de otro. Nunca.» |
| RE6 | El score solo ordena; no descarta a nadie automáticamente. | [03:57] «Solo ordena. El reclutador decide.» |
| RE7 | La página no se traba esperando el score. | [01:53] «Lo que no puede pasar es que la página se trabe esperando.» |
| RE8 | Una vacante con 500 candidatos abre rápido. | [04:06] «Que abra rápido aunque tenga quinientos.» |
| RE9 | El costo no se dispara: 1.000 CVs de golpe no pueden generar una factura de miles de dólares. | [04:21] «Si alguien sube mil CVs de golpe, no quiero una factura de miles de dólares.» |
| RE10 | Para el 15-ene: un reclutador abre una vacante y ve los candidatos ordenados con score y explicación. | [05:09] «Que un reclutador abra una vacante, vea los candidatos ordenados con su score y su porqué.» |
| RE11 | Soportar CVs en español y en inglés. | [02:37] «los CVs llegan en los dos idiomas» |

Volumen de referencia confirmado (coincide con `docs/contexto.md`): [04:06] «Unos nueve mil candidatos nuevos al mes en toda la plataforma. Vacantes abiertas, unas seiscientas.»

---

## 4. Requisitos implícitos

Lo que Tomás no pidió como requisito, pero se desprende de lo que dijo. Cada uno es una lectura nuestra, no una afirmación suya.

| # | Requisito implícito | De dónde sale | Por qué se desprende |
|---|---|---|---|
| RI1 | **La interfaz tiene que funcionar bien en celular** (pantalla chica, red mala, de pie). Tomás lo contó como un hecho de uso, no como requisito. | [00:55] «la mayoría ni se sienta en la compu: revisan todo desde el celular […] en el coche, donde sea.» | Si el uso real es móvil, una vista pensada para escritorio no se usa. |
| RI2 | **Los scores se guardan, no se calculan al abrir la vacante.** | [01:53] «los reclutadores revisan en la mañana lo que llegó en la noche» + [04:06] «Que abra rápido aunque tenga quinientos» + [01:53] «que la página se trabe esperando» | 500 llamadas al modelo al abrir una página no cumple ninguna de las tres cosas. |
| RI3 | **Un CV se puntúa una sola vez por vacante** (cache / idempotencia), y re-puntuar es una acción explícita. | [04:21] «Que no se dispare» | Es la forma más directa de que el costo no crezca sin control. |
| RI4 | **Límite de ráfaga / cola con tope** para cargas masivas. | [04:21] «Si alguien sube mil CVs de golpe» | Tomás describe el escenario de abuso; contenerlo es parte del requisito. |
| RI5 | **La explicación tiene que citar evidencia concreta del CV**, no ser genérica. | [00:16] «un numerito solo no le sirve a nadie; los reclutadores no le creen» | El objetivo declarado es que el reclutador *crea*; eso exige trazabilidad al CV. |
| RI6 | **El idioma de la interfaz/explicación se decide por usuario, no por empresa.** | [02:37] «sus reclutadores de Monterrey trabajan en español» (dentro de Meridian, que también opera en Dallas) | Dentro de una misma empresa hay reclutadores en los dos idiomas. |
| RI7 | **Detectar el idioma del CV** y que el score no penalice al candidato por el idioma en que escribió. | [02:37] «la mitad de sus candidatos manda el CV en español» | Si el modelo compara un CV en español contra una vacante en inglés, el idioma puede contaminar el score. Riesgo de sesgo, ver R4. |
| RI8 | **Guardar, por cada score: entradas, salida, versión del prompt y versión del modelo.** | [03:29] «tienes que hacer una auditoría de sesgo» | Sin ese registro, una auditoría de sesgo (o de SOC 2) no se puede hacer a posteriori. |
| RI9 | **Match no crea copias nuevas de datos de candidato en lugares no inventariados**, y lo que cree se borra junto con el candidato. | [04:35] «Nos tardamos dos semanas en encontrar dónde estaba todo: el CV en un bucket, notas en otra tabla, un export que alguien se bajó… Un desastre.» | Tomás cerró el tema con [04:53] «eso ya pasó», pero Match agrega scores, explicaciones, prompts y logs: si no se inventarian, el próximo borrado tarda más de dos semanas. |
| RI10 | **Si el proveedor de modelo falla o tarda, la vacante sigue abriendo** (candidatos sin score, no error). | [01:53] «Lo que no puede pasar es que la página se trabe esperando.» | Una dependencia externa tiene caídas; el requisito de no bloquear aplica también a ese caso. |
| RI11 | **El acceso de staff de Criba a scores y explicaciones también queda auditado** (D6 ya lo exige para datos de candidato). | D6 + que el score es un dato derivado del CV | Un score explicado es información sobre el candidato. |
| RI12 | **Nada en la UI debe parecer un descarte automático** (ni ocultar, ni colapsar, ni filtrar por defecto a los de score bajo). | [03:57] «Nunca queremos que el sistema descarte a nadie solo.» | Esconder por defecto a los de abajo es un descarte de facto, y es justo lo que mira la ley de NY. |

---

## 5. Contradicciones

### C1 — CV completo a un proveedor externo vs. D3 (contra lo ya decidido) 🔴

- **Llamada [02:14]:** «mándale el CV completo al modelo. Todo, con nombre, con todo. […] que lo haga el proveedor que funcione mejor: OpenAI, Anthropic, el que sea.»
- **D3 (`docs/decisiones.md`, kickoff 12-nov, Priya Shah):** «los CVs y los datos personales de los candidatos **no salen de la infraestructura de Criba**. Ningún tercero los procesa.»

Incompatibles. Bloquea la decisión de arquitectura del módulo entero. Issue `01`.

### C2 — «En tiempo real» vs. «unos minutos» (dentro de la llamada)

- **[01:32]:** «Lo que sí es que tiene que ser instantáneo: llega el CV y ya tiene su score. En tiempo real.»
- **[01:53]:** «los reclutadores revisan en la mañana lo que llegó en la noche. Si se tarda unos minutos, nadie se va a dar cuenta.»

Tomás se corrige a sí mismo en la misma llamada. La segunda cita es la que trae la justificación de uso, pero no está confirmado cuál es el requisito. Issue `03`.

### C3 — Porcentaje 0-100 vs. semáforo (dentro de la llamada, sin resolver)

- **[01:32]:** «Un porcentaje, de cero a cien.»
- **[01:32]:** «Dana, la de customer success, dice que los clientes entienden mejor algo tipo semáforo: verde, amarillo, rojo. Las dos cosas tienen sentido.»

No hay decisión: Tomás deja las dos abiertas. Issue `04`.

### C4 — «Solo ordena» vs. el problema que se quiere resolver (tensión, relevante para la ley de NY)

- **[03:57]:** «Solo ordena. El reclutador decide. Nunca queremos que el sistema descarte a nadie solo.»
- **[00:55]:** «Abren la vacante, ven quién va arriba y le escriben.»

Si el reclutador contacta a los de arriba y no baja, el orden sí define quién queda fuera en la práctica, aunque el sistema no descarte a nadie. No es una contradicción de intención de Tomás, pero sí puede serlo para la ley 144 de NY, cuyo criterio es si la herramienta «asiste sustancialmente» la decisión. No lo resolvemos nosotros: issue `06`.

---

## 6. Preguntas abiertas para Tomás

Las que Tomás mismo pidió anotar están marcadas con ⭑.

| # | Pregunta | Por qué / cita |
|---|---|---|
| P1 | **¿Se cambia D3?** ¿Autorizan tú y Priya mandar CVs completos con nombre a un proveedor externo (OpenAI/Anthropic)? Si no, ¿la alternativa es un modelo que corra dentro de la infraestructura de Criba, aceptando peor calidad de score? Nada arranca sin esta respuesta. | C1. [02:14] vs D3 |
| P2 | ⭑ **¿Los hiring managers ven el score?** | [01:18] «¿deberían ver el score? No sé. Ahorita no lo hemos decidido. Ponlo en tu lista.» |
| P3 | ⭑ **¿En qué idioma va la explicación?** ¿Según el idioma del reclutador que la lee, o el del CV? | [02:55] «en el que lea el reclutador, supongo. No lo había pensado.» |
| P4 | ⭑ **¿Porcentaje, semáforo o los dos?** Dijiste que lo verías con Dana. | C3. [01:32] |
| P5 | ⭑ **¿Cuál es el techo de costo mensual** que acepta el CFO para Match? Sin un número no se puede dimensionar. | [04:21] «No tengo un número.» / [04:32] Víctor: «Lo dejo como pregunta: un techo mensual.» → [04:35] «Va.» |
| P6 | ⭑ **¿Qué aplica de la ley 144 de Nueva York?** Necesitamos la respuesta de tu abogado, no una interpretación nuestra. ¿Y la respuesta llega antes o después del 15-ene? | [03:29] «No sé bien qué aplica a nosotros. Lo vemos después, ¿no?» |
| P7 | **Latencia aceptable:** ¿segundos o minutos? (ver C2) ¿Hay un máximo a partir del cual sí es un problema? | C2. [01:32] vs [01:53] |
| P8 | **Para la demo del 15-ene: ¿cuántas vacantes y cuántos candidatos de Northstar** tienen que estar puntuados? ¿Toda su cuenta o un subconjunto? | [04:53] «Match funcionando con sus vacantes, aunque sea básico» — «sus vacantes» no está acotado |
| P9 | **¿Hay datos reales de Northstar con los que podamos probar la calidad del score** antes de la demo, y bajo qué condiciones? | RE10 + D3; sin datos no hay forma de saber si el score sirve |
| P10 | **¿El score se recalcula** cuando cambia la descripción de la vacante, o se queda con el valor del momento en que llegó el CV? | [01:32] «llega el CV y ya tiene su score» — no cubre el caso de que la vacante cambie |
| P11 | **¿Se avisa al candidato** de que su CV se puntúa de forma automatizada? Depende de P6, pero también es una decisión de producto. | [03:29] «avisarles a los candidatos» |
| P12 | **¿Qué pasa con los ~9.000 candidatos al mes de las otras ~38 empresas** durante diciembre y enero? ¿Match se enciende para todos o solo para Northstar hasta pasada la demo? Afecta directo al costo (P5). | [04:06] volumen + [04:53] foco en Northstar |

---

## 7. Riesgos

| # | Riesgo | Impacto | Cita / origen |
|---|---|---|---|
| R1 | **El calendario no cierra.** Arranque 1-dic (D5), demo 15-ene, 20 h/semana, con navidades en medio: ~120 h para un módulo nuevo con dependencia de un modelo externo. Y la decisión de arquitectura (P1) todavía no existe. | La renovación de Northstar depende de esa demo. | [04:53] + D5 |
| R2 | **Fuga entre empresas.** Un solo query sin `empresa_id` en el camino del score, del prompt o del log. | Tomás lo pone como pérdida del cliente más grande, el mismo día. Y es el primer punto de SOC 2. | [03:03] «Northstar nos cancela el contrato ese mismo día» + [03:29] «Tenemos la auditoría de SOC 2 en marzo y esto es lo primero que van a revisar.» |
| R3 | **Ruptura de un compromiso contractual (D3)** si se manda el CV a un tercero sin revisar antes los contratos enterprise y el alcance de SOC 2. | Peor que un bug: es incumplimiento de contrato frente a los clientes enterprise, en el trimestre previo a la auditoría. | C1 |
| R4 | **Sesgo del modelo y exposición legal.** Un score sobre un CV completo, con nombre, en dos idiomas, es un vector claro de sesgo por nombre, género, origen o idioma. | Ley 144 de NY (auditoría de sesgo + aviso), y Northstar opera justo en NY. | [02:14] «con nombre, con todo» + [03:29] + RI7 |
| R5 | **Costo sin techo.** 9.000 candidatos/mes × (vacantes a las que aplica cada uno) llamadas al modelo, sin número de referencia del CFO. | Puede matar el caso de negocio del módulo después de construirlo. | [04:21] «Mi CFO ya me preguntó. No tengo un número.» |
| R6 | **Dependencia de un proveedor externo** (caída, límites de tasa, cambio de precio, cambio de modelo → scores que no comparan). | La vacante es la pantalla principal de 120 reclutadores. | N4 + RI10 |
| R7 | **El score no convence a los reclutadores** y no lo usan: Tomás ya dice que hoy «no le creen» a un número. | El módulo se construye y no se adopta. | [00:16] «los reclutadores no le creen» |
| R8 | **Deuda de borrado de datos.** Match agrega scores, explicaciones y logs con texto de CV. Si no se inventaria desde el día uno, el próximo pedido de borrado tarda más de las dos semanas que ya tardó. | Riesgo de privacidad y de SOC 2. | [04:35] + RI9 |
| R9 | **Uso móvil no validado.** Nadie describió la vista móvil y es donde ocurre el trabajo real. | Se construye para escritorio y no se usa. | [00:55] + RI1 |
| R10 | **«Aunque sea básico» no está definido.** Riesgo de que lo mínimo para nosotros no sea lo mínimo para Northstar en la demo. | Se llega al 15-ene con algo que no sirve para firmar. | [04:53] + P8 |

---

## 8. Action items

Fechas: las que vienen de la llamada están citadas. Las marcadas *(propuesta)* las proponemos nosotros y necesitan que Tomás las confirme — no salen del transcript.

| # | Qué | Quién | Para cuándo | Issue |
|---|---|---|---|---|
| A1 | Mandar este delta + el correo de seguimiento a Tomás. | Víctor | Hoy, como se acordó: [05:16] «Hoy te mando un resumen con lo que entendí, lo que cambia y las preguntas.» | — |
| A2 | Resolver C1/P1: D3 vs. mandar el CV completo a un proveedor externo. Decisión de Tomás **con Priya Shah**; Víctor documenta las dos opciones y su costo en calidad y en tiempo. | Tomás + Priya (deciden); Víctor (documenta) | Antes del arranque del 1-dic (D5) *(propuesta: bloquea todo lo demás)* | `01` |
| A3 | Implementar el aislamiento multiempresa en un solo punto de acceso a datos, con tests que fallen si falta el `empresa_id`. | Víctor | Primera entrega después del arranque *(propuesta)* | `02` |
| A4 | Diseñar el scoring asíncrono: la vacante abre sin esperar al modelo, con scores ya guardados. | Víctor | Antes de la demo del 15-ene | `03` |
| A5 | Decidir el formato del score (porcentaje / semáforo / ambos), con Dana. | Tomás + Dana | *(propuesta: antes del 1-dic, define la UI)* | `04` |
| A6 | Dar un techo de costo mensual para Match (con el CFO). | Tomás | *(propuesta: antes del 1-dic)* | `05` |
| A7 | Consultar al abogado el alcance de la ley 144 de NY para Match y pasarnos la respuesta por escrito. | Tomás (con el abogado externo; Priya al tanto) | *(propuesta: antes del 15-ene — Northstar opera en NY y es el cliente de la demo)* | `06` |
| A8 | Responder si los hiring managers ven el score. | Tomás | *(propuesta: antes del 1-dic)* | `07` |
| A9 | Definir el comportamiento bilingüe: idioma de la explicación e idioma de la interfaz. | Tomás + Dana (deciden); Víctor (implementa) | *(propuesta: antes del 1-dic)* | `08` |
| A10 | Verificar el rendimiento de la vacante con 500+ candidatos. | Víctor | Antes de la demo del 15-ene | `09` |
| A11 | Inventariar dónde guarda Match datos derivados del candidato y cómo se borran. | Víctor (con Priya para el criterio de SOC 2) | *(propuesta: con la primera migración que cree tablas de Match)* | `10` |
| A12 | Acordar por escrito el alcance mínimo de la demo del 15-ene (cuántas vacantes, cuántos candidatos, qué datos). | Víctor (propone); Tomás (confirma) | *(propuesta: antes del 1-dic, para poder planear las ~120 h)* | `11` |
