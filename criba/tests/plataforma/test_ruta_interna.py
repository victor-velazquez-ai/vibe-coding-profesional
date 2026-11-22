"""`ruta_interna` es la única puerta del issue #16, y hasta aquí nadie la probaba.

Hallazgo **M1** de la ronda 1 de revisión de PR-QA-E2E. El E2E
(`tests/e2e/test_qa_redireccion_abierta.py`) ejercita el agujero tal como lo
reprodujo el triage —`//example.com` y `/\\example.com` por `GET /entrar?destino=…`—
y eso cubre el **camino**: que la redirección del login pasa por esta función. Lo
que no cubre son las otras dos mitades de la regla, que viven solo dentro de
`app/plataforma/sesion.py`:

- `.translate(SIN_SALTOS)`: el navegador borra tabulador, CR y LF de una URL
  antes de resolverla (WHATWG URL, «URL parsing»), así que sin esa línea
  `/<TAB>/example.com` pasa el filtro y el navegador ve `//example.com`;
- la guarda `candidato.startswith("//")`: `urlsplit("///example.com")` no deja
  `netloc`, así que sin ella `///example.com` sale entero y el navegador lo
  normaliza igual a `//example.com`.

Las dos se pueden borrar hoy con la suite en verde. Este archivo es un test de
unidad y no un E2E a propósito: lo que falta no es otro navegador, es cubrir las
entradas de **la función** —y un guion de Playwright por variante costaría
segundos para probar lo mismo (`CLAUDE.md` §E2E: un E2E se espera a una
condición, pero el que no hace falta no se escribe).

Fuentes: `qa/TRIAGE.md` §«lo que encontró el triage y no la QA» (issue #16),
`SPEC.md` CA1 (ningún dato cruza entre empresas), `docs/prs/PR-QA-E2E.md`
(«Riesgo que introduce `ruta_interna`: es la única puerta de la regla»).
"""

from __future__ import annotations

import pytest

from app.plataforma.sesion import RUTA_POR_OMISION, ruta_interna

# Cada uno es un `destino` que, si se devolviera tal cual, llevaría al navegador
# a otro sitio después de un login legítimo de Criba.
FUERA_DE_CRIBA = [
    pytest.param("//example.com", id="doble_barra"),
    pytest.param("/\\example.com", id="barra_invertida"),
    pytest.param("/\t/example.com", id="tabulador"),
    pytest.param("/\r\n/example.com", id="cr_y_lf"),
    # El que necesita **las dos** mitades de la regla: el tabulador no deja ver la
    # doble barra, y la doble barra no deja ver el tabulador. Sin
    # `.translate(SIN_SALTOS)` esta cadena sale entera —`urlsplit` sí borra el
    # tabulador para decidir, pero lo que se devuelve es la cadena de entrada, y
    # `"/\t//example.com".startswith("//")` es falso—; sin la guarda de `//`
    # tampoco se descarta. Es el único parámetro que distingue la línea 60.
    pytest.param("/\t//example.com", id="tabulador_y_doble_barra"),
    pytest.param("///example.com", id="triple_barra"),
    pytest.param("/\\\\example.com", id="dos_barras_invertidas"),
    pytest.param("http://example.com/vacantes", id="esquema_http"),
    pytest.param("https://example.com", id="esquema_https"),
    pytest.param("javascript:alert(1)", id="javascript"),
    # Y los dos que no son un destino de nada: una ruta relativa se resolvería
    # contra la ruta actual, y la cadena vacía es lo que llega cuando el campo
    # oculto del formulario viene sin valor.
    pytest.param("vacantes", id="ruta_relativa"),
    pytest.param("", id="cadena_vacia"),
]

INTERNAS = [
    pytest.param("/vacantes/3", id="vacante_propia"),
    pytest.param("/vacantes?orden=fecha", id="con_parametros"),
    # Multiempresa (CA1): el `destino` de una vacante de **otra** empresa se
    # respeta como ruta y muere en el 404 de siempre. Aquí no hay lista blanca de
    # ids, y convertirlo en `/vacantes` escondería el aislamiento detrás de una
    # regla de redirección —que es justo donde nadie lo iría a buscar—.
    pytest.param("/vacantes/9999", id="vacante_de_otra_empresa"),
]


@pytest.mark.parametrize("destino", FUERA_DE_CRIBA)
def test_ruta_interna_descarta_todo_destino_que_saque_al_navegador_de_criba(destino: str) -> None:
    """Issue #16 · solo manda una ruta de Criba; cualquier otra cosa cae en la de omisión."""
    assert ruta_interna(destino) == RUTA_POR_OMISION, (
        f"redirección abierta (issue #16): ruta_interna({destino!r}) devolvió "
        f"{ruta_interna(destino)!r} en vez de {RUTA_POR_OMISION!r}. El navegador normaliza ese "
        "valor a otro dominio: una URL de Criba no puede decidir a qué sitio va alguien "
        "después de entrar."
    )


@pytest.mark.parametrize("destino", INTERNAS)
def test_ruta_interna_respeta_una_ruta_de_criba_aunque_sea_de_otra_empresa(destino: str) -> None:
    """La otra mitad del arreglo: «ignorar `destino` siempre» no es la regla.

    Sin esta aserción, la forma perezosa de poner el test de arriba en verde
    —devolver siempre `/vacantes`— pasaría, y con ella se rompería lo que la QA
    comprobó que **no** era un bug (BUG-5: un `destino` interno se respeta).
    """
    assert ruta_interna(destino) == destino, (
        f"ruta_interna({destino!r}) devolvió {ruta_interna(destino)!r}: un destino interno de "
        "Criba se respeta tal cual, también el de otra empresa (CA1, BUG-5)"
    )
