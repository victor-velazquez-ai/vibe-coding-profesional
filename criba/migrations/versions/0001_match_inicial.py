"""Esquema inicial de Criba Match: scores, cola, auditoría por score y gasto del mes.

Cuatro tablas **nuevas** (`docs/arquitectura.md` §2, ADR-001 §Decisión 1) y el
índice de la vista de vacante, adelantado desde PR-21 porque T1 se mide una vez y
tiene que medir la consulta real (PLAN.md PR-02, R2·I3).

Tres cosas que **no** hace, con el argumento completo en `docs/prs/PR-02.md`:
**ninguna clave ajena declara `ON DELETE CASCADE`** (R3·M2) —con cascada el
borrado de la plataforma se adelanta al gancho de PR-18 y el esquema toma por
Priya la pregunta abierta 3 de `SPEC.md`; con `RESTRICT` falla el borrado—; **no
crea la activación por empresa ni el idioma por omisión** (R4·I1, R3·I3), que
viven en `app/match/configuracion.py` y no en una columna de `empresas` (F16); y
**no añade nada a una tabla de negocio existente**: de `empresas`, `candidatos` y
`vacantes` solo toca las claves ajenas, y crear una FK toma `SHARE ROW EXCLUSIVE`
sobre la referenciada (R6·M5), de ahí el `lock_timeout` de abajo.

Revision ID: 0001_match
Revises: 0000_plataforma
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_match"
down_revision: str | None = "0000_plataforma"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(nombre: str, *valores: str) -> sa.Enum:
    # Como los de la plataforma: VARCHAR con CHECK, no un tipo nativo.
    return sa.Enum(*valores, name=nombre, native_enum=False, length=20, create_constraint=True)


# `listo` con score; `sin_score` con motivo visible y nunca un cero (CA13).
_estado_score = _enum("estado_score", "listo", "sin_score")
_estado_trabajo = _enum("estado_trabajo", "pendiente", "en_curso", "listo", "error")  # ADR-001 §D1
# Separa el gasto de producción del del conjunto dorado de CA14 (PR-13, I5).
_etiqueta_de_uso = _enum("etiqueta_de_uso", "produccion", "calidad")


def _fecha(nombre: str) -> sa.Column:
    """La pone el servidor, no el cliente. Una columna nueva en cada llamada."""
    return sa.Column(nombre, sa.DateTime(True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    # F16 en mecanismo, no en frase: con `candidatos` tomada por una transacción
    # larga, esto falla en 3 s en vez de encolar detrás a 120 reclutadores.
    op.execute("SET lock_timeout = '3s'")

    op.create_table(
        "match_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id"), nullable=False),
        sa.Column("candidato_id", sa.Integer(), sa.ForeignKey("candidatos.id"), nullable=False),
        sa.Column("vacante_id", sa.Integer(), sa.ForeignKey("vacantes.id"), nullable=False),
        # `idioma` en la clave natural desde la primera migración (R2·I4): las
        # razones son por par, pero el idioma es por usuario (D11, CA11). La v1
        # genera una sola fila por par.
        sa.Column("idioma", sa.String(5), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("razones", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("estado", _estado_score, nullable=False),
        sa.Column("motivo_sin_score", sa.String(120), nullable=True),
        _fecha("creado_en"),
        _fecha("actualizado_en"),
        sa.UniqueConstraint(
            "empresa_id", "candidato_id", "vacante_id", "idioma", name="uq_match_scores_par_idioma"
        ),
        # CA13: o hay score, o hay estado «sin score». Nunca un cero en su lugar.
        sa.CheckConstraint(
            "(estado = 'listo') = (score IS NOT NULL)", name="ck_match_scores_estado_coherente"
        ),
        sa.CheckConstraint(
            "score IS NULL OR (score BETWEEN 0 AND 100)", name="ck_match_scores_rango"
        ),
    )
    # El índice de CA5/T1. Tabla nueva: no aplica F16 ni hace falta CONCURRENTLY.
    op.create_index(
        "ix_match_scores_empresa_vacante_score",
        "match_scores",
        ["empresa_id", "vacante_id", "score"],
    )

    op.create_table(
        "match_trabajos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id"), nullable=False),
        sa.Column("candidato_id", sa.Integer(), sa.ForeignKey("candidatos.id"), nullable=False),
        sa.Column("vacante_id", sa.Integer(), sa.ForeignKey("vacantes.id"), nullable=False),
        sa.Column("idioma", sa.String(5), nullable=False),
        sa.Column("estado", _estado_trabajo, nullable=False, server_default="pendiente"),
        sa.Column("motivo", sa.String(120), nullable=True),
        sa.Column("intentos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_vence_en", sa.DateTime(timezone=True), nullable=True),
        # (candidato, vacante, hash de CV, versión de prompt) — ADR-001 §Decisión 3.
        sa.Column("clave_idempotencia", sa.String(160), nullable=False),
        # `lote_recalculo` + `creado_en`: de ahí se deriva el límite de 1
        # recálculo/día/vacante de D23, y PR-23 no necesita migración (R2·M4).
        sa.Column("lote_recalculo", sa.String(60), nullable=True),
        _fecha("creado_en"),
        _fecha("actualizado_en"),
        sa.UniqueConstraint(
            "empresa_id", "clave_idempotencia", name="uq_match_trabajos_idempotencia"
        ),
    )
    # Para el `SELECT … FOR UPDATE SKIP LOCKED` de ADR-001 y la alerta de CA7.
    op.create_index("ix_match_trabajos_estado_creado", "match_trabajos", ["estado", "creado_en"])

    op.create_table(
        "match_auditoria_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id"), nullable=False),
        sa.Column("candidato_id", sa.Integer(), sa.ForeignKey("candidatos.id"), nullable=False),
        sa.Column("vacante_id", sa.Integer(), sa.ForeignKey("vacantes.id"), nullable=False),
        # Hash del CV, no texto: D15 y CA15 prohíben guardar el texto aquí.
        sa.Column("hash_cv", sa.String(64), nullable=False),
        sa.Column("version_prompt", sa.String(40), nullable=False),
        sa.Column("version_modelo", sa.String(80), nullable=False),
        _fecha("creado_en"),
    )
    op.create_index(
        "ix_match_auditoria_empresa_candidato",
        "match_auditoria_scores",
        ["empresa_id", "candidato_id"],
    )

    # Contador transaccional del gasto del mes (D12, CA10, F23). **Sin
    # `empresa_id` a propósito:** el techo de 1.500 USD es de toda la plataforma,
    # así que un contador por empresa no podría dispararlo.
    op.create_table(
        "match_gasto_mes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mes", sa.String(7), nullable=False),  # 'YYYY-MM'
        sa.Column("etiqueta_uso", _etiqueta_de_uso, nullable=False),
        sa.Column("gasto_centavos", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("alerta_80_en", sa.DateTime(timezone=True), nullable=True),
        _fecha("creado_en"),
        _fecha("actualizado_en"),
        sa.UniqueConstraint("mes", "etiqueta_uso", name="uq_match_gasto_mes_etiqueta"),
    )


def downgrade() -> None:
    op.drop_table("match_gasto_mes")
    op.drop_table("match_auditoria_scores")
    op.drop_table("match_trabajos")
    op.drop_table("match_scores")
