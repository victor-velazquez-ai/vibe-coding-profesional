"""Material común de los tests del arnés de evals: los casos reales y las respuestas fabricadas.

**Qué es el arnés, y qué no es.** Es una herramienta de calidad del fit score, no un
paso de `PLAN.md`: el antecesor pequeño del conjunto dorado de CA14 (`SPEC.md`
CA14, PR-17), con 12 casos **sintéticos** en `evals/casos.json` en lugar de las 10
vacantes cerradas de Northstar. Por eso vive en `evals/` y no en `app/`, y por eso
estos tests no tocan la base de datos: **no hay dato de ninguna empresa aquí**
(regla 1.6 de `PLAN.md` §1, D3 modificado, F12). El aislamiento multiempresa que
estos tests no ejercen está cubierto donde ocurre —`tests/match/test_aislamiento.py`
y `tests/match/test_activacion_por_empresa.py`—; el arnés no abre sesión, no
consulta ninguna tabla y no recibe `empresa_id`.

**Qué fijan los tests de este directorio, y qué no.** Solo la **calificación del
resultado**: banda, menciones, invariante, inyección y el conteo pass^1 / pass^k.
El corredor (`uv run python -m evals --proveedor mock|claude --k 3`), el camino de
producción que recorre —pseudonimizador → cliente del proveedor → validación de
PR-11—, el costo, el modelo que reporta el proveedor y el JSON de
`evals/resultados/` **no los fija ningún test de aquí**: se califican resultados
**fabricados a mano**, que es lo que permite probar el calificador sin red, sin
clave y sin gastar dinero. Eso está dicho en voz alta en la respuesta del paso.

**Las respuestas fabricadas son del tipo de producción**
(`app.match.configuracion.RespuestaDelProveedor`) y no un diccionario inventado:
el arnés califica lo que el camino real devuelve —score `None` incluido, que es el
«sin score, nunca un cero» de CA13— y si el calificador exigiera otra forma, el
corredor tendría que traducir y la traducción sería código sin test.

**El contrato que estos tests fijan**, para quien lo construya:

- `evals/calificacion.py`
  - `banda_de(score: int | None) -> str` → `"alto" | "medio" | "bajo" | "insuficiente"`,
    con los cortes que declara `evals/casos.json`;
  - `calificar(caso, respuesta, gemela=None) -> Calificacion`, con
    `banda`, `banda_ok`, `menciones_ok`, `invariante_ok`, `inyeccion_ok`, `paso`
    y `motivos` (texto legible de por qué no pasó; el informe lo necesita).
    `invariante_ok` e `inyeccion_ok` valen `None` cuando el caso no declara
    gemelo ni bandas prohibidas: una dimensión que el caso no declara **no se
    califica** y no estorba al `paso`.
- `evals/informe.py`
  - `resumir_caso(caso_id, calificaciones) -> ResultadoDeCaso` con `caso_id`, `k`,
    `aciertos`, `pass_1` (fracción) y `pass_k` (booleano);
  - `totales(resultados) -> Totales` con `casos`, `intentos`, `aciertos`, `pass_1`
    y `pass_k` (fracción de casos con los k intentos bien). Si el informe necesita
    además el costo y el modelo, entran por parámetros opcionales: no los fija
    ningún test porque los pone el proveedor, no el calificador.

**Por qué el import es perezoso.** El arnés todavía no existe, así que un
`import evals.calificacion` en la cabecera dejaría los diez archivos en error de
colección —«ningún test llegó a correr»— y no en rojo por lo que falta. `modulo()`
lo importa dentro de cada test y, si no está, falla con el contrato escrito en el
mensaje: un fallo por test, con su nombre y su razón.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from app.match.configuracion import RespuestaDelProveedor

RAIZ = Path(__file__).resolve().parents[2]
RUTA_DE_CASOS = RAIZ / "evals" / "casos.json"

# Cuántos casos tiene el archivo hoy. No es decoración: si alguien añade un caso
# sin banda esperada o sin `no_debe`, el recorrido de los 12 lo dice en vez de
# saltárselo en silencio.
CASOS_ESPERADOS = 12

# Un score cómodamente dentro de cada banda, para fabricar la respuesta «ideal» de
# un caso sin pegarse a los bordes (los bordes los prueba su propio test).
SCORE_POR_BANDA = {"alto": 85, "medio": 55, "bajo": 20}

# La versión de modelo de las respuestas fabricadas. Dice en voz alta que ningún
# modelo las produjo: el calificador no la mira, el informe sí la reporta.
VERSION_FABRICADA = "fabricado-en-el-test"

# El marco de las razones fabricadas. Está elegido para no contener por accidente
# ninguno de los términos exigidos ni prohibidos de `evals/casos.json`: si el marco
# satisficiera un grupo, el recorrido de los 12 casos pasaría sin que el término
# del caso apareciera.
MARCO_DE_RAZON = "Punto considerado: {}"
MARCO_DE_MOTIVO = "Sin score: {}"

CONTRATO = (
    "Lo que estos tests fijan: `evals/calificacion.py` con `banda_de(score)` y "
    "`calificar(caso, respuesta, gemela=None)`, y `evals/informe.py` con "
    "`resumir_caso(caso_id, calificaciones)` y `totales(resultados)`. El detalle está en "
    "el docstring de tests/evals/conftest.py."
)


def archivo_de_casos() -> dict[str, Any]:
    """`evals/casos.json` tal cual. Los tests leen el archivo de verdad: es la
    fuente de los cortes de banda y de los términos, y un calificador que no case
    con él no sirve para nada."""
    return json.loads(RUTA_DE_CASOS.read_text(encoding="utf-8"))


def bandas() -> dict[str, Any]:
    return archivo_de_casos()["bandas"]


def casos() -> list[dict[str, Any]]:
    return archivo_de_casos()["casos"]


def caso(caso_id: str) -> dict[str, Any]:
    for uno in casos():
        if uno["id"] == caso_id:
            return uno
    raise AssertionError(f"{RUTA_DE_CASOS.name} no trae el caso {caso_id!r}")


def respuesta(
    score: int | None,
    *razones: str,
    motivo: str | None = None,
    version: str = VERSION_FABRICADA,
) -> RespuestaDelProveedor:
    """Una respuesta del proveedor **fabricada a mano**, del tipo de producción."""
    return RespuestaDelProveedor(score, tuple(razones), version, motivo)


def terminos_exigidos(un_caso: dict[str, Any]) -> list[str]:
    """La primera alternativa de cada grupo de `debe_mencionar`.

    Una por grupo y no todas: dentro de un grupo las alternativas son un «o»
    —`["sql", "postgres", "mysql", "relacional"]` es un solo requisito escrito de
    cuatro formas— y entre grupos es un «y»."""
    debe = un_caso["debe_mencionar"]
    return [grupo[0] for clave in ("fortalezas", "brechas") for grupo in debe[clave]]


def respuesta_ideal(un_caso: dict[str, Any]) -> RespuestaDelProveedor:
    """La respuesta que un modelo perfecto daría para `un_caso`, construida **del
    propio caso**: la banda esperada y un término de cada grupo exigido.

    Los casos de banda `insuficiente` no llevan score ni razones: llevan
    **motivo** (CA13, `SPEC.md` §15). Así que ahí los términos exigidos solo pueden
    estar en el motivo, y eso es parte del contrato: el texto que el calificador
    mira son las razones **y** el motivo del «sin score».
    """
    terminos = terminos_exigidos(un_caso)
    banda = un_caso["banda_esperada"]
    if banda == "insuficiente":
        return respuesta(None, motivo=MARCO_DE_MOTIVO.format("; ".join(terminos)))
    razones = tuple(MARCO_DE_RAZON.format(termino) for termino in terminos)
    return respuesta(SCORE_POR_BANDA[banda], *(razones or ("Ajuste evaluado",)))


def modulo(nombre: str) -> ModuleType:
    """El módulo del arnés, o un fallo que dice qué falta.

    `pytest.fail` y no un import en la cabecera: así el rojo de este paso es un
    fallo por test con su nombre, y no diez errores de colección."""
    try:
        return importlib.import_module(nombre)
    except ModuleNotFoundError as falta:
        pytest.fail(
            f"El arnés de evals todavía no existe: no se pudo importar «{nombre}» ({falta}). "
            + CONTRATO,
            pytrace=False,
        )


def calificador() -> ModuleType:
    return modulo("evals.calificacion")


def informador() -> ModuleType:
    return modulo("evals.informe")
