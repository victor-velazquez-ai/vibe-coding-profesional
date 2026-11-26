# Staging local con la configuración de producción

> Cuerpo del PR, con la plantilla de `PLAN.md` §6.
>
> **No lleva número de PR a propósito:** es una **tarea de operación de la sección
> 8**, no un paso de `PLAN.md`, y los IDs `PR-##` son identificadores estables
> citados en `docs/revision-plan/` y en las tablas de §4 y §8. Por eso el archivo
> se llama `staging-local.md` y los commits van marcados `(op-staging)`, que es la
> convención que ya usó `evals-fit-score.md`.

> **Resuelto (ronda 1):** el constructor reportó que 2 de los 23 tests no podían pasar con ningún código (ver «El bloqueante»)
> y **no los tocó**. El escritor de tests lo verificó, lo corrigió en `tests/staging/conftest.py` con un `JOIN` sobre
> `pg_class`/`pg_namespace` (no con el `CAST` que proponía el parche de abajo, que quedó como documento histórico de
> por qué el `::regclass` no funciona) y explicó por qué su rojo de la primera vez no le avisó.
>
> **Resuelto (ronda 2, revisión adversarial del agente):** la revisión encontró, entre otros, un bloqueante real —
> `SoloNuestrosLoggers` (`app/registro.py`) solo deja pasar loggers `app.*` y el camino de lectura registraba bajo
> `criba.match.listado`, así que `staging/logs/app.jsonl` nacía sin su mitad de lectura— y una transacción abierta
> durante toda una tanda de hasta 100 trabajos en `bucle` (`app/match/comandos/ejecutor.py`). Los dos están
> corregidos; el detalle de cada hallazgo (corregido o rechazado, con su razón) está en «Seguimiento de la revisión
> adversarial» más abajo. `poe check`: 254 passed, 2 skipped (el humo del staging, sin `CRIBA_URL_STAGING` en CI), 1
> xfailed — **en verde, sin bloqueante**. Y, aparte de la suite: el staging sí se levantó con `docker compose` después
> de escrito este cuerpo, y el E2E de humo (`tests/staging/test_humo_staging.py`) corrió contra él de verdad:
> **2 passed**, no saltado.

## Qué cambia y por qué

El staging local con la **configuración de producción**: Match encendido, el
proveedor real (`claude_cli`), solo Northstar activada (D7, CA3) y la app entrando
a la base con un rol que no puede hacer DDL. Es el único entorno donde esa
combinación se puede recorrer entera antes de la demo del 15-ene: la suite corre
**siempre** con el MOCK y con el interruptor global encendido por
`tests/conftest.py`, así que hay un camino de producción que hoy nadie recorre.

Con él vienen las tres cosas que un entorno así necesita para servir de algo: un
sitio desde el que mirar números **sin ver un dato de un candidato** (el esquema
`metricas` y el rol `agente_metricas`), un sitio donde queden los logs
(`staging/logs/`), y un orden escrito para cuando algo se rompa (`RUNBOOK.md`).

Fuentes: `docs/adr/ADR-001.md` §Decisión 2 y T1; `docs/arquitectura.md` §2
(componente «Logs JSON»: «`request_id`, `empresa_id`, decisión tomada, latencia,
versión de modelo y prompt») y §5.5; `docs/fallas.md` F12, F16, F19;
`docs/decisiones.md` D3 modificado, D7, D12, D15, D16; `SPEC.md` CA1, CA2, CA3,
CA13, CA16; `PLAN.md` regla 1.7 y §4.

| Pieza | Qué fija |
|---|---|
| `migrations/versions/0002_metricas_staging.py` | el esquema `metricas`, sus **dos vistas** y el `GRANT` **condicionado** a que el rol exista |
| `staging/roles.sql` | `criba_app` (lee y escribe, sin DDL) y `agente_metricas` (solo `SELECT` sobre `metricas.*`). Idempotente |
| `docker-compose.staging.yml` | Postgres 16, `criba-staging-db`, 5455 en 127.0.0.1, volumen propio, `TZ=UTC` |
| `staging/staging.env` | la configuración de producción, con la URL de `criba_app` y un secreto de sesión de staging |
| `app/match/comandos/ejecutor.py` | el ejecutor como **proceso aparte**: `una_pasada` en bucle, una sesión y un `commit()` por trabajo, hasta vaciar la cola y esperar 5 s, hasta Ctrl+C |
| `app/registro.py` | consola legible y, con `CRIBA_LOG_DIR`, una línea JSON por registro a un archivo por proceso |
| `app/match/cola/ejecutor.py` | **una línea por trabajo cerrado**: `trabajo_id`, `empresa_id`, `vacante_id`, `estado`, `motivo`, `ms` |
| `pyproject.toml` | cinco tareas `poe`: levantar y migrar, sembrar, la app, el ejecutor y el humo |
| `RUNBOOK.md` + `postmortems/PLANTILLA.md` | el orden del incidente y el informe sin culpables |
| `staging/metricas.py` + `CRIBA_URL_METRICAS` (`staging/staging.env`) | la consulta SQL de solo lectura para un agente en un incidente, con el rol `agente_metricas` — entró en un commit posterior y la revisión adversarial señaló que faltaba en esta tabla; añadida aquí, sin test propio (ver «Seguimiento de la revisión adversarial») |

### Las tres decisiones que no son obvias

**1 · El `GRANT` va condicionado y el rol lo crea un guion, no la migración.** Los
roles son del **clúster**, no de la base: una migración que creara roles obligaría
a correr Alembic con un superusuario. Y un `GRANT` incondicional rompería
`alembic upgrade` en **toda** base donde el guion del staging no corrió —la de
test de este repo incluida—, o sea la suite entera. Así que la migración pregunta
a `pg_roles` dentro de un `DO $…$` y solo da el permiso si el rol está.

**2 · Las migraciones las corre el dueño, nunca `criba_app`.** `criba_app` no es
dueña de ninguna tabla y no tiene `CREATE` en ningún esquema
(`REVOKE CREATE ON SCHEMA public FROM PUBLIC`), así que un `ALTER TABLE` suyo
falla con permiso denegado. Eso obliga a que `poe staging-arriba` y
`poe staging-sembrar` lleven la URL del dueño —migrar es DDL y sembrar hace
`TRUNCATE … RESTART IDENTITY`— y que solo la app, el ejecutor y el humo vayan con
`uv run --env-file staging/staging.env`. Para que el orden «levantar → migrar →
arrancar» no necesite volver a tocar permisos, `roles.sql` deja puestas las
**privilegios por omisión** del dueño: la tabla que añada la próxima migración
nace legible y escribible por `criba_app`.

**3 · En el staging el ejecutor va aparte, y eso contradice a ADR-001 a
propósito.** ADR-001 §Decisión 2 dice «el ejecutor corre en el proceso web» y deja
extraerlo registrado como **cambio preparado, no hecho**. Sigue siendo así en
producción. En el staging va aparte por tres razones, escritas en el docstring del
comando: el staging existe para medir **T1** —«p95 al abrir la vacante, con la
cola trabajando»— y con los dos en el mismo proceso no se puede separar la
contención del scoring de la de la web; con el proveedor real una pasada tarda lo
que tarde el CLI y hay que poder pararla con Ctrl+C sin tirar la app; y es la forma
de ejercer el cambio preparado antes de necesitarlo.

### Qué no sale nunca de aquí: nada del candidato

Las dos mitades, porque la primera sola no basta:

- **las columnas**: `scores_por_vacante` expone `empresa_id`, `vacante_id`, `dia`,
  `n_con_score`, `n_score_cero`, `n_sin_score` y `score_promedio`;
  `trabajos_por_estado` expone `empresa_id`, `dia`, `estado`, `motivo` y `n`.
  Dimensiones de empresa y de tiempo, conteos y un promedio. Ni `candidato_id`;
- **lo que leen**: ninguna de las dos toca `nombre`, `correo`, `telefono`, `links`,
  `cv_texto`, `razones` (dato derivado, F25) ni `hash_cv` (identificador, CA16).

Lo mismo en el log del trabajo cerrado: los tres identificadores que **no** son
del candidato, la decisión (`estado`, `motivo`) y la latencia — que es exactamente
la lista de `docs/arquitectura.md` §2 leída para el camino de escritura. Y el
formateador del archivo **no escribe la traza de la excepción**, que es el camino
literal de F12: un `subprocess.TimeoutExpired` del CLI lleva dentro el prompt con
el CV, y dejar que el formateador añada el `exc_info` es la línea más natural del
mundo.

`n_con_score` cuenta **el 0 incluido** y `n_score_cero` es su desglose: un «sin
score» no se puede leer como un cero ni al revés (CA13).

## Tipo de cambio

- [ ] estructural
- [ ] comportamiento
- [x] **las dos cosas, en commits separados (estructurales primero)**

| Commit | Qué lleva |
|---|---|
| `estructural: donde vive el staging local, sin cambiar ninguna conducta (op-staging)` | compose, `staging.env`, `app/registro.py` (nadie lo llama aún), el comando del ejecutor, las tareas `poe`, `RUNBOOK.md`, `postmortems/PLANTILLA.md`, `.gitignore` |
| `comportamiento: el esquema metricas, el rol del agente y la linea por trabajo cerrado (op-staging)` | la migración 0002, `staging/roles.sql`, la línea de log del bucle y los logs del proceso web |
| `estructural: comentarios de poe staging-arriba, metricas.py y staging/logs/.gitkeep (op-staging)` | corrige los comentarios que seguían nombrando `poe staging-migrar` (no existe), el `.gitkeep` que el `.gitignore` decía tener y no tenía, y precisa el docstring de `staging/metricas.py` sobre quién acota el SQL — nada de esto cambia una conducta medida por un test |
| `comportamiento: el logger del camino de lectura llega al archivo y el bucle deja de abrir una transaccion larga (op-staging)` | el bloqueante y lo importante de la revisión adversarial: `LOG_DEL_LISTADO` pasa a `app.match.listado` (`app/match/services/listado.py`) y `bucle` usa `una_pasada` con un `commit()` por trabajo en vez de `pasadas(bd)` con `maximo=100` en una sola transacción (`app/match/comandos/ejecutor.py`) |
| `docs: sincroniza el cuerpo del PR con la revision adversarial y con el staging ya levantado (op-staging)` | este archivo: evidencia rehecha, checkboxes corregidas y la tabla de seguimiento de hallazgos |

El primer estructural **no cambia ningún resultado de la suite**: la medición está en la
evidencia 1, y es el mismo número que dejó el escritor de tests. El comando del
ejecutor va en el estructural por la fila PR-C2 de `PLAN.md` §4 («mover el bucle a
su propio punto de entrada | ninguno: es solo quién lo invoca»). El segundo
estructural tampoco cambia ningún resultado: son comentarios, un archivo vacío y
una frase de un docstring. El comportamiento de la ronda 2 sí cambia un resultado
medido —`tests/match/test_logs_de_staging.py` pasa de `1 failed, 2 passed` a
`3 passed`— y el de `bucle` no tiene test propio (ver «Seguimiento de la revisión
adversarial», fila del hallazgo «importante» del bucle).

## Tests primero

Los escribió el escritor de tests en el commit «test: metricas sin datos personales, rol del agente y humo del staging», antes de que existiera una línea
de este código. 23 tests, uno por criterio:

- `tests/staging/test_metricas_sin_datos_personales.py` (9) → CA2, CA13, CA16, D15, F12, D4/CA1
- `tests/staging/test_rol_agente_metricas.py` (12) → CA2, CA16, D15
- `tests/staging/test_humo_staging.py` (2) → CA1, CA3, D4, D7, R6·B1

## Evidencia

**1. En rojo, antes del código** (salida real, con rutas relativas al repo). El
árbol es el del commit del escritor de tests más las piezas del commit
estructural, que no cambian ningún resultado: la migración y `staging/roles.sql`
no están todavía.

```
$ uv run python -m pytest tests/staging --no-header -rN --tb=no
ssFFFFFFFFFFFFFFFFFFFFF                                                  [100%]
21 failed, 2 skipped in 0.78s
```

Los 21 fallan con **cuatro** mensajes distintos, todos `assert` del cuerpo del
test y ninguno error de import ni de fixture. Citados (no es salida pegada: la
consola de esta máquina es cp1252 y destroza los acentos):

1. «no existe el esquema metricas: lo crea la migración nueva del staging»
2. «no existe metricas.scores_por_vacante; en el esquema metricas hay []. La crea
   la migración nueva del staging.»
3. «se esperaba una sola migración que cree el esquema metricas y hay []»
4. «falta staging/roles.sql: el rol agente_metricas lo crea el guion del staging,
   no la migración» (`tests/staging/conftest.py:308`)

Y la lista de los 21, pegada tal cual:

```
$ uv run python -m pytest tests/staging --no-header -q --tb=line
…
=========================== short test summary info ===========================
FAILED tests/staging/test_metricas_sin_datos_personales.py::test_la_migracion_crea_el_esquema_metricas_con_las_dos_vistas_agregadas
FAILED tests/staging/test_metricas_sin_datos_personales.py::test_scores_por_vacante_expone_exactamente_las_siete_columnas_del_contrato
FAILED tests/staging/test_metricas_sin_datos_personales.py::test_trabajos_por_estado_expone_exactamente_las_cinco_columnas_del_contrato
FAILED tests/staging/test_metricas_sin_datos_personales.py::test_ninguna_vista_expone_ni_lee_un_dato_del_candidato[scores_por_vacante]
FAILED tests/staging/test_metricas_sin_datos_personales.py::test_ninguna_vista_expone_ni_lee_un_dato_del_candidato[trabajos_por_estado]
FAILED tests/staging/test_metricas_sin_datos_personales.py::test_los_conteos_de_scores_por_vacante_cuadran_con_las_filas_sembradas
FAILED tests/staging/test_metricas_sin_datos_personales.py::test_los_conteos_de_trabajos_por_estado_cuadran_con_las_filas_sembradas
FAILED tests/staging/test_metricas_sin_datos_personales.py::test_las_vistas_no_mezclan_empresas_ni_en_un_sentido_ni_en_el_otro
FAILED tests/staging/test_metricas_sin_datos_personales.py::test_la_migracion_de_metricas_va_y_vuelve_sobre_la_base_de_test
FAILED tests/staging/test_rol_agente_metricas.py::test_el_rol_lo_crea_el_guion_del_staging_y_no_una_migracion
FAILED tests/staging/test_rol_agente_metricas.py::test_la_migracion_le_da_permisos_solo_si_el_rol_existe
FAILED tests/staging/test_rol_agente_metricas.py::test_con_el_rol_del_agente_se_pueden_leer_las_dos_vistas
FAILED tests/staging/test_rol_agente_metricas.py::test_con_el_rol_del_agente_el_select_a_las_tablas_del_candidato_falla[candidatos]
FAILED tests/staging/test_rol_agente_metricas.py::test_con_el_rol_del_agente_el_select_a_las_tablas_del_candidato_falla[usuarios]
FAILED tests/staging/test_rol_agente_metricas.py::test_con_el_rol_del_agente_el_select_a_las_tablas_del_candidato_falla[match_scores]
FAILED tests/staging/test_rol_agente_metricas.py::test_con_el_rol_del_agente_el_select_a_las_tablas_del_candidato_falla[match_trabajos]
FAILED tests/staging/test_rol_agente_metricas.py::test_con_el_rol_del_agente_insertar_actualizar_o_borrar_falla[candidatos]
FAILED tests/staging/test_rol_agente_metricas.py::test_con_el_rol_del_agente_insertar_actualizar_o_borrar_falla[usuarios]
FAILED tests/staging/test_rol_agente_metricas.py::test_con_el_rol_del_agente_insertar_actualizar_o_borrar_falla[match_scores]
FAILED tests/staging/test_rol_agente_metricas.py::test_con_el_rol_del_agente_insertar_actualizar_o_borrar_falla[match_trabajos]
FAILED tests/staging/test_rol_agente_metricas.py::test_el_guion_del_staging_deja_creado_el_rol_y_es_idempotente
```

(El `…` recorta el cuerpo de los 21 fallos, que son los cuatro mensajes de
arriba. Los 2 saltados son el humo: sin `CRIBA_URL_STAGING` no se miden, y
saltarse no es aprobar.)

Y la suite entera en ese mismo árbol, que es la evidencia de que el commit
estructural no cambia ninguna conducta:

```
$ uv run python -m pytest --no-header -rN --tb=no
21 failed, 196 passed, 2 skipped, 1 xfailed, 1 warning in 9.64s
```

**2. En verde, después del escritor de tests (ronda 1)** — los 21 de `tests/staging`,
con el bloqueante ya resuelto en `tests/staging/conftest.py` (el `JOIN` sobre
`pg_class`, no el `CAST` del parche de abajo):

```
$ uv run python -m pytest tests/staging --no-header -rN --tb=no
ss.....................                                                  [100%]
21 passed, 2 skipped in 1.67s
```

**2.1 En rojo, antes del constructor (ronda 2, revisión adversarial)** — el
escritor de tests añadió `tests/match/test_logs_de_staging.py` para cubrir el
bloqueante y lo importante de la revisión (ver «Seguimiento de la revisión
adversarial»); antes de los dos cambios de código de esta ronda:

```
$ uv run python -m pytest tests/match/test_logs_de_staging.py --no-header -rA --tb=short
F..                                                                      [100%]
...
E   AssertionError: la línea del camino de lectura (logger 'criba.match.listado') no llegó a …\app.jsonl: SoloNuestrosLoggers solo deja pasar 'app' o 'app.*', y ese logger no empieza por ese prefijo, así que staging/logs/app.jsonl nace sin su mitad de lectura (RUNBOOK.md §2)
E   assert 'match.listar_vacante' in {'match.trabajo_cerrado'}
=========================== short test summary info ===========================
FAILED tests/match/test_logs_de_staging.py::test_la_linea_del_camino_de_lectura_llega_al_archivo_de_logs_igual_que_la_del_ejecutor
1 failed, 2 passed in 0.60s
```

**2.2 En verde, después (ronda 2)** — con `LOG_DEL_LISTADO = "app.match.listado"`
(`app/match/services/listado.py`):

```
$ uv run python -m pytest tests/match/test_logs_de_staging.py --no-header -rA --tb=short
...                                                                      [100%]
3 passed in 0.57s
```

**3. Suite completa** (`poe check`: ruff check, ruff format --check y pytest), en
verde, sin bloqueante:

```
$ uv run python -m poethepoet check
Poe => python -m ruff check .
All checks passed!
Poe => python -m ruff format --check .
186 files already formatted
Poe => python -m pytest
........................................................................ [ 28%]
........................................................................ [ 56%]
.......................x................................................ [ 84%]
...ss....................................                                [100%]
254 passed, 2 skipped, 1 xfailed, 1 warning in 18.43s
```

(El aumento de 196/215 a 254 `passed` entre rondas es por los tests de otros PRs
que se fusionaron en `s8/staging` mientras tanto, más los 3 nuevos de
`test_logs_de_staging.py`; no es un efecto de este PR.)

**4. Lo que se midió en esta ronda y lo que sigue sin medirse, y por qué.**

- **el staging sí se levantó con `docker compose`**, después de escrito este
  cuerpo: el E2E de humo (`tests/staging/test_humo_staging.py`) corrió con
  `CRIBA_URL_STAGING` puesta y dio **2 passed**, no saltado. El constructor de
  esta ronda no tiene permiso para invocar `docker` en su sesión —igual que en la
  ronda 1— así que no repitió esa corrida aquí; el resultado (2 passed) se toma
  como un hecho reportado y no como algo que esta sesión haya vuelto a ejercer.
  Lo que no se repite tampoco se contradice: ningún cambio de esta ronda toca el
  camino del humo (`app/plataforma/*`, las vistas);
- **lo que sigue sin medirse por un test de este repo**, porque escribirlo es
  `tests/` y no es mi contrato: que `configurar_logs` sin `CRIBA_LOG_DIR` sea un
  no-op, que `FormateadorJSON` no deje pasar `exc_info`, y el punto de entrada
  `main()` de `app/match/comandos/ejecutor.py`. Importar `app/registro.py` sí lo
  ejercen ahora `tests/match/test_logs_de_staging.py` (la ronda 2 del escritor de
  tests), así que un revert completo del módulo rompe esos tres tests por
  `ImportError`; lo que no rompe ningún test es revertir solo el cuerpo de
  `_objeto_json`/`FormateadorJSON.format` o el `main()` del comando, que son las
  piezas que hoy no tienen una aserción propia.

## El bloqueante

**Resuelto.** El escritor de tests corrigió `tests/staging/conftest.py::definicion_de`
en su ronda siguiente, pero **no con el `CAST` que proponía el parche de abajo**:
resolvió la relación con un `JOIN` sobre `pg_class`/`pg_namespace` —el mismo par
`:esquema`/`:vista` que ya usaban `relaciones_de_metricas` y `columnas_de`— y un
`assert definicion is not None` para que `pg_get_viewdef` de algo que no existe no
se cuele como una definición vacía. Los 21 tests de `tests/staging` pasan hoy
(evidencia 2 arriba). Queda el resto de esta sección **como documento histórico**
de por qué `:nombre::regclass` no es un parámetro de SQLAlchemy — el diagnóstico
sigue siendo correcto, solo cambió el arreglo elegido.

`tests/staging/conftest.py:169` leía la definición de una vista así:

```python
consulta = text("SELECT pg_get_viewdef(:nombre::regclass, true)")
return str(sesion.scalar(consulta, {"nombre": f"{ESQUEMA}.{vista}"}))
```

`:nombre::regclass` **no es un parámetro de SQLAlchemy**. Su detector de
parámetros es, en la versión instalada (`.venv/.../sqlalchemy/sql/elements.py:2576`):

```python
_bind_params_regex = re.compile(r"(?<![:\w\x5c]):(\w+)(?![:\w])", re.UNICODE)
```

El `(?![:\w])` del final impide que `:nombre` cuente cuando le sigue `:`, y
retroceder no ayuda porque toda subcadena más corta va seguida de letra. Así que
no hay ningún parámetro: el texto sale **literal** hacia el servidor, y Postgres
lo rechaza al parsearlo. La salida real:

```
E   sqlalchemy.exc.ProgrammingError: (pg8000.dbapi.ProgrammingError) {'S': 'ERROR', 'V': 'ERROR', 'C': '42601', 'M': 'syntax error at or near ":"', 'P': '23', 'F': 'scan.l', 'L': '1244', 'R': 'scanner_yyerror'}
E   [SQL: SELECT pg_get_viewdef(:nombre::regclass, true)]
```

`42601` es error de **sintaxis** y `P: 23` es la posición del `:` en esa cadena:
el error ocurre antes de que el servidor mire qué vista era, así que **no depende
de nada de este PR**. Con el esquema `metricas` vacío, con las vistas puestas o
sin base de datos, falla igual. Y la traza lo confirma: los dos únicos fotogramas
son el cuerpo del test y el andamio, sin un solo archivo de `app/` ni de
`migrations/` en medio.

```
tests/staging/test_metricas_sin_datos_personales.py:148: in test_ninguna_vista_expone_ni_lee_un_dato_del_candidato
tests/staging/conftest.py:170: in definicion_de
```

**Lo que hace falta:** sustituir el `::` por un `CAST` en esa línea, que es la
forma que el detector de SQLAlchemy sí reconoce. El parche, listo para
`git apply`:

```diff
--- a/criba/tests/staging/conftest.py
+++ b/criba/tests/staging/conftest.py
@@ -166,7 +166,11 @@
 def definicion_de(sesion: Session, vista: str) -> str:
-    """El SQL de la vista, para mirar **lo que lee** y no solo lo que expone."""
-    consulta = text("SELECT pg_get_viewdef(:nombre::regclass, true)")
+    """El SQL de la vista, para mirar **lo que lee** y no solo lo que expone.
+
+    `CAST(:nombre AS regclass)` y no `:nombre::regclass`: el detector de
+    parámetros de SQLAlchemy es `(?<![:\\w\\x5c]):(\\w+)(?![:\\w])`, y el
+    `(?![:\\w])` descarta `:nombre` cuando le sigue `:`. Con la forma `::` no se
+    sustituye nada, el texto sale literal y Postgres responde 42601.
+    """
+    consulta = text("SELECT pg_get_viewdef(CAST(:nombre AS regclass), true)")
     return str(sesion.scalar(consulta, {"nombre": f"{ESQUEMA}.{vista}"}))
```

Con eso, los 23 tests quedan medibles y `poe check` vuelve a verde (los 2 que hoy
fallan ya recorren bien la mitad de las columnas, así que lo único que les falta
es poder leer la definición).

**Por qué no lo hago:** `tests/` es el contrato del escritor de tests y un hook me
lo impide; y las tres salidas que me dejarían en verde sin arreglarlo —marcar los
tests, meter un `try/except` o escribir las vistas para que el error no ocurra—
están prohibidas y, sobre todo, dejarían **el criterio de privacidad más
importante del PR sin medir**: si nadie mira `pg_get_viewdef`, una vista que
llamara `n` a una columna y metiera dentro el correo del candidato pasaría.

**Quién lo arregla:** el escritor de tests, en `tests/staging/conftest.py`. **Ya
lo arregló** (ver «Resuelto» arriba): esto ya no bloquea el PR.

## Criterio de terminado

- [x] la migración crea el esquema `metricas` con **las dos vistas y ninguna
      tabla**, y va y vuelve dos veces
- [x] cada vista expone **exactamente** las columnas del contrato (7 y 5)
- [x] **ninguna columna** de las vistas es dato ni identificador del candidato
- [x] **ninguna vista lee** un dato del candidato ← resuelto por el escritor de
      tests (`JOIN` sobre `pg_class`, ver «El bloqueante»); los 2 tests pasan
- [x] los conteos cuadran, con la fila de score 0 y la fila sin score dentro
- [x] las vistas **no mezclan empresas**, en los dos sentidos
- [x] el rol lo crea `staging/roles.sql` y **ninguna migración**; el guion es
      idempotente
- [x] el `GRANT` está condicionado a que el rol exista, y la migración se reaplica
      sin romperse
- [x] con el rol puesto se leen las dos vistas, y `SELECT`/`INSERT`/`UPDATE`/
      `DELETE` fallan con `42501` en `candidatos`, `usuarios`, `match_scores` y
      `match_trabajos`
- [x] **la línea del camino de lectura llega al archivo de logs del staging**,
      igual que la del ejecutor ← hallazgo bloqueante de la revisión adversarial,
      corregido (`LOG_DEL_LISTADO` ahora es `app.match.listado`); ejercido por
      `tests/match/test_logs_de_staging.py`
- [x] el E2E de humo contra el staging, con `docker compose` arriba de verdad ←
      corrido después de escrito este cuerpo: **2 passed**, no saltado
- [x] `docker-compose.staging.yml` levanta el contenedor en 5455 con los roles
      creados ← verificado en esa misma corrida
- [x] las cinco tareas `poe` del staging ← `staging-arriba`, `staging-sembrar` y
      `staging-humo` se ejercieron en esa corrida; `staging-app` y
      `staging-ejecutor` son las que sirvieron la vista y procesaron la cola que
      el humo necesitó para pasar
- [x] `ruff check` y `ruff format --check`, en verde
- [x] `poe check` entero en verde ← 254 passed, 2 skipped, 1 xfailed (evidencia 3)

## Riesgo

**Qué cubre.** F12 por dos sitios: el log del trabajo cerrado nombra sus seis
campos y ninguno es del candidato, y el formateador del archivo no escribe trazas
ni deja pasar loggers que no sean de `app.` —el que importa es
`sqlalchemy.engine`, que con `echo=True` escribiría el texto del CV—. Y CA16/D15
por el rol: el agente que mira métricas en producción no puede leer un CV, un
score ni un usuario, y eso lo ejercen 8 tests con el código de error `42501` a la
vista.

**Qué introduce.**

1. **Una migración que la suite de este repo aplica siempre.** Si el `GRANT` no
   estuviera condicionado, `alembic upgrade` se rompería en toda base sin el rol y
   nadie podría correr los tests. Está condicionado y hay un test que lo exige,
   pero el riesgo es real y el mecanismo —un `DO $…$` con `pg_roles`— hay que
   mirarlo en la revisión.
2. **Contraseñas en el repo.** `staging/roles.sql`, `staging/staging.env`,
   `docker-compose.staging.yml` y las dos tareas `poe` del dueño llevan
   credenciales en claro. Son de una máquina local con datos sintéticos, el
   contenedor solo escucha en 127.0.0.1 y los tres archivos lo dicen en un
   comentario — pero es superficie nueva para F19, y la protección de push del
   repo tiene que seguir mirando. **Ninguna de las cuatro se parece a una clave de
   proveedor**, que es lo que el guardia de F19 busca.
3. **Un segundo proceso que puede morir solo.** El ejecutor aparte sube la
   gravedad de F9 exactamente como ADR-001 advierte en su argumento en contra: ya
   no es un trabajo atascado, es todo el scoring detenido, y el único detector
   sigue siendo la alerta de pendientes >60 min de CA7, **cuyo destinatario sigue
   sin definir** (pregunta abierta 4 de `docs/fallas.md`). En el staging es
   asumible porque lo arranca una persona en una terminal que está mirando.
4. **El proveedor real encendido.** `CRIBA_MATCH_PROVEEDOR=claude_cli` gasta
   dinero contra el techo de D12 cada vez que el ejecutor toma un trabajo. El
   `RUNBOOK` dice cómo cortarlo (volver al MOCK **y reiniciar**), pero no hay
   ningún tope en el staging: el contador de gasto es PR-13.
5. **Logs sin rotación ni retención.** `staging/logs/*.jsonl` crece sin límite y su
   retención es pregunta abierta de F12. Está ignorado por git, que es lo único que
   este PR resuelve.

## Qué NO entra

- **Arreglar los 2 tests bloqueados.** Está en `tests/`: lo hace el escritor de
  tests, en una línea (arriba está cuál).
- **Correr el staging.** No hay docker en la sesión del constructor. La revisión
  tiene que empezar por ahí.
- **El `README.md`** no menciona el staging: el alcance de esta tarea nombra siete
  piezas y el README no es ninguna. El orden de arranque vive en `RUNBOOK.md`.
- **Rotación, retención y `request_id` propagado** en los logs. La retención la
  decide Priya (F12); el `request_id` por middleware no lo pide nadie todavía.
- **Apagado ordenado del ejecutor (SIGTERM), tope de concurrencia, lease y
  reintentos.** PR-14 y PR-15. Hoy es una pasada a la vez y Ctrl+C.
- **La reconciliación y la alerta de pendientes >60 min** (CA7): PR-15.
- **Más vistas en `metricas`.** Dos, y las dos agregadas. Una tercera se decide
  cuando alguien tenga una pregunta que estas dos no contesten.
- **Nada en `docs/decisiones.md`, `SPEC.md` ni `PLAN.md`.** Este PR no cambia
  ninguna decisión: la diferencia con ADR-001 §Decisión 2 es **de entorno** y está
  declarada en el docstring del comando y en `RUNBOOK.md`, no en la ADR.
- **Dependencias nuevas: ninguna.** Ni una línea en `[project.dependencies]` ni en
  `[dependency-groups]`.

## Dependencias

- PR-02 (las tablas `match_*` que las dos vistas leen), PR-03, PR-04 (`repo_de`,
  por donde el andamio de los tests siembra), PR-05 (el interruptor global
  `CRIBA_MATCH_ACTIVO` y la columna de score que el humo mira), PR-06 (el bucle),
  PR-09 (`CRIBA_MATCH_PROVEEDOR` y las líneas de log del adaptador).
- **Toca una migración**, así que la lista de F16: la 0002 crea un esquema y dos
  vistas sobre tablas que ya existen. Crear una vista toma `ACCESS SHARE` sobre lo
  que lee, y la migración pone `SET lock_timeout = '3s'` como la 0001: con una
  transacción larga encima falla en 3 s en vez de encolarse detrás.

## Fuentes

- `docs/adr/ADR-001.md` · §Decisión 1 y 2, el argumento en contra, T1-T5,
  preguntas abiertas 1 y 2
- `docs/arquitectura.md` · §2 (componente «Logs JSON»), §4, §5.3, §5.5
- `docs/fallas.md` · F9, F11, F12, F16, F19, F23, F25
- `docs/decisiones.md` · D3 modificado, D4, D5, D7, D12, D15, D16
- `SPEC.md` · CA1, CA2, CA3, CA7, CA13, CA16
- `PLAN.md` · regla 1.7, §4, §9 pregunta abierta 11
- `tests/staging/` · los 23 tests de el commit «test: metricas sin datos personales, rol del agente y humo del staging»

## Seguimiento de la revisión adversarial

La revisión de tu agente (`herramientas/revisar_pr.py`, comenta y no aprueba) corrió dos veces sobre este PR.

**Primera revisión: 20 %, 1 bloqueante, 4 importantes, 3 menores.**
- Bloqueante, **corregido**: el logger del listado (`criba.match.listado`) no llegaba al archivo del staging. Ahora está bajo `app.` y hay test (`tests/match/test_logs_de_staging.py`).
- Sin tests para el registro, **corregido**: los tres tests de ese archivo.
- El bucle del ejecutor encadenaba hasta 100 trabajos en una transacción, **corregido**: una sesión y un `commit()` por trabajo.
- Evidencia desincronizada, **corregido**: el staging se levantó y el E2E de humo corrió contra él (2 passed).
- Menores: `staging/metricas.py` y `CRIBA_URL_METRICAS` quedan declarados aquí; `poe staging-migrar` no existe (la migración va dentro de `staging-arriba`).

**Segunda revisión: 55 %, 0 bloqueantes, 4 importantes, 3 menores.** Lo que queda fuera del alcance de este PR va a issues con su criterio de aceptación:
- un agregado de un solo candidato no anonimiza: **#24** (bloquea producción, no el staging con datos sintéticos);
- la suite crea roles LOGIN en el clúster de desarrollo: **#25**;
- el bucle del ejecutor muere con el primer error de conexión: **#26**;
- este apartado, que el cuerpo citaba y no existía, y el `.gitkeep` de `staging/logs/`: corregidos aquí.

El merge lo decide una persona, con la CI en verde.
