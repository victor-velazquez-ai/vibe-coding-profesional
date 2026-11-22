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
que la CI no lo corre con el modelo real (`docs/arquitectura.md` §2, D12). Lo que
sí vive en `tests/evals/` es la **calificación**, que es determinista: ahí se
prueba con respuestas del proveedor fabricadas a mano.

**No hay dato de ninguna empresa aquí.** Los 12 casos son sintéticos y ficticios
(correos en `example.com`), el arnés **no abre sesión, no consulta ninguna tabla y
no recibe `empresa_id`**, y por eso no puede violar D4 ni CA1: no tiene nada que
cruzar. El aislamiento multiempresa está probado donde ocurre
(`tests/match/test_aislamiento.py`, `tests/match/test_activacion_por_empresa.py`).

**Los cuatro módulos y qué decide cada uno:**

- `casos.py` — dónde está el archivo, cómo se lee y cuáles son los cortes de banda
  que **él declara**. Ninguna banda está escrita a mano en el código;
- `calificacion.py` — las cuatro dimensiones de un resultado, y nada más: no llama
  a nadie;
- `informe.py` — pass^1, pass^k, el total y las dos formas del informe (la tabla
  que se lee y el JSON que se guarda);
- `corredor.py` — el **camino de producción** que se recorre, y el único módulo que
  importa de `app/`.

`python -m evals --proveedor mock --k 3` es la invocación de humo: sin red, en
segundos y sin gastar nada. El `README.md` de este directorio dice cómo correrlo
con el modelo real y qué cuesta.
"""
