"""PR-09 · la regla de log del cliente real: ni cuerpo, ni respuesta, ni clave.

«Los logs son una superficie de salida de datos y el boceto los trata como
telemetría» (`docs/arquitectura.md` §5.5). El escenario, literal: «timeout del
proveedor, el cliente registra el cuerpo de la petición por defecto, y queda texto
de CV de Northstar en los logs de la plataforma. Está pseudonimizado, pero D3
modificado autorizó esa salida bajo tres condiciones y un archivo de log no cumple
ninguna; D15 además dice que el texto del CV no se guarda».

Eso es **F12** (severidad 4 x probabilidad 3 = 12), y su fila dice dos cosas que
este archivo convierte en tests: que hoy **no tiene ninguna forma de detección**
—«se descubre leyendo logs, o en la auditoría de marzo»— y que el test que falta
es el que «falla si una línea de log contiene una frase de ocho palabras del CV de
fixture». Las ocho palabras son la misma medida que CA15 usa para la fila de
auditoría, y por el mismo motivo: corta para que cualquier fragmento reconocible
caiga, larga para que «turno nocturno» no dé un falso positivo.

Con el proveedor elegido (N4: el CLI `claude -p` por subproceso) el camino del
timeout es **peor** que con un cliente HTTP, no mejor:
`subprocess.TimeoutExpired` y `CalledProcessError` llevan dentro la línea de
órdenes, la salida parcial del proceso y el error estándar — o sea el prompt y lo
que el modelo había empezado a responder. Un `logging.exception` en el camino del
fallo, que es la línea más natural del mundo, escribe el CV en el log de la
plataforma. Por eso los dobles de este archivo meten el CV **dentro** de la
excepción cruda: el test no comprueba que el adaptador sea prudente, comprueba que
lo sea con la excepción que de verdad va a recibir.

Y la segunda mitad del criterio de terminado del paso: **la clave del proveedor,
solo en variable de entorno y ausente de los logs** (F19). En este repo del curso
el adaptador no usa clave —es la decisión N4: CLI por subproceso, sin clave—, y
eso también se asercia, porque es la diferencia entre este repo y el del cliente.

Ningún test de este archivo lanza el CLI de verdad.
"""

from __future__ import annotations

import ast
import logging
import subprocess
import traceback
from collections.abc import Callable
from pathlib import Path

import pytest

from app.match.configuracion import IDIOMA_POR_OMISION
from tests.dobles.cli import (
    CV_SINTETICO,
    CLIDoblado,
    adaptador,
    frases_de,
    normalizar,
    payload_sintetico,
    salida_del_cli,
)

RAIZ = Path(__file__).resolve().parents[2]
APP = RAIZ / "app"

# Una clave **ficticia**, y a propósito con una forma que no se parece a la de
# ningún proveedor: la protección de push del repositorio (F19, PR-01) tiene que
# seguir mirando un repo sin nada que parezca una clave, también en los tests.
CLAVE_FICTICIA = "clave-ficticia-de-test-no-sirve-para-nada"

# Las variables de entorno por las que una clave llega a un proceso hijo. El
# adaptador de este repo no usa ninguna; el del proyecto real del cliente usaría
# una, y la regla es la misma: ni en `argv`, ni en el prompt, ni en el log.
VARIABLES_DE_CLAVE = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_API_KEY")

# El prefijo con el que empiezan las claves de este proveedor. El guardia de F19
# lo busca en `app/` y no en todo el repo a propósito: los tests declaran material
# ficticio y el control del repo entero es la protección de push, no un test
# (`docs/fallas.md` F19: «sin test; control del repositorio»).
PREFIJOS_DE_CLAVE = ("sk-ant", "sk-or-", "sk-proj")


def _texto_de_los_logs(capturado: pytest.LogCaptureFixture) -> str:
    """Todo lo que la suite registró, en una sola cadena normalizada.

    Se mira el mensaje formateado, los **argumentos** sin formatear, el
    diccionario del registro —que es donde aterriza un `extra={...}`— y la traza
    de la excepción, que es por donde entra el cuerpo cuando alguien escribe
    `logging.exception`. Mirar solo `getMessage()` dejaría fuera justo el camino
    que F12 nombra.
    """
    piezas: list[str] = []
    for registro in capturado.records:
        piezas.append(registro.getMessage())
        piezas.append(repr(registro.args))
        piezas.append(repr(registro.__dict__))
        if registro.exc_info:
            piezas.append("".join(traceback.format_exception(*registro.exc_info)))
    return normalizar(" ".join(piezas))


def _del_adaptador(capturado: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Los registros que escribió el adaptador del proveedor.

    Sirven para que este test **no sea vacío**: un adaptador que no registre nada
    pasa cualquier prohibición de contenido. Y una línea por llamada es lo que F12
    pide a cambio de prohibir los cuerpos —«solo `request_id`, `empresa_id`,
    decisión, latencia y versiones»— y lo que CA7 necesita para saber cuánto tarda
    el proveedor sin tener que medirlo desde fuera.
    """
    return [
        registro
        for registro in capturado.records
        if registro.module == "cliente" or "proveedor" in registro.name
    ]


def _doble_de_exito() -> CLIDoblado:
    return CLIDoblado(salida=salida_del_cli())


def _doble_de_timeout() -> CLIDoblado:
    """El camino que F12 nombra: la excepción cruda **con el cuerpo dentro**."""
    return CLIDoblado(
        fallo=subprocess.TimeoutExpired(
            cmd=["claude", "-p", "--model", "el-modelo"],
            timeout=1.0,
            output=CV_SINTETICO,
            stderr=CV_SINTETICO,
        )
    )


def _doble_de_error() -> CLIDoblado:
    """Y el otro: el CLI responde con código de salida y el prompt en el error estándar."""
    return CLIDoblado(
        fallo=subprocess.CalledProcessError(
            1, ["claude", "-p"], output=CV_SINTETICO, stderr=CV_SINTETICO
        )
    )


@pytest.mark.parametrize(
    "doblar",
    (_doble_de_exito, _doble_de_timeout, _doble_de_error),
    ids=("exito", "timeout", "error_del_cli"),
)
async def test_ninguna_linea_de_log_lleva_una_frase_de_ocho_palabras_del_cv(
    caplog: pytest.LogCaptureFixture,
    cli: Callable[..., CLIDoblado],
    doblar: Callable[[], CLIDoblado],
) -> None:
    """F12, D15, §5.5 · «ni cuerpo de la petición ni respuesta del modelo en logs».

    Los tres caminos, porque el único que no basta es el del éxito: el del timeout
    es el que la falla nombra —«es el que registra cuerpos por omisión»— y el del
    error del CLI trae el prompt de vuelta en el error estándar. Un adaptador que
    registre con cuidado al acertar y haga `logging.exception` al fallar pasa el
    caso del éxito y deja el CV de las ~680 personas de la demo en los logs de la
    plataforma, donde D15 no llega, el inventario de borrado de CA16 no lo ve y la
    retención de los logs sigue siendo **pregunta abierta** (F12, decide Priya).

    Las frases se sacan del **cuerpo pseudonimizado** y del CV crudo: lo que puede
    aparecer en un log es lo uno o lo otro, y las dos cosas son texto del CV. Que
    el cuerpo esté pseudonimizado no lo autoriza: D3 modificado permitió esa
    salida hacia un proveedor con retención cero y anexo firmado, tres condiciones
    que un archivo de log no cumple ninguna.

    El error tipado entra en el mismo control, y no por completismo: el motivo del
    trabajo lo escribe el bucle desde la excepción (`cola/ejecutor.py`), así que un
    mensaje con el CV dentro acaba en la columna `motivo` de `match_trabajos` y de
    ahí a cualquier log de operación.
    """
    puerta = adaptador()
    doble = cli(doblar())
    payload = payload_sintetico()
    frases = frases_de(payload.cv) | frases_de(CV_SINTETICO)
    assert frases, "la fixture no da ninguna frase de ocho palabras: el control sería vacío"

    caplog.set_level(logging.DEBUG)
    error: BaseException | None = None
    try:
        await puerta.real().puntuar(payload, IDIOMA_POR_OMISION)
    except puerta.error as fallo:
        error = fallo

    assert doble.llamadas == 1, "el adaptador no llegó a lanzar el proceso"
    if doble.fallo is not None:
        assert error is not None, "el fallo del CLI no salió como error tipado del proveedor"

    en_el_log = sorted(frase for frase in frases if frase in _texto_de_los_logs(caplog))
    assert en_el_log == [], (
        f"queda texto del CV en los logs de la plataforma: {en_el_log[:1]} (F12, D15, "
        "`docs/arquitectura.md` §5.5)"
    )
    if error is not None:
        en_el_error = sorted(frase for frase in frases if frase in normalizar(str(error)))
        assert en_el_error == [], (
            f"el error tipado lleva el CV en su mensaje: {en_el_error[:1]}. El bucle escribe el "
            "motivo del trabajo desde la excepción, así que acaba en `match_trabajos.motivo`"
        )

    assert _del_adaptador(caplog), (
        "el adaptador no registró nada en este camino: la prohibición de registrar cuerpos no "
        "está comprobando nada. F12 pide una línea por llamada —`request_id`, decisión, "
        "latencia y versiones— y CA7 necesita esa latencia"
    )


def _literales_de_clave(ruta: Path) -> list[str]:
    """Las cadenas de ese archivo que parecen una clave del proveedor."""
    hallados: list[str] = []
    for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        if (
            isinstance(nodo, ast.Constant)
            and isinstance(nodo.value, str)
            and any(nodo.value.startswith(prefijo) for prefijo in PREFIJOS_DE_CLAVE)
        ):
            hallados.append(f"{ruta.relative_to(RAIZ)}:{nodo.lineno}")
    return hallados


async def test_la_clave_del_proveedor_no_esta_en_el_repo_ni_sale_en_la_invocacion_ni_en_el_log(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    cli: Callable[..., CLIDoblado],
) -> None:
    """F19, criterio de terminado de PR-09 · «la clave solo en variable de entorno».

    F19 es severidad 5 («acceso de terceros a nuestra cuenta: gasto ajeno contra el
    techo de D12 y payloads de CV en una cuenta que no controlamos») y su
    mitigación es de costo cero: la clave solo en el entorno, nunca en los logs.
    `docs/fallas.md` la deja «sin test; control del repositorio», y eso cubre el
    repo —la protección de push de PR-01— pero no cubre el log ni la línea de
    órdenes, que es donde una clave acaba cuando alguien la pasa como argumento
    para salir del paso. Las tres mitades, aquí:

    1. **en `app/` no hay ningún literal que parezca una clave** del proveedor;
    2. **con una clave en el entorno, no aparece en `argv`, ni en el prompt, ni en
       ninguna línea de log.** `argv` importa tanto como el log: lo lee cualquier
       proceso de la máquina con `ps`;
    3. **y en este repo el adaptador no necesita clave ninguna** (N4): sin ninguna
       de las variables puestas, puntúa igual. Es lo que separa este repo del
       proyecto real del cliente, donde el adaptador sería el de la API con su
       clave en el entorno — y la razón por la que la CI de este repo no necesita
       ningún secreto para correr en verde.
    """
    puerta = adaptador()

    literales = [linea for ruta in sorted(APP.rglob("*.py")) for linea in _literales_de_clave(ruta)]
    assert literales == [], f"hay algo que parece una clave del proveedor en el repo: {literales}"

    for variable in VARIABLES_DE_CLAVE:
        monkeypatch.setenv(variable, CLAVE_FICTICIA)
    caplog.set_level(logging.DEBUG)
    con_clave = cli()

    await puerta.real().puntuar(payload_sintetico(), IDIOMA_POR_OMISION)

    invocacion = con_clave.ultima
    assert CLAVE_FICTICIA not in invocacion.linea, (
        "la clave viaja en la línea de órdenes del proceso: `ps` la muestra a cualquier proceso "
        "de la máquina (F19)"
    )
    assert CLAVE_FICTICIA not in invocacion.entrada, "la clave viaja dentro del prompt"
    assert CLAVE_FICTICIA not in _texto_de_los_logs(caplog), "la clave quedó en una línea de log"

    for variable in VARIABLES_DE_CLAVE:
        monkeypatch.delenv(variable, raising=False)
    sin_clave = cli()
    respuesta = await puerta.real().puntuar(payload_sintetico(), IDIOMA_POR_OMISION)
    assert sin_clave.llamadas == 1 and respuesta.score is not None, (
        "el adaptador de este repo exige una clave: la decisión N4 dice que aquí no hay clave de "
        "API y que el cliente real es el CLI por subproceso. Con esto rojo, la CI necesitaría un "
        "secreto para correr"
    )
