"""Cada corrida de tests crea su propia base Postgres, la migra y la borra.

El nombre lleva un sufijo aleatorio, asi que se pueden correr varias copias del
repo (o varios workers) en paralelo contra el mismo servidor.
"""

import os
import secrets
import uuid
from collections.abc import Iterator

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.config import PROJECT_ROOT, MissingConfigError, Settings, get_settings

# Secreto de usar y tirar: los tests no dependen de ningun valor del repo.
os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(32))

MAINTENANCE_DB = "postgres"


def _base_settings() -> Settings:
    try:
        return get_settings()
    except MissingConfigError as exc:
        pytest.exit(f"{exc}\nLuego levanta Postgres con `uv run poe db`.", returncode=1)


def _connect_admin(settings: Settings) -> psycopg.Connection[tuple[object, ...]]:
    try:
        return psycopg.connect(
            settings.psycopg_conninfo(MAINTENANCE_DB), autocommit=True, connect_timeout=5
        )
    except psycopg.OperationalError as exc:
        pytest.exit(
            "No puedo conectar con Postgres en "
            f"{settings.postgres_host}:{settings.postgres_port} ({exc}).\n"
            "Levantalo con `uv run poe db`.",
            returncode=1,
        )


def _drop_database(settings: Settings, name: str) -> None:
    with _connect_admin(settings) as conn:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (name,),
        )
        conn.execute(f'DROP DATABASE IF EXISTS "{name}"')


def _run_migrations(url: str) -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    settings = _base_settings()
    # El nombre es nuestro y solo tiene [a-z0-9_], seguro de interpolar.
    name = f"taller_test_{uuid.uuid4().hex[:12]}"

    with _connect_admin(settings) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')

    url = settings.sqlalchemy_url_for(name)
    try:
        _run_migrations(url)
        yield url
    finally:
        from app.database import reset_engine

        reset_engine()
        _drop_database(settings, name)


@pytest.fixture(scope="session")
def client(database_url: str) -> Iterator[TestClient]:
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()

    # Importar despues de fijar DATABASE_URL: el engine se crea perezosamente.
    from app.database import get_sessionmaker, reset_engine
    from app.main import app
    from app.seed import seed_if_empty

    reset_engine()
    with get_sessionmaker()() as db:
        seed_if_empty(db)

    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/login", data={"username": username, "password": password})
    response.raise_for_status()
    token: str = response.json()["access_token"]
    return token
