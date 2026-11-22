"""El camino de producción del arnés, doblado en su **única puerta**.

Los tests de `tests/evals/test_calificacion.py` y `test_pass_k.py` califican
respuestas **fabricadas a mano** y no recorren nada: eso es lo que les permite
probar el calificador sin red, sin clave y sin gastar dinero. Lo que estos dobles
añaden es la otra mitad, la que la revisión del paso echó en falta (hallazgo I1):
`evals/corredor.py` y `evals/__main__.py` **recorren** el camino de producción
—pseudonimizador → fábrica de proveedor → adaptador del CLI— y hoy nada falla si
ese recorrido se rompe.

**Dónde se dobla, y por qué justo ahí.** En `proveedor/cliente.py::correr_cli`, la
costura que `tests/dobles/cli.py` ya fijó como contrato en PR-09: la única función
de la aplicación que lanza un proceso. Doblarla ahí y no más arriba es lo que hace
que estos tests ejerciercan de verdad `pseudonimizar`, `proveedor_configurado`,
`exigir_payload` e `interpretar` —las tres piezas que el corredor promete recorrer—
en vez de un camino paralelo inventado por el test. **Ningún test de aquí lanza el
CLI ni abre red** (la fixture `ningun_cli_de_verdad` de `tests/conftest.py` lo
garantiza además por omisión para toda la suite).

**El guion es por caso y por número de llamada**, no por orden global: el
emparejamiento del gemelo de un invariante es «el mismo intento», así que un test
que quiera distinguir el intento 1 del intento 2 necesita darle a cada caso su
propia secuencia de respuestas. Qué caso viaja en una invocación se reconoce por el
**CV que salió de Criba** —el que la frontera de CA2 dejó salir, calculado con la
misma función que usa el corredor—, y no por una marca de texto elegida a ojo: dos
casos del archivo comparten frases (fs-25 y fs-26 son el mismo CV con datos
personales añadidos) y una marca ambigua haría que el guion contestara por el caso
equivocado sin que nada lo dijera.

**Nada de aquí sabe de empresas, y no es un olvido:** los 12 casos son texto
sintético, el arnés no abre sesión, no consulta ninguna tabla y no recibe
`empresa_id` (D4, CA1, regla 1.6 de `PLAN.md` §1). El aislamiento multiempresa está
probado donde ocurre, en `tests/match/test_aislamiento.py` y
`tests/match/test_activacion_por_empresa.py`. Lo que sí se prueba aquí es la otra
mitad de esa familia de controles, la que el arnés **sí** puede romper: que ni la
traza ni el informe guardado lleven texto de un CV o de una respuesta (F12, D15).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache

import pytest

from app.match.configuracion import MODO_MOCK, VARIABLE_DE_MODO, ajustes_match
from app.match.proveedor import cliente
from app.match.services.pseudonimizador import pseudonimizar
from evals.casos import casos
from evals.corredor import candidato_del_caso
from tests.dobles.cli import NOMBRE_DE_LA_COSTURA, SOBRE_DEL_CLI, salida_del_cli

# Lo que el CLI reporta de costo en cada llamada, tomado del mismo sobre que el
# doble de PR-09 emite (`total_cost_usd`, medido en PR-09: 0,0082 USD por CV
# sintético). El arnés lo lee de paso en la única puerta: ver `costo_observado`.
COSTO_POR_LLAMADA = float(SOBRE_DEL_CLI["total_cost_usd"])  # type: ignore[arg-type]

# Las razones de los casos de QA (fs-25 y fs-26): las dos exigen «playwright» y
# nada más, así que con esta única razón lo único que puede mover el resultado es
# el score — que es lo que los tests del invariante necesitan.
RAZONES_DE_QA = ("Punto considerado: playwright",)

# Las de fs-01, un «alto» que exige fastapi y postgres.
RAZONES_DE_FS01 = ("Punto considerado: fastapi", "Punto considerado: postgres")


def respuesta_del_cli(score: int, *razones: str) -> str:
    """Lo que el CLI escribe en salida estándar: **el sobre** con el score dentro.

    Es el mismo `salida_del_cli` de `tests/dobles/cli.py` y por tanto la misma forma
    que PR-09 fijó: con `--output-format json` el CLI real devuelve siempre el
    sobre, y es ese sobre el que trae el `total_cost_usd` que el arnés suma.
    """
    return salida_del_cli(score, tuple(razones))


@lru_cache(maxsize=1)
def _cv_por_caso() -> dict[str, str]:
    """El CV **ya pseudonimizado** de cada caso → su `id`.

    Se calcula con `candidato_del_caso` + `pseudonimizar`, o sea con las dos
    funciones que el corredor usa: si el arnés dejara de pasar por la frontera de
    CA2, estos textos no casarían con lo que llega a la puerta y el guion lo diría
    en vez de contestar igual.
    """
    return {pseudonimizar(candidato_del_caso(uno)).cv: uno["id"] for uno in casos()}


def caso_de_la_entrada(entrada: str) -> str:
    """Qué caso viaja en esta invocación, por el CV que lleva dentro.

    Se queda con la coincidencia **más larga** a propósito: el CV de fs-26 es el de
    fs-25 con tres líneas de datos personales añadidas, y si los dos casaran, el
    guion tiene que contestar por el que de verdad salió.
    """
    coincidencias = [(len(cv), ident) for cv, ident in _cv_por_caso().items() if cv in entrada]
    assert coincidencias, (
        "la entrada que llegó a la única puerta del proveedor no lleva el CV "
        "pseudonimizado de ninguno de los 12 casos del archivo: el arnés no pasó por "
        "`pseudonimizar(candidato_del_caso(...))` (CA2, PR-08)"
    )
    return max(coincidencias, key=lambda par: par[0])[1]


@dataclass(slots=True)
class CLIGuionado:
    """La costura doblada con un guion **por caso**, que apunta lo que recibió.

    `guion[caso_id]` es la lista de respuestas de ese caso, en orden de intento: una
    cadena es lo que el proceso escribe, una excepción es el fallo **crudo** del
    subproceso que el adaptador tiene que convertir en error tipado.
    """

    guion: dict[str, list[str | BaseException]]
    entradas: list[str] = field(default_factory=list)
    argumentos: list[tuple[str, ...]] = field(default_factory=list)
    casos_llamados: list[str] = field(default_factory=list)

    def __call__(self, argumentos: Sequence[str], entrada: str, timeout: float) -> str:
        self.entradas.append(entrada)
        self.argumentos.append(tuple(str(pieza) for pieza in argumentos))
        ident = caso_de_la_entrada(entrada)
        self.casos_llamados.append(ident)
        pendientes = self.guion.get(ident, [])
        assert pendientes, (
            f"el guion no tiene más respuestas para {ident!r}: el arnés llamó al "
            f"proveedor más veces de las previstas (llamadas: {self.casos_llamados})"
        )
        siguiente = pendientes.pop(0)
        if isinstance(siguiente, BaseException):
            raise siguiente
        return siguiente

    @property
    def llamadas(self) -> int:
        return len(self.entradas)


Guion = Mapping[str, Sequence[str | BaseException]]
PonerGuion = Callable[[Guion], CLIGuionado]


@contextmanager
def camino_doblado(monkeypatch: pytest.MonkeyPatch) -> Iterator[PonerGuion]:
    """El arnés hablando con un CLI guionado, y el modo del proveedor restaurado.

    Devuelve la función que **pone** un guion y entrega el doble ya instalado. Un
    test que solo necesite la restauración del modo —los que corren con el MOCK—
    puede no poner ninguno.

    Lo de restaurar el modo no es cosmética: `corredor.proveedor_del_modo` escribe
    `CRIBA_MATCH_PROVEEDOR` en el entorno **del proceso** y vacía la caché de
    `ajustes_match`, que se lee una vez por proceso. Sin esto, un test que corra el
    arnés con `--proveedor claude` deja el modo real puesto para todos los tests
    siguientes, y la garantía de `tests/conftest.py` —«la suite habla con el MOCK,
    dicho por la suite y no heredado del entorno»— se pierde a mitad de la pasada.

    Es un gestor de contexto y no una fixture a propósito: las fixtures importadas
    de otro módulo dan un `F811` en cada test que las pide (el parámetro tapa al
    import), así que cada archivo de tests declara su fixture `camino` de cuatro
    líneas y la conducta vive aquí, sin duplicarse.
    """
    monkeypatch.setenv(VARIABLE_DE_MODO, MODO_MOCK)

    def poner(guion: Guion) -> CLIGuionado:
        doble = CLIGuionado({ident: list(salidas) for ident, salidas in guion.items()})
        monkeypatch.setattr(cliente, NOMBRE_DE_LA_COSTURA, doble)
        return doble

    try:
        yield poner
    finally:
        ajustes_match.cache_clear()
