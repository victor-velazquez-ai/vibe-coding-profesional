"""Issue #6: ficha del candidato (GET /candidates/{id}) y filtro por fecha de alta."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tests.conftest import login


def _headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, username, password)}"}


def _crear(client: TestClient, headers: dict[str, str], name: str) -> dict[str, object]:
    response = client.post(
        "/candidates",
        json={"name": name, "position": "Planificadora de demanda", "stage": "Aplicó"},
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
    marcus = _headers(client, "marcus", "marcus1234")

    response = client.get("/candidates/99999", headers=marcus)

    assert response.status_code == 404


def test_ficha_sin_token_devuelve_401(client: TestClient) -> None:
    response = client.get("/candidates/1")

    assert response.status_code == 401


def test_filtro_por_fecha_de_alta_incluye_los_de_hoy(client: TestClient) -> None:
    sofia = _headers(client, "sofia", "sofia1234")
    creado = _crear(client, sofia, "Iván Torres")
    hoy = datetime.now(UTC).date()

    response = client.get(
        "/candidates",
        params={
            "created_from": hoy.isoformat(),
            "created_to": (hoy + timedelta(days=1)).isoformat(),
        },
        headers=sofia,
    )

    assert response.status_code == 200
    assert creado["id"] in [c["id"] for c in response.json()]


def test_filtro_por_fecha_sin_candidatos_devuelve_lista_vacia(client: TestClient) -> None:
    sofia = _headers(client, "sofia", "sofia1234")

    response = client.get(
        "/candidates",
        params={"created_from": "2020-01-01", "created_to": "2020-01-31"},
        headers=sofia,
    )

    assert response.status_code == 200
    assert response.json() == []
