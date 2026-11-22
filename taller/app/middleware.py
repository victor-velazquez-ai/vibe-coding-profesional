import re
import time
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import REQUEST_ID_HEADER, get_logger, request_id_var

logger = get_logger("app.request")

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _resolve_request_id(raw: str | None) -> str:
    """Respeta el `X-Request-ID` entrante si es razonable; si no, genera uno."""
    if raw is not None and _SAFE_REQUEST_ID.match(raw):
        return raw
    return uuid.uuid4().hex


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Pone un `request_id` en el contexto, en el log y en la respuesta."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = _resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
        token = request_id_var.set(request_id)
        request.state.request_id = request_id
        started = time.perf_counter()
        context: dict[str, Any] = {"method": request.method, "path": request.url.path}

        try:
            try:
                response = await call_next(request)
            except Exception:
                context["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
                logger.exception("request_failed", extra={"context": context})
                raise
            response.headers[REQUEST_ID_HEADER] = request_id
            context["status_code"] = response.status_code
            context["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
            logger.info("request_completed", extra={"context": context})
            return response
        finally:
            # Se resetea despues de loguear, para que el id siga en el contexto.
            request_id_var.reset(token)
