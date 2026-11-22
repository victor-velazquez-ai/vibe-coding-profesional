# PR-QA-E2E · Los tres hallazgos de QA que se arreglan ahora

> Cuerpo del PR, con la plantilla de `PLAN.md` §6.

## Qué cambia y por qué

Los **tres** hallazgos que `qa/TRIAGE.md` (22-nov-2026) marca «se arregla ahora»,
cada uno con el cambio más chico que lo arregla de verdad. El E2E en rojo lo dejó
antes el escritor de tests en `39f3222`, como pide `CLAUDE.md` §7 («cada hallazgo
de QA que se arregla entra primero como E2E en rojo»), y **este PR no toca
`tests/`**.

| Hallazgo | Criterio / fuente | Archivo | El cambio |
|---|---|---|---|
| **QA frontend BUG-3** · la vacante desborda en horizontal a 360 px (`scrollWidth` 979 contra 360 en el informe) | CA19 (D22, RI1, `SPEC.md` §19), F15 (S4×P3=12) | `app/static/criba.css` | **una línea**: la pista de `.split` en una columna pasa de `1fr` a `minmax(0, 1fr)` |
| **QA backend BUG-2** · borrar con un `vacante_id` ajeno **borra igual** y responde 404 | `qa/reportes/2026-11-22-backend.md`, CA1 | `app/plataforma/repositorio.py`, `app/plataforma/rutas/candidatos.py` | guardia `exigir_vacante_del_borrado` **antes** del borrado; 404 sin efecto |
| **Issue #16** · redirección abierta en el login (`destino=//example.com`) | `qa/TRIAGE.md` §«lo que encontró el triage y no la QA» | `app/plataforma/sesion.py` | `ruta_interna` deja de aceptar «empieza por `/`» |

**Por qué cada uno es así, en una frase:**

1. **CA19.** `.table-wrap` ya tenía su `overflow-x: auto` desde el kit: lo que le
   faltaba era que alguien le diera un ancho que respetar. Con el mínimo de la
   pista en `auto`, la columna de grid tomaba el `min-content` de la tabla
   (~840 px) y la **página entera** se iba con ella —cabecera incluida—, en vez
   de dejar que la tabla se desplazara dentro de su contenedor. No se esconde
   ninguna columna: el score sigue visible, y el E2E lo asercia.
2. **BUG-2.** El formulario de borrado manda un `vacante_id` que afirma «estoy
   viendo a este candidato en esta vacante» (`_candidatos.html`), y nadie
   comprobaba la afirmación: el borrado se ejecutaba y **después** la respuesta
   fallaba con 404. El reclutador leía «aquí no hay nada» y lo que había pasado
   es que perdió al candidato, su CV y su postulación. De las dos salidas que la
   QA aceptaba, el triage eligió **no borrar nada y responder 404**.
3. **Issue #16.** `destino.startswith("/")` acepta `//example.com` y
   `/\example.com`, que el navegador lee como **otro dominio**: una URL de Criba
   decidía a qué sitio iba alguien después de un login legítimo. Ahora el
   `destino` se normaliza como lo normaliza el navegador (se borran tabulador, CR
   y LF; la barra invertida pasa a `/`) y solo manda si queda una ruta de Criba.
   Un `destino` interno se sigue respetando tal cual —BUG-5 **no era** un bug—,
   también el de otra empresa, que muere en el 404 de siempre (CA1).

## Tipo de cambio

- [ ] estructural
- [ ] comportamiento
- [x] **las dos cosas, en commits separados (estructurales primero)**

| Commit | Qué lleva | Líneas |
|---|---|---|
| `estructural:` `a9419fd` | extrae a `sesion.py` la expresión que `POST /entrar` tenía escrita a mano (`destino if destino.startswith("/") else "/vacantes"`) como `ruta_interna`, **con la regla de hoy**, y nombra `RUTA_POR_OMISION`, que tres sitios repetían | 16 (+), 4 (−) |
| `comportamiento:` `fbb7faa` | los tres arreglos: la línea de CSS, el guardia del borrado y la regla nueva de `ruta_interna` | 91 (+), 2 (−) |
| `docs:` (ronda 1) | este cuerpo, con los dos hallazgos de la revisión. **Sin cambio en `app/`:** los dos eran huecos de cobertura y los cerró el escritor de tests en `51c4f57` | solo `docs/` |

El diff del PR contra el commit de tests es de **106 inserciones y 5 borrados**
(los dos commits suman 107 y 6: una línea que el estructural escribe la vuelve a
tocar el de comportamiento). De esas 106, **52 son el guardia del borrado con su
docstring**. Lejos del límite de 400 de la regla 1.1 de `PLAN.md`.

```
$ git diff 39f3222 --stat -- app/
 criba/app/plataforma/repositorio.py         | 52 +++++++++++++++++++++++++++++
 criba/app/plataforma/rutas/autenticacion.py |  8 +++--
 criba/app/plataforma/rutas/candidatos.py    |  6 ++++
 criba/app/plataforma/sesion.py              | 37 +++++++++++++++++++-
 criba/app/static/criba.css                  |  8 ++++-
 5 files changed, 106 insertions(+), 5 deletions(-)
```

**El commit estructural no cambia ninguna conducta**, y eso es comprobable: con
él aplicado, el E2E del issue #16 sigue rojo **por la misma razón y con el mismo
mensaje** (`Location: //example.com`), y el resto de la suite da lo mismo. Es la
costura donde el segundo commit aprieta la regla: con la expresión en medio de un
`RedirectResponse`, el arreglo se habría escrito ahí dentro.

## Tests primero

Los tres archivos los escribió el escritor de tests en `39f3222`
(«Rol: escritor-tests»), y los dos de la ronda 1 de revisión en `51c4f57` (mismo
rol). **Este PR no los toca**: el diff de `tests/` contra el último de esos
commits está vacío.

```
$ git diff 51c4f57 --stat -- tests/
(sin salida)
```

| Test | Qué protege |
|---|---|
| `tests/e2e/test_qa_movil_360.py::test_la_vacante_no_desborda_en_horizontal_en_un_viewport_de_360_px` | CA19 · `scrollWidth <= clientWidth` a 360×640 con seis candidatos, **y** el score visible: esconder la tabla no es el arreglo |
| `tests/e2e/test_qa_movil_360.py::test_la_reclutadora_de_meridian_sigue_recibiendo_404_a_360_px` | CA1 · el arreglo de CA19 no puede servir un fragmento de móvil sin el guardia de empresa (nació verde; es regresión) |
| `tests/e2e/test_qa_borrado_con_vacante_ajena.py::test_borrar_con_un_vacante_id_ajeno_no_borra_nada_y_responde_404` (3 parámetros) | QA backend BUG-2 · las tres formas de que el `vacante_id` sea ajeno: inexistente, otra vacante de la empresa y vacante de Meridian. Primero «el candidato sigue en su vacante», después el 404 |
| `tests/e2e/test_qa_redireccion_abierta.py::test_el_login_respeta_un_destino_interno_y_nunca_sale_de_criba` | Issue #16 · `destino` interno respetado, `destino` interno ajeno respetado como ruta y muerto en 404, y `destino` que sale de Criba caído en `/vacantes`, en las dos formas (`//` y `/\`) y en los dos planos (cabecera `Location` y URL del navegador) |
| `tests/e2e/test_qa_borrado_con_vacante_ajena.py::test_borrar_un_candidato_sin_postulaciones_con_una_vacante_ajena_no_borra_nada_y_da_404` (2 parámetros) · **ronda 1, I1** | La **segunda** mitad del guardia: candidato sin postulaciones + vacante inexistente o de Meridian → 404 sin borrar. La huella se lee en la base (`sigue_en_la_base`), porque un candidato sin postulaciones no sale en ninguna lista de la interfaz |
| `tests/e2e/test_qa_borrado_con_vacante_ajena.py::test_meridian_no_borra_un_candidato_sin_postulaciones_de_northstar_ni_con_su_propia_vacante` · **ronda 1, I1** | CA1 · la mitad permisiva del guardia en la otra dirección: con **su propia** vacante Meridian pasa el guardia, y lo único que separa al candidato de Northstar del borrado es la comprobación de empresa de `borrar_candidato` |
| `tests/plataforma/test_ruta_interna.py` (15 parámetros) · **ronda 1, M1** | Issue #16 · unidad de la única puerta de la regla: doce `destino` que salen de Criba (tabulador, CR/LF, `///`, `/\`, esquema, `javascript:`, ruta relativa, cadena vacía) y tres internos que se respetan, incluido el de otra empresa |

## Evidencia

**1. En rojo, antes del código** (salida real del commit de tests `39f3222`; se
recortan con `…` los listados de código fuente que pytest repite y el aviso de
`pytest-playwright`, que es anterior a este paso):

```
$ uv run python -m pytest tests/e2e/test_qa_movil_360.py tests/e2e/test_qa_borrado_con_vacante_ajena.py tests/e2e/test_qa_redireccion_abierta.py
F.FFFF                                                                   [100%]
================================== FAILURES ===================================
_ test_la_vacante_no_desborda_en_horizontal_en_un_viewport_de_360_px[chromium] _
…
        medida = page.evaluate(MEDIDA_DEL_DOCUMENTO)
>       assert medida["scroll"] <= medida["cliente"], (
E       AssertionError: la página desborda a 360 px: scrollWidth 941 contra clientWidth 360 (CA19, QA frontend BUG-3). La tabla tiene que quedar contenida —su propio scroll horizontal—, no arrastrar la página entera.
E       assert 941 <= 360

tests\e2e\test_qa_movil_360.py:107: AssertionError
_ test_borrar_con_un_vacante_id_ajeno_no_borra_nada_y_responde_404[chromium-inexistente] _
…
_ test_borrar_con_un_vacante_id_ajeno_no_borra_nada_y_responde_404[chromium-vacante_de_meridian] _
…
        # Primero lo que importa: no se borró nada.
        assert abrir(page, servidor, f"/vacantes/{datos.vacante_id}") == 200
>       assert filas_con(page, candidato_de_northstar.nombre) == 1, (
E       AssertionError: QA backend BUG-2: el borrado se ejecutó con un vacante_id ajeno (vacante_de_meridian, vacante_id=3) y el candidato ya no está en su vacante. La respuesta fue 404: el servidor ejecutó la acción destructiva y le dijo al reclutador que aquí no hay nada.
E       assert 0 == 1
E        +  where 0 = filas_con(<Page url='http://127.0.0.1:55789/vacantes/1'>, 'Candidato sintético 3 del borrado')
E        +    where 'Candidato sintético 3 del borrado' = CandidatoSintetico(id=4, nombre='Candidato sintético 3 del borrado').nombre

tests\e2e\test_qa_borrado_con_vacante_ajena.py:163: AssertionError
__ test_el_login_respeta_un_destino_interno_y_nunca_sale_de_criba[chromium] ___
…
            location = _location_del_login(servidor, datos.reclutadora, destino)
            partes = urlsplit(location)
>           assert partes.scheme == "" and partes.netloc == "", (
E           AssertionError: redirección abierta (issue #16): el login con destino='//example.com' responde 303 con Location='//example.com', que saca al navegador de Criba. Una URL de Criba no puede decidir a qué dominio va alguien después de entrar.
E           assert ('' == '' and 'example.com' == ''
E            +  where '' = SplitResult(scheme='', netloc='example.com', path='', query='', fragment='').scheme
E             
E             + example.com)

tests\e2e\test_qa_redireccion_abierta.py:112: AssertionError
============================== warnings summary ===============================
…
=========================== short test summary info ===========================
FAILED tests/e2e/test_qa_movil_360.py::test_la_vacante_no_desborda_en_horizontal_en_un_viewport_de_360_px[chromium]
FAILED tests/e2e/test_qa_borrado_con_vacante_ajena.py::test_borrar_con_un_vacante_id_ajeno_no_borra_nada_y_responde_404[chromium-inexistente]
FAILED tests/e2e/test_qa_borrado_con_vacante_ajena.py::test_borrar_con_un_vacante_id_ajeno_no_borra_nada_y_responde_404[chromium-otra_vacante_de_la_empresa]
FAILED tests/e2e/test_qa_borrado_con_vacante_ajena.py::test_borrar_con_un_vacante_id_ajeno_no_borra_nada_y_responde_404[chromium-vacante_de_meridian]
FAILED tests/e2e/test_qa_redireccion_abierta.py::test_el_login_respeta_un_destino_interno_y_nunca_sale_de_criba[chromium]
5 failed, 1 passed, 1 warning in 5.07s
```

De los tres rojos del borrado solo se pega entero el del `vacante_id` de
Meridian: los tres fallan en la **misma** línea 163 y con el mismo mensaje, con
su `caso` y su `vacante_id` dentro. El que pasa (`1 passed`) es el de Meridian a
360 px, que nació verde.

**2. En verde, después** (salida real):

```
$ uv run python -m pytest tests/e2e/test_qa_movil_360.py tests/e2e/test_qa_borrado_con_vacante_ajena.py tests/e2e/test_qa_redireccion_abierta.py -v
============================= test session starts =============================
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function

tests\e2e\test_qa_movil_360.py ..                                        [ 33%]
tests\e2e\test_qa_borrado_con_vacante_ajena.py ...                       [ 83%]
tests\e2e\test_qa_redireccion_abierta.py .                               [100%]

============================== warnings summary ===============================
…
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 6 passed, 1 warning in 6.72s =========================
```

**3. Suite completa** (salida real **después de la ronda 1**; se recorta el aviso
de `pytest-playwright`):

```
$ uv run python -m poethepoet check
Poe => python -m ruff check .
All checks passed!
Poe => python -m ruff format --check .
160 files already formatted
Poe => python -m pytest
........................................................................ [ 32%]
........................................................................ [ 65%]
............x........................................................... [ 97%]
.....                                                                    [100%]
============================== warnings summary ===============================
…
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
220 passed, 1 xfailed, 1 warning in 13.48s
```

220 = los 202 de la ronda 0 (los 197 verdes que declaró el commit de tests + los
5 rojos de los tres hallazgos) **+ los 18 de la ronda 1** (15 parámetros de
`test_ruta_interna.py` y 3 tests del borrado sin postulaciones). El `x` es el
`xfail(strict=True)` de PR-08, de antes de este paso.

**4. Medición de CA19** (instrumentación temporal, **no es un test** y **no entra
en el repo**: un archivo de diagnóstico en la raíz, corrido con pytest para
reutilizar el andamio del E2E, borrado antes del primer commit; el control que
queda es el E2E). Mide lo mismo que CA19 y, además, enumera las cajas que
sobresalen del viewport:

```
$ uv run python -m pytest _medicion_360.py -s          # antes del arreglo
limite: 360 scrollWidth: 860
 - section.stack ancho=844 derecha=860 overflowX=visible
 - h2.section-title ancho=844 derecha=860 overflowX=visible
 - div.stack ancho=844 derecha=860 overflowX=visible
 - div.table-wrap ancho=844 derecha=860 overflowX=auto
 - table.table ancho=842 derecha=859 overflowX=visible
 …

$ uv run python -m pytest _medicion_360.py -s          # después
limite: 360 scrollWidth: 360
 - table.table ancho=842 derecha=859 overflowX=visible
 - thead. ancho=842 derecha=859 overflowX=visible
 …
```

Es la medición que decidió el arreglo y la que dice que es correcto, no solo que
el número baja: **antes**, `div.table-wrap` medía 844 px —su `overflow-x: auto`
no tenía nada que recortar, porque su propio ancho ya era el de la tabla—;
**después**, la única caja ancha es la `table`, que es la que tiene que
desplazarse dentro del contenedor. El `scrollWidth` del documento queda en 360,
igual que el `clientWidth`. (Los 860 de aquí contra los 941 del E2E son los seis
candidatos del guion contra los cinco del diagnóstico: el ancho lo fijan las
columnas, no las filas, pero los nombres sintéticos son más cortos.)

**4 bis. El arreglo de CA19 es de una línea, y se comprobó que no hace falta
más.** El primer intento llevaba **dos** cambios: `minmax(0, 1fr)` en la media
query y `.split > * { min-width: 0 }`. Quitando la segunda regla y dejando solo
la primera, el E2E sigue verde:

```
$ uv run python -m pytest tests/e2e/test_qa_movil_360.py --tb=line -rf
2 passed, 1 warning in 2.25s
```

La razón es la del propio algoritmo de grid: el mínimo automático de un item solo
se calcula desde su contenido si la pista que ocupa tiene mínimo `auto`, y
ninguna pista de `.split` lo tiene: las dos de escritorio ya eran
`minmax(0, 1.55fr)` y `minmax(21rem, 1fr)`, y la de una columna lo es desde este
PR. La regla de más
se borró: una línea de CSS que no cambia nada es exactamente el tipo de cosa que
nadie se atreve a quitar en seis meses.

## Ronda 1 de revisión: los dos hallazgos

| ID | Sev. | Qué pedía | Resultado | Diff en `app/` |
|---|---|---|---|---|
| **I1** | I | La segunda mitad de `exigir_vacante_del_borrado` (candidato sin postulaciones + vacante ajena → 404 sin borrar) no tiene test | **Real, cerrado con test** | **ninguno** |
| **M1** | M | `ruta_interna` no tiene test de unidad: `.translate(SIN_SALTOS)` y la guarda de `//` se pueden borrar con la suite en verde | **Real, cerrado con test** | **ninguno** |

**Los dos hallazgos eran reales y ninguno era un defecto de conducta.** El revisor
lo dice él mismo en M1 («la lógica actual es correcta para esos casos, pero no
está protegida») y en I1 su reproducción es condicional («si se borran las líneas
…»). El código ya hacía lo correcto en las dos ramas; lo que faltaba era la prueba
de que lo siga haciendo mañana. Eso es `tests/`, y lo escribió el escritor de
tests en `51c4f57`. **Este PR no cambia ni una línea de `app/`** en esta ronda, y
no se inventa un cambio para tener algo que mostrar: un arreglo que no arregla
nada es ruido en el diff y una mentira en el historial.

```
$ git status --short
$ git diff --stat
(sin salida: nada que commitear en app/)
```

**Por qué «cerrado» y no «ya estaba bien, no hay nada que hacer»:** un guardia que
nadie ejercita no es un guardia, es un comentario. La ronda 0 ya lo había anotado
como riesgo en su propia sección («es la única puerta de la regla»), así que el
hallazgo convierte una nota en un control. Lo que sigue es la prueba de que los
tests nuevos **sí** sujetan esas líneas, con el experimento que pedía cada
hallazgo: se borra la línea, se corre, se restaura.

**I1 · sin las dos líneas de empresa del guardia** (`repositorio.py` 206-207):

```
$ uv run python -m pytest tests/e2e/test_qa_borrado_con_vacante_ajena.py --tb=line -q
...FF.                                                                   [100%]
================================== FAILURES ===================================
E   AssertionError: QA backend BUG-2 (I1): el borrado se ejecutó con un vacante_id ajeno (inexistente, vacante_id=999999) sobre un candidato sin postulaciones, y la fila ya no está. La respuesta fue 404: el servidor ejecutó la acción destructiva y le dijo al reclutador que aquí no hay nada.
    assert False
     +  where False = sigue_en_la_base(Engine(postgresql+pg8000://criba:***@localhost:5444/criba_e2e_test), 5)
     +    where 5 = CandidatoSintetico(id=5, nombre='Candidato sintético 4 del borrado').id
tests\e2e\test_qa_borrado_con_vacante_ajena.py:259: AssertionError: …
E   AssertionError: QA backend BUG-2 (I1): el borrado se ejecutó con un vacante_id ajeno (vacante_de_meridian, vacante_id=3) sobre un candidato sin postulaciones, y la fila ya no está. La respuesta fue 404: …
    assert False
     +  where False = sigue_en_la_base(Engine(postgresql+pg8000://criba:***@localhost:5444/criba_e2e_test), 6)
     +    where 6 = CandidatoSintetico(id=6, nombre='Candidato sintético 5 del borrado').id
tests\e2e\test_qa_borrado_con_vacante_ajena.py:259: AssertionError: …
=========================== short test summary info ===========================
FAILED tests/e2e/test_qa_borrado_con_vacante_ajena.py::test_borrar_un_candidato_sin_postulaciones_con_una_vacante_ajena_no_borra_nada_y_da_404[chromium-inexistente]
FAILED tests/e2e/test_qa_borrado_con_vacante_ajena.py::test_borrar_un_candidato_sin_postulaciones_con_una_vacante_ajena_no_borra_nada_y_da_404[chromium-vacante_de_meridian]
```

Es **exactamente** la forma de BUG-2 que describía el hallazgo: 404 con la fila ya
borrada. Y es la rama multiempresa, porque el segundo parámetro es la vacante de
Meridian (CA1). Antes de la ronda 1, esa misma mutación dejaba la suite entera en
verde.

**M1 · sin `.translate(SIN_SALTOS)`** (`sesion.py` 60):

```
$ uv run python -m pytest tests/plataforma/test_ruta_interna.py tests/e2e/test_qa_redireccion_abierta.py --tb=line -q
....F...........                                                         [100%]
================================== FAILURES ===================================
E   AssertionError: redirección abierta (issue #16): ruta_interna('/\t//example.com') devolvió '/\t//example.com' en vez de '/vacantes'. El navegador normaliza ese valor a otro dominio: una URL de Criba no puede decidir a qué sitio va alguien después de entrar.
    assert '/\t//example.com' == '/vacantes'

      - /vacantes
      + /	//example.com
tests\plataforma\test_ruta_interna.py:74: AssertionError: …
=========================== short test summary info ===========================
FAILED tests/plataforma/test_ruta_interna.py::test_ruta_interna_descarta_todo_destino_que_saque_al_navegador_de_criba[tabulador_y_doble_barra]
```

Cae **un** parámetro, y es el que el escritor de tests dejó documentado como el
único que distingue esa línea: `/<TAB>//example.com`. Con `/<TAB>/example.com` a
secas, `urlsplit` ya borra el tabulador para decidir y la guarda de `//` atrapa el
resto, así que la línea parecería de adorno. Nótese que el E2E del issue #16 sigue
verde con la mutación: era justo el hueco del hallazgo.

**M1 · sin la guarda `candidato.startswith("//")`** (`sesion.py` 64):

```
$ uv run python -m pytest tests/plataforma/test_ruta_interna.py --tb=line -q
=========================== short test summary info ===========================
FAILED tests/plataforma/test_ruta_interna.py::test_ruta_interna_descarta_todo_destino_que_saque_al_navegador_de_criba[tabulador_y_doble_barra]
FAILED tests/plataforma/test_ruta_interna.py::test_ruta_interna_descarta_todo_destino_que_saque_al_navegador_de_criba[triple_barra]
FAILED tests/plataforma/test_ruta_interna.py::test_ruta_interna_descarta_todo_destino_que_saque_al_navegador_de_criba[dos_barras_invertidas]
E   AssertionError: redirección abierta (issue #16): ruta_interna('///example.com') devolvió '///example.com' en vez de '/vacantes'. …
    assert '///example.com' == '/vacantes'
E   AssertionError: redirección abierta (issue #16): ruta_interna('/\\\\example.com') devolvió '///example.com' en vez de '/vacantes'. …
    assert '///example.com' == '/vacantes'
tests\plataforma\test_ruta_interna.py:74: AssertionError: …
```

Los tres que el revisor nombraba, incluido `///example.com`, que `urlsplit` no
marca con `netloc` y el navegador normaliza igual a `//example.com`.

**Y el verde, con el código tal como está en la rama** (las dos líneas
restauradas; el árbol quedó limpio, lo dice el `git status` de arriba):

```
$ uv run python -m pytest tests/plataforma/test_ruta_interna.py tests/e2e/test_qa_borrado_con_vacante_ajena.py
.....................                                                    [100%]
21 passed in 3.54s
```

Las mutaciones fueron locales y temporales, una a la vez, **restauradas antes de
cualquier commit**: no entran en el diff. El `uv run python -m poethepoet check`
del bloque 3 de «Evidencia» es posterior a restaurarlas.

## Una decisión declarada: el candidato sin postulaciones

El guardia del borrado tiene **dos mitades**, y la asimetría no es un adorno: es
el único punto donde el hallazgo de la QA y un test que ya estaba en verde se
tocan. Dicho antes de que lo encuentre el revisor:

- si el candidato **aparece en alguna lista**, el `vacante_id` del formulario
  tiene que ser una de ellas. Es la afirmación falsa del hallazgo, en sus tres
  formas;
- si el candidato **no está postulado a nada**, no hay ninguna lista que el
  formulario pueda estar mirando, y lo único que queda por exigir es que la
  vacante sea de esta empresa (CA1), porque de ella sale el fragmento de la
  respuesta.

La segunda mitad existe porque `tests/match/test_vacante_no_espera.py::test_los_cuatro_puntos_de_render_traen_la_misma_lista`
(PR-05, verde desde entonces) **borra un candidato sin postulaciones** desde la
vista de la vacante y espera su lista de vuelta con 200 —usa un candidato así a
propósito, para no chocar con la FK de `match_trabajos` que PR-18 arregla—. Con
la regla «el `vacante_id` tiene que ser una postulación del candidato» a secas,
ese test se pondría rojo: la regla rompería un contrato que otro rol fijó, y eso
no se decide desde este asiento.

En la interfaz la asimetría no se nota: el botón «Borrar» solo existe en una fila
de la tabla, y una fila es una postulación (`_candidatos.html`), así que el
camino real siempre entra por la primera mitad. **Y era justo por eso que la
segunda no tenía test** —el hallazgo I1 de la ronda 1—: los tres casos
parametrizados llegan por la interfaz y por la interfaz esa rama no se alcanza.
Desde `51c4f57` la cubren tres tests que entran por `page.request.post`, que es
el camino que un atacante usaría y el único que la alcanza.

**Lo que queda sin cerrar** es si borrar un candidato que no está postulado a nada
debería pedir `vacante_id` siquiera; hoy lo acepta y devuelve esa lista. Quien
decide: Víctor, y la casa natural es **PR-18**, que es quien vuelve a abrir el
procedimiento de borrado.

## Criterio de terminado

- [x] **Los tres hallazgos de `qa/TRIAGE.md` en verde**, con el E2E que el
      escritor de tests dejó en rojo y sin tocarlo (bloques 1 y 2).
- [x] **`uv run python -m poethepoet check` en verde**: lint, formato y la suite
      entera, E2E incluido (bloque 3), después de la ronda 1.
- [x] **Los dos hallazgos de la ronda 1 atendidos**, cada uno con su resultado y
      su salida real (sección «Ronda 1 de revisión»). Ninguno pedía un cambio de
      conducta y ninguno lo recibió: `app/` no se toca en esta ronda.
- [x] **`tests/` idéntico al commit `51c4f57`**: `git diff 51c4f57 -- tests/`
      no devuelve ninguna línea. Ningún `skip`, ningún `xfail` nuevo, ningún test
      desactivado, ningún `try/except` que se trague el error ni ningún `if` para
      el caso del test.
- [x] **No se borra nada con un `vacante_id` ajeno**, y la respuesta es 404: las
      tres formas del hallazgo, cada una con un candidato nuevo (si compartieran
      candidato, el segundo caso pasaría por una razón falsa).
- [x] **Multiempresa, en las dos direcciones**: Meridian no borra un candidato de
      Northstar ni con el `vacante_id` correcto, no ve su vacante a 360 px, y un
      `destino` interno de otra empresa se respeta como ruta y muere en el 404 de
      siempre, sin filtrar el título de la vacante ajena.
- [x] **El arreglo de CA19 no esconde nada**: el E2E asercia que la tabla está
      visible, que trae las seis filas y que el score se ve. La medición del
      bloque 4 lo confirma caja por caja.
- [x] **Un `destino` interno sigue funcionando**: el arreglo del issue #16 no es
      «ignorar `destino` siempre», que es la forma perezosa de poner ese test en
      verde (y la que habría convertido BUG-5 en un bug de verdad).
- [x] **Sin dependencias nuevas**: `pyproject.toml` y `uv.lock` no se tocan.
- [x] **Sin migraciones**: no aplica la lista de comprobación de bloqueo de F16.
- [ ] **CI verde con la ejecución enlazada** (§0 punto 3, regla 1.2): sin marcar,
      porque esta sesión **no empuja** la rama (no se le pidió). La evidencia de
      los bloques 1 a 4 es local, de la máquina de quien escribe. **Antes del
      merge: empujar y enlazar la ejecución de `criba-ci`.**
- [ ] **Ensayo manual a 360 px en un teléfono de verdad**: sin marcar. CA19 pide
      también eso (F15: «un ensayo manual en el teléfono de Dana antes del
      15-ene») y aquí solo hay Chromium a 360×640. No se presenta el test como si
      fuera la medición manual.

## Riesgo

- **Cubre F15** (S4×P3=12, `docs/fallas.md`: «las razones reales… desbordan a 360
  px, o el control de orden queda fuera de la pantalla»), pero solo su primera
  mitad: hoy no hay razones ni control de orden que desborden, porque no existen
  (van en PR-20). Lo que este PR cierra es el desbordamiento **que ya ocurría con
  la tabla de hoy**, y deja el contenedor haciendo su trabajo, que es lo que
  PR-20 necesita encontrarse hecho.
- **Los otros dos hallazgos no tienen fila en `docs/fallas.md`, y lo digo en vez
  de forzar una.** El mapa de fallas es de Match; estos son defectos de la
  plataforma que replica el producto de hoy: una acción destructiva que no valida
  su parámetro y una redirección que acepta cualquier cosa que empiece por `/`.
  El borrado roza F43 (borrado + cola) y F13 (inventario de borrado), que son de
  **PR-18**; la redirección no roza ninguna.
- **Riesgo que introduce el guardia del borrado:** un 404 nuevo en una ruta que
  antes respondía siempre. Si algún camino de la interfaz mandara un `vacante_id`
  distinto del de la fila, el botón «Borrar» dejaría de funcionar en silencio
  —un 404 en el swap de HTMX—. Hoy ese camino no existe (la plantilla pone
  `vacante.id` en el campo oculto) y los cuatro puntos de render siguen verdes,
  pero conviene decirlo: a partir de aquí, el `vacante_id` del formulario de
  borrado es contrato.
- **Riesgo que introduce `ruta_interna`:** es la única puerta de la regla, así que
  una redirección construida **sin** pasar por ella vuelve a abrir el agujero.
  La ronda 1 (M1) cerró la mitad de este riesgo: la **función** ya tiene su test
  de unidad con las quince entradas, así que lo que hay dentro de ella no se
  puede aflojar en silencio. Lo que sigue abierto es el otro lado, el de quién la
  llama.
  Nada lo impide hoy más que la lectura del código: no hay test de forma que
  enumere los `RedirectResponse` de la plataforma, y no se inventa aquí uno
  porque los tests son de otro rol. Queda anotado como lo que es.
- **Lo que este PR no mueve de sitio:** nada del esquema, nada de Match. El diff
  no entra en `app/match/`.

## Qué NO entra

- **Las otras dos mitades de CA19** —las tres razones y el control de orden,
  visibles y accionables a 360 px— → **PR-20**, igual que QA frontend BUG-1 y
  BUG-2 y QA backend BUG-3 y BUG-4 (`qa/TRIAGE.md`). No existen todavía: no hay
  nada que mirar, y el E2E lo dice en su docstring.
- **La precondición de los 500 candidatos de CA19 y CA5** → `tests/match/`, no un
  E2E. El desbordamiento lo causan los anchos de las columnas, no el número de
  filas.
- **QA backend BUG-1** (borrar un candidato **con score** da 500) → **PR-18**, con
  la regla 1.7: ningún dato real se puntúa antes de que el borrado de Match esté
  en verde. Por eso los candidatos de este E2E van **sin CV y sin score**: para
  que el rojo fuera el de BUG-2 y no el de BUG-1.
- **QA backend BUG-6** (subir CV con un `vacante_id` de otra vacante devuelve el
  fragmento equivocado) → **issue**, por decisión del triage. Es el mismo defecto
  de forma que BUG-2 en la ruta vecina (`POST /candidatos/{id}/cv`) y **se dejó
  intacto a propósito**: arreglarlo aquí sería ampliar el alcance, y la ruta del
  CV no es destructiva —devuelve el fragmento equivocado, no borra nada—. Cuando
  se decida arreglarlo, `exigir_vacante_del_borrado` es el molde.
- **El 500 de schemathesis con un id mayor que `bigint`** → **issue**, por
  decisión del triage.
- **Sanear `destino` también en `GET /entrar`.** La regla se aplica donde se
  construye la redirección, que es el único punto donde decide algo. El campo
  oculto del formulario sigue reflejando lo que venga en la URL (escapado por
  Jinja): es feo en el HTML y ya no lleva a ninguna parte. Hacerlo en los dos
  sitios es un cambio de lo que la página muestra, y eso no lo pide ningún test
  ni ningún hallazgo.
- **Las cinco «optimizaciones» del informe de frontend** (el `1 abiertas`, el
  favicon, los `aria-label` de los botones repetidos, el diálogo de confirmación
  —que existe: `hx-confirm`— y el «52 de 100»): la QA las marca como «no son
  bugs» y el triage no las manda arreglar.
- **Un test de forma que enumere las redirecciones de la plataforma** → es
  `tests/`, y este rol no escribe tests.

## Dependencias

- **PR-07** (el andamio de E2E: servidor real en un hilo, base comprometida en
  `criba_test` y datos sintéticos). Los tres guiones nuevos **añaden** archivos a
  `tests/e2e/` y no cambian ninguno de los suyos.
- **PR-05** (la vista de vacante y la columna de score que el E2E de CA19
  asercia), **PR-01** (la plataforma: login, repositorio por empresa y las rutas
  de candidatos).
- **No toca ninguna migración** (F16) y **no añade dependencias**.

## Fuentes

- `qa/TRIAGE.md` (22-nov-2026): la tabla de decisiones y la sección «lo que
  encontró el triage y no la QA» (BUG-5 no existe; la redirección abierta sí, y
  es el issue #16).
- `qa/reportes/2026-11-22-frontend.md` BUG-3 (`scrollWidth` 979 y 999 contra 360,
  con sus capturas) y `qa/reportes/2026-11-22-backend.md` BUG-2 y BUG-5.
- `SPEC.md` CA19 (móvil a 360 px), CA1 (ningún dato cruza entre empresas), CA18.
- `docs/decisiones.md` D22 (el viewport de 360 px), D17.
- `docs/fallas.md` F15 (navegador a 360 px, S4×P3=12), F43 y F13 (borrado, que
  son de PR-18), F16 (migraciones).
- `CLAUDE.md` §E2E: nada de esperas por tiempo, y cada hallazgo que se arregla
  entra primero como E2E en rojo.
- `PLAN.md` §1 (reglas 1.1 y 1.7), §4 (estructural antes que comportamiento), §6
  (esta plantilla).
- Los commits de tests `39f3222` y `51c4f57` («Rol: escritor-tests»), que son el
  contrato que este PR pone en verde.
- La **ronda 1 de revisión** de PR-QA-E2E (confianza 85, veredicto «corregir»),
  hallazgos I1 y M1: los dos, huecos de cobertura sobre código ya correcto.
