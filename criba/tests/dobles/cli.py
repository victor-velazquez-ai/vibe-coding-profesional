"""Doble del subproceso del CLI del proveedor, y la puerta al adaptador (PR-09).

**Ningún test de este repo llama al CLI de verdad.** El adaptador real del
proveedor elegido (N4, decisión de Víctor del 22-nov-2026: el modelo es Claude y
en este repo del curso no hay clave de API, así que el cliente real llama al CLI
`claude -p` por subproceso, sin herramientas y sin sesión) tiene **una sola
costura**: la función que lanza el proceso. Este módulo la sustituye por un doble
que cuenta invocaciones y recuerda qué recibió — igual que
`tests/dobles/proveedor.py` hace con el proveedor entero (PR-03) y por la misma
razón: el control de CA3 y el de F12 son «cuántas llamadas» y «qué salió», y eso
solo se asercia si alguien lo apunta.

Lo que este doble fija como **contrato de la costura**, porque un doble no puede
no fijarlo:

- es **una función del módulo del adaptador** —`correr_cli`—, no un método
  inyectado por constructor: el recorrido de implementaciones del test de CA2 las
  instancia **sin argumentos** (`tests/match/test_pseudonimizacion.py::
  implementaciones_del_proveedor`, «el cliente de PR-09 se configura por variable
  de entorno, no por constructor»), así que la costura no puede vivir en la firma
  del constructor;
- es **síncrona** y recibe tres cosas: los argumentos del proceso, el texto que
  va por **entrada estándar** y el **timeout** en segundos. Devuelve lo que el
  proceso escribió en salida estándar. Si el adaptador la envuelve en
  `asyncio.to_thread` para cumplir el `Protocol` asíncrono de ADR-001 (T5), el
  doble sigue valiendo: lo que se dobla es el lanzamiento, no el `await`;
- se lee **por nombre o por posición** (`_leer`), para no fijar más de lo
  necesario: lo que el paso necesita es que el CV viaje por la entrada y que el
  timeout llegue al proceso, no cómo se llaman los parámetros.

Y la segunda mitad del módulo, `adaptador()`, es la **puerta**: resuelve los
símbolos que PR-09 tiene que escribir y, mientras no existan, falla con un
`assert` que los nombra. Es el mismo patrón que `frontera()` en
`tests/match/test_pseudonimizacion.py` y existe por la misma razón: un
`ImportError` al recoger los tests no dice qué falta ni deja correr el resto del
archivo, y el rojo de este paso tiene que ser legible.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any

from app.match.proveedor.payload import PayloadPseudonimizado
from app.match.services.pseudonimizador import pseudonimizar
from app.plataforma.modelos import Candidato

# Tres razones cortas y sintéticas (alcance 1 de `SPEC.md`). El doble no traduce:
# el idioma del prompt es CA11 y llega en PR-22.
RAZONES_DEL_CLI = (
    "Licencia RN vigente en el estado de la vacante",
    "Cinco años en el turno que la vacante pide",
    "Experiencia en piso de medicina interna",
)
SCORE_DEL_CLI = 83

# Donde se buscan los símbolos del paso. Dos módulos y no uno porque dónde se
# **declara** el modo —en el adaptador o en la configuración de Match— es decisión
# del constructor: `app/match/configuracion.py` no puede importar al adaptador
# (el adaptador importa de ella `Proveedor` y `RespuestaDelProveedor`, y sería un
# ciclo), así que la fábrica vive en el adaptador, pero el **nombre de la
# variable** puede vivir en cualquiera de los dos.
MODULOS = ("app.match.proveedor.cliente", "app.match.configuracion")

NOMBRE_DE_LA_COSTURA = "correr_cli"

# La superficie que PR-09 declara, con la razón de cada símbolo. Es el contrato
# del paso: estos nombres son los que los tests importan.
SUPERFICIE: dict[str, str] = {
    "ProveedorClaudeCLI": (
        "el adaptador real detrás de la frontera de PR-08: implementa el `Protocol` "
        "`Proveedor` y se construye **sin argumentos** (CA2, el recorrido de "
        "implementaciones de test_pseudonimizacion.py)"
    ),
    NOMBRE_DE_LA_COSTURA: (
        "la ÚNICA función que lanza el subproceso `claude -p`: síncrona, recibe los "
        "argumentos, el texto de entrada estándar y el timeout en segundos, y "
        "devuelve la salida estándar (N4; F12: una sola puerta por la que puede "
        "salir un CV y una sola donde vale la regla de log)"
    ),
    "proveedor_configurado": (
        "la fábrica que lee el modo de la configuración y devuelve el proveedor: el "
        "MOCK por omisión, el adaptador real solo con configuración explícita "
        "(PLAN.md PR-09, test 3; pregunta abierta 11 de §9)"
    ),
    "ErrorDelProveedor": (
        "el error **tipado** del adaptador: lo que sale cuando el proveedor falla, "
        "en vez de la excepción cruda del subproceso (PLAN.md PR-09, test 2)"
    ),
    "TiempoDeEsperaDelProveedor": (
        "el error tipado del timeout, **subclase** del anterior: PR-11 lo trata como "
        "causa transitoria —pendiente con reintento, no «sin score»— y para eso "
        "tiene que poder distinguirlo (tabla de estados de PLAN.md PR-11)"
    ),
    "VARIABLE_DE_MODO": (
        "el nombre de la variable de entorno que elige el proveedor: configuración "
        "por entorno, nunca en el repo (F19, PLAN.md PR-09, archivos)"
    ),
    "MODO_MOCK": "el valor del modo MOCK, que es el de omisión (PLAN.md PR-09, test 3)",
    "MODO_CLAUDE_CLI": "el valor del modo del adaptador real (N4)",
}


@dataclass(frozen=True, slots=True)
class Adaptador:
    """Los símbolos de PR-09, ya resueltos, y el módulo donde vive la costura."""

    modulo_de_la_costura: ModuleType
    real: type
    costura: Any
    error: type[BaseException]
    tiempo_agotado: type[BaseException]
    configurado: Any
    variable_de_modo: str
    modo_mock: str
    modo_cli: str


def adaptador() -> Adaptador:
    """Resuelve la superficie de PR-09, o falla nombrando lo que falta."""
    resueltos: dict[str, tuple[ModuleType, Any]] = {}
    faltan: list[str] = []
    for nombre, razon in SUPERFICIE.items():
        for ruta in MODULOS:
            modulo = importlib.import_module(ruta)
            if hasattr(modulo, nombre):
                resueltos[nombre] = (modulo, getattr(modulo, nombre))
                break
        else:
            faltan.append(f"  - {nombre}: {razon}")
    assert faltan == [], (
        "el cliente real del proveedor todavía no existe. En "
        + " o ".join(MODULOS)
        + " falta:\n"
        + "\n".join(faltan)
    )
    return Adaptador(
        modulo_de_la_costura=resueltos[NOMBRE_DE_LA_COSTURA][0],
        real=resueltos["ProveedorClaudeCLI"][1],
        costura=resueltos[NOMBRE_DE_LA_COSTURA][1],
        error=resueltos["ErrorDelProveedor"][1],
        tiempo_agotado=resueltos["TiempoDeEsperaDelProveedor"][1],
        configurado=resueltos["proveedor_configurado"][1],
        variable_de_modo=resueltos["VARIABLE_DE_MODO"][1],
        modo_mock=resueltos["MODO_MOCK"][1],
        modo_cli=resueltos["MODO_CLAUDE_CLI"][1],
    )


class LlamadaProhibidaAlCLI(AssertionError):
    """Se lanzó el CLI en un caso que lo prohíbe (CA3, el modo MOCK). Falla el test."""


@dataclass(frozen=True, slots=True)
class Invocacion:
    """Qué recibió el subproceso: su línea de órdenes, su entrada y su timeout."""

    argumentos: tuple[str, ...]
    entrada: str
    timeout: float | None

    @property
    def linea(self) -> str:
        """Los argumentos como una sola cadena, para buscar dentro de ellos.

        Es la forma en que un CV o una clave en `argv` se ve de verdad: en `ps`, en
        un volcado de proceso o en una línea de log del sistema (F12, F19).
        """
        return " ".join(self.argumentos)


def _leer(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Invocacion:
    """Lee la invocación **por nombre o por posición**, sin fijar los nombres.

    Lo que el paso necesita fijar es qué viaja por dónde —el CV por la entrada
    estándar, el timeout hasta el proceso—, no si el parámetro se llama `entrada`
    o `stdin`. Así el adaptador elige sus nombres y el doble sigue valiendo.
    """
    posicionales = list(args)

    def siguiente(*nombres: str) -> Any:
        for nombre in nombres:
            if nombre in kwargs:
                return kwargs[nombre]
        return posicionales.pop(0) if posicionales else None

    argumentos = siguiente("argumentos", "orden", "comando", "argv")
    entrada = siguiente("entrada", "stdin", "texto", "prompt")
    timeout = siguiente("timeout", "segundos", "tiempo", "espera")
    assert argumentos is not None, (
        "la costura del subproceso se llamó sin argumentos de proceso: el doble no puede "
        "comprobar qué se iba a lanzar (N4, F12, F19)"
    )
    if isinstance(argumentos, str):  # una cadena con `shell=True` sería otra cosa, y peor
        argumentos = (argumentos,)
    return Invocacion(tuple(str(pieza) for pieza in argumentos), str(entrada or ""), timeout)


@dataclass(slots=True)
class CLIDoblado:
    """La costura doblada: apunta cada invocación y devuelve lo que se le diga.

    `salida` es lo que el proceso escribe en salida estándar; `fallo`, la excepción
    **cruda** que el subproceso levantaría (`subprocess.TimeoutExpired`,
    `CalledProcessError`, `FileNotFoundError`), que es justo lo que el adaptador
    tiene que convertir en un error tipado (PLAN.md PR-09, test 2).
    """

    salida: str = ""
    fallo: BaseException | None = None
    prohibido: bool = False
    invocaciones: list[Invocacion] = field(default_factory=list)

    def __call__(self, *args: Any, **kwargs: Any) -> str:
        # Se apunta **antes** de fallar: con `prohibido`, el test necesita poder
        # decir cuántas invocaciones hubo, no solo que hubo alguna.
        self.invocaciones.append(_leer(args, kwargs))
        if self.prohibido:
            raise LlamadaProhibidaAlCLI(
                "este caso prohíbe lanzar el CLI del proveedor y se lanzó igual"
            )
        if self.fallo is not None:
            raise self.fallo
        return self.salida

    @property
    def llamadas(self) -> int:
        return len(self.invocaciones)

    @property
    def ultima(self) -> Invocacion:
        assert self.invocaciones, "el adaptador no lanzó ningún subproceso"
        return self.invocaciones[-1]


# --- el material sintético de los dos archivos de tests del paso -----------

# **Sintético** (D3 modificado, D15, F12). Largo suficiente para que haya frases
# de ocho palabras, que es la medida de F12 y de CA15.
CV_SINTETICO = (
    "Enfermera registrada con licencia vigente en el estado de la vacante. "
    "Ocho años en piso de medicina interna y cinco de ellos en turno nocturno "
    "de doce horas. Telemetría, manejo de vía central y valoración al ingreso. "
    "Soporte vital básico y avanzado vigentes, con atención bilingüe en consulta."
)


def candidato_sintetico() -> Candidato:
    """Un candidato sintético **sin base de datos**: `pseudonimizar` solo lee campos.

    Los tests del adaptador no necesitan la plataforma; los que sí la necesitan
    —el bucle del ejecutor y el de multiempresa— piden las fixtures enteras.
    """
    return Candidato(
        nombre="Valentina Sintetica",
        correo="valentina@ejemplo.test",
        telefono="+1 713 555 0101",
        links=[],
        cv_texto=CV_SINTETICO,
    )


def payload_sintetico() -> PayloadPseudonimizado:
    """El cuerpo que sale de Criba, por la única fábrica que lo construye (CA2, PR-08)."""
    return pseudonimizar(candidato_sintetico())


def salida_del_cli(score: int = SCORE_DEL_CLI, razones: tuple[str, ...] = RAZONES_DEL_CLI) -> str:
    """Lo que el CLI escribe en salida estándar: el score y sus tres razones.

    JSON pelado y **sin versión de modelo dentro**, a propósito: la versión que la
    auditoría de D15 y CA15 va a guardar tiene que ser la que el adaptador
    **pidió**, no la que el CLI eligiera por su cuenta (ver el test de la
    invocación). Un score fuera de rango, cuatro razones o un JSON roto son casos
    de PR-11, no de este doble.
    """
    return json.dumps({"score": score, "razones": list(razones)}, ensure_ascii=False)


def cli_que_prohibe_llamadas() -> CLIDoblado:
    """El doble que falla el test con una sola invocación (CA3, el modo MOCK)."""
    return CLIDoblado(prohibido=True)


# --- la regla de F12, medida en frases de ocho palabras --------------------

PALABRAS_POR_FRASE = 8

# Las formas en que un salto de línea o una tabulación llegan **escapados** a una
# línea de log: `json.dumps` convierte el salto en los dos caracteres `\` y `n`,
# así que buscar la frase tal cual no encontraría nada y el test de F12 pasaría
# con el CV entero dentro del log.
_ESCAPES = ("\\n", "\\r", "\\t", "\\\\n")


def normalizar(texto: str) -> str:
    """El texto con los espacios colapsados y los saltos escapados deshechos.

    Es lo que hace comparable «una frase de ocho palabras del CV» con una línea de
    log: el CV viene con saltos de línea y el log, con el salto escapado o con el
    texto reflujado.
    """
    for escape in _ESCAPES:
        texto = texto.replace(escape, " ")
    return " ".join(texto.split())


def frases_de(texto: str) -> set[str]:
    """Todas las frases de ocho palabras consecutivas del texto.

    Ocho palabras es el umbral que `SPEC.md` CA15 y `docs/fallas.md` F12 usan:
    corto para que cualquier fragmento reconocible del CV caiga, largo para que
    «turno nocturno» o «licencia vigente» —que no identifican a nadie y están en
    cualquier descripción de vacante— no den un falso positivo.
    """
    palabras = normalizar(texto).split()
    return {
        " ".join(palabras[inicio : inicio + PALABRAS_POR_FRASE])
        for inicio in range(len(palabras) - PALABRAS_POR_FRASE + 1)
    }
