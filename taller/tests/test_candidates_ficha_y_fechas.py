"""Issue #6: ficha del candidato (GET /candidates/{id}) y filtro por fecha de alta."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.database import get_sessionmaker
from app.models import Candidate
from tests.conftest import login

AUSTIN = ZoneInfo("America/Chicago")


def _headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, username, password)}"}


def _crear(
    client: TestClient, headers: dict[str, str], name: str, notes: str = ""
) -> dict[str, object]:
    response = client.post(
        "/candidates",
        json={
            "name": name,
            "position": "Planificadora de demanda",
            "stage": "Aplicó",
            "notes": notes,
        },
        headers=headers,
    )
    assert response.status_code == 201
    candidate: dict[str, object] = response.json()
    return candidate


def test_ficha_devuelve_el_candidato_de_mi_empresa(client: TestClient) -> None:
    sofia = _headers(client, "sofia", "sofia1234")
    creado = _crear(client, sofia, "Rosa Medina")

    response = client.get(f"/candidates/{creado['id']}", headers=sofia)

    assert response.status_code == 200
    assert response.json()["name"] == "Rosa Medina"


def test_ficha_de_otra_empresa_devuelve_404(client: TestClient) -> None:
    """Revisión, error 2: el test original pedía el id 99999, que no existe.

    Pasaba aunque la ruta no existiera. Aquí el candidato SÍ existe, pero es de Meridian.
    """
    sofia = _headers(client, "sofia", "sofia1234")
    marcus = _headers(client, "marcus", "marcus1234")
    creado = _crear(client, sofia, "Elena Ruiz", notes="pide 95 mil dólares; confidencial")

    response = client.get(f"/candidates/{creado['id']}", headers=marcus)

    assert response.status_code == 404
    assert "confidencial" not in response.text


def test_ficha_sin_token_devuelve_401(client: TestClient) -> None:
    response = client.get("/candidates/1")

    assert response.status_code == 401


def test_filtro_por_fecha_usa_el_dia_de_austin_con_ambos_extremos_incluidos(
    client: TestClient,
) -> None:
    """Revisión, error 3: las fechas son días de Austin y `created_to` se incluye completo."""
    sofia = _headers(client, "sofia", "sofia1234")
    creado = _crear(client, sofia, "Iván Torres")
    # 21-nov a las 23:30 en Austin = 22-nov a las 05:30 UTC. Para la reclutadora, es del 21.
    with get_sessionmaker()() as db:
        candidato = db.get(Candidate, creado["id"])
        assert candidato is not None
        candidato.created_at = datetime(2026, 11, 21, 23, 30, tzinfo=AUSTIN)
        db.commit()

    def ids(desde: str, hasta: str) -> list[object]:
        response = client.get(
            "/candidates",
            params={"created_from": desde, "created_to": hasta},
            headers=sofia,
        )
        assert response.status_code == 200
        return [c["id"] for c in response.json()]

    assert creado["id"] in ids("2026-11-21", "2026-11-21")
    assert creado["id"] not in ids("2026-11-22", "2026-11-22")


def test_filtro_por_fecha_sin_candidatos_devuelve_lista_vacia(client: TestClient) -> None:
    sofia = _headers(client, "sofia", "sofia1234")

    response = client.get(
        "/candidates",
        params={"created_from": "2020-01-01", "created_to": "2020-01-31"},
        headers=sofia,
    )

    assert response.status_code == 200
    assert response.json() == []
