# Delta de la segunda llamada con Tomás Reyes · 2026-11-22

Fuente de las citas de este documento: `llamadas/2026-11-22-tomas-2.md` (minutos entre corchetes).
Estado contra el que se compara: `README.md`, `SPEC.md`, `docs/decisiones.md` (D1-D6),
`llamadas/2026-11-20-tomas-delta.md` (N1-N9, RE1-RE11, RI1-RI12, C1-C4, P1-P12, R1-R10, A1-A12),
`llamadas/2026-11-21-cambios-decisiones.md` (D3 modificado y D7-D23, **propuestos**, PR comprometido para el 27-nov),
`docs/decisiones-propuestas/2026-11-22-proveedor-y-vacante.md` (D24 propuesto), `PLAN.md`, `docs/fallas.md` y el código de `app/match/`.

No se edita `SPEC.md` ni `docs/decisiones.md`. Lo que cambia se **propone** aquí (sección 2) y se aplica por PR.
Las numeraciones nuevas continúan las del delta del 20-nov: **RE12+, RI13+, P13+, R11+, A13+**.

El incidente del cero **no** lleva issue: se trata por el camino del `RUNBOOK.md` (contener → entender → arreglar → verificar → postmortem) y su informe vive en `postmortems/`.

---

## 1. Prioridades, en el orden que fija la llamada

El orden no es nuestro: lo dicta Víctor en voz alta y Tomás lo confirma.

> **[02:38]** Víctor: «Te mando por escrito lo que entendí, con el orden: primero el cero, después estas dos.»
> **[02:44]** Tomás: «Perfecto. Lo del cero es lo urgente. Lo otro puede esperar a después de la demo.»

| # | Prioridad | Cita que la fija |
|---|---|---|
| **1** | **Contener el cero:** que en lugar de un cero se muestre «no disponible». | **[01:12]** Víctor: «Lo primero que hago es que en vez de un cero salga "no disponible", para que nadie confíe en un número que no es real.» → **[01:20]** Tomás: «Va, perfecto. Hazlo.» |
| **2** | **Entender la causa del cero**, después de contener. | **[01:12]** «Luego vemos la causa.» + **[02:49]** Víctor: «Te escribo en cuanto tenga contenido el problema.» |
| **3** | **Hiring managers ven el score y el porqué** en su vista de solo lectura. Es «la primera» de las dos cosas del piloto. | **[01:31]** «La primera: los hiring managers de Northstar […] ahora quieren verlo ellos también, en su vista de solo lectura.» |
| **4** | **Recálculo cuando se edita la vacante.** Es «la segunda». | **[02:08]** «La segunda: cuando un reclutador edita la vacante, por ejemplo le cambia los requisitos, el score se queda con la versión vieja. […] Quieren que se recalcule.» |

Las prioridades 3 y 4 quedan **después del 15-ene**: **[02:44]** «Lo otro puede esperar a después de la demo.» Es decir, `PLAN.md` §10, no la v1 — con la tensión de que la misma llamada dice **[01:58]** «Pero que se pueda, ¿eh?» (ver P16).

---

## 2. Delta contra `SPEC.md` y `docs/decisiones.md`

### 2.1 Qué CONTRADICE lo ya decidido

#### 🔴 C5 — Hiring managers ven score y razones, contra D10 y CA18

- **Llamada [01:31]:** «En el piloto vieron el score y el porqué en la pantalla de la reclutadora, y ahora quieren verlo ellos también, en su vista de solo lectura. Hoy no ven nada de Match, ¿verdad?»
- **Llamada [01:58]:** «Pero que se pueda, ¿eh? Aunque sea solo el score y el porqué, sin poder cambiar nada.»

Choca con cuatro cosas escritas, en este orden de dureza:

| Qué choca | Texto vigente o propuesto |
|---|---|
| **CA18** (`SPEC.md`, criterio de aceptación) | «Dado un hiring manager con acceso de solo lectura a una vacante; cuando la abre; entonces **no hay score, ni razones, ni orden por score, ni sección de pendientes** en la respuesta, y los endpoints de Match le devuelven 403.» |
| **D10** (propuesto en `llamadas/2026-11-21-cambios-decisiones.md` §3, §13 del correo) | «**Hiring managers:** en la v1 no ven nada de Match.» Ese mismo renglón dice que D10 «cierra P2 / issue `07`»: el pedido de ahora **reabre el issue `07`**, que se cerró con la respuesta contraria hace un día. |
| **`SPEC.md` · Usuarios y permisos** | «**Hiring manager** → **Nada de Match en la v1** (D10). Ni score, ni razones, ni el orden por score.» |
| **`SPEC.md` · No-objetivos** | «Confirmados en §24: […] hiring managers; […]» |

Y ya está implementado así: `app/match/services/listado.py:41` tiene el conjunto único `ROLES_QUE_VEN_MATCH = {RECLUTADOR, ADMIN_EMPRESA, STAFF_CRIBA}` con el comentario «el hiring manager no (CA18, D10)». No es un detalle de plantilla: es una línea que decide el permiso, y cambiarla cambia CA18.

**Lo que no se puede resolver aquí:** Tomás pide lo contrario de lo que él mismo decidió por correo el 21-nov, y la decisión tiene una precondición legal que él acepta en la llamada: **[01:44]** Víctor: «eso toca lo de la ley de Nueva York que te comentó tu abogado: si más gente usa el score para decidir, hay que revisarlo con él y con Priya» → **[01:58]** Tomás: «Sí, sí, lo hablo con Priya.» **No se implementa hasta que Tomás, Priya y el abogado respondan.** Issue `12`.

#### 🔴 C6 — Recalcular al editar la vacante, contra D23 y CA9(b)

- **Llamada [02:08]:** «cuando un reclutador edita la vacante, por ejemplo le cambia los requisitos, el score se queda con la versión vieja. Les pasó en el piloto: quitaron "inglés avanzado" y los scores no se movieron. Quieren que se recalcule.»

| Qué choca | Texto vigente o propuesto |
|---|---|
| **D23** (propuesto, `2026-11-21-cambios-decisiones.md` §3, §12 y §24 del correo) | «**Recálculo:** automático cuando el candidato sube un CV nuevo. Al cambiar la vacante **no** se recalcula solo: botón «recalcular vacante» para el admin de la empresa, máximo una vez al día por vacante.» |
| **CA9** (`SPEC.md`) | «Cuando se edita la descripción de la vacante, entonces **ningún score se recalcula solo**.» |
| **`SPEC.md` · No-objetivos** | «Confirmados en §24: […] recálculo automático al cambiar la vacante; […]» |
| **`PLAN.md` PR-23, test (b)** | «editar la descripción de la vacante → **cero recálculos y cero filas nuevas en `match_trabajos`**» |

Lo que la llamada **sí** aporta es el dato que faltaba: el comportamiento decidido (D23) le resultó incomprensible a un usuario real del piloto. Y Tomás se contradice dentro del mismo turno, que es la parte útil:

> **[02:23]** Víctor: «¿Todos los candidatos de esa vacante, cada vez que alguien la edite?»
> **[02:27]** Tomás: «Eh… pues sí, supongo. Aunque una vacante de esas tiene quinientos candidatos. Si cada vez que alguien corrige una coma se recalculan quinientos… mi CFO me mata. **Tú dime cómo.**»

O sea: pide el requisito y rechaza su costo en la misma frase, y delega el diseño. Choca además con **D12** (techo de 1.500 USD/mes, alerta al 80 %) y con **F31** de `docs/fallas.md` («el recálculo masivo consume el techo»). **No hay decisión; hay un encargo de propuesta.** Issue `13`.

#### 🟠 C7 — El cero no contradice la spec: **la incumple**

Esto no es un cambio de alcance, es un criterio de aceptación roto en el staging del piloto.

- **Llamada [00:18]:** «a algunos candidatos les sale cero desde ayer. Cero de cero a cien. Y no son malos candidatos: una reclutadora de Northstar encontró a una enfermera con doce años de experiencia hasta abajo de la lista, con cero.»
- **CA13** (`SPEC.md`): «**Sin score, nunca un cero** […] el candidato queda en estado «sin score» con el motivo visible para el reclutador, y **en ningún caso con score 0**.»
- **`docs/fallas.md` F8**, que lo predijo con nombre y apellido: «Si se guarda un 0, se viola CA13: un cero se lee como «no encaja»», y en su columna de detección: «**Un 0 guardado no dispara nada.**»

Estado del repo, sin interpretar la causa (eso es del postmortem): `app/match/services/scoring.py` guarda tal cual lo que devuelve el proveedor y **no valida la respuesta**; su propio docstring lo dice en la línea 80 («eso es «sin score con motivo» del alcance 6 y **lo decide PR-11**»). PR-11 es el paso que todavía no está. La contención que Tomás aprueba en **[01:20]** es, literalmente, PR-11 del plan, y el **texto exacto** que se muestra está declarado en `PLAN.md` PR-11 como «lado UI, PR-20» (ver P21: «no disponible» es la palabra de Víctor en la llamada, no un texto decidido con Dana).

### 2.2 Qué cambia (matiz sobre lo ya decidido)

| Decisión o criterio | Cambio que trae la llamada | Cita |
|---|---|---|
| **D17 / CA20** (demo 15-ene: tres vacantes de Texas de Northstar) y **`PLAN.md` §0 punto 1** («no se puntúa ningún dato real hasta que PR-18 y PR-19 estén mezclados») | Aparece una tercera posibilidad que ninguno de los dos documentos contempla: que la demo se haga **sobre el staging con candidatos de prueba**, que es donde ocurre el piloto. «Con esto tal cual» no dice si se refiere al alcance funcional o también al entorno y a los datos. Pregunta abierta P15, no un cambio aplicable. | **[00:06]** «Sus reclutadoras de Texas lo están probando en el staging, con candidatos de prueba, y **quieren que la demo del quince de enero sea con esto tal cual**.» |
| **C4 del delta del 20-nov** y **RI12** («nada en la UI debe parecer un descarte automático») | Dejan de ser lectura nuestra: ahora es el cliente quien lo dice, y lo dice como preocupación propia. Esto sube la relevancia de F39 (paginar = descarte de facto) y del criterio de la ley 144 (D20). | **[01:04]** «Pues el sistema no descarta a nadie, eso lo dejamos claro. **Pero si sale hasta abajo, nadie lo ve. Que para el caso es lo mismo.** Eso es lo que me preocupa.» |
| **D20** (ley 144: el abogado responde por escrito el 10-dic-2026) | La llamada habla del abogado en pasado, como si ya hubiera dicho algo. No sabemos si hay una respuesta previa al 10-dic o si es una forma de hablar. P18. | **[01:44]** Víctor: «eso toca lo de la ley de Nueva York **que te comentó tu abogado**». |
| **R7 / F1 / F17** (el reclutador no le cree al score) | El riesgo dejó de ser hipotético: una reclutadora del piloto ya vio un número falso en una candidata buena. | **[00:18]** «una enfermera con doce años de experiencia hasta abajo de la lista, con cero.» |

### 2.3 Qué se agrega (temas nuevos, sin decisión previa)

1. **Descripciones de vacante muy largas como entrada real.** **[00:41]** «Esa tiene una descripción larguísima: legal le metió todo el texto de cumplimiento, los requisitos de licencia de cada estado… es como de cuatro páginas.» Ni `SPEC.md` ni `docs/fallas.md` acotan el tamaño de la descripción: **F7** es el truncamiento silencioso **del CV** y **F22** es el caso opuesto (descripción de dos líneas). La descripción viaja al proveedor en el mismo pedido desde la decisión del 22-nov (`docs/decisiones-propuestas/2026-11-22-proveedor-y-vacante.md` §2), así que comparte el tope de tokens con el CV y hoy nadie mide eso. **Dato para el postmortem, y hueco nuevo del mapa de fallas.**
2. **Dana como canal de incidentes.** **[00:18]** «hoy en la mañana me escribe Dana, la de customer success». El síntoma lleva un día («desde ayer») y llega por el cliente, no por una alerta nuestra: es exactamente el punto ciego que F8 declara.
3. **El piloto existe como entorno con usuarios reales mirando.** **[00:06]** «Sus reclutadoras de Texas lo están probando en el staging, con candidatos de prueba.» No estaba en ningún documento del repo: `PLAN.md` trata el staging como el sitio donde se mide T1 con sintéticos, no como un piloto con reclutadoras de un cliente delante.
4. **Un caso de uso de la edición de vacante que nadie había descrito:** quitar un requisito para **ampliar** el embudo. **[02:08]** «quitaron "inglés avanzado" y los scores no se movieron.» D23 se decidió pensando en el costo del recálculo, no en este uso.

---

## 3. Requisitos explícitos

| # | Requisito | Cita |
|---|---|---|
| RE12 | Mientras no se conozca la causa, donde hoy sale un cero tiene que salir «no disponible»: nadie debe confiar en un número que no es real. | **[01:12]** «en vez de un cero salga "no disponible", para que nadie confíe en un número que no es real» → **[01:20]** «Va, perfecto. Hazlo.» |
| RE13 | Después de contener, encontrar la causa y reportarla por escrito. | **[01:12]** «Luego vemos la causa.» + **[02:49]** «Te escribo en cuanto tenga contenido el problema.» |
| RE14 | El hiring manager puede ver el score y el porqué en su vista de solo lectura, **sin poder cambiar nada**. | **[01:58]** «Aunque sea solo el score y el porqué, sin poder cambiar nada.» |
| RE15 | Cuando se edita la vacante —por ejemplo sus requisitos—, el score se recalcula. | **[02:08]** «Quieren que se recalcule.» |
| RE16 | Ese recálculo no puede costar 500 scores cada vez que alguien corrige una coma. | **[02:27]** «Si cada vez que alguien corrige una coma se recalculan quinientos… mi CFO me mata.» |
| RE17 | El **cómo** del recálculo lo propone Víctor. | **[02:27]** «Tú dime cómo.» |
| RE18 | Informe escrito de la llamada, con el orden de prioridades. | **[02:38]** «Te mando por escrito lo que entendí, con el orden: primero el cero, después estas dos.» |
| RE19 | Los dos pedidos del piloto van **después** de la demo del 15-ene. | **[02:44]** «Lo del cero es lo urgente. Lo otro puede esperar a después de la demo.» |
| RE20 | La demo del 15-ene se hace con lo que las reclutadoras están probando hoy. | **[00:06]** «quieren que la demo del quince de enero sea con esto tal cual» |

---

## 4. Requisitos implícitos

Lectura nuestra, no afirmaciones de Tomás.

| # | Requisito implícito | De dónde sale | Por qué se desprende |
|---|---|---|---|
| RI13 | **Un candidato sin score no puede terminar al final de la lista.** El estado «no disponible» necesita además una posición visible, no solo un texto. | **[00:18]** «hasta abajo de la lista, con cero» + **[01:04]** «si sale hasta abajo, nadie lo ve» | Cambiar el 0 por un texto y dejar la fila al final no resuelve lo que preocupa a Tomás. Es lo que CA8 ya pide («Pendientes de score» **arriba**) y lo que PR-20 implementa. |
| RI14 | **Nos tenemos que enterar nosotros:** alguna señal sobre la distribución de scores (ceros en masa, caída brusca) antes de que lo reporte el cliente. | **[00:18]** «les sale cero **desde ayer**» (lo reporta Dana) | F8 lo dice en su columna de detección: «un 0 guardado no dispara nada». La alerta de CA7 cubre pendientes, no scores malos guardados. |
| RI15 | **Las descripciones de vacante largas son dato real y no pueden degradar el score en silencio**, ni por truncamiento ni por dilución. | **[00:41]** «es como de cuatro páginas» | Es legal de Northstar quien mete ese texto: va a volver a pasar, y la vacante de la queja es una de las tres de la demo (enfermería en Texas). |
| RI16 | **El texto que sustituye al cero va en los dos idiomas** (`usuarios.idioma`, D11/CA11). | **[01:12]** «que […] salga "no disponible"» + D11 | Todo lo que ve el reclutador sale en su idioma; un motivo fijo en español rompe CA11 para Northstar, que trabaja en inglés. |
| RI17 | **La corrección se verifica en el staging del piloto**, que es donde las reclutadoras lo están viendo, no solo en local. | **[00:06]** «lo están probando en el staging» | Si la contención no llega ahí, para Tomás no pasó nada. `RUNBOOK.md` pide verificar «otra vez, después del arreglo». |
| RI18 | **Los ceros ya guardados hay que corregirlos**, no solo dejar de mostrarlos: re-encolar esos pares. | **[01:12]** «para que nadie confíe en un número que no es real» | Un score guardado sigue ordenando la lista aunque la celda muestre otra cosa. |
| RI19 | **El recálculo por edición necesita saber qué cambió** en la vacante: comparar la versión del texto con la que se usó al puntuar. | **[02:27]** «cada vez que alguien corrige una coma» | Distinguir «corrigió una coma» de «quitó inglés avanzado» exige versionar la descripción. Hoy la clave de idempotencia **no** la incluye (ADR-001 §Decisión 3, pregunta abierta 12 de `PLAN.md`, F18). |
| RI20 | **Si el hiring manager ve score y razones, ese acceso deja rastro y no habilita nada más.** | **[01:58]** «sin poder cambiar nada» + D6/D21 | Las razones citan contenido del CV (RI5): ampliar quién las lee amplía qué puede leer ese rol, que es lo que el issue `07` ya advertía. |
| RI21 | **El piloto necesita que le digan qué pasó.** Las reclutadoras vieron números falsos durante un día. | **[00:18]** reporte vía Dana + **[01:04]** «Eso es lo que me preocupa» | La confianza en el score es el requisito de adopción (R7, F17); un arreglo silencioso no la recupera. |

---

## 5. Preguntas abiertas

Las que la llamada asigna a alguien distinto de Tomás van marcadas con **→ para quién**.

| # | Pregunta | Para quién | Por qué / cita |
|---|---|---|---|
| P13 | **¿El cero sale en todos los candidatos o solo en las vacantes nuevas?** Sin el alcance real no se puede acotar el impacto ni saber a quién avisar. | **Dana** (la llamada se lo atribuye) | **[00:38]** Víctor: «¿A todos los candidatos o solo en algunas vacantes?» → **[00:41]** Tomás: «**No sé bien.** Dana dice que parece que es en las vacantes nuevas.» |
| P14 | **¿Qué versión corre el staging del piloto?** «Hasta abajo de la lista» describe un orden por score, y en `main` el listado ordena **por fecha** (`app/match/services/listado.py`, `ORDEN_POR_FECHA`; el orden por score es PR-20, pendiente). O el staging lleva algo que `main` no tiene, o «hasta abajo» significa otra cosa. | interno (Víctor) | **[00:18]** «hasta abajo de la lista, con cero» contra el código de `main` |
| P15 | **¿«Con esto tal cual» incluye el entorno y los datos?** ¿La demo del 15-ene es en el staging con candidatos de prueba, o en la cuenta real de Northstar? Afecta a D17, CA20 (100 % de cobertura de las tres vacantes de Texas) y a `PLAN.md` §0 punto 1. | Tomás + Dana | **[00:06]** «quieren que la demo del quince de enero sea con esto tal cual» |
| P16 | **Hiring managers: ¿v1 o después de la demo?** La llamada dice las dos cosas: «que se pueda, ¿eh?» y «puede esperar a después de la demo». | Tomás | **[01:58]** vs **[02:44]** |
| P17 | **¿Qué ve exactamente el hiring manager?** ¿Score y razones solamente, o también el orden por score y la sección «Pendientes de score»? CA18 nombra las cuatro cosas por separado. | Tomás (con Dana) | **[01:58]** «Aunque sea solo el score y el porqué» — «aunque sea solo» no dice si es un mínimo o un límite |
| P18 | **¿Qué dijo ya el abogado, y la respuesta escrita sigue siendo el 10-dic?** ¿Cambia su análisis si el score lo ven también los hiring managers («si más gente usa el score para decidir»)? | Tomás + el abogado externo, **Priya al tanto** | **[01:44]** «la ley de Nueva York que te comentó tu abogado» + **[01:58]** «lo hablo con Priya», contra D20 |
| P19 | **¿Qué cambios de la vacante disparan recálculo, quién lo autoriza y contra qué presupuesto?** ¿Se mantiene el límite de 1/día por vacante de D23? ¿El techo de 1.500 USD (D12) se revisa o el recálculo se paga con el mismo? | Tomás + su CFO | **[02:27]** «mi CFO me mata. Tú dime cómo.» |
| P20 | **Mientras no se recalcule, ¿se le dice al reclutador que el score es de una versión anterior de la vacante?** Es la pregunta abierta 7 de `SPEC.md` y F18, y el piloto acaba de tropezar con ella. | Tomás + Dana | **[02:08]** «el score se queda con la versión vieja» |
| P21 | **¿Cuál es el texto exacto, en español y en inglés?** «No disponible» es la palabra de Víctor en la llamada; CA13 pide «el motivo visible», y PR-11 deja el texto para el lado UI. Un motivo técnico **no** puede atribuirle nada al candidato. | Dana (copy) + Tomás | **[01:12]** «que […] salga "no disponible"» |
| P22 | **¿Qué se hace con los ceros ya guardados y ya vistos?** ¿Se re-encolan esos pares, y se le cuenta al piloto qué pasó? | Víctor propone; Tomás y Dana comunican | **[01:12]** «nadie confíe en un número que no es real» + RI18, RI21 |
| P23 | **¿Hay un tamaño máximo razonable para la descripción de la vacante?** La de cuatro páginas es de legal de Northstar, no un error del usuario. | Tomás (con Dana y legal de Northstar) | **[00:41]** «legal le metió todo el texto de cumplimiento […] es como de cuatro páginas» |

---

## 6. Riesgos

| # | Riesgo | Impacto | Cita / origen |
|---|---|---|---|
| R11 | **El piloto ya perdió confianza en el número.** Una reclutadora encontró una buena candidata con cero. Y la demo que decide la renovación es, por pedido del cliente, «esto tal cual». | Es R7 y F17 materializados, con usuarios reales, a ocho semanas de la demo. | **[00:18]** + **[00:06]** |
| R12 | **Descarte de facto, ahora dicho por el cliente.** El orden decide quién se ve; nadie mira abajo. | Es el criterio que mira la ley 144 («asiste sustancialmente»), con la respuesta del abogado pendiente al 10-dic (D20) y Northstar operando en NY. Agravado si el score lo ven más roles (C5). | **[01:04]** «si sale hasta abajo, nadie lo ve. Que para el caso es lo mismo» + C4 del delta anterior, RI12, F39 |
| R13 | **Contener sin entender.** Cambiar el 0 por «no disponible» quita el síntoma más visible; si la causa degrada scores sin llevarlos a 0 (por ejemplo truncamiento, F7, con la descripción de cuatro páginas en el mismo pedido), quedan candidatos con scores bajos **plausibles** que nadie detectará. | Un arreglo que cierra el ticket y deja el defecto. `RUNBOOK.md` lo prevé: contener **y** entender. | **[01:12]** «Luego vemos la causa» + F7, F40 |
| R14 | **El recálculo por edición revienta el techo.** 500 candidatos × cada edición, en una plataforma con ~600 vacantes abiertas, contra 1.500 USD/mes (D12). | Mata el caso de negocio o la vacante queda sin recalcular en el peor momento. Tomás ya lo dijo: «mi CFO me mata». | **[02:27]** + D12, F31 |
| R15 | **Alcance que crece antes de la demo.** La cuenta de `PLAN.md` §7 ya estaba al límite con ~120 h y PR-11 → PR-26 pendientes; ahora entran un incidente con postmortem y dos pedidos nuevos. | R1 del delta anterior, peor. Si los dos pedidos se cuelan en la v1, algo del camino de la demo no se entrega. | **[01:20]** «dos cosas que me pidieron en el piloto» + `PLAN.md` §7 |
| R16 | **Tocar permisos a última hora.** Habilitar Match para un rol que hoy está excluido en un solo punto (`ROLES_QUE_VEN_MATCH`) es el tipo de cambio que se hace rápido y deja una vista sin el filtro de siempre. | Un fallo aquí es incidente de seguridad, no bug (D4, CA1, F4, F41), con SOC 2 en marzo. | C5 + `app/match/services/listado.py` |
| R17 | **No tenemos detección propia.** Un día entero de ceros y la señal llegó por el cliente. | El próximo defecto puede no traer una Dana que escriba. | **[00:18]** «desde ayer» + F8 (detección) |
| R18 | **Piloto en staging con reclutadoras de un cliente delante.** `PLAN.md` (regla 1.7 y §0 punto 3) sostiene el staging sobre datos **solo sintéticos**; hoy Tomás dice «con candidatos de prueba», y eso hay que mantenerlo verificado, no supuesto. | Si entrara un CV real al staging del piloto, es un asunto de privacidad con Priya, no un bug. | **[00:06]** «en el staging, con candidatos de prueba» + `PLAN.md` §0 punto 3, hecho 9 de PR-01 |

---

## 7. Action items

Fechas: las que salen de la llamada van citadas. Las marcadas *(propuesta)* las proponemos nosotros y necesitan que Tomás las confirme.

| # | Qué | Quién | Para cuándo | Issue |
|---|---|---|---|---|
| A13 | Mandar este delta por escrito, con el orden de prioridades de la sección 1. | Víctor | **Hoy, 22-nov** — **[02:38]** «Te mando por escrito lo que entendí, con el orden» | — |
| A14 | **Contención del cero:** ningún camino escribe `score = 0`; en su lugar, estado sin score con motivo visible en los dos idiomas, y verificado en el staging del piloto. Es PR-11 del plan, adelantado por el incidente. | Víctor | **Urgente** — **[02:44]** «Lo del cero es lo urgente» | — (incidente) |
| A15 | **Causa raíz y postmortem** según `RUNBOOK.md` (dentro de 48 h, sin culpables), incluyendo la medición de cuántas descripciones y CVs superan el tope de tokens (la que PR-11 ya pedía para F7). | Víctor | **[01:12]** «Luego vemos la causa» + **[02:49]** «en cuanto tenga contenido el problema» | — (incidente) |
| A16 | Confirmar con Dana el alcance del síntoma (P13) y la lista de candidatos afectados. | Dana (responde); Víctor (pregunta) | *(propuesta: antes de cerrar el postmortem)* | — |
| A17 | Decidir qué se hace con los ceros ya guardados y qué se le dice al piloto. | Víctor (propone); Tomás y Dana (comunican) | *(propuesta: con la contención, no después)* | — |
| A18 | Hablar con Priya —y con el abogado— sobre que los hiring managers vean score y razones, antes de implementarlo. | Tomás (con Priya y el abogado externo) | **[01:58]** «lo hablo con Priya» · *(propuesta: junto con la respuesta de D20, 10-dic-2026)* | `12` |
| A19 | Responder P16 y P17: si los hiring managers entran en la v1 o después de la demo, y qué ven exactamente. Propuesta de cambio a D10 por PR. | Tomás (decide); Víctor (documenta) | *(propuesta: después del 15-ene, salvo que Tomás lo suba de prioridad — **[02:44]** «puede esperar a después de la demo»)* | `12` |
| A20 | Proponer por escrito el **cómo** del recálculo al editar la vacante, con su costo estimado contra D12 y las opciones que no requieren recalcular 500 candidatos por coma. | Víctor (propone); Tomás con su CFO (deciden) | **[02:27]** «Tú dime cómo» · *(propuesta: después de la demo)* | `13` |
| A21 | Aclarar P15: entorno y datos de la demo del 15-ene («con esto tal cual» vs. D17/CA20 y `PLAN.md` §0). | Tomás y Dana (responden); Víctor (propone el acuerdo escrito) | *(propuesta: antes del 1-dic, es precondición de la planificación)* | `11` (ya existe) |
| A22 | Decidir si entra una señal propia de calidad del score (distribución, ceros en masa) y a quién avisa. | Víctor (propone); Tomás (acepta el alcance) | *(propuesta: con el postmortem, como acción de prevención)* | — |
