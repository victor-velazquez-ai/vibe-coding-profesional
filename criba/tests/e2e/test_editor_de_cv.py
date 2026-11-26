"""PR-PERF-1 · el editor de CV por la interfaz real (cambio nº 1 de `perf/MEDICION.md` §6).

Un guion, con Chromium headless y el mismo andamio de PR-07 (`tests/e2e/conftest.py`):
servidor de verdad, base comprometida en `criba_test` y proveedor MOCK.

Qué añade al humo de PR-07: que **subir un CV sigue funcionando como hoy** cuando
el `<textarea>` ya no viene en la respuesta de la vacante. El guion 1 del humo
rellena `textarea[name='cv_texto']` después de abrir el `<details>`, así que
tiene que seguir en verde con el editor cargado por HTMX; este guion lo ejerce
aparte y asercia, además, las dos mitades de §6 nº 1 contra el navegador: el
texto del CV **no** viaja en la lista y **sí** en el pedido del editor.

Sin `sleep`: se espera por el selector y por el valor del campo, que es lo que
hace el resto del E2E (`CLAUDE.md`; `tests/e2e/conftest.py`, «un número inventado
es lo que convierte un E2E en inestable»).
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

from tests.e2e.conftest import CONTRASENA, Datos

# Sin ningún carácter que Jinja escape (`&`, `<`, `>`, comillas): si lo hubiera,
# la aserción «no está en la lista» pasaría por el escape y no por el arreglo.
CV_SUBIDO = (
    "Enfermera titulada sintetica. Licencia RN vigente en Texas. "
    "Seis anos en piso de medicina interna, turno nocturno."
)


def _entrar(page: Page, servidor: str, usuario: str) -> None:
    """Login por el formulario real, igual que el humo de PR-07."""
    page.goto(f"{servidor}/entrar")
    page.fill("#usuario", usuario)
    page.fill("#contrasena", CONTRASENA)
    page.click("button[type='submit']")
    page.wait_for_url(f"{servidor}/vacantes")


def test_la_lista_no_lleva_el_cv_y_el_editor_llega_al_abrir_el_details(
    page: Page, servidor: str, datos: Datos
) -> None:
    """§6 nº 1 · subir sigue funcionando, la lista no lleva el texto, el editor sí."""
    _entrar(page, servidor, datos.reclutadora)
    respuesta = page.goto(f"{servidor}/vacantes/{datos.vacante_id}")
    assert respuesta is not None and respuesta.status == 200

    # 1 · subir un CV por la UI, el camino del guion 1 del humo (alcance 7, CA9(a)).
    page.click("summary:has-text('CV')")
    page.fill("textarea[name='cv_texto']", CV_SUBIDO)
    page.click("button:has-text('Guardar CV')")
    page.wait_for_selector('[data-testid="fila-candidato"] .tone-success')

    # 2 · recargada, la lista dice el largo del CV y **no** lleva el texto.
    page.reload()
    contenido = page.content()
    assert f"{len(CV_SUBIDO)} caracteres" in contenido, "la subida no quedó guardada"
    assert CV_SUBIDO not in contenido, (
        "la vista sigue trayendo el texto del CV en la lista (perf/MEDICION.md §5.1)"
    )

    # 3 · el editor, pedido al abrir el `<details>`, sí lo trae.
    page.click("summary:has-text('CV')")
    editor = page.locator("textarea[name='cv_texto']")
    expect(editor).to_have_value(CV_SUBIDO)
