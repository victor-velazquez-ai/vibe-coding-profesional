"""Proveedor MOCK: score fijo, no sale de la red (PR-06, `docs/arquitectura.md` §2).

Es el **único** proveedor que existe hasta PR-09, y eso es la regla 1.5 de
`PLAN.md`: mientras no existan la frontera de pseudonimización (PR-08) y la
comprobación de activación por empresa (PR-10), el camino que podría sacar un CV
de Criba **no existe en el repo**. Este módulo no importa ningún cliente HTTP:
devuelve un score fijo y tres razones sintéticas, y por eso CA2 y CA3 no pueden
quedar en deuda técnica en la Etapa 0.

Lo que el MOCK **no** es: una medida de calidad. El conjunto dorado de CA14 se
mide con el proveedor real (PR-17); aquí el número solo tiene que ser el mismo
siempre, para que el E2E de PR-07 pueda asercir sobre él.
"""

from __future__ import annotations

from app.match.configuracion import RespuestaDelProveedor

SCORE_DEL_MOCK = 70
VERSION_DEL_MOCK = "mock-1"

# Sintéticas y en español, como las fixtures (D3 modificado, D15, F12). El MOCK
# no traduce: el idioma se decide en el prompt, que llega en PR-09 y PR-22.
RAZONES_DEL_MOCK = (
    "Cumple la licencia que la vacante pide",
    "Experiencia en el turno de la vacante",
    "Ciudad compatible con el puesto",
)


class ProveedorMock:
    """Implementa `app.match.configuracion.Proveedor` sin salir del proceso."""

    async def puntuar(self, payload: object, idioma: str) -> RespuestaDelProveedor:
        return RespuestaDelProveedor(SCORE_DEL_MOCK, RAZONES_DEL_MOCK, VERSION_DEL_MOCK)
