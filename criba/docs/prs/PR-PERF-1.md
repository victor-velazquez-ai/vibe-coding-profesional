# PR-PERF-1 · La lista sin el texto del CV, el editor aparte y la respuesta comprimida

> Cuerpo del PR, con la plantilla de `PLAN.md` §6.

## Qué cambia y por qué

Los cambios **nº 1 y nº 3** de `perf/MEDICION.md` §6, y solo esos dos. La
medición del 22-nov dejó escrito dónde está el tiempo y los bytes de
`GET /vacantes/{id}` con 500 candidatos:

| # | Cambio | Evidencia que lo pide | Número que §6 espera mover |
|---|---|---|---|
| 1 | La lista deja de traer el `cv_texto`; el editor se pide aparte por HTMX | §5.1: la columna del CV son **10,5 ms** de los 24,9 ms de la consulta de la lista (medida 2 contra 3) y §5.2: **542.091 bytes** del cuerpo, para precargar un `<textarea>` por fila dentro de un `<details>` cerrado «que el reclutador casi nunca abre». La lista solo pinta su largo | p50 **−11 ms**, cuerpo **−542 KB** |
| 3 | La respuesta viaja comprimida cuando el navegador lo acepta | §5.2: «`app/fabrica.py` no monta ningún middleware de compresión, así que ese 1,52 MiB viaja tal cual». Es el único cambio de §6 que mueve la fila «página visible en celular, buena red: < 2 s» de la tabla de rendimiento de `SPEC.md` | cuerpo en el cable **1,52 MiB → ~150 KB**; p95 **+5 a +15 ms** de CPU |

Las dos restricciones que acotan el arreglo, citadas porque son las que hacen
que esto no sea paginación: **CA8** («ninguno queda oculto ni colapsado»,
`llamadas/2026-11-20-tomas.md` [03:57], F39) y **CA19** (la vista completa a 360
px). Aquí no desaparece ni una fila: las 500 siguen en la respuesta, con nombre,
score, contacto, largo del CV, etapa y fecha. Lo que deja de viajar es **una
columna que la lista nunca mostró**.

El editor es una ruta nueva de la plataforma, así que arrastra lo de siempre:
el `empresa_id` sale de la cookie y nunca de la URL, así que un candidato de otra
empresa es **404** (CA1, D4, [03:03]); pide `SesionQueEscribe`, así que el hiring
manager —de solo lectura, D10— recibe **403** y su fila no trae el pedido
(CA18, F34); y guardar sigue siendo el mismo `POST /candidatos/{id}/cv`, el
gancho de PR-06 (alcance 7, CA9(a)).

**No se mide nada en este PR.** El servidor de medición corre con el código de
antes y lo reinicia un humano: la medición de después es el paso siguiente. Los
números de la tabla de arriba son las **estimaciones** de §6, no resultados.

## Tipo de cambio

- [ ] estructural (mover, renombrar, extraer, preparar — **sin cambio de conducta**)
- [ ] comportamiento
- [x] las dos cosas, en commits separados (estructurales primero)

| Commit | Qué |
|---|---|
| `ca194bf` **estructural** | El formulario del CV sale de `_candidatos.html` a `_editor_cv.html` y la fila lo incluye. Mismo marcado, misma ruta de guardado. Evidencia: `check` da **el mismo resultado antes y después** (8 failed, 196 passed, 1 xfailed), sin tocar `tests/` |
| `e28ca36` **comportamiento** | Cambio nº 1: `candidatos_de_vacante` proyecta columnas y `length(cv_texto)`; `CandidatoDeLista` en vez de `Candidato`; `GET /candidatos/{id}/cv` y el `hx-get` de la fila |
| `076a6c8` **comportamiento** | Cambio nº 3: `GZipMiddleware` en `app/fabrica.py` (una línea) |

Diff de producción: **6 archivos, 148 insertions, 21 deletions**. Ni una línea
en `tests/`, `migrations/`, `SPEC.md`, `PLAN.md` ni `docs/decisiones.md`.

## Tests primero

Los escribió el escritor de tests en `f57d507`, antes de este código, y no se
tocaron:

- `tests/match/test_lista_sin_cv_texto.py::test_abrir_la_vacante_no_trae_el_cv_texto_de_ningun_candidato` → §6 nº 1 (primera mitad) + CA8
- `…::test_el_editor_de_cv_se_pide_aparte_y_ese_pedido_si_trae_el_texto` → §6 nº 1 (segunda mitad): que exista el pedido **y que sea perezoso**
- `…::test_el_editor_de_cv_de_otra_empresa_responde_404_en_las_dos_direcciones` → CA1, D4, F4
- `…::test_el_hiring_manager_no_recibe_el_editor_de_cv_ni_puede_pedirlo` → CA18, D10, F34
- `…::test_subir_un_cv_sigue_funcionando_y_el_fragmento_tampoco_trae_el_texto` → alcance 7, CA9(a)
- `tests/match/test_compresion.py::test_la_vista_de_vacante_va_comprimida_cuando_el_navegador_acepta_gzip` → §6 nº 3
- `…::test_sin_accept_encoding_la_misma_vista_va_sin_comprimir_y_con_el_mismo_html` → §6 nº 3 (la otra mitad: el mismo HTML)
- `tests/e2e/test_editor_de_cv.py::test_la_lista_no_lleva_el_cv_y_el_editor_llega_al_abrir_el_details` → §6 nº 1 por la interfaz real, con Chromium

Dos cosas que los tests **no** fijan y que por tanto eligió quien construye: la
ruta del endpoint (los tests la leen del `hx-get` de la fila) y cómo se dispara
el pedido. Están abajo, en «Tres decisiones de construcción».

## Evidencia

Las rutas de la salida de pytest van **relativas al repo**: se quitó el prefijo
de la máquina de las líneas de `--tb=line` y de la de aviso, igual que
`perf/MEDICION.md` §3.1 hizo con sus líneas de log. Lo demás es literal.

**1. En rojo, antes del código** (los 8, cada uno por su propio assert):

```
$ uv run python -m pytest tests/match/test_lista_sin_cv_texto.py tests/match/test_compresion.py tests/e2e/test_editor_de_cv.py -q --no-header --tb=line
FFFFFFFF                                                                 [100%]
================================== FAILURES ===================================
E   AssertionError: la vista sigue trayendo el texto del CV de la lista
    assert 'CENTINELA-CV' not in '<!doctype h...dy>\n</html>'

      'CENTINELA-CV' is contained here:
         required>CENTINELA-CV-11 · texto de relleno. texto de relleno. …</textarea>
      ?           ++++++++++++
                              </div>
                              <button class="btn btn--primary btn--sm" type="submit">Guardar CV</button>
          ...

      ...Full output truncated, use '-vv' to show
tests/match/test_lista_sin_cv_texto.py:108: AssertionError: la vista sigue trayendo el texto del CV de la lista
E   AssertionError: la fila del candidato 15 declara 0 `hx-get`: el editor de CV no se pide aparte (perf/MEDICION.md §6 nº 1)
    assert 0 == 1
     +  where 0 = len([])
tests/match/test_lista_sin_cv_texto.py:85: AssertionError: la fila del candidato 15 declara 0 `hx-get`: el editor de CV no se pide aparte (perf/MEDICION.md §6 nº 1)
E   AssertionError: la fila del candidato 27 declara 0 `hx-get`: el editor de CV no se pide aparte (perf/MEDICION.md §6 nº 1)
    assert 0 == 1
     +  where 0 = len([])
tests/match/test_lista_sin_cv_texto.py:85: AssertionError: la fila del candidato 27 declara 0 `hx-get`: el editor de CV no se pide aparte (perf/MEDICION.md §6 nº 1)
E   AssertionError: la fila del candidato 41 declara 0 `hx-get`: el editor de CV no se pide aparte (perf/MEDICION.md §6 nº 1)
    assert 0 == 1
     +  where 0 = len([])
tests/match/test_lista_sin_cv_texto.py:85: AssertionError: la fila del candidato 41 declara 0 `hx-get`: el editor de CV no se pide aparte (perf/MEDICION.md §6 nº 1)
E   AssertionError: el fragmento de la lista sigue trayendo el texto del CV
    assert 'CENTINELA-CV' not in '\n<div clas...\n  \n</div>'
      …
tests/match/test_lista_sin_cv_texto.py:240: AssertionError: el fragmento de la lista sigue trayendo el texto del CV
E   AssertionError: la respuesta viaja sin comprimir: `app/fabrica.py` no monta compresión
    assert None == 'gzip'
     +  where None = get('content-encoding')
     +    where get = Headers({'content-length': '31227', 'content-type': 'text/html; charset=utf-8'}).get
     +      where Headers({'content-length': '31227', 'content-type': 'text/html; charset=utf-8'}) = <Response [200 OK]>.headers
tests/match/test_compresion.py:49: AssertionError: la respuesta viaja sin comprimir: `app/fabrica.py` no monta compresión
E   AssertionError: sin compresión montada este test no ejerce nada (perf/MEDICION.md §6 nº 3)
    assert None == 'gzip'
     +  where None = get('content-encoding')
     +    where get = Headers({'content-length': '31227', 'content-type': 'text/html; charset=utf-8'}).get
     +      where Headers({'content-length': '31227', 'content-type': 'text/html; charset=utf-8'}) = <Response [200 OK]>.headers
tests/match/test_compresion.py:72: AssertionError: sin compresión montada este test no ejerce nada (perf/MEDICION.md §6 nº 3)
E   AssertionError: la vista sigue trayendo el texto del CV en la lista (perf/MEDICION.md §5.1)
    assert 'Enfermera t...no nocturno.' not in '<!DOCTYPE h...body></html>'
      …
tests/e2e/test_editor_de_cv.py:59: AssertionError: la vista sigue trayendo el texto del CV en la lista (perf/MEDICION.md §5.1)
============================== warnings summary ===============================
tests/e2e/test_editor_de_cv.py::test_la_lista_no_lleva_el_cv_y_el_editor_llega_al_abrir_el_details[chromium]
  .venv/Lib/site-packages/_pytest/fixtures.py:1392: PytestRemovedIn10Warning: Session-scoped fixtures defined as instance methods are deprecated.
  …
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
```

Recortes marcados con `…`: el texto de relleno de los CV **sintéticos** (que
además no va en un cuerpo de PR, D3 modificado, D15, F12), los bloques
«contained here» de dos de los fallos y el cuerpo del aviso de pytest.

**Nota honesta sobre esta salida**: no trae la línea de conteo
(`8 failed, …`). En esta máquina, cuando el módulo de E2E es **el último** en
cerrar la corrida, pytest no alcanza a imprimir su línea final; pasa igual en
rojo y en verde, y pasaba ya en la corrida del escritor de tests. El conteo está
en el bloque 3, donde el E2E no cierra la corrida.

**2. En verde, después** (el mismo comando, mismo orden de archivos):

```
$ uv run python -m pytest tests/match/test_lista_sin_cv_texto.py tests/match/test_compresion.py tests/e2e/test_editor_de_cv.py -q --no-header --tb=line
........                                                                 [100%]
============================== warnings summary ===============================
tests/e2e/test_editor_de_cv.py::test_la_lista_no_lleva_el_cv_y_el_editor_llega_al_abrir_el_details[chromium]
  .venv/Lib/site-packages/_pytest/fixtures.py:1392: PytestRemovedIn10Warning: Session-scoped fixtures defined as instance methods are deprecated.
  …
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
```

Y con nombre y conteo, por partes:

```
$ uv run python -m pytest tests/match/test_lista_sin_cv_texto.py tests/match/test_compresion.py --no-header -v
============================= test session starts =============================
collected 7 items

tests\match\test_lista_sin_cv_texto.py .....                             [ 71%]
tests\match\test_compresion.py ..                                        [100%]

============================== 7 passed in 1.30s ==============================
```

```
$ uv run python -m pytest tests/e2e --no-header -v -W ignore
============================= test session starts =============================
collected 5 items

tests\e2e\test_editor_de_cv.py .                                         [ 20%]
tests\e2e\test_humo.py ....                                              [100%]

============================== 5 passed in 4.13s ==============================
```

El E2E entero, no solo el guion nuevo: el **guion 1 del humo** rellena
`textarea[name='cv_texto']` después de abrir el `<details>`, así que es el que
dice que la subida de CV por la interfaz sigue funcionando con el editor cargado
por HTMX.

**3. Suite completa** (lint, formato y todos los tests, E2E incluido):

```
$ uv run python -m poethepoet check
Poe => python -m ruff check .
All checks passed!
Poe => python -m ruff format --check .
156 files already formatted
Poe => python -m pytest
........................................................................ [ 35%]
........................................................................ [ 70%]
...................x.........................................            [100%]
============================== warnings summary ===============================
tests/e2e/test_editor_de_cv.py::test_la_lista_no_lleva_el_cv_y_el_editor_llega_al_abrir_el_details[chromium]
  .venv/Lib/site-packages/_pytest/fixtures.py:1392: PytestRemovedIn10Warning: Session-scoped fixtures defined as instance methods are deprecated.
  …
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
204 passed, 1 xfailed, 1 warning in 34.46s
```

**204 = 196 + 8**: los 196 que ya pasaban antes de este PR, más los 8 nuevos. El
`xfailed` y el aviso de `pytest-playwright` son los de antes.

Y el mismo comando en el commit **estructural**, que es su evidencia:

```
$ uv run python -m poethepoet check          # en ca194bf
…
8 failed, 196 passed, 1 xfailed, 1 warning in 34.83s
Error: Sequence aborted after failed subtask 'check[2]'
```

Los 8 rojos son exactamente los 8 de PR-PERF-1 y fallan por el mismo assert que
antes del commit: el movimiento del formulario no cambió ninguna conducta.

**4. Mediciones: ninguna.** A propósito, y no por olvido: el servidor de
medición de `perf/MEDICION.md` §2 corre con el código de antes y lo reinicia un
humano. Los milisegundos y los bytes de «después» son un paso aparte, con el
mismo guion de §9 (`sembrar_carga` → `locust` → `perfil`) y sobre `criba_perf`.
Lo único con número que sale de esta sesión está dentro de la salida de arriba y
es del entorno de tests, con **12 filas y no 500**: el `content-length` de la
misma página era de **31.227 bytes** en el bloque de rojo. No es una medición de
CA5 y no se debe leer como tal.

## Tres decisiones de construcción que ningún documento fijaba

1. **La ruta del editor: `GET /candidatos/{candidato_id}/cv?vacante_id=…`.** El
   mismo camino que el `POST` que ya guarda ese CV, que es el nombre del recurso
   que se está editando. Los tests la leen del `hx-get` de la fila, así que no
   estaban comprometidos con ninguna. El `vacante_id` viaja como parámetro porque
   es la lista que el formulario repinta al guardar; **no se valida aquí** —este
   endpoint no lee nada de la vacante— y vuelve a resolverse con el contexto de
   empresa en el `POST`, que ya responde 404 si no es de la empresa.
2. **El disparo es `hx-trigger="toggle from:closest details once"`, no `load`.**
   Un `load` por fila cumpliría la letra del cambio —el texto saldría de la
   consulta de la lista— y haría 500 peticiones al abrir la vacante, que es peor
   que el problema de §5.1. `toggle` es el evento del propio `<details>`, así que
   funciona también abriéndolo con el teclado, y `once` evita un pedido por cada
   apertura.
3. **`tiene_cv` de la lista pasa a ser `largo_cv > 0`.** El `Candidato` del
   modelo lo define como `bool(cv_texto and cv_texto.strip())`, y eso ya no se
   puede evaluar sin el texto. Diferencia observable: un CV formado **solo** por
   espacios en blanco contaría ahora como «con CV» y pintaría su largo. No es
   alcanzable por la aplicación —`subir_cv` rechaza con 422 un `cv_texto` que
   queda vacío al recortarlo, y es el único camino a `guardar_cv`—, pero queda
   escrito aquí porque es el único cambio de conducta de este PR que ningún test
   pide. `Candidato.tiene_cv` sigue como está para quien sí tiene el texto.

## Criterio de terminado

- [x] Los 8 tests de `f57d507` en verde, sin tocar `tests/` (bloque 2). El diff de `tests/` entre `f57d507` y `HEAD` está vacío.
- [x] `uv run python -m poethepoet check` en verde: ruff, formato y la suite entera, E2E incluido (bloque 3).
- [x] **La vista no trae el `cv_texto` de ningún candidato**, ni la página ni el fragmento HTMX de la subida.
- [x] **La lista sigue completa**: el test asercia 13 filas renderizadas para 13 postulaciones (CA8, F39). No hay paginación, ni carga por tramos, ni filas colapsadas.
- [x] **El editor se pide aparte y solo al abrirlo**: un `hx-get` por fila y ningún `hx-trigger` de `load`.
- [x] **CA1 en las dos direcciones**: 404 y ningún dato del candidato ajeno, con sesión de Meridian sobre Northstar y al revés.
- [x] **CA18**: el hiring manager abre la vacante con 200 y su lista completa, su fila no declara el pedido, y el endpoint le responde 403.
- [x] **Subir un CV sigue funcionando** por el `POST` de siempre, en test y por la interfaz real (guion 1 del humo).
- [x] **Compresión negociada**: `gzip` cuando el cliente lo acepta, y con `identity` el **mismo HTML** sin cabecera de codificación.
- [x] Una sola consulta para la lista, con el conteo de notas correlacionado (F27): la proyección cambia las columnas, no el número de consultas.
- [x] Sin dependencias nuevas, sin migración y sin cambios en `docs/decisiones.md`, `SPEC.md` ni `PLAN.md`.

## Riesgo

**Lo que cubre.** F39 (S4×P3=12, paginar la lista de 500) por la vía contraria a
la tentadora: la respuesta se abarata **sin** quitar filas, que es lo que §6
exige («500 filas más baratas», no «menos de 500 filas»). F27 (S3×P3=9) se
mantiene: sigue siendo una consulta por lista. F34 (S3×P2=6): el endpoint nuevo
nace con control de rol y con test que lo asercia — y conviene decir que la
enumeración de rutas de CA18 recorre `/match`, así que a esta ruta de la
plataforma la cubre su test propio, no el recorrido.

**Lo que introduce**, con nombre:

1. **F36 (S2×P3=6), HTMX: el editor ahora depende de una segunda petición.** Si
   ese `hx-get` falla o llega a medias, la reclutadora ve el `<details>` abierto
   con «Abriendo el CV…» y nada más; antes el `<textarea>` ya estaba en la
   página. No hay camino de vuelta sin JavaScript —no hay una página de edición
   de CV a la que caer, y la recarga completa tampoco lo trae, porque la lista ya
   no lo lleva—. `docs/arquitectura.md` §2 dice «si falla el fragmento HTMX, el
   fallback es la recarga de la página completa»; para el editor, hoy eso no
   existe. Queda abajo, en «Qué NO entra».
2. **Una petición por `<details>` que se abre.** Es el canje explícito de §6 nº
   1: cero coste para las 500 filas que nadie abre, una petición ligera para la
   que sí. En el peor caso —una reclutadora abriendo muchas filas— son muchas
   peticiones pequeñas en vez de un cuerpo grande, y cada una resuelve **un**
   candidato por su clave primaria.
3. **Compresión = CPU en el camino de la petición.** §6 nº 3 lo estima en +5 a
   +15 ms de p95 y lo declara **no medido**; esta sesión tampoco lo mide. Si la
   medición de después muestra que el p95 se acerca al presupuesto de 300 ms de
   CA5, el middleware es una línea y se puede quitar o subirle el `minimum_size`
   sin tocar nada más.
4. **`CandidatoDeLista` es un tipo nuevo en la frontera con Match.**
   `FilaDeLista.candidato` ya no es un `Candidato` del ORM. Ninguna plantilla ni
   servicio le pedía más que `id`, `nombre`, `correo`, `telefono` y el largo del
   CV (`app/match/templates/match/_lista.html` solo pinta el nombre), y la suite
   entera lo confirma. El día que PR-20 necesite otra columna en la lista, hay
   que añadirla a la proyección: es el precio de que el ahorro no dependa de que
   la plantilla se acuerde.

## Qué NO entra

- **Los cambios nº 2, 4, 5, 6 y 7 de `perf/MEDICION.md` §6.** El nº 2 (no
  hidratar 499 `ScoreDeMatch` para quedarse con un `int`) es el siguiente por
  milisegundos por línea y toca `RepositorioDeMatch`; el nº 4 (el `<select>` con
  el padrón entero) y el nº 5 (un formulario por fila en vez de dos) siguen; el
  nº 6 es una migración; el nº 7 es **decisión de un humano** (`pyproject.toml`
  documenta que esta máquina bloquea el `.dll` de libpq de psycopg).
- **La medición de después.** Otro paso, con el servidor de medición reiniciado
  por un humano sobre el código de ahora (§9 de `perf/MEDICION.md`).
- **El fallback sin JavaScript del editor** (riesgo 1). Hoy el `<details>` sin
  HTMX no edita. Si se quiere, es una página propia de edición de CV o un
  `<textarea>` vacío que se envíe por formulario normal; ningún test lo pide y
  `SPEC.md` no lo exige, así que no se añade por cuenta propia.
- **CA19 a 360 px.** El marcado del editor es el mismo de antes dentro del mismo
  `<details>`, pero el ensayo a 360 px no tiene test automático en el repo
  todavía (llega en su paso del plan) y esta sesión no abrió un navegador a 360
  px.
- **Los «< 2 s en celular».** Objetivo y medición manual de la tabla de
  `SPEC.md`, no test (§5.2, §8 nº 5 de la medición). La compresión es lo que lo
  mueve; **nadie midió un teléfono** y este PR no lo afirma.
- **Bajar el `cv_texto` del `<select>` de «añadir un candidato»**, que §5.3
  describe: es el cambio nº 4 y trae decisión de interfaz (un buscador en vez de
  2.000 `<option>`).

## Dependencias

Ninguna nueva en `pyproject.toml`: `GZipMiddleware` viene con Starlette, que ya
es dependencia por FastAPI. Sin migración, así que no aplica la lista de
comprobación de bloqueo de F16. Encima de PR-01 a PR-10 y de la sesión de
medición (`34d8b52`); los tests son de `f57d507`.

## Fuentes

- `perf/MEDICION.md` §5.1, §5.2, §5.3, §6 (cambios nº 1 y nº 3), §8, §9
- `SPEC.md`: CA1, CA5, CA8, CA9(a), CA18, CA19, alcance 7, tabla «Rendimiento (números medibles)»
- `docs/decisiones.md`: D4 (punto único de acceso con `empresa_id` del contexto), D7, D10
- `docs/fallas.md`: F4, F27, F34, F36, F39
- `llamadas/2026-11-20-tomas.md` [00:16], [03:03], [03:57], [04:06]
- `docs/arquitectura.md` §2 (HTML en servidor, fallback a recarga completa), §4
- `PLAN.md` §4 (estructural contra comportamiento) y §6 (esta plantilla)

## Ronda 1 de revisión (revisor-pr, claude-fable-5-1): 80 %, 1 B · 1 I · 1 M → corregir

| Hallazgo | Qué se hizo |
|---|---|
| **B1** · la §10 de `perf/MEDICION.md` tenía números sin evidencia: un «antes con gzip» estimado como base de un porcentaje, un «−12 ms p50» que no salía de ninguna tabla, el perfil sin correr y la frase «corresponde exactamente al cambio nº 1» | **Corregido.** §10 rehecha solo con números medidos, cada uno con su archivo y su comando (`perf/resultados/perfil-despues.txt`, `perf/resultados/bytes-despues.txt`, `perf/resultados/despues*.csv`). Se declara que locust mide los cambios nº 1 y nº 3 juntos y que la corrección M1 no se volvió a medir. |
| **I1** · la proyección de la lista (sin `cv_texto`) no tenía ningún test | **Corregido en `tests/`** por el escritor de tests: un guardia que captura las sentencias de `GET /vacantes/{id}` y falla si alguna selecciona `candidatos.cv_texto` fuera de `length(`. |
| **M1** · `CandidatoDeLista.tiene_cv` (`largo_cv > 0`) divergía de `Candidato.tiene_cv` | **Corregido.** `Candidato.tiene_cv` pasa a `hybrid_property` y la lista la proyecta tal cual: la misma definición, calculada por Postgres. Test del escritor: un CV de solo espacios dice «sin CV» en la lista. |

Suite tras la corrección: 231 tests, 0 fallas (230 passed, 1 xfailed).
