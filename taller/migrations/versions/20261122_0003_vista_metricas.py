"""Vista de métricas sin datos personales (para el rol agente_metricas)

Revision ID: 0003_vista_metricas
Revises: 0002_created_at
Create Date: 2026-11-22

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_vista_metricas"
down_revision: str | None = "0002_created_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Solo conteos por empresa y etapa: ni nombres, ni notas, ni salarios.
    op.execute(
        """
        CREATE VIEW metricas_candidatos_por_etapa AS
        SELECT co.name AS empresa, ca.stage AS etapa, count(*) AS total
        FROM candidates ca
        JOIN companies co ON co.id = ca.company_id
        GROUP BY co.name, ca.stage
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS metricas_candidatos_por_etapa")
