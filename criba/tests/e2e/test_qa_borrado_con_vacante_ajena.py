"""E2E de **BUG-2 de la QA de backend** (`qa/reportes/2026-11-22-backend.md`).

Hallazgo: `POST /candidatos/{candidato_id}/borrar` con un `vacante_id` que no
corresponde a ninguna postulación del candidato **ejecuta el borrado igual** y
responde `404 «Aquí no hay nada»`. El reclutador lee un error y lo que ocurrió es
que perdió al candidato, su CV y su postulación. `qa/TRIAGE.md` lo decide **«se
arregla ahora»**, y por `CLAUDE.md` el arreglo entra primero como E2E en rojo.

**Lo que se asercia, y de dónde sale.** La QA dejó dos salidas abiertas («404 sin
borrar nada» o «borrar y responder 303») y el triage eligió la primera: *no se
borra nada y la respuesta es 404*. Esa es la que se asercia aquí, en ese orden de
importancia: primero que el candidato **sigue en su vacante**, después el 404.

**Tres formas de que el `vacante_id` sea ajeno**, y el test las recorre como
parámetros porque las tres llegan por el mismo formulario y hoy fallan de dos
maneras distintas:

1. `inexistente` — el `vacante_id=999` de la reproducción de la QA;
2. `otra_vacante_de_la_empresa` — una vacante real de Northstar a la que **este**
   candidato no está postulado. Es la que la QA no probó en `/borrar` (sí en
   `/cv`, BUG-6) y hoy ni siquiera da 404: devuelve 200 con el fragmento de la
   otra vacante, después de haber borrado;
3. `vacante_de_meridian` — el `vacante_id` de otra empresa, que es el segundo caso
   de la reproducción (candidato 13 con la vacante 1 de Northstar). Es también la
   mitad multiempresa del hallazgo: el dato de la otra empresa no puede ni
   consultarse ni servir de palanca para borrar (CA1).

**Sin CV y sin score, a propósito.** Un candidato con score hoy da 500 por BUG-1,
que es otro hallazgo y va a PR-18 (`qa/TRIAGE.md`). Este guion usa candidatos
recién creados y sin CV para que el rojo sea el de BUG-2 y no el de BUG-1.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import count

import pytest
from playwright.sync_api import Page
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.plataforma.modelos import Candidato, Postulacion, Vacante
from tests.e2e.ayudas import abrir, empresa_por_slug, entrar, filas_con
from tests.e2e.conftest import SLUG_MERIDIAN, SLUG_NORTHSTAR, Datos

# Un id que ninguna migración ni ninguna fixture puede haber creado: es el
# `vacante_id=999` de la reproducción de la QA, con margen.
VACANTE_INEXISTENTE = 999_999
TITULO_DE_LA_OTRA = "Analista de TI · soporte de red (sintética)"
TITULO_DE_MERIDIAN = "Coordinador/a de flota (sintética)"

_SECUENCIA = count(1)


@dataclass(frozen=True, slots=True)
class CandidatoSintetico:
    id: int
    nombre: str


@pytest.fixture(scope="module")
def vacantes_ajenas(motor_test: Engine, datos: Datos) -> dict[str, int]:
    """Las tres formas de que el `vacante_id` del formulario sea ajeno."""
    with Session(motor_test, expire_on_commit=False) as sesion:
        northstar = empresa_por_slug(sesion, SLUG_NORTHSTAR)
        meridian = empresa_por_slug(sesion, SLUG_MERIDIAN)
        otra = Vacante(
            empresa_id=northstar.id,
            titulo=TITULO_DE_LA_OTRA,
            descripcion="Soporte de red en sitio. Datos sintéticos.",
            ciudad="Austin, TX",
        )
        de_meridian = Vacante(
            empresa_id=meridian.id,
            titulo=TITULO_DE_MERIDIAN,
            descripcion="Patio de carga. Datos sintéticos.",
            ciudad="El Paso, TX",
        )
        sesion.add_all([otra, de_meridian])
        sesion.commit()
        return {
            "inexistente": VACANTE_INEXISTENTE,
            "otra_vacante_de_la_empresa": otra.id,
            "vacante_de_meridian": de_meridian.id,
        }


@pytest.fixture
def candidato_de_northstar(motor_test: Engine, datos: Datos) -> CandidatoSintetico:
    """Un candidato propio, **nuevo para cada caso**, sin CV y sin score.

    Nuevo para cada caso porque el defecto borra de verdad: si los tres casos
    compartieran candidato, el segundo y el tercero responderían 404 por una razón
    distinta —el candidato ya no existe— y pasarían sin ejercer nada.
    """
    numero = next(_SECUENCIA)
    with Session(motor_test, expire_on_commit=False) as sesion:
        northstar = empresa_por_slug(sesion, SLUG_NORTHSTAR)
        candidato = Candidato(
            empresa_id=northstar.id,
            nombre=f"Candidato sintético {numero} del borrado",
            correo=f"borrado.{numero}@northstar-e2e.test",
            telefono=f"+1 713 555 02{numero:02d}",
            links=[],
        )
        sesion.add(candidato)
        sesion.flush()
        sesion.add(
            Postulacion(
                empresa_id=northstar.id,
                candidato_id=candidato.id,
                vacante_id=datos.vacante_id,
            )
        )
        sesion.commit()
        return CandidatoSintetico(id=candidato.id, nombre=candidato.nombre)


@pytest.mark.parametrize(
    "caso", ["inexistente", "otra_vacante_de_la_empresa", "vacante_de_meridian"]
)
def test_borrar_con_un_vacante_id_ajeno_no_borra_nada_y_responde_404(
    page: Page,
    servidor: str,
    datos: Datos,
    vacantes_ajenas: dict[str, int],
    candidato_de_northstar: CandidatoSintetico,
    caso: str,
) -> None:
    """QA backend BUG-2 · la acción destructiva no se ejecuta con un `vacante_id` ajeno."""
    vacante_ajena = vacantes_ajenas[caso]

    # Multiempresa, la otra dirección (CA1): la reclutadora de Meridian no borra
    # un candidato de Northstar ni con el `vacante_id` correcto. Hoy pasa; es lo
    # que el arreglo no puede romper al empezar a validar el `vacante_id`.
    entrar(page, servidor, datos.reclutadora_meridian)
    desde_meridian = page.request.post(
        f"{servidor}/candidatos/{candidato_de_northstar.id}/borrar",
        form={"vacante_id": str(datos.vacante_id)},
    )
    assert desde_meridian.status == 404, (
        "Meridian recibió algo distinto de un 404 al borrar un candidato de Northstar: "
        f"{desde_meridian.status}"
    )

    entrar(page, servidor, datos.reclutadora)
    assert abrir(page, servidor, f"/vacantes/{datos.vacante_id}") == 200
    assert filas_con(page, candidato_de_northstar.nombre) == 1, (
        "el candidato de Northstar desapareció con una sesión de Meridian: es un incidente "
        "de aislamiento, no un bug de formulario (CA1)"
    )

    # El hallazgo: su propia reclutadora, su propio candidato, un `vacante_id` que
    # no es de ninguna postulación suya.
    respuesta = page.request.post(
        f"{servidor}/candidatos/{candidato_de_northstar.id}/borrar",
        form={"vacante_id": str(vacante_ajena)},
    )

    # Primero lo que importa: no se borró nada.
    assert abrir(page, servidor, f"/vacantes/{datos.vacante_id}") == 200
    assert filas_con(page, candidato_de_northstar.nombre) == 1, (
        f"QA backend BUG-2: el borrado se ejecutó con un vacante_id ajeno ({caso}, "
        f"vacante_id={vacante_ajena}) y el candidato ya no está en su vacante. La respuesta "
        f"fue {respuesta.status}: el servidor ejecutó la acción destructiva y le dijo al "
        "reclutador que aquí no hay nada."
    )

    # Y después, la respuesta que el triage eligió de las dos que la QA aceptaba.
    assert respuesta.status == 404, (
        f"con un vacante_id ajeno ({caso}, vacante_id={vacante_ajena}) la ruta tiene que "
        f"responder 404 sin efecto; respondió {respuesta.status}"
    )

    # Y la vacante ajena no se cuela en la respuesta de una empresa que no es suya.
    if caso == "vacante_de_meridian":
        assert TITULO_DE_MERIDIAN not in respuesta.text()
