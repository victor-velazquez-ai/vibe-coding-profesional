"""`uv run python -m evals --proveedor mock|claude --k 3`: corre el arnés e informa.

Este archivo no decide nada de calidad: arma la invocación, llama a `corredor.py`,
enseña el informe de `informe.py` y lo guarda en `evals/resultados/`.

**El código de salida.** Es 0 aunque los casos fallen, y 1 solo si **el camino**
falló (algún intento sin respuesta, `ErrorDelProveedor`). La razón es la que separa
este arnés de un test: un caso que no pasa es un dato de calidad del modelo —el
informe está para eso— y no un repo roto. Lo que sí es un repo roto es que el
camino de producción no devuelva nada, y eso es lo que `poe evals` vigila con el
MOCK, en segundos y sin red.

**Con el MOCK los casos fallan, y está bien.** El MOCK devuelve un score fijo de 70
y tres razones sintéticas que no hablan de ningún caso (`proveedor/mock.py`): no es
una medida de calidad y nunca lo fue. Lo que `poe evals` comprueba es que el camino
—pseudonimizador → fábrica de proveedor → adaptador → calificación— funciona de
punta a punta. La calidad se mide con `--proveedor claude`, que cuesta dinero y la
CI no corre (`docs/arquitectura.md` §2, D12).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime

from evals.casos import RUTA_DE_RESULTADOS
from evals.corredor import IDIOMA_DE_LOS_CASOS, MODOS, Pasada, correr
from evals.informe import como_json, lineas

K_POR_OMISION = 3


def _salida_en_utf8() -> None:
    """Las dos salidas en UTF-8, pase lo que pase con la consola.

    Windows le da a un proceso con la salida redirigida la página de códigos del
    sistema (cp1252), y un `print` con «·» o «»» ahí es un `UnicodeEncodeError`:
    la herramienta se caería al imprimir el informe, después de haber pagado las
    llamadas. `errors="replace"` porque un carácter que la consola no sabe pintar
    no puede tirar una pasada de 11 minutos. Es la misma línea que
    `.claude/hooks/terminado.py` tiene arriba y por la misma razón.
    """
    for salida in (sys.stdout, sys.stderr):
        salida.reconfigure(encoding="utf-8", errors="replace")


def argumentos(crudos: list[str] | None = None) -> argparse.Namespace:
    analizador = argparse.ArgumentParser(
        prog="python -m evals",
        description=(
            "Arnés de evals del fit score: corre los casos de evals/casos.json por el "
            "camino de producción y califica banda, menciones, invariante e inyección."
        ),
    )
    analizador.add_argument(
        "--proveedor",
        choices=sorted(MODOS),
        default="mock",
        help=(
            "mock: no sale del proceso, en segundos y sin gastar nada (el de omisión). "
            "claude: el adaptador real del CLI, que cuesta dinero."
        ),
    )
    analizador.add_argument(
        "--k",
        type=int,
        default=K_POR_OMISION,
        help="cuántas veces se corre cada caso. pass^k son los k intentos bien.",
    )
    analizador.add_argument(
        "--idioma",
        default=IDIOMA_DE_LOS_CASOS,
        help=(
            "el idioma en que se piden las razones. Por omisión «es», que es el de los "
            "12 casos y de sus términos exigidos."
        ),
    )
    analizador.add_argument(
        "--casos",
        nargs="*",
        default=[],
        metavar="ID",
        help="correr solo estos casos (y los gemelos que sus invariantes necesiten).",
    )
    analizador.add_argument(
        "--sin-guardar",
        action="store_true",
        help="no escribir el informe en evals/resultados/.",
    )
    elegidos = analizador.parse_args(crudos)
    if elegidos.k < 1:
        analizador.error("--k tiene que ser 1 o más: pass^k no significa nada con 0 intentos")
    return elegidos


def cabecera(elegidos: argparse.Namespace, pasada: Pasada) -> dict[str, object]:
    """Lo que hay que saber para leer el informe dentro de dos semanas.

    `sustituciones` es el contador del payload (PR-08): **cuánto se le quitó a cada
    CV antes de salir de Criba**. Va en el informe porque limpiar por patrón puede
    quitar de más y eso degrada el texto que decide el score (F1), y porque quien
    mide ese daño es este arnés y, en serio, CA14 (PR-17).
    """
    return {
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "proveedor": elegidos.proveedor,
        "k": elegidos.k,
        "idioma": elegidos.idioma,
        "casos_pedidos": elegidos.casos or "todos",
        "sustituciones": {
            uno.caso_id: uno.sustituciones for uno in pasada.intentos if uno.respuesta
        },
    }


def guardar(informe: dict[str, object], proveedor: str, k: int) -> str:
    """El informe en `evals/resultados/`, con fecha, proveedor y k en el nombre."""
    sello = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    ruta = RUTA_DE_RESULTADOS / f"{sello}-{proveedor}-k{k}.json"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(ruta)


def main(crudos: list[str] | None = None) -> int:
    _salida_en_utf8()
    elegidos = argumentos(crudos)
    print(
        f"arnés de evals · proveedor={elegidos.proveedor} k={elegidos.k} idioma={elegidos.idioma}",
        file=sys.stderr,
    )
    pasada = asyncio.run(
        correr(
            modo=elegidos.proveedor,
            k=elegidos.k,
            idioma=elegidos.idioma,
            ids=elegidos.casos,
        )
    )

    print()
    for linea in lineas(pasada.resultados, pasada.total):
        print(linea)
    print(
        f"costo: {pasada.total.costo_usd:.4f} USD · modelos: "
        f"{', '.join(pasada.total.modelos) or '—'}"
    )

    if not elegidos.sin_guardar:
        informe = como_json(pasada.resultados, pasada.total, cabecera=cabecera(elegidos, pasada))
        print(f"informe: {guardar(informe, elegidos.proveedor, elegidos.k)}")

    errores = pasada.errores
    if errores:
        print(
            f"\n{len(errores)} intentos no llegaron a tener respuesta: el camino de "
            "producción falló, no el modelo. El primero: "
            f"{errores[0].caso_id} → {errores[0].error}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
