"""PR-05 · abrir la vacante no espera a nadie, y no se rompe con Match apagado.

Cuatro controles del paso:

- **CA4** (D16, RE7, [01:53]): cero llamadas al proveedor al abrir, y la ruta de
  lectura **no recibe** el proveedor ni el MatchService como dependencia (F38);
- **guardia de número de consultas constante** (R6·M4): con 2 candidatos y con
  50, **el mismo número**. Lo que detecta el N+1 es la independencia del número
  de filas, no la cifra —un `<= 5` escrito a mano se convierte en el `<= 505`
  que deja pasar el N+1 de 500 filas en PR-20—;
- los **cuatro puntos de render** de la plataforma traen la misma lista (R6·I1):
  abrir la vacante, postular, subir CV y borrar;
- con el **interruptor global apagado** (R6·B1), la vacante sigue respondiendo
  **200 con la lista de hoy** para reclutadora y hiring manager, y los endpoints
  bajo `/match` **no están montados**.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.match.routers import vacante as vacante_de_match
from app.plataforma.rutas import candidatos, vacantes
from tests.dobles.proveedor import ProveedorContado
from tests.match.conftest import (
    EmpresaDePrueba,
    Entrar,
    rutas_de_match,
    sembrar_candidatos,
    sembrar_score,
)

PUNTOS = 83


@contextmanager
def contar_consultas(sesion: Session) -> Iterator[list[str]]:
    """Las sentencias que salen por la conexión del test, en orden."""
    conexion = sesion.get_bind()
    sentencias: list[str] = []

    def _antes(
        conn: object, cursor: object, sentencia: str, parametros: object, ctx: object, muchos: bool
    ) -> None:
        sentencias.append(sentencia)

    event.listen(conexion, "before_cursor_execute", _antes)
    try:
        yield sentencias
    finally:
        event.remove(conexion, "before_cursor_execute", _antes)


def test_abrir_la_vacante_no_llama_al_proveedor_ni_lo_recibe(
    sesion: Session,
    northstar: EmpresaDePrueba,
    sesion_reclutador_northstar: TestClient,
    proveedor_contado: ProveedorContado,
) -> None:
    """CA4 · la respuesta se construye **solo con scores ya guardados**.

    El doble está instanciado y no cableado, que es justo lo que se asercia: el
    día que alguien ponga «si no tiene score, lo calculo al abrir» (F38), el
    contador deja de ser cero y las firmas dejan de estar limpias.
    """
    sembrar_score(sesion, northstar, PUNTOS)
    respuesta = sesion_reclutador_northstar.get(f"/vacantes/{northstar.vacante.id}")
    assert respuesta.status_code == 200
    assert f'data-testid="score">{PUNTOS}<' in respuesta.text
    assert proveedor_contado.llamadas == 0

    for funcion in (vacantes.ver, candidatos.subir_cv, vacante_de_match.lista):
        anotaciones = [str(p.annotation) for p in inspect.signature(funcion).parameters.values()]
        prohibidas = [a for a in anotaciones if "Proveedor" in a or "MatchService" in a]
        assert prohibidas == [], f"{funcion.__name__} recibe el proveedor: {prohibidas}"


def test_el_numero_de_consultas_no_crece_con_el_numero_de_filas(
    sesion: Session,
    northstar: EmpresaDePrueba,
    sesion_reclutador_northstar: TestClient,
) -> None:
    """R6·M4, F27 · 2 filas y 50 filas, el mismo número de consultas."""
    url = f"/vacantes/{northstar.vacante.id}"
    sembrar_score(sesion, northstar, PUNTOS)
    sembrar_candidatos(sesion, northstar, 1)  # la fixture trae uno: dos en total
    assert sesion_reclutador_northstar.get(url).status_code == 200  # calentamiento

    sesion.flush()
    with contar_consultas(sesion) as con_dos:
        assert sesion_reclutador_northstar.get(url).status_code == 200

    sembrar_candidatos(sesion, northstar, 48)
    sesion.flush()
    with contar_consultas(sesion) as con_cincuenta:
        assert sesion_reclutador_northstar.get(url).status_code == 200

    assert con_dos, "el contador no vio ninguna consulta: el guardia pasaría vacío"
    assert len(con_dos) == len(con_cincuenta), (
        f"el número de consultas crece con las filas: {len(con_dos)} con 2 candidatos y "
        f"{len(con_cincuenta)} con 50\n" + "\n".join(con_cincuenta)
    )


def test_los_cuatro_puntos_de_render_traen_la_misma_lista(
    sesion: Session,
    northstar: EmpresaDePrueba,
    sesion_reclutador_northstar: TestClient,
) -> None:
    """R6·I1 · si solo se tocara `ver`, los tres POST devolverían la lista de la
    plataforma y la tabla con score desaparecería hasta recargar.

    **Quién se borra, y por qué no es el mismo que se postula (R7·M3, corregido
    en PR-06).** Desde PR-06 los ganchos encolan, y `match_trabajos.candidato_id`
    es una clave ajena **sin `ON DELETE CASCADE`** (PR-02, R3·M2): borrar un
    candidato que ya tiene fila de Match viola la FK hasta que PR-18 inserte el
    recorrido de Match antes del `delete`. Así que el que se borra es un
    candidato **sin postulaciones**, que por eso no tiene trabajo ni score.
    """
    sembrar_score(sesion, northstar, PUNTOS)
    para_postular, para_borrar = sembrar_candidatos(sesion, northstar, 2, postular=False)
    vacante_id, candidato_id = northstar.vacante.id, northstar.candidato.id
    cliente = sesion_reclutador_northstar

    respuestas = {
        "ver": cliente.get(f"/vacantes/{vacante_id}"),
        "postular": cliente.post(
            f"/vacantes/{vacante_id}/postulaciones", data={"candidato_id": para_postular.id}
        ),
        "subir_cv": cliente.post(
            f"/candidatos/{candidato_id}/cv",
            data={"cv_texto": "CV sintético nuevo.", "vacante_id": vacante_id},
        ),
        "borrar": cliente.post(
            f"/candidatos/{para_borrar.id}/borrar", data={"vacante_id": vacante_id}
        ),
    }
    for nombre, respuesta in respuestas.items():
        assert respuesta.status_code == 200, f"{nombre} respondió {respuesta.status_code}"
        assert f'data-testid="score">{PUNTOS}<' in respuesta.text, f"{nombre} sin score"
        assert northstar.candidato.correo in respuesta.text, f"{nombre} sin la lista de hoy"


def test_con_el_interruptor_apagado_la_vacante_responde_200_con_la_lista_de_hoy(
    apagar_match: None,
    aplicacion: FastAPI,
    sesion: Session,
    northstar: EmpresaDePrueba,
    entrar: Entrar,
) -> None:
    """R6·B1 · el interruptor apaga `/match`, **nunca** la vista de vacante.

    Es la mitad que falta del test 4 de PR-06: allí se asercia que no se escribe
    nada; aquí, que no se rompe nada de lo que la plataforma ya servía a las 40
    empresas.
    """
    sembrar_score(sesion, northstar, PUNTOS)
    assert rutas_de_match(aplicacion) == [], "con el interruptor apagado `/match` sigue montado"
    assert aplicacion.state.match_montado is False

    for usuario in (northstar.reclutador, northstar.hiring_manager):
        cliente = entrar(usuario)
        respuesta = cliente.get(f"/vacantes/{northstar.vacante.id}")
        assert respuesta.status_code == 200, f"{usuario.rol} recibió {respuesta.status_code}"
        assert northstar.candidato.correo in respuesta.text, "la lista de hoy desapareció"
        assert 'data-testid="score"' not in respuesta.text
        assert cliente.get(f"/match/vacantes/{northstar.vacante.id}/lista").status_code == 404
