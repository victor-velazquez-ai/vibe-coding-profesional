"""Alembic desde Python, para que el comando de semilla y los tests lo reusen.

La URL se pasa explícita en cada llamada: así la base de tests nunca se confunde
con la de desarrollo.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

RAIZ = Path(__file__).resolve().parent.parent


def _config(url: str) -> Config:
    config = Config(str(RAIZ / "alembic.ini"))
    config.set_main_option("script_location", str(RAIZ / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def aplicar_migraciones(url: str, revision: str = "head") -> None:
    command.upgrade(_config(url), revision)


def revertir_migraciones(url: str, revision: str = "base") -> None:
    command.downgrade(_config(url), revision)
