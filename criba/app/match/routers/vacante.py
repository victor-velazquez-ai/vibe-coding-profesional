"""El router de Match: el fragmento de lista que Match sirve por su cuenta.

`GET /match/vacantes/{vacante_id}/lista?orden=fecha` (R6·I4). Bajo la opción (b)
de R3·I2 la **vista** de vacante es de la plataforma, así que este endpoint no
sirve la página: sirve el fragmento HTMX de la lista, y existe por tres razones
que el plan nombra:

- es el endpoint que da **403 al hiring manager** (CA18) y **404 con sesión de
  otra empresa** (CA1): sin él, los dos tests nacerían vacíos;
- es el que **PR-20 extiende** con `orden=score` y la sección de pendientes;
- es lo que el **interruptor global desmonta** (R6·B1), mientras la vista de
  vacante de la plataforma sigue respondiendo 200 sin él.

El router resuelve sesión → usuario, rol y `empresa_id`, y **no construye ni una
consulta** (`docs/arquitectura.md` §3, pasos 2-4): pide la lista al servicio.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.db import crear_sesion
from app.match.services.listado import ORDEN_POR_FECHA, ROLES_QUE_VEN_MATCH, listar_vacante
from app.plantillas import plantillas
from app.plataforma.sesion import Contexto, SesionActual

PREFIJO = "/match"

router = APIRouter(prefix=PREFIJO, tags=["match"])

BD = Annotated[Session, Depends(crear_sesion)]


@router.get("/vacantes/{vacante_id}/lista", response_class=HTMLResponse)
def lista(
    request: Request,
    bd: BD,
    sesion: SesionActual,
    contexto: Contexto,
    vacante_id: int,
    orden: str = ORDEN_POR_FECHA,
) -> Response:
    """El fragmento de la lista. `orden=score` llega en PR-20.

    **403 al hiring manager** (CA18): el 403 es de los endpoints de Match, no de
    la vista de vacante, que le sigue respondiendo 200 sin Match. **404 con
    sesión de otra empresa** (CA1): un ID de otra empresa no existe, nunca 403.
    """
    if sesion.rol not in ROLES_QUE_VEN_MATCH:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Match no está disponible para tu rol."
        )
    if orden != ORDEN_POR_FECHA:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El orden por score llega en PR-20."
        )
    datos = listar_vacante(bd, contexto, vacante_id, rol=sesion.rol)
    if datos is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return plantillas.TemplateResponse(
        request, "match/_lista.html", {"sesion": sesion, "lista": datos}
    )
