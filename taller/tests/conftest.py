import os
import tempfile

import pytest

db_fd, db_path = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()
    os.close(db_fd)
    os.remove(db_path)


def login(client, username: str, password: str) -> str:
    response = client.post("/login", data={"username": username, "password": password})
    response.raise_for_status()
    return response.json()["access_token"]
