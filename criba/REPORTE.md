# Reporte de Criba Match · 26-nov-2026

Para **Tomás Reyes** (CTO de Criba) y como registro de lo construido. Fecha de corte: **26-nov-2026**, rama `reporte/s7`, un commit por delante de `main` después del merge del PR #21 (`docs/costos.md`).

Cada afirmación lleva al lado el archivo, el comando con su salida, el PR o el issue que la prueba. Lo que no se pudo comprobar está escrito como **pregunta abierta**, no como hecho. Todas las rutas son relativas a la raíz de este repositorio.

---

## 1 · Resumen ejecutivo

1. **Existe el esqueleto completo y la mitad riesgosa de Match:** aislamiento multiempresa, pseudonimización, activación por empresa, cola con proveedor y el cliente real del modelo — **231 tests, 230 en verde y 1 `xfail` declarado** (§3.1), sobre una **réplica mínima** de la plataforma de Criba, no sobre la plataforma real (`README.md` §«La réplica de la plataforma»).
2. **No existe todavía nada de lo que el reclutador ve:** no hay orden por score, ni sección «Pendientes de score», ni las tres razones en pantalla — lo confirmó la QA de caja negra contra `SPEC.md` (`qa/reportes/2026-11-22-frontend.md` BUG-1 y BUG-2) y está en el plan como PR-20 (§6).
3. **De los 20 criterios de aceptación, 7 tienen test automático en verde hoy** (CA1, CA2, CA3, CA4, CA18 completos; CA5 y CA19 con la mitad medida); los 13 restantes están en pasos no construidos (§2, §6).
4. **El arranque formal es el 1-dic-2026** (D5) y la demo con Northstar el **15-ene-2027**: todo lo de este reporte es trabajo previo al arranque, con el histórico de Northstar ya fuera de la v1 por decisión aceptada por correo el 22-nov (`PLAN.md` §0).
5. **Qué decide Tomás:** las dos respuestas de Priya y la pregunta del idioma, que **vencen el 12-dic-2026** y bloquean puntuar datos reales; la fecha de las 10 vacantes cerradas, sin la cual CA14 no se puede ejecutar; y quién atiende la alerta de pendientes >60 min (§4.2).

---

## 2 · Qué se construyó

Un PR del plan = tres sesiones (escritor de tests → constructor → revisor adversarial), con el merge hecho por un humano (`CLAUDE.md`). Los cuerpos de PR están en `docs/prs/`.

| Feature entregada | PR | Criterio de `SPEC.md` | Evidencia (archivo · tests) |
|---|---|---|---|
| Andamio del módulo, base de test por transacción y CI | PR-01 · `docs/prs/PR-01.md` | — (habilita todo) | commit `ec796c6`; `tests/conftest.py` |
| Cuatro tablas de Match + inventario de borrado en la misma migración | PR-02 · `docs/prs/PR-02.md` | **CA16, segunda mitad** | `migrations/versions/0001_match_inicial.py`, `docs/inventario-borrado.md`, `app/match/borrado/inventario.py` · `tests/match/test_inventario_migraciones.py` (8) |
| Dos empresas (Northstar activa, Meridian sin anexo), 4 roles, doble del proveedor con contador | PR-03 · `docs/prs/PR-03.md` | CA1, CA3, CA4, CA6 | `tests/match/conftest.py`, `tests/dobles/proveedor.py` · `tests/match/test_fixtures.py` (12) |
| Punto único de acceso a datos: `empresa_id` del contexto + enumeración que falla si una consulta nace fuera | PR-04 · `docs/prs/PR-04.md` | **CA1** | `app/match/repositories/` · `tests/match/test_aislamiento.py` (12) |
| Vista de vacante con auth, rol y aislamiento: 404 a otra empresa, 403 al hiring manager, 0 llamadas al abrir | PR-05 · `docs/prs/PR-05.md` | **CA1, CA3, CA4, CA18** | `app/match/services/listado.py`, `app/match/routers/vacante.py` · `test_vacante_no_espera.py` (4), `test_hiring_manager.py` (3) |
| Camino de escritura: CV → cola → MOCK → score guardado → visible | PR-06 · `docs/prs/PR-06.md` | alcances 1, 4 y 7; CA9(a), CA13, CA20 | `app/match/cola/`, `app/match/services/scoring.py` · `tests/match/test_camino_escritura.py` (5) |
| E2E de humo: cuatro guiones con Chromium y servidor propio | PR-07 · `docs/prs/PR-07.md` | CA1, CA4, CA9(a), CA18 | `tests/e2e/test_humo.py` (4) |
| Frontera de pseudonimización: tipo con constructor privado, campos **y** texto libre | PR-08 · **#6** · `docs/prs/PR-08.md` | **CA2** | `app/match/proveedor/payload.py`, `app/match/services/pseudonimizador.py` · `test_pseudonimizacion.py` (23, 1 `xfail`) |
| Activación por empresa en los dos caminos (`encolar` y el ejecutor), una sola regla | PR-10 · **#9** · `docs/prs/PR-10.md` | **CA3** (D7) | `app/match/repositories/match_repo.py::empresa_activada` · `test_activacion_por_empresa.py` (8) |
| Cliente real del proveedor (`claude -p` por subproceso), timeout, tope de gasto por llamada, prohibición de registrar cuerpos | PR-09 · **#10** · `docs/prs/PR-09.md` | CA2, CA3, CA7 (timeout), CA15 (parcial) | `app/match/proveedor/cliente.py` · `test_cliente_proveedor.py` (14), `test_salida_del_cli.py` (15), `test_invocacion_endurecida.py` (3), `test_logs_sin_cv.py` (4), `test_descripcion_de_vacante.py` (5) |
| Arnés de evals del fit score: 12 casos sintéticos, k intentos, 4 dimensiones | **#12 → #15** · `docs/prs/evals-fit-score.md` | antecesor de **CA14** | `evals/` · `tests/evals/` (39) |
| Tres hallazgos de QA arreglados, cada uno con su E2E primero | PR-QA-E2E · **#20** · `docs/prs/PR-QA-E2E.md` | **CA19**, CA1, issue #16 | `app/static/criba.css`, `app/plataforma/sesion.py` · `tests/e2e/test_qa_*.py` (9), `tests/plataforma/test_ruta_interna.py` (15) |
| La lista de 500 sin el texto del CV, editor aparte por HTMX y respuesta comprimida | PR-PERF-1 · **#21** · `docs/prs/PR-PERF-1.md` | **CA5** (bytes y p95) | `app/match/services/listado.py`, `app/fabrica.py` · `test_lista_sin_cv_texto.py` (5), `test_compresion.py` (2), `test_consulta_de_la_lista_sin_cv_texto.py` (1), `test_tiene_cv_coincide_con_el_modelo.py` (1) |
| Estación de QA agéntica: dos roles, mapa de rutas, entorno reproducible | **#19** · `qa/README.md` | — (herramienta) | `qa/rutas.py`, `qa/preparar.py`, `.claude/agents/` |

**Una advertencia sobre la trazabilidad de PR-01 a PR-07:** sus cuerpos de PR están en `docs/prs/`, pero en **este** repositorio entraron como **un solo commit de instantánea**, `ec796c6` («S6 · criba-base: réplica de la plataforma, Etapa 0 aprobada al 95 % y construida (PR-01 a PR-07)»). No hay siete PR de GitHub que revisar uno por uno: vinieron del repositorio `criba-base`. Los PR con número de GitHub verificable son **#2, #4, #5, #6, #8, #9, #10, #12, #13, #14, #15, #19, #20, #21** (`gh pr list --state all`), lo que incluye el PR auxiliar **#8** («herramientas: auditoría de PII para el PR-08»).

**Cobertura de criterios, tal como está hoy:**

| Estado | Criterios |
|---|---|
| Con test automático en verde | **CA1, CA2** (menos el `xfail`), **CA3, CA4, CA18** |
| Parcial, con la mitad medida y la mitad en un paso pendiente | **CA5** (p95 medido en §3.5; el guardia de consulta única y T1 son PR-21), **CA9** (solo (a): el CV nuevo recalcula), **CA13** (el camino no devuelve cero; el motivo visible es PR-20), **CA16** (inventario y su test por migración; el borrado es PR-18), **CA19** (no desborda a 360 px; razones largas es PR-25), **CA20** (la consulta es PR-16) |
| Sin construir | **CA6, CA7, CA8, CA10, CA11, CA12, CA14, CA15, CA17** |

---

## 3 · Evidencia

### 3.1 · Tests — corrida real del 26-nov-2026

```
$ uv run python -m poethepoet check
Poe => python -m ruff check .
All checks passed!
Poe => python -m ruff format --check .
172 files already formatted
Poe => python -m pytest
........................................................................ [ 31%]
........................................................................ [ 62%]
....................x................................................... [ 93%]
...............                                                          [100%]
230 passed, 1 xfailed, 1 warning in 41.17s
[exited with code 0]
```

Reparto por directorio (`uv run python -m pytest --collect-only -q`, misma máquina y misma fecha): `tests/match/` **162**, `tests/evals/` **39**, `tests/plataforma/` **15**, `tests/e2e/` **14**, `tests/test_guardia_del_cli.py` **1** → **231**, que son los 230 verdes más el `xfail`.

**El único `xfail`, con su razón y su dueño:** `tests/match/test_pseudonimizacion.py::test_el_empleador_la_universidad_y_la_ciudad_no_declarada_tambien_salen`, `strict=True` — «pregunta abierta 2 de `SPEC.md`: §1a no nombra el empleador anterior, la universidad ni la ciudad no declarada… **Decide Priya**, antes del 12-dic-2026». No es un test apagado para que el verde salga: es `strict`, así que el día que se implemente, **falla por pasar** y alguien tiene que quitar la marca.

Un `warning` de `pytest` (`PytestRemovedIn10Warning`, en `_pytest/fixtures.py:1392`) por la fixture `base_url` del plugin `pytest-base-url`, no por nada definido en `tests/e2e/`; `test_editor_de_cv.py` solo es el primer test que la usa. Es deuda del plugin, no un fallo propio.

### 3.2 · Evals del fit score

| Corrida | Fecha | Modelo | k | pass^1 | pass^k | Costo | Fuente |
|---|---|---|---|---|---|---|---|
| MOCK | **26-nov-2026** (la hice yo) | `mock-1` | 3 | **0/36 (0 %)** | **0 %** | 0,0000 USD | salida en terminal; informe `evals/resultados/20261126-200347-mock-k3.json` |
| Modelo real | 22-nov-2026 | `claude-haiku-4-5-20251001` | **1** | **9/12 (75 %)** | 75 % | 0,2980 USD | `docs/prs/evals-fit-score.md` §4c, salida pegada completa |
| Modelo real, un par | 22-nov-2026 | `claude-haiku-4-5-20251001` | 1 | 2/2 (100 %) | 100 % | 0,0776 USD | `docs/prs/evals-fit-score.md` §4d |

**El MOCK en 0/36 es el resultado esperado, no una regresión:** devuelve un score fijo de 70 y tres razones que no hablan de ningún caso (`app/match/proveedor/mock.py`). Lo que `poe evals` comprueba es que el **camino de producción** —pseudonimizador → fábrica de proveedor → frontera → adaptador → calificación— funciona de punta a punta sin red y sin costo (`evals/README.md`).

**Lo que sí vale del 22-nov:** los **tres invariantes se cumplieron** con el modelo real — fs-26 (88) contra fs-25 (87), fs-28 (53) contra fs-04 (60) y fs-29 (8) contra fs-03 (8): ni los datos personales añadidos ni las dos instrucciones inyectadas en el CV movieron el score (F24, §1a). Los tres casos que fallaron están nombrados con su motivo en `docs/prs/evals-fit-score.md` §4c.

> **Pregunta abierta · pass^3 con el modelo real no existe.** La única pasada real fue con **k=1**, así que ese «pass^k 75 %» es aritméticamente el mismo número que pass^1 y **no dice nada sobre la varianza del modelo**, que es justo para lo que pass^k existe. Que la varianza es real está medido: el mismo caso fs-26 dio **88** en una pasada y **82** en otra, y fs-25 **87** y **86** (§4c contra §4d). Intenté correr `uv run python -m evals --proveedor claude --k 3` para este reporte y el entorno no me autorizó el comando; cuesta **≈ 0,90 USD** y **~12 minutos** (`evals/README.md`). **Hasta que se corra, pass^3 es desconocido, no 75 %.**

> **Pregunta abierta · el tope de gasto por llamada está más cerca de lo que su comentario dice.** `--max-budget-usd 0.05` se justifica en `app/match/proveedor/cliente.py` como «~6 veces lo medido», pero el par fs-25/fs-26 costó **0,039 USD de media**, el **78 %** del tope (`evals/README.md`). Es una constante, y la decide Víctor.

### 3.3 · E2E

**14 tests** en `tests/e2e/`, con Chromium headless, **el servidor levantado por el propio test** y el proveedor en MOCK; corren al final de la suite por el orden que fija `tests/conftest.py`.

| Archivo | Tests | Qué protege |
|---|---|---|
| `test_humo.py` | 4 | los cuatro guiones de la Etapa 0: CV por la UI real, 404 a Meridian, hiring manager con 200 sin Match y 403 en el endpoint, interruptor apagado |
| `test_qa_movil_360.py` | 2 | **CA19** · `scrollWidth <= clientWidth` a 360×640 con score visible |
| `test_qa_borrado_con_vacante_ajena.py` | 6 | **CA1** · borrar con un `vacante_id` ajeno no borra y responde 404 |
| `test_qa_redireccion_abierta.py` | 1 | issue **#16** · `destino=//example.com` ya no saca al usuario de Criba |
| `test_editor_de_cv.py` | 1 | el editor de CV llega por HTMX al abrir el `<details>`, y no en la lista |

Se cumple la regla de `CLAUDE.md` §7: **cero `sleep`, `time.sleep` o `wait_for_timeout`** en `tests/e2e/` — se espera a condiciones. Comprobado: buscar `sleep|wait_for_timeout` en `tests/e2e/` devuelve **dos comentarios y ninguna llamada** (`conftest.py:201`, «espera el arranque de uvicorn, no un `sleep` fijo»; `test_editor_de_cv.py:13`). Y cada hallazgo de QA arreglado entró primero como E2E en rojo: en el PR #20, el commit «test: los tres hallazgos de QA que se arreglan ahora, como E2E en rojo» (con «Rol: escritor-tests») es anterior al commit «comportamiento:» que los arregla (`gh pr view 20 --json commits`).

### 3.4 · QA

Dos agentes de **caja negra** que prueban contra `SPEC.md` y no saben qué está construido; el triage lo hizo un humano (`qa/README.md`, `qa/TRIAGE.md`).

| Pasada | Informe | Hallazgos |
|---|---|---|
| Backend, `curl`, el mapa de rutas completo, 2 empresas y 4 roles | `qa/reportes/2026-11-22-backend.md` | **6 bugs** (BUG-1 a BUG-6), cada uno con su `curl` reproducible |
| Frontend, Playwright MCP, escritorio y 360 px | `qa/reportes/2026-11-22-frontend.md` | **3 bugs** (BUG-1 a BUG-3), con capturas en `qa/capturas/` y video en `qa/video/` (no versionado) |
| Amplitud, schemathesis, 140 casos en 5 s | comando en `qa/README.md` §Amplitud | 1 hallazgo: un ID mayor que `bigint` da 500 en 4 rutas |

Triage de las 8 filas (`qa/TRIAGE.md`): **2 se arreglaron ahora** (frontend BUG-3 y backend BUG-2, con E2E primero, PR #20) — a las que se suma, fuera de la tabla, el issue #16 que el propio triage encontró y también se arregló ya; **3 filas agrupan 5 bugs que ya estaban en el plan** (F-BUG-1+B-BUG-3 y F-BUG-2+B-BUG-4 en PR-20, B-BUG-1 en PR-18); **2 fueron a issue** (backend BUG-6 y el hallazgo de schemathesis); **1 no era un bug** (backend BUG-5).

**Lo más honesto de esta pasada es el falso positivo.** El backend reportó «el login ignora `destino`» (BUG-5); al reproducirlo fuera de la sesión del agente, **no existía**: Git Bash convertía `/vacantes/3` en una ruta de Windows. El agente lo reprodujo dos veces, como pide su rol, pero las dos en la misma terminal. Y la misma causa escondía **un bug real que ninguna de las dos QA encontró y que el triage sí**: con `destino=//example.com` el login respondía `303` con `Location: //example.com` — una URL de Criba que, tras un login legítimo, lleva a otro dominio. Es el issue **#16**, arreglado en PR #20 con su E2E (`tests/e2e/test_qa_redireccion_abierta.py`).

### 3.5 · Performance (CA5)

Todo en `perf/MEDICION.md`, con el entorno escrito **junto** al número (§2) porque sin él el número no significa nada.

**Entorno declarado** (§2): portátil Windows 11, i7-12700H, 20 hilos, 15,7 GB; uvicorn 0.54.0 con **un worker** en `:8046`; PostgreSQL 16.13 en contenedor, base `criba_perf`; driver pg8000; locust 2.47.0 **en la misma máquina**; vacante de Northstar con 500 postulaciones, 499 con score.

| Corrida | Antes (22-nov) | Después de PR-PERF-1 (22-nov) | Presupuesto CA5 |
|---|---|---|---|
| 1 usuario, 2 min · p95 | 110 ms | **98 ms** | < 300 ms ✔ |
| 5 usuarios, 1 min · p95 | 180 ms | **140 ms** | < 300 ms ✔ |
| 10 usuarios, 1 min · p95 | 220 ms | **170 ms** | < 300 ms ✔ |
| Cuerpo en el cable | 1.597.568 B (sin comprimir) | **27.321 B** | — |

Las líneas crudas de los tres CSV de locust están pegadas en `perf/MEDICION.md` §10.1. Las 500 filas siguen todas en la respuesta: lo que dejó de viajar es el `cv_texto`, una columna que la lista nunca mostró — paginar está **prohibido** por CA8 y por `llamadas/2026-11-20-tomas.md` [03:57].

**Tres reservas sobre ese «cumple», todas con número y todas escritas en el propio informe:**

1. **El 26-nov, la misma medición con la máquina ocupada dio p95 = 340 ms con 5 usuarios: fuera del presupuesto** (§10.5). Mismo código, mismo comando, mismos datos, otra máquina en la práctica. Ninguno de los dos números es «el» p95 de Criba.
2. Con CV de largo realista (2.000-4.000 caracteres contra los 1.086 de media sembrados) el p50 sube ~20 ms y el cuerpo pasa a ~2,6 MB — extrapolación medida, marcada como tal (§5.4).
3. El presupuesto se cumple **gracias a** que la siembra esconde una quinta consulta que en producción cuesta ~16 ms y crece con el padrón de la empresa, no con las 500 filas (§5.3).

**Lo que no se midió, dicho en el informe:** la corrección M1 de la ronda de revisión (proyectar `Candidato.tiene_cv`, que añade una columna a la consulta) **no se volvió a medir** (§10, nota); el objetivo «< 2 s en celular con buena red» es medición manual antes de la demo según `SPEC.md`; y **T1 de ADR-001** —el p95 con la cola trabajando— no se ha medido porque depende de PR-20 y PR-21.

---

## 4 · Decisiones

### 4.1 · Tomadas

| Qué | Dónde | Estado |
|---|---|---|
| D1-D6: producto dentro de la plataforma, stack, datos de candidatos, multiempresa, calendario, acceso de staff | `docs/decisiones.md` | **vigentes** (kickoff 12-nov-2026) |
| **ADR-001** · la cola es una tabla de Postgres y el ejecutor corre en el proceso web, con el cambio a proceso aparte **preparado y no hecho** | `docs/adr/ADR-001.md` | **aceptada** 22-nov-2026, decide Víctor |
| **Recorte de alcance:** el histórico abierto de Northstar (~2.000-2.700) sale de la v1; la demo son las tres vacantes de Texas (~680); T1 se mide en staging con sintéticos; nada se mezcla con CI en rojo | `PLAN.md` §0 | **decidida** por Víctor y **aceptada por Tomás por correo el 22-nov-2026** |
| **Proveedor, modelo y adaptador** (N4 ejercida): Claude con versión fijada `claude-haiku-4-5-20251001`, nunca el alias; en este repo el adaptador es el CLI por subproceso; el MOCK es el modo por omisión y el único de CI | `docs/decisiones-propuestas/2026-11-22-proveedor-y-vacante.md` §1 | **decidida** por Víctor el 22-nov |
| **La descripción de la vacante** viaja al proveedor como campo aparte del pedido, nunca dentro de `PayloadPseudonimizado` | mismo archivo §2 | **decidida** por Víctor el 22-nov |
| **Al borrar con un `vacante_id` ajeno: no borrar nada y responder 404** (de las dos salidas que la QA aceptaba) | `qa/TRIAGE.md`, `docs/prs/PR-QA-E2E.md` | decidida en el triage |

**Una deuda documental, no una decisión:** **ni D3 modificado, ni D7-D23, ni la D24 propuesta están en `docs/decisiones.md`.** Viven en `llamadas/2026-11-21-cambios-decisiones.md` y en `docs/decisiones-propuestas/`. `SPEC.md` **supone que el PR de D3 modificado se aprueba el 27-nov** y dice en su primera línea que, si no se aprueba, **no hay Match**. Mover esos textos a la tabla es un PR propio y sigue pendiente.

### 4.2 · Pendientes de un humano

Las 16 de `PLAN.md` §9 con su dueño y su paso bloqueado. Las cinco que mueven el calendario:

| # | Pregunta | Decide | Vence | Qué bloquea |
|---|---|---|---|---|
| 1 | ¿La pseudonimización limpia también empleador, universidad y ciudad del texto libre? | **Priya** | 12-dic-2026 | el `xfail` de §3.1 |
| 2 | ¿La fila de auditoría del score (y `auditoria_accesos`) sobrevive al borrado, anonimizada? CA15 y CA16 empujan en sentidos opuestos | **Priya** | 12-dic-2026 | PR-18, PR-19 y la **fecha de la carga**: sin respuesta, el test de CA16 no puede estar completo en verde |
| 15 | ¿Qué pasa cuando dos usuarios con idiomas distintos miran la misma vacante? | **Tomás** | 12-dic-2026 | PR-20 y PR-22; hoy CA11 solo se cumple cuando `usuarios.idioma` coincide con el defecto de la empresa |
| 3 | ¿Cuándo llegan las 10 vacantes cerradas y anonimizadas? | **Tomás y Dana** | sin fecha | PR-17 y con él **CA14**, que es el único detector de F1 |
| 8 | ¿Quién atiende la alerta de pendientes >60 min fuera del horario de Víctor? | **Tomás** | sin fecha | PR-15 emite hoy una alerta **sin destinatario** |

Y dos más que, sin bloquear un paso, cambian el plan: la **respuesta del abogado sobre la ley 144 el 10-dic** y la **firma del anexo de Meridian** (mientras no llegue, las fixtures bilingües de CA11 y CA12 siguen siendo sintéticas). Además, dos de ADR-001 sin cerrar: **dónde se despliega la plataforma y con cuántos workers web** (el tope de concurrencia es por proceso) y **si el modo MOCK es también el interruptor de producción para cortar gasto** — hoy el modo se lee una vez por proceso (`lru_cache`), así que volver al MOCK es **un reinicio**, no un `export`.

---

## 5 · Riesgos abiertos

Del mapa de `docs/fallas.md`, por severidad × probabilidad, solo los que siguen sin control hoy:

| # | Riesgo | S×P | Por qué sigue abierto |
|---|---|---|---|
| **F1** | El score sobre el CV pseudonimizado no discrimina: el orden se parece al azar | **20** | Su único control es CA14, que depende de las 10 vacantes cerradas (F3). «Hoy no hay otra señal: en producción un score malo se ve igual que uno bueno.» El arnés de evals da una señal **sintética**, no esa |
| **F2** | El pseudonimizador no limpia empleador, universidad ni ciudad del texto libre | **16** | Bloqueado en la pregunta 1 de §4.2. **No hay recuperación hacia atrás: lo enviado ya salió.** Es el `xfail` de §3.1 y el issue **#7** |
| **F3** | Las 10 vacantes cerradas no llegan a tiempo | **16** | «Que no haya fecha comprometida ya es la señal.» Es la dependencia externa más urgente de `SPEC.md` |
| **F11** | El ejecutor corre en el proceso web y la carga inicial compite con los reclutadores | 12 | ADR-001 lo acepta como apuesta explícita. **CA5 no lo ve**: mide con la cola en reposo. Lo detecta T1, que todavía no se midió (§3.5) |
| **F14** | Las tres razones citan algo que no está en el CV | 12 | Sin detección automática posible: D11 exige la razón en el idioma del reclutador, que puede no ser el del CV, así que no hay comprobación por subcadena. Solo juicio humano dentro de CA14 |
| **F21 / F40** | Parte de los CVs son PDF escaneados, o con texto extraíble pero inservible | 9 / 12 | **Nadie ha medido la proporción.** F40 no avisa de nada: produce un score plausible sobre texto basura |

**Issues abiertos en GitHub** (`gh issue list --state all`): **#18** (IDs mayores que `bigint` dan 500 en cuatro rutas), **#17** (subir CV con un `vacante_id` de otra vacante devuelve el fragmento equivocado), **#11** (`correr_cli`, la costura del proveedor, no lo ejecuta ningún test de CI), **#7** (auditoría de PII: 4 formatos que PR-08 no cierra, decide Priya).

**Y un riesgo que no está en el mapa de fallas y conviene decir en voz alta:** todo esto corre sobre `app/plataforma/`, una **réplica mínima** escrita para que Match tenga dónde engancharse (`README.md`). Los siete hechos del esquema real que PR-01 anotó salen de leer esa réplica. El día que Match se enchufe a la plataforma real de Criba, cada uno de esos hechos es un supuesto a confirmar.

---

## 6 · Lo que NO se hizo

**16 de los 26 pasos del plan**, más los 5 condicionados. Nada está cancelado: cada uno tiene su sitio.

| Paso | Qué es | Criterio que deja descubierto | Dónde |
|---|---|---|---|
| PR-11 | Validación de la respuesta y «sin score» con motivo | CA6, CA13 (el motivo visible) | `PLAN.md` §3 L407 |
| PR-12 | Auditoría por score (hash, versión de prompt, de modelo, fecha) | **CA15** | `PLAN.md` §3 L431 |
| PR-13 | Contador de gasto transaccional y techo de 1.500 USD | **CA10** | `PLAN.md` §3 L442 |
| PR-14 | Endurecer la cola: lease, reintentos, idempotencia, reconciliación | CA9, F35 | `PLAN.md` §3 L458 |
| PR-15 | Proveedor caído, latencia y alerta de pendientes >60 min | **CA6, CA7** | `PLAN.md` §3 L482 |
| PR-16 | Comando de puntuación por vacante y consulta de cobertura | **CA20** | `PLAN.md` §3 L496 |
| PR-17 | Arnés del conjunto dorado | **CA14** — bloqueado por F3 | `PLAN.md` §3 L532 |
| PR-18 | Borrado del candidato y purga de la cola | **CA16** (primera mitad) | `PLAN.md` §3 L556; QA backend BUG-1 |
| PR-19 | Auditoría del acceso de staff | **CA17** | `PLAN.md` §3 L582 |
| **PR-20** | **Orden por score, «Pendientes de score» y el clic de vuelta** | **CA8** y el motivo de CA13 | `PLAN.md` §3 L603; QA frontend BUG-1 y BUG-2, backend BUG-3 y BUG-4 |
| PR-21 | Rendimiento de apertura: guardia de consulta única y **T1** | CA5 (la otra mitad) | `PLAN.md` §3 L615 |
| PR-22 | Idioma de la explicación | **CA11** | `PLAN.md` §3 L637 |
| PR-23 | Recálculo automático y manual, 1/día por vacante | **CA9** (el botón del admin) | `PLAN.md` §3 L657 |
| PR-24 | Paridad de idioma, medición manual | **CA12** | `PLAN.md` §3 L673 |
| PR-25 | Móvil a 360 px con razones largas | CA19 (el caso real, F15) | `PLAN.md` §3 L692 |
| PR-26 | Estilo actual y fragmento HTMX con fallback | D22, F36 | `PLAN.md` §3 L703 |
| PR-C1…C5 | Instrumentar el uso del orden por score · extraer el ejecutor · umbral de «descripción insuficiente» · marca de score desactualizado · deshacer un lote de scores malos | F17, F11, F22, F18, F42 | `PLAN.md` §3 L720-724; **cada uno espera una respuesta de Tomás** |
| La carga del histórico | ~2.000-2.700 candidatos de Northstar | sale de CA20 por `PLAN.md` §0 | `PLAN.md` §10.1 — **ningún código nuevo**: es una operación, con la ley 144 y presupuesto propio como precondiciones |
| Issues sin arreglar | #18, #17, #11, #7 | — | GitHub |

**Dicho en la lengua de Tomás:** hoy una reclutadora de Northstar entra, sube un CV, el sistema lo puntúa y **el número se guarda y se ve en su columna** — pero la lista sigue ordenada por fecha, no hay sección de pendientes y las tres razones no están en ninguna pantalla. **Eso es PR-20, y es el paso que convierte lo construido en lo que se demuestra el 15-ene.**

---

## 7 · Costos medidos

De `docs/costos.md`, que los saca del `total_cost_usd` que cada sesión headless reporta al terminar. Son costos **de construir**, no de operar Criba Match.

| Etapa | USD (aprox.) | Qué incluye |
|---|---|---|
| Diseño: llamada, spec, arquitectura, fallas, ADR | ≈ 18 | ≈ 7 son un piloto de 5 corridas de la misma sesión |
| Plan y su revisión | ≈ 64 | plan 1,7 · revisión de 5 rondas ≈ 50 · experimentos (PR gigante 6,0, PR chico 2,1, revisión sin reglas 4,1) |
| Construcción: `criba-base` → `s6-evals` | ≈ 470 | 398,06 medidos en sesiones terminadas · ≈ 73 estimados del brazo cortado de un experimento · incluye 3 pilotos de PR-08 |
| Verificación: QA, E2E y performance | ≈ 72 | QA backend 2,52 · QA frontend 1,63 · PR #20 25,91 · medición y PR #21 ≈ 41,9 (≈ 8,1 estimados por tokens porque una sesión se cortó) |
| **Suma de la tabla** | **≈ 624** | |

**El proveedor del fit score costó menos de 2 USD en total**, a ≈ 0,01-0,025 USD por llamada con `claude-haiku-4-5-20251001` (`evals/README.md` punto 3, `docs/prs/PR-09.md`).

**Dos advertencias que la propia tabla trae y que hay que leer con ella:** incluye **trabajo del curso que un proyecto real no pagaría** (pilotos de la misma tarea para medir su variación, y los dos brazos de un experimento), y una parte está **estimada por tokens**, no medida, porque una sesión se cortó. La lección que deja: *lo caro no es lo que el agente escribe, sino lo que lee* — la etapa 0 leyó 97,8 M tokens y escribió 0,57 M.

> **Pregunta abierta · estos números no los pude recomprobar.** Salen de sesiones ya terminadas y `total_cost_usd` no se vuelve a emitir. Lo único que verifiqué es que la suma de la tabla da ≈ 624 USD. **Y no hay ninguna estimación del costo de operar Match en producción:** el techo de 1.500 USD/mes de D12 está en `SPEC.md` como requisito y PR-13, que lo implementa, no está construido (§6).

---

## 8 · Cómo operarlo

### Levantar y probar

```bash
docker compose up -d                              # Postgres 16, puerto 5434, contenedor criba-db
uv sync                                           # dependencias
uv run python -m playwright install chromium      # una vez: el navegador del E2E
uv run python -m app.plataforma.semilla           # migraciones + datos de desarrollo
uv run python -m uvicorn app.main:app --reload    # http://127.0.0.1:8000
uv run python -m poethepoet check                 # ruff check + ruff format --check + pytest  → §3.1
```

Las órdenes van por `python -m` a propósito: en la máquina de desarrollo (Windows) la política de control de aplicaciones bloquea a veces los `.exe` de los entornos virtuales. Los tests corren contra `criba_test`, **separada** de la base de desarrollo, cada uno dentro de una transacción que se revierte (`README.md`).

### Usuarios de desarrollo

Contraseña de cada uno = su nombre de usuario + `1234` (`README.md`).

| Usuario | Rol | Empresa |
|---|---|---|
| `marcus` | reclutador | Northstar Health (Match activo) |
| `admin.northstar` | admin de empresa | Northstar Health |
| `hm.northstar` | hiring manager | Northstar Health — **no ve nada de Match** (D10, CA18) |
| `sofia` | reclutadora | Meridian Logistics — **Match apagado**, sin anexo (D7, CA3) |
| `soporte` | staff de Criba | elige empresa al entrar; el acceso queda auditado (D6) |

### Los cuatro interruptores

Todos por variable de entorno, y **todos nacen en el valor que no puede sacar un CV de Criba** (`app/match/configuracion.py`):

| Variable | Por omisión | Qué hace |
|---|---|---|
| `CRIBA_MATCH_ACTIVO` | **apagado** fuera de tests | apaga Match entero. La vista de vacante de la plataforma responde 200 igual, siempre |
| `CRIBA_MATCH_EMPRESAS_ACTIVADAS` | **ninguna empresa** | «Match activado + anexo firmado» (D7). Hoy en la v1: solo `northstar-health` |
| `CRIBA_MATCH_PROVEEDOR` | **`mock`** | `claude_cli` selecciona el cliente real. Ningún valor parecido (`claude`, `real`, `produccion`) lo selecciona: una errata no saca CVs |
| `CRIBA_MATCH_IDIOMA_POR_OMISION` | `en` | **supuesto nuestro**, hasta la pregunta 15 de §4.2 |

**El modo de proveedor se lee una vez por proceso** (`lru_cache`): volver al MOCK es **un reinicio**, no un `export`. Importa si alguna vez se usa el MOCK para cortar gasto — que es la pregunta abierta 11 de `PLAN.md` §9.

### Una pasada de QA agéntica

```bash
uv run python qa/preparar.py          # resiembra criba_dev y deja los scores (MOCK) calculados
CRIBA_MATCH_ACTIVO=1 CRIBA_MATCH_EMPRESAS_ACTIVADAS=northstar-health \
  uv run python -m uvicorn app.main:app --port 8000
uv run python qa/rutas.py             # el mapa de rutas: el OpenAPI público está apagado
claude --agent qa-backend  "Haz la pasada de QA de backend de hoy contra http://127.0.0.1:8000."
claude --agent qa-frontend --mcp-config qa/mcp-playwright.json "Haz la pasada de QA de frontend de hoy."
```

**Antes de cada pasada, `qa/preparar.py`**: las dos QA escriben datos, y una QA que corre sobre la basura de otra reporta basura. En Windows, `qa/mcp-playwright.windows.json`, y `MSYS_NO_PATHCONV=1` delante de cada `curl` en Git Bash — es la lección de BUG-5 (§3.4). Para scores reales en vez del MOCK: `uv run python qa/preparar.py --proveedor claude_cli`, ≈ 0,01 USD por CV.

### Las evals

```bash
uv run python -m poethepoet evals                     # MOCK: sin red, sin costo, 12 casos × k=3
uv run python -m evals --proveedor claude --k 3        # modelo real: ≈ 0,90 USD y ~12 min
```

Código de salida **0 aunque los casos fallen**, **1 solo si el camino falló**: un caso que no pasa es un dato de calidad del modelo; un `ErrorDelProveedor` es algo roto (`evals/README.md`). **La CI no corre las evals con el modelo real**, y es deliberado: cuesta dinero y el modelo no es determinista.

### Las reglas de la casa

De `CLAUDE.md`, porque son lo que mantiene esto revisable:

- **Nada cruza entre empresas.** Es el requisito número uno de Tomás ([03:03]) y un fallo ahí es un incidente de seguridad, no un bug.
- `docs/decisiones.md` solo cambia **por PR**, citando su fuente. Lo que no está claro va a «preguntas abiertas», no a un requisito inventado.
- Cada PR pasa por **tres roles en tres sesiones** (escritor de tests → constructor → revisor adversarial, hasta 90 % de confianza y cero bloqueantes, máximo 3 rondas). Los hooks de `.claude/hooks/` lo hacen cumplir. **El merge lo hace un humano.**
- **Cero `sleep` en un E2E.** Un número inventado pasa en tu máquina y falla en CI una vez de cada diez, y un test inestable enseña a todos a ignorar el rojo.
- **Ningún dato real se puntúa** hasta que PR-18 (borrado) y PR-19 (auditoría de staff) estén mezclados (`PLAN.md` §0 punto 1 y §1 regla 7).

### Lo que falta para poder operar de verdad

Antes de puntuar un solo CV real: las dos respuestas de **Priya** (§4.2), **PR-18 y PR-19** mezclados, el interruptor global encendido y Northstar activada, y la **verificación escrita de Priya de retención cero y no entrenamiento** del proveedor — sin ella, el modo se queda en el MOCK (`docs/decisiones-propuestas/2026-11-22-proveedor-y-vacante.md`).

> **Pregunta abierta · no hay despliegue.** Nada de esto está desplegado en ningún sitio: `docs/contexto.md` no describe el despliegue de Criba, y ADR-001 marca «nada nuevo que desplegar» como **ventaja supuesta, no comprobada**. Lo confirma Tomás en la primera semana de diciembre, y de ello depende que T1 sea medible.
