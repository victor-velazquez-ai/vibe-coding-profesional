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

Y una cuarta, que PR-09 añade y la ronda de revisión del paso corrigió de alcance
(M4): **ningún test de la suite puede lanzar el CLI del proveedor de verdad**, y
«ningún» incluye `tests/e2e`, que corre con la app real y llama al bucle del
ejecutor. Son dos líneas y las dos viven aquí porque el alcance es la suite
entera, no `tests/match`: el **modo de proveedor fijado al MOCK** —igual que el
interruptor global, para que la suite no dependa de lo que alguien haya exportado
en su terminal— y la fixture `autouse` `ningun_cli_de_verdad`, que deja la costura
del subproceso doblada y prohibida por omisión. Su detector es
`tests/test_guardia_del_cli.py`.

Y un orden, que PR-07 añade: **el E2E de Playwright corre al final**
(`pytest_collection_modifyitems`, con su razón escrita ahí mismo).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import suppress

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.orm import Session

from app.configuracion import ajustes
from app.db import crear_sesion
from app.fabrica import crear_app
from app.match.configuracion import MODO_MOCK, VARIABLE_DE_MODO, VARIABLE_GLOBAL
from app.migracion import aplicar_migraciones
from tests.dobles.cli import NOMBRE_DE_LA_COSTURA, adaptador, cli_que_prohibe_llamadas

os.environ[VARIABLE_GLOBAL] = "1"
# **El MOCK, dicho por la suite y no heredado del entorno** (PR-09, N4, M4). Se
# fija aquí y no en `tests/match/conftest.py` porque el bucle del ejecutor le
# pregunta a `proveedor_configurado()` en cada pasada, y el E2E corre ese bucle:
# con `CRIBA_MATCH_PROVEEDOR=claude_cli` exportada en la shell, el humo lanzaba el
# CLI de verdad. Los tests que quieren otro modo lo piden con la fixture `modo`.
os.environ[VARIABLE_DE_MODO] = MODO_MOCK


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


@pytest.fixture(autouse=True)
def ningun_cli_de_verdad(monkeypatch: pytest.MonkeyPatch) -> None:
    """**Ningún test lanza el CLI del proveedor de verdad** (PR-09, N4).

    Es `autouse` y vive en el `conftest` de la raíz a propósito: el olvido de un
    doble en un test cualquiera no puede convertirse en un proceso `claude -p`
    lanzado desde la suite —con un CV dentro—. Con el doble prohibitivo puesto por
    omisión, ese olvido es un test rojo y no una llamada.

    Estuvo en `tests/match/conftest.py` hasta la ronda de revisión de PR-09, que
    señaló el alcance (M4): ahí no cubría `tests/e2e`, que levanta la app real y
    corre el bucle del ejecutor, y el bucle pregunta por el proveedor configurado.

    El `suppress` es lo que hace que esta fixture **no** sea un error de montaje
    si la costura no existe o cambia de nombre; el precio es que el guardia
    podría desaparecer en silencio, y por eso tiene un detector propio en
    `tests/test_guardia_del_cli.py`.
    """
    with suppress(AssertionError):
        puerta = adaptador()
        monkeypatch.setattr(
            puerta.modulo_de_la_costura, NOMBRE_DE_LA_COSTURA, cli_que_prohibe_llamadas()
        )


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
