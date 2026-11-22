"""El guardia del CLI del proveedor, para **toda** la suite (PR-09, N4).

Este archivo cubre el hueco que la ronda de revisión de PR-09 llama **M4**, y
vive **fuera de `tests/match/`** a propósito: eso es justo lo que comprueba.

El doble prohibitivo de la costura del subproceso (`ningun_cli_de_verdad`) nació
en `tests/match/conftest.py`, así que cubría `tests/match` y nada más. Su propio
docstring dice que existe para que «el olvido de un doble en un test **cualquiera**
no pueda convertirse en un proceso `claude -p` lanzado desde la suite», y ese
«cualquiera» era media suite: `tests/e2e` corre con la costura real, levanta la
app de verdad y llama al bucle del ejecutor —`correr_el_ejecutor`—, que desde
PR-09 le pregunta a `proveedor_configurado()` qué proveedor usar. Y esa fábrica
lee **el entorno heredado de la shell que lanzó pytest**: con
`CRIBA_MATCH_PROVEEDOR=claude_cli` exportada, el humo del E2E lanzaba el CLI de
verdad con el CV de una fixture dentro.

Los CVs de las fixtures son sintéticos (D3 modificado, D15, F12), así que lo que
está en juego no es una fuga: es que **la suite dependa del entorno de quien la
corre**. Un control de privacidad que se apaga porque alguien exportó una
variable en su terminal no es un control, y la CI tiene que dar el mismo
resultado en la máquina de Víctor y en el runner.

Las dos mitades de la inmunidad, que son las dos de este test:

1. **la costura está doblada en todo el proceso**, no solo en `tests/match`: la
   fixture `autouse` vive en `tests/conftest.py`;
2. **el modo de proveedor de la suite es el MOCK**, fijado por `tests/conftest.py`
   igual que el interruptor global, y no heredado del entorno. El MOCK es el
   único proveedor que no sale de la red y el único que la CI usa
   (`docs/arquitectura.md` §2, N4).

Por qué es un test y no solo un arreglo del `conftest`: la fixture resuelve la
costura con `suppress(AssertionError)` —tiene que poder ser un no-op mientras el
adaptador no exista—, así que el día que la costura se renombre el guardia
desaparece **en silencio** y toda la suite sigue verde. Este test es su detector,
y no lanza nada para comprobarlo: mira qué hay instalado en la costura.
"""

from __future__ import annotations

from app.match.configuracion import MODO_MOCK, VARIABLE_DE_MODO, ajustes_match
from tests.dobles.cli import CLIDoblado, adaptador


def test_ningun_test_de_la_suite_puede_lanzar_el_cli_del_proveedor_de_verdad() -> None:
    """F12, N4, `docs/arquitectura.md` §2 · la suite no depende del entorno del runner.

    Este test está en `tests/` y no en `tests/match/` porque lo que asercia es el
    **alcance** del guardia. Si vuelve a `tests/match/conftest.py`, este test se
    pone rojo: es la única forma de que el alcance se note.
    """
    puerta = adaptador()

    assert isinstance(puerta.costura, CLIDoblado), (
        f"fuera de `tests/match` la costura del subproceso es {puerta.costura!r}: un test que "
        "olvide su doble —o el bucle del ejecutor del E2E, que pregunta por el proveedor "
        "configurado— lanza el CLI del proveedor de verdad. El doble prohibitivo tiene que "
        "estar puesto por omisión en TODA la suite, o sea en `tests/conftest.py`"
    )
    assert puerta.costura.prohibido, (
        "la costura está doblada pero el doble **permite** la llamada: el guardia por omisión "
        "tiene que fallar el test, no devolver una respuesta de mentira"
    )
    assert puerta.costura.llamadas == 0, "algo lanzó la costura antes de este test"

    assert ajustes_match().modo_proveedor == MODO_MOCK, (
        f"la suite corre con el modo de proveedor que traiga el entorno de quien la lanza "
        f"({VARIABLE_DE_MODO}={ajustes_match().modo_proveedor!r}). `tests/conftest.py` fija el "
        "interruptor global para toda la suite y tiene que fijar también el modo: el MOCK es el "
        "único proveedor que no sale de la red y el único que la CI usa (N4)"
    )
