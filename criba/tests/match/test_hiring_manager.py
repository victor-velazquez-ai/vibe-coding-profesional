"""PR-05 · CA18 · el hiring manager abre la vacante y no ve nada de Match.

Los dos lados del criterio, que el plan separa a propósito (R1·M1): la **vista de
vacante** responde **200 sin score** —no 403, que le quitaría la lectura que hoy
tiene y que ninguna decisión le quita— y los **endpoints propios de Match**
responden **403**. El que ejerce ese 403 en la Etapa 0 es
`GET /match/vacantes/{vacante_id}/lista` (R6·I4).

Y la tercera cosa, que tres rondas dejaron sin dueño (R5·I2): **quién pinta la
columna de score**. Si nadie la pinta, el E2E de PR-07 nace rojo.
"""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy.orm import Session

from tests.match.conftest import EmpresaDePrueba, Entrar, rutas_de_match, sembrar_score

PUNTOS = 72


def test_el_hiring_manager_abre_la_vacante_y_recibe_200_sin_nada_de_match(
    sesion: Session, northstar: EmpresaDePrueba, entrar: Entrar
) -> None:
    """CA18 · 200, la lista de hoy completa, y sin score, razones, orden ni pendientes."""
    sembrar_score(sesion, northstar, PUNTOS)
    respuesta = entrar(northstar.hiring_manager).get(f"/vacantes/{northstar.vacante.id}")
    assert respuesta.status_code == 200
    assert northstar.candidato.correo in respuesta.text, "la lista de hoy llega recortada"
    assert 'data-testid="score"' not in respuesta.text
    assert "Pendientes de score" not in respuesta.text
    assert "orden=score" not in respuesta.text


def test_los_endpoints_de_match_responden_403_al_hiring_manager(
    aplicacion: FastAPI, northstar: EmpresaDePrueba, entrar: Entrar
) -> None:
    """CA18, segunda mitad · con **enumeración de rutas**, como CA1 (F34)."""
    rutas = rutas_de_match(aplicacion)
    assert rutas, "sin endpoint propio de Match este test sería vacío (R6·I4)"
    cliente = entrar(northstar.hiring_manager)
    for ruta in rutas:
        respuesta = cliente.get(ruta.format(vacante_id=northstar.vacante.id))
        assert respuesta.status_code == 403, f"{ruta} no le dio 403 al hiring manager"


def test_la_columna_de_score_la_ve_la_reclutadora_y_el_hiring_manager_no(
    sesion: Session, northstar: EmpresaDePrueba, entrar: Entrar
) -> None:
    """R5·I2 · la misma plantilla, la columna condicionada por rol."""
    sembrar_score(sesion, northstar, PUNTOS)
    url = f"/vacantes/{northstar.vacante.id}"
    de_reclutadora = entrar(northstar.reclutador).get(url).text
    del_hiring_manager = entrar(northstar.hiring_manager).get(url).text
    assert f'data-testid="score">{PUNTOS}<' in de_reclutadora
    assert 'data-testid="score"' not in del_hiring_manager
