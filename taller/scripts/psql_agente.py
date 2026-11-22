"""psql con la identidad del agente, dentro del contenedor de Postgres.

Uso: uv run poe psql-agente -c "SELECT ..."          (rol agente_lectura)
     uv run poe psql-agente --metricas -c "SELECT ..."  (rol agente_metricas)

La contraseña sale de tu .env y viaja por una variable de entorno: tu agente nunca la ve.
"""

import os
import subprocess
import sys

from app.config import get_settings

CONTAINER = "taller-db"


def main(argv: list[str]) -> int:
    settings = get_settings()
    role, field = "agente_lectura", "agente_lectura_password"
    if "--metricas" in argv:
        argv = [a for a in argv if a != "--metricas"]
        role, field = "agente_metricas", "agente_metricas_password"
    password = getattr(settings, field)
    if not password:
        print(f"Falta {field.upper()} en tu .env. Corre: uv run poe init-env && uv run poe roles")
        return 1
    cmd = [
        "docker", "exec", "-i", "-e", "PGPASSWORD", CONTAINER,
        "psql", "-h", "127.0.0.1", "-U", role, "-d", settings.postgres_db,
        "-v", "ON_ERROR_STOP=1", *argv,
    ]  # fmt: skip
    return subprocess.run(cmd, env={**os.environ, "PGPASSWORD": password}).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
