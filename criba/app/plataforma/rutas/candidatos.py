"""El editor de CV, su subida y el borrado de candidato.

Las dos rutas que el resto del plan necesita localizar:

- `POST /candidatos/{candidato_id}/cv` → **el gancho de PR-06** (`SPEC.md`
  alcance 7, CA9(a)), ya puesto. El CV cuelga del candidato, así que una subida
  afecta a todas sus postulaciones abiertas y encola **una por cada una**;
- `POST /candidatos/{candidato_id}/borrar` → **el gancho de PR-18**. Es el
  procedimiento de borrado de hoy (`llamadas/2026-11-20-tomas.md` [04:35]: ya
  llegan peticiones). Delega en `RepositorioEmpresa.borrar_candidato`, que es el
  único lugar donde hay que insertar el recorrido de Match.

Y desde PR-PERF-1, `GET /candidatos/{candidato_id}/cv`: el **editor** de ese CV,
que la lista ya no trae consigo (`perf/MEDICION.md` §6 nº 1). Es la única ruta
nueva, y es de lectura.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.db import crear_sesion
from app.match.fachada import encolar
from app.plantillas import plantillas
from app.plataforma.fragmentos import fragmento_candidatos
from app.plataforma.repositorio import RepositorioEmpresa, SinPermiso
from app.plataforma.sesion import Contexto, SesionQueEscribe

router = APIRouter(tags=["candidatos"])

BD = Annotated[Session, Depends(crear_sesion)]


@router.get("/candidatos/{candidato_id}/cv", response_class=HTMLResponse)
def editor_de_cv(
    request: Request,
    bd: BD,
    sesion: SesionQueEscribe,
    contexto: Contexto,
    candidato_id: int,
    vacante_id: int,
) -> Response:
    """El `<textarea>` con el CV de un candidato, pedido aparte por HTMX.

    La lista de la vacante dejó de traer el texto del CV de las 500 filas
    (`perf/MEDICION.md` §6 nº 1), así que el editor se pide **cuando se abre**.
    Lo que trae es lo mismo que la fila precargaba antes: por eso el formulario
    es la misma plantilla, `_editor_cv.html`.

    Lo de siempre para una ruta nueva de la plataforma:

    - `SesionQueEscribe` → el hiring manager recibe **403**: es de solo lectura y
      no edita CVs (CA18, D10, `exigir_escritura`);
    - el `empresa_id` sale de la cookie y nunca de la URL, así que el candidato de
      otra empresa es un **404** sin nada suyo en el cuerpo (CA1, D4);
    - `vacante_id` es la lista que el formulario repinta al guardar. No se
      comprueba aquí porque este endpoint no lee nada de ella: vuelve en el
      `POST`, y ahí sí se resuelve con el contexto de empresa (404 si no es suya).
    """
    candidato = RepositorioEmpresa(bd, contexto.empresa_id).candidato(candidato_id)
    if candidato is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return plantillas.TemplateResponse(
        request, "_editor_cv.html", {"candidato": candidato, "vacante_id": vacante_id}
    )


@router.post("/candidatos/{candidato_id}/cv", response_class=HTMLResponse)
def subir_cv(
    request: Request,
    bd: BD,
    sesion: SesionQueEscribe,
    contexto: Contexto,
    candidato_id: int,
    cv_texto: Annotated[str, Form()],
    vacante_id: Annotated[int, Form()],
) -> Response:
    repo = RepositorioEmpresa(bd, contexto.empresa_id)
    texto = cv_texto.strip()
    if not texto:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El CV viene vacío.")
    try:
        repo.guardar_cv(candidato_id, texto)
    except SinPermiso as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND) from exc
    # El gancho de PR-06 (CA9(a), alcance 7): **un trabajo por postulación
    # abierta**, porque el CV cuelga del candidato (hecho 1 de PR-01) y una
    # enfermera postulada a enfermería y a administración necesita dos scores
    # (R2·I4). Las postulaciones son tablas de la plataforma, así que las enumera
    # el gancho con su propia consulta (R3·M3); de Match solo se llama a
    # `encolar`, sin reglas propias y en esta misma transacción (R6·I2).
    for postulacion in repo.postulaciones_abiertas(candidato_id):
        encolar(bd, postulacion.vacante_id, candidato_id)
    bd.commit()
    return fragmento_candidatos(request, bd, repo, sesion, contexto, vacante_id)


@router.post("/candidatos/{candidato_id}/borrar")
def borrar(
    request: Request,
    bd: BD,
    sesion: SesionQueEscribe,
    contexto: Contexto,
    candidato_id: int,
    vacante_id: Annotated[int, Form()] = 0,
) -> Response:
    repo = RepositorioEmpresa(bd, contexto.empresa_id)
    try:
        # Primero el guardia y después el borrado, que es el orden que faltaba
        # (QA backend BUG-2): con un `vacante_id` ajeno se respondía 404 **ya
        # borrado**. Sin `vacante_id` no hay vacante que comprobar: la respuesta
        # es la redirección de abajo y no el fragmento de ninguna lista.
        if vacante_id:
            repo.exigir_vacante_del_borrado(candidato_id, vacante_id)
        repo.borrar_candidato(candidato_id)
    except SinPermiso as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND) from exc
    bd.commit()
    if vacante_id:
        return fragmento_candidatos(request, bd, repo, sesion, contexto, vacante_id)
    return RedirectResponse("/vacantes", status_code=status.HTTP_303_SEE_OTHER)
