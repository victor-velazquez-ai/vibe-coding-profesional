"""Crea (o actualiza) los roles del agente en el Postgres de desarrollo.

Uso: uv run poe roles
Lee las contraseñas del .env y aplica scripts/roles.sql. Se puede correr las veces que quieras.
"""

import sys
from pathlib import Path

import psycopg
from psycopg import sql

from app.config import get_settings

ROLES = {
    "agente_lectura": "agente_lectura_password",
    "agente_metricas": "agente_metricas_password",
}
SQL_FILE = Path(__file__).with_name("roles.sql")


def main() -> int:
    settings = get_settings()
    conninfo = settings.psycopg_conninfo(settings.postgres_db)
    with psycopg.connect(conninfo, autocommit=True) as conn:
        for role, field in ROLES.items():
            password = getattr(settings, field)
            if not password:
                print(f"Falta {field.upper()} en tu .env (uv run poe init-env lo genera).")
                return 1
            exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
            verb = sql.SQL("ALTER ROLE") if exists else sql.SQL("CREATE ROLE")
            conn.execute(
                sql.SQL("{} {} LOGIN PASSWORD {}").format(
                    verb, sql.Identifier(role), sql.Literal(password)
                )
            )
            print(f"{'actualizado' if exists else 'creado'}: {role}")

        db = sql.Identifier(settings.postgres_db).as_string(conn)
        lines = SQL_FILE.read_text(encoding="utf-8").splitlines()
        script = "\n".join(ln for ln in lines if not ln.strip().startswith("--"))
        for statement in script.split(";"):
            if statement.strip():
                text = statement.strip().replace("{db}", db)
                conn.execute(text.encode())
                print(text + ";")
    return 0


if __name__ == "__main__":
    sys.exit(main())
