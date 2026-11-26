"""PR-PERF-1 · cambio nº 3 de `perf/MEDICION.md` §6: la respuesta va comprimida.

Lo que la medición dice, citado: «`app/fabrica.py` no monta ningún middleware de
compresión, así que ese 1,52 MiB viaja tal cual» (§5.2). Para CA5 da casi igual
—el `loopback` no cobra—, pero es el único cambio de §6 que mueve la fila «Página
visible en celular, buena red: < 2 s» de la tabla de rendimiento de `SPEC.md`,
que es **objetivo y medición manual, no test automático**. Así que lo que estos
tests asercian es **la compresión**, no los dos segundos: el número del celular
no se puede comprobar desde aquí y nadie debería leer un verde de este archivo
como si se hubiera medido un teléfono.

Dos criterios, uno por test:

1. **comprimida cuando el navegador la acepta** (`Accept-Encoding: gzip`), y el
   cuerpo en el cable pesa menos que el HTML;
2. **sin comprimir cuando no la acepta** (`Accept-Encoding: identity`), con el
   **mismo HTML** en los dos casos.

El segundo test empieza aserciando el primero. No es redundancia: hoy, sin
middleware, «no comprime cuando el cliente no lo acepta» pasa solo y no ejerce
nada —es la misma trampa que `rutas_de_match` vacía—, así que la precondición es
parte del criterio.

La vista medida es `GET /vacantes/{id}`, que es la de §5.2. Aquí van doce
candidatos y no 500: lo que se comprueba es la negociación de contenido, y el
tamaño de la respuesta ya pasa de sobra el mínimo por debajo del cual un
middleware de compresión no se molesta.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.match.conftest import EmpresaDePrueba, sembrar_candidatos

CUANTOS = 12


def test_la_vista_de_vacante_va_comprimida_cuando_el_navegador_acepta_gzip(
    sesion: Session, northstar: EmpresaDePrueba, sesion_reclutador_northstar: TestClient
) -> None:
    """§6 nº 3 · `Accept-Encoding: gzip` → `Content-Encoding: gzip` y menos bytes."""
    sembrar_candidatos(sesion, northstar, CUANTOS)
    respuesta = sesion_reclutador_northstar.get(
        f"/vacantes/{northstar.vacante.id}", headers={"Accept-Encoding": "gzip"}
    )
    assert respuesta.status_code == 200
    assert respuesta.headers.get("content-encoding") == "gzip", (
        "la respuesta viaja sin comprimir: `app/fabrica.py` no monta compresión"
    )

    en_el_cable = respuesta.headers.get("content-length")
    assert en_el_cable is not None, "la respuesta comprimida no declara su largo"
    assert int(en_el_cable) < len(respuesta.content), (
        f"comprimida pesa {en_el_cable} y el HTML {len(respuesta.content)}: no comprime nada"
    )


def test_sin_accept_encoding_la_misma_vista_va_sin_comprimir_y_con_el_mismo_html(
    sesion: Session, northstar: EmpresaDePrueba, sesion_reclutador_northstar: TestClient
) -> None:
    """§6 nº 3, la otra mitad · `identity` → ningún `Content-Encoding`.

    Un cliente que no acepta gzip —un `curl` de soporte, un lector de pantalla
    antiguo, el `TestClient` de otro test— tiene que recibir exactamente el mismo
    HTML. Si cambiara, este arreglo de rendimiento sería un cambio de conducta.
    """
    sembrar_candidatos(sesion, northstar, CUANTOS)
    url = f"/vacantes/{northstar.vacante.id}"
    comprimida = sesion_reclutador_northstar.get(url, headers={"Accept-Encoding": "gzip"})
    assert comprimida.headers.get("content-encoding") == "gzip", (
        "sin compresión montada este test no ejerce nada (perf/MEDICION.md §6 nº 3)"
    )

    plana = sesion_reclutador_northstar.get(url, headers={"Accept-Encoding": "identity"})
    assert plana.status_code == 200
    assert plana.headers.get("content-encoding") is None, (
        "comprime aunque el cliente declare que no lo acepta"
    )
    assert plana.text == comprimida.text, "el HTML cambia según la codificación aceptada"
