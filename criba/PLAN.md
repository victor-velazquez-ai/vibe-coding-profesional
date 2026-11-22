# Plan de implementación · Criba Match v1

Plan de pasos para llegar a la demo del 15-ene-2027. Cada paso es **un PR revisable en 5 minutos**.

Fuentes: `SPEC.md` (CA1-CA20 y sus preguntas abiertas), `docs/arquitectura.md` (§2, §3, §4, §5), `docs/fallas.md` (F1-F43 y sus cinco conclusiones), `docs/adr/ADR-001.md` (cola en Postgres, ejecutor en el proceso web, T1-T5), `docs/decisiones.md` (D1-D6), `llamadas/2026-11-21-cambios-decisiones.md` (D3 modificado, D7-D23), `llamadas/2026-11-20-tomas.md` (minutos entre corchetes) y `llamadas/2026-11-20-tomas-delta.md` (RI, R, RE).

Este plan **no decide nada nuevo**. Donde falta una decisión, el paso queda marcado como bloqueado y la pregunta vive en «Preguntas abiertas que este plan no resuelve». Donde hay un supuesto nuestro, dice «**supuesto nuestro**».

**Supuesto que sostiene todo:** el PR de D3 modificado se aprueba el 27-nov. Si no se aprueba, no hay Match (`SPEC.md` §2, D19) y este plan no aplica.

---

## 1. Las reglas del plan

1. **Un PR = una preocupación.** De 300 a 400 líneas de diff como máximo, tests incluidos. Si se pasa, se parte en dos.
2. **Tests primero.** Cada paso dice qué tests se escriben antes del código. La evidencia del PR trae la salida **en rojo** antes y **en verde** después (§6).
3. **Commits estructurales separados de los de comportamiento** (§4). Un PR puede traer los dos tipos, en ese orden y en commits distintos; nunca mezclados en un commit.
4. **Orden:** primero un esqueleto que camina de punta a punta con auth, aislamiento por empresa y un E2E de humo (etapa 0); después lo más riesgoso, empezando por lo que falla sin síntoma visible (etapa 1); después lo que el reclutador ve (etapa 2); al final lo cosmético (etapa 3).
5. **Regla de orden que no se negocia:** **ningún PR introduce el cliente real del proveedor antes de que existan la frontera de pseudonimización (PR-08) y la comprobación de activación por empresa (PR-10).** Hasta PR-09 el único cliente que existe es el MOCK, que no sale de la red (`docs/arquitectura.md` §2). Así CA2 y CA3 no pueden quedar en deuda técnica: el camino que las viola no existe.
6. **Ningún PR trae datos reales de cliente.** Ni en fixtures, ni en la evidencia, ni en logs (D3 modificado, D15, F12).

---

## 2. Mapa de archivos propuesto

El repo todavía no tiene código (`docs/fallas.md`, supuesto 7). Esta disposición es **propuesta nuestra**, derivada de D2 (Python 3.13 + FastAPI, Postgres 16 con SQLAlchemy 2 + Alembic, Jinja2 + HTMX) y de las tres capas de `docs/arquitectura.md` §2. **Si la plataforma actual de Criba ya tiene otra disposición, PR-01 la respeta y el resto del plan ajusta las rutas**; lo que no se mueve son las rutas de test, que ya están fijadas en `SPEC.md`.

```
app/match/
  routers/vacante.py            # HTTP: sesión, rol, parámetros, render. No consulta datos.
  services/listado.py           # orden, pendientes, activación por empresa
  services/scoring.py           # MatchService
  services/pseudonimizador.py
  services/gasto.py             # techo y alerta
  services/recalculo.py
  repositories/contexto.py      # empresa_id del contexto de petición o del trabajo
  repositories/match_repo.py    # ÚNICO punto de acceso a datos de Match
  proveedor/payload.py          # tipo PayloadPseudonimizado (frontera)
  proveedor/cliente.py          # adaptador real
  proveedor/mock.py
  cola/trabajos.py              # encolar, tomar (FOR UPDATE SKIP LOCKED), lease
  cola/ejecutor.py              # bucle, concurrencia, reintentos, reconciliación
  comandos/carga_inicial.py
  comandos/cobertura.py
  borrado/inventario.py         # inventario de borrado, legible por el test
  borrado/borrar_candidato.py
  templates/match/vacante.html, _lista.html, _fila.html
migrations/versions/*_match_*.py
docs/inventario-borrado.md
tests/match/…                   # nombres fijados por SPEC.md
tests/calidad/test_gold_northstar.py
tests/e2e/test_humo.py
```

---

## 3. Los pasos

Tamaños en líneas de diff son estimaciones; el límite duro es 400.

### Etapa 0 · El esqueleto que camina (PR-01 → PR-07)

Meta de la etapa: un CV entra, se puntúa con el proveedor MOCK, y una reclutadora de Northstar lo ve en su vacante; una reclutadora de Meridian recibe 404 con los mismos IDs; un hiring manager recibe 403. Todo verificado por un E2E.

---

#### PR-01 · Andamio del módulo y CI
- **Objetivo:** que exista dónde escribir y cómo correr los tests. Sin comportamiento.
- **Archivos:** `app/match/` con los paquetes vacíos de §2, `pyproject.toml` (pytest, ruff, pytest-asyncio, httpx), `tests/conftest.py` con la base de datos de test y transacción por test, `.github/workflows/ci.yml` (lint + pytest).
- **Tests primero:** `tests/match/test_andamio.py`: la app importa, el router de Match está montado y responde 404 en una ruta inexistente; la base de datos de test levanta y se revierte entre tests.
- **Criterio de terminado:** CI verde en un PR limpio; `pytest -q` corre en local con una sola orden documentada en el README.
- **Riesgo:** bajo. El único riesgo real es F19 (clave del proveedor en el repo): este PR activa la protección de push del repositorio y fija que la clave vive solo en variable de entorno, que es la mitigación que `docs/fallas.md` asigna a F19 a costo cero.
- **Dependencias:** ninguna. Es el primero.
- **Tamaño / commits:** ≈200 líneas · 1 commit `estructural:`.

---

#### PR-02 · Esquema inicial de Match e inventario de borrado
- **Objetivo:** las tablas de Match y, en la **misma** migración, el inventario de dónde vive cada dato derivado del candidato.
- **Archivos:** `migrations/versions/0001_match_inicial.py`, `app/match/borrado/inventario.py`, `docs/inventario-borrado.md`, `tests/match/test_inventario_migraciones.py`.
- **Tablas** (`docs/arquitectura.md` §2, ADR-001 §Decisión 1): `match_scores` (empresa_id, candidato_id, vacante_id, score nullable, **razones**, estado, motivo_sin_score, fechas), `match_trabajos` (empresa_id, candidato, vacante, estado pendiente→en curso→listo/error, motivo, intentos, lease con vencimiento, clave de idempotencia), `match_auditoria_scores` (hash del CV, versión de prompt, versión de modelo, fecha — sin texto), `match_gasto_mes` (contador transaccional).
- **Tests primero:**
  1. `test_inventario_migraciones.py`: enumera las tablas que crean las migraciones de Match y **falla si alguna no está en el inventario de borrado** (CA16, segunda mitad; F13).
  2. El mismo test exige que la columna de **razones** esté declarada como dato derivado del candidato (F25).
  3. `migrate up` y `migrate down` de ida y vuelta sobre base limpia.
- **Criterio de terminado:** los dos tests en verde; `docs/inventario-borrado.md` lista tabla, columna y por qué es dato del candidato; ningún índice sobre tablas de negocio existentes en esta migración.
- **Riesgo:** F16 (una migración bloquea una tabla de negocio en horario laboral, S4). Mitigación: este PR solo crea tablas nuevas y lleva en el cuerpo la lista de comprobación de bloqueo (F16, test no automático).
- **Dependencias:** PR-01.
- **Tamaño / commits:** ≈330 líneas · `estructural:` (migración + inventario) y `comportamiento:` (el test de guardia, que es el control nuevo).

---

#### PR-03 · Fixtures de dos empresas, sesión y doble del proveedor
- **Objetivo:** el material de prueba que usan casi todos los pasos siguientes. Solo tests.
- **Archivos:** `tests/match/conftest.py`, `tests/fixtures/cv_*.md` (sintéticos: español, inglés), `tests/dobles/proveedor.py`.
- **Contenido:** dos empresas (Northstar con Match activo, Meridian sin anexo — D7), un reclutador, un admin, un hiring manager y un staff de Criba por empresa; helper de sesión atada a empresa; **doble del proveedor con contador de llamadas** que falla el test si recibe una sola llamada (CA3) y variantes de timeout/500 (CA6).
- **Tests primero:** `tests/match/test_fixtures.py`: las fixtures crean exactamente las dos empresas esperadas, el doble cuenta llamadas y el helper de sesión produce sesiones de empresas distintas que no se mezclan.
- **Criterio de terminado:** cualquier test posterior puede pedir `sesion_reclutador_northstar` y `proveedor_contado` sin escribir montaje propio. Los CV de fixture son sintéticos y el PR lo dice.
- **Riesgo:** fixtures pobres son el punto ciego de CA2 (F2) y CA19 (F15). Este PR no cierra esos huecos: los abre con nombre (`cv_pii_en_texto_libre` llega en PR-08, `razones_largas` en PR-25). Las fixtures bilingües son sintéticas mientras Meridian no firme (pregunta abierta 5 de `SPEC.md`).
- **Dependencias:** PR-02.
- **Tamaño / commits:** ≈300 líneas · 1 commit `estructural:` (solo tests, sin comportamiento de producción).

---

#### PR-04 · El punto único de acceso a datos
- **Objetivo:** un único repositorio de Match que **exige** `empresa_id` tomado del contexto (petición o registro de la cola), no de la URL ni de un argumento que un llamador pueda olvidar (D4, N9, [03:25], `docs/arquitectura.md` §4).
- **Archivos:** `app/match/repositories/contexto.py`, `app/match/repositories/match_repo.py`, `tests/match/test_aislamiento.py` (primera mitad).
- **Tests primero:**
  1. El repositorio no se puede construir sin contexto de empresa (error, no valor por omisión).
  2. **Test de enumeración:** falla si alguna consulta de Match se construye fuera de `match_repo.py` — recorre los módulos de `app/match/` buscando construcción de sentencias SQL/SQLAlchemy y acepta solo el repositorio (CA1, segunda mitad; F4).
  3. Una consulta con dos empresas sembradas devuelve filas de una sola, siempre.
- **Criterio de terminado:** los tres en verde, y el test de enumeración **falla a propósito** en una rama de prueba donde se añade una consulta suelta (la evidencia del PR trae esa salida en rojo).
- **Riesgo:** F4 (S5×P3=15, puede costar el cliente, [03:03]). Es el paso que convierte el aislamiento de convención en control. Riesgo propio: el test de enumeración puede ser burlable; el PR declara explícitamente qué patrones detecta y qué no.
- **Dependencias:** PR-02, PR-03.
- **Tamaño / commits:** ≈300 líneas · `estructural:` (contexto y repositorio vacío) + `comportamiento:` (la exigencia de `empresa_id` y el test de enumeración).

---

#### PR-05 · Vista de vacante: auth, rol y aislamiento
- **Objetivo:** la vacante abre con la lista de candidatos ordenada por fecha, con los controles de acceso puestos. Todavía sin score.
- **Archivos:** `app/match/routers/vacante.py`, `app/match/services/listado.py`, `app/match/templates/match/vacante.html` y `_lista.html`, `tests/match/test_aislamiento.py` (segunda mitad), `tests/match/test_hiring_manager.py`, `tests/match/test_vacante_no_espera.py`.
- **Tests primero:**
  1. **CA1:** recorre **todos** los endpoints y fragmentos de Match con sesión de otra empresa y exige 404, nunca un 200 parcial; el candidato de Northstar no aparece en ninguna lista, orden, export ni log de Meridian.
  2. **CA18:** un hiring manager abre la vacante: sin score, sin razones, sin orden por score, sin sección de pendientes; los endpoints de Match le devuelven 403. Con **enumeración de rutas** del módulo, como en CA1 (F34).
  3. **CA4:** la ruta de lectura no recibe MatchService como dependencia; con el doble contado, `llamadas == 0` (F38).
- **Criterio de terminado:** los tres tests en verde; el router resuelve sesión → usuario, rol y `empresa_id` y no construye ni una consulta (`docs/arquitectura.md` §3, pasos 2-4).
- **Riesgo:** F34 (endpoint nuevo sin control de rol) y F38 (el atajo «si no tiene score, lo calculo al abrir»). Los dos se cubren con enumeración de rutas, que es lo que `docs/fallas.md` conclusión 2 pide en lugar de revisiones de código.
- **Dependencias:** PR-04.
- **Tamaño / commits:** ≈380 líneas · `estructural:` (router y plantilla sin reglas) + `comportamiento:` (rol, aislamiento, cero llamadas).

---

#### PR-06 · Camino de escritura mínimo con proveedor MOCK
- **Objetivo:** cerrar el circuito: llega un CV → se encola un trabajo → un bucle lo toma → el MOCK devuelve un score fijo → se guarda → se ve en la vista. La versión más simple posible: un trabajo a la vez, sin lease, sin reintentos, sin concurrencia.
- **Archivos:** `app/match/cola/trabajos.py` (encolar, tomar), `app/match/cola/ejecutor.py` (bucle mínimo), `app/match/services/scoring.py` (MatchService mínimo), `app/match/proveedor/mock.py`, `tests/match/test_camino_escritura.py`.
- **Tests primero:** encolar un trabajo de Northstar, correr una pasada del bucle, aserciar que hay una fila en `match_scores` con `empresa_id` correcto; y que el `empresa_id` del trabajo viene **del registro de la cola**, no del candidato resuelto por otro camino (F5, `docs/arquitectura.md` §5.3).
- **Criterio de terminado:** el test en verde y el bucle invocable como función (todavía no como comando). El PR dice en su cuerpo, explícitamente, qué queda sin hacer y en qué paso llega: lease y reintentos (PR-14), activación (PR-10), pseudonimización (PR-08), auditoría (PR-12), techo (PR-13).
- **Riesgo:** es el paso que acepta deuda a propósito para que el esqueleto camine. La deuda se contiene con la regla 5 de §1: sin cliente real, nada sale de Criba. El riesgo de retrabajo es real y asumido: PR-14 reescribe la toma del trabajo.
- **Dependencias:** PR-04, PR-05.
- **Tamaño / commits:** ≈300 líneas · `comportamiento:`.

---

#### PR-07 · E2E de humo
- **Objetivo:** un test que recorre de punta a punta lo que existe, para que cualquier rotura posterior se vea en un solo sitio.
- **Archivos:** `tests/e2e/test_humo.py` (Playwright), `tests/e2e/conftest.py`.
- **Tests primero:** es todo test. Guion: login como reclutadora de Northstar → sembrar un candidato → correr una pasada del ejecutor → abrir la vacante → el candidato aparece con su score del MOCK. Segundo guion: la misma URL con sesión de Meridian → 404. Tercero: hiring manager → 403.
- **Criterio de terminado:** el E2E corre en CI con Postgres de servicio y el MOCK; tiempo de ejecución por debajo de un minuto (**supuesto nuestro**: que el E2E sea rápido es lo que hace que se siga corriendo).
- **Riesgo:** un E2E lento o inestable se desactiva y deja de proteger. Si no se puede estabilizar en este PR, se marca como no bloqueante de CI y se dice en el cuerpo, en lugar de dejarlo rojo e ignorado.
- **Dependencias:** PR-06.
- **Tamaño / commits:** ≈250 líneas · `comportamiento:` (solo tests).

> **Hito 0 (viernes 5-dic, propuesto):** el esqueleto camina. A partir de aquí, cada paso endurece algo que ya funciona.

---

### Etapa 1 · Lo más riesgoso: lo que falla sin síntoma visible (PR-08 → PR-19)

Orden tomado de `docs/fallas.md` (severidad × probabilidad) y de su conclusión 2: cuatro de las seis filas más altas no producen ningún síntoma visible. Esas van primero.

---

#### PR-08 · La frontera de pseudonimización
- **Objetivo:** que el cliente del proveedor **no acepte** otra cosa que un payload ya pseudonimizado: un tipo distinto con constructor privado, no un método dentro de un servicio grande (`docs/arquitectura.md` §5.4, F6).
- **Archivos:** `app/match/proveedor/payload.py`, `app/match/services/pseudonimizador.py`, `tests/match/test_pseudonimizacion.py`, `tests/fixtures/cv_pii_en_texto_libre.md`.
- **Tests primero:**
  1. **CA2:** CV en español y en inglés con los seis datos de §1a (nombre, correo, teléfono, dirección, links a perfiles, fotos); ninguno aparece en el cuerpo construido.
  2. **CA2 segunda mitad:** el test falla si se puede invocar al cliente del proveedor sin pasar por el pseudonimizador — a nivel de tipos y con un test que lo intenta.
  3. **(nuevo, F2):** fixture con el nombre, la ciudad y la universidad **dentro de la narrativa** del CV, no en campos estructurados.
- **Criterio de terminado:** 1 y 2 en verde. **El test 3 queda marcado `xfail` con el motivo escrito** mientras Priya no decida la pregunta abierta 2 de `SPEC.md` (¿la limpieza es solo de campos estructurados o también de texto libre?). No se inventa la respuesta: se deja la fixture escrita para que el día que Priya decida solo haya que quitar la marca.
- **Riesgo:** F2 (S4×P4=16) y F6 (S5×P3=15). Recuperación: ninguna hacia atrás — lo enviado ya salió. Por eso este paso va antes que cualquier cliente real.
- **Dependencias:** PR-06. **Bloqueo parcial:** Priya, pregunta abierta 2 de `SPEC.md`.
- **Tamaño / commits:** ≈350 líneas · `estructural:` (extraer la llamada al proveedor del MatchService de PR-06) + `comportamiento:` (la frontera).

---

#### PR-09 · Cliente real del proveedor, timeout y reglas de log
- **Objetivo:** el adaptador del proveedor elegido detrás de la frontera, con tope de tokens, timeout y la prohibición explícita de registrar cuerpos.
- **Archivos:** `app/match/proveedor/cliente.py`, configuración por variable de entorno, `tests/match/test_logs_sin_cv.py`, `tests/match/test_cliente_proveedor.py`.
- **Tests primero:**
  1. **(nuevo, F12):** falla si una línea de log contiene una frase de 8 palabras del CV de fixture — incluido el camino de timeout, que es el que registra cuerpos por omisión.
  2. El cliente aplica timeout y devuelve un error tipado, no una excepción cruda.
  3. El modo MOCK se selecciona por configuración explícita y nunca abre red.
- **Criterio de terminado:** los tres en verde; la clave del proveedor solo en variable de entorno y ausente de logs (F19); el PR registra qué versión de modelo se usa, que es lo que después va a cada fila de auditoría (D15).
- **Riesgo:** F12 (S4×P3=12, queda texto de CV en los logs de la plataforma y D15 dice que no se guarda). Riesgo de calendario: el proveedor lo elige Víctor (N4 acotada) y Priya verifica por escrito retención cero y no entrenamiento **antes de producción** (§1b). Si esa verificación no está, este PR se puede mezclar pero el cliente real **no se habilita en producción**; el interruptor es de configuración.
- **Dependencias:** PR-08 (regla 5 de §1). **Bloqueo:** elección del proveedor; verificación escrita de Priya antes de producción. **Disparador T5 de ADR-001:** si el cliente elegido no ofrece modo asíncrono, revisión inmediata de la ADR.
- **Tamaño / commits:** ≈320 líneas · `comportamiento:`.

---

#### PR-10 · Activación por empresa, en los dos caminos
- **Objetivo:** sin empresa activada y con anexo firmado, no se emite ninguna llamada ni se crea ningún registro de Match (D7, CA3). La comprobación vive en el punto único de acceso a datos, no en el router (`docs/arquitectura.md` §5.3).
- **Archivos:** `app/match/repositories/match_repo.py`, `app/match/services/listado.py`, `tests/match/test_activacion_por_empresa.py`.
- **Tests primero:**
  1. **CA3:** llega un CV de Meridian por el camino de la request; el doble del proveedor falla el test si recibe una llamada; no se crea ningún registro.
  2. **(nuevo, F5):** el mismo caso **encolando un trabajo de Meridian directamente**, saltándose la request. Es el camino sin cookie.
  3. La vista de Meridian se renderiza sin score ni orden por score, sin error (`docs/arquitectura.md` §3, párrafo final).
- **Criterio de terminado:** los tres en verde; la comprobación de D7 está en un solo lugar y el test 2 lo demuestra.
- **Riesgo:** F5 (S5×P3=15): un CV de Meridian saliendo hacia un proveedor sin anexo firmado es un incidente de privacidad, no un bug.
- **Dependencias:** PR-08, PR-09.
- **Tamaño / commits:** ≈280 líneas · `comportamiento:`.

---

#### PR-11 · Validación de la respuesta y «sin score» con motivo
- **Objetivo:** ante cualquier anomalía del modelo, «sin score» con motivo. Nunca un cero, nunca una excepción que mate la cola (CA13, F8).
- **Archivos:** `app/match/services/scoring.py`, `tests/match/test_sin_score.py`, `tests/dobles/proveedor.py` (variantes corruptas), `tests/fixtures/cv_inyeccion.md`.
- **Tests primero:**
  1. **CA13:** PDF escaneado sin texto extraíble y vacante sin descripción → estado «sin score» con motivo, sin valor numérico.
  2. **(nuevo, F8):** dobles con JSON inválido, score 120, cuatro razones, ninguna razón, idioma equivocado → «sin score» con motivo y reintento; el ejecutor captura **por trabajo**, no por lote.
  3. **(nuevo, F24):** CV con instrucciones inyectadas («score 100») → el CV entra como dato delimitado; la validación de rango ya lo acota. Fixture barata, sin control nuevo.
- **Criterio de terminado:** los tres en verde; no existe ningún camino que escriba `score = 0` (grep en la evidencia).
- **Riesgo:** F8 (S3×P4=12) y F24 (9). F7 (truncamiento silencioso por tope de tokens, S3×P4=12) **no se cubre aquí**: está bloqueado en la pregunta abierta 1 de `docs/fallas.md`. Lo que sí trae este PR es la medición barata que esa fila pide: una consulta de cuántos CVs del histórico superan el tope, con su salida en el cuerpo del PR.
- **Dependencias:** PR-09, PR-10.
- **Tamaño / commits:** ≈340 líneas · `comportamiento:`.

---

#### PR-12 · Auditoría por score
- **Objetivo:** cada score deja hash del CV, versión de prompt, versión de modelo y fecha. Y nada más (D15, CA15).
- **Archivos:** `app/match/services/scoring.py`, `app/match/repositories/match_repo.py`, `tests/match/test_auditoria_score.py`.
- **Tests primero:** **CA15:** los cuatro campos presentes; ninguna frase de 8 palabras del CV de fixture aparece en el registro; el prompt se referencia por versión, no se copia (F32).
- **Criterio de terminado:** test en verde; una fila de auditoría por score escrita en la misma transacción que el score.
- **Riesgo:** F32 (S4×P2=8: se incumple D15 justo en la tabla que existe para demostrar cumplimiento). **Tensión conocida:** CA15 contra CA16 (F29) — si la fila de auditoría sobrevive al borrado del candidato lo decide Priya (pregunta abierta 3 de `SPEC.md`). Este PR escribe la fila; **no** decide qué pasa con ella en el borrado. PR-18 recoge el bloqueo.
- **Dependencias:** PR-11.
- **Tamaño / commits:** ≈240 líneas · `comportamiento:`.

---

#### PR-13 · Contador de gasto transaccional y techo
- **Objetivo:** techo de 1.500 USD/mes con alerta al 80 %; al tope, los nuevos quedan pendientes y no se emite ninguna llamada (D12, CA10).
- **Archivos:** `app/match/services/gasto.py`, `tests/match/test_techo_costo.py`.
- **Tests primero:**
  1. **CA10:** contador simulado en 79 %, 80 % y 100 % → alerta en 80 %, cero llamadas en 100 %.
  2. **(nuevo, F23):** caso **concurrente** con dos ejecutores: el contador se lee y se actualiza en la misma transacción antes de cada llamada; el test falla si los dos se creen al 70 %.
- **Criterio de terminado:** los dos en verde; el contador no vive en memoria de proceso (`docs/arquitectura.md` §5.2).
- **Riesgo:** F23 (S3×P3=9) tiene la peor detección del mapa: la factura a mes vencido. F31 (S4×P2=8: un bucle de reintentos consume el techo) depende además de la idempotencia de PR-14. La estimación de precio por score es **supuesto nuestro** (supuesto 3 de `docs/fallas.md`) y hay que recalcularla con el proveedor elegido: este PR deja el precio en configuración, no en código.
- **Dependencias:** PR-09.
- **Tamaño / commits:** ≈280 líneas · `comportamiento:`.

---

#### PR-14 · Endurecer la cola: lease, reintentos, idempotencia, reconciliación
- **Objetivo:** llevar la cola de PR-06 a lo que decide ADR-001: toma con `SELECT … FOR UPDATE SKIP LOCKED`, lease con vencimiento, reintentos con espera creciente, tope de concurrencia, idempotencia y una pasada periódica de reconciliación.
- **Archivos:** `app/match/cola/trabajos.py`, `app/match/cola/ejecutor.py`, `migrations/versions/0002_match_cola_lease.py` (si faltan columnas), `tests/match/test_cola.py`.
- **Tests primero:**
  1. Dos ejecutores concurrentes no toman el mismo trabajo (`SKIP LOCKED`).
  2. **(nuevo, F35):** el mismo trabajo entregado dos veces → **una** sola fila de score, **una** sola de auditoría, **una** sola llamada. Clave: (candidato, vacante, hash de CV, versión de prompt) (RI3).
  3. **(nuevo, F9):** trabajo tomado y nunca liberado → el vencimiento del lease y la reconciliación lo devuelven a pendiente **sin reiniciar el proceso** (es un sábado por la noche con el proceso vivo).
  4. Reintentos acotados por trabajo: no hay tormenta de reintentos (F10, F31).
- **Criterio de terminado:** los cuatro en verde; el bucle es el mismo código que invocará el comando de carga inicial de PR-16 (ADR-001 §Decisión 2).
- **Riesgo:** F9 (S3×P4=12) y F35 (6). Asume F11 a cambio de horas (ADR-001 §Consecuencias): el ejecutor corre en el proceso web con tope de concurrencia. El argumento en contra está registrado en ADR-001 y su disparador de revisión es T1, que se mide en PR-16.
- **Dependencias:** PR-06, PR-11, PR-13.
- **Tamaño / commits:** ≈380 líneas · `estructural:` (extraer la toma del trabajo de PR-06 sin cambiar conducta) + `comportamiento:` (lease, reintentos, idempotencia, reconciliación).

---

#### PR-15 · Proveedor caído, latencia y alerta de pendientes
- **Objetivo:** el proveedor caído no rompe la vacante (CA6) y los pendientes viejos avisan (CA7).
- **Archivos:** `app/match/cola/ejecutor.py`, `app/match/services/scoring.py`, `tests/match/test_fallo_proveedor.py`, `tests/match/test_latencia_cola.py`.
- **Tests primero:**
  1. **CA6:** doble que lanza timeout y error 500 → la vista responde 200, el candidato en «Pendientes de score», ningún error al reclutador ([01:53]).
  2. **CA7:** 200 CVs encolados contra un proveedor simulado con la latencia medida en staging → p95 ≤ 10 min; más test unitario de la alerta por antigüedad > 60 min.
- **Criterio de terminado:** los dos en verde. La latencia del simulado sale de una medición, no de un número inventado: si todavía no hay staging con el proveedor elegido, el PR dice qué latencia usó y de dónde salió.
- **Riesgo:** F33 (S2×P4=8) es el modo de falla mejor cubierto del diseño. El agujero es de proceso: **quién atiende la alerta fuera del horario de Víctor sigue sin definir** (pregunta abierta 4 de `docs/fallas.md`, pregunta 1 de ADR-001). Este PR emite la alerta y escribe en el cuerpo que no tiene destinatario asignado. No se inventa uno.
- **Dependencias:** PR-14.
- **Tamaño / commits:** ≈300 líneas · `comportamiento:`.

---

#### PR-16 · Comando de carga inicial y consulta de cobertura
- **Objetivo:** poder correr la carga inicial de CA20 en diciembre, fuera del horario de los reclutadores, y saber en cualquier momento cuánta cobertura hay.
- **Archivos:** `app/match/comandos/carga_inicial.py`, `app/match/comandos/cobertura.py`, `tests/match/test_cobertura_demo.py`.
- **Tests primero:** **CA20:** la consulta de cobertura falla si queda algún candidato sin score **y** sin motivo; el comando de carga inicial es idempotente (se puede reejecutar sin pagar dos veces, apoyado en PR-14) y acepta un tope de concurrencia.
- **Criterio de terminado:** test en verde y **la carga inicial ejecutada de verdad** contra el histórico abierto de Northstar y las tres vacantes de Texas, con tres salidas reales en el cuerpo del PR:
  1. la cobertura resultante (CA20),
  2. el porcentaje de CVs sin texto extraíble (F21, que nadie ha medido),
  3. **la medición de T1**: p95 de servidor al abrir la vacante de 500 **con la cola trabajando** (ADR-001 T1, F11, el punto ciego de CA5).
- **Riesgo:** F10 (429 del proveedor durante la carga, S4×P3=12) y F11 (contención, 12). Las dos mitigaciones son de calendario: diciembre y fuera de horario (ADR-001 §Decisión 4). **Si T1 sale ≥ 300 ms, se dispara PR-C2** (extraer el ejecutor), y es mejor saberlo en diciembre que en enero. **Entrada que falta:** si la carga inicial son ~2.000 o ~2.700 scores lo confirma Dana (pregunta abierta 7 de `docs/fallas.md`, T3).
- **Dependencias:** PR-14, PR-15. **Bloqueo operativo:** dónde se despliega la plataforma y si el comando se puede correr ahí (pregunta 2 de ADR-001, a confirmar con Tomás la primera semana de diciembre).
- **Tamaño / commits:** ≈300 líneas · `comportamiento:`.

---

#### PR-17 · Arnés del conjunto dorado (CA14)
- **Objetivo:** poder responder, en diciembre, si el score discrimina. Es el único detector de F1, la falla que decide la demo.
- **Archivos:** `tests/calidad/test_gold_northstar.py`, `app/match/comandos/informe_calidad.py`, `docs/calidad/README.md`.
- **Tests primero:** es todo test, y **manual**: no entra en CI porque cuesta dinero y usa datos del cliente (CA14). Carga las 10 vacantes cerradas y anonimizadas, puntúa todos sus candidatos y aserciona que en ≥8 de 10 el candidato contactado primero queda entre los 5 primeros. Informe reproducible por vacante.
- **Criterio de terminado:** el arnés corre con un conjunto de prueba sintético (verde técnico) **y** con el conjunto dorado real si ya llegó. El informe es el artefacto que Dana y dos reclutadoras de Northstar validan.
- **Riesgo:** **F1 (S5×P4=20, la fila más alta del mapa) y F3 (16).** F3 es una dependencia externa: las 10 vacantes anonimizadas no tienen hoy fecha ni dueño («la dependencia externa más urgente», pregunta abierta 6 de `SPEC.md`). Acción del plan, no del código: pedir fecha a Tomás y Dana **en la primera semana de diciembre** y tratarla como hito. Contingencia conocida: conjunto reducido de 3-4 vacantes para tener *alguna* señal, aceptando que no cumple D18. Si da <8/10, la decisión vuelve a Tomás y Priya **antes** del 15-ene (`llamadas/2026-11-21-cambios-decisiones.md` §4).
- **Dependencias:** PR-16. **Bloqueo:** F3, que es externo y no se resuelve escribiendo código.
- **Tamaño / commits:** ≈300 líneas · `comportamiento:` (solo tests y un comando de informe).

> **Hito 1 (viernes 19-dic, propuesto):** carga inicial hecha, T1 medido, CA14 ejecutado al menos una vez. Es el hito que decide si hay que hablar con Tomás y Priya, y hay semanas de margen para hacerlo.

---

#### PR-18 · Borrado del candidato y purga de la cola
- **Objetivo:** que no quede ningún dato ni identificador del candidato en ninguna tabla o cola de Match (CA16, ≤7 días, D15).
- **Archivos:** `app/match/borrado/borrar_candidato.py`, `app/match/borrado/inventario.py`, `tests/match/test_borrado_candidato.py`.
- **Tests primero:**
  1. **CA16:** crear, puntuar, borrar y recorrer **todas** las tablas de Match buscando el `candidato_id` y el hash; incluidas las razones (F25).
  2. El test de inventario por migración de PR-02 sigue en verde (F13).
  3. **(nuevo, F43):** borrar **con un trabajo en vuelo** → el borrado purga primero los trabajos en cola y el ejecutor comprueba que el candidato sigue existiendo antes de escribir. El candidato borrado no reaparece.
- **Criterio de terminado:** los tres en verde. **Lo que no entra y se dice en el cuerpo:** qué pasa con la fila de auditoría del score (CA15 contra CA16, F29). **Decide Priya** con criterio de SOC 2 (pregunta abierta 3 de `SPEC.md`), y `docs/fallas.md` es explícito: no implementar una salida sin esa respuesta. El PR deja el recorrido escrito y la fila de auditoría fuera del borrado, marcado como pendiente de decisión.
- **Riesgo:** F13 (12), F43 (8), F25 (9). F43 es «CA16 pasa en el test y falla en producción», la peor combinación para un control de privacidad.
- **Dependencias:** PR-12, PR-14. **Bloqueo parcial:** Priya (F29).
- **Tamaño / commits:** ≈340 líneas · `comportamiento:`.

---

#### PR-19 · Auditoría del acceso de staff
- **Objetivo:** cada acceso del staff de Criba a scores y razones deja fila en `auditoria_accesos` (D6, D21, CA17).
- **Archivos:** `app/match/routers/vacante.py`, `app/match/repositories/match_repo.py`, `tests/match/test_auditoria_staff.py`.
- **Tests primero:**
  1. **CA17:** staff carga la vista → fila con quién, qué candidato y cuándo.
  2. **(nuevo, F41):** **enumeración de vistas** — el test recorre todas las vistas y fragmentos de Match que muestran score o razones y falla si alguna no audita. Como en CA1.
  3. La escritura va en la misma transacción que sirve la vista: si no se puede auditar, no se muestra.
- **Criterio de terminado:** los tres en verde; la enumeración falla a propósito en una rama de prueba con una vista nueva sin auditar (salida en rojo en la evidencia).
- **Riesgo:** F41 (S4×P3=12): falla en silencio un control obligatorio que SOC 2 revisa en marzo.
- **Dependencias:** PR-05, PR-12.
- **Tamaño / commits:** ≈260 líneas · `comportamiento:`.

---

### Etapa 2 · Lo que el reclutador ve (PR-20 → PR-24)

---

#### PR-20 · Orden por score, «Pendientes de score» y el clic de vuelta
- **Objetivo:** el comportamiento de la lista que pide D9: orden por score por defecto, pendientes **arriba** con su fecha, nadie oculto ni colapsado, un clic devuelve el orden por fecha (CA8, §11).
- **Archivos:** `app/match/services/listado.py`, `app/match/templates/match/_lista.html` y `_fila.html`, `tests/match/test_orden_y_pendientes.py`.
- **Tests primero:** **CA8:** el conteo de candidatos renderizados es igual al total (nada de paginar ni cargar por tramos — F39, RI12, [03:57]); el orden por defecto es por score; la sección de pendientes está por encima de la lista y muestra la fecha; un clic cambia a orden por fecha. Y el motivo de «sin score» es visible para el reclutador (CA13, lado UI).
- **Criterio de terminado:** test en verde; la plantilla no tiene ningún camino de paginación.
- **Riesgo:** F39 (S4×P3=12). Paginar es la salida natural para sostener el p95 de CA5 y sería **un descarte de facto**, justo el criterio que mira la ley 144 (D20). Si hace falta para sostener CA5, es una decisión de producto que vuelve a Tomás, no un detalle de implementación: el PR lo dice y no lo decide. También F18: que el score pueda estar calculado contra una versión anterior de la vacante **no se marca en la UI**, porque es la pregunta abierta 7 de `SPEC.md` y no es requisito aún.
- **Dependencias:** PR-11 (necesita estados «sin score» reales).
- **Tamaño / commits:** ≈320 líneas · `comportamiento:`.

---

#### PR-21 · Rendimiento de apertura
- **Objetivo:** p95 de servidor < 300 ms con 500 candidatos (CA5, RE8, [04:06]).
- **Archivos:** `migrations/versions/0003_match_indice.py`, `app/match/repositories/match_repo.py`, `tests/match/test_rendimiento_vacante.py`.
- **Tests primero:** **CA5:** sembrar 500 candidatos con score, medir p95 del lado del servidor en 50 peticiones, fallar por encima de 300 ms. Más un test que falla si la plantilla provoca una consulta por candidato (F27): contador de consultas, debe ser una.
- **Criterio de terminado:** test en verde; índice por `(empresa_id, vacante_id, score)` creado en migración, **con `CONCURRENTLY` y fuera de horario si toca una tabla existente** (F16, lista de comprobación en el cuerpo del PR).
- **Riesgo:** F27 (9) y F16 (8). Punto ciego conocido y asumido: **CA5 mide con la cola en reposo** (F11). La medición con la cola trabajando es T1 y se hizo en PR-16; este test no la sustituye y el PR lo dice.
- **Dependencias:** PR-20.
- **Tamaño / commits:** ≈240 líneas · `estructural:` (migración del índice) + `comportamiento:` (consulta única y test de rendimiento).

---

#### PR-22 · Idioma de la explicación
- **Objetivo:** las tres razones en el idioma del reclutador (`usuarios.idioma`, D11, CA11), pedido por separado del idioma del CV.
- **Archivos:** `app/match/services/scoring.py`, `app/match/cola/trabajos.py` (el idioma viaja en el trabajo, `docs/arquitectura.md` §2), `tests/match/test_idioma_explicacion.py`.
- **Tests primero:** **CA11:** reclutador con `idioma='es'` y CV en inglés → razones en español; y al revés. Verifica el idioma pedido en el prompt y el idioma del texto renderizado. Más **F37:** `usuarios.idioma` vacío o con valor inesperado → idioma por omisión explícito y validación del valor.
- **Criterio de terminado:** los dos en verde.
- **Riesgo:** F37 (S2×P2=4, bajo en la v1 porque Northstar trabaja en inglés, [02:37]; sube cuando se encienda Meridian). Este paso es el prerrequisito de PR-24.
- **Dependencias:** PR-11.
- **Tamaño / commits:** ≈220 líneas · `comportamiento:`.

---

#### PR-23 · Recálculo automático y manual
- **Objetivo:** CV nuevo recalcula solo; editar la vacante no recalcula nada; el admin puede «recalcular vacante» 1 vez al día; el reclutador no puede (D23, CA9).
- **Archivos:** `app/match/services/recalculo.py`, `app/match/routers/vacante.py`, `tests/match/test_recalculo.py`.
- **Tests primero:** **CA9**, tres casos: (a) CV nuevo → recálculo sin intervención; (b) editar la descripción de la vacante → cero recálculos; (c) reclutador → 403, admin dos veces el mismo día → el segundo **se rechaza con un mensaje, no con un error**.
- **Criterio de terminado:** los tres en verde; el botón solo existe para el rol admin.
- **Riesgo:** F31 (el recálculo masivo consume el techo): el límite de 1/día y la idempotencia de PR-14 son la contención. F18 (scores viejos tras editar la vacante) queda sin marca en la UI por la pregunta abierta 7. La zona horaria del límite «1/día» está declarada fuera de alcance en `docs/fallas.md`; el PR dice qué zona usó.
- **Dependencias:** PR-14, PR-20.
- **Tamaño / commits:** ≈300 líneas · `comportamiento:`.

---

#### PR-24 · Paridad de idioma
- **Objetivo:** el mismo CV en español y en inglés difiere en ≤5 puntos contra la misma vacante (CA12, RI7, R4).
- **Archivos:** `tests/match/test_paridad_idioma.py`, `tests/fixtures/pares_idioma/`.
- **Tests primero:** **CA12:** 10 pares de CV traducidos; falla si algún par supera los 5 puntos.
- **Criterio de terminado:** test en verde, o **hallazgo documentado** si falla. Dos límites van escritos en el cuerpo del PR: el umbral de 5 puntos es **supuesto nuestro** (pregunta abierta 1 de `SPEC.md`, pendiente del visto bueno de Tomás o Dana) y las fixtures son **sintéticas** mientras Meridian no firme el anexo (pregunta abierta 5).
- **Riesgo:** F28 (S3×P3=9): es sesgo, y Northstar opera en Nueva York (D20). Si CA12 falla, es un hallazgo para Tomás y Priya, **no un parche de prompt a última hora**.
- **Dependencias:** PR-22.
- **Tamaño / commits:** ≈250 líneas · `comportamiento:` (solo tests y fixtures).

---

### Etapa 3 · Cosmético (PR-25 → PR-26)

---

#### PR-25 · Móvil a 360 px
- **Objetivo:** sin desbordamiento horizontal a 360 px, con score, razones y control de orden visibles y accionables (CA19, D22).
- **Archivos:** `app/match/templates/match/*`, hoja de estilo del módulo, `tests/match/test_movil_360.py`, `tests/fixtures/razones_largas.py`.
- **Tests primero:** **CA19:** Playwright a 360×640, `scrollWidth <= clientWidth` y visibilidad de los tres elementos. Más **(nuevo, F15):** fixture con las tres razones **en su longitud máxima** y en dos idiomas, que es el caso real y no el de las fixtures cortas.
- **Criterio de terminado:** test en verde **y** un ensayo manual en un teléfono real antes del 15-ene (F15, F30: Dana maneja la vista desde su celular, D17). La evidencia del ensayo es una captura y el dispositivo, declarados como medición manual.
- **Riesgo:** F15 (S4×P3=12) depende del límite de caracteres por razón, que es la **pregunta abierta 8 de `SPEC.md`, sin decidir**. Este PR usa la longitud máxima observada en las razones reales de la carga inicial y lo dice; no inventa un límite.
- **Dependencias:** PR-20.
- **Tamaño / commits:** ≈280 líneas · `comportamiento:`.

---

#### PR-26 · Estilo actual y fragmento HTMX con fallback
- **Objetivo:** el módulo se ve como el resto de la plataforma (D22) y el cambio de orden sobrevive a un fragmento que falla.
- **Archivos:** `app/match/templates/match/*`, `tests/match/test_htmx_fallback.py`.
- **Tests primero:** **(nuevo, F36):** el orden también funciona como parámetro de la vista completa, así que si el fragmento HTMX falla o llega a medias, la recarga lo resuelve (`docs/arquitectura.md` §2).
- **Criterio de terminado:** test en verde; el estilo revisado contra la plataforma actual.
- **Riesgo:** F36 (S2×P3=6), el más bajo del plan. **Es el primer PR que se sacrifica si el calendario aprieta** (§7).
- **Dependencias:** PR-25.
- **Tamaño / commits:** ≈220 líneas · `comportamiento:`.

---

### Pasos condicionales

No entran en el camino principal. Cada uno tiene un disparador explícito.

| ID | Paso | Disparador | Tipo |
|---|---|---|---|
| **PR-C1** | Instrumentar el uso del orden por score (métrica del 60 %, §23) | Tomás responde que entra en la v1 (pregunta abierta 11 de `SPEC.md`). Es el único detector posible de F17 y **no se puede añadir con efecto retroactivo**: si la respuesta tarda, el costo de la espera es permanente. | comportamiento |
| **PR-C2** | Extraer el ejecutor a un proceso aparte | Cualquiera de T1-T5 de ADR-001. T1 se mide en PR-16. El código del bucle es el mismo y solo cambia quién lo invoca: ADR-001 lo deja como **cambio preparado, no hecho**. | **estructural** (mover, no cambiar conducta) |
| **PR-C3** | Umbral de «descripción insuficiente» de la vacante | Tomás aprueba ampliar CA13 (F22, pregunta abierta 2 de `docs/fallas.md`). | comportamiento |
| **PR-C4** | Marca en la UI de «calculado con una versión anterior de la vacante» | Tomás responde la pregunta abierta 7 de `SPEC.md` (F18). | comportamiento |
| **PR-C5** | Vía de recálculo por versión de prompt, solo para nosotros | Tomás decide la pregunta abierta 8 de `docs/fallas.md` (F42: hoy no hay camino de vuelta tras un error nuestro). | comportamiento |

---

## 4. Estructural contra comportamiento

Regla: **un commit nunca mezcla los dos.** El prefijo del asunto lo declara.

- `estructural:` mover, renombrar, extraer, preparar, crear una migración que solo añade tablas, añadir fixtures. **No cambia ninguna conducta observable.** Su evidencia es que **los mismos tests pasan antes y después**, sin tocar tests.
- `comportamiento:` cambia lo que el sistema hace. Trae test propio, y ese test falla antes del cambio.

Dentro de un PR, los estructurales van primero, para que el commit de comportamiento sea pequeño y legible. Ejemplos de este plan:

| PR | Commit estructural | Commit de comportamiento |
|---|---|---|
| PR-02 | migración que crea tablas nuevas + inventario | el test de inventario por migración |
| PR-04 | crear contexto y repositorio vacío | exigir `empresa_id`, test de enumeración |
| PR-05 | router y plantilla sin reglas | rol, aislamiento, cero llamadas |
| PR-08 | extraer del MatchService la llamada al proveedor | la frontera de tipos |
| PR-14 | extraer la toma del trabajo de PR-06 | lease, reintentos, idempotencia |
| PR-21 | migración del índice | consulta única y p95 |
| PR-C2 | mover el bucle a su propio punto de entrada | ninguno: es solo quién lo invoca |

Si un PR de comportamiento necesita mover cosas, el movimiento se separa: se mezcla primero el PR estructural, solo.

---

## 5. Cómo reviso esto en 5 minutos

Orden de lectura del revisor, pensado para que el límite de 400 líneas sirva de algo:

1. El título y la sección «Qué cambia y por qué», con su cita.
2. **Los tests primero.** Si el diff de tests no se entiende solo, el PR está mal partido.
3. La evidencia: rojo antes, verde después.
4. El diff de código.
5. «Qué NO entra»: es donde se ve si el PR dejó deuda con nombre o deuda escondida.

---

## 6. Plantilla del cuerpo del PR

Se copia tal cual en `.github/pull_request_template.md` (lo hace PR-01).

````markdown
## Qué cambia y por qué
Una o dos frases. **Cita obligatoria:** archivo y minuto de la llamada, o el ID de la decisión
(D#), el criterio (CA#), la fila de fallas (F#) o la ADR.

Ejemplo: «Exige `empresa_id` en el único punto de acceso a datos de Match
(D4, `llamadas/2026-11-20-tomas.md` [03:25], CA1, F4).»

## Tipo de cambio
- [ ] estructural (mover, renombrar, extraer, preparar — **sin cambio de conducta**)
- [ ] comportamiento
- [ ] las dos cosas, en commits separados (estructurales primero)

## Tests primero
Qué tests se escribieron **antes** del código y qué protegen:
- `tests/…::test_…` → CA# / F#

## Evidencia

**1. En rojo, antes del código** (pegar la salida real, sin editar):
```
$ pytest tests/match/test_aislamiento.py -q
<salida real>
```

**2. En verde, después** (pegar la salida real):
```
$ pytest tests/match/test_aislamiento.py -q
<salida real>
```

**3. Suite completa:**
```
$ pytest -q
<salida real>
```

**4. Mediciones, si el paso las tiene** (comando y número real; declarar si es manual):
```
$ <comando>
<salida real>
```

Reglas de la evidencia:
- Salida **real**, pegada tal cual. Si se recorta, decir dónde con `…`.
- Si el paso es estructural: la evidencia es `pytest -q` **antes y después**, igual, sin tocar tests.
- Si la verificación es manual (p. ej. CA14, los <2 s en celular, el ensayo a 360 px),
  escribir **medición manual**, qué se midió, con qué dispositivo o red y quién la hizo.
  No se presenta una medición manual como si fuera un test.
- **Nada de datos reales de cliente ni texto de CV en el cuerpo del PR** (D3 modificado, D15, F12).
  Fixtures sintéticas o resultados agregados.

## Criterio de terminado
Lista verificable. Cada punto, comprobable por el revisor desde la evidencia de arriba.

## Riesgo
Qué fila de `docs/fallas.md` cubre o toca este PR (F#, con su S×P), y qué riesgo **introduce**.
Si el riesgo queda sin cubrir, decirlo aquí.

## Qué NO entra
Lo que quedó fuera a propósito y en qué paso del plan llega. Si está bloqueado en una decisión
de otra persona, nombrar a quién decide y la pregunta abierta.

## Dependencias
PR-## previos. Si toca una migración, enlazar la lista de comprobación de bloqueo (F16).

## Fuentes
Enlaces a `SPEC.md`, `docs/decisiones.md`, `llamadas/…`, `docs/adr/…`, `issues/…`.
````

---

## 7. Calendario y capacidad

**Cuenta nuestra**, no un dato: 1-dic → 15-ene son ~6,5 semanas; descontando navidades quedan ~5 semanas de trabajo, y a 20 h/semana (D5) son **~100 h**. Los 26 pasos del camino principal, a ~4 h cada uno, son **~104 h**. El plan está **al límite de la capacidad**, sin holgura para imprevistos, y el calendario es R1.

| Hito | Fecha propuesta | Qué tiene que estar |
|---|---|---|
| H0 | 5-dic | PR-01 → PR-07: el esqueleto camina, con auth, aislamiento y E2E |
| H1 | 19-dic | PR-08 → PR-17: fronteras de datos cerradas, carga inicial hecha, **T1 medido**, **CA14 ejecutado** |
| H2 | 9-ene | PR-18 → PR-23: borrado, auditoría de staff, orden, rendimiento, idioma, recálculo |
| H3 | 14-ene | PR-24 → PR-26 y el ensayo manual en el teléfono real |
| Demo | 15-ene | — |

Dos cosas tienen que pasar **en la primera semana de diciembre** y no son código (`docs/fallas.md`, conclusión 1): pedir fecha del conjunto dorado a Tomás y Dana (F3) y confirmar con Tomás dónde se despliega la plataforma (pregunta 2 de ADR-001).

**Si el calendario aprieta, el orden en que se sacrifica es este** — y es una decisión que se comunica, no se toma en silencio: PR-26 (estilo y fallback HTMX, F36 es el riesgo más bajo del mapa), luego PR-24 (CA12, con el aviso de que queda un sesgo sin medir, F28), luego los condicionales. **Nada de la etapa 0 ni de la etapa 1 se sacrifica:** son el aislamiento entre empresas, la PII y la calidad del score, o sea CA1, CA2, CA3 y CA14.

---

## 8. Cobertura: de los criterios a los pasos

| CA | Qué | Paso |
|---|---|---|
| CA1 | Aislamiento entre empresas | PR-04 (punto único + enumeración), PR-05 (404 en todos los endpoints) |
| CA2 | Nada identificable sale de Criba | PR-08 (+ `xfail` de texto libre, F2) |
| CA3 | Sin anexo no se llama al proveedor | PR-10 (los dos caminos) |
| CA4 | Abrir la vacante no llama al modelo | PR-05 |
| CA5 | p95 < 300 ms | PR-21 (en reposo) + PR-16 (T1, con la cola trabajando) |
| CA6 | Proveedor caído no rompe la vacante | PR-15 |
| CA7 | Latencia del score y alerta >60 min | PR-15 |
| CA8 | Orden y pendientes | PR-20 |
| CA9 | Recálculo | PR-23 |
| CA10 | Techo de costo | PR-13 (+ caso concurrente) |
| CA11 | Idioma de la explicación | PR-22 |
| CA12 | El idioma del CV no cambia el score | PR-24 |
| CA13 | Sin score, nunca un cero | PR-11 (lógica) + PR-20 (motivo visible) |
| CA14 | Calidad del score | PR-17 (manual, bloqueado por F3) |
| CA15 | Auditoría de cada score | PR-12 |
| CA16 | Borrado en 7 días | PR-02 (inventario) + PR-18 (recorrido y trabajo en vuelo) |
| CA17 | Acceso de staff auditado | PR-19 (+ enumeración de vistas) |
| CA18 | Hiring manager no ve Match | PR-05 |
| CA19 | Móvil a 360 px | PR-25 (+ razones largas) |
| CA20 | Cobertura para la demo | PR-16 |

**Tests que `docs/fallas.md` propone y que todavía no están en `SPEC.md`** (los siete de su sección «dependen de un test que todavía no está en la spec»): F12 → PR-09; F15 → PR-25; F22 → PR-C3 (bloqueado); F24 → PR-11; F35 → PR-14; F36 → PR-26; F43 → PR-18.

**Filas que este plan deja sin test, igual que el mapa** (y por qué): F3 (dependencia externa, se gestiona como hito en §7), F7 (bloqueada en la pregunta abierta 1 de `docs/fallas.md`; PR-11 trae la medición, no el control), F17 (PR-C1, bloqueado), F19 (control del repositorio, PR-01), F20 (fuera del alcance de Match), F26 (consulta manual), F29 (dos tests en contradicción, decide Priya), F30 (medición manual declarada en `SPEC.md`), F40 (muestreo manual del histórico, junto a la medición de F21 en PR-16), F42 (PR-C5, sin procedimiento), F14 y F16 (controles humanos: juicio de CA14 y lista de comprobación por migración).

---

## 9. Preguntas abiertas que este plan no resuelve

Ninguna se responde aquí. Cada una bloquea un paso concreto y tiene un dueño.

| # | Pregunta | Decide | Paso bloqueado | Origen |
|---|---|---|---|---|
| 1 | ¿La pseudonimización limpia también el texto libre del CV? | Priya | PR-08 (el test de F2 queda `xfail`) | `SPEC.md` pregunta 2, F2 |
| 2 | ¿La fila de auditoría del score sobrevive al borrado, anonimizada? | Priya | PR-18 (y la tensión CA15/CA16) | `SPEC.md` pregunta 3, F29 |
| 3 | ¿Cuándo llegan las 10 vacantes cerradas anonimizadas? | Tomás y Dana | PR-17, o sea el único detector de F1 | `SPEC.md` pregunta 6, F3 |
| 4 | ¿El umbral de 5 puntos de CA12 es el correcto? | Tomás o Dana | PR-24 | `SPEC.md` pregunta 1 |
| 5 | ¿Límite de caracteres por razón? ¿Las razones citan evidencia del CV? | Tomás | PR-25 (F15) y la detección de F14 | `SPEC.md` pregunta 8 |
| 6 | ¿Se instrumenta el uso del orden por score en la v1? | Tomás | PR-C1, y no es retroactivo | `SPEC.md` pregunta 11, F17 |
| 7 | ¿El truncamiento por tope de tokens se registra y se muestra? | Víctor con Tomás | PR-11 (sin control, solo medición) | `docs/fallas.md` pregunta 1, F7 |
| 8 | ¿Quién atiende la alerta de pendientes >60 min? | Tomás | PR-15 emite una alerta sin destinatario | `docs/fallas.md` pregunta 4, ADR-001 pregunta 1 |
| 9 | ¿Dónde se despliega la plataforma y se puede correr ahí el comando de carga inicial? | Tomás | PR-16 | ADR-001 pregunta 2 |
| 10 | ¿La carga inicial son ~2.000 o ~2.700 scores? | Dana | PR-16, y es la entrada de T3 | `docs/fallas.md` pregunta 7 |
| 11 | ¿El modo MOCK es solo de test o también interruptor de producción? | Víctor | PR-09 lo implementa solo como modo de configuración; cortar gasto a mano sigue sin definir | `docs/arquitectura.md` pregunta 3, ADR-001 pregunta 4 |
| 12 | ¿Se marca en la UI un score calculado contra una versión anterior de la vacante? | Tomás | PR-C4 (F18) | `SPEC.md` pregunta 7 |
| 13 | ¿Cómo se deshace un lote de scores malos? | Tomás | PR-C5 (F42) | `docs/fallas.md` pregunta 8 |
| 14 | ¿Una descripción de vacante demasiado corta cuenta como «sin descripción»? | Tomás | PR-C3 (F22) | `docs/fallas.md` pregunta 2 |

Dos más que no bloquean un paso pero cambian el plan si se mueven: la respuesta del abogado sobre la ley 144 el 10-dic (`SPEC.md` pregunta 4, D20) y la firma del anexo de Meridian, que mientras no llegue mantiene sintéticas las fixtures bilingües de PR-24 (`SPEC.md` pregunta 5, D7).
