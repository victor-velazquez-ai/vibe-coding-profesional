"""El contexto de empresa de Match, sus cuatro constructores y el contexto de
sistema enumerado (PR-04; D4, CA1, `docs/arquitectura.md` §4 y §5.3, [03:25]).

El `empresa_id` **nunca es argumento de un llamador**: sale de la cookie de la
petición (`ContextoEmpresa` de la plataforma), de la fila del trabajo ya tomada,
de la fila de la vacante o de la fila del candidato. Los cuatro constructores
reciben **la sesión de la petición** y ninguno hace `commit()`: el commit sigue
siendo de la ruta (R6·I2).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.match.repositories.modelos import TrabajoDeMatch
from app.plataforma.modelos import Candidato, Vacante
from app.plataforma.sesion import ContextoEmpresa


class SinContexto(Exception):
    """Sin contexto de empresa, o con el de otra empresa.

    La ruta la traduce a **404, nunca a 403**: un ID de otra empresa no existe,
    igual que `SinPermiso` en la plataforma (`docs/arquitectura.md` §4).
    """


class Origen(StrEnum):
    """De dónde salió el `empresa_id`. Cuatro, y se ven en el diff."""

    PETICION = "peticion"
    TRABAJO = "trabajo"
    VACANTE = "vacante"
    CANDIDATO = "candidato"


class OperacionDeSistema(StrEnum):
    """Las **tres** operaciones de Match que son por naturaleza sin empresa (I1).

    (a) tomar el siguiente trabajo —todavía no se sabe de qué empresa es—,
    (b) la reconciliación de leases y la alerta de pendientes >60 min (CA7) y
    (c) el contador de gasto (D12 es un techo de toda la plataforma).

    Añadir una cuarta es un cambio visible en este diff, no un argumento en una
    revisión. Enumerar candidatos de una vacante **no** es una de ellas: es una
    lectura con empresa (R4·M3).
    """

    TOMAR_TRABAJO = "tomar_trabajo"
    RECONCILIAR = "reconciliar"
    GASTO = "gasto"


@dataclass(frozen=True, slots=True)
class ContextoDeSistema:
    """Tipo propio y explícito: ni `None`, ni un valor por omisión, ni un vacío."""

    operacion: OperacionDeSistema


@dataclass(frozen=True, slots=True)
class ContextoDeEmpresa:
    """El `empresa_id` con el que se construye el repositorio, y de dónde salió."""

    empresa_id: int
    origen: Origen
    es_soporte: bool = False

    def __post_init__(self) -> None:
        if not self.empresa_id:
            raise SinContexto("Un contexto de empresa de Match sin `empresa_id` no se construye.")

    @classmethod
    def desde_la_peticion(cls, contexto: ContextoEmpresa) -> ContextoDeEmpresa:
        """La cookie de la plataforma, que es también la del soporte.

        El staff de Criba elige empresa al entrar, queda la fila en
        `accesos_soporte` y la cookie queda atada a esa empresa (D6, hecho 3 de
        PR-01). Así el soporte entra por el mismo camino que un reclutador: no
        hace falta una cuarta operación de sistema ni la empresa en la URL.
        """
        return cls(contexto.empresa_id, Origen.PETICION, contexto.es_soporte)

    @classmethod
    def desde_el_trabajo(cls, bd: Session, trabajo_id: int) -> ContextoDeEmpresa:
        """La fila del trabajo **ya tomada** (F5, `docs/arquitectura.md` §5.3)."""
        trabajo = bd.scalars(
            select(TrabajoDeMatch).where(TrabajoDeMatch.id == trabajo_id)
        ).one_or_none()
        if trabajo is None:
            raise SinContexto(f"No hay trabajo {trabajo_id} del que tomar la empresa.")
        return cls(trabajo.empresa_id, Origen.TRABAJO)

    @classmethod
    def desde_la_vacante(
        cls, bd: Session, vacante_id: int, candidato_id: int | None = None
    ) -> ContextoDeEmpresa:
        """Para el gancho de subida de CV, que corre **antes** de que exista la
        fila de la cola y puede no tener sesión de empresa (R2·I5).

        Con `candidato_id`, comprueba que el candidato sea de la **misma** empresa
        que la vacante y falla si no. Sobre este contexto evalúa PR-10 la
        activación de D7.
        """
        vacante = bd.get(Vacante, vacante_id)
        if vacante is None:
            raise SinContexto(f"No hay vacante {vacante_id} de la que tomar la empresa.")
        if candidato_id is not None:
            candidato = bd.get(Candidato, candidato_id)
            if candidato is None or candidato.empresa_id != vacante.empresa_id:
                raise SinContexto(
                    f"El candidato {candidato_id} no es de la empresa de la vacante {vacante_id}."
                )
        return cls(vacante.empresa_id, Origen.VACANTE)

    @classmethod
    def desde_el_candidato(cls, bd: Session, candidato_id: int) -> ContextoDeEmpresa:
        """El que necesita el recorrido de CA16: sin vacante y sin cookie (R6·I3)."""
        candidato = bd.get(Candidato, candidato_id)
        if candidato is None:
            raise SinContexto(f"No hay candidato {candidato_id} del que tomar la empresa.")
        return cls(candidato.empresa_id, Origen.CANDIDATO)
