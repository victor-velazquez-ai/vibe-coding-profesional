"""E2E de **BUG-3 de la QA de frontend** (`qa/reportes/2026-11-22-frontend.md`).

Hallazgo: en un viewport de 360 por 640, `GET /vacantes/{id}` desborda en horizontal
—`document.documentElement.scrollWidth` 979 contra `clientWidth` 360 en la
vacante de enfermería, 999 contra 360 en la de TI—, así que hay que mover toda la
página (cabecera incluida) para llegar a las columnas CV, Etapa, Se postuló y
Acciones. `qa/TRIAGE.md` lo decide **«se arregla ahora»**, y por `CLAUDE.md` el
arreglo entra primero como E2E en rojo.

Criterio: **CA19 · Móvil a 360 px** (`SPEC.md`, D22, RI1, §19).

**Qué cubre este archivo y qué no, dicho en voz alta.** CA19 tiene tres mitades y
este E2E solo puede aserciar una:

- *no hay desbordamiento horizontal* → es lo que se asercia aquí, con la misma
  medición que pide la SPEC (`scrollWidth <= clientWidth`);
- *el score es visible* → se asercia como segunda línea de defensa: la columna la
  pinta PR-05 y ya existe, así que un arreglo que esconda la columna en móvil
  («display:none» a la tabla entera) no vale;
- *las razones y el control de orden son visibles y accionables* → **no existen
  todavía** (QA frontend BUG-1 y BUG-2, backend BUG-3 y BUG-4: `qa/TRIAGE.md` los
  manda a PR-20). No se asercian aquí porque hoy no hay nada que mirar; CA19
  queda cubierta del todo cuando PR-20 los traiga, y su test de los 500
  candidatos es el `tests/match/test_movil_360.py` que fija `SPEC.md`.

**Y la precondición de CA19 aquí no es la de la SPEC**: la SPEC dice «con 500
candidatos» y este guion abre la vacante con seis, que es lo que la QA reprodujo.
El desbordamiento lo causa el ancho de las columnas, no el número de filas; los
500 candidatos son la precondición de CA5 (p95) y viven en el test de `match/`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.plataforma.modelos import Candidato, Postulacion
from tests.e2e.ayudas import (
    MEDIDA_DEL_DOCUMENTO,
    abrir,
    empresa_por_slug,
    entrar,
)
from tests.e2e.conftest import SLUG_NORTHSTAR, Datos

# El viewport de D22 y del flujo 6 de la QA: el más estrecho que la v1 soporta.
MOVIL_360 = {"width": 360, "height": 640}

# Cinco candidatos más, para abrir la vacante con seis filas como las 5-6 de la
# reproducción de la QA. Sintéticos, con dominio `.test` (D3 modificado, D15, F12).
CANDIDATOS_DE_MAS = (
    ("Priscila Okonjo-Vega", "priscila.okonjo.vega@northstar-e2e.test", "+1 713 555 0111"),
    ("Tobías Nkemelu", "tobias.nkemelu@northstar-e2e.test", "+1 713 555 0112"),
    ("Marisol Echeverría", "marisol.echeverria@northstar-e2e.test", "+1 713 555 0113"),
    ("Yusuf Barrantes", "yusuf.barrantes@northstar-e2e.test", "+1 713 555 0114"),
    ("Ingrid Vasconcelos", "ingrid.vasconcelos@northstar-e2e.test", "+1 713 555 0115"),
)


@pytest.fixture(scope="module")
def vacante_poblada(motor_test: Engine, datos: Datos) -> Iterator[int]:
    """La vacante del andamio, con cinco candidatos más postulados a ella."""
    with Session(motor_test, expire_on_commit=False) as sesion:
        northstar = empresa_por_slug(sesion, SLUG_NORTHSTAR)
        for nombre, correo, telefono in CANDIDATOS_DE_MAS:
            candidato = Candidato(
                empresa_id=northstar.id,
                nombre=nombre,
                correo=correo,
                telefono=telefono,
                links=[],
            )
            sesion.add(candidato)
            sesion.flush()
            sesion.add(
                Postulacion(
                    empresa_id=northstar.id,
                    candidato_id=candidato.id,
                    vacante_id=datos.vacante_id,
                )
            )
        sesion.commit()
    yield datos.vacante_id


def test_la_vacante_no_desborda_en_horizontal_en_un_viewport_de_360_px(
    page: Page, servidor: str, datos: Datos, vacante_poblada: int
) -> None:
    """CA19 · la reclutadora de Northstar abre su vacante en un móvil de 360 px.

    El rojo de hoy está en la aserción de `scrollWidth <= clientWidth`, que es la
    literal de CA19 y la que la QA midió en 979 contra 360.
    """
    page.set_viewport_size(MOVIL_360)
    entrar(page, servidor, datos.reclutadora)
    assert abrir(page, servidor, f"/vacantes/{vacante_poblada}") == 200

    tabla = page.locator('[data-testid="tabla-candidatos"]')
    expect(tabla).to_be_visible()
    expect(page.locator('[data-testid="fila-candidato"]')).to_have_count(1 + len(CANDIDATOS_DE_MAS))

    medida = page.evaluate(MEDIDA_DEL_DOCUMENTO)
    assert medida["scroll"] <= medida["cliente"], (
        f"la página desborda a {MOVIL_360['width']} px: scrollWidth {medida['scroll']} contra "
        f"clientWidth {medida['cliente']} (CA19, QA frontend BUG-3). La tabla tiene que quedar "
        "contenida —su propio scroll horizontal—, no arrastrar la página entera."
    )

    # Segunda mitad de CA19 que hoy existe: esconder la tabla no es el arreglo.
    expect(page.locator('[data-testid="score"]').first).to_be_visible()


def test_la_reclutadora_de_meridian_sigue_recibiendo_404_a_360_px(
    page: Page, servidor: str, datos: Datos, vacante_poblada: int
) -> None:
    """Multiempresa, en el mismo viewport: Meridian no ve la vacante de Northstar.

    Va en este archivo porque el arreglo de CA19 toca la plantilla o la hoja de
    estilos de **esa misma vista**, y un arreglo que sirva un fragmento aparte
    para móvil («una plantilla sin el guardia») sería una fuga entre empresas, que
    es el requisito número uno del cliente (CA1, `CLAUDE.md`). Hoy esta aserción
    pasa: es lo que el arreglo no puede romper, no un hallazgo.
    """
    page.set_viewport_size(MOVIL_360)
    entrar(page, servidor, datos.reclutadora_meridian)
    assert abrir(page, servidor, f"/vacantes/{vacante_poblada}") == 404

    contenido = page.content()
    assert datos.nombre_candidato not in contenido
    assert datos.correo_candidato not in contenido
    for nombre, correo, _ in CANDIDATOS_DE_MAS:
        assert nombre not in contenido
        assert correo not in contenido
