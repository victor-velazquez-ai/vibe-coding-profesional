"""Doble del proveedor de modelos, con contador de llamadas (PR-03).

No sale de la red, como el MOCK (`docs/arquitectura.md` §2), y su contador es lo
que tres criterios asercian: **CA3** —una empresa sin anexo firmado no produce
**ninguna** llamada, y `proveedor_que_prohibe_llamadas()` falla el test con una
sola—, **CA4** —abrir la vacante emite cero— y **CA6** —el proveedor caído no
rompe la vacante: `proveedor_con_timeout()` y `proveedor_con_error(500)`—.

**Qué recibe, desde la decisión de Víctor del 22-nov-2026 sobre el hallazgo 1 de
PR-09** (`docs/prs/PR-09.md` §«Lo que este paso descubre y no puede arreglar»; la
decisión **todavía no tiene archivo propio en `docs/`** y registrarla es parte de
esta ronda — M2): el
payload pseudonimizado del CV, el idioma y **la descripción de la vacante**, que
es dato de la empresa y no del candidato y viaja como un campo aparte del pedido
—nunca dentro de `PayloadPseudonimizado`, que sigue siendo solo del candidato
(CA2)—. El doble lee ese tercer dato **sin fijar la forma del pedido**
(`_descripcion_de_vacante`): por posición o por nombre, igual que
`tests/dobles/cli.py::_leer` hace con la invocación del subproceso, porque cómo
se llama el parámetro es del constructor y lo que el criterio exige es que
**llegue**. Y lo lee con firma abierta (`*extras`) a propósito: así los tests de
PR-03, PR-06, PR-08 y PR-10 que llaman con dos argumentos siguen valiendo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.match.configuracion import RespuestaDelProveedor

# Nombres por los que puede entrar la descripción de la vacante si el pedido la
# pasa por palabra clave. No es una lista exhaustiva: por eso se mira también la
# posición, que es la forma que no depende de ningún nombre.
NOMBRES_DE_LA_VACANTE = ("vacante", "descripcion")

# Tres razones cortas y sintéticas. El doble no traduce: el idioma se comprueba
# donde se decide, en el prompt (CA11, PR-22).
RAZONES = (
    "Cumple la licencia que la vacante pide",
    "Experiencia en el turno de la vacante",
    "Ciudad compatible con el puesto",
)


class LlamadaProhibida(AssertionError):
    """Llegó una llamada que el criterio prohíbe (CA3). Es un fallo del test."""


class ErrorDelProveedor(RuntimeError):
    """El proveedor respondió con un error HTTP (CA6)."""


def _descripcion_de_vacante(extras: tuple[Any, ...], kwargs: dict[str, Any]) -> str | None:
    """La descripción de la vacante del pedido, por nombre o por posición.

    Devuelve `None` cuando no llegó, que es lo que hace legible el rojo del
    criterio: «el proveedor recibió el CV y el idioma, y no la descripción».
    """
    for nombre, valor in kwargs.items():
        if any(pieza in nombre.lower() for pieza in NOMBRES_DE_LA_VACANTE):
            return None if valor is None else str(valor)
    for extra in extras:
        if isinstance(extra, str):
            return extra
    return None


@dataclass(slots=True)
class ProveedorContado:
    """Implementa `app.match.configuracion.Proveedor` y recuerda qué recibió."""

    score: int = 72
    version_modelo: str = "doble-1"
    prohibido: bool = False
    fallo: Exception | None = None
    llamadas: int = 0
    payloads: list[object] = field(default_factory=list)
    idiomas: list[str] = field(default_factory=list)
    # La descripción de la vacante de cada llamada, o `None` si no llegó
    # (decisión de Víctor del 22-nov-2026 sobre el hallazgo 1 de PR-09).
    vacantes: list[str | None] = field(default_factory=list)

    async def puntuar(
        self, payload: object, idioma: str = "", *extras: Any, **kwargs: Any
    ) -> RespuestaDelProveedor:
        # Se cuenta **antes** de fallar: con `prohibido`, el test necesita poder
        # decir cuántas llamadas hubo, no solo que hubo alguna.
        self.llamadas += 1
        self.payloads.append(payload)
        self.idiomas.append(idioma)
        self.vacantes.append(_descripcion_de_vacante(extras, kwargs))
        if self.prohibido:
            raise LlamadaProhibida("este caso prohíbe toda llamada al proveedor (CA3)")
        if self.fallo is not None:
            raise self.fallo
        return RespuestaDelProveedor(self.score, RAZONES, self.version_modelo)


def proveedor_que_prohibe_llamadas() -> ProveedorContado:
    return ProveedorContado(prohibido=True)


def proveedor_con_timeout() -> ProveedorContado:
    return ProveedorContado(fallo=TimeoutError("el proveedor agotó el tiempo de espera"))


def proveedor_con_error(estado: int = 500) -> ProveedorContado:
    return ProveedorContado(fallo=ErrorDelProveedor(f"el proveedor respondió {estado}"))
