"""Los modelos SQLAlchemy de las tablas `match_*` (PR-02).

Viven **bajo `repositories/` a propósito** (PLAN.md §2, R3·I1): así la regla (a)
del test de enumeración de PR-04 los cubre **por ruta** y no por nombre. Las
columnas son las de `migrations/versions/0001_match_inicial.py`, que sigue siendo
la dueña del esquema: aquí nadie hace `create_all`.

`estado` y `etiqueta_uso` se mapean como texto porque en la base son VARCHAR con
CHECK (`native_enum=False`), igual que en la plataforma.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, MappedColumn, mapped_column

from app.db import Base


def _ahora() -> MappedColumn[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ScoreDeMatch(Base):
    """Un score por (empresa, candidato, vacante, **idioma**) — R2·I4."""

    __tablename__ = "match_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    candidato_id: Mapped[int] = mapped_column(ForeignKey("candidatos.id"), nullable=False)
    vacante_id: Mapped[int] = mapped_column(ForeignKey("vacantes.id"), nullable=False)
    idioma: Mapped[str] = mapped_column(String(5), nullable=False)
    score: Mapped[int | None] = mapped_column(nullable=True)
    razones: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    motivo_sin_score: Mapped[str | None] = mapped_column(String(120), nullable=True)
    creado_en: Mapped[datetime] = _ahora()
    actualizado_en: Mapped[datetime] = _ahora()


class TrabajoDeMatch(Base):
    """Una fila de la cola en Postgres (ADR-001 §Decisión 1)."""

    __tablename__ = "match_trabajos"

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    candidato_id: Mapped[int] = mapped_column(ForeignKey("candidatos.id"), nullable=False)
    vacante_id: Mapped[int] = mapped_column(ForeignKey("vacantes.id"), nullable=False)
    idioma: Mapped[str] = mapped_column(String(5), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente")
    motivo: Mapped[str | None] = mapped_column(String(120), nullable=True)
    intentos: Mapped[int] = mapped_column(nullable=False, default=0)
    lease_vence_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clave_idempotencia: Mapped[str] = mapped_column(String(160), nullable=False)
    lote_recalculo: Mapped[str | None] = mapped_column(String(60), nullable=True)
    creado_en: Mapped[datetime] = _ahora()
    actualizado_en: Mapped[datetime] = _ahora()


class GastoDelMes(Base):
    """Contador del gasto de **toda la plataforma** (D12, CA10): sin `empresa_id`."""

    __tablename__ = "match_gasto_mes"

    id: Mapped[int] = mapped_column(primary_key=True)
    mes: Mapped[str] = mapped_column(String(7), nullable=False)
    etiqueta_uso: Mapped[str] = mapped_column(String(20), nullable=False)
    gasto_centavos: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    alerta_80_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    creado_en: Mapped[datetime] = _ahora()
    actualizado_en: Mapped[datetime] = _ahora()
