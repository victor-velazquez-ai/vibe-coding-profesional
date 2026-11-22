"""El entorno Jinja2 de la app, compartido por la plataforma y por Match.

Dos directorios de plantillas: las de la plataforma y las de Match
(`app/match/templates/`, PLAN.md §2). Match nombra las suyas con el prefijo
`match/`, así que los nombres no chocan.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader, StrictUndefined

RAIZ = Path(__file__).resolve().parent
PLANTILLAS_PLATAFORMA = RAIZ / "plataforma" / "plantillas"
PLANTILLAS_MATCH = RAIZ / "match" / "templates"

_MESES = (
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
)


def fecha_corta(valor: datetime | None) -> str:
    """`6-ene-2027`. Una fecha siempre se escribe igual en toda la app."""
    if valor is None:
        return "—"
    return f"{valor.day}-{_MESES[valor.month - 1]}-{valor.year}"


plantillas = Jinja2Templates(directory=str(PLANTILLAS_PLATAFORMA))
plantillas.env.loader = ChoiceLoader(
    [FileSystemLoader(str(PLANTILLAS_PLATAFORMA)), FileSystemLoader(str(PLANTILLAS_MATCH))]
)
plantillas.env.undefined = StrictUndefined
plantillas.env.filters["fecha_corta"] = fecha_corta
