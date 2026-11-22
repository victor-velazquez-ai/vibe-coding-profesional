"""Entrar y salir. Formulario y cookie de sesión firmada, atada a una empresa."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.db import crear_sesion
from app.plantillas import plantillas
from app.plataforma import repositorio
from app.plataforma.modelos import Rol
from app.plataforma.seguridad import verificar_contrasena
from app.plataforma.sesion import (
    RUTA_POR_OMISION,
    UsuarioSesion,
    borrar_cookie,
    escribir_cookie,
    ruta_interna,
    sesion_opcional,
)

router = APIRouter(tags=["autenticacion"])

BD = Annotated[Session, Depends(crear_sesion)]


@router.get("/", include_in_schema=False)
def raiz(sesion: Annotated[UsuarioSesion | None, Depends(sesion_opcional)]) -> RedirectResponse:
    destino = "/vacantes" if sesion else "/entrar"
    return RedirectResponse(destino, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/entrar", response_class=HTMLResponse)
def formulario(request: Request, bd: BD, destino: str = RUTA_POR_OMISION) -> Response:
    return plantillas.TemplateResponse(
        request,
        "entrar.html",
        {
            "destino": destino,
            "empresas": repositorio.empresas(bd),
            "error": None,
            "usuario": "",
        },
    )


@router.post("/entrar", response_class=HTMLResponse)
def entrar(
    request: Request,
    bd: BD,
    usuario: Annotated[str, Form()],
    contrasena: Annotated[str, Form()],
    empresa: Annotated[str, Form()] = "",
    destino: Annotated[str, Form()] = RUTA_POR_OMISION,
) -> Response:
    fila = repositorio.usuario_por_nombre(bd, usuario.strip())
    valido = fila is not None and verificar_contrasena(contrasena, fila.hash_contrasena)

    if not valido or fila is None:
        return _con_error(request, bd, usuario, destino, "Usuario o contraseña incorrectos.")

    # El staff de Criba no pertenece a ninguna empresa: elige una al entrar y el
    # acceso queda auditado (D6). El resto hereda la de su usuario.
    if fila.rol is Rol.STAFF_CRIBA:
        elegida = repositorio.empresa_por_slug(bd, empresa.strip()) if empresa.strip() else None
        if elegida is None:
            return _con_error(
                request, bd, usuario, destino, "Elige la empresa a la que vas a dar soporte."
            )
        repositorio.registrar_acceso_soporte(
            bd, usuario_id=fila.id, empresa_id=elegida.id, motivo="soporte: entrada a la empresa"
        )
        bd.commit()
        empresa_id, empresa_nombre, es_soporte = elegida.id, elegida.nombre, True
    else:
        if fila.empresa is None:  # el CHECK de la tabla lo impide; aquí es cinturón
            return _con_error(request, bd, usuario, destino, "Tu usuario no tiene empresa.")
        empresa_id, empresa_nombre, es_soporte = fila.empresa_id or 0, fila.empresa.nombre, False

    respuesta = RedirectResponse(
        ruta_interna(destino),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    escribir_cookie(
        respuesta,
        UsuarioSesion(
            usuario_id=fila.id,
            usuario=fila.usuario,
            nombre=fila.nombre,
            rol=fila.rol,
            empresa_id=empresa_id,
            empresa_nombre=empresa_nombre,
            es_soporte=es_soporte,
        ),
    )
    return respuesta


@router.post("/salir")
def salir() -> RedirectResponse:
    respuesta = RedirectResponse("/entrar", status_code=status.HTTP_303_SEE_OTHER)
    borrar_cookie(respuesta)
    return respuesta


def _con_error(request: Request, bd: Session, usuario: str, destino: str, error: str) -> Response:
    return plantillas.TemplateResponse(
        request,
        "entrar.html",
        {
            "destino": destino,
            "empresas": repositorio.empresas(bd),
            "error": error,
            "usuario": usuario,
        },
        status_code=status.HTTP_401_UNAUTHORIZED,
    )
