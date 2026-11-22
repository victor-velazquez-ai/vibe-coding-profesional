"""Entorno de Alembic.

De dónde sale la URL, en este orden: la opción `-x url=...` de la línea de
órdenes, el `sqlalchemy.url` que `app/migracion.py` fija al llamar por código, y
si no, `CRIBA_URL_BD` del entorno.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine

from app.configuracion import ajustes
from app.db import Base
from app.plataforma import modelos as modelos_plataforma  # noqa: F401  (registra las tablas)

metadata_destino = Base.metadata


def _url() -> str:
    argumentos = context.get_x_argument(as_dictionary=True)
    if "url" in argumentos:
        return argumentos["url"]
    por_codigo = context.config.get_main_option("sqlalchemy.url", None)
    if por_codigo:
        return por_codigo
    return ajustes().url_bd


def migrar_sin_conexion() -> None:
    context.configure(
        url=_url(), target_metadata=metadata_destino, literal_binds=True, compare_type=True
    )
    with context.begin_transaction():
        context.run_migrations()


def migrar_con_conexion() -> None:
    motor = create_engine(_url())
    with motor.connect() as conexion:
        context.configure(connection=conexion, target_metadata=metadata_destino, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    motor.dispose()


if context.is_offline_mode():
    migrar_sin_conexion()
else:
    migrar_con_conexion()
