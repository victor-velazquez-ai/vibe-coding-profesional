"""El arnés de evals · las dos formas de enseñar el informe.

`test_pass_k.py` fija el **conteo** —pass^1, pass^k y el total— y nada fija cómo se
enseña (**hallazgo I1**): ni la tabla de la terminal (`lineas`) ni el JSON que se
guarda en `evals/resultados/` (`como_json`), que son las dos cosas que alguien lee
de verdad. Los tres criterios de aquí:

1. la tabla trae una línea por caso con **las cuatro dimensiones** y los motivos del
   intento que falló: «pass^1 = 0/3» sin ellas obliga a abrir el JSON para saber si
   falló la banda o una mención prohibida;
2. el JSON guardado trae **los k intentos de cada caso con sus motivos**, porque la
   pregunta que se le hace a un informe de hace dos semanas es «¿qué contestó el
   modelo en el intento que falló?»;
3. el JSON guardado **no lleva el texto de ninguna respuesta ni de ningún CV**. Hoy
   los casos son sintéticos, pero el formato es el que mañana se usará con el
   conjunto dorado de CA14 (PR-17), que son datos de candidatos reales de Northstar
   (D3 modificado, D15, F12).

Las calificaciones se construyen con el `calificar` de verdad, igual que en
`test_pass_k.py`: así el informe y el calificador no pueden desalinearse.
"""

from __future__ import annotations

import json

from evals.calificacion import calificar
from evals.informe import como_json, lineas, resumir_caso, totales
from tests.dobles.cli import frases_de, normalizar
from tests.evals.conftest import caso, respuesta, respuesta_ideal

# Las claves que el informe guardado declara por intento. La lista entera y no un
# `in`: una dimensión que desapareciera del JSON dejaría el informe sin la columna
# por la que se busca el fallo, y el total seguiría cuadrando.
CLAVES_DEL_INTENTO = {
    "banda",
    "banda_ok",
    "menciones_ok",
    "invariante_ok",
    "inyeccion_ok",
    "paso",
    "motivos",
}

RAZON_DE_QA = "Punto considerado: playwright"


def _fs26_con_el_invariante_roto(score: int, score_del_gemelo: int):
    """fs-26 calificado contra su gemelo, con las dos bandas en «alto».

    Lo único que puede fallar es el invariante, que es lo que hace legible lo que
    el informe tiene que enseñar."""
    return calificar(
        caso("fs-26"),
        respuesta(score, RAZON_DE_QA),
        gemela=respuesta(score_del_gemelo, RAZON_DE_QA),
    )


def test_la_tabla_del_informe_trae_una_linea_por_caso_con_sus_cuatro_dimensiones() -> None:
    """Criterio 1 · lo que se lee en la terminal.

    fs-01 no declara gemelo ni bandas prohibidas, así que sus dos últimas
    dimensiones se enseñan como «—» y no como «no»: una dimensión que el caso no
    declara no se calificó, y contarla verde sería decir once invariantes donde solo
    hay tres pares. fs-26 falla por el invariante, y el motivo va debajo de su
    línea."""
    fs01 = caso("fs-01")
    resultados = [
        resumir_caso("fs-01", [calificar(fs01, respuesta_ideal(fs01))]),
        resumir_caso("fs-26", [_fs26_con_el_invariante_roto(77, 88)]),
    ]

    filas = lineas(resultados, totales(resultados))

    cabecera = filas[0].split()
    assert cabecera[:2] == ["caso", "banda"]
    assert {"bnd", "men", "inv", "iny"} <= set(cabecera)

    fila01 = next(fila for fila in filas if fila.startswith("fs-01"))
    assert "alto" in fila01 and "si" in fila01
    assert "—" in fila01, "fs-01 no declara invariante ni banda prohibida"

    fila26 = next(fila for fila in filas if fila.startswith("fs-26"))
    assert "NO" in fila26
    assert any("fs-25" in fila and "invariante" in fila for fila in filas), (
        "el motivo del caso que falló no aparece debajo de su línea"
    )

    total = filas[-1]
    assert total.startswith("TOTAL")
    assert "2 casos" in total and "1/2" in total and "50%" in total


def test_el_informe_guardado_trae_los_k_intentos_de_cada_caso_con_sus_motivos() -> None:
    """Criterio 2 · el JSON de `evals/resultados/`, con la cabecera de la pasada.

    Dos intentos del mismo caso, uno bueno y uno roto: el informe tiene que
    distinguirlos, no promediarlos. Y tiene que ser serializable tal cual, porque
    es lo que `__main__.guardar` escribe."""
    resultados = [
        resumir_caso(
            "fs-26",
            [_fs26_con_el_invariante_roto(85, 85), _fs26_con_el_invariante_roto(85, 70)],
        )
    ]
    total = totales(resultados, costo_usd=0.0165, modelos=["claude-haiku-4-5-20251001"])

    informe = como_json(resultados, total, cabecera={"proveedor": "claude", "k": 2})

    assert informe["proveedor"] == "claude"
    assert informe["k"] == 2
    assert informe["total"] == {
        "casos": 1,
        "intentos": 2,
        "aciertos": 1,
        "pass_1": 0.5,
        "pass_k": 0.0,
        "costo_usd": 0.0165,
        "modelos": ["claude-haiku-4-5-20251001"],
    }

    guardado = informe["casos"][0]
    assert (guardado["caso_id"], guardado["k"], guardado["aciertos"]) == ("fs-26", 2, 1)
    assert guardado["pass_k"] is False
    bueno, roto = guardado["intentos"]
    assert set(bueno) == CLAVES_DEL_INTENTO
    assert (bueno["paso"], bueno["invariante_ok"], bueno["motivos"]) == (True, True, [])
    assert roto["paso"] is False and roto["invariante_ok"] is False
    assert any("fs-25" in motivo for motivo in roto["motivos"]), roto["motivos"]
    json.dumps(informe, ensure_ascii=False)


def test_el_informe_guardado_no_lleva_el_texto_de_ninguna_respuesta_ni_de_ningun_cv() -> None:
    """Criterio 3 · el formato es el que mañana lleva datos del cliente (CA14).

    La respuesta de este intento trae dentro el CV entero del caso, que es lo peor
    que un modelo puede contestar (y pasa: un modelo que repite el texto que se le
    dio). Ni ese texto ni la razón del modelo pueden acabar en el archivo que se
    guarda en disco y que alguien adjunta a un informe de calidad. Lo que sí lleva
    son los **motivos**, que los escribe el calificador citando el término del
    archivo de casos, nunca lo que el modelo respondió."""
    fs01 = caso("fs-01")
    razon_larga = "La candidata encaja porque el equipo de plataforma usa el mismo stack"
    calificacion = calificar(
        fs01,
        respuesta(
            85,
            "Punto considerado: fastapi",
            "Punto considerado: postgres",
            razon_larga,
            # Lo peor que un modelo puede contestar, y pasa: repetir el texto que
            # se le dio. Si el informe copiara las razones, el CV entero acabaría
            # en un archivo de `evals/resultados/`.
            fs01["cv"],
        ),
    )
    resultados = [resumir_caso("fs-01", [calificacion])]

    informe = como_json(resultados, totales(resultados), cabecera={"proveedor": "claude"})
    crudo = normalizar(json.dumps(informe, ensure_ascii=False))

    assert razon_larga not in crudo, "el informe guardado lleva una razón del modelo dentro"
    filtradas = [frase for frase in frases_de(fs01["cv"]) if frase in crudo]
    assert filtradas == [], f"el informe guardado lleva texto del CV: {filtradas}"
    assert "fs-01" in crudo, "y aun así el informe identifica el caso"
