"""PR-07 · E2E de humo: los cuatro guiones de la Etapa 0.

Un solo test que recorre de punta a punta **lo que existe**, para que cualquier
rotura posterior se vea en un sitio y no en veinte (`PLAN.md` PR-07). Con
Chromium headless, servidor levantado por el propio test y el proveedor MOCK:

1. **el circuito**: la reclutadora de Northstar entra, sube un CV por la UI —el
   gancho de PR-06 encola—, una pasada del bucle lo puntúa con el MOCK y el
   candidato aparece **con su score** en `GET /vacantes/{vacante_id}` (la columna
   la pinta PR-05, R6·I1);
2. **aislamiento**: la misma URL con sesión de Meridian → **404**, y nada del
   candidato de Northstar en la respuesta (CA1);
3. **rol**: el hiring manager abre la vacante → **200 sin score, sin razones, sin
   orden por score y sin sección de pendientes**; y pide
   `GET /match/vacantes/{vacante_id}/lista` → **403** (CA18, R2·M1, R6·I4);
4. **interruptor**: con `CRIBA_MATCH_ACTIVO` apagada, la reclutadora **sigue
   abriendo la vacante** —200 con la lista por fecha, sin score y sin error— y el
   endpoint de Match no existe (R6·B1).

**El orden importa y es el del archivo.** El guion 1 deja un score real en la
base, así que los guiones 3 y 4 no asercian sobre la ausencia de datos: asercian
que, **existiendo** el score, el hiring manager no lo ve y con Match apagado no
se pinta. Si se reordenaran, los dos últimos pasarían sin ejercer nada.
"""

from __future__ import annotations

from playwright.sync_api import Page

from app.match.proveedor.mock import SCORE_DEL_MOCK
from tests.e2e.conftest import CONTRASENA, Datos, correr_el_ejecutor

CV_SUBIDO = (
    "Enfermera titulada sintética. Licencia RN vigente en Texas. "
    "Seis años en piso de medicina interna, turno nocturno."
)


def _entrar(page: Page, servidor: str, usuario: str) -> None:
    """Login por el formulario real: `POST /entrar` y cookie firmada."""
    page.goto(f"{servidor}/entrar")
    page.fill("#usuario", usuario)
    page.fill("#contrasena", CONTRASENA)
    page.click("button[type='submit']")
    page.wait_for_url(f"{servidor}/vacantes")


def _abrir_la_vacante(page: Page, servidor: str, vacante_id: int) -> int:
    """La ruta por la que una reclutadora llega hoy a la vacante (hecho 4 de PR-01)."""
    respuesta = page.goto(f"{servidor}/vacantes/{vacante_id}")
    assert respuesta is not None, "el navegador no recibió respuesta"
    return respuesta.status


def test_guion_1_un_cv_subido_se_puntua_con_el_mock_y_la_reclutadora_ve_el_score(
    page: Page, servidor: str, datos: Datos, motor_test: object
) -> None:
    """Alcance 7, CA9(a), CA4 · el circuito entero, por la interfaz real."""
    _entrar(page, servidor, datos.reclutadora)
    assert _abrir_la_vacante(page, servidor, datos.vacante_id) == 200
    assert datos.nombre_candidato in page.content()
    # El candidato está sin CV, así que la columna de score está en «—»: la
    # vacante se abre **sin esperar a nadie** (CA4, D16).
    assert page.locator('[data-testid="score"]').inner_text().strip() == "—"

    # Sube el CV por la UI (HTMX). Aquí se dispara el gancho de PR-06.
    page.click("summary:has-text('CV')")
    page.fill("textarea[name='cv_texto']", CV_SUBIDO)
    page.click("button:has-text('Guardar CV')")
    page.wait_for_selector('[data-testid="fila-candidato"] .tone-success')

    # Una pasada del bucle, con el MOCK. En producción la invoca el proceso web
    # (ADR-001); aquí la invoca el test, que es lo que PR-06 dejó disponible.
    assert correr_el_ejecutor(motor_test) == 1, "la subida de CV no encoló ningún trabajo"

    page.reload()
    assert page.locator('[data-testid="score"]').inner_text().strip() == str(SCORE_DEL_MOCK)


def test_guion_2_la_misma_vacante_con_sesion_de_meridian_responde_404(
    page: Page, servidor: str, datos: Datos
) -> None:
    """CA1 · 404 con los mismos IDs, y **nunca un 200 parcial**."""
    _entrar(page, servidor, datos.reclutadora_meridian)
    assert _abrir_la_vacante(page, servidor, datos.vacante_id) == 404

    contenido = page.content()
    assert datos.nombre_candidato not in contenido
    assert datos.correo_candidato not in contenido
    assert str(SCORE_DEL_MOCK) not in contenido


def test_guion_3_el_hiring_manager_abre_la_vacante_sin_match_y_recibe_403_en_match(
    page: Page, servidor: str, datos: Datos
) -> None:
    """CA18, R2·M1, R6·I4 · el 403 es del endpoint de Match, no de la vacante.

    El score del guion 1 **existe** en la base cuando este guion corre: lo que se
    asercia es que el hiring manager no lo ve, no que no haya nada que ver.
    """
    _entrar(page, servidor, datos.hiring_manager)
    assert _abrir_la_vacante(page, servidor, datos.vacante_id) == 200

    contenido = page.content()
    assert datos.nombre_candidato in contenido, "el hiring manager perdió la lista que ya tenía"
    assert page.locator('[data-testid="score"]').count() == 0
    assert str(SCORE_DEL_MOCK) not in contenido
    assert "Score" not in page.locator("thead").inner_text()
    assert "orden=score" not in contenido, "hay un control de orden por score"
    assert page.locator('[data-testid="pendientes"]').count() == 0

    respuesta = page.goto(f"{servidor}/match/vacantes/{datos.vacante_id}/lista")
    assert respuesta is not None and respuesta.status == 403


def test_guion_4_con_el_interruptor_apagado_la_vacante_sigue_abriendo_sin_score(
    page: Page, servidor_apagado: str, datos: Datos
) -> None:
    """R6·B1 · el interruptor apaga Match, **no** la plataforma.

    Es el guion que convierte en E2E lo que la regla 1.7 promete: el 5-dic, con
    `CRIBA_MATCH_ACTIVO` apagada en producción, la vista de vacante de las 40
    empresas responde lo mismo que respondía antes de que Match existiera.
    """
    _entrar(page, servidor_apagado, datos.reclutadora)
    assert _abrir_la_vacante(page, servidor_apagado, datos.vacante_id) == 200

    contenido = page.content()
    assert datos.nombre_candidato in contenido, "la lista de hoy desapareció"
    assert page.locator('[data-testid="score"]').count() == 0
    assert str(SCORE_DEL_MOCK) not in contenido
    assert "Por fecha de postulación" in contenido

    respuesta = page.goto(f"{servidor_apagado}/match/vacantes/{datos.vacante_id}/lista")
    assert respuesta is not None and respuesta.status == 404, "`/match` sigue montado"
