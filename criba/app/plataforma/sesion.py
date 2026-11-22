"""La sesión y su empresa.

Regla de la plataforma (`docs/contexto.md`): **la sesión está atada a una
empresa**. Un reclutador, un admin y un hiring manager la heredan de su usuario;
el staff de Criba la elige al entrar y queda auditado en `accesos_soporte` (D6).

Ningún handler lee `empresa_id` de la URL: sale siempre de la cookie, por
`contexto_empresa`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status

from app.configuracion import ajustes
from app.plataforma.modelos import Rol
from app.plataforma.seguridad import firmar_sesion, leer_sesion

ROLES_QUE_ESCRIBEN = frozenset({Rol.RECLUTADOR, Rol.ADMIN_EMPRESA})
RUTA_POR_OMISION = "/vacantes"


class NecesitaEntrar(Exception):
    """Sin sesión válida. El manejador de la app redirige a /entrar."""

    def __init__(self, destino: str = RUTA_POR_OMISION) -> None:
        self.destino = destino


def ruta_interna(destino: str) -> str:
    """A dónde manda el `destino` de un formulario, o la ruta por omisión.

    Un solo punto para la regla: quien construye una redirección con un valor que
    viene de fuera pasa por aquí y no la escribe a mano.
    """
    return destino if destino.startswith("/") else RUTA_POR_OMISION


@dataclass(frozen=True, slots=True)
class UsuarioSesion:
    usuario_id: int
    usuario: str
    nombre: str
    rol: Rol
    empresa_id: int
    empresa_nombre: str
    es_soporte: bool

    @property
    def puede_escribir(self) -> bool:
        """Hiring manager y staff de Criba son de solo lectura (D6, contexto.md)."""
        return self.rol in ROLES_QUE_ESCRIBEN

    @property
    def iniciales(self) -> str:
        partes = [p for p in self.nombre.split() if p]
        return "".join(p[0] for p in partes[:2]).upper() or "?"


@dataclass(frozen=True, slots=True)
class ContextoEmpresa:
    """El `empresa_id` con el que se construye el repositorio. Nunca viene de la URL."""

    empresa_id: int
    es_soporte: bool


def escribir_cookie(respuesta: Response, sesion: UsuarioSesion) -> None:
    token = firmar_sesion(
        {
            "usuario_id": sesion.usuario_id,
            "usuario": sesion.usuario,
            "nombre": sesion.nombre,
            "rol": str(sesion.rol),
            "empresa_id": sesion.empresa_id,
            "empresa_nombre": sesion.empresa_nombre,
            "es_soporte": sesion.es_soporte,
        }
    )
    conf = ajustes()
    respuesta.set_cookie(
        conf.cookie_sesion,
        token,
        max_age=conf.horas_de_sesion * 3600,
        httponly=True,
        samesite="lax",
        path="/",
    )


def borrar_cookie(respuesta: Response) -> None:
    respuesta.delete_cookie(ajustes().cookie_sesion, path="/")


def sesion_opcional(request: Request) -> UsuarioSesion | None:
    token = request.cookies.get(ajustes().cookie_sesion)
    if not token:
        return None
    datos = leer_sesion(token)
    if not datos:
        return None
    try:
        return UsuarioSesion(
            usuario_id=int(datos["usuario_id"]),
            usuario=str(datos["usuario"]),
            nombre=str(datos["nombre"]),
            rol=Rol(datos["rol"]),
            empresa_id=int(datos["empresa_id"]),
            empresa_nombre=str(datos["empresa_nombre"]),
            es_soporte=bool(datos["es_soporte"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def sesion_requerida(
    request: Request,
    sesion: Annotated[UsuarioSesion | None, Depends(sesion_opcional)],
) -> UsuarioSesion:
    if sesion is None:
        raise NecesitaEntrar(destino=request.url.path)
    return sesion


def contexto_empresa(
    sesion: Annotated[UsuarioSesion, Depends(sesion_requerida)],
) -> ContextoEmpresa:
    return ContextoEmpresa(empresa_id=sesion.empresa_id, es_soporte=sesion.es_soporte)


def exigir_escritura(sesion: Annotated[UsuarioSesion, Depends(sesion_requerida)]) -> UsuarioSesion:
    if not sesion.puede_escribir:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Tu rol es de solo lectura.")
    return sesion


SesionActual = Annotated[UsuarioSesion, Depends(sesion_requerida)]
SesionQueEscribe = Annotated[UsuarioSesion, Depends(exigir_escritura)]
Contexto = Annotated[ContextoEmpresa, Depends(contexto_empresa)]
