"""El bucle del ejecutor: concurrencia, reintentos y reconciliación (PR-06, PR-14, PR-15).

La versión mínima de la Etapa 0: **un trabajo a la vez, sin lease, sin reintentos
y sin concurrencia**. Es deuda aceptada a propósito y PR-14 reescribe la toma del
trabajo; lo que este paso fija y PR-14 no cambia es de dónde sale el
`empresa_id`: **de la fila de la cola ya tomada** (F5, `docs/arquitectura.md`
§5.3, ADR-001 §Decisión 1). Ni de la cookie, ni de un argumento, ni del candidato
resuelto por otro camino.

El bucle es **una función invocable**, todavía no un comando ni una tarea de
arranque: quién lo invoca en producción es ADR-001 («el ejecutor corre en el
proceso web») y el comando de la carga es PR-16. Por eso la reconciliación de
leases y la alerta de pendientes >60 min (CA7) no están aquí: son de PR-15.

Con el **interruptor global apagado** el bucle no corre (R4·I1, R6·B1).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.match.cola.trabajos import tomar
from app.match.configuracion import Proveedor, ajustes_match
from app.match.proveedor.mock import ProveedorMock
from app.match.repositories.contexto import ContextoDeEmpresa
from app.match.repositories.match_repo import RepositorioDeMatch
from app.match.services.scoring import MatchService

LARGO_DEL_MOTIVO = 120


async def una_pasada(bd: Session, proveedor: Proveedor | None = None) -> int:
    """Toma **un** trabajo pendiente, lo puntúa y lo cierra. Devuelve 1 o 0.

    Devuelve 1 también cuando el trabajo termina en `error`: lo que cuenta es
    cuántos salieron de `pendiente`, para que `pasadas` no gire para siempre.
    El reintento es de PR-14.
    """
    if not ajustes_match().activo:
        return 0
    trabajo = tomar(bd)
    if trabajo is None:
        return 0

    # Aquí nace el contexto de empresa, y nace de la fila (F5). El resto de la
    # pasada no puede ver otra empresa: el repositorio filtra por esta.
    repo = RepositorioDeMatch(bd, ContextoDeEmpresa.desde_el_trabajo(bd, trabajo.id))
    repo.marcar_trabajo(trabajo.id, "en_curso")
    try:
        await MatchService(repo, proveedor or ProveedorMock()).puntuar(trabajo)
    except Exception as exc:  # el motivo queda en la fila, no en un log con PII
        repo.marcar_trabajo(trabajo.id, "error", motivo=type(exc).__name__[:LARGO_DEL_MOTIVO])
        return 1
    repo.marcar_trabajo(trabajo.id, "listo")
    return 1


async def pasadas(bd: Session, proveedor: Proveedor | None = None, maximo: int = 100) -> int:
    """El bucle: pasadas hasta que no quede nada pendiente. Devuelve cuántas.

    `maximo` es un tope de seguridad y no una política de concurrencia: con un
    trabajo que volviera a `pendiente` por su cuenta, esto giraría sin fin. El
    tope de concurrencia de verdad —y el reintento que lo necesita— es PR-14.
    """
    hechos = 0
    while hechos < maximo and await una_pasada(bd, proveedor):
        hechos += 1
    return hechos
