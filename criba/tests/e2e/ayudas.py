"""Ayudas de los tres E2E de los hallazgos de QA del 22-nov-2026.

Los tres guiones nuevos (`qa/TRIAGE.md`) comparten el login por el formulario
real y la medición del ancho del documento. Viven aquí y **no** en
`tests/e2e/conftest.py` para no reescribir el andamio que fijó PR-07: este paso
**añade** archivos a `tests/e2e/` y no cambia ninguno de los suyos.

Nada de esperas por tiempo (`CLAUDE.md`): se espera a `wait_for_url`, a
`expect(...)` o al estado de una respuesta ya recibida, nunca a un número de
segundos inventado.
"""

from __future__ import annotations

from playwright.sync_api import Page
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.plataforma.modelos import Empresa
from tests.e2e.conftest import CONTRASENA

# El ancho real del documento contra el del viewport. Es la medición literal de
# CA19 y la que usó la QA en BUG-3 (`scrollWidth` 979 contra `clientWidth` 360).
MEDIDA_DEL_DOCUMENTO = """() => ({
  scroll: document.documentElement.scrollWidth,
  cliente: document.documentElement.clientWidth,
})"""


def empresa_por_slug(sesion: Session, slug: str) -> Empresa:
    """La empresa sembrada por `tests/e2e/conftest.py`, que no expone sus ids.

    Los tres guiones nuevos necesitan **más** filas que las del humo (otra
    vacante, otros candidatos) y las siembran igual que el andamio: comprometidas
    en `criba_test` y borradas por el `TRUNCATE` del final del módulo.
    """
    return sesion.scalars(select(Empresa).where(Empresa.slug == slug)).one()


def entrar(page: Page, servidor: str, usuario: str) -> None:
    """Login por el formulario real, hasta `/vacantes` (el destino por omisión)."""
    _rellenar_y_enviar(page, f"{servidor}/entrar", usuario)
    page.wait_for_url(f"{servidor}/vacantes")


def entrar_con_destino(page: Page, servidor: str, usuario: str, destino: str) -> None:
    """Login entrando por `GET /entrar?destino=…`, que es el vector del issue #16.

    La plataforma propaga `destino` al campo oculto del formulario, así que es una
    **URL de Criba** la que decide a dónde va el navegador después de un login
    legítimo. Por eso el ataque se escribe así y no tocando el DOM.

    **No espera ninguna URL a propósito:** a dónde llega el navegador es
    exactamente lo que el test asercia.
    """
    _rellenar_y_enviar(page, f"{servidor}/entrar?destino={destino}", usuario)


def _rellenar_y_enviar(page: Page, url: str, usuario: str) -> None:
    page.goto(url)
    page.fill("#usuario", usuario)
    page.fill("#contrasena", CONTRASENA)
    page.click("button[type='submit']")


def abrir(page: Page, servidor: str, ruta: str) -> int:
    """Navega a una ruta de Criba y devuelve el estado HTTP de la respuesta."""
    respuesta = page.goto(f"{servidor}{ruta}")
    assert respuesta is not None, f"el navegador no recibió respuesta de {ruta}"
    return respuesta.status


def filas_con(page: Page, nombre: str) -> int:
    """Cuántas filas de la tabla de candidatos nombran a este candidato.

    Se cuenta sobre la fila (`data-testid="fila-candidato"`) y no sobre el texto
    de la página, para que un nombre que aparezca en un mensaje de error no
    cuente como «sigue en su vacante».
    """
    return page.locator('[data-testid="fila-candidato"]', has_text=nombre).count()
