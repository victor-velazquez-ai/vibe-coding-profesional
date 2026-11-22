"""El arnés de evals · la línea de órdenes y el código de salida.

`uv run python -m evals --proveedor mock|claude --k 3` es la forma en que alguien
usa el arnés, y nada de ella estaba fijado (**hallazgo I1**): el código de salida lo
promete el README y, según el propio cuerpo del paso, se «midió a mano». Los seis
criterios de aquí:

1. el código de salida es **1** cuando algún intento no llegó a tener respuesta: eso
   es el **camino de producción roto**, que es lo que `poe evals` vigila con el MOCK
   en segundos y sin red;
2. y es **0** aunque los casos no pasen: un caso que falla es un dato de calidad del
   modelo —el informe está para eso— y no un repo roto. Es la distinción que separa
   este arnés de un test, y la que hace que se pueda correr con el proveedor real
   sin que la CI se ponga roja por la varianza de un modelo;
3. `--k 0` se rechaza: pass^k no significa nada con cero intentos;
4. el informe se guarda en `evals/resultados/` con fecha, proveedor y k en el
   nombre, y `--sin-guardar` no escribe nada;
5. el archivo que queda en disco no lleva el CV ni lo que el modelo respondió
   (F12, D15), que es la mitad del formato que importa de cara a CA14;
6. las razones se piden en el idioma de los **casos** y no en el de producción.

El directorio de resultados se desvía a `tmp_path`: un test no escribe en el repo.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.match.configuracion import IDIOMA_POR_OMISION
from app.match.proveedor.cliente import instrucciones
from app.match.proveedor.mock import RAZONES_DEL_MOCK
from evals import __main__ as principal
from evals.__main__ import argumentos, main
from evals.corredor import IDIOMA_DE_LOS_CASOS
from tests.dobles.cli import frases_de, normalizar
from tests.evals.conftest import caso
from tests.evals.doble_del_camino import (
    RAZONES_DE_FS01,
    PonerGuion,
    camino_doblado,
    respuesta_del_cli,
)


@pytest.fixture
def camino(monkeypatch: pytest.MonkeyPatch) -> Iterator[PonerGuion]:
    """El arnés con la única puerta del proveedor doblada (`camino_doblado`).

    Los tests que corren con el MOCK la piden igual y no ponen ningún guion: lo que
    necesitan de ella es que el modo del proveedor quede como estaba."""
    with camino_doblado(monkeypatch) as poner:
        yield poner


def test_el_codigo_de_salida_es_uno_cuando_un_intento_no_llego_a_tener_respuesta(
    camino: PonerGuion,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Criterio 1 · lo que sí es un repo roto.

    El único intento del único caso pedido termina en un `ErrorDelProveedor`, así
    que no hay nada que medir: el arnés sale con 1 y dice en el error estándar
    cuántos intentos se quedaron sin respuesta y cuál fue el primero. Con 0, `poe
    evals` daría por bueno un camino de producción que no devuelve nada."""
    camino({"fs-01": [subprocess.TimeoutExpired(cmd="claude", timeout=120)]})

    codigo = main(["--proveedor", "claude", "--k", "1", "--casos", "fs-01", "--sin-guardar"])

    assert codigo == 1
    error = capsys.readouterr().err
    assert "no llegaron a tener respuesta" in error
    assert "fs-01" in error


def test_el_codigo_de_salida_es_cero_aunque_los_casos_no_pasen(
    camino: PonerGuion,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Criterio 2 · un caso que no pasa no es un fallo del arnés.

    Con el MOCK, fs-09 falla por definición: el MOCK devuelve un 70 fijo y fs-09 es
    el caso de CA13, que espera «sin score». El informe lo enseña como lo que es
    —`NO` en pass^k— y el arnés sale con 0, porque el camino funcionó."""
    codigo = main(["--proveedor", "mock", "--k", "1", "--casos", "fs-09", "--sin-guardar"])

    assert codigo == 0
    salida = capsys.readouterr().out
    assert "fs-09" in salida
    assert "NO" in salida, "el informe tiene que decir que el caso no pasó"


def test_la_linea_de_ordenes_rechaza_un_k_menor_que_uno(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Criterio 3 · pass^k no significa nada con cero intentos.

    Sin este rechazo, `--k 0` da una pasada de cero llamadas con un informe de
    ceros y un pass^k del 0 %, que es indistinguible de doce casos que fallaron."""
    with pytest.raises(SystemExit) as salida:
        argumentos(["--k", "0"])

    assert salida.value.code == 2
    assert "--k" in capsys.readouterr().err


def test_el_informe_se_guarda_con_fecha_proveedor_y_k_y_sin_guardar_no_escribe_nada(
    camino: PonerGuion,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Criterio 4 · el informe de la pasada queda en disco, y solo si se pide.

    El nombre lleva proveedor y k porque una pasada con el MOCK y otra con el
    modelo real no se pueden confundir dos semanas después, y la cabecera lleva
    además el idioma, los casos pedidos y las **sustituciones** del payload (PR-08):
    cuánto se le quitó a cada CV antes de salir de Criba, que es la señal de F1 —
    limpiar por patrón puede quitar de más y degradar el texto que decide el
    score—."""
    resultados = tmp_path / "resultados"
    monkeypatch.setattr(principal, "RUTA_DE_RESULTADOS", resultados)

    assert main(["--proveedor", "mock", "--k", "1", "--casos", "fs-01"]) == 0

    guardados = list(resultados.glob("*.json"))
    assert len(guardados) == 1
    assert "mock" in guardados[0].name and "k1" in guardados[0].name

    informe = json.loads(guardados[0].read_text(encoding="utf-8"))
    assert informe["proveedor"] == "mock"
    assert informe["k"] == 1
    assert informe["casos_pedidos"] == ["fs-01"]
    assert informe["sustituciones"] == {"fs-01": informe["sustituciones"]["fs-01"]}
    assert "fecha" in informe and "idioma" in informe

    assert main(["--proveedor", "mock", "--k", "1", "--casos", "fs-01", "--sin-guardar"]) == 0
    assert len(list(resultados.glob("*.json"))) == 1, "--sin-guardar escribió un informe"


def test_el_informe_que_queda_en_disco_no_lleva_el_cv_ni_lo_que_el_modelo_respondio(
    camino: PonerGuion,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Criterio 5 · lo que se escribe en disco, de punta a punta (F12, D15).

    `test_informe_de_salida.py` fija que `como_json` no copia el texto; esto lo
    comprueba sobre el archivo que de verdad queda, cabecera incluida —que es la
    parte que `como_json` no construye— y con una pasada entera por el camino del
    MOCK. El día que alguien añada «y las razones, para poder revisarlas», el
    archivo de `evals/resultados/` pasa a llevar texto de un CV de Northstar en
    cuanto esto corra con el conjunto dorado de CA14 (PR-17), y nadie lo mira.

    Lo que sí tiene que llevar son los **motivos**: sin ellos el informe guardado no
    sirve para nada, y un archivo vacío pasaría este test sin decir nada."""
    resultados = tmp_path / "resultados"
    monkeypatch.setattr(principal, "RUTA_DE_RESULTADOS", resultados)

    assert main(["--proveedor", "mock", "--k", "1", "--casos", "fs-01", "fs-26"]) == 0

    guardado = next(iter(resultados.glob("*.json")))
    crudo = normalizar(guardado.read_text(encoding="utf-8"))

    assert "no menciona ninguna de" in crudo, "el informe guardado no trae los motivos"
    for razon in RAZONES_DEL_MOCK:
        assert razon not in crudo, "el informe guardado lleva lo que el modelo respondió"
    for ident in ("fs-01", "fs-26", "fs-25"):
        filtradas = [frase for frase in frases_de(caso(ident)["cv"]) if frase in crudo]
        assert filtradas == [], f"el informe guardado lleva texto del CV de {ident}: {filtradas}"


def test_el_arnes_pide_las_razones_en_el_idioma_de_los_casos_y_no_en_el_de_produccion(
    camino: PonerGuion,
) -> None:
    """Criterio 6 · el idioma por omisión del arnés es el del archivo de casos.

    Los 12 casos están escritos en español y sus términos exigidos también
    («ingles», «requisit», «conciliacion»), así que con el `'en'` por omisión de
    producción (`IDIOMA_POR_OMISION`, el supuesto de D20) ningún caso podría
    acertar las menciones y el informe mediría el idioma en vez de la calidad. No
    es una decisión del arnés: la fija el archivo, y `--idioma` la cambia."""
    doble = camino({"fs-01": [respuesta_del_cli(85, *RAZONES_DE_FS01)]})
    assert IDIOMA_DE_LOS_CASOS != IDIOMA_POR_OMISION, "si fueran el mismo, esto no protegería nada"

    assert main(["--proveedor", "claude", "--k", "1", "--casos", "fs-01", "--sin-guardar"]) == 0

    pedido = doble.argumentos[0]
    assert instrucciones(IDIOMA_DE_LOS_CASOS) in pedido
    assert instrucciones(IDIOMA_POR_OMISION) not in pedido
