"""Staging · E2E de humo contra el staging **de verdad**.

Dos criterios, uno por test, los dos contra el servidor que `CRIBA_URL_STAGING`
apunta:

1. `marcus` —reclutador de Northstar, con la contraseña de la semilla— entra,
   abre **una vacante de Northstar de la semilla** y recibe **200 con la columna
   de score**. Que la columna esté es lo que distingue un staging con la
   configuración de producción de uno a medio encender: la pinta
   `_candidatos.html` solo si `listar_vacante` dice que sí, y para eso hacen
   falta el interruptor global **y** Northstar activada (R6·B1, D7, CA3);
2. **la misma vacante con `sofia`** —reclutadora de Meridian— da **404**, y en el
   cuerpo no va nada del candidato de Northstar (CA1, D4: el requisito número uno
   del cliente).

**Se salta sin `CRIBA_URL_STAGING`**: en CI no hay staging (`PLAN.md` §0 punto 3,
hecho 9 de PR-01, que deja la pregunta de qué datos tiene staging para Tomás el
1-dic). Saltarse no es aprobar: sin la variable estos dos criterios **no se
miden**, y la evidencia del trabajo es la corrida con la variable puesta.

**Sin navegador**: el humo de PR-07 ya recorre la interfaz con Playwright contra
un servidor del propio test. Lo que falta aquí es otra cosa —que el **staging
desplegado** responda lo que se espera—, y para eso HTTP con `httpx` basta: login
por `POST /entrar`, cookie firmada y dos GET.

**Qué datos usa, y por qué los lee de la semilla.** Usuarios, contraseñas y
títulos salen de `app/plataforma/semilla.py`, no escritos a mano: si la semilla
cambia de usuario o de vacante, estos tests la siguen. La contraseña es la regla
de la semilla —usuario + `1234`— y solo vale en un entorno sembrado con datos
**sintéticos**, que es la única forma en que la regla 1.7 de `PLAN.md` permite
encender Match en staging.
"""

from __future__ import annotations

import os
import re

import httpx
import pytest

from app.plataforma.modelos import Rol
from app.plataforma.semilla import MERIDIAN, NORTHSTAR, EmpresaSemilla

URL_STAGING = os.environ.get("CRIBA_URL_STAGING", "").strip().rstrip("/")

pytestmark = pytest.mark.skipif(
    not URL_STAGING, reason="sin CRIBA_URL_STAGING: en CI no hay staging que probar"
)

SEGUNDOS = 15.0


def _reclutador(empresa: EmpresaSemilla) -> str:
    """El usuario reclutador de una empresa de la semilla, elegido por su rol."""
    return next(usuario for usuario, _, rol in empresa.usuarios if rol is Rol.RECLUTADOR)


USUARIO_NORTHSTAR = _reclutador(NORTHSTAR)
USUARIO_MERIDIAN = _reclutador(MERIDIAN)
TITULO_DE_NORTHSTAR = NORTHSTAR.vacantes[0].titulo
# El candidato de la semilla que está postulado a esa vacante: su correo es lo que
# el 404 de Meridian no puede traer en el cuerpo.
CORREO_DE_NORTHSTAR = NORTHSTAR.candidatos[0].correo

# Los dos marcadores de la columna de score de `_candidatos.html`. El `th` es la
# cabecera y el `data-testid` es la celda: la cabecera sola se pinta aunque no
# haya ni una fila, y la semilla tiene filas.
CABECERA_DE_SCORE = '<th scope="col">Score</th>'
CELDA_DE_SCORE = 'data-testid="score"'

# `<a href="/vacantes/3">Enfermera/o …</a>` de `vacantes.html`.
PATRON_DE_VACANTE = re.compile(r'href="/vacantes/(\d+)">\s*([^<]+?)\s*</a>')


def _entrar(usuario: str) -> httpx.Client:
    """Login por el camino de producción: `POST /entrar` y cookie firmada.

    La contraseña es la regla de la semilla: usuario + `1234`.
    """
    cliente = httpx.Client(base_url=URL_STAGING, timeout=SEGUNDOS, follow_redirects=False)
    respuesta = cliente.post("/entrar", data={"usuario": usuario, "contrasena": f"{usuario}1234"})
    assert respuesta.status_code == 303, (
        f"{usuario} no pudo entrar en {URL_STAGING}: {respuesta.status_code}. "
        "¿Está sembrado el staging con los datos sintéticos de la semilla?"
    )
    return cliente


def _vacante_de_northstar(cliente: httpx.Client) -> int:
    """El id de la vacante de la semilla, leído de `GET /vacantes`.

    Por el título y no por un id escrito a mano: la semilla reinicia los
    contadores, pero un id fijo en un test es exactamente lo que envejece mal.
    """
    respuesta = cliente.get("/vacantes")
    assert respuesta.status_code == 200, f"GET /vacantes devolvió {respuesta.status_code}"
    por_titulo = {titulo: int(ident) for ident, titulo in PATRON_DE_VACANTE.findall(respuesta.text)}
    assert TITULO_DE_NORTHSTAR in por_titulo, (
        f"la vacante «{TITULO_DE_NORTHSTAR}» de la semilla no está en el staging: {por_titulo}"
    )
    return por_titulo[TITULO_DE_NORTHSTAR]


def test_marcus_abre_su_vacante_de_northstar_en_el_staging_con_la_columna_de_score() -> None:
    """Criterio 1 · 200 y columna de score en el staging desplegado."""
    with _entrar(USUARIO_NORTHSTAR) as cliente:
        vacante_id = _vacante_de_northstar(cliente)
        respuesta = cliente.get(f"/vacantes/{vacante_id}")

        assert respuesta.status_code == 200, (
            f"{USUARIO_NORTHSTAR} recibió {respuesta.status_code} en su propia vacante"
        )
        cuerpo = respuesta.text
        assert CABECERA_DE_SCORE in cuerpo, (
            "la vacante abre sin la columna de score: en el staging falta el interruptor "
            "global de Match o la activación de Northstar (R6·B1, D7)"
        )
        assert CELDA_DE_SCORE in cuerpo, "la columna de score está sin ninguna celda"


def test_la_misma_vacante_de_northstar_con_sofia_de_meridian_responde_404() -> None:
    """Criterio 2 · multiempresa, con los mismos ids y en el staging de verdad."""
    with _entrar(USUARIO_NORTHSTAR) as de_northstar:
        vacante_id = _vacante_de_northstar(de_northstar)

    with _entrar(USUARIO_MERIDIAN) as de_meridian:
        respuesta = de_meridian.get(f"/vacantes/{vacante_id}")

        assert respuesta.status_code == 404, (
            f"{USUARIO_MERIDIAN} recibió {respuesta.status_code} en la vacante de Northstar"
        )
        cuerpo = respuesta.text
        assert TITULO_DE_NORTHSTAR not in cuerpo, "el 404 trae el título de la vacante ajena"
        assert CORREO_DE_NORTHSTAR not in cuerpo, "el 404 trae el correo de un candidato ajeno"
        assert CELDA_DE_SCORE not in cuerpo
