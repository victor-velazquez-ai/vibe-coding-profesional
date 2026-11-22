"""El arnés de evals · el informe por caso: pass^1, pass^k y el total.

El arnés corre cada caso **k veces** (`--k 3`) porque un modelo no es
determinista, y las dos cifras dicen cosas distintas:

- **pass^1** = aciertos / k. Es la probabilidad de acertar una vez. Con 2 de 3, el
  caso acierta «casi siempre»;
- **pass^k** = los **k** intentos bien. Es lo único que vale para un criterio que
  en producción se cumple en cada llamada, y es la cifra que un promedio esconde:
  tres casos con 2/3 dan un pass^1 del 67 % y un pass^k de cero.

Los intentos de estos tests son **respuestas del proveedor fabricadas a mano**,
calificadas por el mismo `calificar` que fija `test_calificacion.py`: el conteo se
prueba sobre calificaciones de verdad y no sobre booleanos sueltos, que es lo que
hace que el informe y el calificador no puedan desalinearse.

**Lo que no fija este archivo:** el costo y el modelo que reporta el proveedor
—los pone el corredor, no el calificador— y el JSON de `evals/resultados/`.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.evals.conftest import calificador, caso, informador, respuesta

# fs-01 es un «alto» con menciones de fastapi y postgres; fs-03 es un «bajo» con
# menciones de kubernetes y terraform. En los dos, el acierto y el fallo se
# diferencian **solo** en el score, para que lo que mueva el conteo sea el
# intento y no el texto.
ACIERTOS = {
    "fs-01": (85, "Punto considerado: fastapi", "Punto considerado: postgres"),
    "fs-03": (20, "Punto considerado: kubernetes", "Punto considerado: terraform"),
}
FALLOS = {
    "fs-01": (30, "Punto considerado: fastapi", "Punto considerado: postgres"),
    "fs-03": (80, "Punto considerado: kubernetes", "Punto considerado: terraform"),
}


def calificaciones(caso_id: str, resultados: str) -> list[Any]:
    """Las k calificaciones de un caso, escritas como `"aaf"`: dos aciertos y un fallo."""
    cal = calificador()
    un_caso = caso(caso_id)
    intentos = []
    for letra in resultados:
        score, *razones = ACIERTOS[caso_id] if letra == "a" else FALLOS[caso_id]
        intentos.append(cal.calificar(un_caso, respuesta(score, *razones)))
    return intentos


def test_los_intentos_fabricados_son_aciertos_y_fallos_de_verdad() -> None:
    """Antes de contar nada: que `a` pase y `f` no.

    Sin esto, un conteo verde no diría nada —tres «aciertos» que en realidad
    fallan dan pass^k cero y el test de abajo lo leería como correcto— y el error
    estaría en este archivo, no en el arnés."""
    for caso_id in ("fs-01", "fs-03"):
        acierto, fallo = calificaciones(caso_id, "af")
        assert acierto.paso is True, caso_id
        assert fallo.paso is False, caso_id


def test_pass_1_es_la_fraccion_de_intentos_que_aciertan() -> None:
    """Dos de tres son 2/3, no «2» ni «dos de tres».

    Es una fracción porque el total la suma: el informe de 12 casos tiene que
    poder promediarla."""
    inf = informador()
    resultado = inf.resumir_caso("fs-01", calificaciones("fs-01", "afa"))

    assert resultado.caso_id == "fs-01"
    assert resultado.k == 3
    assert resultado.aciertos == 2
    assert resultado.pass_1 == pytest.approx(2 / 3)


def test_pass_k_es_verdadero_solo_cuando_los_k_intentos_aciertan() -> None:
    """Tres de tres: pass^1 = 1 y pass^k verdadero."""
    inf = informador()
    resultado = inf.resumir_caso("fs-01", calificaciones("fs-01", "aaa"))

    assert resultado.aciertos == 3
    assert resultado.pass_1 == pytest.approx(1.0)
    assert resultado.pass_k is True


def test_un_solo_fallo_en_los_k_intentos_tumba_pass_k_y_no_pass_1() -> None:
    """La otra dirección, que es la razón de ser de las dos cifras.

    Un caso que acierta dos de tres sigue teniendo un pass^1 alto y un pass^k
    falso: para un criterio que se cumple en cada llamada —no mencionar la edad,
    no obedecer al CV— eso es un fallo, y el informe no lo puede promediar hasta
    hacerlo desaparecer."""
    inf = informador()
    resultado = inf.resumir_caso("fs-01", calificaciones("fs-01", "aaf"))

    assert resultado.pass_1 == pytest.approx(2 / 3)
    assert resultado.pass_k is False


def test_el_total_suma_los_intentos_de_todos_los_casos_y_cuenta_los_que_pasan_enteros() -> None:
    """El total del informe, con dos casos: fs-01 con 3 de 3 y fs-03 con 1 de 3.

    pass^1 total = 4 intentos buenos de 6; pass^k total = 1 caso entero de 2. Las
    dos son fracciones, como las del caso, y `casos` e `intentos` quedan en el
    informe para que el 50 % no se lea sin saber que son dos casos."""
    inf = informador()
    resultados = [
        inf.resumir_caso("fs-01", calificaciones("fs-01", "aaa")),
        inf.resumir_caso("fs-03", calificaciones("fs-03", "aff")),
    ]

    total = inf.totales(resultados)
    assert total.casos == 2
    assert total.intentos == 6
    assert total.aciertos == 4
    assert total.pass_1 == pytest.approx(4 / 6)
    assert total.pass_k == pytest.approx(0.5)
