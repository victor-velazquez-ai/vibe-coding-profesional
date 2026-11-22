"""El request_id y el log JSON son parte del contrato operativo del repo."""

import json
import logging
import uuid

from fastapi.testclient import TestClient

from app.config import get_settings
from app.logging_config import REQUEST_ID_HEADER


def _log_size() -> int:
    path = get_settings().log_file
    return path.stat().st_size if path.exists() else 0


def _log_lines_since(offset: int) -> list[dict[str, object]]:
    for handler in logging.getLogger().handlers:
        handler.flush()
    path = get_settings().log_file
    with path.open("r", encoding="utf-8") as handle:
        handle.seek(offset)
        return [json.loads(line) for line in handle if line.strip()]


def test_response_carries_a_generated_request_id(client: TestClient) -> None:
    response = client.get("/candidates")
    assert response.headers[REQUEST_ID_HEADER]


def test_incoming_request_id_is_respected(client: TestClient) -> None:
    incoming = uuid.uuid4().hex
    response = client.get("/candidates", headers={REQUEST_ID_HEADER: incoming})
    assert response.headers[REQUEST_ID_HEADER] == incoming


def test_garbage_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/candidates", headers={REQUEST_ID_HEADER: "no vale\neste"})
    assert response.headers[REQUEST_ID_HEADER] != "no vale\neste"
    assert response.headers[REQUEST_ID_HEADER]


def test_each_log_line_is_json_and_carries_the_request_id(client: TestClient) -> None:
    offset = _log_size()
    incoming = uuid.uuid4().hex
    client.get("/candidates", headers={REQUEST_ID_HEADER: incoming})

    lines = _log_lines_since(offset)
    assert lines, "no se ha escrito nada en logs/app.log"
    assert all(line.get("request_id") for line in lines)
    assert any(
        line.get("event") == "request_completed" and line.get("request_id") == incoming
        for line in lines
    )
