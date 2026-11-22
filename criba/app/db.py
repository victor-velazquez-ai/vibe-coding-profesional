"""Motor, base declarativa y sesión de SQLAlchemy.

El motor se crea la primera vez que se pide, no al importar: así la app se puede
importar (y los tests del andamio pueden correr) sin que Postgres esté arriba.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.configuracion import ajustes


class Base(DeclarativeBase):
    """Base declarativa compartida por la plataforma y por Match."""


@lru_cache(maxsize=1)
def motor() -> Engine:
    return create_engine(ajustes().url_bd, pool_pre_ping=True)


def crear_sesion() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por petición, con commit al final."""
    with Session(motor(), expire_on_commit=False) as sesion:
        yield sesion
