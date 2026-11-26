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

Con el **interruptor global apagado** el bucle no corre (R4·I1, R6·B1). Y con la
empresa de la fila **sin activación**, el trabajo no se puntúa: es el segundo
momento de la comprobación de D7 (PR-10, F5, §5.3), y la decide la misma función
del repositorio que `encolar` llama antes del `INSERT`.
"""

from __future__ import annotations

import json
import logging
import time

from sqlalchemy.orm import Session

from app.match.cola.trabajos import tomar
from app.match.configuracion import Proveedor, ajustes_match
from app.match.proveedor.cliente import proveedor_configurado
from app.match.repositories.contexto import ContextoDeEmpresa
from app.match.repositories.match_repo import RepositorioDeMatch
from app.match.repositories.modelos import TrabajoDeMatch
from app.match.services.scoring import MatchService

LARGO_DEL_MOTIVO = 120
# El motivo del trabajo que D7 rechaza al tomarlo. Es un motivo **del trabajo**,
# no un «sin score» que se le muestre al reclutador (eso es CA13, PR-11): aquí no
# hay nada que decirle al candidato, hay una empresa sin anexo firmado.
SIN_ACTIVACION = "empresa_sin_activacion"

# La línea de log del camino de escritura, la pareja de `LOG_DEL_LISTADO`
# (`services/listado.py`) para el camino de lectura.
LOG_DEL_EJECUTOR = "app.match.cola.ejecutor"
EVENTO_DE_CIERRE = "match.trabajo_cerrado"

_log = logging.getLogger(LOG_DEL_EJECUTOR)


async def una_pasada(bd: Session, proveedor: Proveedor | None = None) -> int:
    """Toma **un** trabajo pendiente, lo puntúa y lo cierra. Devuelve 1 o 0.

    Devuelve 1 también cuando el trabajo termina en `error`: lo que cuenta es
    cuántos salieron de `pendiente`, para que `pasadas` no gire para siempre.
    El reintento es de PR-14.
    """
    if not ajustes_match().activo:
        return 0
    comienzo = time.perf_counter()
    trabajo = tomar(bd)
    if trabajo is None:
        return 0

    # Aquí nace el contexto de empresa, y nace de la fila (F5). El resto de la
    # pasada no puede ver otra empresa: el repositorio filtra por esta.
    repo = RepositorioDeMatch(bd, ContextoDeEmpresa.desde_el_trabajo(bd, trabajo.id))
    # D7 y CA3, **segunda vez y misma función** (PR-10, `docs/arquitectura.md`
    # §5.3): la fila pudo encolarse cuando la empresa estaba activada, o pudo
    # retirarse el anexo después, y aquí **no hay cookie** que revalidar. Sin
    # esto, el escenario literal de F5: «entra un CV de Meridian y se emite una
    # llamada al proveedor por una empresa sin anexo firmado» (severidad 5).
    if not repo.empresa_activada():
        # Sale de `pendiente` a propósito. Dejarlo pendiente lo haría volver a
        # tomarse en cada pasada y lo pondría en la alerta de >60 min de CA7 para
        # siempre, por una empresa que nunca se va a puntuar. Qué estado merece
        # —y si PR-14 debe reintentarlo— es **pregunta abierta** de este paso:
        # `estado_trabajo` solo admite los cuatro valores de la 0001 y PR-10 no
        # trae migración. Lo único que no puede ser es `listo`: nadie lo puntuó.
        _registrar_cierre(repo.marcar_trabajo(trabajo.id, "error", motivo=SIN_ACTIVACION), comienzo)
        return 1

    repo.marcar_trabajo(trabajo.id, "en_curso")
    try:
        # **El proveedor lo elige la configuración, no este bucle** (PR-09). El
        # argumento sigue existiendo para los tests que inyectan su doble; lo que
        # cambia es el valor por omisión, que antes era `ProveedorMock()` escrito
        # a mano aquí. Sin esto, el modo de configuración sería una variable de
        # entorno que no cambia nada: el cliente real existiría y no habría forma
        # de llegar a él.
        #
        # **Y cambiar el modo exige reiniciar el proceso** (R?·M1). Se pregunta
        # por pasada, pero `ajustes_match` es `lru_cache(maxsize=1)`: la variable
        # se lee **una vez por proceso**, como los ajustes de la plataforma. Así
        # que ni encender el cliente real ni volver al MOCK para cortar gasto
        # —pregunta abierta 11 de `PLAN.md` §9— se consiguen exportando la
        # variable: hay que reiniciar. Preguntar por pasada no sirve para eso,
        # sirve para que el proveedor no quede **congelado al importar** el
        # módulo: así el objeto se construye con los ajustes de la pasada y los
        # tests pueden invalidar la caché (`ajustes_match.cache_clear()`). Qué
        # modo rige en cada entorno es precondición de la operación de PR-16.
        await MatchService(repo, proveedor or proveedor_configurado()).puntuar(trabajo)
    except Exception as exc:  # el motivo queda en la fila, no en un log con PII
        # **Un fallo del proveedor no se convierte en un score** (CA13,
        # `SPEC.md:91-93`; F8, `docs/fallas.md:75`). El fallo es nuestro o del
        # proveedor, no un juicio sobre el candidato, así que aquí no hay ninguna
        # de las dos cosas que CA13 permite escribir: ni un score, ni un «sin
        # score» con un motivo que sea información del candidato. Lo que se
        # escribe es el cierre del **trabajo**: `error` con el motivo de la cola.
        #
        # Y por eso no se toca `match_scores`: `guardar_score` **actualiza la
        # fila del par** (`match_repo.py:264-271`, CA9(a)), así que escribir por
        # aquí no solo inventaría un número, también se llevaría el score bueno
        # que el par ya tuviera. Es el incidente 001: 7 pares con `score=0` y
        # `estado="listo"`, que para la vista y para `metricas.scores_por_vacante`
        # son scores de verdad.
        #
        # **Pregunta abierta, de PR-14 y no de aquí:** qué ve el reclutador
        # mientras tanto. Sin fila de score el candidato aparece en «Pendientes
        # de score» por ausencia (CA6, `SPEC.md:63-65`), pero el trabajo sale de
        # `pendiente` y hoy nadie lo re-encola, y la tabla de estados de `PLAN.md`
        # PR-11 quiere la causa transitoria **en `pendiente` con reintentos
        # acotados** y, al agotarlos, en «sin score con motivo técnico»
        # re-encolable. Las dos mitades necesitan el lease y el contador de
        # intentos de PR-14 —dejarlo `pendiente` sin ellos lo haría tomarse en
        # cada pasada y lo metería para siempre en la alerta de >60 min de CA7—,
        # así que este paso no la decide: la deja escrita. Lo único que no
        # negocia CA13 es lo de arriba: ninguna fila de score que nadie calculó.
        _registrar_cierre(
            repo.marcar_trabajo(trabajo.id, "error", motivo=type(exc).__name__[:LARGO_DEL_MOTIVO]),
            comienzo,
        )
        return 1
    _registrar_cierre(repo.marcar_trabajo(trabajo.id, "listo"), comienzo)
    return 1


def _registrar_cierre(trabajo: TrabajoDeMatch, comienzo: float) -> None:
    """**Una línea JSON por trabajo cerrado**, y nada del candidato (F12, CA1, D15).

    Los seis campos son los que `docs/arquitectura.md` §2 autoriza a salir de
    Criba leídos para el camino de escritura: los identificadores que **no** son
    del candidato —el trabajo, la empresa y la vacante—, la decisión (`estado` y
    `motivo`) y la latencia. Ni `candidato_id`, ni correo, ni hash de CV, ni
    score: el score es dato derivado del candidato y en un log no tiene nada que
    hacer, que es la mitad «ni log suyo» de CA1 (R6·M6) y lo que
    `services/listado.py` ya hace en el camino de lectura.

    El `motivo` entra porque está acotado por construcción: o es
    `empresa_sin_activacion`, o es el **nombre del tipo** de la excepción cortado
    a 120 caracteres. Nunca el mensaje: ese es el camino de F12 por el que el
    `stderr` del CLI del proveedor —con el prompt dentro— llega a un archivo.

    `ms` es la latencia **de la pasada**: desde que se toma la fila hasta que se
    cierra. No es la de D16/T2 (CV recibido → score guardado), que necesita el
    `creado_en` del trabajo y se mira en `metricas.trabajos_por_estado`.

    Es `info` y es una sola línea: el ejecutor del staging da vueltas cada pocos
    segundos y un log por pasada vacía no se podría leer. Las pasadas sin trabajo
    no registran nada.
    """
    _log.info(
        json.dumps(
            {
                "evento": EVENTO_DE_CIERRE,
                "trabajo_id": trabajo.id,
                "empresa_id": trabajo.empresa_id,
                "vacante_id": trabajo.vacante_id,
                "estado": trabajo.estado,
                "motivo": trabajo.motivo,
                "ms": round((time.perf_counter() - comienzo) * 1000, 1),
            }
        )
    )


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
