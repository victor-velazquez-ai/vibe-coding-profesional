"""PR-PERF-1 · cambio nº 1 de `perf/MEDICION.md` §6: la lista no lleva el texto del CV.

Lo que la medición dice, citado: `_candidatos.html` pinta
`{{ fila.candidato.cv_texto|length }}` —un número— pero la vista trae la columna
entera para precargar **un `<textarea>` por fila** dentro de un `<details>`
cerrado «que el reclutador casi nunca abre» (`perf/MEDICION.md` §5.1). Eso cuesta
10,5 ms de los 24,9 ms de la consulta grande (§5.1, medida 2 contra 3) y 542.091
de los 1.597.568 bytes del cuerpo (§5.2).

El arreglo que §6 nº 1 propone tiene dos mitades y las dos son criterios aquí:
la vista **no incluye el `cv_texto` de ningún candidato**, y el editor **se pide
aparte, cuando la reclutadora lo abre** —y ese pedido sí trae el texto—.

El pedido nuevo es un endpoint más de la plataforma, así que arrastra lo de
siempre:

- **CA1** (`SPEC.md`, D4, [03:03]): con sesión de otra empresa, 404 y ningún dato
  del candidato ajeno. En las **dos** direcciones: Meridian no ve lo de Northstar
  y Northstar no ve lo de Meridian;
- **CA18** (D10, §13): el hiring manager es de solo lectura
  (`app/plataforma/sesion.py::exigir_escritura`), así que no edita CVs: su lista
  no trae el editor y el endpoint le responde **403**;
- y subir un CV sigue funcionando como hoy (alcance 7, CA9(a)).

**Lo que ningún documento fija: la ruta del endpoint nuevo.** No está en
`SPEC.md`, ni en `PLAN.md`, ni en §6 de la medición. Así que estos tests **no la
escriben a mano**: la leen del `hx-get` de la fila, que es lo que la propia
medición describe («cargar el editor de CV por HTMX cuando se abre el
`<details>`»). Quien construya elige la ruta y su forma; lo que no puede elegir
es que el editor no se pida aparte.

Lo que este archivo **no** mide: milisegundos ni bytes. El presupuesto de CA5 ya
se cumple hoy (§4) y el número de §6 nº 1 es una estimación; lo que se asercia es
la conducta de la que ese número depende.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.plataforma.modelos import Candidato
from app.plataforma.repositorio import RepositorioEmpresa
from tests.match.conftest import EmpresaDePrueba, Entrar, sembrar_candidatos

CUANTOS = 12
CENTINELA = "CENTINELA-CV"
# Una línea reconocible del CV de fixture de Northstar (`cv_enfermeria_es.md`),
# sin ningún carácter que Jinja escape: si apareciera escapada, la aserción no
# muerde y pasaría en rojo.
DEL_CV_DE_FIXTURE = "manejo de vía central"
PATRON_HX_GET = re.compile(r"""hx-get\s*=\s*["']([^"']+)["']""")


def _sembrar_cvs(sesion: Session, empresa: EmpresaDePrueba) -> list[Candidato]:
    """`CUANTOS` candidatos postulados, cada uno con un CV reconocible.

    El texto se guarda por `RepositorioEmpresa.guardar_cv`, que es por donde pasa
    una subida de verdad. Todo sintético (D3 modificado, D15, F12).
    """
    repo = RepositorioEmpresa(sesion, empresa.empresa.id)
    candidatos = sembrar_candidatos(sesion, empresa, CUANTOS)
    for indice, candidato in enumerate(candidatos):
        repo.guardar_cv(candidato.id, f"{CENTINELA}-{indice} · " + "texto de relleno. " * 20)
    return candidatos


def _fila_de(html: str, candidato: Candidato) -> str:
    """El trozo de HTML de la fila de ese candidato, buscado por su correo."""
    trozos = [t for t in html.split('data-testid="fila-candidato"')[1:] if candidato.correo in t]
    assert len(trozos) == 1, f"el candidato {candidato.id} sale {len(trozos)} veces en la lista"
    return trozos[0]


def _url_del_editor(html: str, candidato: Candidato) -> str:
    """La ruta del editor de CV, **leída de la fila** y no escrita a mano.

    Ningún documento la fija (ver el docstring del módulo). Lo que sí está escrito
    es que el editor se **pide** cuando se abre el `<details>`: o sea, un `hx-get`
    en la fila del candidato y uno solo.
    """
    urls = PATRON_HX_GET.findall(_fila_de(html, candidato))
    assert len(urls) == 1, (
        f"la fila del candidato {candidato.id} declara {len(urls)} `hx-get`: "
        "el editor de CV no se pide aparte (perf/MEDICION.md §6 nº 1)"
    )
    return str(urls[0])


# --- 1 · la lista -----------------------------------------------------------


def test_abrir_la_vacante_no_trae_el_cv_texto_de_ningun_candidato(
    sesion: Session, northstar: EmpresaDePrueba, sesion_reclutador_northstar: TestClient
) -> None:
    """§6 nº 1, primera mitad · ni un `cv_texto` en la respuesta de la vista.

    Y la lista sigue siendo la de hoy: las trece filas completas (CA8, «ninguno
    queda oculto ni colapsado») y el largo del CV, que es lo que la plantilla
    pinta de verdad.
    """
    candidatos = _sembrar_cvs(sesion, northstar)
    respuesta = sesion_reclutador_northstar.get(f"/vacantes/{northstar.vacante.id}")
    assert respuesta.status_code == 200

    assert CENTINELA not in respuesta.text, "la vista sigue trayendo el texto del CV de la lista"
    assert DEL_CV_DE_FIXTURE not in respuesta.text, "el CV del candidato de fixture viaja entero"

    assert respuesta.text.count('data-testid="fila-candidato"') == len(candidatos) + 1
    assert f"{len(northstar.candidato.cv_texto or '')} caracteres" in respuesta.text, (
        "la lista dejó de decir el largo del CV, que es lo único que pinta de él"
    )


# --- 2 · el editor, aparte --------------------------------------------------


def test_el_editor_de_cv_se_pide_aparte_y_ese_pedido_si_trae_el_texto(
    sesion: Session, northstar: EmpresaDePrueba, entrar: Entrar
) -> None:
    """§6 nº 1, segunda mitad · el editor llega en su propio pedido, con el texto.

    Dos cosas en una, porque son la misma: que exista el pedido y que sea
    **perezoso**. Un `hx-trigger="load"` por fila cumpliría la letra del cambio
    —el texto sale de la consulta de la lista— y haría 500 peticiones al abrir la
    vacante, que es peor que el problema que §5.1 describe.
    """
    candidatos = _sembrar_cvs(sesion, northstar)
    elegido = candidatos[0]
    cliente = entrar(northstar.reclutador)

    lista = cliente.get(f"/vacantes/{northstar.vacante.id}")
    assert lista.status_code == 200
    fila = _fila_de(lista.text, elegido)
    assert "hx-trigger" not in fila or "load" not in fila, (
        "el editor se carga con la propia vista: el ahorro de §6 nº 1 desaparece"
    )

    editor = cliente.get(_url_del_editor(lista.text, elegido))
    assert editor.status_code == 200
    assert elegido.cv_texto is not None and elegido.cv_texto in editor.text, (
        "el pedido del editor no trae el texto del CV"
    )
    assert 'name="cv_texto"' in editor.text, "el editor llega sin el campo que se guarda"


# --- 3 · CA1, en las dos direcciones ---------------------------------------


def test_el_editor_de_cv_de_otra_empresa_responde_404_en_las_dos_direcciones(
    sesion: Session, northstar: EmpresaDePrueba, meridian: EmpresaDePrueba, entrar: Entrar
) -> None:
    """CA1 · 404, nunca un 200 parcial, y ningún dato del candidato ajeno.

    Las dos direcciones a propósito: «ningún dato cruza entre empresas» no es una
    propiedad de Northstar, es del endpoint.
    """
    _sembrar_cvs(sesion, northstar)
    de_northstar = entrar(northstar.reclutador)
    de_meridian = entrar(meridian.reclutador)

    url_northstar = _url_del_editor(
        de_northstar.get(f"/vacantes/{northstar.vacante.id}").text, northstar.candidato
    )
    url_meridian = _url_del_editor(
        de_meridian.get(f"/vacantes/{meridian.vacante.id}").text, meridian.candidato
    )

    ida = de_meridian.get(url_northstar)
    assert ida.status_code == 404, f"{url_northstar} con sesión de Meridian dio {ida.status_code}"
    assert northstar.candidato.correo not in ida.text
    assert DEL_CV_DE_FIXTURE not in ida.text

    vuelta = de_northstar.get(url_meridian)
    assert vuelta.status_code == 404, (
        f"{url_meridian} con sesión de Northstar dio {vuelta.status_code}"
    )
    assert meridian.candidato.correo not in vuelta.text


# --- 4 · CA18 --------------------------------------------------------------


def test_el_hiring_manager_no_recibe_el_editor_de_cv_ni_puede_pedirlo(
    sesion: Session, northstar: EmpresaDePrueba, entrar: Entrar
) -> None:
    """CA18, D10 · es de solo lectura: no edita CVs.

    Sigue abriendo la vacante con **200** y su lista completa —la vista nunca le
    da 403, R2·M1— y el endpoint del editor le responde **403**, que es lo que
    `exigir_escritura` responde hoy a un rol de solo lectura y lo que CA18 pide
    para los endpoints.
    """
    _sembrar_cvs(sesion, northstar)
    url_vacante = f"/vacantes/{northstar.vacante.id}"
    url_editor = _url_del_editor(
        entrar(northstar.reclutador).get(url_vacante).text, northstar.candidato
    )

    cliente = entrar(northstar.hiring_manager)
    vista = cliente.get(url_vacante)
    assert vista.status_code == 200
    assert northstar.candidato.correo in vista.text, (
        "el hiring manager perdió la lista que ya tenía"
    )
    assert 'name="cv_texto"' not in vista.text, "le llega un editor de CV"
    assert PATRON_HX_GET.findall(_fila_de(vista.text, northstar.candidato)) == [], (
        "la fila del hiring manager declara el pedido del editor"
    )

    respuesta = cliente.get(url_editor)
    assert respuesta.status_code == 403, f"el editor le dio {respuesta.status_code}"
    assert DEL_CV_DE_FIXTURE not in respuesta.text


# --- 5 · subir un CV sigue funcionando como hoy ----------------------------


def test_subir_un_cv_sigue_funcionando_y_el_fragmento_tampoco_trae_el_texto(
    sesion: Session, northstar: EmpresaDePrueba, sesion_reclutador_northstar: TestClient
) -> None:
    """Alcance 7, CA9(a) · el camino de escritura no cambia con este arreglo.

    El fragmento que devuelve la subida es **la misma lista**, así que el criterio
    de §6 nº 1 vale también ahí: el CV guardado se ve en el largo y se lee
    pidiendo el editor, no en el cuerpo de la lista.
    """
    _sembrar_cvs(sesion, northstar)
    nuevo = f"{CENTINELA}-nuevo · enfermera titulada sintetica, piso de medicina interna."
    cliente = sesion_reclutador_northstar

    respuesta = cliente.post(
        f"/candidatos/{northstar.candidato.id}/cv",
        data={"cv_texto": nuevo, "vacante_id": northstar.vacante.id},
    )
    assert respuesta.status_code == 200
    assert f"{len(nuevo)} caracteres" in respuesta.text, "la subida no quedó guardada"
    assert CENTINELA not in respuesta.text, (
        "el fragmento de la lista sigue trayendo el texto del CV"
    )

    editor = cliente.get(_url_del_editor(respuesta.text, northstar.candidato))
    assert editor.status_code == 200
    assert nuevo in editor.text, "el editor no trae el CV que se acaba de guardar"
