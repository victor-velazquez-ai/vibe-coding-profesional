"""PR-09 · el cliente real del proveedor: modo, invocación y timeout.

El adaptador del proveedor elegido, detrás de la frontera de PR-08 y después de
la comprobación de activación por empresa de PR-10 (regla 1.5 de `PLAN.md` §1,
con el orden que R3·M1 corrigió: **PR-08 → PR-10 → PR-09**).

**Qué proveedor, y cómo se llama** (N4, decisión de Víctor del 22-nov-2026, que
`SPEC.md` §Privacidad deja en sus manos «dentro de esa restricción»): el modelo es
Claude. En **este** repo del curso no hay clave de API, así que el cliente real es
un adaptador que llama al CLI `claude -p` por **subproceso**, sin herramientas y
sin sesión. En el proyecto real del cliente sería la API con su clave en una
variable de entorno, nunca en el repo ni en la CI (F19). Lo que no cambia entre
los dos: el **MOCK es el modo por omisión y el único que la CI usa**.

**Ningún test de este archivo lanza el CLI de verdad.** La costura es una sola
función —la que lanza el proceso— y se sustituye por el doble de
`tests/dobles/cli.py`, que apunta qué recibió. La fixture `ningun_cli_de_verdad`
de `tests/match/conftest.py` la deja prohibida por omisión en **toda** la suite de
Match, para que el olvido de un doble sea un test rojo y no un `claude -p` con un
CV dentro.

Los tres controles que `PLAN.md` PR-09 pide, y dónde están:

1. **la regla de log** (F12) → `test_logs_sin_cv.py`, con la clave de F19;
2. **timeout y error tipado** → aquí, tests 4 y 5, y el **cerrojo sobre la cadena
   de causas** que la segunda ronda de revisión pide (M4): lo que sale tipado no
   puede llevar colgada la excepción cruda, que trae el prompt y la salida parcial
   del proceso dentro;
3. **el modo MOCK por configuración explícita, y que nunca abre red** → aquí,
   tests 1, 2 y 3, más el guardia de la única puerta (test 6).

Y el requisito número uno del cliente, que no se suspende porque el paso sea un
adaptador: **nada cruza entre empresas** (CA1, D4) y una empresa sin anexo de
subprocesador no produce ni una invocación (CA3, D7) ni siquiera con el cliente
real configurado. Es el test 7.
"""

from __future__ import annotations

import ast
import inspect
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.match.cola.ejecutor import pasadas
from app.match.cola.trabajos import encolar
from app.match.configuracion import IDIOMA_POR_OMISION
from app.match.proveedor.mock import SCORE_DEL_MOCK, ProveedorMock
from tests.dobles.cli import (
    CV_SINTETICO,
    RAZONES_DEL_CLI,
    SCORE_DEL_CLI,
    CLIDoblado,
    adaptador,
    cli_que_prohibe_llamadas,
    frases_de,
    payload_sintetico,
)
from tests.match.conftest import EmpresaDePrueba, Entrar, repo_de, sembrar_candidatos

RAIZ = Path(__file__).resolve().parents[2]
APP = RAIZ / "app"

# El techo de CA7: p95 de CV recibido a score guardado ≤ 10 min, y eso incluye la
# espera en cola y los reintentos de PR-14. Un timeout **por llamada** igual al
# presupuesto entero no deja sitio para nada de eso.
SEGUNDOS_DE_CA7 = 600

# Argumentos que le darían al CLI **herramientas** o **sesión**, que es justo lo
# que la decisión de Víctor excluye. No es una lista exhaustiva —ninguna lista de
# prohibidos lo es (F34)— y por eso el control de verdad es el otro: el CV viaja
# por la entrada estándar y nada del CV aparece en la línea de órdenes. Pero estas
# son las puertas conocidas, y cada una deja texto del CV **fuera de Criba**: en
# un archivo de sesión o en lo que una herramienta escriba (D15, F12, CA2).
ARGUMENTOS_PROHIBIDOS = frozenset(
    {
        "-c",
        "--continue",
        "--resume",
        "--session-id",
        "--allowedTools",
        "--allowed-tools",
        "--disallowedTools",
        "--permission-mode",
        "--dangerously-skip-permissions",
        "--add-dir",
        "--mcp-config",
        "--settings",
    }
)

# Valores que **no** son el modo declarado. Ninguno puede seleccionar el cliente
# real: «el modo se selecciona por configuración explícita» (PLAN.md PR-09, test 3)
# y un valor mal escrito que acabe eligiendo el adaptador real manda CVs fuera de
# Criba por una errata.
MODOS_QUE_NO_SON_EL_MODO = ("claude", "real", "produccion", "1", "si", "")

# Las formas de lanzar un proceso desde Python. El guardia del test 6 las busca en
# **toda** la aplicación: la regla de log de F12 y la frontera de CA2 valen lo que
# valga la cantidad de puertas por las que un CV puede salir del proceso.
_MODULOS_DE_PROCESO = frozenset({"subprocess", "pty"})
_LLAMADAS_DE_PROCESO = frozenset(
    {"system", "popen", "create_subprocess_exec", "create_subprocess_shell"}
)


def _o_el_error(funcion: Callable[[], Any]) -> Any:
    """Lo que devuelve, o la excepción que levanta.

    Existe para un solo caso: un valor de modo desconocido. Que la fábrica falle
    al arrancar o que se quede en el MOCK son **las dos salidas razonables** y
    `PLAN.md` no elige ninguna, así que este test no la elige tampoco: lo único
    que asercia es que el valor raro **no** selecciona el cliente real.
    """
    try:
        return funcion()
    except Exception as error:
        return error


# --- 1 · el adaptador existe, se construye sin argumentos y tipa sus errores --


def test_el_adaptador_real_se_construye_sin_argumentos_y_sus_errores_son_tipados() -> None:
    """PLAN.md PR-09 (archivos y test 2) · la superficie del paso.

    Tres cosas que el resto del archivo da por hechas, juntas y en un sitio:

    - **se construye sin argumentos.** No es estilo: el recorrido de
      implementaciones de la frontera de CA2 instancia cada clase con `puntuar`
      del paquete `app/match/proveedor/` **sin argumentos**
      (`test_pseudonimizacion.py::implementaciones_del_proveedor`, «el cliente de
      PR-09 se configura por variable de entorno, no por constructor»). Un
      adaptador que pidiera su configuración por constructor dejaría ese recorrido
      roto y la frontera sin comprobar justo en el paso en el que empieza a
      importar;
    - **`puntuar` es asíncrona**, que es lo que el `Protocol` `Proveedor` declara y
      lo que ADR-001 exige (T5: si el cliente elegido no ofrece modo asíncrono, se
      revisa la ADR);
    - **el error del timeout es una subclase del error del proveedor.** PR-11
      clasifica las causas: timeout y 500 son **transitorias** —pendiente con
      reintento— y «CV sin texto» es permanente (tabla de estados de PR-11). Si el
      timeout no fuera distinguible por tipo, esa tabla se tendría que leer de un
      mensaje de texto.

    Y el modo vive en una variable de entorno de Criba, no en el código: es la
    mitigación que `docs/fallas.md` asigna a F19 a costo cero.
    """
    puerta = adaptador()

    cliente = puerta.real()  # sin argumentos
    assert inspect.iscoroutinefunction(cliente.puntuar), (
        "`puntuar` no es asíncrona: el `Protocol` `Proveedor` la declara `async` (ADR-001, T5)"
    )
    assert callable(puerta.costura), "la costura del subproceso no es invocable"

    assert issubclass(puerta.tiempo_agotado, puerta.error), (
        "el error del timeout no es una subclase del error del proveedor: PR-11 no podría "
        "separar la causa transitoria de la permanente por tipo"
    )
    assert not issubclass(puerta.error, subprocess.SubprocessError), (
        "el «error tipado» del adaptador es la excepción cruda del subproceso con otro nombre"
    )

    assert puerta.modo_mock != puerta.modo_cli, "los dos modos son el mismo valor"
    assert puerta.variable_de_modo.startswith("CRIBA_"), (
        f"{puerta.variable_de_modo} no está en el espacio de configuración de Criba: el modo se "
        "lee del entorno, como el interruptor global y la activación por empresa"
    )


# --- 2 · el modo MOCK es el de omisión y el real pide configuración explícita --


def test_el_modo_de_omision_es_el_mock_y_el_cliente_real_solo_con_configuracion_explicita(
    cli: Callable[..., CLIDoblado], modo: Callable[..., None]
) -> None:
    """PLAN.md PR-09, test 3 · «el modo MOCK se selecciona por configuración explícita».

    Leído en el sentido que importa: **sin configuración, el MOCK**. Es la misma
    forma que el estado de activación por empresa (R4·I1) y el interruptor global
    (R6·I5): un entorno nuevo, o un despliegue al que se le olvidó la variable,
    nace en el modo que no saca nada de Criba. Al revés —que el defecto fuera el
    cliente real— el primer entorno sin variable manda CVs al proveedor, y para
    Meridian eso es un incidente de privacidad (D7, CA3), no un ajuste.

    Y **elegir no llama a nadie**: la fábrica construye un objeto, no abre red ni
    lanza procesos. El doble prohibitivo es lo que lo asercia; sin él, una fábrica
    que «comprobara la conexión» al arrancar pasaría este test sin que se note.
    """
    puerta = adaptador()
    doble = cli(cli_que_prohibe_llamadas())

    modo()  # sin variable de entorno: el valor por omisión
    assert isinstance(puerta.configurado(), ProveedorMock), (
        "sin configuración el proveedor no es el MOCK: un despliegue sin la variable sacaría "
        "CVs de Criba (D3 modificado, F19)"
    )

    modo(puerta.modo_mock)
    assert isinstance(puerta.configurado(), ProveedorMock)

    modo(puerta.modo_cli)
    assert isinstance(puerta.configurado(), puerta.real), (
        "con el modo declarado explícitamente la fábrica no devuelve el cliente real: el modo "
        "no selecciona nada y la configuración es decoración"
    )

    for valor in MODOS_QUE_NO_SON_EL_MODO:
        modo(valor)
        elegido = _o_el_error(puerta.configurado)
        assert not isinstance(elegido, puerta.real), (
            f"el valor {valor!r} seleccionó el cliente real: una errata en la variable de "
            "entorno saca CVs de Criba"
        )

    assert doble.llamadas == 0, "elegir el proveedor lanzó un subproceso"


# --- 3 · el bucle usa el proveedor que dice la configuración -----------------


async def test_el_bucle_del_ejecutor_puntua_con_el_proveedor_que_dice_la_configuracion(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    cli: Callable[..., CLIDoblado],
    modo: Callable[..., None],
) -> None:
    """PLAN.md PR-09, test 3 (segunda mitad) · el modo tiene que llegar a alguna parte.

    El test 2 comprueba la fábrica; este comprueba que **alguien la usa**. Hoy el
    bucle construye el MOCK a mano (`cola/ejecutor.py`: `proveedor or
    ProveedorMock()`), así que con la fábrica escrita y el bucle sin tocar el modo
    sería una variable de entorno que no cambia nada: el cliente real existiría y
    no habría forma de llegar a él, y la pregunta abierta 11 de §9 —«¿el MOCK es
    solo de test o también interruptor de producción?»— seguiría sin la mitad que
    `PLAN.md` sí decide («PR-09 lo implementa solo como modo de configuración»).

    Las dos mitades en el mismo test porque lo que se asercia es el **contraste**:
    con el modo por omisión puntúa el MOCK y **no se lanza ningún proceso** (ahí
    está la mitad «nunca abre red» del test 3 del plan), y con el modo declarado
    puntúa el adaptador real, una invocación, y el score guardado es el que
    devolvió el CLI. Con un solo caso, un bucle que siempre usara el MOCK pasaría
    la primera mitad y nadie vería la segunda.

    El doble prohibitivo no basta como control —`una_pasada` captura por trabajo,
    así que su `AssertionError` se convertiría en un trabajo en `error` y el test
    pasaría solo—: el control es `llamadas == 0` y el score del MOCK guardado.
    """
    puerta = adaptador()
    prohibido = cli(cli_que_prohibe_llamadas())
    modo()

    assert encolar(sesion, northstar.vacante.id, northstar.candidato.id) is not None
    assert await pasadas(sesion) == 1, "el bucle no puntuó el trabajo con el modo por omisión"
    del_mock = repo_de(sesion, northstar).scores()
    assert [fila.score for fila in del_mock] == [SCORE_DEL_MOCK], (
        "con el modo por omisión el score no es el del MOCK: la CI no está corriendo con el "
        "único proveedor que no sale de la red (N4, `docs/arquitectura.md` §2)"
    )
    assert prohibido.llamadas == 0, "el modo MOCK lanzó el CLI del proveedor"

    doble = cli()
    modo(puerta.modo_cli)
    otro = sembrar_candidatos(sesion, northstar, 1)[0]
    assert encolar(sesion, northstar.vacante.id, otro.id) is not None
    assert await pasadas(sesion) == 1, "el bucle no puntuó el trabajo con el cliente real"

    assert doble.llamadas == 1, (
        "el bucle no llegó al cliente real con el modo declarado: el modo de configuración no "
        "selecciona el proveedor de la pasada"
    )
    del_cli = [fila for fila in repo_de(sesion, northstar).scores() if fila.candidato_id == otro.id]
    assert [fila.score for fila in del_cli] == [SCORE_DEL_CLI]
    assert repo_de(sesion, meridian).scores() == [], "un score cruzó de empresa"


# --- 4 · la invocación: el CV por la entrada, el modelo declarado ------------


async def test_el_cv_viaja_por_la_entrada_estandar_y_la_invocacion_declara_el_modelo(
    cli: Callable[..., CLIDoblado],
) -> None:
    """N4 (`claude -p`, sin herramientas y sin sesión) y D15 · qué se lanza.

    Cuatro propiedades de la invocación, y ninguna es decorativa:

    - **el CV va por la entrada estándar y no en la línea de órdenes.** `argv` es
      visible para cualquier proceso de la máquina (`ps`), sale en los volcados y
      es lo que `subprocess.TimeoutExpired` lleva dentro al fallar: un CV en `argv`
      es F12 por una vía que ningún filtro de log tapa, y D3 modificado autorizó
      la salida del CV bajo tres condiciones que `ps` no cumple ninguna;
    - **es el modo no interactivo de la decisión** (`claude -p`): sin eso el
      proceso espera una entrada que nadie va a darle y el trabajo muere por
      timeout en cada intento;
    - **sin herramientas y sin sesión** (`ARGUMENTOS_PROHIBIDOS`): las dos cosas
      escriben el CV **fuera de Criba** —un archivo de sesión, lo que escriba una
      herramienta— y eso es exactamente lo que D15 y el inventario de borrado de
      CA16 no pueden cubrir;
    - **el modelo se pide explícitamente y es el que se reporta.** D15 y CA15
      exigen la versión de modelo en cada fila de auditoría (PR-12). Si la versión
      que el adaptador devuelve no es la que pidió —porque el CLI eligió su
      modelo por omisión, y ese cambia—, la fila de auditoría de marzo dice una
      cosa y la llamada fue otra. Por eso la salida del doble **no** trae modelo
      dentro: la única fuente posible es lo que el adaptador pidió.
    """
    puerta = adaptador()
    doble = cli()
    payload = payload_sintetico()

    respuesta = await puerta.real().puntuar(payload, IDIOMA_POR_OMISION)

    assert doble.llamadas == 1, "el adaptador no lanzó exactamente una invocación"
    invocacion = doble.ultima

    assert payload.cv in invocacion.entrada, (
        "el cuerpo pseudonimizado no viaja por la entrada estándar del proceso"
    )
    frases = frases_de(payload.cv)
    assert frases, "la fixture no da ninguna frase de ocho palabras: el control sería vacío"
    en_argv = sorted(frase for frase in frases if frase in invocacion.linea)
    assert en_argv == [], (
        f"el CV va en la línea de órdenes del proceso: {en_argv[:1]} (F12: `ps`, los volcados y "
        "`TimeoutExpired` lo llevan dentro, y ningún filtro de log lo tapa)"
    )

    assert "claude" in invocacion.argumentos[0].lower(), (
        f"la invocación no es la del CLI de la decisión N4: {invocacion.argumentos[:1]}"
    )
    assert {"-p", "--print"} & set(invocacion.argumentos), (
        "falta el modo no interactivo (`claude -p`): el proceso esperaría una entrada que nadie "
        "le va a dar y cada trabajo moriría por timeout"
    )
    prohibidos = sorted(
        argumento
        for argumento in invocacion.argumentos
        if argumento.split("=", 1)[0] in ARGUMENTOS_PROHIBIDOS
    )
    assert prohibidos == [], (
        f"la invocación da herramientas o sesión al CLI: {prohibidos}. Las dos dejan texto del "
        "CV fuera de Criba, donde D15 no llega y el inventario de borrado de CA16 no lo ve"
    )

    assert respuesta.score == SCORE_DEL_CLI, "el score no sale de la salida estándar del proceso"
    assert tuple(respuesta.razones) == RAZONES_DEL_CLI
    assert respuesta.version_modelo, (
        "la respuesta no trae versión de modelo: D15 y CA15 la exigen en cada fila de auditoría"
    )
    assert any(respuesta.version_modelo in argumento for argumento in invocacion.argumentos), (
        f"la versión reportada ({respuesta.version_modelo!r}) no es la que la invocación pidió: "
        "el modelo lo eligió el CLI y la fila de auditoría de CA15 no sería comprobable"
    )


# --- 5 · el timeout llega al proceso y sale como error tipado ---------------


async def test_el_timeout_llega_al_subproceso_y_sale_como_error_tipado(
    cli: Callable[..., CLIDoblado],
) -> None:
    """PLAN.md PR-09, test 2 · «el cliente aplica timeout y devuelve un error tipado».

    Las dos mitades, y la primera es la que se olvida: un timeout **declarado** en
    una constante y no pasado al proceso es un proceso que se queda colgado. Con
    el ejecutor dentro del proceso web (ADR-001) eso no es un trabajo lento: es un
    hilo retenido mientras 120 reclutadores abren vacantes, que es F11 por la
    puerta de atrás. Así que se asercia el valor que **llegó** al proceso, y que
    está por debajo del presupuesto de CA7 (10 min de CV recibido a score
    guardado, cola y reintentos de PR-14 incluidos).

    La segunda mitad es el tipo. Lo que el subproceso levanta es
    `subprocess.TimeoutExpired`, que **lleva dentro** la línea de órdenes y la
    salida parcial del proceso: si se propaga cruda, cualquier
    `logging.exception` de arriba convierte el fallo en la fuga de F12. Y PR-11
    necesita distinguirla por tipo para dejar el trabajo en «pendiente» con
    reintento, no en «sin score» permanente.
    """
    puerta = adaptador()
    crudo = subprocess.TimeoutExpired(
        cmd=["claude", "-p"], timeout=1.0, output=CV_SINTETICO, stderr=CV_SINTETICO
    )
    doble = cli(CLIDoblado(fallo=crudo))

    with pytest.raises(puerta.tiempo_agotado) as fallo:
        await puerta.real().puntuar(payload_sintetico(), IDIOMA_POR_OMISION)

    assert not isinstance(fallo.value, subprocess.SubprocessError), (
        "el adaptador propaga la excepción cruda del subproceso, que lleva dentro la línea de "
        "órdenes y la salida parcial del proceso (F12)"
    )
    timeout = doble.ultima.timeout
    assert isinstance(timeout, int | float) and timeout > 0, (
        f"al proceso no le llegó ningún timeout ({timeout!r}): un `claude -p` colgado retiene "
        "un hilo del proceso web mientras los reclutadores abren vacantes (ADR-001, F11)"
    )
    assert timeout < SEGUNDOS_DE_CA7, (
        f"el timeout por llamada ({timeout}s) se come el presupuesto entero de CA7 (10 min de "
        "CV recibido a score guardado), sin dejar sitio para la cola ni los reintentos de PR-14"
    )


# --- 6 · los demás fallos crudos también salen tipados ----------------------


def _timeout() -> CLIDoblado:
    return CLIDoblado(fallo=subprocess.TimeoutExpired(cmd=["claude", "-p"], timeout=1.0))


def _codigo_de_salida() -> CLIDoblado:
    return CLIDoblado(fallo=subprocess.CalledProcessError(1, ["claude", "-p"], stderr="falló"))


def _cli_ausente() -> CLIDoblado:
    return CLIDoblado(fallo=FileNotFoundError(2, "no existe el programa claude"))


def _salida_vacia() -> CLIDoblado:
    return CLIDoblado(salida="")


def _salida_que_no_es_json() -> CLIDoblado:
    return CLIDoblado(salida="Lo siento, no puedo ayudarte con eso.")


@pytest.mark.parametrize(
    "doblar",
    (_timeout, _codigo_de_salida, _cli_ausente, _salida_vacia, _salida_que_no_es_json),
    ids=("timeout", "codigo_de_salida", "cli_ausente", "salida_vacia", "salida_no_json"),
)
async def test_ningun_fallo_del_cli_sale_como_excepcion_cruda(
    cli: Callable[..., CLIDoblado], doblar: Callable[[], CLIDoblado]
) -> None:
    """PLAN.md PR-09, test 2 · «un error tipado, **no una excepción cruda**».

    Las cinco formas en que esta invocación falla de verdad, y las cinco levantan
    algo distinto si nadie las convierte: `TimeoutExpired`, `CalledProcessError`,
    `FileNotFoundError` —el CLI no instalado, que es el caso corriente en una
    máquina nueva y en la CI— y, en las dos últimas, un `JSONDecodeError` o un
    `KeyError` al leer una salida que no es el JSON esperado.

    Por qué un tipo y no cinco escapando hacia arriba: quien decide qué hacer con
    el fallo es PR-11, y su tabla de estados reparte por **causa**, no por el
    nombre de la excepción de la librería que lo trajo. Un `KeyError` llegando al
    bucle deja al candidato en un trabajo en `error` con el motivo
    `'KeyError'` —`cola/ejecutor.py` escribe `type(exc).__name__`—, que no es
    ninguno de los tres estados de esa tabla.

    La salida que no es JSON entra aquí y no en PR-11 por el mismo motivo: lo que
    PR-11 clasifica es «respuesta inválida del modelo» como **causa transitoria**,
    y para clasificarla tiene que recibirla ya tipada.
    """
    puerta = adaptador()
    cli(doblar())

    with pytest.raises(puerta.error) as fallo:
        await puerta.real().puntuar(payload_sintetico(), IDIOMA_POR_OMISION)

    assert not isinstance(
        fallo.value, subprocess.SubprocessError | OSError | json.JSONDecodeError | KeyError
    ), f"el fallo sale crudo del adaptador: {type(fallo.value).__name__}"


# --- 6b · el error tipado no arrastra la excepción cruda como causa ---------


def _timeout_con_el_cv_dentro() -> CLIDoblado:
    """El `TimeoutExpired` tal como llega: con el prompt y la salida parcial dentro."""
    return CLIDoblado(
        fallo=subprocess.TimeoutExpired(
            cmd=["claude", "-p"], timeout=1.0, output=CV_SINTETICO, stderr=CV_SINTETICO
        )
    )


def _codigo_de_salida_con_el_cv_dentro() -> CLIDoblado:
    return CLIDoblado(
        fallo=subprocess.CalledProcessError(
            1, ["claude", "-p"], output=CV_SINTETICO, stderr=CV_SINTETICO
        )
    )


@pytest.mark.parametrize(
    "doblar",
    (_timeout_con_el_cv_dentro, _codigo_de_salida_con_el_cv_dentro),
    ids=("timeout", "codigo_de_salida"),
)
async def test_el_error_tipado_no_arrastra_la_excepcion_cruda_del_subproceso_como_causa(
    cli: Callable[..., CLIDoblado], doblar: Callable[[], CLIDoblado]
) -> None:
    """F12, D15 · la cadena de causas es una superficie de salida más (ronda 2, M4).

    Los tests 5 y 6 comprueban que lo que **sale** del adaptador es un error
    tipado. Esto comprueba la otra mitad, que es la que hoy no asercia nadie: que
    el error tipado no lleve **colgada** la excepción cruda del subproceso. Las dos
    que este paso recibe llevan dentro la línea de órdenes, la salida parcial del
    proceso y el error estándar —o sea el prompt y lo que el modelo había empezado
    a responder— y Python engancha ese objeto al nuevo error por sí solo, sin que
    nadie lo pida: `raise` dentro de un `except` deja la original en la cadena.

    Por qué importa hoy que no hay fuga: `cola/ejecutor.py` no escribe la traza, y
    por eso `test_logs_sin_cv.py` —que mira líneas de log y `str(error)`— queda
    verde aunque la cadena se arrastre. El día que alguien añada el
    `logging.exception` más natural del mundo en el bucle, el formateador imprime
    la cadena y el CV de las ~680 personas de la demo acaba en los logs de la
    plataforma, donde D15 no llega y el inventario de borrado de CA16 no lo ve. El
    control de F12 no lo habría visto venir: la defensa existe (`raise … from
    None`) y quitarla deja la suite verde.

    Las dos cosas que se exigen, y cada una tapa una forma distinta de perderla:

    - **`__cause__` vacío**: nadie encadena la cruda a propósito (`raise … from
      fallo`), que es la forma en que esto se «arregla para depurar mejor» y la que
      sí imprime el contenido en cualquier traza;
    - **el contexto suprimido**: es lo que hace que el formateador de trazas de
      Python —el que usa `logging.exception`— **no** imprima la original.

    **Lo que este test no puede exigir, y queda dicho aquí:** `__context__` sigue
    apuntando a la excepción cruda incluso con `from None`, porque el lenguaje lo
    engancha igual y `from None` solo suprime su impresión. Un recolector de
    errores que recorra la cadena por su cuenta —no el formateador estándar— sigue
    viéndola con el CV en `output`/`stderr`. Limpiarla del todo es conducta nueva
    en la única puerta del paso y es decisión de quien lleva el cuerpo del PR, no
    de un test que la inventa.

    Este test **nace en verde a propósito**: es un cerrojo sobre una defensa que ya
    está escrita, y su trabajo es ponerse rojo el día que alguien quite el `from
    None` o lo cambie por un `from fallo`.
    """
    puerta = adaptador()
    doble = cli(doblar())

    with pytest.raises(puerta.error) as fallo:
        await puerta.real().puntuar(payload_sintetico(), IDIOMA_POR_OMISION)

    assert doble.llamadas == 1 and isinstance(doble.fallo, BaseException), (
        "el doble no llegó a levantar la excepción cruda: el test no está ejerciendo la cadena"
    )
    assert fallo.value.__cause__ is None, (
        f"el error tipado encadena la excepción cruda del subproceso como causa "
        f"({type(fallo.value.__cause__).__name__}): lleva la línea de órdenes y la salida "
        "parcial del proceso, y cualquier traza de arriba las imprime (F12, D15)"
    )
    assert fallo.value.__suppress_context__, (
        "el error tipado arrastra la excepción cruda del subproceso en su cadena de contexto "
        "sin suprimirla: un `logging.exception` en el bucle imprimiría el prompt y la salida "
        "parcial del CLI en los logs de la plataforma (F12, `docs/arquitectura.md` §5.5). La "
        "defensa es `raise … from None` en el camino del fallo"
    )


# --- 7 · una sola puerta por la que puede salir un CV -----------------------


def _lanzamientos_de_proceso(ruta: Path) -> list[str]:
    """Las formas de lanzar un proceso que hay en ese archivo, con su línea."""
    hallados: list[str] = []
    for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        visto = ""
        if isinstance(nodo, ast.Import):
            visto = next(
                (
                    alias.name
                    for alias in nodo.names
                    if alias.name.split(".")[0] in _MODULOS_DE_PROCESO
                ),
                "",
            )
        elif isinstance(nodo, ast.ImportFrom):
            visto = (
                nodo.module or ""
                if (nodo.module or "").split(".")[0] in _MODULOS_DE_PROCESO
                else ""
            )
        elif isinstance(nodo, ast.Attribute):
            visto = nodo.attr if nodo.attr in _LLAMADAS_DE_PROCESO else ""
        if visto:
            hallados.append(f"{ruta.relative_to(RAIZ)}:{nodo.lineno}: {visto}")
    return hallados


def test_el_subproceso_del_proveedor_vive_en_un_solo_modulo_de_la_aplicacion() -> None:
    """F12, F6, CA2 · la regla de log y la frontera valen por cada puerta que hay.

    Es la misma clase de control que la regla (a) de PR-04 —ninguna sentencia SQL
    de Match fuera de `repositories/`— y existe por la misma razón: una segunda
    puerta no se ve en una revisión de código, se ve enumerando. Aquí la puerta
    manda un CV **fuera del proceso**, así que lo que hay detrás de ella es la
    prohibición de registrar cuerpos (F12), el timeout (ADR-001, CA7) y la
    frontera de tipos de CA2. Un segundo `subprocess.run` en enero —«un script
    rápido para re-puntuar», que es el escenario literal de §5.4— no tiene nada de
    eso, y nadie lo nota hasta la auditoría de marzo.

    `tests/` y `migrations/` quedan fuera por ruta, como en PR-04: este guardia es
    sobre la aplicación. El doble de `tests/dobles/cli.py` lanza procesos tanto
    como un diccionario.
    """
    archivos = sorted(APP.rglob("*.py"))
    assert len(archivos) > 20, f"la enumeración no está mirando la aplicación: {len(archivos)}"

    puertas = {
        ruta: lanzamientos for ruta in archivos if (lanzamientos := _lanzamientos_de_proceso(ruta))
    }
    esperada = APP / "match" / "proveedor" / "cliente.py"
    assert list(puertas) == [esperada], (
        "el lanzamiento de procesos de la aplicación no está en el adaptador del proveedor y "
        "solo ahí:\n"
        + "\n".join(linea for lineas in puertas.values() for linea in lineas)
        + "\n(hoy, con la lista vacía, es que el adaptador de PR-09 todavía no existe)"
    )


# --- 8 · multiempresa: el cliente real no cambia el requisito número uno ----

MARCA_DE_NORTHSTAR = "piso de medicina interna en el turno nocturno"
MARCA_DE_MERIDIAN = "ruta de reparto en almacen refrigerado de Laredo"
CV_DE_NORTHSTAR = f"Enfermera registrada con ocho años en {MARCA_DE_NORTHSTAR}, Houston."
CV_DE_MERIDIAN = f"Operador de montacargas con seis años en {MARCA_DE_MERIDIAN}."


async def test_con_el_cliente_real_configurado_meridian_no_lanza_el_cli_ni_ve_a_northstar(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    entrar: Entrar,
    cli: Callable[..., CLIDoblado],
    modo: Callable[..., None],
) -> None:
    """CA3 y CA1 · el paso que de verdad podía sacar un CV de Criba, por las dos empresas.

    PR-10 probó la activación por empresa con el **doble del proveedor**, porque el
    cliente real no existía (regla 1.5). Este es el primer paso en el que sí
    existe, y es el único momento en que se puede comprobar lo que D7 dice de
    verdad: con el adaptador real **configurado y en el camino**, un CV de
    Meridian no lanza ni una invocación. Si la comprobación de D7 se hubiera
    quedado en el camino del doble, este test es el que lo ve.

    Y las dos mitades de CA1 con los mismos IDs: la reclutadora de Meridian pide
    la vacante de Northstar y recibe **404, nunca un 200 parcial**, y al revés. Más
    la tercera, que es de este paso y no de PR-10: **nada de Meridian viaja en la
    invocación** que sale por Northstar. Un adaptador que juntara trabajos en una
    sola llamada para ahorrar —la optimización tentadora de enero— pasaría los dos
    404 y mandaría los dos CVs en el mismo cuerpo.
    """
    puerta = adaptador()
    doble = cli()
    modo(puerta.modo_cli)

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
        "salió una invocación por una empresa sin anexo de subprocesador firmado (D7, CA3): "
        "con el cliente real configurado, eso es un CV fuera de Criba"
    )
    assert MARCA_DE_NORTHSTAR in doble.ultima.entrada, "no salió el CV de la empresa con anexo"
    assert MARCA_DE_MERIDIAN not in doble.ultima.entrada, (
        "el cuerpo que salió lleva texto de la otra empresa dentro"
    )

    assert [fila.score for fila in repo_de(sesion, northstar).scores()] == [SCORE_DEL_CLI]
    de_meridian_repo = repo_de(sesion, meridian)
    assert de_meridian_repo.trabajos() == [], "Meridian dejó una fila en match_trabajos"
    assert de_meridian_repo.scores() == [], "Meridian dejó una fila en match_scores"

    cruzada = de_meridian.get(f"/vacantes/{northstar.vacante.id}")
    assert cruzada.status_code == 404 and MARCA_DE_NORTHSTAR not in cruzada.text
    al_reves = de_northstar.get(f"/vacantes/{meridian.vacante.id}")
    assert al_reves.status_code == 404 and MARCA_DE_MERIDIAN not in al_reves.text
    propia = de_northstar.get(f"/vacantes/{northstar.vacante.id}")
    assert f'data-testid="score">{SCORE_DEL_CLI}<' in propia.text, (
        "la empresa con anexo firmado no ve el score que el cliente real acabó de calcular"
    )
