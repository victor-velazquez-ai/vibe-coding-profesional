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
from app.match.proveedor.payload import PayloadPseudonimizado, exigir_payload

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

    async def puntuar(
        self,
        payload: PayloadPseudonimizado,
        idioma: str,
        descripcion_de_vacante: str = "",
    ) -> RespuestaDelProveedor:
        """Exige la frontera **aunque no salga de la red** (PR-08, CA2).

        El MOCK no necesita el control para sí mismo: lo necesita para que el
        camino que el cliente real de PR-09 va a recorrer esté ya cerrado y
        probado cuando ese cliente exista. Si el único que exigiera el tipo fuera
        el cliente real, la frontera nacería el día en que de verdad hay algo que
        perder (regla 1.5, F6).

        **Recibe la descripción de la vacante y no la mira**, y eso es correcto
        aquí: el MOCK devuelve un número fijo para que el E2E pueda asercir sobre
        él, así que el par (candidato, vacante) no cambia nada de lo que
        responde. Está en la firma porque el `Protocol` la declara —el
        `MatchService` se la pasa a quien sea el proveedor de la pasada— y porque
        lo contrario sería que el MOCK dejara de cumplirlo.
        """
        exigir_payload(payload)
        return RespuestaDelProveedor(SCORE_DEL_MOCK, RAZONES_DEL_MOCK, VERSION_DEL_MOCK)
