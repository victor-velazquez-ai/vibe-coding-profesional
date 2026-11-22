"""Cambio de etapa de un candidato: PATCH /candidates/{id}/stage."""

from fastapi.testclient import TestClient

from tests.conftest import login


def _auth(client: TestClient, user: str, password: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, user, password)}"}


def _crear(client: TestClient, stage: str = "contacto") -> int:
    response = client.post(
        "/candidates",
        json={"name": "Dana Ruiz", "position": "Coordinadora de flota", "stage": stage},
        headers=_auth(client, "sofia", "sofia1234"),
    )
    assert response.status_code == 201
    candidate_id: int = response.json()["id"]
    return candidate_id


def test_cambiar_etapa(client: TestClient) -> None:
    candidate_id = _crear(client)
    response = client.patch(
        f"/candidates/{candidate_id}/stage",
        json={"stage": "entrevista"},
        headers=_auth(client, "sofia", "sofia1234"),
    )
    assert response.status_code == 200
    assert response.json()["stage"] == "entrevista"


def test_etapa_inexistente_es_422(client: TestClient) -> None:
    candidate_id = _crear(client)
    response = client.patch(
        f"/candidates/{candidate_id}/stage",
        json={"stage": "en_pausa"},
        headers=_auth(client, "sofia", "sofia1234"),
    )
    assert response.status_code == 422


def test_candidato_de_otra_empresa_es_404(client: TestClient) -> None:
    candidate_id = _crear(client)
    response = client.patch(
        f"/candidates/{candidate_id}/stage",
        json={"stage": "entrevista"},
        headers=_auth(client, "marcus", "marcus1234"),
    )
    assert response.status_code == 404


def test_candidato_inexistente_es_404(client: TestClient) -> None:
    response = client.patch(
        "/candidates/999999/stage",
        json={"stage": "entrevista"},
        headers=_auth(client, "sofia", "sofia1234"),
    )
    assert response.status_code == 404


def test_sin_credenciales_es_401(client: TestClient) -> None:
    candidate_id = _crear(client)
    response = client.patch(f"/candidates/{candidate_id}/stage", json={"stage": "entrevista"})
    assert response.status_code == 401


def test_descartado_es_final(client: TestClient) -> None:
    candidate_id = _crear(client, stage="descartado")
    response = client.patch(
        f"/candidates/{candidate_id}/stage",
        json={"stage": "entrevista"},
        headers=_auth(client, "sofia", "sofia1234"),
    )
    assert response.status_code == 409


def test_reabrir_candidato_descartado(client: TestClient) -> None:
    candidate_id = _crear(client, stage="descartado")
    response = client.patch(
        f"/candidates/{candidate_id}/stage",
        json={"stage": "entrevista"},
        headers=_auth(client, "sofia", "sofia1234"),
    )
    assert response.status_code == 200
    assert response.json()["stage"] == "entrevista"
