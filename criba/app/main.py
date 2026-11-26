"""Punto de entrada: `uv run python -m uvicorn app.main:app --reload`.

En el staging, con la configuración de producción:

    uv run --env-file staging/staging.env python -m uvicorn app.main:app --port 8001

`configurar_logs` va aquí y no en `crear_app()` a propósito: toca el logger raíz
del **proceso**, y `crear_app()` lo llaman también la suite y el E2E, que traen su
propia captura de logs (`caplog`). Lo que configura el arranque de un proceso se
configura en el punto de entrada del proceso. Sin `CRIBA_LOG_DIR` no escribe
ningún archivo (`app/registro.py`).
"""

from __future__ import annotations

from app.fabrica import crear_app
from app.registro import configurar_logs

configurar_logs("app")

app = crear_app()
