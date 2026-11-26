"""Cuántos bytes de la vista de vacante viajan por el cable, con y sin gzip.

    uv run python -m perf.bytes_de_la_vista

`perf/perfil.py` mide milisegundos y el tamaño del **cuerpo**; esto mide lo otro
que el cambio nº 3 de `perf/MEDICION.md` §6 mueve: los bytes que salen de la
aplicación cuando el navegador manda `Accept-Encoding: gzip` y los que salen
cuando no. Son dos peticiones a la misma ruta con la misma sesión, y lo único que
cambia entre ellas es esa cabecera.

Por qué hace falta un comando aparte y no basta con locust: el cliente de locust
manda `Accept-Encoding` por omisión y reporta el **cuerpo ya descomprimido**
(`Average Content Size` de los CSV), así que con sus corridas no se puede saber
qué viajó. Y por qué es en proceso y no con `curl` contra el servidor de
medición: ese servidor corre con el código de antes del PR-PERF-1 y lo reinicia
un humano (`perf/MEDICION.md` §2).

Qué se imprime, y de dónde sale cada número:

- **en el cable** = la cabecera `Content-Length` de la respuesta. Starlette la
  reescribe con el tamaño ya comprimido cuando comprime, así que es lo que el
  servidor pone en el socket;
- **cuerpo** = `len(respuesta.content)`, es decir el HTML ya descomprimido por el
  cliente. Que las dos peticiones den el **mismo** cuerpo es la comprobación de
  que la compresión no cambia el HTML: si no coincidieran, el programa aborta y
  no imprime una tabla que compararía dos páginas distintas;
- **filas** = cuántas veces aparece la marca de fila de `_candidatos.html`, para
  que se vea que los bytes son los de las 500 filas completas (CA8).

Y el **tiempo** de las dos, porque §6 nº 3 estima que comprimir cuesta «+5 a +15
ms de p95» y no lo midió nadie: aquí la misma petición se repite `REPETICIONES`
veces con cada cabecera y se comparan las medianas. Ese reloj está **alrededor**
de la petición en proceso, así que incluye la **descompresión del cliente**, que
en producción paga el navegador: es un techo. Por eso al final se cronometran
aparte, sobre el mismo cuerpo, `gzip.compress` —lo que paga el servidor— y
`gzip.decompress` —lo que paga el cliente—, con el `compresslevel` que Starlette
usa por omisión.
"""

from __future__ import annotations

import gzip as zip_
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass
from inspect import signature

from starlette.middleware.gzip import GZipMiddleware
from starlette.testclient import TestClient

from app.configuracion import ajustes
from app.fabrica import crear_app

# El login y la marca de fila son los mismos que usa `perf/perfil.py`: se
# importan en vez de copiarse para que las dos sondas midan exactamente la misma
# petición de la misma sesión. Son de `perf/`, no API de la aplicación.
from perf.perfil import MARCA_DE_FILA, _entrar

USUARIO = "marcus"  # el reclutador de la petición de CA5 (§3.2)
RUTA = "/vacantes/1"  # la vacante de 500 candidatos de la base de medición
CODIFICACIONES = ("identity", "gzip")
CALENTAMIENTO = 5
REPETICIONES = 20


@dataclass(frozen=True, slots=True)
class Medida:
    """Lo que una cabecera `Accept-Encoding` da: bytes, HTML y tiempos."""

    en_el_cable: int
    cuerpo: int
    codificacion_aplicada: str
    filas: int
    ms: list[float]
    html: bytes

    @property
    def p50(self) -> float:
        return statistics.median(self.ms)

    @property
    def p95(self) -> float:
        return sorted(self.ms)[round(0.95 * (len(self.ms) - 1))]


def medir(cliente: TestClient, codificacion: str) -> Medida:
    """`REPETICIONES` peticiones con `Accept-Encoding: <codificacion>`."""
    cabeceras = {"Accept-Encoding": codificacion}
    tiempos = []
    for _ in range(REPETICIONES):
        comienzo = time.perf_counter()
        respuesta = cliente.get(RUTA, headers=cabeceras)
        tiempos.append((time.perf_counter() - comienzo) * 1000)
        respuesta.raise_for_status()
    return Medida(
        en_el_cable=int(respuesta.headers["content-length"]),
        cuerpo=len(respuesta.content),
        codificacion_aplicada=respuesta.headers.get("content-encoding", "(ninguna)"),
        filas=respuesta.text.count(MARCA_DE_FILA),
        ms=tiempos,
        html=respuesta.content,
    )


def _mediana_ms(hacer: Callable[[], object]) -> float:
    tiempos = []
    for _ in range(REPETICIONES):
        comienzo = time.perf_counter()
        hacer()
        tiempos.append((time.perf_counter() - comienzo) * 1000)
    return statistics.median(tiempos)


def main() -> None:
    print(f"Base: {ajustes().url_bd}")
    print(
        f"Petición: {USUARIO} GET {RUTA}, en proceso con TestClient. "
        f"{REPETICIONES} repeticiones por cabecera, {CALENTAMIENTO} de calentamiento.\n"
    )

    with TestClient(crear_app()) as cliente:
        _entrar(cliente, USUARIO)
        for _ in range(CALENTAMIENTO):
            cliente.get(RUTA).raise_for_status()  # plantillas Jinja y pool de conexiones
        medidas = {codificacion: medir(cliente, codificacion) for codificacion in CODIFICACIONES}

    cuerpos = {medida.cuerpo for medida in medidas.values()}
    if len(cuerpos) != 1:
        raise RuntimeError(
            f"las dos peticiones devolvieron cuerpos de distinto tamaño ({sorted(cuerpos)}): "
            "no se está comparando la misma página y la tabla no significaría nada."
        )

    print(
        f"    {'Accept-Encoding':<18}{'en el cable':>14}{'cuerpo':>12}"
        f"{'Content-Encoding':>20}{'p50 ms':>10}{'p95 ms':>9}"
    )
    print(f"    {'-' * 83}")
    for codificacion, m in medidas.items():
        print(
            f"    {codificacion:<18}{m.en_el_cable:>14,}{m.cuerpo:>12,}"
            f"{m.codificacion_aplicada:>20}{m.p50:>10.1f}{m.p95:>9.1f}"
        )
    sin_gzip, con_gzip = medidas["identity"], medidas["gzip"]
    print(
        f"\n    ahorro de gzip: {sin_gzip.en_el_cable - con_gzip.en_el_cable:,} bytes "
        f"({100 * (1 - con_gzip.en_el_cable / sin_gzip.en_el_cable):.1f} % de "
        f"{sin_gzip.en_el_cable:,})"
    )
    print(
        f"    coste de comprimir, techo: p50 {con_gzip.p50 - sin_gzip.p50:+.1f} ms, "
        f"p95 {con_gzip.p95 - sin_gzip.p95:+.1f} ms (incluye la descompresión del cliente)"
    )
    print(f"    filas renderizadas en las dos respuestas: {con_gzip.filas}")

    # El `compresslevel` se lee del propio middleware y no se escribe aquí: si
    # Starlette cambia su omisión, este bloque mide lo que la app hace.
    nivel = signature(GZipMiddleware.__init__).parameters["compresslevel"].default
    html = sin_gzip.html
    comprimido = zip_.compress(html, compresslevel=nivel)
    print("\n    las dos mitades de ese techo, cronometradas aparte sobre el mismo cuerpo:")
    mitades = (
        (
            f"gzip.compress(cuerpo, compresslevel={nivel})",
            _mediana_ms(lambda: zip_.compress(html, compresslevel=nivel)),
            f"→ {len(comprimido):,} bytes · lo paga el servidor",
        ),
        (
            "gzip.decompress(comprimido)",
            _mediana_ms(lambda: zip_.decompress(comprimido)),
            "lo paga el navegador",
        ),
    )
    for etiqueta, ms, de_quien in mitades:
        print(f"      {etiqueta:<42}{ms:>7.1f} ms   {de_quien}")


if __name__ == "__main__":
    main()
