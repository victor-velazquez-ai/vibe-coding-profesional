"""Arranca y para el Postgres de desarrollo (docker compose, proyecto `taller`)."""

import subprocess
import sys
import time

import psycopg

from app.config import PROJECT_ROOT, MissingConfigError, get_settings

WAIT_SECONDS = 90
COMPOSE = ["docker", "compose", "-f", str(PROJECT_ROOT / "docker-compose.yml")]


def _compose(*args: str) -> int:
    return subprocess.run([*COMPOSE, *args], cwd=PROJECT_ROOT, check=False).returncode


def _wait_until_ready() -> bool:
    settings = get_settings()
    conninfo = settings.psycopg_conninfo(settings.postgres_db)
    deadline = time.monotonic() + WAIT_SECONDS
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(conninfo, connect_timeout=3):
                return True
        except psycopg.Error as exc:  # todavia arrancando
            last_error = exc
            time.sleep(1)
    print(f"Postgres no respondio en {WAIT_SECONDS}s: {last_error}", file=sys.stderr)
    return False


def up() -> int:
    code = _compose("up", "-d")
    if code != 0:
        return code

    settings = get_settings()
    print(f"Esperando a Postgres en {settings.postgres_host}:{settings.postgres_port}...")
    if not _wait_until_ready():
        return 1
    print(
        f"Postgres 16 listo: base '{settings.postgres_db}' en el puerto {settings.postgres_port}."
    )
    return 0


def down() -> int:
    return _compose("down")


def main(argv: list[str]) -> int:
    command = argv[0] if argv else "up"
    actions = {"up": up, "down": down}
    if command not in actions:
        print(f"Uso: python -m scripts.db [{'|'.join(actions)}]", file=sys.stderr)
        return 2
    try:
        return actions[command]()
    except MissingConfigError as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
