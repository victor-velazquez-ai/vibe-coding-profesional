"""PR-10 · CA3 · la activación por empresa, en los dos caminos.

Sin empresa activada y con anexo de subprocesador firmado **no se emite ninguna
llamada al proveedor y no se crea ningún registro de Match** (`SPEC.md` CA3, D7 de
`llamadas/2026-11-21-cambios-decisiones.md` §1(c) y §8). Los dos caminos son los
que `docs/arquitectura.md` §5.3 separa:

- **el de la request**, con cookie de empresa: los dos ganchos de PR-06 (subida de
  CV y creación de postulación) llaman a `encolar`, y la comprobación vive
  **dentro de `encolar`**, antes del `INSERT` —CA3 prohíbe «ningún registro», no
  solo «ninguna llamada» (PLAN.md PR-10, R2·M2)—;
- **el sin cookie**: el ejecutor toma una fila de la cola y el `empresa_id` sale
  de la fila, no de la sesión. `docs/arquitectura.md` §5.3 es el escenario
  literal: «el trabajo de recálculo por CV nuevo toma la empresa del candidato y
  nadie revalida la activación; entra un CV de Meridian y se emite una llamada al
  proveedor por una empresa sin anexo firmado» (F5, severidad 5 x probabilidad
  3 = 15).

Son **dos momentos del mismo camino y una sola regla**: la misma función del
punto único de acceso a datos, llamada dos veces (PLAN.md PR-10, criterio de
terminado; `docs/arquitectura.md` §5.3: «la comprobación de D7 debe vivir en el
mismo punto de acceso a datos, no en el router»). Eso es lo que asercia el último
test de este archivo.

**Lo que la activación apagada NO apaga:** la plataforma. Meridian es cliente de
Criba hoy, y D7 dice «Match apagado para Meridian», no «Meridian roto»: subir un
CV y postular siguen respondiendo 200 y guardando lo suyo, y la vista de vacante
se renderiza «sin score ni orden por score» y **sin error**
(`docs/arquitectura.md` §3, párrafo final; R6·B1: «la vista de vacante responde
200 con interruptor apagado, siempre»). Un `encolar` que levante una excepción
convierte CA3 en un 500 en la ruta de subida de CV de las 39 empresas sin Match.

El material es sintético (D3 modificado, D15, F12) y el proveedor es el **doble**,
que no sale de la red: nada de este paso necesita el cliente real (PLAN.md PR-10,
dependencias; la regla 1.5 pone este paso **antes** de PR-09).
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.match import configuracion as configuracion_de_match
from app.match.cola.ejecutor import una_pasada
from app.match.cola.trabajos import encolar
from app.match.configuracion import VARIABLE_DE_EMPRESAS, AjustesDeMatch, ajustes_match
from app.plataforma.repositorio import RepositorioEmpresa
from tests.dobles.proveedor import ProveedorContado, proveedor_que_prohibe_llamadas
from tests.match.conftest import (
    EmpresaDePrueba,
    Entrar,
    repo_de,
    rutas_de_match,
    sembrar_candidatos,
    sembrar_score,
)

RAIZ = Path(__file__).resolve().parents[2]
APP = RAIZ / "app"
# Dónde puede leerse el estado de activación por empresa: donde se **declara**
# (configuración de Match, R4·I1) y donde se **decide** (el punto único de acceso
# a datos, `docs/arquitectura.md` §4 y §5.3). En ningún otro sitio.
DONDE_SE_LEE_LA_ACTIVACION = (
    APP / "match" / "configuracion.py",
    APP / "match" / "repositories",
)

CV_NUEVO = "CV sintético nuevo: licencia RN vigente en Texas, turno nocturno."
PUNTOS = 88


@pytest.fixture
def activacion(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., None]]:
    """Fija **exactamente** qué empresas están activadas, y permite retirar una.

    La fixture `activar_match` de PR-03 solo enciende, y estos tests necesitan las
    dos cosas: el **valor por omisión** (sin argumentos: la variable de entorno no
    existe, «ninguna empresa activada», R4·I1) y el caso de la empresa que estuvo
    activada el tiempo justo para dejar una fila en la cola.
    """

    def fijar(*slugs: str) -> None:
        if slugs:
            monkeypatch.setenv(VARIABLE_DE_EMPRESAS, ",".join(sorted(slugs)))
        else:
            monkeypatch.delenv(VARIABLE_DE_EMPRESAS, raising=False)
        ajustes_match.cache_clear()

    yield fijar
    ajustes_match.cache_clear()


# --- 1 · CA3 · el camino de la request ------------------------------------


def test_un_cv_de_meridian_por_la_ruta_de_la_plataforma_no_llama_ni_deja_fila(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    entrar: Entrar,
    proveedor_contado: ProveedorContado,
) -> None:
    """CA3, D7 · «llega un CV nuevo suyo» → cero llamadas **y cero filas**.

    Las dos mitades juntas, y la de las filas es la que R2·I2 añadió: si el gancho
    encola y la comprobación llegara solo al tomar el trabajo, «cero llamadas»
    pasaría y «ningún registro» fallaría, dejando una fila con un `candidato_id`
    de Meridian en una tabla de Match hasta que alguien la limpie.

    Las **dos puertas** de PR-06 en el mismo test, porque las dos llaman a la
    misma función (`encolar`) y la comprobación es una: la subida de CV (CA9(a),
    alcance 7) y la postulación sin CV nuevo (R4·B1).
    """
    cliente = entrar(meridian.reclutador)
    otro = sembrar_candidatos(sesion, meridian, 1, postular=False)[0]

    subida = cliente.post(
        f"/candidatos/{meridian.candidato.id}/cv",
        data={"cv_texto": CV_NUEVO, "vacante_id": meridian.vacante.id},
    )
    postulacion = cliente.post(
        f"/vacantes/{meridian.vacante.id}/postulaciones", data={"candidato_id": otro.id}
    )

    # La plataforma de Meridian sigue funcionando: D7 apaga Match, no la empresa.
    assert (subida.status_code, postulacion.status_code) == (200, 200)
    plataforma = RepositorioEmpresa(sesion, meridian.empresa.id)
    guardado = plataforma.candidato(meridian.candidato.id)
    assert guardado is not None and guardado.cv_texto == CV_NUEVO, "el CV no se guardó"
    assert [p.candidato_id for p in plataforma.postulaciones_abiertas(otro.id)] == [otro.id]

    # Y Match no se enteró: ni fila, ni llamada. «Cero filas» **por empresa**
    # (R6·I3): en global pasaría aunque la fila se escribiera con otro empresa_id.
    for empresa in (meridian, northstar):
        repo = repo_de(sesion, empresa)
        assert repo.trabajos() == [], f"{empresa.slug} dejó una fila en match_trabajos"
        assert repo.scores() == [], f"{empresa.slug} dejó una fila en match_scores"
    assert proveedor_contado.llamadas == 0


# --- 2 · F5 · el camino sin cookie, antes del INSERT ------------------------


def test_encolar_un_trabajo_de_meridian_sin_pasar_por_la_request_no_deja_ninguna_fila(
    sesion: Session, northstar: EmpresaDePrueba, meridian: EmpresaDePrueba
) -> None:
    """F5 · el mismo caso **sin cookie**: la regla no vive en el router.

    `encolar` es lo que llaman los dos ganchos de PR-06 y lo que llamará el comando
    de la carga (PR-16), que no tiene sesión. Si la comprobación viviera en la
    ruta, este camino la saltaría entera.

    No devuelve fila, como ya hace con el interruptor global apagado
    (`app/match/cola/trabajos.py::encolar`, «`None` si Match está apagado»): una
    excepción aquí es un 500 en la ruta de subida de CV de Meridian (test 1).
    """
    assert ajustes_match().activo, "el interruptor global está apagado: este test sería vacío"
    assert not ajustes_match().match_activado(meridian.slug), "la fixture activó Meridian"

    assert encolar(sesion, meridian.vacante.id, meridian.candidato.id) is None
    for empresa in (meridian, northstar):
        assert repo_de(sesion, empresa).trabajos() == [], f"{empresa.slug} encoló sin anexo"


# --- 3 · F5 · el segundo momento: al tomar el trabajo -----------------------


async def test_al_tomar_un_trabajo_de_una_empresa_sin_anexo_no_se_llama_al_proveedor(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    activacion: Callable[..., None],
) -> None:
    """F5, `docs/arquitectura.md` §5.3 · la revalidación al tomar la fila.

    El escenario es el de §5.3 y no es hipotético: la fila ya existe en la cola
    —porque la empresa estuvo activada, porque el anexo se retiró, porque la carga
    la encoló— y en el ejecutor **no hay cookie**. Sin la segunda comprobación, la
    llamada al proveedor sale por una empresa sin anexo firmado, que es
    exactamente lo que CA3 prohíbe.

    El doble **prohíbe** toda llamada (CA3), pero el `assert` de abajo es el
    control de verdad: `una_pasada` captura por trabajo (`cola/ejecutor.py`), así
    que un `LlamadaProhibida` se convertiría en un trabajo en `error` y el test
    pasaría sin que nadie hubiera comprobado nada.

    El contraste —que el bucle **sí** puntúa cuando la empresa está activada— lo
    sostiene `test_camino_escritura.py::test_el_circuito_completo…`, así que aquí
    no hace falta un segundo trabajo que compita por el mismo turno de la cola.
    """
    proveedor = proveedor_que_prohibe_llamadas()
    activacion(northstar.slug, meridian.slug)
    trabajo = encolar(sesion, meridian.vacante.id, meridian.candidato.id)
    assert trabajo is not None, "con Meridian activada, `encolar` tiene que dejar su fila"

    # Se retira la activación: el anexo de subprocesador de Meridian no está
    # firmado (D7) y la fila se quedó en la cola.
    activacion(northstar.slug)
    assert ajustes_match().activo, "el interruptor global está apagado: este test sería vacío"

    await una_pasada(sesion, proveedor)

    assert proveedor.llamadas == 0, "salió una llamada al proveedor por una empresa sin anexo"
    repo = repo_de(sesion, meridian)
    assert repo.scores() == [], "se guardó un score de una empresa sin anexo"
    # Qué estado le queda al trabajo rechazado es una **pregunta abierta** de este
    # paso (ver la respuesta del escritor de tests): PLAN.md no lo dice y CA3 no lo
    # pide. Lo único que no puede ser es «listo»: nadie lo puntuó.
    tomado = [t for t in repo.trabajos() if t.id == trabajo.id]
    assert [t.estado for t in tomado] != ["listo"], "el trabajo quedó cerrado sin puntuarse"
    assert repo_de(sesion, northstar).scores() == [], "un score cruzó de empresa"


# --- 4 · la vista de la empresa sin anexo ----------------------------------


def test_la_vista_de_meridian_se_renderiza_sin_score_ni_orden_por_score_y_sin_error(
    sesion: Session,
    aplicacion: FastAPI,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    entrar: Entrar,
    activacion: Callable[..., None],
) -> None:
    """`docs/arquitectura.md` §3 (párrafo final), CA3 · 200 y la lista de hoy.

    Sofia, en Meridian, abre su vacante: el recorrido se detiene en el paso 3 —el
    service, no el router ni la plantilla— y la vista se renderiza **sin score ni
    orden por score**, con su lista entera y sin error. Es la mitad de CA3 que no
    es «cero llamadas»: lo que Meridian ve el 15-ene.

    El score se siembra con Meridian activada y la activación se retira después,
    para que el test no dependa de dónde quede la comprobación en el repositorio:
    lo que se asercia es que **la fila existe y no se muestra**. Sin fila, este
    test estaría verde con la tabla vacía.

    Y el contraste de las dos mitades del requisito número uno (CA1, D4): Northstar
    **sí** ve su score, y con los IDs de la otra empresa la respuesta es 404 en los
    dos sentidos, nunca un 200 parcial.
    """
    activacion(northstar.slug, meridian.slug)
    sembrar_score(sesion, meridian, PUNTOS)
    sembrar_score(sesion, northstar, PUNTOS)
    activacion(northstar.slug)

    de_meridian = entrar(meridian.reclutador)
    vista = de_meridian.get(f"/vacantes/{meridian.vacante.id}")
    assert vista.status_code == 200, "la vista de la empresa sin anexo no es un error"
    assert meridian.candidato.correo in vista.text, "la lista de hoy llega recortada"
    assert 'data-testid="score"' not in vista.text
    assert "Pendientes de score" not in vista.text
    assert "orden=score" not in vista.text

    # Los endpoints propios de Match, **enumerados** (F34): el fragmento de la
    # lista responde 200 sin score, no 404 y no 500.
    rutas = rutas_de_match(aplicacion)
    assert rutas, "sin endpoint propio de Match esta mitad sería vacía (R6·I4)"
    for ruta in rutas:
        respuesta = de_meridian.get(ruta.format(vacante_id=meridian.vacante.id))
        assert respuesta.status_code == 200, f"{ruta} falló para la empresa sin anexo"
        assert 'data-testid="score"' not in respuesta.text, f"{ruta} mostró score sin anexo"

    # El contraste: con anexo firmado el score se ve. Si no, este test pasaría
    # igual con una plantilla que no pinte score para nadie.
    de_northstar = entrar(northstar.reclutador)
    assert (
        f'data-testid="score">{PUNTOS}<'
        in de_northstar.get(f"/vacantes/{northstar.vacante.id}").text
    )

    # Multiempresa, en los dos sentidos (CA1, D4): 404, nunca un 200 parcial.
    cruzada = de_meridian.get(f"/vacantes/{northstar.vacante.id}")
    assert cruzada.status_code == 404 and northstar.candidato.correo not in cruzada.text
    al_reves = de_northstar.get(f"/vacantes/{meridian.vacante.id}")
    assert al_reves.status_code == 404 and meridian.candidato.correo not in al_reves.text
    for ruta in rutas:
        assert de_meridian.get(ruta.format(vacante_id=northstar.vacante.id)).status_code == 404


# --- 5 · R4·I1 · el valor por omisión: ninguna empresa activada -------------


async def test_con_la_configuracion_por_omision_northstar_tampoco_encola_ni_llama(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    entrar: Entrar,
    activacion: Callable[..., None],
    proveedor_contado: ProveedorContado,
) -> None:
    """R4·I1 · la activación es un estado que hay que **encender a propósito**.

    Los cuatro tests anteriores miran a Meridian, así que un entorno nuevo —o la
    propia configuración recién creada— podría nacer con **todas** las empresas
    activadas y seguirían verdes. Este mira a la empresa que sí tiene anexo
    firmado, con la configuración en su valor por omisión: sin variable de
    entorno, «ninguna empresa activada» (PLAN.md PR-03 y PR-10, R4·I1).

    Por qué importa el 15-ene: si el defecto fuera «activada», el día que alguien
    despliegue sin la variable, las 39 empresas sin anexo empiezan a encolar.
    """
    activacion()  # sin argumentos: el valor por omisión, la variable no existe
    assert ajustes_match().empresas_activadas == frozenset(), "el defecto no es «ninguna»"
    assert not ajustes_match().match_activado(northstar.slug), "el defecto es un `True` implícito"
    assert ajustes_match().activo, "el interruptor global está apagado: este test sería vacío"

    cliente = entrar(northstar.reclutador)
    otro = sembrar_candidatos(sesion, northstar, 1, postular=False)[0]
    subida = cliente.post(
        f"/candidatos/{northstar.candidato.id}/cv",
        data={"cv_texto": CV_NUEVO, "vacante_id": northstar.vacante.id},
    )
    postulacion = cliente.post(
        f"/vacantes/{northstar.vacante.id}/postulaciones", data={"candidato_id": otro.id}
    )
    assert (subida.status_code, postulacion.status_code) == (200, 200)
    assert encolar(sesion, northstar.vacante.id, northstar.candidato.id) is None

    for empresa in (northstar, meridian):
        repo = repo_de(sesion, empresa)
        assert repo.trabajos() == [], f"{empresa.slug} encoló con la configuración por omisión"
        assert repo.scores() == [], f"{empresa.slug} guardó un score con la configuración apagada"
    assert await una_pasada(sesion, proveedor_contado) == 0, "el bucle corrió sin cola"
    assert proveedor_contado.llamadas == 0

    # Y la vista sigue respondiendo 200 con su lista de hoy, como la de Meridian.
    vista = cliente.get(f"/vacantes/{northstar.vacante.id}")
    assert vista.status_code == 200 and 'data-testid="score"' not in vista.text


# --- 6 · una sola regla, en el punto único de acceso a datos ----------------


def _nombres_de_la_activacion() -> set[str]:
    """Los símbolos del estado por empresa, **derivados** y no escritos a mano.

    Así el test no se queda vacío el día que `match_activado` cambie de nombre
    (F34): se pregunta a la configuración cuáles son sus símbolos de activación.
    El interruptor **global** (`activo`, `CRIBA_MATCH_ACTIVO`) queda fuera a
    propósito: es otra cosa y lo leen la fachada, `encolar` y el bucle (R6·I5).
    """
    nombres = {nombre for nombre in dir(AjustesDeMatch) if "activad" in nombre}
    nombres |= {nombre for nombre in vars(configuracion_de_match) if "EMPRESAS" in nombre}
    return nombres


def _lecturas_de_la_activacion(ruta: Path, nombres: set[str]) -> list[str]:
    fuente = ruta.read_text(encoding="utf-8")
    hallados = []
    for nodo in ast.walk(ast.parse(fuente)):
        leido = ""
        if isinstance(nodo, ast.Attribute):
            leido = nodo.attr
        elif isinstance(nodo, ast.Name):
            leido = nodo.id
        if leido in nombres:
            hallados.append(f"{ruta.relative_to(RAIZ)}:{nodo.lineno}: {leido}")
    return hallados


def test_la_comprobacion_de_d7_se_lee_en_un_solo_sitio_y_no_en_el_router() -> None:
    """PLAN.md PR-10 (criterio de terminado), `docs/arquitectura.md` §4 y §5.3.

    «La comprobación de D7 debe vivir en el mismo punto de acceso a datos, no en
    el router» y «no son dos lugares distintos con dos reglas distintas: es la
    misma función del repositorio llamada dos veces». Eso es una afirmación sobre
    la **forma** del código, y sin test es una frase: hoy el estado por empresa se
    lee en `services/listado.py` y no se lee en el camino de escritura, que es
    justamente la mitad que falta y la que produce la fuga de CA3.

    Es la misma clase de control que la regla (a) de PR-04 (`test_aislamiento.py`)
    y por la misma razón: dos sitios que deciden D7 son dos reglas que se separan
    en enero. `tests/` y `migrations/` quedan fuera por ruta, como allí.
    """
    nombres = _nombres_de_la_activacion()
    assert len(nombres) >= 2, f"no se reconoce el estado de activación por empresa: {nombres}"

    permitidas: list[str] = []
    fuera: list[str] = []
    archivos = sorted(APP.rglob("*.py"))
    assert len(archivos) > 20, f"la enumeración no está mirando la aplicación: {len(archivos)}"
    for ruta in archivos:
        en_su_sitio = any(ruta.is_relative_to(sitio) for sitio in DONDE_SE_LEE_LA_ACTIVACION)
        destino = permitidas if en_su_sitio else fuera
        destino.extend(_lecturas_de_la_activacion(ruta, nombres))

    assert permitidas, "nadie lee el estado de activación por empresa: CA3 no está comprobada"
    assert fuera == [], "el estado de activación por empresa se lee fuera del repositorio:\n" + (
        "\n".join(fuera)
    )
