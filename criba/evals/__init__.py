"""El arnés de evals del fit score: una herramienta de calidad, no un paso de `PLAN.md`.

**Qué es.** El antecesor pequeño del conjunto dorado de **CA14** (`SPEC.md` CA14,
`PLAN.md` PR-17): 12 casos **sintéticos** en `evals/casos.json` en lugar de las 10
vacantes cerradas y anonimizadas de Northstar, que son una dependencia externa sin
fecha (pregunta abierta 6 de `SPEC.md`). Corre cada caso **k veces** por el camino
de producción y **califica el resultado** —banda, menciones, invariante e
inyección—, con pass^1 y pass^k por caso y un total.

**Por qué vive en `evals/` y no en `app/` ni en `tests/`.** No es aplicación: no
lo importa nada de `app/`. Y no es la suite: `poe check` corre `tests/`, y lo que
este arnés mide con el proveedor real **cuesta dinero** y no es determinista, así
que la CI no lo corre con el modelo real (`docs/arquitectura.md` §2, D12).

**Lo que de este arnés vive en `tests/evals/`, que es casi todo:** la
**calificación** y el conteo pass^k con respuestas del proveedor **fabricadas a
mano** (`test_calificacion.py`, `test_pass_k.py`, `test_bandas_del_camino.py`), las
dos formas del informe (`test_informe_de_salida.py`), y el **corredor** y la
**línea de órdenes** con la única puerta del proveedor doblada en su costura
(`test_corredor.py`, `test_linea_de_ordenes.py`, `doble_del_camino.py`). Ninguno
llama a un modelo, abre red, lanza el CLI ni toca la base de datos, así que los
seis archivos corren en `poe check`. Lo que **no** se puede probar ahí es la
calidad del modelo: eso es una medición con `--proveedor claude`, y está en el
cuerpo del PR.

**No hay dato de ninguna empresa aquí.** Los 12 casos son sintéticos y ficticios
(correos en `example.com`), el arnés **no abre sesión, no consulta ninguna tabla y
no recibe `empresa_id`**, y por eso no puede violar D4 ni CA1: no tiene nada que
cruzar. El aislamiento multiempresa está probado donde ocurre
(`tests/match/test_aislamiento.py`, `tests/match/test_activacion_por_empresa.py`).

**Los cuatro módulos y qué decide cada uno:**

- `casos.py` — dónde está el archivo, cómo se lee y cuáles son los cortes de banda
  que **él declara**. Ninguna banda está escrita a mano en el código;
- `calificacion.py` — las cuatro dimensiones de un resultado, y nada más: **no
  llama a nadie**. De `app/` solo trae un tipo, el `RespuestaDelProveedor` que el
  camino devuelve;
- `informe.py` — pass^1, pass^k, el total y las dos formas del informe (la tabla
  que se lee y el JSON que se guarda);
- `corredor.py` — el **camino de producción** que se recorre, y el único módulo que
  **llama** a `app/`. La licencia que eso supone está escrita en su docstring.

`python -m evals --proveedor mock --k 3` es la invocación de humo: sin red, en
segundos y sin gastar nada. El `README.md` de este directorio dice cómo correrlo
con el modelo real y qué cuesta.
"""
