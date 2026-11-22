"""Candidatos: created_at con zona horaria (timestamptz)

Revision ID: 0004_created_at_tz
Revises: 0003_vista_metricas
Create Date: 2026-11-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_created_at_tz"
down_revision: str | None = "0003_vista_metricas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "candidates",
        "created_at",
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )


def downgrade() -> None:
    op.alter_column(
        "candidates",
        "created_at",
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
