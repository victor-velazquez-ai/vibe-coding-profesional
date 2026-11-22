"""PR-09 · la descripción de la vacante viaja al proveedor, y el payload no cambia.

**Fuente:** decisión de Víctor del 22-nov-2026 sobre el hallazgo 1 del cuerpo de
PR-09, que es el que la planteó («la descripción de la vacante no cruza la
frontera»: `docs/prs/PR-09.md`, §«Lo que este paso descubre y no puede
arreglar»). **La decisión todavía no tiene archivo propio en `docs/`**, y eso es
el hallazgo M2 de esta misma ronda: el escritor de tests no puede escribir fuera
de `tests/`, así que la propuesta de cambio a `docs/decisiones.md` —sin editarlo—
queda para quien lleva el cuerpo del PR. Literal de la decisión:

> la descripción de la vacante es **dato de la empresa, no del candidato**. Viaja
> al proveedor junto al payload pseudonimizado del CV, como un **campo aparte del
> pedido**, y NUNCA dentro de `PayloadPseudonimizado` (CA2 sigue siendo sobre el
> candidato).

Lo que la decisión cierra es un hueco que el propio PR-09 encontró y declaró: el
adaptador puntuaba **un CV** y no el par (candidato, vacante) que `SPEC.md` define
—alcance 1— con las entradas que `SPEC.md` alcance 2 y **D13** enumeran: «solo el
texto del CV y la descripción de la vacante». Hasta este paso no se veía, porque
el MOCK devuelve un número fijo; con un modelo al otro lado, le faltaba la mitad
de la pregunta.

Los tres tests que la decisión pide, uno por mitad:

1. el **MatchService** le pasa al proveedor la descripción de la vacante **del
   trabajo** (la de la fila de la cola, no la de un argumento ni la de la cookie);
2. el **adaptador real** la incluye en lo que manda al CLI;
3. el **payload pseudonimizado no cambia**: sigue llevando `cv` y
   `sustituciones` y nada más, y CA2 sigue siendo sobre el candidato.

Y el cuarto, que no es opcional en este repo: **nada cruza entre empresas**. La
descripción es el **primer dato de la empresa** que sale de Criba, así que el
aislamiento de CA1/D4 deja de ser solo sobre el candidato: la descripción que
viaja es la de la vacante de la empresa del trabajo, la de Meridian no aparece en
ninguna invocación, y los IDs cruzados siguen dando 404 en los dos sentidos.

**Lo que no se decide aquí:** «vacante sin descripción → sin score con motivo» es
el test 1 de **PR-11** (`SPEC.md` alcance 6), y el recálculo cuando la
descripción cambia es **D23/CA9** (PR-21). Este archivo solo exige que el dato
llegue.

Ningún test de este archivo lanza el CLI de verdad.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.orm import Session

from app.match.cola.ejecutor import pasadas
from app.match.cola.trabajos import encolar
from app.match.configuracion import IDIOMA_POR_OMISION
from tests.dobles.cli import CLIDoblado, adaptador, payload_sintetico
from tests.dobles.proveedor import ProveedorContado
from tests.match.conftest import EmpresaDePrueba, Entrar, repo_de

# Dos descripciones de vacante **distinguibles**, porque la fixture de PR-03 le
# pone la misma a las dos empresas: con el mismo texto, «no cruzó» no se puede
# asercir. Cada marca es una frase que solo tiene sentido en su empresa.
MARCA_DE_NORTHSTAR = "piso de medicina interna en el turno nocturno de doce horas"
MARCA_DE_MERIDIAN = "ruta de reparto en almacen refrigerado de Laredo"
DESCRIPCION_DE_NORTHSTAR = (
    f"Enfermera o enfermero de {MARCA_DE_NORTHSTAR}. Licencia RN vigente en Texas."
)
DESCRIPCION_DE_MERIDIAN = f"Operador de montacargas para {MARCA_DE_MERIDIAN}. Turno diurno."

# Los CVs que se suben por la interfaz. No llevan ninguna de las dos marcas: así
# una marca en la invocación solo puede venir de la **descripción de la vacante**.
CV_DE_NORTHSTAR = "Enfermera registrada con ocho anos en hospital de Houston y soporte vital."
CV_DE_MERIDIAN = "Operador con seis anos de experiencia en almacen y manejo de inventario."


def _descripciones(sesion: Session, *empresas: tuple[EmpresaDePrueba, str]) -> None:
    """Le pone a cada vacante su descripción distinguible."""
    for empresa, descripcion in empresas:
        empresa.vacante.descripcion = descripcion
    sesion.flush()


def _pedido(puntuar: Callable[..., Any]) -> Callable[[Any, str, str], Awaitable[Any]]:
    """Una forma de invocar `puntuar` con los **tres** datos del pedido.

    Resuelve la firma en vez de darla por hecha, y falla con un `assert` que
    nombra lo que falta, igual que `adaptador()` y `frontera()`: un `TypeError`
    por llamar con tres argumentos a algo que recibe dos no dice qué criterio está
    en rojo. La forma del pedido —tres parámetros o un objeto— la elige el
    constructor; esto solo exige que la descripción tenga **dónde entrar**.
    """
    parametros = [p for p in inspect.signature(puntuar).parameters.values() if p.name != "self"]
    nombres = ", ".join(p.name for p in parametros)
    assert len(parametros) >= 3, (
        f"`puntuar({nombres})` no tiene dónde entrar la descripción de la vacante. Decisión de "
        "Víctor del 22-nov-2026 sobre el hallazgo 1 de PR-09; `SPEC.md` alcance 2 y D13: las "
        "entradas del score son «solo el texto del CV y la descripción de la vacante»"
    )
    tercero = parametros[2]
    assert tercero.default is not inspect.Parameter.empty, (
        f"el parámetro «{tercero.name}» no tiene valor por omisión. El recorrido de "
        "implementaciones de CA2 —`tests/match/test_pseudonimizacion.py`, contrato de PR-08— "
        "llama `puntuar(cuerpo, idioma)` con dos argumentos y espera `FronteraViolada`: sin "
        "valor por omisión, ese test se cae con un `TypeError` y la frontera deja de estar "
        "comprobada justo donde empieza a importar"
    )
    if tercero.kind is inspect.Parameter.KEYWORD_ONLY:
        return lambda payload, idioma, vacante: puntuar(payload, idioma, **{tercero.name: vacante})
    return lambda payload, idioma, vacante: puntuar(payload, idioma, vacante)


# --- 1 · el MatchService pasa la descripción del trabajo -------------------


async def test_el_match_service_le_pasa_al_proveedor_la_descripcion_de_la_vacante_del_trabajo(
    sesion: Session,
    northstar: EmpresaDePrueba,
    proveedor_contado: ProveedorContado,
) -> None:
    """`SPEC.md` alcance 1 y 2, D13 · el par (candidato, vacante), no el CV solo.

    El score es «por par (candidato, vacante **a la que aplicó**)» y sus entradas
    son «solo el texto del CV **y la descripción de la vacante**». Sin la segunda,
    el modelo responde a «¿qué tan bueno es este CV?», que no es la pregunta:
    puntúa idoneidad contra una vacante que no ha visto. Eso además **bloquea la
    medición de CA14** —un conjunto dorado medido contra un prompt sin vacante
    mide otra cosa— y deja sin sentido el «sin score por vacante sin descripción»
    de `SPEC.md` alcance 6, que es de PR-11.

    La descripción sale de **la vacante del trabajo**, que es la fila de la cola
    ya tomada: la misma regla que el `empresa_id` (F5,
    `docs/arquitectura.md` §5.3, ADR-001 §Decisión 1). No de un argumento del
    llamador y no de la cookie — aquí no hay cookie.

    El doble lee el tercer dato por posición o por nombre, así que no fija la
    forma del pedido: lo que este test exige es que **llegue**.
    """
    _descripciones(sesion, (northstar, DESCRIPCION_DE_NORTHSTAR))
    assert encolar(sesion, northstar.vacante.id, northstar.candidato.id) is not None

    assert await pasadas(sesion, proveedor_contado) == 1, "el bucle no puntuó el trabajo"

    assert proveedor_contado.llamadas == 1
    assert proveedor_contado.vacantes == [DESCRIPCION_DE_NORTHSTAR], (
        f"el proveedor recibió {proveedor_contado.vacantes!r} como descripción de la vacante. "
        "La decisión de Víctor del 22-nov-2026 dice que la descripción viaja al proveedor junto "
        "al payload, como campo aparte del pedido; sin ella el modelo puntúa un CV y no el par "
        "(candidato, vacante) de `SPEC.md` alcance 1"
    )
    assert proveedor_contado.idiomas == [IDIOMA_POR_OMISION], (
        "el idioma dejó de llegar al añadir la descripción (D11, CA11)"
    )


# --- 2 · el adaptador real la manda al CLI ---------------------------------


async def test_el_adaptador_real_manda_la_descripcion_de_la_vacante_al_cli_por_la_entrada(
    cli: Callable[..., CLIDoblado],
) -> None:
    """La decisión de Víctor, segunda mitad · «viaja al proveedor».

    Que el `MatchService` se la pase al proveedor y que el proveedor **la mande**
    son dos cosas: un adaptador que reciba la descripción y la deje caer pasa el
    test 1 y manda exactamente lo mismo que hoy.

    **Va por la entrada estándar, junto al payload**, que es lo que la decisión
    dice («junto al payload pseudonimizado del CV») y lo que la propiedad que
    manda sobre esta invocación exige: `argv` lo lee cualquier proceso de la
    máquina con `ps`, sale en los volcados y es lo que `TimeoutExpired` lleva
    dentro. El CV no puede ir ahí (F12) y la descripción de la vacante de un
    cliente tampoco: es dato de la empresa, y el aislamiento de D4 no distingue
    entre dato del candidato y dato de la empresa.

    (Si Víctor prefiere que la descripción vaya en el prompt del sistema —en
    `argv`—, es una decisión suya y este test es el que hay que cambiar: queda
    anotado como lectura nuestra de «junto al payload».)
    """
    puerta = adaptador()
    doble = cli()
    payload = payload_sintetico()
    pedir = _pedido(puerta.real().puntuar)

    respuesta = await pedir(payload, IDIOMA_POR_OMISION, DESCRIPCION_DE_NORTHSTAR)

    assert doble.llamadas == 1, "el adaptador no lanzó exactamente una invocación"
    invocacion = doble.ultima
    assert MARCA_DE_NORTHSTAR in invocacion.entrada, (
        "la descripción de la vacante no sale en lo que se le manda al CLI: el modelo puntúa un "
        "CV contra una vacante que no ha visto (`SPEC.md` alcance 2, D13)"
    )
    assert payload.cv in invocacion.entrada, (
        "al añadir la descripción se dejó de mandar el cuerpo pseudonimizado del CV"
    )
    assert MARCA_DE_NORTHSTAR not in invocacion.linea, (
        "la descripción de la vacante viaja en la línea de órdenes del proceso: `ps` la muestra "
        "a cualquier proceso de la máquina, y es dato de un cliente (D4, F12)"
    )
    assert respuesta.score is not None, "la llamada con los tres datos ya no devuelve score"


# --- 3 · el payload pseudonimizado no cambia -------------------------------


def test_el_payload_pseudonimizado_sigue_siendo_solo_del_candidato() -> None:
    """CA2 y la decisión de Víctor · «NUNCA dentro de `PayloadPseudonimizado`».

    Es el cierre de la decisión, y el que impide el atajo barato: meter la
    descripción dentro del payload cerraría el hueco en una línea y rompería la
    frontera de PR-08 por dos sitios a la vez.

    - `PayloadPseudonimizado` es **lo que la fábrica única construye y lo que la
      frontera exige**. Si además llevara dato de la empresa, «pseudonimizado»
      dejaría de significar lo que CA2 dice —seis datos del **candidato** fuera—
      y el tipo pasaría a ser «el pedido entero», que es lo que `exigir_payload`
      no puede verificar;
    - y el cuerpo que CA2 inspecciona es el del candidato: un test que busque los
      seis datos de §1a en un payload que además lleva la descripción de la
      vacante seguiría verde mientras el pedido crece sin control.

    Este test **nace en verde a propósito**: es un cerrojo, no un criterio
    pendiente. Su trabajo es ponerse rojo el día que alguien añada un campo al
    payload.
    """
    payload = payload_sintetico()

    expuesto = {nombre for nombre in dir(payload) if not nombre.startswith("_")}
    assert expuesto == {"cv", "sustituciones"}, (
        f"el payload de la frontera expone {sorted(expuesto)}: la descripción de la vacante y "
        "cualquier otro campo del pedido van fuera de `PayloadPseudonimizado` (CA2, decisión de "
        "Víctor del 22-nov-2026)"
    )
    assert MARCA_DE_NORTHSTAR not in payload.cv, (
        "la descripción de la vacante acabó dentro del cuerpo pseudonimizado del candidato"
    )


# --- 4 · multiempresa: la descripción es dato de la empresa ----------------


async def test_la_descripcion_que_sale_es_la_de_la_empresa_del_trabajo_y_la_de_meridian_no_cruza(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    entrar: Entrar,
    cli: Callable[..., CLIDoblado],
    modo: Callable[..., None],
) -> None:
    """CA1, CA3, D4, D7 · el primer dato de la **empresa** que sale de Criba.

    Hasta esta decisión, lo único que salía de Criba era el CV pseudonimizado de
    un candidato, y el aislamiento se comprobaba sobre él. La descripción de la
    vacante es dato de la empresa cliente —lo que Northstar busca, escrito por
    Northstar— y sale por el mismo camino, así que el requisito número uno aplica
    igual:

    - la descripción que viaja es la de la vacante **de la empresa del trabajo**,
      resuelta por el punto único de acceso a datos con su `empresa_id` y no por
      un `select` suelto (D4, CA1, F4). Un repositorio que lea la vacante sin
      filtrar por empresa manda la descripción de Northstar en la llamada de otra
      empresa, y eso no es un bug: es el incidente de [03:03];
    - **Meridian no produce ninguna invocación** ni ninguna fila, con el cliente
      real configurado y en el camino (D7, CA3): no firmó el anexo de
      subprocesador;
    - y los IDs cruzados siguen dando **404 en los dos sentidos, nunca un 200
      parcial**, también sobre el texto de la descripción: la reclutadora de
      Meridian no ve la vacante de Northstar ni al revés (CA1).
    """
    puerta = adaptador()
    doble = cli()
    modo(puerta.modo_cli)
    _descripciones(
        sesion, (northstar, DESCRIPCION_DE_NORTHSTAR), (meridian, DESCRIPCION_DE_MERIDIAN)
    )

    de_meridian = entrar(meridian.reclutador)
    subida_de_meridian = de_meridian.post(
        f"/candidatos/{meridian.candidato.id}/cv",
        data={"cv_texto": CV_DE_MERIDIAN, "vacante_id": meridian.vacante.id},
    )
    de_northstar = entrar(northstar.reclutador)
    subida_de_northstar = de_northstar.post(
        f"/candidatos/{northstar.candidato.id}/cv",
        data={"cv_texto": CV_DE_NORTHSTAR, "vacante_id": northstar.vacante.id},
    )
    # D7 apaga Match para Meridian, no la plataforma de Meridian.
    assert (subida_de_meridian.status_code, subida_de_northstar.status_code) == (200, 200)

    assert await pasadas(sesion) == 1, "la cola tenía algo más que el trabajo de Northstar"
    assert doble.llamadas == 1, (
        "salió una invocación por una empresa sin anexo de subprocesador firmado (D7, CA3)"
    )
    salio = doble.ultima
    assert MARCA_DE_NORTHSTAR in salio.entrada, (
        "no salió la descripción de la vacante de la empresa del trabajo (`SPEC.md` alcance 2)"
    )
    assert MARCA_DE_MERIDIAN not in salio.entrada + salio.linea, (
        "la invocación lleva dentro la descripción de la vacante de la otra empresa: un dato de "
        "Meridian salió de Criba en una llamada de Northstar (CA1, D4)"
    )

    de_meridian_repo = repo_de(sesion, meridian)
    assert de_meridian_repo.trabajos() == [], "Meridian dejó una fila en match_trabajos"
    assert de_meridian_repo.scores() == [], "Meridian dejó una fila en match_scores"

    cruzada = de_meridian.get(f"/vacantes/{northstar.vacante.id}")
    assert cruzada.status_code == 404, "Meridian recibió algo distinto de un 404 (CA1)"
    assert MARCA_DE_NORTHSTAR not in cruzada.text
    al_reves = de_northstar.get(f"/vacantes/{meridian.vacante.id}")
    assert al_reves.status_code == 404, "Northstar recibió algo distinto de un 404 (CA1)"
    assert MARCA_DE_MERIDIAN not in al_reves.text
