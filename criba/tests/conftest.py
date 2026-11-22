"""Base de datos de test y transacción por test.

Dos garantías, y las dos existen para que un test no pueda ensuciar nada:

1. **la base de test es otra**: `CRIBA_URL_BD_TEST` apunta a `criba_test`, no a
   `criba_dev`, y la fixture se niega a arrancar si el nombre no acaba en
   `_test`. Las dos viven en el mismo contenedor `criba-db` (puerto 5434);
2. **cada test corre dentro de una transacción que se revierte**: la sesión se
   une a una transacción externa con `join_transaction_mode="create_savepoint"`,
   así que un `commit()` del código bajo prueba cae en un savepoint y la
   reversión final se lo lleva igual.

Y una tercera, que PR-05 añade: **el interruptor global de Match lo enciende esta
suite, explícitamente** (R6·I5). Está apagado por omisión, así que sin esta línea
toda la suite de Match sería no-op. El test que lo quiere apagado usa la fixture
`apagar_match` de `tests/match/conftest.py`.

Y un orden, que PR-07 añade: **el E2E de Playwright corre al final**
(`pytest_collection_modifyitems`, con su razón escrita ahí mismo).
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.orm import Session

from app.configuracion import ajustes
from app.db import crear_sesion
from app.fabrica import crear_app
from app.match.configuracion import VARIABLE_GLOBAL
from app.migracion import aplicar_migraciones

os.environ[VARIABLE_GLOBAL] = "1"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """**El E2E corre al final de la suite, siempre** (PR-07).

    No es una preferencia: la API *sync* de Playwright mantiene un bucle de
    eventos vivo en el hilo del test mientras viva su fixture de sesión, y
    `pytest-asyncio` no puede abrir otro después. Con el orden alfabético de los
    directorios —`e2e` antes de `match`— los tests `async` de PR-03 y PR-06
    fallan con «Cannot run the event loop while another loop is running» sin que
    nada de su código esté mal. Reordenar aquí es mecánico; un flag en la orden
    de correr los tests dependería de que alguien lo recuerde.
    """
    items.sort(key=lambda item: "tests/e2e" in item.nodeid.replace("\\", "/"))


@pytest.fixture(scope="session")
def url_bd_test() -> str:
    url = ajustes().url_bd_test
    nombre = make_url(url).database or ""
    if not nombre.endswith("_test"):
        raise RuntimeError(
            f"CRIBA_URL_BD_TEST apunta a {nombre!r}, que no acaba en '_test'. "
            "Los tests borran el esquema: se niegan a correr sobre otra base."
        )
    if url == ajustes().url_bd:
        raise RuntimeError("La base de test y la de desarrollo son la misma.")
    return url


@pytest.fixture(scope="session")
def motor_test(url_bd_test: str) -> Iterator[Engine]:
    """Esquema limpio por sesión de tests, construido por las migraciones reales."""
    motor = create_engine(url_bd_test)
    with motor.begin() as conexion:
        conexion.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conexion.execute(text("CREATE SCHEMA public"))
    aplicar_migraciones(url_bd_test)
    yield motor
    motor.dispose()


@pytest.fixture
def sesion(motor_test: Engine) -> Iterator[Session]:
    conexion = motor_test.connect()
    transaccion = conexion.begin()
    with Session(bind=conexion, join_transaction_mode="create_savepoint") as sesion:
        yield sesion
    transaccion.rollback()
    conexion.close()


@pytest.fixture
def aplicacion(sesion: Session) -> FastAPI:
    """La app real, con la sesión de base de datos apuntada al test."""
    app = crear_app()
    app.dependency_overrides[crear_sesion] = lambda: sesion
    return app


@pytest.fixture
def cliente(aplicacion: FastAPI) -> Iterator[TestClient]:
    with TestClient(aplicacion) as cliente:
        yield cliente
