"""E2E de la **redirección abierta del login** (issue #16, `qa/TRIAGE.md`).

No es un hallazgo de la QA: es lo que encontró el triage al reproducir BUG-5
—«el login ignora `destino`»— fuera de Git Bash. BUG-5 **no existe** (era la
conversión de rutas POSIX de MSYS), y al reproducirlo apareció un defecto real:
con `destino=//example.com`, `POST /entrar` responde `303` con
`Location: //example.com` y el navegador **sale de Criba a otro dominio**. Es el
enlace de phishing perfecto: una URL de Criba que, después de un login legítimo,
termina en otra parte. `qa/TRIAGE.md` lo decide «se arregla ahora».

**Lo que este guion fija, en un solo test porque es un solo criterio:**

1. un `destino` interno **se respeta** (es la refutación de BUG-5, y es lo que un
   arreglo perezoso —«ignorar `destino` siempre»— rompería);
2. un `destino` interno **de otra empresa** se respeta como ruta y muere en el 404
   de siempre, sin filtrar nada (CA1: el arreglo no puede volverse una lista
   blanca que deje leer una vacante de Meridian);
3. un `destino` que apunta fuera de Criba **termina en `/vacantes`** y el
   navegador nunca cambia de dominio. **Aquí está el rojo de hoy.**

Los bloques van en ese orden a propósito: 1 y 2 pasan hoy y se ejecutan de
verdad; el fallo cae en el 3, que es el hallazgo.

**Dos formas de escribir el mismo escape**, y las dos se asercian: `//example.com`
(la del triage) y `/\\example.com`, que empieza por `/` —así que pasa el filtro
actual `destino.startswith("/")`— y que el navegador normaliza a `//example.com`.
Si solo se aserciara la primera, un arreglo que rechace `//` dejaría el agujero
abierto con una barra invertida.

**Y se asercia en los dos planos**: la cabecera `Location` del `303` (el contrato
del servidor, con `httpx` y sin seguir la redirección: una `Location` que apunta a
otro dominio es el defecto, se resuelva el DNS o no) y la URL en la que el
navegador se queda (el vector real, con Playwright).
"""

from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import urlsplit

import httpx
import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.plataforma.modelos import Vacante
from tests.e2e.ayudas import abrir, empresa_por_slug, entrar_con_destino
from tests.e2e.conftest import CONTRASENA, SLUG_MERIDIAN, Datos

# Los dos `destino` que salen de Criba. El segundo empieza por «/», así que el
# filtro de hoy lo acepta, y el navegador lo normaliza a «//example.com».
DESTINOS_QUE_SALEN = ("//example.com", "/\\example.com")
DESTINO_POR_OMISION = "/vacantes"
TITULO_DE_MERIDIAN = "Reparto urbano · turno mañana (sintética)"


@pytest.fixture(scope="module")
def vacante_de_meridian(motor_test: Engine, datos: Datos) -> Iterator[int]:
    """Una vacante de la otra empresa, para el `destino` interno pero ajeno."""
    with Session(motor_test, expire_on_commit=False) as sesion:
        meridian = empresa_por_slug(sesion, SLUG_MERIDIAN)
        vacante = Vacante(
            empresa_id=meridian.id,
            titulo=TITULO_DE_MERIDIAN,
            descripcion="Reparto en ciudad. Datos sintéticos.",
            ciudad="El Paso, TX",
        )
        sesion.add(vacante)
        sesion.commit()
        yield vacante.id


def _location_del_login(servidor: str, usuario: str, destino: str) -> str:
    """`POST /entrar` **sin seguir la redirección**: la cabecera cruda del 303."""
    respuesta = httpx.post(
        f"{servidor}/entrar",
        data={"usuario": usuario, "contrasena": CONTRASENA, "destino": destino},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303, (
        f"el login con destino={destino!r} no respondió 303 sino {respuesta.status_code}"
    )
    return respuesta.headers["location"]


def test_el_login_respeta_un_destino_interno_y_nunca_sale_de_criba(
    page: Page, servidor: str, datos: Datos, vacante_de_meridian: int
) -> None:
    """Issue #16 · `destino` solo manda dentro de Criba."""
    # 1. Un destino interno se respeta (BUG-5 no existe, y el arreglo no puede
    #    convertirse en «ignorar destino siempre»).
    suya = f"/vacantes/{datos.vacante_id}"
    assert _location_del_login(servidor, datos.reclutadora, suya) == suya
    entrar_con_destino(page, servidor, datos.reclutadora, suya)
    expect(page).to_have_url(f"{servidor}{suya}")
    expect(page.get_by_text(datos.nombre_candidato)).to_be_visible()

    # 2. Multiempresa (CA1): un destino interno de otra empresa se respeta como
    #    ruta y muere en el 404 de siempre. No se filtra nada por el camino.
    ajena = f"/vacantes/{vacante_de_meridian}"
    assert _location_del_login(servidor, datos.reclutadora, ajena) == ajena
    entrar_con_destino(page, servidor, datos.reclutadora, ajena)
    expect(page).to_have_url(f"{servidor}{ajena}")
    assert abrir(page, servidor, ajena) == 404
    assert TITULO_DE_MERIDIAN not in page.content()

    # 3. El hallazgo del triage: un destino que apunta fuera de Criba.
    for destino in DESTINOS_QUE_SALEN:
        location = _location_del_login(servidor, datos.reclutadora, destino)
        partes = urlsplit(location)
        assert partes.scheme == "" and partes.netloc == "", (
            f"redirección abierta (issue #16): el login con destino={destino!r} responde 303 "
            f"con Location={location!r}, que saca al navegador de Criba. Una URL de Criba no "
            "puede decidir a qué dominio va alguien después de entrar."
        )
        assert location == DESTINO_POR_OMISION, (
            f"un destino que no es una ruta interna de Criba ({destino!r}) tiene que caer en "
            f"{DESTINO_POR_OMISION}; cayó en {location!r}"
        )

        entrar_con_destino(page, servidor, datos.reclutadora, destino)
        expect(page).to_have_url(f"{servidor}{DESTINO_POR_OMISION}")
