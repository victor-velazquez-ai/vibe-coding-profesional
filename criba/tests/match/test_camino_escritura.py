"""PR-06 · el camino de escritura mínimo con el proveedor MOCK.

Cierra el circuito de la Etapa 0: llega un CV → se encola un trabajo → el bucle
lo toma → el MOCK devuelve un score fijo → se guarda → se ve en la vista. Los
cinco controles del paso (PLAN.md PR-06):

- el **circuito completo**, con el `empresa_id` tomado de la **fila de la cola** y
  no del candidato resuelto por otro camino (F5, `docs/arquitectura.md` §5.3);
- **CA9(a)**: subir un CV por la ruta de la plataforma encola **un trabajo por
  postulación abierta** del candidato en esa empresa —no uno por CV (R2·I4)—, con
  el idioma declarado en PR-03 (R6·M3);
- candidato y vacante de **empresas distintas** → error y **cero filas** (R2·I5);
- **la segunda puerta** (R4·B1): una postulación nueva **sin CV nuevo** encola el
  par, que es la que el plan no tenía y la que CA20 ve el 15-ene;
- el **interruptor global apagado** (R4·I1, R6·B1): los dos ganchos no encolan
  nada, el bucle no corre, `/match` no queda montado y la vista de vacante
  responde **200 con la lista de hoy**.

Los tres controles que este paso **no** trae y en qué paso llegan están en
`docs/prs/PR-06.md`: activación por empresa dentro de `encolar` (PR-10),
pseudonimización (PR-08), lease y reintentos (PR-14).
"""

from __future__ import annotations

import inspect

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.match.cola.ejecutor import pasadas, una_pasada
from app.match.cola.trabajos import encolar
from app.match.configuracion import IDIOMA_POR_OMISION
from app.match.repositories.contexto import SinContexto
from app.plataforma.modelos import Etapa, Postulacion, Vacante
from tests.dobles.proveedor import RAZONES, ProveedorContado
from tests.match.conftest import (
    EmpresaDePrueba,
    Entrar,
    repo_de,
    rutas_de_match,
    sembrar_candidatos,
)

CV_NUEVO = "CV sintético nuevo: licencia RN vigente en Texas, turno nocturno."


def _vacante(sesion: Session, empresa: EmpresaDePrueba, titulo: str) -> Vacante:
    vacante = Vacante(empresa_id=empresa.empresa.id, titulo=titulo, descripcion="Sintética.")
    sesion.add(vacante)
    sesion.flush()
    return vacante


def _postular(
    sesion: Session,
    empresa: EmpresaDePrueba,
    vacante: Vacante,
    etapa: Etapa = Etapa.POSTULADA,
) -> Postulacion:
    postulacion = Postulacion(
        empresa_id=empresa.empresa.id,
        candidato_id=empresa.candidato.id,
        vacante_id=vacante.id,
        etapa=etapa,
    )
    sesion.add(postulacion)
    sesion.flush()
    return postulacion


# --- el circuito, y el `empresa_id` de la fila de la cola -------------------


async def test_el_circuito_completo_toma_el_empresa_id_de_la_fila_de_la_cola(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    proveedor_contado: ProveedorContado,
) -> None:
    """Encolar → una pasada del bucle → una fila en `match_scores` por empresa.

    Las **dos** empresas de la fixture encolan a propósito: entre PR-06 y PR-10
    `encolar` todavía no comprueba la activación por empresa (R2·M2), y no hay
    fuga porque el único proveedor que existe es el doble —en producción, el
    MOCK— y nada sale de Criba (regla 1.5). Lo que este test sostiene es F5: el
    score de cada empresa sale del `empresa_id` **de su fila de la cola**.
    """
    encolar(sesion, northstar.vacante.id, northstar.candidato.id)
    encolar(sesion, meridian.vacante.id, meridian.candidato.id)

    assert await pasadas(sesion, proveedor_contado) == 2
    assert proveedor_contado.llamadas == 2

    for empresa in (northstar, meridian):
        repo = repo_de(sesion, empresa)
        trabajos, scores = repo.trabajos(), repo.scores()
        assert [t.estado for t in trabajos] == ["listo"], f"{empresa.slug}: la cola no se cerró"
        assert [(s.candidato_id, s.vacante_id, s.score, s.estado) for s in scores] == [
            (empresa.candidato.id, empresa.vacante.id, proveedor_contado.score, "listo")
        ]
        assert scores[0].razones == list(RAZONES)
        assert scores[0].idioma == trabajos[0].idioma == IDIOMA_POR_OMISION
        # F5, `docs/arquitectura.md` §5.3: el score hereda la empresa del trabajo.
        assert scores[0].empresa_id == trabajos[0].empresa_id == empresa.empresa.id

    # Y el bucle no tiene por dónde recibir otra empresa: ni contexto, ni
    # `empresa_id`. Lo único que puede usar es la fila que acaba de tomar.
    for funcion in (una_pasada, pasadas):
        sobrantes = [
            nombre
            for nombre in inspect.signature(funcion).parameters
            if "empresa" in nombre or "contexto" in nombre
        ]
        assert sobrantes == [], f"{funcion.__name__} recibe la empresa de fuera: {sobrantes}"


# --- 1 · CA9(a): un trabajo por postulación abierta ------------------------


def test_subir_un_cv_encola_un_trabajo_por_cada_postulacion_abierta(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    sesion_reclutador_northstar: TestClient,
) -> None:
    """CA9(a), R2·I4 · el CV cuelga del candidato (hecho 1 de PR-01).

    Una enfermera con postulaciones abiertas a enfermería y a administración
    necesita **dos** trabajos: con uno solo, en la segunda vacante su score
    seguiría siendo el del CV viejo. La postulación **cerrada** no encola: la
    enumeración es de las abiertas.
    """
    segunda = _vacante(sesion, northstar, "Administración · recepción")
    cerrada = _vacante(sesion, northstar, "TI · soporte de guardia")
    _postular(sesion, northstar, segunda)
    _postular(sesion, northstar, cerrada, etapa=Etapa.RECHAZADA)

    respuesta = sesion_reclutador_northstar.post(
        f"/candidatos/{northstar.candidato.id}/cv",
        data={"cv_texto": CV_NUEVO, "vacante_id": northstar.vacante.id},
    )
    assert respuesta.status_code == 200

    trabajos = repo_de(sesion, northstar).trabajos()
    assert {t.vacante_id for t in trabajos} == {northstar.vacante.id, segunda.id}
    assert [t.candidato_id for t in trabajos] == [northstar.candidato.id] * 2
    assert [t.estado for t in trabajos] == ["pendiente"] * 2
    # El idioma, desde el primer trabajo y declarado en PR-03 (R6·M3): no sale de
    # `usuarios.idioma`, que no existe (hecho 8 de PR-01).
    assert {t.idioma for t in trabajos} == {IDIOMA_POR_OMISION}
    assert repo_de(sesion, meridian).trabajos() == [], "un trabajo cruzó de empresa"


# --- 2 · candidato y vacante de empresas distintas -------------------------


def test_candidato_y_vacante_de_empresas_distintas_dejan_cero_filas(
    sesion: Session, northstar: EmpresaDePrueba, meridian: EmpresaDePrueba
) -> None:
    """R2·I5 · el contexto «desde la vacante» comprueba la pertenencia y falla."""
    with pytest.raises(SinContexto):
        encolar(sesion, northstar.vacante.id, meridian.candidato.id)
    with pytest.raises(SinContexto):
        encolar(sesion, meridian.vacante.id, northstar.candidato.id)
    # «Cero filas» **por empresa**, sobre las dos de la fixture (R6·I3).
    for empresa in (northstar, meridian):
        assert repo_de(sesion, empresa).trabajos() == []


# --- 3 · la segunda puerta: postulación nueva sin CV nuevo -----------------


def test_postular_sin_subir_ningun_cv_encola_el_par_nuevo(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    sesion_reclutador_northstar: TestClient,
) -> None:
    """R4·B1 · la otra puerta por la que nace un par (candidato, vacante).

    El candidato ya tiene su CV en la plataforma y **no sube nada**. Sin este
    gancho, el 15-ene aparece en «Pendientes de score» sin score y sin motivo,
    que es lo que CA20 prohíbe (y lo que el alcance 4 presupone resuelto).
    """
    nuevo = sembrar_candidatos(sesion, northstar, 1, postular=False)[0]
    assert nuevo.tiene_cv, "el caso de R4·B1 es el de un candidato que YA tiene CV"

    respuesta = sesion_reclutador_northstar.post(
        f"/vacantes/{northstar.vacante.id}/postulaciones", data={"candidato_id": nuevo.id}
    )
    assert respuesta.status_code == 200

    trabajos = repo_de(sesion, northstar).trabajos()
    assert [(t.candidato_id, t.vacante_id) for t in trabajos] == [(nuevo.id, northstar.vacante.id)]
    assert repo_de(sesion, meridian).trabajos() == []


# --- 4 · el interruptor global apagado ------------------------------------


async def test_con_el_interruptor_apagado_no_se_encola_y_la_vacante_responde_200(
    apagar_match: None,
    aplicacion: FastAPI,
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    entrar: Entrar,
    proveedor_contado: ProveedorContado,
) -> None:
    """R4·I1, R6·B1 · las tres mitades en el mismo test, a propósito.

    «Cero filas y ruta no montada» a secas se lee como «la fachada es no-op
    apagada», y eso deja sin candidatos la vista de vacante de las 40 empresas.
    Lo que el interruptor apaga: `encolar`, el bucle y los endpoints bajo
    `/match`. Lo que no apaga nunca: la vista de vacante de la plataforma.
    """
    cliente = entrar(northstar.reclutador)
    nuevo = sembrar_candidatos(sesion, northstar, 1, postular=False)[0]

    subida = cliente.post(
        f"/candidatos/{northstar.candidato.id}/cv",
        data={"cv_texto": CV_NUEVO, "vacante_id": northstar.vacante.id},
    )
    postulacion = cliente.post(
        f"/vacantes/{northstar.vacante.id}/postulaciones", data={"candidato_id": nuevo.id}
    )
    assert (subida.status_code, postulacion.status_code) == (200, 200)

    for empresa in (northstar, meridian):
        assert repo_de(sesion, empresa).trabajos() == [], f"{empresa.slug} encoló con Match apagado"
    assert await una_pasada(sesion, proveedor_contado) == 0, "el bucle corrió con Match apagado"
    assert proveedor_contado.llamadas == 0

    assert rutas_de_match(aplicacion) == [], "con el interruptor apagado `/match` sigue montado"
    assert aplicacion.state.match_montado is False

    for usuario in (northstar.reclutador, northstar.hiring_manager):
        respuesta = entrar(usuario).get(f"/vacantes/{northstar.vacante.id}")
        assert respuesta.status_code == 200, f"{usuario.rol} recibió {respuesta.status_code}"
        assert northstar.candidato.correo in respuesta.text, "la lista de hoy desapareció"
        assert 'data-testid="score"' not in respuesta.text
