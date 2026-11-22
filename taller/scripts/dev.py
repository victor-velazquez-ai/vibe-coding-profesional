"""Servidor de desarrollo en segundo plano, con pidfile.

`start` es idempotente: si ya hay un servidor vivo, no lanza otro, solo informa
del pid y la URL. Funciona igual en Windows, macOS y Linux.
"""

import contextlib
import json
import os
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

import psutil

from app.config import PROJECT_ROOT, MissingConfigError, get_settings

RUN_DIR = PROJECT_ROOT / ".run"
PIDFILE = RUN_DIR / "dev.pid"
SERVER_LOG = PROJECT_ROOT / "logs" / "server.log"
APP_LOG = PROJECT_ROOT / "logs" / "app.log"
LOG_TAIL_LINES = 40
STOP_TIMEOUT = 10


def _read_pidfile() -> dict[str, object] | None:
    if not PIDFILE.exists():
        return None
    try:
        data = json.loads(PIDFILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _running_process() -> tuple[psutil.Process, dict[str, object]] | None:
    """Proceso vivo del pidfile, o None (limpiando el pidfile si es basura)."""
    data = _read_pidfile()
    if data is None:
        return None
    pid = data.get("pid")
    if not isinstance(pid, int):
        PIDFILE.unlink(missing_ok=True)
        return None
    try:
        process = psutil.Process(pid)
        # El pid se puede reutilizar: comprobamos que el proceso sea el nuestro.
        if process.create_time() != data.get("create_time"):
            raise psutil.NoSuchProcess(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        PIDFILE.unlink(missing_ok=True)
        return None
    return process, data


def _url(data: dict[str, object]) -> str:
    return f"http://{data.get('host')}:{data.get('port')}"


def _spawn(host: str, port: int, log_file: Path) -> subprocess.Popen[bytes]:
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    creation_flags = 0
    start_new_session = False
    if os.name == "nt":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        start_new_session = True

    with log_file.open("ab") as handle:
        return subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            stdout=handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=creation_flags,
            start_new_session=start_new_session,
        )


def start() -> int:
    existing = _running_process()
    if existing is not None:
        _, data = existing
        print(f"El servidor ya esta corriendo: pid {data['pid']} en {_url(data)}")
        return 0

    settings = get_settings()
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    SERVER_LOG.parent.mkdir(parents=True, exist_ok=True)

    process = _spawn(settings.app_host, settings.app_port, SERVER_LOG)
    time.sleep(1.5)  # margen para que falle rapido si el puerto esta ocupado
    if process.poll() is not None:
        print(
            f"El servidor murio al arrancar (codigo {process.returncode}). Mira {SERVER_LOG}",
            file=sys.stderr,
        )
        return 1

    PIDFILE.write_text(
        json.dumps(
            {
                "pid": process.pid,
                "create_time": psutil.Process(process.pid).create_time(),
                "host": settings.app_host,
                "port": settings.app_port,
            }
        ),
        encoding="utf-8",
    )
    print(
        f"Servidor arrancado: pid {process.pid} en http://{settings.app_host}:{settings.app_port}"
    )
    print(f"Logs de la app: {APP_LOG}  |  salida del servidor: {SERVER_LOG}")
    return 0


def stop() -> int:
    existing = _running_process()
    if existing is None:
        print("No hay ningun servidor corriendo.")
        return 0

    process, data = existing
    targets = [*process.children(recursive=True), process]
    for target in targets:
        with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            target.terminate()

    _, alive = psutil.wait_procs(targets, timeout=STOP_TIMEOUT)
    for target in alive:
        with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            target.kill()

    PIDFILE.unlink(missing_ok=True)
    print(f"Servidor parado (pid {data['pid']}).")
    return 0


def status() -> int:
    existing = _running_process()
    if existing is None:
        print("Parado. Arrancalo con: uv run poe dev")
        return 1
    _, data = existing
    print(f"Corriendo: pid {data['pid']} en {_url(data)}")
    return 0


def logs() -> int:
    if not APP_LOG.exists():
        print(f"Todavia no hay log en {APP_LOG}.")
        return 0
    with APP_LOG.open("r", encoding="utf-8", errors="replace") as handle:
        tail = deque(handle, maxlen=LOG_TAIL_LINES)
    sys.stdout.writelines(tail)
    return 0


def main(argv: list[str]) -> int:
    command = argv[0] if argv else "status"
    actions = {"start": start, "stop": stop, "status": status, "logs": logs}
    if command not in actions:
        print(f"Uso: python -m scripts.dev [{'|'.join(actions)}]", file=sys.stderr)
        return 2
    try:
        return actions[command]()
    except MissingConfigError as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
