"""Factoría de la aplicación de Criba.

Es el único sitio donde la plataforma monta Match, y lo hace por la **fachada**:
`fachada.montar(app)`. No importa `app.match.routers` ni ningún otro interno
(PLAN.md §2, R3·I1), así que la regla (b) del test de enumeración de PR-04 no
necesita hacerle una excepción.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as ErrorHTTP

from app.match import fachada
from app.plantillas import plantillas
from app.plataforma.rutas import autenticacion, candidatos, vacantes
from app.plataforma.sesion import NecesitaEntrar

ESTATICOS = Path(__file__).resolve().parent / "static"

TITULOS_DE_ERROR = {
    status.HTTP_403_FORBIDDEN: "No tienes acceso a esto",
    status.HTTP_404_NOT_FOUND: "Aquí no hay nada",
}


def crear_app() -> FastAPI:
    app = FastAPI(title="Criba", docs_url=None, redoc_url=None, openapi_url=None)

    app.mount("/static", StaticFiles(directory=str(ESTATICOS)), name="static")

    app.include_router(autenticacion.router)
    app.include_router(vacantes.router)
    app.include_router(candidatos.router)

    fachada.montar(app)

    @app.exception_handler(NecesitaEntrar)
    async def _sin_sesion(request: Request, exc: NecesitaEntrar) -> Response:
        return RedirectResponse(
            f"/entrar?destino={exc.destino}", status_code=status.HTTP_303_SEE_OTHER
        )

    @app.exception_handler(ErrorHTTP)
    async def _error_http(request: Request, exc: ErrorHTTP) -> Response:
        if exc.status_code not in TITULOS_DE_ERROR:
            return await http_exception_handler(request, exc)
        return plantillas.TemplateResponse(
            request,
            "error.html",
            {
                "codigo": exc.status_code,
                "titulo": TITULOS_DE_ERROR[exc.status_code],
                "detalle": exc.detail if isinstance(exc.detail, str) else "",
            },
            status_code=exc.status_code,
        )

    @app.get("/salud", include_in_schema=False, response_class=HTMLResponse)
    def _salud() -> str:
        return "ok"

    return app
