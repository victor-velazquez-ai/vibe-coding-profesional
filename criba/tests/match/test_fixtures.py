"""PR-03 · el material de prueba que usan casi todos los pasos siguientes.

Prueba las fixtures, no Match: que las dos empresas son las esperadas, que el
doble cuenta llamadas y que el helper produce sesiones de empresas distintas
**que no se mezclan** (D4, CA1, el requisito número uno).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.match.configuracion import IDIOMA_POR_OMISION, ajustes_match
from app.plataforma.modelos import AccesoSoporte, Empresa, Rol, Usuario
from tests.dobles.proveedor import (
    ErrorDelProveedor,
    LlamadaProhibida,
    ProveedorContado,
    proveedor_con_error,
    proveedor_con_timeout,
    proveedor_que_prohibe_llamadas,
)
from tests.match.conftest import (
    ARCHIVOS_DE_CV,
    EmpresaDePrueba,
    Entrar,
    SesionDeSoporte,
    cv,
)


def test_las_fixtures_crean_las_dos_empresas_y_su_configuracion(
    sesion: Session, northstar: EmpresaDePrueba, meridian: EmpresaDePrueba
) -> None:
    """D7, CA3, R4·I1 y R6·M3: las dos empresas y la misma regla por sus lados.

    Northstar encendida a propósito; Meridian apagada por no haberla encendido;
    una empresa que ninguna fixture nombra, también apagada —«ninguna empresa
    activada» es el valor por omisión—; y un idioma declarado, que es lo que
    PR-06 necesita escribir en cada trabajo desde el primero.
    """
    assert sesion.scalar(select(func.count()).select_from(Empresa)) == 2
    assert {northstar.slug, meridian.slug} == {"northstar-health", "meridian-logistics"}
    ajustes = ajustes_match()
    assert ajustes.match_activado(northstar.slug) is True
    assert ajustes.match_activado(meridian.slug) is False
    assert ajustes.match_activado("empresa-que-nadie-activo") is False
    assert ajustes.idioma_de(northstar.slug) == IDIOMA_POR_OMISION == "en"


def test_tres_roles_por_empresa_y_un_solo_staff_sin_empresa(
    sesion: Session, northstar: EmpresaDePrueba, meridian: EmpresaDePrueba, staff: Usuario
) -> None:
    """R6·M1: el CHECK `ck_usuarios_staff_sin_empresa` no deja fingir un staff por empresa."""
    for empresa in (northstar, meridian):
        roles = sesion.scalars(
            select(Usuario.rol).where(Usuario.empresa_id == empresa.empresa.id)
        ).all()
        assert set(roles) == {Rol.RECLUTADOR, Rol.ADMIN_EMPRESA, Rol.HIRING_MANAGER}
    del_staff = sesion.scalars(select(Usuario).where(Usuario.rol == Rol.STAFF_CRIBA)).all()
    assert [u.empresa_id for u in del_staff] == [None] and staff.empresa_id is None


def test_las_sesiones_de_empresas_distintas_no_se_mezclan(
    entrar: Entrar,
    sesion_reclutador_northstar: TestClient,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
) -> None:
    """Las dos sesiones viven a la vez y cada una ve solo su empresa (CA1)."""
    norte, sur = sesion_reclutador_northstar, entrar(meridian.reclutador)
    assert norte.get(f"/vacantes/{northstar.vacante.id}").status_code == 200
    assert norte.get(f"/vacantes/{meridian.vacante.id}").status_code == 404
    assert sur.get(f"/vacantes/{meridian.vacante.id}").status_code == 200
    assert sur.get(f"/vacantes/{northstar.vacante.id}").status_code == 404


def test_la_sesion_de_soporte_entra_por_el_camino_de_produccion(
    sesion: Session,
    sesion_soporte: SesionDeSoporte,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
) -> None:
    """R6·M1: elige empresa en `POST /entrar` y deja fila en `accesos_soporte` (D6).

    Si la fixture inventara el contexto, el test de soporte de PR-05 no
    ejercería el camino real.
    """
    cliente = sesion_soporte(northstar)
    assert cliente.get(f"/vacantes/{northstar.vacante.id}").status_code == 200
    assert cliente.get(f"/vacantes/{meridian.vacante.id}").status_code == 404
    filas = sesion.scalars(select(AccesoSoporte)).all()
    assert [(f.empresa_id, bool(f.motivo)) for f in filas] == [(northstar.empresa.id, True)]


async def test_el_doble_cuenta_llamadas_y_trae_sus_tres_variantes(
    proveedor_contado: ProveedorContado,
) -> None:
    """El contador de CA4 (`llamadas == 0`), la prohibición de CA3 y los dos
    fallos de CA6. La llamada prohibida **queda contada**, para poder explicar
    el fallo con un número y no solo con una excepción."""
    assert proveedor_contado.llamadas == 0
    respuesta = await proveedor_contado.puntuar({"cv": "pseudonimizado"}, "en")
    assert proveedor_contado.llamadas == 1
    assert respuesta.score is not None and len(respuesta.razones) == 3
    assert proveedor_contado.idiomas == ["en"]

    prohibido = proveedor_que_prohibe_llamadas()
    with pytest.raises(LlamadaProhibida):
        await prohibido.puntuar(object(), "en")
    assert prohibido.llamadas == 1
    with pytest.raises(TimeoutError):
        await proveedor_con_timeout().puntuar(object(), "en")
    with pytest.raises(ErrorDelProveedor):
        await proveedor_con_error(500).puntuar(object(), "en")


@pytest.mark.parametrize("nombre", ARCHIVOS_DE_CV)
def test_los_cv_de_fixture_se_declaran_sinteticos(nombre: str) -> None:
    """D3 modificado, D15, F12: el archivo lo dice de sí mismo, para que nadie
    deje caer un CV real aquí sin que un test se queje."""
    assert "sintético" in cv(nombre).lower()
