# Incidente 001 · el proveedor caído no deja un cero en la vacante

> Cuerpo del PR, con la plantilla de `PLAN.md` §6.
> Arreglo del incidente 001 sobre el criterio de **PR-11** (CA13), y la mitad de
> operación que lo disparó.

## Declaración previa: el bug está sembrado a propósito

Las dos causas de este incidente **las sembramos nosotros para el curso**, y esto
no es un hallazgo del análisis: es parte del guion.

| Commit | Qué sembró | Por qué |
|---|---|---|
| el commit «cola: si el proveedor falla, el candidato no se queda sin fila en la vista» «cola: si el proveedor falla, el candidato no se queda sin fila en la vista» | el `score=0` en el camino de excepción de `una_pasada` | es un arreglo que suena razonable en su mensaje de commit y viola CA13; entró **sin un test que ejerciera el camino de error** (`git show --stat`: solo `ejecutor.py`) |
| el commit «staging: tope de tokens de salida del proveedor, para cortar gasto» «staging: tope de tokens de salida del proveedor, para cortar gasto» | `CLAUDE_CODE_MAX_OUTPUT_TOKENS=800` en `staging/staging.env` | un cambio de **operación**, desde un archivo de entorno que ningún test lee, que cambia la conducta del proveedor |

Ninguno de los dos es un error de alguien del equipo. Los dos están aquí para que
el ejercicio tenga un incidente con **dos causas** y para que se vea qué deja sin
proteger un camino de error sin test. El diagnóstico de la sesión de triage
(rol de producción, 22-nov) es el documento que los encontró; este PR es el
arreglo del código y de la configuración, en el orden que manda `RUNBOOK.md` §3:
dos causas, dos arreglos, en un solo PR pero en piezas separadas y declaradas.

## Qué pasó

A 7 pares candidato–vacante de Northstar les salió **score 0** en el staging. No
lo dijo el modelo: lo escribía nuestro código.

1. **La causa del cero (código, CA13).** El camino de excepción de `una_pasada`
   guardaba `score=0` con la razón «No se pudo evaluar automáticamente.»
   (`app/match/cola/ejecutor.py`, el commit «cola: si el proveedor falla, el candidato no se queda sin fila en la vista»). Como `guardar_score` marca
   `estado="listo"` cuando el score no es `None` (`match_repo.py:267`), para la
   vista de la vacante y para `metricas.scores_por_vacante` **era un score de
   verdad**. Viola CA13 (`SPEC.md:91-93`, «Sin score, nunca un cero») y CA6
   (`SPEC.md:63-65`, el candidato aparece en «Pendientes de score»), y es el
   escenario literal de F8: «si se guarda un 0, se viola CA13: un cero se lee
   como *no encaja*» (`docs/fallas.md:75`).
2. **La causa de los fallos (operación, F7).** `CLAUDE_CODE_MAX_OUTPUT_TOKENS=800`
   en `staging/staging.env` (el commit «staging: tope de tokens de salida del proveedor, para cortar gasto»), que `_entorno()` hereda al
   subproceso del CLI (`app/match/proveedor/cliente.py:215-219`, y no está en
   `VARIABLES_DEL_ANFITRION`, `:93-97`). Las 7 llamadas fallidas registraron
   `decision=codigo_de_salida` con latencias de 30–34 s: el CLI trabajó la
   llamada entera y **después** salió con código distinto de 0.

Las dos juntas: la 2 hacía fallar llamadas, la 1 convertía cada fallo en un cero
visible. Sin la 1 el mismo incidente se habría visto como candidatos en
«Pendientes de score» —ruidoso, pero honesto— y no como una enfermera con un 0.

**Alcance** (vistas de `metricas`, día 2026-11-22): 7 pares con cero falso, todos
de `empresa_id=1`; vacante 1 → 2 de 4, vacante 5 → 5 de 6; 7 de 19 trabajos en
`ErrorDelProveedor`. **Ningún dato cruzó entre empresas.** Agravante: como
`guardar_score` actualiza la fila del par (CA9(a)), un par con un score bueno que
se re-puntúa en el minuto del fallo **perdía el score bueno**.

## Qué cambia y por qué

| Pieza | Qué cambia |
|---|---|
| `app/match/cola/ejecutor.py` | el camino de excepción **ya no escribe ninguna fila de score**. El trabajo se cierra en `error` con su motivo —el nombre del tipo de la excepción cortado a `LARGO_DEL_MOTIVO`, nunca el mensaje (F12, D15)— y el par se queda **sin fila**, así que el candidato aparece en «Pendientes de score» por ausencia (CA6) |
| `staging/staging.env` | se **quita** `CLAUDE_CODE_MAX_OUTPUT_TOKENS=800` y queda un comentario con las tres razones por las que no es un tope de gasto |

Las tres razones del comentario de `staging.env`, porque son el motivo de quitarla
y no un adorno:

1. **no es un límite de dinero**, es un límite de la respuesta del modelo: con ella
   puesta la llamada se paga entera y además se pierde el resultado (código de
   salida ≠ 0 tras 30–34 s);
2. **el tope de gasto ya existe y vive en el adaptador**, por llamada y con tests:
   `TOPE_POR_LLAMADA_USD = "0.05"` (`app/match/proveedor/cliente.py:77-84`), ~6×
   lo medido por CV. El techo mensual de 1.500 USD de D12 es de PR-13, no de un
   `.env`;
3. `_entorno()` pasa todo `os.environ` al hijo menos tres marcas, así que una
   variable escrita en ese archivo **cambia la conducta del proveedor sin que
   ningún test la lea**. Ni código, ni test, ni documento la conocían.

## Tipo de cambio

- [ ] estructural (mover, renombrar, extraer, preparar — **sin cambio de conducta**)
- [ ] comportamiento
- [x] las dos cosas, en commits separados (estructurales primero)

| Commit | Qué hace |
|---|---|
| `estructural: los dos cierres en error del ejecutor se leen igual (incidente-001)` | `una_pasada` cierra en `error` por dos caminos (empresa sin activación y excepción del proveedor) y los escribía distinto; se inlinea la variable `fallido` para que los dos digan lo mismo. `poe check` idéntico antes y después |
| `comportamiento: un fallo del proveedor nunca se convierte en un score (incidente-001)` | la escritura del 0 fuera, y el tope de tokens fuera de `staging.env` |

## Tests primero

Los escribió el escritor de tests en el commit «test: el proveedor caído no escribe un cero ni pisa el score», **antes** de este código, y aquí
no se tocó ni uno (ni se marcó ninguno con skip o xfail):

- `tests/match/test_fallo_proveedor.py::test_un_error_tipado_del_proveedor_deja_el_trabajo_en_error_y_cero_filas_de_score`
  → CA13, F8 (los tres errores tipados del adaptador, enumerados por
  `__subclasses__`; «cero filas» aserciado **por empresa**, CA1)
- `tests/match/test_fallo_proveedor.py::test_un_fallo_del_proveedor_no_pisa_el_score_que_el_par_ya_tenia`
  → CA9(a), CA13 (el agravante del alcance)
- `tests/match/test_fallo_proveedor.py::test_con_el_proveedor_caido_la_vacante_responde_200_y_sin_un_numero_de_score`
  → CA6 (200 y ninguna celda de score con un número)
- `tests/match/test_fallo_proveedor.py::test_el_fallo_del_proveedor_no_deja_nada_que_la_otra_empresa_pueda_ver`
  → CA1, F34 (rutas enumeradas, 404 en los dos sentidos)
- `tests/match/test_sobre_de_error_del_cli.py::test_el_sobre_de_error_real_del_cli_no_deja_ni_un_cero_en_la_vacante`
  → CA13, F12, D15 (el sobre real del CLI con código de salida 1, por el
  adaptador configurado; y nada del sobre en el motivo ni en el log)
- `tests/match/test_sobre_de_error_del_cli.py::test_la_fixture_es_el_sobre_de_error_del_cli_y_no_lleva_datos_de_candidato`
  → la guardia de la fixture; es el único que ya estaba en verde

## Evidencia

Dos notas sobre cómo leer estos bloques, para que nadie los tome por editados:

- **las rutas son relativas al repo**; donde el `warnings summary` de pytest
  imprimía la ruta absoluta del `.venv` de esta máquina, está recortado con `…`;
- `addopts` ya trae `-q` (`pyproject.toml:47`), así que pasar `-q` otra vez es
  `-qq` y pytest **no imprime la línea de recuento**. Por eso el bloque 1 acaba
  en la última línea `FAILED` y el bloque 3 la trae: se corrió sin el `-q` extra.

**1. En rojo, antes del código** (en el commit «test: el proveedor caído no escribe un cero ni pisa el score», el commit del escritor de tests):

```
$ uv run python -m pytest tests/match/test_fallo_proveedor.py tests/match/test_sobre_de_error_del_cli.py --tb=no -q
FFFFFF.F                                                                 [100%]
=========================== short test summary info ===========================
FAILED tests/match/test_fallo_proveedor.py::test_un_error_tipado_del_proveedor_deja_el_trabajo_en_error_y_cero_filas_de_score[ErrorDelProveedor]
FAILED tests/match/test_fallo_proveedor.py::test_un_error_tipado_del_proveedor_deja_el_trabajo_en_error_y_cero_filas_de_score[RespuestaInvalidaDelProveedor]
FAILED tests/match/test_fallo_proveedor.py::test_un_error_tipado_del_proveedor_deja_el_trabajo_en_error_y_cero_filas_de_score[TiempoDeEsperaDelProveedor]
FAILED tests/match/test_fallo_proveedor.py::test_un_fallo_del_proveedor_no_pisa_el_score_que_el_par_ya_tenia
FAILED tests/match/test_fallo_proveedor.py::test_con_el_proveedor_caido_la_vacante_responde_200_y_sin_un_numero_de_score
FAILED tests/match/test_fallo_proveedor.py::test_el_fallo_del_proveedor_no_deja_nada_que_la_otra_empresa_pueda_ver
FAILED tests/match/test_sobre_de_error_del_cli.py::test_el_sobre_de_error_real_del_cli_no_deja_ni_un_cero_en_la_vacante
```

**El rojo por la razón correcta**, con el aserto que lo dice (recortado al `E` de
cada fallo; la consola de esta máquina imprime los acentos y las comillas
angulares como `�`, el texto real es el del archivo de test):

```
$ uv run python -m pytest tests/match/test_fallo_proveedor.py tests/match/test_sobre_de_error_del_cli.py
…
E   AssertionError: northstar-health: el proveedor fall� y se escribi� una fila de score igual: [(0, 'listo', None)]. CA13 dice que o hay score, o hay �sin score� con su motivo; un 0 con estado �listo� es un score que nadie calcul� (F8, `docs/fallas.md:75`)
tests\match\test_fallo_proveedor.py:151: AssertionError
E   AssertionError: el fallo del proveedor pis� el score que el par ya ten�a: la reclutadora abre la vacante y el candidato que ten�a 72 aparece con lo que escribi� el camino de excepci�n (CA9(a), CA13)
E   assert (0, 'listo', ...nte.',), None) == (72, 'listo',...uesto'), None)
E     At index 0 diff: 0 != 72
tests\match\test_fallo_proveedor.py:194: AssertionError
E   AssertionError: la vista de vacante: hay un n�mero en la celda de score de un candidato que nadie puntu� (['0']). Un cero se lee como �no encaja� (F8) y CA13 lo proh�be: o score, o �sin score� con motivo
tests\match\test_fallo_proveedor.py:241: AssertionError
E   AssertionError: northstar-health: el fallo del proveedor dej� una fila de score [(0, 'listo')], que es el cero falso del incidente 001 (CA13)
tests\match\test_fallo_proveedor.py:286: AssertionError
E   AssertionError: el c�digo de salida 1 del CLI acab� en una fila de score [(0, 'listo', ['No se pudo evaluar autom�ticamente.'], None)]. Es el cero falso del incidente 001: el sobre real del proveedor no trae ning�n score �trae su propio error� y CA13 dice que o hay score, o hay �sin score� con su motivo, nunca un cero en lugar de un score (F8, `docs/fallas.md:75`)
tests\match\test_sobre_de_error_del_cli.py:195: AssertionError
```

Los cinco asertos hablan de lo mismo: `[(0, 'listo', …)]`, la fila que nadie
calculó. Ninguno falla por un import, por una fixture ni por una firma.

**2. En verde, después:**

```
$ uv run python -m pytest tests/match/test_fallo_proveedor.py tests/match/test_sobre_de_error_del_cli.py --tb=no
........                                                                 [100%]
8 passed in 1.12s
```

**3. Suite completa** (`poe check`: ruff + formato + todos los tests, E2E incluido).

En rojo, antes (recortado al final; el bloque de `warnings summary` traía la ruta
absoluta del `.venv`):

```
$ uv run python -m poethepoet check
…
=========================== short test summary info ===========================
FAILED tests/match/test_fallo_proveedor.py::test_un_error_tipado_del_proveedor_deja_el_trabajo_en_error_y_cero_filas_de_score[ErrorDelProveedor]
FAILED tests/match/test_fallo_proveedor.py::test_un_error_tipado_del_proveedor_deja_el_trabajo_en_error_y_cero_filas_de_score[RespuestaInvalidaDelProveedor]
FAILED tests/match/test_fallo_proveedor.py::test_un_error_tipado_del_proveedor_deja_el_trabajo_en_error_y_cero_filas_de_score[TiempoDeEsperaDelProveedor]
FAILED tests/match/test_fallo_proveedor.py::test_un_fallo_del_proveedor_no_pisa_el_score_que_el_par_ya_tenia
FAILED tests/match/test_fallo_proveedor.py::test_con_el_proveedor_caido_la_vacante_responde_200_y_sin_un_numero_de_score
FAILED tests/match/test_fallo_proveedor.py::test_el_fallo_del_proveedor_no_deja_nada_que_la_otra_empresa_pueda_ver
FAILED tests/match/test_sobre_de_error_del_cli.py::test_el_sobre_de_error_real_del_cli_no_deja_ni_un_cero_en_la_vacante
7 failed, 218 passed, 2 skipped, 1 xfailed, 1 warning in 10.11s
Error: Sequence aborted after failed subtask 'check[2]'
```

En verde, después (el `warnings summary` es el aviso de Playwright que ya traía la
suite, con su ruta absoluta recortada):

```
$ uv run python -m poethepoet check
Poe => python -m ruff check .
All checks passed!
Poe => python -m ruff format --check .
159 files already formatted
Poe => python -m pytest
........................................................................ [ 31%]
........................................................................ [ 63%]
..................x.....................................ss.............. [ 94%]
............                                                             [100%]
============================== warnings summary ===============================
tests/e2e/test_humo.py::test_guion_1_un_cv_subido_se_puntua_con_el_mock_y_la_reclutadora_ve_el_score[chromium]
  …/_pytest/fixtures.py:1392: PytestRemovedIn10Warning: Session-scoped fixtures defined as instance methods are deprecated.
  …
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
225 passed, 2 skipped, 1 xfailed, 1 warning in 9.49s
```

De 7 rojos a 0, y **218 → 225 passed**: los 7 que pasaron son exactamente los 7
del incidente. Ningún test existente cambió de resultado, y los 2 `skipped` y el
`xfailed` son los mismos de antes (el humo del staging sin `CRIBA_URL_STAGING`).

**4. Mediciones · el criterio «ningún camino escribe `score = 0`»** de PR-11, con
el grep que ese criterio pide:

```
$ git grep -n "guardar_score(\|CLAUDE_CODE_MAX_OUTPUT_TOKENS" -- app staging
app/match/repositories/match_repo.py:234:    def guardar_score(
app/match/services/scoring.py:96:        return self._repo.guardar_score(
staging/staging.env:67:# **`CLAUDE_CODE_MAX_OUTPUT_TOKENS` se quitó** (incidente 001, 22-nov). Estuvo
```

Lo que dice: en todo `app/` queda **un solo llamador** de `guardar_score`, el de
`MatchService.puntuar` (`scoring.py:96`), que es el camino validado y el único que
puede escribir un número; el ejecutor ya no escribe scores. Y la única aparición
de la variable de operación en `app/` y `staging/` es el comentario que explica
por qué no está. (Sigue apareciendo en `tests/`: en la fixture del sobre real del
CLI y en la lista de piezas que el test prohíbe copiar al log. Ahí tiene que
estar.)

**Lo que no se midió aquí, y es de operación, no de este PR:** la verificación
del `RUNBOOK.md` §4 contra el staging —`metricas.scores_por_vacante` con
`n_score_cero = 0`, `trabajos_por_estado` sin `ErrorDelProveedor` nuevos y
`poe staging-humo`— necesita el staging levantado, reiniciar los dos procesos
para que la variable deje de estar en su entorno, y limpiar las 7 filas sucias.
Las tres cosas tienen dueño en el postmortem y ninguna es código.

## Criterio de terminado

- [x] los 7 tests del escritor de tests en verde, y el 8.º (la guardia de la
      fixture) sigue en verde;
- [x] `poe check` completo en verde: ruff, formato y 225 passed, 2 skipped,
      1 xfailed;
- [x] **ningún camino de `app/` escribe `score = 0`**: un solo llamador de
      `guardar_score`, el de `MatchService.puntuar` (grep arriba);
- [x] un fallo del proveedor **no pisa** el score que el par ya tenía (CA9(a));
- [x] el trabajo queda en `error` **con motivo**, y el motivo no cita el mensaje
      de la excepción ni nada del sobre del CLI (F12, D15);
- [x] la vista de la vacante responde 200 con el candidato dentro y sin un número
      en su celda de score (CA6);
- [x] nada cruza entre empresas: 404 en los dos sentidos sobre las rutas
      enumeradas, y «cero filas» aserciado por empresa (CA1);
- [x] `CLAUDE_CODE_MAX_OUTPUT_TOKENS` fuera de `staging/staging.env`, con el
      comentario de por qué no es un tope de gasto;
- [x] `tests/` sin tocar, ningún skip ni xfail nuevo, cero dependencias nuevas;
- [x] commits `estructural:` y `comportamiento:` separados, el estructural con
      `poe check` idéntico antes y después.

## Riesgo

**Lo que cubre:**

- **F8** (`docs/fallas.md:75`, S3×P4=12) en su mitad «si se guarda un 0 se viola
  CA13». La otra mitad de F8 —validar la respuesta del modelo: JSON inválido,
  score fuera de rango, número de razones— es el PR-11 completo y **no entra
  aquí**;
- **F33** (caída normal del proveedor, S2×P4=8) y su criterio CA6, que era «lo
  mejor cubierto del diseño» (`docs/fallas.md`, conclusión 5) y hasta hoy no
  tenía ni un test: `tests/match/test_fallo_proveedor.py` no existía.

**Lo que este PR introduce:** un trabajo que cierra en `error` y **nadie
re-encola**. El par se queda sin fila de score indefinidamente hasta que haya
reintentos (PR-14) o un re-encolado. Es el riesgo que la pregunta abierta de
abajo nombra, y es estrictamente mejor que el anterior: antes el par quedaba con
un número falso y `estado="listo"`, que para CA20 cuenta como cobertura y para la
reclutadora cuenta como «no encaja».

**F7 queda sin cubrir, y a propósito** (S3×P4=12, `docs/fallas.md:74`). Este PR
quita la variable que la disparó; **no** añade ningún control sobre el tope de
tokens. Esa fila está declarada «sin test mientras el tope no se decida» y su
pregunta abierta la deciden **Víctor con Tomás** (`docs/fallas.md:140`,
pregunta 7 de `PLAN.md` §9). Mientras no se decida, nada impide que otra variable
de operación vuelva a cambiar la conducta del proveedor sin que un test lo note.

## Qué queda abierto

**1. Qué estado ve el reclutador mientras PR-14 decide los reintentos.
Pregunta abierta de PR-14, y este PR no la decide.** Está escrita en el código,
en el propio camino de excepción (`app/match/cola/ejecutor.py`).

Hoy el trabajo sale de `pendiente` y se cierra en `error`, y el par se queda sin
fila, así que el candidato aparece en «Pendientes de score» por ausencia (CA6).
La tabla de estados de `PLAN.md` PR-11 quiere otra cosa para una causa
transitoria: **`pendiente` con reintentos acotados** y, al agotarlos, «sin score
con motivo técnico» marcado como re-encolable (CA20 exige el 100 % de candidatos
«con score o con un motivo registrado»). Las dos mitades necesitan el lease y el
contador de intentos de **PR-14**: dejarlo `pendiente` hoy lo haría tomarse en
cada pasada —`pasadas` giraría hasta el `maximo`— y lo metería para siempre en la
alerta de >60 min de CA7. Lo único que CA13 no deja negociar es lo que sí hace
este PR: ninguna fila de score con un número que nadie calculó.

**2. Si se queda un tope de tokens, ¿quién lo pasa?** Pregunta abierta 1 de
`docs/fallas.md:140` (F7). Si se quiere, primero la medición que esa fila pide
—cuántos CVs superan el tope, y subir el tope por encima del máximo real— y
después que lo pase **el adaptador explícitamente**, con su test, o que se
excluya del entorno del hijo en `VARIABLES_DEL_ANFITRION` (`cliente.py:97`).
**Deciden Víctor y Tomás.**

**3. Las 7 filas sucias siguen en la base del staging.** Se identifican por
`score=0` con la razón exacta «No se pudo evaluar automáticamente.»; hay que
pasarlas a «sin score» y re-encolar los pares. Necesita el rol dueño de la
base, que ni este PR ni el rol de producción tienen. Es operación, con dueño y
fecha en el postmortem, y desde la ronda 1 de revisión (I2, abajo) ya no es un
párrafo sin mecanismo: es `staging/remediar_incidente_001.sql`, filtrado por
empresa y por la razón exacta, con un bloque de solo lectura para verificar el
alcance antes de tocar nada y sin `COMMIT` automático. **Este PR no lo
ejecuta.**

**4. El postmortem, dentro de 48 h y sin nombres.** Lo que falló no es el 0: es
que el commit «cola: si el proveedor falla, el candidato no se queda sin fila en la vista» entró sin un test que ejerciera el camino de error y que el commit «staging: tope de tokens de salida del proveedor, para cortar gasto»
cambió la conducta del proveedor desde un archivo que ningún test lee. El primero
ya tiene remedio en el repo (`tests/match/test_fallo_proveedor.py`); el segundo
es la pregunta 2 de esta lista.

## Qué NO entra

- **PR-11 completo.** Este PR arregla el camino de excepción del **ejecutor** y
  nada más. La validación de la respuesta del modelo (JSON inválido, score 120,
  cuatro razones, ninguna, idioma equivocado), el CV con instrucciones inyectadas
  (F24) y la **tabla de estados** caso por caso son PR-11 y siguen pendientes.
  `tests/match/test_sin_score.py` —el archivo que CA13 nombra para el caso del
  dato (CV sin texto extraíble, vacante sin descripción)— **sigue sin existir**:
  es de PR-11, no del incidente, y el escritor de tests no lo trajo.
- **Los reintentos, el lease y la salida tras agotarlos:** PR-14 (y PR-15 para la
  reconciliación y la alerta de pendientes >60 min de CA7).
- **El motivo visible en la vista y la sección «Pendientes de score» de CA8:**
  PR-20. Por eso los tests asercian «ninguna celda de score con un número» y no
  «la celda dice tal cosa»: el texto todavía no existe.
- **Cualquier control sobre el tope de tokens (F7):** bloqueado en una decisión de
  Víctor con Tomás, pregunta 2 de arriba.
- **Correr `staging/remediar_incidente_001.sql` y reiniciar los procesos del
  staging:** operación, no código. El script se escribe y se declara aquí; lo
  corre el rol dueño. Pregunta 3 de arriba.
- **La migración de `estado_trabajo`.** El `error` con el que cierra este camino
  es uno de los cuatro valores que la 0001 admite; añadir un estado nuevo es
  migración y decisión, y las dos son de PR-14.
- **Nada en `docs/decisiones.md`, `SPEC.md` ni `PLAN.md`.** Este PR no cambia
  ninguna decisión: aplica CA13, que ya estaba escrita desde la spec.

## Ronda 1 de revisión (revisor-pr, confianza 86, veredicto «corregir»)

Tres hallazgos. Los tres resueltos; ninguno rechazado sin dejar algo escrito.

**I2 — corregido.** La remediación de los 7 ceros falsos no tenía mecanismo,
solo el párrafo 3 de «Qué queda abierto». Ahora es
`staging/remediar_incidente_001.sql` (commit `herramientas:` de esta ronda):
filtrado por `empresa_id` y por la razón exacta (comparación `=`, no `ILIKE`,
para no arrastrar otro motivo que empiece igual), con un bloque de solo
lectura primero para verificar que son 7 filas antes de tocar nada, y la
remediación en una transacción sin `COMMIT` automático. Pasa las filas sucias
a «sin score» con motivo (CA13) y reabre a `pendiente` el trabajo en `error`
del mismo par —no inserta uno nuevo: `uq_match_trabajos_idempotencia`
(`empresa_id`, `clave_idempotencia`) chocaría con el que ya existe para ese
CV—. **Este PR no lo ejecuta**: lo corre el rol dueño, y queda en el
postmortem con su fecha. Un score bueno que el bug haya pisado no tiene
vuelta: no existe en la base, y el script no finge que la tiene.

**M1 — bloqueado, no corregido.** La instrucción pedía anotarlo como pregunta
abierta de PR-14 **en `PLAN.md`**. El propio rol de constructor tiene escrito,
en su definición (`.claude/agents/constructor.md`): «Lo que NO haces, aunque
te deje en verde: … editar `docs/decisiones.md`, `SPEC.md` o `PLAN.md`», sin
excepción para «es solo anotar una pregunta». Editar `PLAN.md` desde esta
sesión viola esa regla con la misma letra con la que esta sesión les exige a
los hallazgos I1/I2 no ampliar el alcance por su cuenta. No lo hice. Lo que
M1 señala **ya está escrito** —no en `PLAN.md`, pero sí en el repo, por dos
caminos que no necesitan tocar ese archivo—: el comentario del camino de
excepción en `app/match/cola/ejecutor.py` (línea ~118, «Pregunta abierta, de
PR-14 y no de aquí: qué ve el reclutador mientras tanto») y el punto 1 de
«Qué queda abierto» de este mismo documento. Si la pregunta tiene que vivir
también en `PLAN.md` §9 como una fila nueva (junto a la 7, la de F7), es un
cambio de ese archivo y lo decide quien pueda editarlo —el rol de producción
o un PR dedicado a `PLAN.md`—, no el constructor de este PR.

**I1 — decidido.** El hallazgo es real: el commit «comportamiento: un fallo del proveedor nunca se convierte en un score» mezcla el arreglo
de código (`ejecutor.py`) y el de `staging/staging.env` en una sola pieza, así
que revertir uno sin el otro no es un solo comando. La forma más limpia de
corregirlo sería separar ese commit en dos con un `git reset --soft` seguido
de dos commits nuevos; **esta sesión no lo hizo** porque la herramienta de
este entorno bloquea `git reset` sin aprobación interactiva, y no hay forma de
dar esa aprobación desde aquí sin arriesgar una reescritura a ciegas de una
rama que no es mía en exclusiva. Reescribir historia no es la única forma de
resolver «por qué importa» (la reversión ambigua): **la resolución que sí
puedo hacer sin tocar el historial es documentar aquí mismo, explícitamente,
el camino de reversión parcial de cada pieza**, para que nadie tenga que
adivinarlo ni revertir las dos juntas:

```bash
# revertir SOLO el código del ejecutor (deja staging.env como está):
git checkout el commit «comportamiento: un fallo del proveedor nunca se convierte en un score»^ -- app/match/cola/ejecutor.py

# revertir SOLO el cambio de staging.env (deja ejecutor.py como está):
git checkout el commit «comportamiento: un fallo del proveedor nunca se convierte en un score»^ -- staging/staging.env
```

Y la recomendación para el siguiente incidente con dos causas, para que esto
no se repita: el arreglo de código y el de operación van en **commits
separados desde el primer intento** (uno por causa, como `RUNBOOK.md` §3
pide), no en una sola pieza declarada en dos filas de una tabla. Sobre si el
cambio de `staging.env` debería haber entrado por un PR de código en absoluto
en vez de solo quedar anotado en el postmortem (la lectura más estricta de
`RUNBOOK.md` §3, «si el arreglo es de operación … va al postmortem con dueño y
fecha»): se queda en el PR, con esta justificación — a diferencia de exportar
una variable a mano o reiniciar un proceso (los ejemplos de esa frase),
`staging.env` es un archivo **versionado** del repo, y el valor que se quita
lo puso un commit normal (el commit «staging: tope de tokens de salida del proveedor, para cortar gasto», «staging: tope de tokens…», sin pasar por
ningún postmortem); tratarlo distinto solo porque esta vez el valor era
incorrecto —en lugar de una decisión que alguien pueda discutir— trataría el
canal de corrección como más estricto que el canal del error.

## Dependencias

- el commit «test: el proveedor caído no escribe un cero ni pisa el score» (los tests, del escritor de tests), PR-06 (el bucle), PR-09 (el
  adaptador y sus errores tipados), PR-10 (el contexto de empresa desde la fila).
- **Sin migración**, así que no hay lista de comprobación de bloqueo de F16.
- **Sin dependencias nuevas**: `pyproject.toml` no se toca.

## Fuentes

- `SPEC.md:91-93` (CA13), `SPEC.md:63-65` (CA6), `SPEC.md:75-77` (CA9),
  `SPEC.md:43-45` (CA1).
- `docs/fallas.md:75` (F8), `:74` (F7), `:106` (F33), `:116` y `:140`
  (F7 sin test y su pregunta abierta 1).
- `PLAN.md` §3 PR-11 (objetivo, tabla de estados y criterio «ningún camino que
  escriba `score = 0`»), §8 (CA6 y CA13 → PR-11), §9 pregunta 7 (F7, Víctor con
  Tomás), §6 (esta plantilla).
- `RUNBOOK.md` §3 («dos causas en un arreglo son dos arreglos», «si el arreglo
  es de operación … va al postmortem con dueño y fecha») y §4 (qué verificar
  antes de reencender).
- Diagnóstico de la sesión de triage del incidente 001 (rol de producción,
  22-nov-2026): las tres hipótesis, las refutaciones y el alcance.
- Commits sembrados a propósito: el commit «cola: si el proveedor falla, el candidato no se queda sin fila en la vista» (el cero) y el commit «staging: tope de tokens de salida del proveedor, para cortar gasto» (el tope de
  tokens).
- Ronda 1 de revisión (revisor-pr, 26-nov-2026, confianza 86): hallazgos I1,
  I2, M1, resueltos arriba. `.claude/agents/constructor.md` (la regla que
  bloquea M1) y `staging/remediar_incidente_001.sql` (I2).

## Salida real · verificación de esta ronda

Ningún test se tocó y ningún archivo de `app/` cambió en esta ronda (solo
`staging/remediar_incidente_001.sql`, nuevo, y este documento). `poe check`
antes y después de los commits de la ronda 1 es el mismo, **225 passed, 2
skipped, 1 xfailed**, porque la remediación de datos es un script que nadie
ejecuta en CI y no hay test nuevo que ejerza este archivo:

```
$ uv run python -m poethepoet check
Poe => python -m ruff check .
All checks passed!
Poe => python -m ruff format --check .
160 files already formatted
Poe => python -m pytest
........................................................................ [ 31%]
........................................................................ [ 63%]
..................x.....................................ss.............. [ 94%]
............                                                             [100%]
============================== warnings summary ===============================
tests/e2e/test_humo.py::test_guion_1_un_cv_subido_se_puntua_con_el_mock_y_la_reclutadora_ve_el_score[chromium]
  …/_pytest/fixtures.py:1392: PytestRemovedIn10Warning: Session-scoped fixtures defined as instance methods are deprecated.
  …
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
225 passed, 2 skipped, 1 xfailed, 1 warning in 10.31s
```

🤖 Generated with [Claude Code](https://claude.com/claude-code)
