"""El tipo `PayloadPseudonimizado`.

Es la frontera: el cliente real no acepta otra cosa, así que no hay camino corto
que se la salte (PR-08, CA2, `docs/arquitectura.md` §5.4).

El escenario que este módulo tiene que hacer imposible es el de §5.4: «enero,
presión de demo, alguien añade un segundo prompt para re-puntuar y llama al
cliente directo porque es más corto». Contra eso hacen falta **tres** cosas a la
vez, y ninguna sirve sola:

1. **el tipo**, que `Proveedor.puntuar` y toda implementación anotan — se ve al
   escribir el segundo prompt, aunque `poe check` no tenga comprobador de tipos;
2. **el rechazo en ejecución**, `exigir_payload`, que es el que de verdad corta —
   una anotación no es un control;
3. **el constructor privado**: un tipo que cualquiera pueda construir es
   «pseudonimizado» por declaración, y entonces 1 y 2 solo piden una línea más.

El 3 se cierra sin lista blanca de llamadores (`PLAN.md` §2, R3·I1): quien quiera
un payload tiene que **pasar por la única fábrica**, que es la función que se
decora con `unica_fabrica` —`services/pseudonimizador.py::pseudonimizar`— y que
este módulo deja registrar **una sola vez**. Una segunda fábrica no es un `# TODO`
en una lista de excepciones: es un `FronteraViolada` al importar.
"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps


class FronteraViolada(RuntimeError):
    """Algo intentó cruzar la frontera de CA2 sin pasar por el pseudonimizador.

    Es un error y no un aviso: lo que está del otro lado es una llamada a un
    proveedor externo, y de eso **no hay recuperación hacia atrás** (`PLAN.md`
    PR-08 §Riesgo, F2, F6). Nunca lleva el texto del CV en el mensaje (D15, F12).
    """


# Verdadero solo dentro de la fábrica única. `ContextVar` y no una bandera de
# módulo porque el ejecutor pasa a ser concurrente en PR-14: con un `bool` global,
# una tarea sellando su payload abriría la puerta a las demás.
_SELLANDO: ContextVar[bool] = ContextVar("criba_match_sellando", default=False)

# La fábrica registrada, por nombre y no por identidad: así volver a importar el
# módulo no cuenta como una segunda fábrica, y una **de verdad** sí.
_FABRICA: str | None = None


def unica_fabrica[**P, T](funcion: Callable[P, T]) -> Callable[P, T]:
    """Marca la **única** función autorizada a construir payloads.

    Lo que hace: dentro de su llamada —y solo ahí— el constructor de
    `PayloadPseudonimizado` deja de fallar. Fuera, falla siempre.
    """
    global _FABRICA
    nombre = f"{funcion.__module__}.{funcion.__qualname__}"
    if _FABRICA is not None and nombre != _FABRICA:
        raise FronteraViolada(
            f"La frontera de CA2 admite una sola fábrica de payloads y ya está registrada "
            f"«{_FABRICA}»: «{nombre}» sería una segunda puerta. El cuerpo que sale de Criba "
            "se construye en app/match/services/pseudonimizador.py y en ningún otro sitio."
        )
    _FABRICA = nombre

    @wraps(funcion)
    def envoltura(*args: P.args, **kwargs: P.kwargs) -> T:
        ficha = _SELLANDO.set(True)
        try:
            return funcion(*args, **kwargs)
        finally:
            _SELLANDO.reset(ficha)

    return envoltura


@dataclass(frozen=True, slots=True)
class PayloadPseudonimizado:
    """El cuerpo que sale de Criba, ya sin ninguno de los seis datos de §1a.

    `frozen=True` para que nadie le vuelva a meter el CV crudo después de
    construirlo, y constructor privado para que «pseudonimizado» no sea una
    declaración de quien llama.

    `sustituciones` no es decoración: es el número que `PLAN.md` PR-08 pide por CV
    de fixture en el cuerpo del PR —cuánto se quitó— porque limpiar por patrón
    puede **quitar de más** y eso degrada el texto que decide el score (F1). Quién
    mide ese daño es CA14 sobre el conjunto dorado (PR-17).
    """

    cv: str
    sustituciones: int

    def __post_init__(self) -> None:
        if not _SELLANDO.get():
            raise FronteraViolada(
                "PayloadPseudonimizado no se construye a mano: se obtiene de "
                "app.match.services.pseudonimizador.pseudonimizar(candidato). Un payload "
                "construido fuera de la fábrica sería «pseudonimizado» por declaración y no "
                "por conducta (CA2, docs/arquitectura.md §5.4, F6)."
            )


def exigir_payload(payload: object) -> PayloadPseudonimizado:
    """El rechazo en ejecución, en un solo sitio.

    Lo llama **toda** implementación de `Proveedor` como primera línea de
    `puntuar` —el MOCK hoy, el cliente real de PR-09 mañana—, y por eso el
    recorrido de implementaciones del test de CA2 está enumerado y no escrito a
    mano: el cliente que PR-09 añada entra en el control sin tocar nada.
    """
    if not isinstance(payload, PayloadPseudonimizado):
        raise FronteraViolada(
            f"Al proveedor solo se le pasa un PayloadPseudonimizado y llegó un "
            f"{type(payload).__name__}. Nada identificable sale de Criba (CA2, D3 modificado "
            "§1a): el cuerpo se construye en services/pseudonimizador.py."
        )
    return payload
