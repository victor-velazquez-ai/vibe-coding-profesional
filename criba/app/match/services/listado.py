"""La lista de candidatos de una vacante (PR-05, opción (b) de R3·I2).

La vista de vacante es **de la plataforma** —`GET /vacantes/{vacante_id}`, hecho 4
de PR-01— y delega el listado aquí, por la fachada. Lo que este módulo devuelve es
siempre **la lista de hoy completa**, por fecha de postulación, y le añade score,
razones y estado según el rol, la activación de la empresa y el interruptor
global. Nunca una lista vacía, nunca un 404 por falta de Match, nunca un 500:

- hiring manager → la lista de hoy, sin nada de Match (CA18, D10);
- empresa sin anexo de subprocesador → la lista de hoy, sin nada (CA3, D7);
- interruptor global apagado → la lista de hoy, sin nada (R6·B1).

Devuelve `None` **solo** si la vacante no es de la empresa del contexto: el
llamador lo traduce a 404, que es exactamente lo que la vista hace hoy.

El orden por score y la sección de pendientes son de PR-20; aquí el orden es el
de hoy y va declarado en la línea de log, para que el día que cambie se vea.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.orm import Session

from app.match.configuracion import ajustes_match
from app.match.repositories.contexto import ContextoDeEmpresa
from app.match.repositories.match_repo import RepositorioDeMatch
from app.match.repositories.modelos import ScoreDeMatch
from app.plataforma.modelos import Postulacion, Rol, Vacante
from app.plataforma.repositorio import CandidatoDeLista, FilaCandidato, RepositorioEmpresa
from app.plataforma.sesion import ContextoEmpresa

ORDEN_POR_FECHA = "fecha"
# Bajo `app.`, como `LOG_DEL_EJECUTOR` (`cola/ejecutor.py`): `SoloNuestrosLoggers`
# (`app/registro.py`) solo deja pasar al archivo los loggers `app` o `app.*`, y
# con el prefijo `criba.` la línea de `match.listar_vacante` no llegaba nunca a
# `staging/logs/app.jsonl` (RUNBOOK.md §2). Un solo prefijo en el proceso.
LOG_DEL_LISTADO = "app.match.listado"

# Quién ve Match: el hiring manager no (CA18, D10) y el staff de Criba sí, porque
# CA17 presupone que soporte puede ver el score y las razones (D6, D21).
ROLES_QUE_VEN_MATCH = frozenset({Rol.RECLUTADOR, Rol.ADMIN_EMPRESA, Rol.STAFF_CRIBA})

_log = logging.getLogger(LOG_DEL_LISTADO)


@dataclass(frozen=True, slots=True)
class FilaDeLista:
    """Una fila de hoy, con lo de Match encima si el rol y la empresa lo permiten.

    El candidato es el `CandidatoDeLista` de la plataforma —sin `cv_texto`, que
    la lista no pinta (`perf/MEDICION.md` §6 nº 1)—: Match no añade ni quita
    columnas de la fila de hoy, solo le pone score, razones y estado encima.
    """

    candidato: CandidatoDeLista
    postulacion: Postulacion
    notas: int
    score: int | None = None
    razones: tuple[str, ...] = ()
    estado: str | None = None


@dataclass(frozen=True, slots=True)
class ListaDeVacante:
    """Lo que los cuatro puntos de render de la plataforma pintan."""

    vacante: Vacante
    filas: list[FilaDeLista]
    muestra_score: bool
    orden: str = ORDEN_POR_FECHA


def listar_vacante(
    bd: Session, contexto: ContextoEmpresa, vacante_id: int, *, rol: Rol
) -> ListaDeVacante | None:
    """La lista de la vacante, o `None` si no es de la empresa del contexto.

    `contexto` es el **`ContextoEmpresa` tipado** que sale de la cookie
    (`app/plataforma/sesion.py`), nunca un `empresa_id` entero (PR-04, test 6), y
    `bd` es la sesión de la petición: aquí no se hace `commit()` (R6·I2).

    `rol` va aparte porque el rol vive en la sesión del usuario y no en el
    contexto de empresa, y CA18 se decide con él.
    """
    comienzo = time.perf_counter()
    plataforma = RepositorioEmpresa(bd, contexto.empresa_id)
    vacante = plataforma.vacante(vacante_id)
    if vacante is None:
        return None

    repo = RepositorioDeMatch(bd, ContextoDeEmpresa.desde_la_peticion(contexto))
    filas_de_hoy = plataforma.candidatos_de_vacante(vacante_id)
    con_match = _match_visible(rol, repo)
    scores = _scores_por_candidato(repo, vacante_id) if con_match else {}
    filas = [_fila(fila, scores.get(fila.candidato.id)) for fila in filas_de_hoy]

    _registrar(contexto, vacante_id, con_match, len(filas), comienzo)
    return ListaDeVacante(vacante=vacante, filas=filas, muestra_score=con_match)


def _match_visible(rol: Rol, repo: RepositorioDeMatch) -> bool:
    """Las tres condiciones, cada una donde se decide: interruptor, rol y D7.

    **La activación por empresa ya no se lee aquí** (PLAN.md PR-10): este módulo
    leía `match_activado` por su cuenta, y entonces D7 se decidía en dos sitios
    —aquí y en el camino de escritura, cuando llegara— que es lo que el criterio
    de terminado de PR-10 prohíbe. Se pregunta al repositorio, que es el punto
    único de acceso a datos (`docs/arquitectura.md` §4 y §5.3).

    El orden importa: con el **interruptor global apagado** o con un rol que no ve
    Match (CA18), no se le pregunta nada al repositorio.
    """
    if not ajustes_match().activo or rol not in ROLES_QUE_VEN_MATCH:
        return False
    return repo.empresa_activada()


def _scores_por_candidato(repo: RepositorioDeMatch, vacante_id: int) -> dict[int, ScoreDeMatch]:
    """**Una** consulta para toda la lista, que es lo que el guardia de R6·M4
    asercia: el número de consultas no crece con el número de filas (F27)."""
    return {fila.candidato_id: fila for fila in repo.scores_de_vacante(vacante_id)}


def _fila(fila: FilaCandidato, score: ScoreDeMatch | None) -> FilaDeLista:
    base = (fila.candidato, fila.postulacion, fila.notas)
    if score is None:
        return FilaDeLista(*base)
    return FilaDeLista(*base, score.score, tuple(score.razones), score.estado)


def _registrar(
    contexto: ContextoEmpresa, vacante_id: int, con_match: bool, filas: int, comienzo: float
) -> None:
    """La línea JSON de `docs/arquitectura.md` §2: `request_id` y `empresa_id`.

    **Nada del candidato** (CA1, «ni log suyo»; D15, F12): ni id, ni nombre, ni
    correo, ni score. El `request_id` es por llamada: esta plataforma no tiene
    middleware que lo propague y crearlo no es de este paso.
    """
    _log.info(
        json.dumps(
            {
                "evento": "match.listar_vacante",
                "request_id": uuid4().hex[:12],
                "empresa_id": contexto.empresa_id,
                "vacante_id": vacante_id,
                "orden": ORDEN_POR_FECHA,
                "con_score": con_match,
                "filas": filas,
                "ms": round((time.perf_counter() - comienzo) * 1000, 1),
            }
        )
    )
