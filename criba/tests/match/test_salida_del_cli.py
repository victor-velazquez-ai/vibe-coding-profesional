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

La **segunda** ronda de revisión del paso añade dos tests más a este archivo, y
los dos son sobre la misma pieza:

- **M2** — `modelUsage` con **dos o más** modelos reportados. Con uno manda el
  reportado (test 3); con dos, hoy manda el **pedido**, que es una versión que el
  CLI no reportó haber usado. Es el test 5, y no elige entre las dos salidas
  razonables: solo prohíbe la que D15 no permite;
- **la premisa de todo el archivo** — que la invocación **pida** la salida
  estructurada. Es el test 6. Sin esa bandera no hay sobre, y entonces ni
  `is_error`, ni `modelUsage`, ni `structured_output` existen: los cinco tests de
  arriba hablarían de una forma que el CLI no devuelve. Es también lo que sostiene
  la forma del doble, que desde M1 emite el sobre por omisión.

Lo que **no** se decide aquí, a propósito: si el score está en 0-100, si las
razones son tres y si están en el idioma pedido. Las tres son de **PR-11**, y su
tabla de estados reparte por causa. Aquí solo se separa «esto es una respuesta»
de «esto no lo es», que es lo que hace falta para no propagar un `KeyError` al
bucle.

Ningún test de este archivo lanza el CLI de verdad.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from contextlib import suppress

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

# Y un segundo modelo reportado en la misma llamada, que es el caso de M2. Pasa
# de verdad: un modelo que enruta a otro, o un reintento interno del CLI que cae
# a un modelo distinto, dejan **dos** entradas en `modelUsage`.
OTRO_MODELO_REPORTADO = "claude-sonnet-9-9-20270101"

# Las formas conocidas de pedir la salida estructurada. Se acepta cualquiera —la
# bandera es de la herramienta y una lista de nombres envejece (F34)— y el test
# falla nombrando la propiedad, igual que en `test_invocacion_endurecida.py`.
FORMATOS_DE_SALIDA = ("--output-format", "--output_format")
FORMATOS_ESTRUCTURADOS = frozenset({"json", "stream-json", "json-stream"})


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


# --- 5 · dos modelos reportados: la versión sigue teniendo que ser verdad ----


async def test_con_dos_modelos_reportados_la_version_no_es_una_que_el_cli_no_reporto(
    cli: Callable[..., CLIDoblado],
) -> None:
    """D15 y CA15 · «en marzo tiene que ser verdad», también con `modelUsage` de dos.

    El hueco que la ronda de revisión del paso llama **M2**. El test 3 defiende la
    regla con **un** modelo reportado: manda el reportado sobre el pedido. Con
    **dos o más**, hoy esa regla se invierte en silencio y la versión que viaja
    hacia la fila de auditoría de PR-12 es la que la invocación **pidió**, que en
    este caso el CLI no reportó haber usado. La medición 4c del cuerpo del PR lo
    dice con su propia salida: «dos modelos reportados → modelo=
    claude-haiku-4-5-20251001», el pedido.

    No es un caso de laboratorio: un modelo que enruta a otro, o un reintento
    interno del CLI que cae a un modelo distinto, dejan dos entradas en
    `modelUsage`. Y lo que se guarda es la única cosa que la auditoría de marzo
    tiene para decir con qué se calculó un score; una cadena que nadie reportó es
    una fila de auditoría falsa, que es peor que una fila ausente.

    **Lo que este test NO elige**, porque `PLAN.md` no lo elige y el escritor de
    tests no adivina (es el mismo patrón que `_o_el_error` en
    `test_cliente_proveedor.py` con el modo desconocido): si el adaptador debe
    levantar un **error tipado** —y que PR-11 lo trate como causa transitoria— o
    **registrar lo que de verdad se usó** (uno de los dos, o los dos). Las dos son
    salidas razonables y la decisión es de quien lleva el cuerpo del PR, con PR-12
    detrás. Lo único que se exige es lo que D15 no deja negociar: que la versión
    que sale de aquí **no sea una que el CLI no reportó**.
    """
    puerta = adaptador()
    reportados = (MODELO_REPORTADO, OTRO_MODELO_REPORTADO)
    doble = cli(
        CLIDoblado(
            salida=sobre(
                structured_output=cuerpo(),
                modelUsage={
                    MODELO_REPORTADO: {"inputTokens": 1200, "outputTokens": 90},
                    OTRO_MODELO_REPORTADO: {"inputTokens": 40, "outputTokens": 12},
                },
            )
        )
    )

    # `suppress` y no `pytest.raises`: el **error tipado** es una de las dos
    # salidas razonables de este caso, y PR-11 es quien lo clasifica. Lo que no se
    # permite es la tercera, que es la de hoy: seguir adelante con una versión que
    # nadie reportó.
    respuesta = None
    with suppress(puerta.error):
        respuesta = await puerta.real().puntuar(payload_sintetico(), IDIOMA_POR_OMISION)

    en_argv = sorted(modelo for modelo in reportados if modelo in doble.ultima.linea)
    assert en_argv == [], (
        f"la fixture no está probando nada: {en_argv} es a la vez reportado y pedido, así que "
        "«manda el reportado» y «manda el pedido» darían el mismo resultado"
    )
    if respuesta is None:
        return

    assert respuesta.score == SCORE_DEL_CLI, (
        "con dos modelos reportados se perdió el score del cuerpo: el candidato acaba en "
        "pendiente por una clave del sobre que no es la respuesta (CA13)"
    )
    assert any(modelo in respuesta.version_modelo for modelo in reportados), (
        f"el adaptador devuelve {respuesta.version_modelo!r} y el CLI reportó haber usado "
        f"{list(reportados)}: la versión que va a la fila de auditoría de D15/CA15 es una que "
        "nadie reportó. Vale cualquiera de las dos salidas —un error tipado, o registrar el o "
        "los modelos reportados—, pero no la versión pedida cuando no es ninguna de las usadas"
    )


# --- 6 · la premisa del archivo: el sobre se pide --------------------------


def _formato_pedido(argumentos: Sequence[str]) -> str | None:
    """El valor de la bandera de formato de salida, en sus dos formas (`--x v`, `--x=v`)."""
    for indice, argumento in enumerate(argumentos):
        for bandera in FORMATOS_DE_SALIDA:
            if argumento == bandera and indice + 1 < len(argumentos):
                return argumentos[indice + 1]
            if argumento.startswith(f"{bandera}="):
                return argumento.split("=", 1)[1]
    return None


async def test_el_pedido_declara_el_formato_de_salida_del_que_depende_todo_el_paso(
    cli: Callable[..., CLIDoblado],
) -> None:
    """N4, D15/CA15 y CA13 · el sobre no se supone: se pide.

    Es la **premisa** de este archivo, y hasta la ronda de revisión del paso no la
    aserciaba nadie. Todo lo demás —que el score salga de `structured_output` o de
    `result`, que `is_error` no acabe en un cero, que la versión de modelo salga de
    `modelUsage`— solo llega si la invocación pide la salida estructurada. Sin esa
    bandera el CLI escribe **texto suelto**, y entonces: no hay `is_error` que
    mirar (un error del proveedor se lee como respuesta del modelo), no hay
    `modelUsage` (la versión de la fila de auditoría pasa a ser la pedida, siempre,
    y D15 deja de ser comprobable) y el cuerpo llega envuelto en la prosa del
    modelo.

    Y es también lo que sostiene la forma del doble (M1 de la ronda de revisión):
    `tests/dobles/cli.py::salida_del_cli` emite el sobre **porque esta bandera va
    en todas las invocaciones**. Si alguien la quita, este test se pone rojo aquí y
    no en veinte tests que hablan de otra cosa.

    Se acepta cualquiera de las formas conocidas de pedirlo: la bandera es de la
    herramienta y una lista de nombres envejece (F34), así que el test falla
    nombrando la propiedad.
    """
    puerta = adaptador()
    doble = cli()

    await puerta.real().puntuar(payload_sintetico(), IDIOMA_POR_OMISION)

    assert doble.llamadas == 1, "el adaptador no lanzó exactamente una invocación"
    formato = _formato_pedido(doble.ultima.argumentos)
    assert formato in FORMATOS_ESTRUCTURADOS, (
        f"la invocación no pide una salida estructurada ({formato!r}): sin el sobre no hay "
        "`is_error` que mirar —un fallo del proveedor se leería como respuesta del modelo "
        "(CA13, F8)— ni `modelUsage` del que sacar la versión que D15 y CA15 exigen en cada "
        f"fila de auditoría. Formas aceptadas: {sorted(FORMATOS_ESTRUCTURADOS)}"
    )
