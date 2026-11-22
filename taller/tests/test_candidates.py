from tests.conftest import login


def test_login_success(client):
    token = login(client, "sofia", "sofia1234")
    assert token


def test_login_wrong_password(client):
    response = client.post("/login", data={"username": "sofia", "password": "wrong"})
    assert response.status_code == 401


def test_list_candidates_requires_auth(client):
    response = client.get("/candidates")
    assert response.status_code == 401


def test_recruiter_only_sees_own_company_candidates(client):
    sofia_token = login(client, "sofia", "sofia1234")
    response = client.get(
        "/candidates", headers={"Authorization": f"Bearer {sofia_token}"}
    )
    assert response.status_code == 200
    candidates = response.json()
    names = [c["name"] for c in candidates]
    assert "Laura Gómez" in names
    assert "Priya Nair" not in names

    salary_note = next(c for c in candidates if c["name"] == "Laura Gómez")
    assert salary_note["notes"] == "pide 120 mil dólares; tiene otra oferta"

    marcus_token = login(client, "marcus", "marcus1234")
    response = client.get(
        "/candidates", headers={"Authorization": f"Bearer {marcus_token}"}
    )
    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert "Priya Nair" in names
    assert "Laura Gómez" not in names


def test_create_candidate_assigned_to_recruiter_company(client):
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

    list_response = client.get(
        "/candidates", headers={"Authorization": f"Bearer {token}"}
    )
    names = [c["name"] for c in list_response.json()]
    assert "Nueva Candidata" in names
