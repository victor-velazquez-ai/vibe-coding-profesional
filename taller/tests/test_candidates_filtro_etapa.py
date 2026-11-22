"""Issue #1: GET /candidates?stage=<etapa> filtra por etapa, siempre dentro de la empresa."""

from fastapi.testclient import TestClient

from tests.conftest import login


def test_filtro_por_etapa_devuelve_solo_los_candidatos_de_esa_etapa_y_empresa(
    client: TestClient,
) -> None:
    sofia_token = login(client, "sofia", "sofia1234")
    sofia_headers = {"Authorization": f"Bearer {sofia_token}"}

    response = client.get(
        "/candidates", params={"stage": "Entrevista técnica"}, headers=sofia_headers
    )
    assert response.status_code == 200
    candidates = response.json()
    names = [c["name"] for c in candidates]

    # Laura Gómez está en "Entrevista técnica"; Diego Fernández está en "Preseleccionado".
    assert names == ["Laura Gómez"]
    assert all(c["stage"] == "Entrevista técnica" for c in candidates)

    marcus_token = login(client, "marcus", "marcus1234")
    marcus_headers = {"Authorization": f"Bearer {marcus_token}"}

    # Northstar no tiene a nadie en "Entrevista técnica" (su etapa parecida se llama distinto).
    response = client.get(
        "/candidates", params={"stage": "Entrevista técnica"}, headers=marcus_headers
    )
    assert response.status_code == 200
    assert response.json() == []


def test_sin_parametro_stage_devuelve_todos_los_candidatos_de_la_empresa(
    client: TestClient,
) -> None:
    sofia_token = login(client, "sofia", "sofia1234")
    response = client.get("/candidates", headers={"Authorization": f"Bearer {sofia_token}"})
    assert response.status_code == 200
    names = {c["name"] for c in response.json()}
    assert {"Laura Gómez", "Diego Fernández"}.issubset(names)
    assert "Priya Nair" not in names

    marcus_token = login(client, "marcus", "marcus1234")
    response = client.get("/candidates", headers={"Authorization": f"Bearer {marcus_token}"})
    assert response.status_code == 200
    names = {c["name"] for c in response.json()}
    assert {"Priya Nair", "Tom Alvarez"}.issubset(names)
    assert "Laura Gómez" not in names


def test_etapa_sin_candidatos_devuelve_200_y_lista_vacia(client: TestClient) -> None:
    sofia_token = login(client, "sofia", "sofia1234")
    response = client.get(
        "/candidates",
        params={"stage": "Etapa que no existe"},
        headers={"Authorization": f"Bearer {sofia_token}"},
    )
    assert response.status_code == 200
    assert response.json() == []

    marcus_token = login(client, "marcus", "marcus1234")
    response = client.get(
        "/candidates",
        params={"stage": "Etapa que no existe"},
        headers={"Authorization": f"Bearer {marcus_token}"},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_reclutador_de_otra_empresa_no_ve_candidatos_aunque_coincida_la_etapa(
    client: TestClient,
) -> None:
    stage = "Revisión final"
    sofia_token = login(client, "sofia", "sofia1234")
    marcus_token = login(client, "marcus", "marcus1234")
    sofia_headers = {"Authorization": f"Bearer {sofia_token}"}
    marcus_headers = {"Authorization": f"Bearer {marcus_token}"}

    create_sofia = client.post(
        "/candidates",
        json={
            "name": "Sofia Filtro Compartido",
            "position": "Analista de rutas",
            "stage": stage,
        },
        headers=sofia_headers,
    )
    assert create_sofia.status_code == 201

    create_marcus = client.post(
        "/candidates",
        json={
            "name": "Marcus Filtro Compartido",
            "position": "Técnico de laboratorio",
            "stage": stage,
        },
        headers=marcus_headers,
    )
    assert create_marcus.status_code == 201

    response = client.get("/candidates", params={"stage": stage}, headers=sofia_headers)
    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert names == ["Sofia Filtro Compartido"]
    assert "Marcus Filtro Compartido" not in names

    response = client.get("/candidates", params={"stage": stage}, headers=marcus_headers)
    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert names == ["Marcus Filtro Compartido"]
    assert "Sofia Filtro Compartido" not in names
