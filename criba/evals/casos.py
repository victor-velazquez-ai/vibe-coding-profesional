"""Dónde viven los casos del arnés y cómo se leen. Sin conducta.

**Un solo sitio sabe la forma del archivo**, y es este: la ruta, las dos claves de
arriba (`bandas` y `casos`) y, sobre todo, **los cortes de banda**. El calificador
no escribe «70» en ninguna línea: los lee de aquí, que los lee de
`evals/casos.json`. Una tabla de bandas escrita a mano en el código y otra en el
archivo se separan el día que alguien mueve un corte, y entonces el informe miente
sin que nada se ponga rojo (es el cerrojo que
`tests/evals/test_calificacion.py::test_la_banda_sale_del_score_con_los_cortes_que_declara_casos_json`
exige, leyendo el archivo de verdad).

**«insuficiente» no es un corte y por eso no está en `cortes()`.** En el archivo su
valor es la cadena `"sin score (CA13)"` y no un par de números, porque no es un
rango: es el **«sin score, nunca un cero»** de CA13 (`SPEC.md` §15). Un 0 es un
número y cae en «bajo». Esa distinción es la razón de que la cuarta banda exista, y
el filtro de `cortes()` —solo los valores que son una lista— es lo que la mantiene.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

DIRECTORIO = Path(__file__).resolve().parent
RUTA_DE_CASOS = DIRECTORIO / "casos.json"

# Donde el corredor guarda el informe en JSON. El directorio se versiona vacío
# (`.gitkeep`) y los informes **no** se versionan: son salida de una ejecución, con
# su fecha y su proveedor dentro, y el repo no es el sitio donde se acumulan.
RUTA_DE_RESULTADOS = DIRECTORIO / "resultados"

CLAVE_DE_BANDAS = "bandas"
CLAVE_DE_CASOS = "casos"

# La cuarta banda: la que no sale de un corte numérico (CA13, `SPEC.md` §15).
BANDA_INSUFICIENTE = "insuficiente"

Caso = Mapping[str, Any]


@lru_cache(maxsize=1)
def archivo() -> Mapping[str, Any]:
    """`evals/casos.json` tal cual, leído una vez por proceso.

    `lru_cache` porque el calificador pregunta los cortes **por intento** —12 casos
    por k intentos— y el archivo no cambia dentro de una pasada."""
    return json.loads(RUTA_DE_CASOS.read_text(encoding="utf-8"))


def cortes() -> dict[str, tuple[int, int]]:
    """Las bandas que son un rango de score, `{"alto": (70, 100), …}`.

    Solo las que el archivo declara como par de números: ver el encabezado sobre
    por qué «insuficiente» no está aquí."""
    return {
        nombre: (int(valor[0]), int(valor[1]))
        for nombre, valor in archivo()[CLAVE_DE_BANDAS].items()
        if isinstance(valor, list)
    }


def casos() -> tuple[Caso, ...]:
    """Los 12 casos, en el orden del archivo."""
    return tuple(archivo()[CLAVE_DE_CASOS])


def caso(caso_id: str) -> Caso:
    """Un caso por su `id`, o un `KeyError` que dice qué se pidió.

    El corredor lo usa para el **gemelo** de un invariante (`invariante_con`), que
    es un `id` escrito dentro del propio archivo: si ese `id` no existe, el arnés
    tiene que decirlo y no calificar el invariante contra nada."""
    for uno in casos():
        if uno["id"] == caso_id:
            return uno
    raise KeyError(f"{RUTA_DE_CASOS.name} no trae ningún caso con id {caso_id!r}")
