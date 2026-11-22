"""Configuración de la plataforma, leída del entorno.

Nada de secretos en el repo (F19): la clave de sesión y las URLs de base de datos
salen de variables de entorno. Los valores por omisión son solo para desarrollo
local contra el contenedor `criba-db` de `docker-compose.yml`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

URL_BD_DESARROLLO = "postgresql+pg8000://criba:criba@localhost:5434/criba_dev"
URL_BD_TEST = "postgresql+pg8000://criba:criba@localhost:5434/criba_test"


@dataclass(frozen=True, slots=True)
class Ajustes:
    """Ajustes de la plataforma. Inmutables: se leen una vez por proceso."""

    url_bd: str
    url_bd_test: str
    secreto_sesion: str
    cookie_sesion: str = "criba_sesion"
    horas_de_sesion: int = 12


@lru_cache(maxsize=1)
def ajustes() -> Ajustes:
    return Ajustes(
        url_bd=os.environ.get("CRIBA_URL_BD", URL_BD_DESARROLLO),
        url_bd_test=os.environ.get("CRIBA_URL_BD_TEST", URL_BD_TEST),
        # Solo para desarrollo. En producción es obligatoria y no tiene omisión.
        secreto_sesion=os.environ.get("CRIBA_SECRETO_SESION", "secreto-de-desarrollo-no-usar"),
    )
