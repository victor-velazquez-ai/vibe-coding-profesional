"""Fragmentos HTMX compartidos por las rutas de la plataforma.

La lista de candidatos de una vacante se renderiza desde cuatro sitios (abrir la
vacante, postular, subir CV, borrar). Vive en un solo lugar para que las cuatro
muestren exactamente lo mismo.

**Y es el punto donde la plataforma delega el listado en Match** (PLAN.md PR-05,
opción (b) de R3·I2): los cuatro pasan por `contexto_candidatos`, así que el punto
que se toca es uno. Se llama a `listar_vacante` de la **fachada** —el único import
de Match permitido desde aquí (PR-04, regla (b))— con la sesión de la petición y
el `ContextoEmpresa` tipado de la cookie, nunca un `empresa_id` entero.

Con Match apagado —interruptor global, empresa sin anexo o rol sin acceso— la
fachada devuelve **la lista de hoy**, que es la misma respuesta que estas cuatro
rutas daban antes de que Match existiera.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.match.fachada import listar_vacante
from app.plantillas import plantillas
from app.plataforma.repositorio import RepositorioEmpresa
from app.plataforma.sesion import ContextoEmpresa, UsuarioSesion


def contexto_candidatos(
    bd: Session,
    repo: RepositorioEmpresa,
    sesion: UsuarioSesion,
    contexto: ContextoEmpresa,
    vacante_id: int,
) -> dict[str, object]:
    lista = listar_vacante(bd, contexto, vacante_id, rol=sesion.rol)
    if lista is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return {
        "sesion": sesion,
        "vacante": lista.vacante,
        "filas": lista.filas,
        "muestra_score": lista.muestra_score,
        "disponibles": (
            repo.candidatos_sin_postular_a(vacante_id) if sesion.puede_escribir else []
        ),
    }


def fragmento_candidatos(
    request: Request,
    bd: Session,
    repo: RepositorioEmpresa,
    sesion: UsuarioSesion,
    contexto: ContextoEmpresa,
    vacante_id: int,
) -> HTMLResponse:
    return plantillas.TemplateResponse(
        request, "_candidatos.html", contexto_candidatos(bd, repo, sesion, contexto, vacante_id)
    )
