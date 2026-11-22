"""Esquema inicial de la plataforma de Criba (réplica mínima).

Toda tabla de negocio lleva `empresa_id` (D4). Ninguna clave ajena declara
`ON DELETE CASCADE`: el borrado de un candidato se hace por el procedimiento de
la plataforma, en orden explícito, que es donde PR-18 se engancha.

Revision ID: 0000_plataforma
Revises:
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0000_plataforma"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = ("reclutador", "admin_empresa", "hiring_manager", "staff_criba")
ETAPAS = ("postulada", "en_proceso", "entrevista", "oferta", "contratada", "rechazada")

_rol = sa.Enum(*ROLES, name="rol_usuario", native_enum=False, length=20, create_constraint=True)
_etapa = sa.Enum(
    *ETAPAS, name="etapa_postulacion", native_enum=False, length=20, create_constraint=True
)


def upgrade() -> None:
    op.create_table(
        "empresas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(60), nullable=False, unique=True),
        sa.Column(
            "creada_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id"), nullable=True),
        sa.Column("usuario", sa.String(60), nullable=False, unique=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("rol", _rol, nullable=False),
        sa.Column("hash_contrasena", sa.String(255), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(rol = 'staff_criba') = (empresa_id IS NULL)",
            name="ck_usuarios_staff_sin_empresa",
        ),
    )

    op.create_table(
        "vacantes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id"), nullable=False),
        sa.Column("titulo", sa.String(160), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("ciudad", sa.String(80), nullable=False),
        sa.Column(
            "creada_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_vacantes_empresa", "vacantes", ["empresa_id"])

    op.create_table(
        "candidatos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id"), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("correo", sa.String(160), nullable=False),
        sa.Column("telefono", sa.String(40), nullable=False),
        sa.Column("links", postgresql.JSONB(), nullable=False),
        sa.Column("cv_texto", sa.Text(), nullable=True),
        sa.Column("cv_actualizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("empresa_id", "correo", name="uq_candidatos_empresa_correo"),
    )
    op.create_index("ix_candidatos_empresa", "candidatos", ["empresa_id"])

    op.create_table(
        "postulaciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id"), nullable=False),
        sa.Column("candidato_id", sa.Integer(), sa.ForeignKey("candidatos.id"), nullable=False),
        sa.Column("vacante_id", sa.Integer(), sa.ForeignKey("vacantes.id"), nullable=False),
        sa.Column("etapa", _etapa, nullable=False),
        sa.Column(
            "creada_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("empresa_id", "candidato_id", "vacante_id", name="uq_postulacion"),
    )
    op.create_index(
        "ix_postulaciones_empresa_vacante", "postulaciones", ["empresa_id", "vacante_id"]
    )

    op.create_table(
        "notas_entrevista",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id"), nullable=False),
        sa.Column(
            "postulacion_id", sa.Integer(), sa.ForeignKey("postulaciones.id"), nullable=False
        ),
        sa.Column("autor_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column(
            "creada_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_notas_empresa_postulacion", "notas_entrevista", ["empresa_id", "postulacion_id"]
    )

    op.create_table(
        "accesos_soporte",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id"), nullable=False),
        sa.Column("motivo", sa.String(200), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_accesos_soporte_empresa", "accesos_soporte", ["empresa_id"])


def downgrade() -> None:
    op.drop_table("accesos_soporte")
    op.drop_table("notas_entrevista")
    op.drop_table("postulaciones")
    op.drop_table("candidatos")
    op.drop_table("vacantes")
    op.drop_table("usuarios")
    op.drop_table("empresas")
