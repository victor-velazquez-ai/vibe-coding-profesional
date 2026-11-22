"""PR-09 · lo que el CLI escribe **de verdad**: el sobre, el cerco y la versión usada.

Este archivo cubre el hueco que la ronda de revisión de PR-09 llama **I1**: los
tests del paso solo ejercían el **JSON pelado** que fija el doble
(`tests/dobles/cli.py::salida_del_cli`), y el camino que producción recorre es
otro — el **sobre** de `--output-format json`, con `is_error`,
`structured_output`, `result` y `modelUsage` dentro, y con el cerco ```` ```json ````
que el modelo pone alrededor aunque se le pida que no. Era la parte del adaptador
con más superficie y cero protección: revertir la lectura del sobre dejaba la
suite verde.

Qué criterio sostiene cada test, porque ninguno es sobre «formas raras de JSON»:

- **CA13 y F8** — «o hay score, o hay *sin score* con su motivo; **nunca un
  cero**». Un `is_error` del CLI, o un sobre sin cuerpo usable, no puede acabar en
  un número: un cero ahí es un candidato mal puntuado por un fallo nuestro;
- **D15 y CA15** — la fila de auditoría de cada score lleva la **versión del
  modelo**, y en marzo tiene que ser verdad. La versión que vale es la que el CLI
  reporta haber **usado** (`modelUsage`), no la que pedimos «por si acaso»;
- **el cerco** no es una anomalía de la respuesta, es una forma de escribirla:
  convertirlo en «respuesta inválida» deja al candidato en pendiente por tres
  caracteres, y eso es coste de reintento (PR-14) y un trabajo en `error` por una
  respuesta que estaba bien.

Lo que **no** se decide aquí, a propósito: si el score está en 0-100, si las
razones son tres y si están en el idioma pedido. Las tres son de **PR-11**, y su
tabla de estados reparte por causa. Aquí solo se separa «esto es una respuesta»
de «esto no lo es», que es lo que hace falta para no propagar un `KeyError` al
bucle.

Ningún test de este archivo lanza el CLI de verdad.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest

from app.match.configuracion import IDIOMA_POR_OMISION
from tests.dobles.cli import (
    RAZONES_DEL_CLI,
    SCORE_DEL_CLI,
    CLIDoblado,
    adaptador,
    payload_sintetico,
)

CERCO = "```"

# Un modelo **distinto** del que la invocación pide. No es un caso exótico: el
# alias `haiku` resuelve a la versión del día, y el día que resuelva a otra —o
# que el CLI caiga a su modelo por omisión— la fila de auditoría de CA15 diría
# una cosa y la llamada habría sido otra.
MODELO_REPORTADO = "claude-haiku-7-7-20270315"


def cuerpo(score: int = SCORE_DEL_CLI, razones: tuple[str, ...] = RAZONES_DEL_CLI) -> dict:
    """El objeto del esquema: lo que el modelo tiene que devolver."""
    return {"score": score, "razones": list(razones)}


def sobre(**claves: object) -> str:
    """El sobre de `--output-format json`, con las claves que el caso necesite.

    Las claves de relleno están porque el sobre real las trae y porque el
    adaptador tiene que distinguir **el sobre** de un cuerpo pelado por algo: si
    un día se distinguiera por «tiene exactamente estas claves», este relleno es
    lo que lo delata.
    """
    base: dict[str, object] = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "duration_ms": 1234,
        "num_turns": 1,
        "session_id": "sin-sesion",
    }
    return json.dumps(base | claves, ensure_ascii=False)


def con_cerco(texto: str, etiqueta: str = "json", en_una_linea: bool = False) -> str:
    """El mismo texto envuelto en un cerco de bloque de código."""
    if en_una_linea:
        return f"{CERCO}{etiqueta} {texto} {CERCO}" if etiqueta else f"{CERCO}{texto}{CERCO}"
    return f"{CERCO}{etiqueta}\n{texto}\n{CERCO}"


# --- 1 · el score sale del cuerpo que el sobre trae dentro ------------------


@pytest.mark.parametrize("donde", ("structured_output", "result"))
async def test_el_score_sale_del_cuerpo_que_trae_el_sobre_del_cli_y_no_de_sus_claves(
    cli: Callable[..., CLIDoblado], donde: str
) -> None:
    """N4 y el alcance 1 de `SPEC.md` · el camino que producción recorre.

    Las dos formas en que el sobre lleva el cuerpo, y las dos llegan de verdad:
    `structured_output` —el objeto ya validado contra el `--json-schema`— y
    `result`, que es **el texto** que el modelo escribió y que hay que leer. Un
    adaptador que solo entienda el cuerpo pelado del doble devuelve «respuesta
    inválida» en cada llamada real: el paso entero quedaría verde en la CI y en
    rojo el 15-ene, que es el día de la demo.

    El sobre trae claves de relleno a propósito (`type`, `duration_ms`,
    `session_id`): el score no puede salir de ellas.
    """
    puerta = adaptador()
    carga = cuerpo()
    salida = sobre(**{donde: carga if donde == "structured_output" else json.dumps(carga)})
    doble = cli(CLIDoblado(salida=salida))

    respuesta = await puerta.real().puntuar(payload_sintetico(), IDIOMA_POR_OMISION)

    assert doble.llamadas == 1
    assert respuesta.score == SCORE_DEL_CLI, (
        f"el score no sale del cuerpo que el sobre trae en `{donde}`: con la salida real del "
        "CLI el adaptador no sabe leer su propia respuesta"
    )
    assert tuple(respuesta.razones) == RAZONES_DEL_CLI
    assert respuesta.motivo_sin_score is None, (
        "hay score y además motivo de «sin score»: CA13 dice que es lo uno o lo otro"
    )


# --- 2 · un error del CLI nunca es un score --------------------------------


async def test_un_sobre_con_is_error_no_da_score_sino_error_tipado(
    cli: Callable[..., CLIDoblado],
) -> None:
    """CA13, F8 · «nunca un cero, y nunca un score que no se calculó».

    El sobre lleva `is_error: true` **y** un `result` perfectamente legible, que
    es la forma en que esto pasa de verdad: el CLI agota su tope de gasto o su
    número de turnos y devuelve en `result` el texto de su propio error, o lo que
    el modelo había alcanzado a escribir. Un adaptador que lea `result` sin mirar
    `is_error` convierte ese fallo en un score para un candidato — y nadie puede
    distinguirlo después de un score calculado.

    Sale como **error tipado** porque quien decide qué hacer con él es PR-11:
    causa transitoria, pendiente con reintento, no «sin score» permanente (CA13:
    un permanente le atribuiría al candidato un fallo que es nuestro).
    """
    puerta = adaptador()
    cli(CLIDoblado(salida=sobre(is_error=True, result=json.dumps(cuerpo()))))

    with pytest.raises(puerta.error) as fallo:
        await puerta.real().puntuar(payload_sintetico(), IDIOMA_POR_OMISION)

    assert str(SCORE_DEL_CLI) not in str(fallo.value), (
        "el error cita el score que venía en el sobre de un fallo: ese número no se calculó"
    )


@pytest.mark.parametrize(
    "claves",
    (
        {"result": ""},
        {"result": "   \n"},
        {"structured_output": {}},
        {"structured_output": None, "result": None},
        {},
    ),
    ids=("result_vacio", "result_en_blanco", "estructurado_vacio", "los_dos_nulos", "ninguno"),
)
async def test_un_sobre_sin_cuerpo_usable_no_da_score_ni_un_cero(
    cli: Callable[..., CLIDoblado], claves: dict[str, object]
) -> None:
    """CA13 · el sobre llegó, el cuerpo no. Las cinco formas en que pasa.

    Es el caso del tope de gasto por llamada (D12, `--max-budget-usd`) y el del
    modelo que no escribió nada: el CLI responde con su sobre y sin cuerpo. Lo
    que **no** puede pasar es que un `sobre.get("result")` que vale `None` acabe
    en un score 0 o en razones vacías guardadas como si fueran una respuesta: la
    vista de la reclutadora mostraría un 0 junto al nombre de un candidato que
    nadie puntuó (F8, `SPEC.md` alcance 6: «nunca un cero»).
    """
    puerta = adaptador()
    cli(CLIDoblado(salida=sobre(**claves)))

    with pytest.raises(puerta.error):
        await puerta.real().puntuar(payload_sintetico(), IDIOMA_POR_OMISION)


# --- 3 · la versión de modelo que va a la fila de auditoría ----------------


async def test_la_version_de_modelo_es_la_que_el_cli_reporta_haber_usado(
    cli: Callable[..., CLIDoblado],
) -> None:
    """D15 y CA15 · «versión del modelo» en cada fila de auditoría, y verdad en marzo.

    Dos mitades de un solo criterio:

    - **si el sobre reporta un modelo** (`modelUsage`), la versión que el
      adaptador devuelve es **esa**, aunque no sea la que la invocación pidió. Lo
      que la auditoría de CA15 tiene que poder decir es con qué se calculó el
      score, no con qué queríamos calcularlo; y el día que el alias resuelva a
      otra versión, o que el CLI caiga a su modelo por omisión, la diferencia es
      exactamente lo que hay que registrar;
    - **si no reporta ninguno**, la versión es la que la invocación pidió, que es
      la única fuente que queda y está en `argv`.

    Lo que se hace con un modelo distinto del pedido —avisar, rechazar, recalcular
    el costo— **no es de este paso**: el gasto es PR-13 y la fila de auditoría es
    PR-12. Aquí la única exigencia es que la cadena que viaja hacia ellos sea la
    del modelo que de verdad respondió.
    """
    puerta = adaptador()
    reportado = cli(
        CLIDoblado(
            salida=sobre(
                structured_output=cuerpo(),
                modelUsage={MODELO_REPORTADO: {"inputTokens": 1200, "outputTokens": 90}},
            )
        )
    )

    respuesta = await puerta.real().puntuar(payload_sintetico(), IDIOMA_POR_OMISION)

    assert respuesta.version_modelo == MODELO_REPORTADO, (
        f"el adaptador devuelve {respuesta.version_modelo!r} y el CLI reportó haber usado "
        f"{MODELO_REPORTADO!r}: la fila de auditoría de CA15 diría una cosa y la llamada fue "
        "otra (D15)"
    )
    assert MODELO_REPORTADO not in reportado.ultima.linea, (
        "la fixture no está probando nada: el modelo reportado es el mismo que se pidió"
    )

    sin_reportar = cli(CLIDoblado(salida=sobre(structured_output=cuerpo())))
    otra = await puerta.real().puntuar(payload_sintetico(), IDIOMA_POR_OMISION)
    assert otra.version_modelo, "la respuesta no trae versión de modelo (D15, CA15)"
    assert any(otra.version_modelo in argumento for argumento in sin_reportar.ultima.argumentos), (
        f"sin `modelUsage` en el sobre, la versión devuelta ({otra.version_modelo!r}) no es la "
        "que la invocación pidió: no hay ninguna otra fuente, así que es un valor inventado"
    )


# --- 4 · el cerco de bloque de código --------------------------------------


@pytest.mark.parametrize(
    "envolver",
    (
        lambda texto: con_cerco(texto),
        lambda texto: con_cerco(texto, etiqueta=""),
        lambda texto: con_cerco(texto, etiqueta="", en_una_linea=True),
        lambda texto: sobre(result=con_cerco(texto)),
    ),
    ids=(
        "cerco_con_etiqueta",
        "cerco_sin_etiqueta",
        "cerco_en_una_linea",
        "cerco_dentro_del_sobre",
    ),
)
async def test_un_cerco_de_bloque_de_codigo_no_convierte_una_respuesta_valida_en_error(
    cli: Callable[..., CLIDoblado], envolver: Callable[[str], str]
) -> None:
    """PR-11 por omisión, y por eso es de aquí · el cerco es forma, no anomalía.

    El prompt le pide al modelo que responda «sin cercos y sin texto alrededor», y
    el modelo pone el cerco igual: es la desviación más común que tiene esta
    salida. Si tres caracteres cuentan como «respuesta inválida», cada una de esas
    llamadas se paga dos veces —el reintento de PR-14— y el candidato pasa por
    `pendiente` por una respuesta que estaba bien. Por eso se quita el cerco y
    **lo que viene dentro se valida igual**.

    Las cuatro formas en que llega, y la tercera es la que hoy no está cubierta:
    con etiqueta de lenguaje, sin etiqueta, **en una sola línea** y dentro del
    `result` del sobre. Un `split("\\n")` que dé por hecho el salto de línea
    devuelve cadena vacía justo en la tercera, y el score se pierde con el mismo
    error que si el modelo no hubiera respondido.
    """
    puerta = adaptador()
    cli(CLIDoblado(salida=envolver(json.dumps(cuerpo()))))

    respuesta = await puerta.real().puntuar(payload_sintetico(), IDIOMA_POR_OMISION)

    assert respuesta.score == SCORE_DEL_CLI, (
        "el cerco convirtió una respuesta válida en otra cosa: el score se perdió por tres "
        "caracteres de formato"
    )
    assert tuple(respuesta.razones) == RAZONES_DEL_CLI
