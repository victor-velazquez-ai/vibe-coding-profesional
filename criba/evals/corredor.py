"""El camino de producción que recorre el arnés. El único que **llama** a `app/`.

**La regla de este archivo: aquí no hay una segunda forma de puntuar.** Un arnés
que construyera su propio prompt, su propio cliente o su propia pseudonimización
mediría un camino que nadie recorre en producción, y entonces un verde no diría
nada. Así que cada intento pasa por las mismas tres piezas, en el mismo orden que
`MatchService._del_proveedor`:

1. **`services/pseudonimizador.py::pseudonimizar`** — la **única fábrica** del
   `PayloadPseudonimizado` (CA2, PR-08, `docs/arquitectura.md` §5.4). El arnés no
   puede construir el payload a mano: el constructor lo rechaza, y eso es
   deliberado;
2. **`proveedor/cliente.py::proveedor_configurado`** — la fábrica de proveedor de
   producción, leyendo el modo de **la variable de entorno de siempre**
   (`CRIBA_MATCH_PROVEEDOR`). El arnés no instancia `ProveedorClaudeCLI` a mano:
   `--proveedor claude` escribe la variable y pregunta, igual que el bucle del
   ejecutor;
3. la **validación** que hay en ese camino hoy: `exigir_payload` en la frontera e
   `interpretar` dentro del adaptador —el sobre del CLI, el cerco, la forma de la
   respuesta y los **errores tipados** que nunca devuelven un cero (CA13, F8).

**Lo que todavía no existe, y hay que decirlo:** la validación de **PR-11** (score
fuera de 0-100, razones que no son tres, idioma equivocado → pendiente con
reintento; vacante sin descripción → «sin score» con motivo) **no está escrita en
el repo**: PR-11 es el paso siguiente del plan y el arnés no la va a implementar
por su cuenta, porque sería una segunda validación fuera de producción, que es
exactamente lo que el punto de arriba prohíbe. Hasta que PR-11 exista, lo que el
arnés mide de esa tercera pieza es lo que hay, y lo que **él** aporta mientras
tanto es la banda `fuera_de_rango` de `calificacion.py`: un score de 120 no se
redondea a «alto», se enseña como lo que es. Está en el cuerpo del PR y en
`evals/README.md`.

**Qué no recorre, por una razón y no por olvido:** la cola (`cola/ejecutor.py`), el
repositorio y la activación por empresa (PR-10). Las tres necesitan base de datos y
`empresa_id`, y el arnés **no tiene empresa**: sus 12 casos son texto sintético
(D4, CA1 — no hay nada que cruzar). Lo que esas piezas garantizan está probado
donde ocurre, en `tests/match/`.

**La licencia que este archivo se toma, escrita y no supuesta (hallazgo M2 de la
revisión).** Dos cosas, y la medida que dice cuánto se sale de la norma:
`grep -rl 'from app.match' --include=*.py` fuera de `app/match/` y de `tests/`
devuelve seis archivos, y **cuatro importan la fachada**; los dos que no son de
`evals/`: este, con cuatro imports de internos, y `calificacion.py`, con uno que
es **solo un tipo** (`RespuestaDelProveedor`, para calificar lo que el camino
devuelve sin inventarse una forma paralela). Las dos cosas de aquí:

- **importa internos de Match** (`services.pseudonimizador`, `proveedor.cliente`,
  `configuracion`) en vez de la fachada. Es la consecuencia directa de la regla de
  arriba: la fachada exporta `encolar`, `borrar_candidato`, `montar` y
  `listar_vacante` —cuatro símbolos que necesitan sesión de base de datos,
  `empresa_id` y cola—, y el arnés no tiene ninguna de las tres. Medir el camino
  del proveedor por la fachada sería medir la cola de PR-06, no el score;
- **envuelve la costura del proveedor** (`cliente.correr_cli`) mientras dura la
  pasada, para leer el costo que el sobre del CLI reporta (ver `costo_observado`).

Qué dice el plan, al pie de la letra: la **regla (b)** de PR-04 (`PLAN.md` §2) rige
«desde `app/` fuera de `app/match/`», y los dos tests que la enumeran recorren
`APP.rglob` y dicen en su docstring que son **«sobre la aplicación»**
(`tests/match/test_aislamiento.py::test_desde_la_plataforma_el_unico_import_de_match_es_la_fachada`,
`tests/match/test_cliente_proveedor.py::test_el_subproceso_del_proveedor_vive_en_un_solo_modulo_de_la_aplicacion`).
`evals/` no es la aplicación —no lo importa nada de `app/`— así que la regla no lo
alcanza; pero el plan solo nombra **`migrations/` y `tests/`** como exentos por
ruta, y este directorio no está escrito en ninguna de las dos listas. **Esa
omisión no se arregla desde aquí**: ampliar la enumeración es `tests/` y escribir
la exención es `PLAN.md`, y ninguno de los dos es de este rol. Queda escalado en el
cuerpo del PR con las dos salidas posibles.

Lo que sí se puede acotar, y está acotado: este módulo **no lanza ningún proceso**
—la única puerta sigue siendo `cliente.correr_cli`, y el envoltorio la llama—, no
registra ni guarda ningún cuerpo, y la restauración va en un `finally`. Las tres
condiciones las ejerce
`tests/evals/test_corredor.py::test_el_observador_del_costo_no_altera_la_unica_puerta_ni_se_queda_con_cuerpos`.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass

from app.match.configuracion import (
    MODO_CLAUDE_CLI,
    MODO_MOCK,
    VARIABLE_DE_MODO,
    Proveedor,
    RespuestaDelProveedor,
    ajustes_match,
)
from app.match.proveedor import cliente
from app.match.proveedor.cliente import ErrorDelProveedor, proveedor_configurado
from app.match.services.pseudonimizador import pseudonimizar
from app.plataforma.modelos import Candidato
from evals.calificacion import calificar, por_error
from evals.casos import Caso, caso, casos
from evals.informe import ResultadoDeCaso, Totales, resumir_caso, totales

# Los dos valores de `--proveedor` y el modo de producción que selecciona cada uno.
# `claude` en la línea de órdenes y `claude_cli` en la variable: el nombre del
# encargo es el del proveedor y el de la variable es el del **adaptador**, que en
# este repo es el CLI por subproceso (N4, ver `configuracion.py::MODO_CLAUDE_CLI`).
MODOS = {"mock": MODO_MOCK, "claude": MODO_CLAUDE_CLI}

# **Los 12 casos están escritos en español**, y sus términos exigidos también
# («ingles», «requisit», «conciliacion»). Así que el arnés pide las razones en
# español: con el `'en'` por omisión de producción (`IDIOMA_POR_OMISION`, el
# supuesto de D20 sobre la única empresa activada) ningún caso podría acertar las
# menciones y el informe mediría el idioma en vez de la calidad. No es una decisión
# del arnés: la fija el archivo de casos. Se puede cambiar con `--idioma`.
IDIOMA_DE_LOS_CASOS = "es"

# La clave del sobre del CLI donde viene el costo de la llamada. La lee el
# observador de abajo; el adaptador de producción no la mira porque el gasto es de
# **PR-13**, no suyo.
CLAVE_DE_COSTO = "total_cost_usd"


@dataclass(frozen=True, slots=True)
class Intento:
    """Un intento de un caso: lo que el camino de producción devolvió, o su error."""

    caso_id: str
    numero: int
    respuesta: RespuestaDelProveedor | None
    error: str | None
    sustituciones: int


@dataclass(frozen=True, slots=True)
class Pasada:
    """Todo lo que una ejecución del arnés produjo."""

    resultados: tuple[ResultadoDeCaso, ...]
    total: Totales
    intentos: tuple[Intento, ...]

    @property
    def errores(self) -> tuple[Intento, ...]:
        """Los intentos que **no llegaron a respuesta**: el camino falló.

        Son la única razón por la que el arnés sale con código distinto de cero:
        ver `__main__.py`. Un caso que falla por calidad del modelo no es un fallo
        del arnés; un `ErrorDelProveedor` sí es algo roto."""
        return tuple(uno for uno in self.intentos if uno.error is not None)


def candidato_del_caso(un_caso: Caso) -> Candidato:
    """El caso como el `Candidato` que la frontera de CA2 sabe pseudonimizar.

    **Sin campos estructurados, y es una propiedad de los casos sintéticos**:
    `evals/casos.json` trae `cv` y `vacante` y ningún `nombre`, `correo` o
    `telefono`. Así que de las **dos pasadas** del pseudonimizador (R1·B3) el arnés
    ejerce la de **patrones** —correo, teléfono, URL, dirección y foto caen aunque
    no estén en ningún campo— y no la de valores conocidos, que no tiene nada que
    quitar. Los nombres de los 12 CVs son ficticios y los correos son de
    `example.com`, así que no sale PII de nadie; el conjunto dorado de CA14 (PR-17)
    llegará con los campos y ejercerá las dos.

    `links=[]` y no `None` a propósito: la columna tiene `default=list`, que lo
    pone el `INSERT`, y aquí no hay `INSERT` porque **no hay base de datos**. Este
    objeto no se guarda, no tiene `empresa_id` y no entra en ninguna sesión.
    """
    return Candidato(
        nombre="",
        correo="",
        telefono="",
        links=[],
        cv_texto=un_caso["cv"],
    )


def proveedor_del_modo(modo: str) -> Proveedor:
    """El proveedor de producción para `--proveedor mock|claude`.

    Escribe la variable de entorno y **pregunta a la fábrica de producción**, en
    vez de construir el adaptador a mano: así el arnés recorre también la decisión
    de «qué proveedor se usa», que es la que protege que una errata no saque CVs de
    Criba (PR-09). `cache_clear` porque `ajustes_match` se lee una vez por proceso
    y el arnés fija el modo **después** de arrancar.
    """
    if modo not in MODOS:
        raise ValueError(f"--proveedor {modo!r} no es uno de {sorted(MODOS)}")
    os.environ[VARIABLE_DE_MODO] = MODOS[modo]
    ajustes_match.cache_clear()
    return proveedor_configurado()


@contextmanager
def costo_observado(activo: bool) -> Iterator[list[float]]:
    """El costo que **el proveedor reporta**, leído de paso en la única puerta.

    El CLI lo trae en su sobre (`total_cost_usd`, medido en PR-09: 0,0082 USD por
    CV sintético) y el adaptador de producción lo descarta, porque contar el gasto
    es de **PR-13** y no suyo. El arnés lo necesita —el encargo pide el costo de la
    pasada— y tiene dos salidas: cambiar el contrato de `RespuestaDelProveedor`
    para un informe, pisándole a PR-13 el campo que va a necesitar, o **envolver la
    costura**.

    Esto es lo segundo, y es un observador, no un doble: `correr_cli` se llama de
    verdad, su salida se devuelve **tal cual** y lo único que se hace con ella es
    leerle una clave. Nada de producción cambia en disco; el envoltorio vive en el
    proceso del arnés y se quita al salir del `with`. Cuando PR-13 exponga el costo
    por llamada, esta función se borra entera.

    Con el MOCK no se envuelve nada: no sale del proceso, así que su costo es cero
    y no hay sobre que leer.
    """
    if not activo:
        yield []
        return
    original: Callable[..., str] = cliente.correr_cli
    gastos: list[float] = []

    def observando(argumentos: Sequence[str], entrada: str, timeout: float) -> str:
        salida = original(argumentos, entrada, timeout)
        costo = costo_del_sobre(salida)
        if costo is not None:
            gastos.append(costo)
        return salida

    cliente.correr_cli = observando
    try:
        yield gastos
    finally:
        cliente.correr_cli = original


def costo_del_sobre(salida: str) -> float | None:
    """El `total_cost_usd` del sobre del CLI, o `None` si no viene en esta salida.

    `None` y no una excepción cuando la salida no es el sobre: **el que tiene que
    fallar ahí es el adaptador**, un instante después y con su error tipado
    (`interpretar`). Si este observador levantara su propio error, taparía el de
    producción y el arnés reportaría un fallo del arnés donde había un fallo del
    proveedor. No se traga nada: lo que no se puede leer es el costo, y el costo no
    es la respuesta.
    """
    try:
        sobre = json.loads(salida)
    except json.JSONDecodeError:
        return None
    costo = sobre.get(CLAVE_DE_COSTO) if isinstance(sobre, Mapping) else None
    return float(costo) if isinstance(costo, int | float) else None


async def un_intento(proveedor: Proveedor, un_caso: Caso, numero: int, idioma: str) -> Intento:
    """El camino de producción, de punta a punta, para un caso.

    El `ErrorDelProveedor` se recoge **por intento** y no mata la pasada, que es la
    misma regla que el ejecutor aplica por trabajo (PR-09, tabla de estados de
    PR-11): con el proveedor real, un timeout en el caso 7 no puede tirar a la
    basura los seis intentos ya pagados. Lo que no se recoge es ningún otro error:
    un `FronteraViolada` o un `TypeError` son defectos del arnés y tienen que
    verse.
    """
    payload = pseudonimizar(candidato_del_caso(un_caso))
    try:
        respuesta = await proveedor.puntuar(payload, idioma, un_caso["vacante"])
    except ErrorDelProveedor as fallo:
        return Intento(un_caso["id"], numero, None, f"{type(fallo).__name__}: {fallo}", 0)
    return Intento(un_caso["id"], numero, respuesta, None, payload.sustituciones)


def _calificar_intentos(
    por_correr: Sequence[Caso], intentos: Sequence[Intento]
) -> list[ResultadoDeCaso]:
    """Las k calificaciones de cada caso, con su gemelo **del mismo intento**.

    El gemelo se empareja por número de intento y no contra un promedio: el
    invariante de fs-26 pregunta «¿este CV con la edad dentro puntuó distinto que el
    mismo CV sin ella?», y las dos respuestas tienen que ser de la misma pasada del
    modelo para que la diferencia sea atribuible al dato añadido y no a la varianza
    entre llamadas.

    Si el gemelo falló en ese intento, el caso **no pasa** y el motivo lo nombra: un
    invariante que no se pudo comprobar no se da por bueno, porque es la dimensión
    que sostiene al arnés (fs-26, fs-28, fs-29).

    **Y `critico` del archivo no entra en esta decisión, ni en ninguna otra** (M3):
    cinco casos lo llevan en `casos.json` y **nada del arnés lee ese campo** —los
    cinco se califican y se cuentan como los otros siete—. Qué tendría que hacer un
    crítico en rojo (tumbar la pasada, un código de salida propio, una línea aparte
    del informe) no lo dice el encargo, así que no se adivina: está en «Qué NO
    entra» del cuerpo del PR, con su dueño.
    """
    respuestas = {(uno.caso_id, uno.numero): uno.respuesta for uno in intentos if uno.respuesta}
    errores = {(uno.caso_id, uno.numero): uno.error for uno in intentos if uno.error}
    resultados = []
    for un_caso in por_correr:
        calificaciones = []
        for uno in [i for i in intentos if i.caso_id == un_caso["id"]]:
            gemelo = un_caso["invariante_con"]
            if uno.respuesta is None:
                calificaciones.append(por_error(un_caso["id"], [str(uno.error)]))
            elif gemelo and (gemelo, uno.numero) not in respuestas:
                calificaciones.append(
                    por_error(
                        un_caso["id"],
                        [
                            f"el gemelo {gemelo} no dio respuesta en el intento "
                            f"{uno.numero}, así que el invariante no se pudo "
                            f"comprobar ({errores.get((gemelo, uno.numero))})"
                        ],
                    )
                )
            else:
                calificaciones.append(
                    calificar(
                        un_caso,
                        uno.respuesta,
                        respuestas.get((gemelo, uno.numero)) if gemelo else None,
                    )
                )
        resultados.append(resumir_caso(un_caso["id"], calificaciones))
    return resultados


def casos_a_correr(ids: Sequence[str]) -> tuple[Caso, ...]:
    """Los casos pedidos **más los gemelos que sus invariantes necesiten**.

    Sin esto, `--casos fs-26` no podría calificar nada: su invariante es contra
    fs-25, y pedir un caso suelto dejaría la dimensión sin comparar. Sin `--casos`
    son los 12.
    """
    if not ids:
        return casos()
    elegidos: dict[str, Caso] = {}
    for caso_id in ids:
        uno = caso(caso_id)
        elegidos[caso_id] = uno
        gemelo = uno["invariante_con"]
        if gemelo:
            elegidos.setdefault(gemelo, caso(gemelo))
    return tuple(elegidos.values())


async def correr(
    *,
    modo: str,
    k: int,
    idioma: str = IDIOMA_DE_LOS_CASOS,
    ids: Sequence[str] = (),
    traza: bool = True,
) -> Pasada:
    """La pasada completa: k intentos de cada caso, calificados y contados.

    **Intento por fuera y caso por dentro** —los 12 casos, k veces, en vez de cada
    caso k veces seguidas—: así el gemelo de un invariante se puntúa en la misma
    vuelta que su caso, y así una pasada interrumpida deja los 12 casos con el
    mismo número de intentos en vez de los tres primeros completos.

    Secuencial a propósito: con el proveedor real son llamadas que se pagan y que
    el CLI atiende de una en una. Con el MOCK no sale del proceso y tarda
    milisegundos.
    """
    proveedor = proveedor_del_modo(modo)
    por_correr = casos_a_correr(ids)
    intentos: list[Intento] = []
    with costo_observado(modo != "mock") as gastos:
        for numero in range(1, k + 1):
            for un_caso in por_correr:
                intentos.append(await un_intento(proveedor, un_caso, numero, idioma))
                if traza:
                    _trazar(intentos[-1], numero, k)
    resultados = _calificar_intentos(por_correr, intentos)
    modelos = sorted(
        {uno.respuesta.version_modelo for uno in intentos if uno.respuesta is not None}
    )
    return Pasada(
        resultados=tuple(resultados),
        total=totales(resultados, costo_usd=sum(gastos) if gastos else 0.0, modelos=modelos),
        intentos=tuple(intentos),
    )


def _trazar(intento: Intento, numero: int, k: int) -> None:
    """Una línea por llamada en el error estándar, para que una pasada de 11 minutos
    con el proveedor real no parezca colgada.

    **Score y error, nunca razones ni CV**: es la misma regla de log de F12 y D15, y
    aquí vale igual aunque los casos sean sintéticos, porque el día que esto corra
    con el conjunto dorado de CA14 serán datos del cliente.
    """
    estado = intento.error or f"score={intento.respuesta.score if intento.respuesta else '—'}"
    print(f"  [{numero}/{k}] {intento.caso_id}: {estado}", file=sys.stderr)
