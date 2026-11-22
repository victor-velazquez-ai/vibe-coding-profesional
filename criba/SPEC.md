# SPEC · Criba Match v1

Fuentes: `llamadas/2026-11-20-tomas.md` (minutos entre corchetes), `llamadas/2026-11-20-tomas-delta.md`, `docs/decisiones.md` (IDs D1-D6) y el **correo de Tomás Reyes del 21-nov-2026** (referencias `§n` = número de respuesta). Los cambios a decisiones que trae ese correo están propuestos en `llamadas/2026-11-21-cambios-decisiones.md` (IDs D3 modificado y D7-D23); esta spec **supone que ese PR se aprueba el 27-nov**. Si no se aprueba, no hay Match (§2).

## Objetivo

Dentro de la plataforma actual de Criba (D1), ordenar los candidatos de cada vacante por un **fit score de 0 a 100 acompañado de tres razones cortas**, para que un reclutador no revise 500 CVs uno por uno ([00:16]). El score **ordena, no decide**: nunca descarta a nadie ([03:57], D9). Hito: demo con Northstar el 15-ene-2027, de la que depende su renovación ([04:53]).

## Usuarios y permisos

| Rol | Qué puede hacer en Match |
|---|---|
| **Reclutador** (de una empresa con Match activo) | Ver la lista de su vacante ordenada por score, con score y tres razones. Cambiar al orden por fecha. Explicación en su idioma (`usuarios.idioma`, D11). |
| **Admin de empresa** | Lo del reclutador + botón «recalcular vacante», máximo 1 vez al día por vacante (D23). |
| **Hiring manager** | **Nada de Match en la v1** (D10). Ni score, ni razones, ni el orden por score. |
| **Staff de Criba** | Solo soporte, y cada acceso a scores y razones queda en `auditoria_accesos` (D6, D21). |
| **Candidato** | No ve nada. En la v1 no se le avisa de la puntuación automatizada (D20, riesgo abierto). |

Alcance de activación: **solo Northstar** hasta la demo (§8). Meridian no firmó el anexo de subprocesador, así que para Meridian Match está apagado (D7).

## Alcance: qué entra

1. **Score 0-100 + tres razones cortas** por par (candidato, vacante **a la que aplicó**) — no contra todas las vacantes abiertas (D13, §7).
2. **Entradas:** solo el texto del CV y la descripción de la vacante (D13, §21).
3. **Pseudonimización antes de salir de Criba:** se eliminan nombre, correo, teléfono, dirección, links a perfiles y fotos (D3 modificado, §1a).
4. **Scoring asíncrono y persistido:** la vacante nunca espera al modelo; los scores ya están guardados cuando se abre (D16, RI2).
5. **Orden por score por defecto**, candidatos sin score en sección «Pendientes de score» **arriba** con su fecha, y un clic para volver al orden por fecha (D9, §11).
6. **Estado «sin score» con motivo** cuando el CV no tiene texto legible o la vacante no tiene descripción. Nunca un cero (§15).
7. **Recálculo:** automático al subir un CV nuevo; manual por el admin para toda la vacante, 1/día (D23).
8. **Techo de costo** de 1.500 USD/mes con alerta al 80 %; al tope, los nuevos quedan pendientes (D12).
9. **Aislamiento multiempresa en un solo punto de acceso a datos**, con tests (D4, N9, issue `02`).
10. **Auditoría por score:** hash del CV, versión del prompt, versión del modelo, fecha. Sin texto del CV (D15).
11. **Borrado** de todo lo que Match derive de un candidato, en ≤7 días (D15).
12. **Carga inicial:** puntuar el histórico abierto de Northstar (~2.000 candidatos) y las tres vacantes de la demo (§4, §8).
13. **UI responsive** desde 360 px, Safari/Chrome en iPhone y Android recientes, con el estilo actual (D22).

## No-objetivos: qué NO entra en esta versión

Confirmados en §24: semáforo verde/amarillo/rojo; hiring managers; recálculo automático al cambiar la vacante; criterios de scoring por empresa; aviso al candidato; auditoría de sesgo automatizada; panel de métricas; re-puntuado masivo; Match para las otras ~39 empresas; modelo propio dentro de la infraestructura (§2); notas de entrevista o etapa como entrada (§21); vacantes fuera de Texas en la demo (§10); cualquier forma de descarte, ocultamiento o filtro por defecto de los candidatos con score bajo ([03:57], RI12).

## Criterios de aceptación

**CA1 · Aislamiento entre empresas** (D4, [03:03] — el requisito número uno)
Dado un reclutador de Meridian con sesión activa, y un candidato y un score que pertenecen a Northstar; cuando pide cualquier endpoint o vista de Match con esos IDs; entonces no ve ningún dato de Northstar (404, nunca un 200 parcial) y no aparece en ninguna lista, orden, export ni log suyo.
→ test: `tests/match/test_aislamiento.py` — recorre **todos** los endpoints de Match con sesión de otra empresa y exige 404; más un test que falla si alguna consulta de Match se construye fuera del único repositorio que inyecta `empresa_id`.

**CA2 · Nada identificable sale de Criba** (D3 modificado, §1a)
Dado un CV con nombre, correo, teléfono, dirección, link a perfil y foto; cuando se construye la petición al proveedor; entonces el cuerpo enviado no contiene ninguno de esos seis datos.
→ test: `tests/match/test_pseudonimizacion.py` — fixtures de CV en español y en inglés; asercia que ninguno de los valores de PII conocidos aparece en el payload; más un test que falla si el cliente del proveedor se invoca sin pasar por el pseudonimizador.

**CA3 · Sin anexo firmado no se llama al proveedor** (D7, §1c)
Dada una empresa sin Match activado o sin anexo de subprocesador (hoy, Meridian); cuando llega un CV nuevo suyo; entonces no se emite ninguna llamada al proveedor y no se crea ningún registro de Match.
→ test: `tests/match/test_activacion_por_empresa.py` — doble del proveedor que falla el test si recibe una sola llamada.

**CA4 · Abrir la vacante no llama al modelo** (D16, RE7, [01:53])
Dada una vacante con 500 candidatos; cuando un reclutador la abre; entonces se emiten **cero** llamadas al proveedor y la respuesta se construye solo con scores ya guardados.
→ test: `tests/match/test_vacante_no_espera.py` — doble del proveedor con contador; asercia `llamadas == 0`.

**CA5 · Rendimiento de apertura** (RE8, [04:06])
Dada esa misma vacante de 500 candidatos; cuando se mide el tiempo de respuesta del servidor en 50 peticiones; entonces el p95 es menor que 300 ms.
→ test: `tests/match/test_rendimiento_vacante.py` — siembra 500 candidatos con score, mide p95 del lado del servidor, falla por encima de 300 ms.

**CA6 · El proveedor caído no rompe la vacante** (RI10, [01:53])
Dado el proveedor devolviendo error o agotando el tiempo de espera; cuando llega un CV y luego se abre la vacante; entonces la página responde 200, el candidato aparece en «Pendientes de score» y no se muestra ningún error al reclutador.
→ test: `tests/match/test_fallo_proveedor.py` — doble que lanza timeout y error 500; verifica el estado del candidato y el 200 de la vista.

**CA7 · Latencia del score** (D16, §5)
Dado un CV que entra al sistema en condiciones nominales de carga; cuando se mide el tiempo desde su llegada hasta que su score está guardado; entonces el p95 es ≤ 10 min, y cualquier pendiente con más de 60 min de antigüedad dispara una alerta.
→ test: `tests/match/test_latencia_cola.py` — encola 200 CVs contra un proveedor simulado con la latencia medida en staging y asercia el p95; más test unitario de la alerta por antigüedad > 60 min.

**CA8 · Orden y pendientes** (D9, §11, RI12)
Dada una vacante con candidatos puntuados y candidatos sin score; cuando un reclutador la abre; entonces el orden por score es el de por defecto, los candidatos sin score salen en una sección «Pendientes de score» por encima de la lista con su fecha, ninguno queda oculto ni colapsado, y un clic devuelve el orden por fecha.
→ test: `tests/match/test_orden_y_pendientes.py` — asercia que el conteo de candidatos renderizados es igual al total, el orden por defecto, la posición de la sección y el cambio con un clic.

**CA9 · Recálculo** (D23, §12)
Dado un candidato con score en una vacante; cuando sube un CV nuevo, entonces su score se recalcula sin intervención. Cuando se edita la descripción de la vacante, entonces ningún score se recalcula solo; un admin puede pulsar «recalcular vacante» y un reclutador no puede; el segundo intento el mismo día se rechaza con un mensaje, no con un error.
→ test: `tests/match/test_recalculo.py` — tres casos: CV nuevo recalcula; edición de vacante no dispara nada; rol reclutador 403, admin dos veces en un día → segundo bloqueado.

**CA10 · Techo de costo** (D12, RE9, §6)
Dado un gasto acumulado del mes igual o mayor a 1.500 USD; cuando llegan CVs nuevos; entonces quedan en «pendientes», no se emite ninguna llamada al proveedor, y al cruzar el 80 % del techo se emitió una alerta.
→ test: `tests/match/test_techo_costo.py` — contador de gasto simulado en 79 %, 80 % y 100 %; asercia alerta en 80 % y cero llamadas en 100 %.

**CA11 · Idioma de la explicación** (D11, §14)
Dado un reclutador con `usuarios.idioma = 'es'` y un CV escrito en inglés; cuando ve el score; entonces las tres razones están en español. Y al revés con `'en'`.
→ test: `tests/match/test_idioma_explicacion.py` — verifica el idioma pedido en el prompt y el idioma del texto renderizado, en los dos sentidos.

**CA12 · El idioma del CV no cambia el score** (§15, RI7, R4)
Dado el mismo CV en español y en inglés, puntuado contra la misma vacante en inglés; cuando se comparan los dos scores; entonces difieren en **5 puntos o menos**.
→ test: `tests/match/test_paridad_idioma.py` — 10 pares de CV traducidos; falla si algún par supera los 5 puntos. *El umbral de 5 puntos es un supuesto nuestro: Tomás dijo «el mismo score» y eso no es verificable literalmente. Ver preguntas abiertas.*

**CA13 · Sin score, nunca un cero** (§15)
Dado un CV que es un PDF escaneado sin texto extraíble, o una vacante sin descripción; cuando se intenta puntuar; entonces el candidato queda en estado «sin score» con el motivo visible para el reclutador, y en ningún caso con score 0.
→ test: `tests/match/test_sin_score.py` — los dos casos; asercia estado, motivo y ausencia de un valor numérico.

**CA14 · Calidad del score** (D18, §3, §16)
Dadas las 10 vacantes cerradas y anonimizadas de Northstar, con el dato de a quién contactaron primero; cuando se puntúan todos sus candidatos; entonces en al menos 8 de las 10 ese candidato queda entre los 5 primeros.
→ test: `tests/calidad/test_gold_northstar.py` — ejecución manual (no en CI: cuesta dinero y usa datos del cliente), informe reproducible por vacante. Dana y dos reclutadoras de Northstar validan el resultado. **Si da menos de 8/10, la decisión vuelve a Tomás y Priya antes del 15-ene** (ver `llamadas/2026-11-21-cambios-decisiones.md` §4).

**CA15 · Auditoría de cada score** (D15, RI8, §17)
Dado un score recién calculado; cuando se inspecciona su registro de auditoría; entonces contiene hash del CV, versión del prompt, versión del modelo y fecha, y no contiene ningún fragmento del texto del CV.
→ test: `tests/match/test_auditoria_score.py` — asercia los cuatro campos y que ninguna frase de 8 palabras del CV de fixture aparece en el registro.

**CA16 · Borrado en 7 días** (D15, R8, [04:35])
Dado un candidato con scores, razones, registros de auditoría y entradas en la cola; cuando se ejecuta la petición de borrado; entonces no queda ningún dato suyo ni identificador que apunte a él en ninguna tabla o cola de Match, y el inventario de dónde vive cada dato está en el repo.
→ test: `tests/match/test_borrado_candidato.py` — crea, puntúa, borra y recorre todas las tablas de Match buscando el `candidato_id` y el hash; más un test que falla si una migración nueva de Match crea una tabla que no está en el inventario de borrado.

**CA17 · Acceso de staff auditado** (D6, D21, RI11, §18)
Dado un miembro del staff de Criba viendo el score y las razones de un candidato; cuando carga la vista; entonces queda una fila en `auditoria_accesos` con quién, qué candidato y cuándo.
→ test: `tests/match/test_auditoria_staff.py`.

**CA18 · Hiring manager no ve Match** (D10, §13)
Dado un hiring manager con acceso de solo lectura a una vacante; cuando la abre; entonces no hay score, ni razones, ni orden por score, ni sección de pendientes en la respuesta, y los endpoints de Match le devuelven 403.
→ test: `tests/match/test_hiring_manager.py`.

**CA19 · Móvil a 360 px** (D22, RI1, §19)
Dada la vista de vacante con 500 candidatos en un viewport de 360 px de ancho; cuando se renderiza; entonces no hay desbordamiento horizontal y score, razones y el control de orden son visibles y accionables.
→ test: `tests/match/test_movil_360.py` — Playwright a 360×640, asercia `scrollWidth <= clientWidth` y la visibilidad de los tres elementos.

**CA20 · Cobertura para la demo** (D17, §4, §8)
Dado el 15-ene-2027 y la cuenta de Northstar; cuando se consulta la cobertura; entonces las tres vacantes de Texas (enfermería ~500, administración ~120, TI ~60) y el histórico abierto (~2.000 candidatos) tienen el 100 % de sus candidatos con score o con un motivo de «sin score» registrado.
→ test: `tests/match/test_cobertura_demo.py` — consulta de cobertura que falla si queda algún candidato sin score y sin motivo.

## Privacidad

- **D3 modificado** (propuesto en `llamadas/2026-11-21-cambios-decisiones.md`, aprueba Priya Shah por PR): el CV sale de Criba solo pseudonimizado, solo hacia un proveedor con retención cero y sin entrenamiento, y solo para empresas que activaron Match y firmaron el anexo de subprocesador. Las tres condiciones son acumulativas.
- **Antes de producción**, Priya verifica por escrito la retención cero y el no-entrenamiento del proveedor elegido (§1b, §17). La elección del proveedor es de Víctor (N4) dentro de esa restricción.
- **Lo que se elimina antes de enviar:** nombre, correo, teléfono, dirección, links a perfiles, fotos (§1a).
- **Aislamiento multiempresa** en un único punto de acceso a datos, con tests que fallen si falta `empresa_id` (D4, N9). Un fallo aquí es un incidente de seguridad, no un bug ([03:03]).
- **Auditoría de cada score:** hash del CV, versión del prompt, versión del modelo. El texto del CV no se guarda en la auditoría (§17).
- **Borrado:** ≤7 días, con inventario en el repo de cada lugar donde Match guarda datos derivados del candidato (§17, RI9).
- **Acceso de staff de Criba:** auditado en `auditoria_accesos` (§18).
- **Ley 144 de Nueva York:** respuesta escrita del abogado el 10-dic-2026. Hasta entonces, y para la demo, solo vacantes de Texas. Aviso al candidato y auditoría de sesgo quedan fuera de la v1, como riesgo abierto y aceptado por Tomás (§10).

## Rendimiento (números medibles)

| Qué | Número | Cómo se verifica |
|---|---|---|
| Abrir vacante de 500 candidatos (servidor) | p95 < 300 ms, 0 llamadas al modelo | CA5, CA4 (test automático) |
| Página visible en celular, buena red | < 2 s | **Objetivo, no test automático** (medición manual antes de la demo) |
| CV recibido → score guardado | p95 ≤ 10 min | CA7 |
| Pendiente sin puntuar | alerta a los 60 min | CA7 |
| Ancho mínimo de pantalla | 360 px sin desbordamiento horizontal | CA19 |
| Costo mensual de toda la plataforma | techo 1.500 USD, alerta al 80 % | CA10 |
| «Recalcular vacante» | máx. 1/día/vacante | CA9 |
| Carga para la demo | 3 vacantes + ~2.000 candidatos del histórico, 100 % con score o motivo | CA20 |
| Volumen de referencia | ~9.000 candidatos/mes, ~600 vacantes abiertas en la plataforma; solo Northstar activo en la v1 | `docs/contexto.md`, [04:06], §8 |

## Preguntas que siguen abiertas

1. **¿5 puntos es la tolerancia correcta en CA12?** §15 dice «el mismo score» en español y en inglés, que no es verificable tal cual. El umbral de 5 puntos lo pusimos nosotros. Necesita el visto bueno de Tomás o de Dana.
2. **Pseudonimización dentro del cuerpo del CV.** §1a lista seis campos, pero un CV repite el nombre en el texto, nombra al empleador anterior, la universidad o la ciudad. ¿La limpieza es solo de los campos estructurados, o también del texto libre? Es la diferencia entre una regla simple y una tarea con falsos negativos. **Decide Priya.**
3. **¿La fila de auditoría del score sobrevive al borrado del candidato,** anonimizada? CA15 (guardar para poder auditar) y CA16 (borrar todo en 7 días) empujan en direcciones opuestas. **Decide Priya**, con el criterio de SOC 2.
4. **Si el abogado dice el 10-dic que la ley 144 sí aplica,** ¿qué pasa con la demo y con las vacantes de Northstar en Nueva York? Hoy el plan solo cubre «demo en Texas» (§10), no el día después.
5. **¿Cuándo firma Meridian el anexo?** Hasta entonces Match está apagado para ellos (D7) y la mitad de sus CVs en español son nuestro único caso real bilingüe — los fixtures de CA11 y CA12 saldrán de datos sintéticos.
6. **¿Cuándo nos llegan las 10 vacantes cerradas anonimizadas de Northstar?** Sin ellas no se puede ejecutar CA14, y CA14 es lo que detecta a tiempo que el CV recortado no alcanza. Es la dependencia externa más urgente.
7. **Score desactualizado:** si cambia la descripción de la vacante y nadie pulsa «recalcular» (D23), los scores quedan viejos. ¿Se marca en la UI como «calculado con una versión anterior de la vacante», o no se dice nada?
8. **«Tres razones cortas» (§9):** ¿límite de caracteres por razón? ¿Tienen que citar evidencia textual del CV (RI5), o basta una frase general? De esto depende que el reclutador crea el score ([00:16] «no le creen»).
9. **Cambio de versión del modelo:** cuando el proveedor cambie de modelo, los scores viejos dejan de ser comparables con los nuevos en la misma lista. ¿Se re-puntúa la vacante (costo) o se convive con scores de dos versiones (R6)?
10. **El techo de 1.500 USD/mes es «para toda la plataforma» (§6), pero en la v1 solo corre Northstar.** ¿Sigue siendo 1.500 cuando se enciendan las otras ~39 empresas, o ese número se revisa con el CFO antes?
11. **Métrica de producto (§23):** 60 % de las vacantes abiertas de Northstar usando el orden por score al menos una vez por semana, a 60 días. No es criterio de aceptación de la v1, pero hay que instrumentarlo desde el día uno para poder medirlo — ¿entra en la v1 o se acepta medirlo a mano?
