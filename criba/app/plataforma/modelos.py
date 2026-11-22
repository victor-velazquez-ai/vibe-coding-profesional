"""Modelos de la plataforma de Criba.

Réplica mínima fiel a `docs/contexto.md`: toda tabla de negocio lleva `empresa_id`
y la sesión del usuario está atada a una empresa.

Lo que esta réplica fija, y que PR-01 anota en su cuerpo:
- el **CV cuelga del candidato** (`candidatos.cv_texto`), no de la postulación;
- una **postulación no sube CV**: se crea con el CV que el candidato ya tenga;
- el **staff de Criba** no pertenece a ninguna empresa (`usuarios.empresa_id` nulo)
  y entra a los datos de una empresa por un **contexto de soporte** que deja fila
  en `accesos_soporte` (D6);
- **no existe** ni «idioma por omisión de la empresa» ni «Match activado por
  empresa»: `empresas` solo tiene nombre y slug.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, MappedColumn, mapped_column, relationship

from app.db import Base


class Rol(StrEnum):
    """Los cuatro roles de `docs/contexto.md`."""

    RECLUTADOR = "reclutador"
    ADMIN_EMPRESA = "admin_empresa"
    HIRING_MANAGER = "hiring_manager"
    STAFF_CRIBA = "staff_criba"


class Etapa(StrEnum):
    """Etapas de una postulación. Las dos últimas la cierran."""

    POSTULADA = "postulada"
    EN_PROCESO = "en_proceso"
    ENTREVISTA = "entrevista"
    OFERTA = "oferta"
    CONTRATADA = "contratada"
    RECHAZADA = "rechazada"


ETAPAS_CERRADAS = frozenset({Etapa.CONTRATADA, Etapa.RECHAZADA})


def _valores(enumeracion: type[StrEnum]) -> list[str]:
    """Guarda el *valor* del enum ('reclutador'), no su nombre ('RECLUTADOR')."""
    return [miembro.value for miembro in enumeracion]


_rol = Enum(
    Rol,
    name="rol_usuario",
    native_enum=False,
    length=20,
    validate_strings=True,
    values_callable=_valores,
)
_etapa = Enum(
    Etapa,
    name="etapa_postulacion",
    native_enum=False,
    length=20,
    validate_strings=True,
    values_callable=_valores,
)


def _ahora() -> MappedColumn[datetime]:
    """Columna de fecha de creación: la pone el servidor, no el cliente."""
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    creada_en: Mapped[datetime] = _ahora()


class Usuario(Base):
    """Un usuario pertenece a una empresa, salvo el staff de Criba (`empresa_id` nulo)."""

    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint(
            "(rol = 'staff_criba') = (empresa_id IS NULL)",
            name="ck_usuarios_staff_sin_empresa",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), nullable=True)
    usuario: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    rol: Mapped[Rol] = mapped_column(_rol, nullable=False)
    hash_contrasena: Mapped[str] = mapped_column(String(255), nullable=False)
    activo: Mapped[bool] = mapped_column(nullable=False, default=True)
    creado_en: Mapped[datetime] = _ahora()

    empresa: Mapped[Empresa | None] = relationship(lazy="joined")


class Vacante(Base):
    __tablename__ = "vacantes"
    __table_args__ = (Index("ix_vacantes_empresa", "empresa_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    titulo: Mapped[str] = mapped_column(String(160), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ciudad: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    creada_en: Mapped[datetime] = _ahora()


class Candidato(Base):
    """El CV vive aquí, en el candidato: una subida de CV sirve a todas sus postulaciones."""

    __tablename__ = "candidatos"
    __table_args__ = (
        Index("ix_candidatos_empresa", "empresa_id"),
        UniqueConstraint("empresa_id", "correo", name="uq_candidatos_empresa_correo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    correo: Mapped[str] = mapped_column(String(160), nullable=False)
    telefono: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    links: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    cv_texto: Mapped[str | None] = mapped_column(Text, nullable=True)
    cv_actualizado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    creado_en: Mapped[datetime] = _ahora()

    @property
    def tiene_cv(self) -> bool:
        return bool(self.cv_texto and self.cv_texto.strip())


class Postulacion(Base):
    __tablename__ = "postulaciones"
    __table_args__ = (
        UniqueConstraint("empresa_id", "candidato_id", "vacante_id", name="uq_postulacion"),
        Index("ix_postulaciones_empresa_vacante", "empresa_id", "vacante_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    candidato_id: Mapped[int] = mapped_column(ForeignKey("candidatos.id"), nullable=False)
    vacante_id: Mapped[int] = mapped_column(ForeignKey("vacantes.id"), nullable=False)
    etapa: Mapped[Etapa] = mapped_column(_etapa, nullable=False, default=Etapa.POSTULADA)
    creada_en: Mapped[datetime] = _ahora()

    @property
    def esta_abierta(self) -> bool:
        return self.etapa not in ETAPAS_CERRADAS


class NotaEntrevista(Base):
    __tablename__ = "notas_entrevista"
    __table_args__ = (Index("ix_notas_empresa_postulacion", "empresa_id", "postulacion_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    postulacion_id: Mapped[int] = mapped_column(ForeignKey("postulaciones.id"), nullable=False)
    autor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    creada_en: Mapped[datetime] = _ahora()


class AccesoSoporte(Base):
    """Auditoría del acceso de staff de Criba a los datos de una empresa (D6).

    Es anterior a Match y es el mecanismo que PR-04 reusa como origen del
    contexto de soporte. No es `auditoria_accesos` de PR-19, que audita el
    acceso a scores.
    """

    __tablename__ = "accesos_soporte"
    __table_args__ = (Index("ix_accesos_soporte_empresa", "empresa_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    motivo: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    creado_en: Mapped[datetime] = _ahora()
