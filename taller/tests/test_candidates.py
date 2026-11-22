from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tests.conftest import login


def test_login_success(client: TestClient) -> None:
    token = login(client, "sofia", "sofia1234")
    assert token


def test_login_wrong_password(client: TestClient) -> None:
    response = client.post("/login", data={"username": "sofia", "password": "wrong"})
    assert response.status_code == 401


def test_list_candidates_requires_auth(client: TestClient) -> None:
    response = client.get("/candidates")
    assert response.status_code == 401


def test_recruiter_only_sees_own_company_candidates(client: TestClient) -> None:
    sofia_token = login(client, "sofia", "sofia1234")
    response = client.get("/candidates", headers={"Authorization": f"Bearer {sofia_token}"})
    assert response.status_code == 200
    candidates = response.json()
    names = [c["name"] for c in candidates]
    assert "Laura Gómez" in names
    assert "Priya Nair" not in names

    salary_note = next(c for c in candidates if c["name"] == "Laura Gómez")
    assert salary_note["notes"] == "pide 120 mil dólares; tiene otra oferta"

    marcus_token = login(client, "marcus", "marcus1234")
    response = client.get("/candidates", headers={"Authorization": f"Bearer {marcus_token}"})
    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert "Priya Nair" in names
    assert "Laura Gómez" not in names


def test_create_candidate_assigned_to_recruiter_company(client: TestClient) -> None:
    token = login(client, "sofia", "sofia1234")
    response = client.post(
        "/candidates",
        json={
            "name": "Nueva Candidata",
            "position": "Analista de rutas",
            "stage": "Primer contacto",
            "notes": "Contactada por LinkedIn",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "Nueva Candidata"

    list_response = client.get("/candidates", headers={"Authorization": f"Bearer {token}"})
    names = [c["name"] for c in list_response.json()]
    assert "Nueva Candidata" in names


def test_created_at_llega_con_zona_horaria(client: TestClient) -> None:
    """La API debe devolver created_at con offset explícito (timestamptz),
    no un valor naive cuyo significado depende del TimeZone de la sesión
    de Postgres que lo escribió."""
    token = login(client, "sofia", "sofia1234")
    response = client.post(
        "/candidates",
        json={"name": "Ana Torres", "position": "Despachadora", "stage": "Primer contacto"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201

    creado = datetime.fromisoformat(response.json()["created_at"])
    assert creado.tzinfo is not None, (
        "created_at llegó sin zona horaria: es ambiguo sin saber el TimeZone "
        "de la sesión que lo escribió"
    )


def test_created_at_es_el_instante_real_en_utc(client: TestClient) -> None:
    """created_at debe ser un instante real: comparado en UTC contra la hora
    actual, sin asumir ninguna zona horaria de sesión (p.ej. America/Chicago)."""
    token = login(client, "sofia", "sofia1234")
    antes = datetime.now(UTC)
    response = client.post(
        "/candidates",
        json={"name": "Luis Peña", "position": "Despachador", "stage": "Primer contacto"},
        headers={"Authorization": f"Bearer {token}"},
    )
    despues = datetime.now(UTC)
    assert response.status_code == 201

    creado = datetime.fromisoformat(response.json()["created_at"])
    assert creado.tzinfo is not None, "sin offset no se puede comparar contra UTC de forma segura"
    creado_utc = creado.astimezone(UTC)

    margen = timedelta(seconds=5)
    assert antes - margen <= creado_utc <= despues + margen, (
        f"created_at ({creado_utc.isoformat()}) no corresponde al instante real "
        f"entre {antes.isoformat()} y {despues.isoformat()}"
    )
