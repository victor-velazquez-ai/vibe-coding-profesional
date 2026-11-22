"""Único punto de acceso a datos de negocio de la plataforma.

No se puede construir sin `empresa_id` y **toda** consulta lo filtra. Es el
mismo patrón que `docs/arquitectura.md` §4 exige para Match; aquí vive el de la
plataforma, y los dos son distintos: Match tiene su propio repositorio
(`app/match/repositories/match_repo.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import ScalarSelect, delete, func, select
from sqlalchemy.orm import Session

from app.plataforma.modelos import (
    ETAPAS_CERRADAS,
    AccesoSoporte,
    Candidato,
    Empresa,
    NotaEntrevista,
    Postulacion,
    Usuario,
    Vacante,
)


@dataclass(frozen=True, slots=True)
class FilaCandidato:
    """Lo que la vista de vacante necesita de un candidato, sin filas crudas."""

    candidato: Candidato
    postulacion: Postulacion
    notas: int


class RepositorioEmpresa:
    """Consultas de negocio de una empresa. El `empresa_id` es obligatorio."""

    def __init__(self, sesion: Session, empresa_id: int) -> None:
        if not empresa_id:
            raise ValueError("El repositorio exige un empresa_id del contexto de la sesión.")
        self._s = sesion
        self._empresa_id = empresa_id

    @property
    def empresa_id(self) -> int:
        return self._empresa_id

    # --- lectura -----------------------------------------------------------

    def empresa(self) -> Empresa | None:
        return self._s.get(Empresa, self._empresa_id)

    def vacantes(self) -> list[Vacante]:
        return list(
            self._s.scalars(
                select(Vacante)
                .where(Vacante.empresa_id == self._empresa_id)
                .order_by(Vacante.creada_en.desc(), Vacante.id.desc())
            )
        )

    def vacante(self, vacante_id: int) -> Vacante | None:
        return self._s.scalars(
            select(Vacante).where(Vacante.id == vacante_id, Vacante.empresa_id == self._empresa_id)
        ).one_or_none()

    def conteo_postulaciones(self, vacante_id: int) -> int:
        return (
            self._s.scalar(
                select(func.count(Postulacion.id)).where(
                    Postulacion.empresa_id == self._empresa_id,
                    Postulacion.vacante_id == vacante_id,
                )
            )
            or 0
        )

    def candidatos_de_vacante(self, vacante_id: int) -> list[FilaCandidato]:
        """La vista de vacante de hoy: candidatos **por fecha de postulación**.

        Una sola consulta, con el conteo de notas como subconsulta correlacionada:
        la plantilla no provoca una consulta por candidato.
        """
        filas = self._s.execute(
            select(Candidato, Postulacion, _conteo_notas())
            .join(Postulacion, Postulacion.candidato_id == Candidato.id)
            .where(
                Postulacion.empresa_id == self._empresa_id,
                Candidato.empresa_id == self._empresa_id,
                Postulacion.vacante_id == vacante_id,
            )
            .order_by(Postulacion.creada_en.desc(), Postulacion.id.desc())
        ).all()
        return [FilaCandidato(candidato=c, postulacion=p, notas=n) for c, p, n in filas]

    def candidato(self, candidato_id: int) -> Candidato | None:
        return self._s.scalars(
            select(Candidato).where(
                Candidato.id == candidato_id, Candidato.empresa_id == self._empresa_id
            )
        ).one_or_none()

    def candidatos_sin_postular_a(self, vacante_id: int) -> list[Candidato]:
        """Candidatos de la empresa que todavía no se postularon a esa vacante."""
        ya = select(Postulacion.candidato_id).where(
            Postulacion.empresa_id == self._empresa_id, Postulacion.vacante_id == vacante_id
        )
        return list(
            self._s.scalars(
                select(Candidato)
                .where(Candidato.empresa_id == self._empresa_id, Candidato.id.not_in(ya))
                .order_by(Candidato.nombre)
            )
        )

    def vacantes_postuladas(self, candidato_id: int) -> set[int]:
        """Las vacantes de esta empresa en cuya lista aparece este candidato.

        Sin filtrar por etapa, a propósito: `candidatos_de_vacante` tampoco lo
        hace, así que una postulación cerrada sigue siendo una fila con su botón
        de borrar.
        """
        return set(
            self._s.scalars(
                select(Postulacion.vacante_id).where(
                    Postulacion.empresa_id == self._empresa_id,
                    Postulacion.candidato_id == candidato_id,
                )
            )
        )

    def postulaciones_abiertas(self, candidato_id: int) -> list[Postulacion]:
        """Las postulaciones vivas de un candidato. PR-06 encola una por cada una."""
        return list(
            self._s.scalars(
                select(Postulacion)
                .where(
                    Postulacion.empresa_id == self._empresa_id,
                    Postulacion.candidato_id == candidato_id,
                    Postulacion.etapa.not_in(ETAPAS_CERRADAS),
                )
                .order_by(Postulacion.id)
            )
        )

    # --- escritura ---------------------------------------------------------

    def guardar_cv(self, candidato_id: int, texto: str) -> Candidato:
        candidato = self.candidato(candidato_id)
        if candidato is None:
            raise SinPermiso(f"El candidato {candidato_id} no es de esta empresa.")
        candidato.cv_texto = texto
        candidato.cv_actualizado_en = datetime.now(UTC)
        self._s.flush()
        return candidato

    def crear_postulacion(self, candidato_id: int, vacante_id: int) -> Postulacion:
        """Crea el par (candidato, vacante). **No sube ningún CV.**"""
        candidato = self.candidato(candidato_id)
        vacante = self.vacante(vacante_id)
        if candidato is None or vacante is None:
            raise SinPermiso("Candidato o vacante de otra empresa.")
        postulacion = Postulacion(
            empresa_id=self._empresa_id, candidato_id=candidato_id, vacante_id=vacante_id
        )
        self._s.add(postulacion)
        self._s.flush()
        return postulacion

    def exigir_vacante_del_borrado(self, candidato_id: int, vacante_id: int) -> None:
        """Comprueba, **antes de borrar**, la vacante desde la que se confirma.

        El formulario de borrado manda un `vacante_id` que afirma «estoy viendo a
        este candidato en esta vacante» (`_candidatos.html`), y hasta hoy nadie
        comprobaba la afirmación: con un `vacante_id` ajeno el borrado se
        ejecutaba igual y la respuesta era un 404 —el reclutador leía «aquí no hay
        nada» y lo que había pasado es que perdió al candidato, su CV y su
        postulación— (QA backend BUG-2, `qa/reportes/2026-11-22-backend.md`).
        `qa/TRIAGE.md` elige, de las dos salidas que la QA aceptaba, **no borrar
        nada y responder 404**.

        La regla, en dos mitades porque el `vacante_id` dice dos cosas distintas
        según el candidato:

        - si el candidato **aparece en alguna lista**, la vacante del formulario
          tiene que ser una de ellas. Es la afirmación falsa del hallazgo: una
          vacante inexistente, otra vacante de la empresa o una de otra empresa;
        - si el candidato **no está postulado a nada**, no hay ninguna lista que
          el formulario pueda estar mirando y lo único que queda por exigir es
          que la vacante sea de esta empresa (CA1), que es de donde sale el
          fragmento de la respuesta. Es el caso de
          `tests/match/test_vacante_no_espera.py`, que borra un candidato sin
          postulaciones desde la vista de la vacante y recibe su lista.
        """
        suyas = self.vacantes_postuladas(candidato_id)
        if vacante_id in suyas:
            return
        if suyas:
            raise SinPermiso(
                f"La vacante {vacante_id} no es ninguna de las postulaciones del candidato "
                f"{candidato_id}: el borrado no se ejecuta."
            )
        if self.vacante(vacante_id) is None:
            raise SinPermiso(f"La vacante {vacante_id} no es de esta empresa.")

    def borrar_candidato(self, candidato_id: int) -> None:
        """El procedimiento de borrado de hoy. Es el gancho que PR-18 va a tocar.

        Orden: notas → postulaciones → candidato. Ninguna FK de la plataforma
        lleva `ON DELETE CASCADE`, así que el orden es explícito y PR-18 puede
        insertar el recorrido de Match **antes** de borrar la fila del candidato
        (PLAN.md PR-02, ronda 3 M2).
        """
        candidato = self.candidato(candidato_id)
        if candidato is None:
            raise SinPermiso(f"El candidato {candidato_id} no es de esta empresa.")
        postulaciones = select(Postulacion.id).where(
            Postulacion.empresa_id == self._empresa_id, Postulacion.candidato_id == candidato_id
        )
        self._s.execute(
            delete(NotaEntrevista).where(
                NotaEntrevista.empresa_id == self._empresa_id,
                NotaEntrevista.postulacion_id.in_(postulaciones),
            )
        )
        self._s.execute(
            delete(Postulacion).where(
                Postulacion.empresa_id == self._empresa_id,
                Postulacion.candidato_id == candidato_id,
            )
        )
        self._s.delete(candidato)
        self._s.flush()


class SinPermiso(Exception):
    """Un ID que no es de la empresa del contexto. Se traduce a 404, nunca a 403."""


def _conteo_notas() -> ScalarSelect[int]:
    return (
        select(func.count(NotaEntrevista.id))
        .where(NotaEntrevista.postulacion_id == Postulacion.id)
        .correlate(Postulacion)
        .scalar_subquery()
    )


# --- consultas sin empresa: solo autenticación y contexto de soporte --------


def usuario_por_nombre(sesion: Session, usuario: str) -> Usuario | None:
    """Login. Es la única lectura legítima sin `empresa_id`: resuelve quién entra."""
    return sesion.scalars(
        select(Usuario).where(Usuario.usuario == usuario, Usuario.activo.is_(True))
    ).one_or_none()


def empresa_por_slug(sesion: Session, slug: str) -> Empresa | None:
    """El staff de Criba elige empresa al entrar. Solo para abrir contexto de soporte."""
    return sesion.scalars(select(Empresa).where(Empresa.slug == slug)).one_or_none()


def empresas(sesion: Session) -> list[Empresa]:
    return list(sesion.scalars(select(Empresa).order_by(Empresa.nombre)))


def registrar_acceso_soporte(
    sesion: Session, usuario_id: int, empresa_id: int, motivo: str
) -> AccesoSoporte:
    """D6: cada acceso del staff de Criba a una empresa queda auditado."""
    acceso = AccesoSoporte(
        usuario_id=usuario_id, empresa_id=empresa_id, motivo=motivo[:200] or "soporte"
    )
    sesion.add(acceso)
    sesion.flush()
    return acceso
