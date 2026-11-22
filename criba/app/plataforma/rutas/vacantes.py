"""Las vacantes y la vista de vacante de hoy: sus candidatos, por fecha.

`GET /vacantes/{vacante_id}` es **la vista que PR-01 tenía que localizar**
(PLAN.md §2, «la cuarta puerta»; PR-01 hecho 4): es la ruta por la que una
reclutadora llega hoy a la vacante y por la que hoy se revisan «500 CVs uno por
uno» (`llamadas/2026-11-20-tomas.md` [00:16]).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.db import crear_sesion
from app.match.fachada import encolar
from app.plantillas import plantillas
from app.plataforma.fragmentos import contexto_candidatos, fragmento_candidatos
from app.plataforma.repositorio import RepositorioEmpresa, SinPermiso
from app.plataforma.sesion import Contexto, SesionActual, SesionQueEscribe

router = APIRouter(tags=["vacantes"])

BD = Annotated[Session, Depends(crear_sesion)]


@router.get("/vacantes", response_class=HTMLResponse)
def listar(request: Request, bd: BD, sesion: SesionActual, contexto: Contexto) -> Response:
    repo = RepositorioEmpresa(bd, contexto.empresa_id)
    return plantillas.TemplateResponse(
        request,
        "vacantes.html",
        {
            "sesion": sesion,
            "vacantes": [(v, repo.conteo_postulaciones(v.id)) for v in repo.vacantes()],
        },
    )


@router.get("/vacantes/{vacante_id}", response_class=HTMLResponse)
def ver(
    request: Request, bd: BD, sesion: SesionActual, contexto: Contexto, vacante_id: int
) -> Response:
    repo = RepositorioEmpresa(bd, contexto.empresa_id)
    return plantillas.TemplateResponse(
        request,
        "vacante.html",
        {"sesion": sesion} | contexto_candidatos(bd, repo, sesion, contexto, vacante_id),
    )


@router.post("/vacantes/{vacante_id}/postulaciones", response_class=HTMLResponse)
def postular(
    request: Request,
    bd: BD,
    sesion: SesionQueEscribe,
    contexto: Contexto,
    vacante_id: int,
    candidato_id: Annotated[int, Form()],
) -> Response:
    """Crea el par (candidato, vacante) **sin subir ningún CV**.

    Es la segunda puerta por la que nace un par (PLAN.md PR-06, ronda 4 B1): el
    candidato ya tiene su CV cargado en la plataforma y no sube nada aquí, así
    que el gancho de la subida no se dispara y sin este el par nunca se puntúa
    —el 15-ene aparecería en «Pendientes de score» sin score y sin motivo, que es
    lo que CA20 prohíbe—.
    """
    repo = RepositorioEmpresa(bd, contexto.empresa_id)
    if repo.vacante(vacante_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    try:
        repo.crear_postulacion(candidato_id, vacante_id)
    except SinPermiso as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND) from exc
    # El segundo gancho de PR-06 (R4·B1): una llamada a `encolar` y nada más.
    encolar(bd, vacante_id, candidato_id)
    bd.commit()
    return fragmento_candidatos(request, bd, repo, sesion, contexto, vacante_id)
