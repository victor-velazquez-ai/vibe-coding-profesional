"""PR-07 · el andamio del E2E: servidor real, base comprometida y datos sintéticos.

**Por qué este conftest no reutiliza la fixture `sesion` de `tests/conftest.py`**
(R7·M5, y es la parte del paso que hay que declarar): esa fixture aísla cada test
en una transacción con *savepoint* sobre **una** conexión y sustituye
`crear_sesion` por esa sesión. Funciona con `TestClient`, que corre en el mismo
hilo. Playwright necesita un servidor HTTP **de verdad**, y las dos salidas por
omisión rompen algo: compartir esa `Session` con el hilo de uvicorn no es seguro
—`Session` no es *thread-safe*—, y un servidor que abra su propia sesión no ve
nada de lo sembrado dentro del savepoint. Así que:

- los datos se **comprometen** en `criba_test` y se limpian con
  `TRUNCATE … RESTART IDENTITY CASCADE` al final del módulo, igual que
  `app/plataforma/semilla.py`;
- el servidor es **uvicorn en un hilo** con la app real, y `crear_sesion` se
  sustituye por **una sesión nueva por petición** sobre el motor de test. No es
  la sesión del test: es exactamente lo que hace `crear_sesion` en producción,
  con otra URL. Sin esta sustitución el servidor hablaría con `criba_dev`, que es
  la base de desarrollo —y los tests no escriben ahí (`tests/conftest.py`)—;
- el **guion 4 levanta su propio servidor** con `CRIBA_MATCH_ACTIVO` apagada,
  porque `montar(app)` lee el interruptor al crear la app.

El esquema lo aplica `motor_test` de `tests/conftest.py`, con las migraciones
reales. Todos los datos son **sintéticos** (D3 modificado, D15, F12).
"""

from __future__ import annotations

import asyncio
import socket
import threading
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass

import pytest
import uvicorn
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.db import Base, crear_sesion
from app.fabrica import crear_app
from app.match.cola.ejecutor import una_pasada
from app.match.configuracion import VARIABLE_DE_EMPRESAS, VARIABLE_GLOBAL, ajustes_match
from app.plataforma.modelos import Candidato, Empresa, Postulacion, Rol, Usuario, Vacante
from app.plataforma.seguridad import hash_contrasena

CONTRASENA = "prueba1234"
SLUG_NORTHSTAR = "northstar-health"
SLUG_MERIDIAN = "meridian-logistics"
SEGUNDOS_DE_ARRANQUE = 15


@dataclass(frozen=True, slots=True)
class Datos:
    """Lo que los cuatro guiones necesitan nombrar, ya comprometido en la base."""

    vacante_id: int
    candidato_id: int
    nombre_candidato: str
    correo_candidato: str
    reclutadora: str
    hiring_manager: str
    reclutadora_meridian: str


def correr_el_ejecutor(motor: object) -> int:
    """Una pasada del bucle, en su propia sesión y **comprometida**.

    En producción la invoca el proceso web (ADR-001 §Decisión 2); aquí la invoca
    el test, que es lo que PR-06 dejó disponible —el bucle es una función, no un
    comando—. Va en su propia sesión a propósito: el servidor tiene la suya por
    petición y el E2E no comparte `Session` entre hilos.

    **Y va en su propio hilo**, que es lo que la primera corrida enseñó: la API
    *sync* de Playwright mantiene un bucle de eventos vivo en el hilo del test
    —por eso puede esperar al navegador sin `await`—, así que un `asyncio.run()`
    ahí dentro falla con «cannot be called from a running event loop». El hilo da
    un bucle limpio y, de paso, la sesión del ejecutor no se mezcla con nada.
    """
    assert isinstance(motor, Engine)
    hechos: list[int] = []

    def _pasada() -> None:
        with Session(motor, expire_on_commit=False) as sesion:
            hechos.append(asyncio.run(una_pasada(sesion)))
            sesion.commit()

    hilo = threading.Thread(target=_pasada)
    hilo.start()
    hilo.join(timeout=SEGUNDOS_DE_ARRANQUE)
    assert hechos, "el ejecutor no terminó"
    return hechos[0]


def _vaciar(motor: Engine) -> None:
    tablas = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with motor.begin() as conexion:
        conexion.execute(text(f"TRUNCATE {tablas} RESTART IDENTITY CASCADE"))


def _sembrar(motor: Engine) -> Datos:
    """Dos empresas, tres usuarios, una vacante y un candidato **sin CV**.

    Sin CV a propósito: el guion 1 lo sube por la interfaz, que es la forma de
    que el gancho de PR-06 se dispare de verdad y no por una llamada del test.
    """
    clave = hash_contrasena(CONTRASENA)
    with Session(motor, expire_on_commit=False) as sesion:
        northstar = Empresa(nombre="Northstar Health E2E", slug=SLUG_NORTHSTAR)
        meridian = Empresa(nombre="Meridian Logistics E2E", slug=SLUG_MERIDIAN)
        sesion.add_all([northstar, meridian])
        sesion.flush()

        usuarios = [
            Usuario(
                empresa_id=northstar.id,
                usuario="rec.e2e",
                nombre="Reclutadora sintética",
                rol=Rol.RECLUTADOR,
                hash_contrasena=clave,
            ),
            Usuario(
                empresa_id=northstar.id,
                usuario="hm.e2e",
                nombre="Hiring manager sintético",
                rol=Rol.HIRING_MANAGER,
                hash_contrasena=clave,
            ),
            Usuario(
                empresa_id=meridian.id,
                usuario="rec.meridian.e2e",
                nombre="Reclutadora sintética de Meridian",
                rol=Rol.RECLUTADOR,
                hash_contrasena=clave,
            ),
        ]
        vacante = Vacante(
            empresa_id=northstar.id,
            titulo="Enfermera/o de piso · turno nocturno",
            descripcion="Piso de medicina interna. Licencia RN vigente en Texas.",
            ciudad="Houston, TX",
        )
        candidato = Candidato(
            empresa_id=northstar.id,
            nombre="Valentina Sintetica",
            correo="valentina@northstar-e2e.test",
            telefono="+1 713 555 0100",
            links=[],
        )
        sesion.add_all([*usuarios, vacante, candidato])
        sesion.flush()
        sesion.add(
            Postulacion(empresa_id=northstar.id, candidato_id=candidato.id, vacante_id=vacante.id)
        )
        sesion.commit()

        return Datos(
            vacante_id=vacante.id,
            candidato_id=candidato.id,
            nombre_candidato=candidato.nombre,
            correo_candidato=candidato.correo,
            reclutadora=usuarios[0].usuario,
            hiring_manager=usuarios[1].usuario,
            reclutadora_meridian=usuarios[2].usuario,
        )


def _puerto_libre() -> int:
    with closing(socket.socket()) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def _servidor_en_un_hilo(motor: Engine) -> Iterator[str]:
    """La app real, servida por uvicorn, con una sesión nueva por petición."""
    app = crear_app()

    def sesion_por_peticion() -> Iterator[Session]:
        with Session(motor, expire_on_commit=False) as sesion:
            yield sesion

    app.dependency_overrides[crear_sesion] = sesion_por_peticion

    puerto = _puerto_libre()
    servidor = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=puerto, log_level="warning")
    )
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    try:
        _esperar_a_que_responda(servidor)
        yield f"http://127.0.0.1:{puerto}"
    finally:
        servidor.should_exit = True
        hilo.join(timeout=SEGUNDOS_DE_ARRANQUE)


def _esperar_a_que_responda(servidor: uvicorn.Server) -> None:
    """Espera el arranque de uvicorn, no un `sleep` fijo: un número inventado es
    lo que convierte un E2E en inestable y lo que termina desactivándolo."""
    espera = threading.Event()
    for _ in range(SEGUNDOS_DE_ARRANQUE * 20):
        if servidor.started:
            return
        espera.wait(0.05)
    raise RuntimeError("el servidor del E2E no arrancó")


@pytest.fixture(scope="module")
def datos(motor_test: Engine) -> Iterator[Datos]:
    """Datos comprometidos en `criba_test`, y la base limpia al terminar.

    Se limpia **antes y después**: antes, porque un módulo anterior pudo dejar
    filas si falló a mitad; después, porque los tests de `tests/match/` asercian
    sobre tablas vacías dentro de su transacción.
    """
    _vaciar(motor_test)
    yield _sembrar(motor_test)
    _vaciar(motor_test)


@pytest.fixture(scope="module")
def match_activado() -> Iterator[None]:
    """Match encendido **y Northstar activada** (D7, CA3).

    `tests/conftest.py` enciende el interruptor global para toda la suite; la
    activación por empresa es otra cosa y vive en `CRIBA_MATCH_EMPRESAS_ACTIVADAS`
    (PR-03, R4·I1). Aquí se enciende solo Northstar: Meridian sigue sin anexo.
    """
    parche = pytest.MonkeyPatch()
    parche.setenv(VARIABLE_DE_EMPRESAS, SLUG_NORTHSTAR)
    ajustes_match.cache_clear()
    yield
    parche.undo()
    ajustes_match.cache_clear()


@pytest.fixture(scope="module")
def servidor(motor_test: Engine, match_activado: None, datos: Datos) -> Iterator[str]:
    """El servidor de los guiones 1, 2 y 3: Match encendido."""
    with _servidor_en_un_hilo(motor_test) as url:
        yield url


@pytest.fixture
def servidor_apagado(motor_test: Engine, datos: Datos) -> Iterator[str]:
    """El servidor del guion 4: `CRIBA_MATCH_ACTIVO` apagada, que es su valor por
    omisión fuera de tests (R6·I5). Es un servidor **propio** porque `montar(app)`
    lee el interruptor al crear la app."""
    parche = pytest.MonkeyPatch()
    parche.delenv(VARIABLE_GLOBAL, raising=False)
    ajustes_match.cache_clear()
    with _servidor_en_un_hilo(motor_test) as url:
        yield url
    parche.undo()
    ajustes_match.cache_clear()
