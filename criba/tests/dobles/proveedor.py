"""Doble del proveedor de modelos, con contador de llamadas (PR-03).

No sale de la red, como el MOCK (`docs/arquitectura.md` §2), y su contador es lo
que tres criterios asercian: **CA3** —una empresa sin anexo firmado no produce
**ninguna** llamada, y `proveedor_que_prohibe_llamadas()` falla el test con una
sola—, **CA4** —abrir la vacante emite cero— y **CA6** —el proveedor caído no
rompe la vacante: `proveedor_con_timeout()` y `proveedor_con_error(500)`—.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.match.configuracion import RespuestaDelProveedor

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

    async def puntuar(self, payload: object, idioma: str) -> RespuestaDelProveedor:
        # Se cuenta **antes** de fallar: con `prohibido`, el test necesita poder
        # decir cuántas llamadas hubo, no solo que hubo alguna.
        self.llamadas += 1
        self.payloads.append(payload)
        self.idiomas.append(idioma)
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
