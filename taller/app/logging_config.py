"""Logs estructurados: una linea JSON por evento en `logs/app.log`.

El `request_id` viaja en un ContextVar que planta el middleware, asi que
cualquier log emitido durante una peticion lo lleva sin pasarlo a mano.
"""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from app.config import get_settings

REQUEST_ID_HEADER = "X-Request-ID"
NO_REQUEST_ID = "-"

request_id_var: ContextVar[str] = ContextVar("request_id", default=NO_REQUEST_ID)

_configured = False


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "request_id": getattr(record, "request_id", NO_REQUEST_ID),
        }
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload.update(context)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # ensure_ascii=False para no destrozar los acentos; default=str por si
        # alguien mete un objeto raro en el contexto.
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    """Idempotente: se puede llamar varias veces sin duplicar handlers."""
    global _configured
    if _configured:
        return

    settings = get_settings()
    settings.log_dir.mkdir(parents=True, exist_ok=True)

    handler = logging.FileHandler(settings.log_file, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    root.addHandler(handler)

    # Los eventos de ciclo de vida de uvicorn tambien van al log JSON.
    # `uvicorn.access` se queda fuera a proposito: se emite cuando el
    # middleware ya ha soltado el contexto (iria sin request_id) y duplica el
    # evento `request_completed`, que si lo lleva.
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).propagate = True

    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
