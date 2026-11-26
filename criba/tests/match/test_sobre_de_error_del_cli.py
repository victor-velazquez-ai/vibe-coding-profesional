"""CA13 · el sobre de error **real** del CLI, de punta a punta (incidente 001).

El camino del incidente completo y sin recortes: el CLI doblado devuelve **el
sobre que `claude -p --output-format json` dio de verdad** al pasarse del tope de
tokens de salida, con el **código de salida 1** que lo acompaña → el adaptador
(`app/match/proveedor/cliente.py`) → el bucle del ejecutor
(`app/match/cola/ejecutor.py`) → la vacante que la reclutadora abre. Es el primer
test de la suite que ejerce el sobre de error real del CLI (issue #11): hasta hoy
`tests/match/test_salida_del_cli.py` ejercía sobres **construidos a mano** —y
ninguno con código de salida distinto de 0— y `tests/match/test_cliente_proveedor.py`
dobla el fallo del subproceso sin que la salida del proceso lleve nada dentro.

El sobre está en `tests/fixtures/salida_cli_error_tope_de_tokens.json` y es la
salida literal del CLI, con una sola propiedad que importa comprobar antes de
usarla: **no lleva ningún dato de candidato** (D3 modificado, D15, F12). Lo que
lleva es el texto del error del propio CLI, su contabilidad de tokens y de costo,
y dos identificadores puestos a cero. Por eso puede vivir en el repo.

**Las dos causas del incidente, y por qué este test solo fija una** (`RUNBOOK.md`
§3: «dos causas en un arreglo son dos arreglos»):

- la causa de que las llamadas fallaran es de **operación**: el tope
  `CLAUDE_CODE_MAX_OUTPUT_TOKENS=800` que `staging/staging.env:66-67` añadió el
  21-nov y que `_entorno()` hereda al subproceso (`cliente.py:215-219`). Es la
  falla **F7** del mapa (`docs/fallas.md:74`), **sin test por decisión escrita**
  —«hasta que se decida el tope de tokens»— y su pregunta abierta la deciden
  Víctor y Tomás (`docs/fallas.md:140`, pregunta 7 de `PLAN.md` §9). Este archivo
  **no** asercia nada sobre el tope ni sobre el entorno del hijo: eso no lo decide
  el escritor de tests;
- la causa de que cada fallo se viera como un **cero** es de código y es CA13
  (`SPEC.md:91-93`). Esa es la que este test fija, con la forma exacta en que el
  fallo llegó: código de salida 1 → `subprocess.CalledProcessError` →
  `ErrorDelProveedor` (`cliente.py:489-493`, la `decision=codigo_de_salida` que
  las 7 líneas del log de staging registran) → el camino de excepción de
  `una_pasada` → `score=0` con `estado="listo"`.

Qué hizo el tope con la respuesta, dicho una vez para que no se confunda con la
forma del sobre: el CLI **sí** escribió su sobre en la salida estándar —con
`is_error: true` y el texto de su error en `result`— y **además** terminó con
código 1, así que `subprocess.run(check=True)` levanta su excepción con ese sobre
dentro (`CalledProcessError.output`) y el adaptador no llega a leerlo. Las dos
mitades se aserician: ni sale un score de ahí, ni se copia nada de ese sobre al
motivo de la fila o a la línea de log (F12, D15).

Lo que este test **no** decide, igual que `test_fallo_proveedor.py`: si el par
queda sin fila o con una fila `score=None` + `estado="sin_score"` + motivo. Las
dos cumplen CA13 y lo reparte la tabla de estados de `PLAN.md` PR-11 por causa
—ésta es transitoria: el fallo es nuestro y del proveedor, no del candidato—.

Ningún test de este archivo lanza el CLI de verdad.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.match.cola.ejecutor import LOG_DEL_EJECUTOR, una_pasada
from app.match.cola.trabajos import encolar
from tests.dobles.cli import CLIDoblado, adaptador
from tests.match.conftest import EmpresaDePrueba, Entrar, repo_de
from tests.match.test_fallo_proveedor import numeros_en_la_vista

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
SOBRE_REAL = FIXTURES / "salida_cli_error_tope_de_tokens.json"

# El código de salida con el que el CLI terminó en las 7 llamadas fallidas del
# incidente. Es lo que hace que el sobre no se lea: `check=True` en `correr_cli`
# levanta `CalledProcessError` antes de que nadie mire la salida estándar.
CODIGO_DE_SALIDA = 1

# El trozo del `result` del sobre que identifica la causa de operación (F7). Si la
# fixture deja de traerlo, este archivo ya no está ejerciendo el sobre del
# incidente, sino otro.
ERROR_DEL_TOPE = "exceeded the 800 output token maximum"

# Trozos del sobre que **no pueden aparecer** en el motivo de la fila ni en la
# línea de log del ejecutor: el texto del error del proveedor, el nombre de la
# variable de operación, el costo, el identificador de sesión y el modelo
# reportado. Es la regla de F12 y de D15 aplicada a lo único que el camino de
# excepción deja escrito.
PIEZAS_DEL_SOBRE = (
    "API Error",
    ERROR_DEL_TOPE,
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS",
    "0.0487463",
    "00000000-0000-0000-0000-000000000000",
)


def sobre_real() -> str:
    """La salida literal del CLI, leída del archivo y no copiada al test."""
    return SOBRE_REAL.read_text(encoding="utf-8")


def _fallo_del_subproceso() -> subprocess.CalledProcessError:
    """La excepción **cruda** que `subprocess.run(check=True)` levanta con ese
    sobre en la salida estándar y código 1.

    `cmd` va recortado a propósito: el de verdad lleva `argv` completo —con
    `--system-prompt` y el `--json-schema` dentro— y copiarlo a una fixture sería
    escribir el prompt en el repo. Que el adaptador no cite ni el `cmd` ni el
    `output` es parte de lo que este test asercia.
    """
    return subprocess.CalledProcessError(
        returncode=CODIGO_DE_SALIDA,
        cmd=("claude", "-p", "--output-format", "json"),
        output=sobre_real(),
        stderr="",
    )


def test_la_fixture_es_el_sobre_de_error_del_cli_y_no_lleva_datos_de_candidato() -> None:
    """La premisa del archivo, aserciada antes de usarla (D3 modificado, D15, F12).

    Si alguien recorta la fixture o la sustituye por un sobre de éxito, el rojo
    tiene que decirlo **aquí** y no en el test de punta a punta, que hablaría de
    una forma que el CLI no devolvió. Y la mitad de privacidad: lo que entra al
    repo es la contabilidad del CLI y su propio mensaje de error, nunca un CV.
    """
    datos = json.loads(sobre_real())
    assert datos["is_error"] is True, "el sobre de la fixture no es el de un error del CLI"
    assert datos["subtype"] == "success", (
        "el sobre real dice `subtype: success` con `is_error: true` a la vez, que es justo lo "
        "que hace que un adaptador descuidado lea un fallo como respuesta"
    )
    assert ERROR_DEL_TOPE in datos["result"], "la fixture ya no es la del tope de tokens (F7)"
    assert datos["result"].startswith("API Error"), "el `result` no es el error del propio CLI"
    # El sobre no trae respuesta del modelo: ni `structured_output`, ni score.
    assert "structured_output" not in datos
    assert "score" not in sobre_real()


async def test_el_sobre_de_error_real_del_cli_no_deja_ni_un_cero_en_la_vacante(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    modo: Callable[..., None],
    cli: Callable[..., CLIDoblado],
    entrar: Entrar,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """CA13 · el camino del incidente 001, de `claude -p` a la vista de la vacante.

    Es el único test de la suite que recorre las tres capas con la salida real del
    proveedor: el **adaptador configurado** —no un doble del proveedor inyectado
    por el test, que es lo que hace `test_fallo_proveedor.py`—, el bucle y la
    vista. El modo se fija por variable de entorno, que es como se elige el
    proveedor en producción (`cliente.py::proveedor_configurado`), y la costura
    doblada es la única puerta por la que se lanza un proceso.

    Cuatro cosas:

    1. el adaptador emite **una** invocación y la convierte en un error tipado;
    2. el trabajo queda en `error` con su motivo (el de la cola, no uno que se le
       muestre al candidato);
    3. **no queda ninguna fila de score para ese par**: ni un 0, ni razones
       vacías. Hoy queda `score=0` con `estado="listo"` y la razón «No se pudo
       evaluar automáticamente.» —`ejecutor.py:103-112` y `match_repo.py:267`—,
       que es el cero falso que la reclutadora de Northstar vio en 7 pares;
    4. nada del sobre llega al motivo de la fila ni a la línea de log del cierre
       (F12, D15, `ejecutor.py:122-145`).

    Y la de siempre (CA1, el requisito número uno): Meridian —sin anexo, así que
    su cola está vacía por D7— no tiene ninguna fila de score ni ve la vacante de
    Northstar. El cero falso fue de una sola empresa y así tiene que seguir.
    """
    puerta = adaptador()
    modo(puerta.modo_cli)
    doble = cli(CLIDoblado(salida=sobre_real(), fallo=_fallo_del_subproceso()))
    encolar(sesion, northstar.vacante.id, northstar.candidato.id)

    with caplog.at_level(logging.INFO, logger=LOG_DEL_EJECUTOR):
        # Sin `proveedor`: el que corre es el que dice la configuración, que es el
        # camino de producción y el del incidente.
        assert await una_pasada(sesion) == 1, "el bucle no cerró el trabajo"

    assert doble.llamadas == 1, (
        f"el adaptador configurado lanzó {doble.llamadas} invocaciones del CLI: el modo "
        f"{puerta.modo_cli!r} no llegó al bucle y este test no está ejerciendo el camino real"
    )

    repo = repo_de(sesion, northstar)
    trabajos = repo.trabajos()
    assert [t.estado for t in trabajos] == ["error"], "la cola no se cerró en `error`"
    motivo = trabajos[0].motivo or ""
    assert motivo, "el trabajo quedó en error sin motivo (CA13: el motivo es la otra mitad)"

    assert repo.scores() == [], (
        "el código de salida 1 del CLI acabó en una fila de score "
        f"{[(s.score, s.estado, s.razones, s.motivo_sin_score) for s in repo.scores()]}. Es el "
        "cero falso del incidente 001: el sobre real del proveedor no trae ningún score —trae "
        "su propio error— y CA13 dice que o hay score, o hay «sin score» con su motivo, nunca "
        "un cero en lugar de un score (F8, `docs/fallas.md:75`)"
    )

    lineas = [r.getMessage() for r in caplog.records if r.name == LOG_DEL_EJECUTOR]
    assert lineas, "el ejecutor no registró el cierre del trabajo"
    escrito = "\n".join((motivo, *lineas))
    for pieza in PIEZAS_DEL_SOBRE:
        assert pieza not in escrito, (
            f"el camino de excepción copió «{pieza}» del sobre del CLI al motivo de la fila o a "
            "la línea de log: por ahí sale el prompt y con él el CV (F12, D15)"
        )

    vista = entrar(northstar.reclutador).get(f"/vacantes/{northstar.vacante.id}")
    assert vista.status_code == 200, "el fallo del proveedor rompió la vista de la vacante (CA6)"
    assert northstar.candidato.correo in vista.text, "el candidato desapareció de su vacante"
    assert numeros_en_la_vista(vista.text) == [], (
        f"la reclutadora ve {numeros_en_la_vista(vista.text)} en la celda de score de un "
        "candidato cuya llamada terminó con código 1: es el 0 del incidente 001 (CA13)"
    )

    otra = repo_de(sesion, meridian)
    assert (otra.scores(), otra.trabajos()) == ([], []), "algo del fallo cruzó a la otra empresa"
    de_meridian = entrar(meridian.reclutador)
    for ruta in (
        f"/vacantes/{northstar.vacante.id}",
        f"/match/vacantes/{northstar.vacante.id}/lista",
    ):
        respuesta = de_meridian.get(ruta)
        assert respuesta.status_code == 404, (
            f"{ruta} con sesión de Meridian: {respuesta.status_code}"
        )
        assert northstar.candidato.correo not in respuesta.text
