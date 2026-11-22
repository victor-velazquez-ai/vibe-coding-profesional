"""¿Se filtran datos entre empresas? (ejercicio S1-E1)

Marcus (Northstar Health) pide un candidato de Meridian Logistics por id.
Si recibe 200 y ve la nota confidencial, hay filtración entre clientes.

Uso, dentro de la carpeta taller/ de tu copia:
    uv run python ../herramientas/check_leak.py           # GET /candidates/{id}
    uv run python ../herramientas/check_leak.py --notas   # notas anidadas de un candidato
Imprime una línea JSON.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.getcwd())

SOFIA, MARCUS = ("sofia", "sofia1234"), ("marcus", "marcus1234")
SECRET_NOTE = "pide 120 mil dólares"
NESTED = "--notas" in sys.argv


def build_client():
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app import database
    from app.main import app
    import app.seed as seed_mod

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TS = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    database.Base.metadata.create_all(bind=engine)
    seed = getattr(seed_mod, "seed_if_empty", None) or next(
        getattr(seed_mod, n) for n in dir(seed_mod) if n.startswith("seed") and callable(getattr(seed_mod, n)))
    with TS() as db:
        seed(db)

    def override():
        db = TS()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[database.get_db] = override
    return app, TestClient(app)


def auth(client, user):
    r = client.post("/login", data={"username": user[0], "password": user[1]})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def routes(app, method, pattern):
    return [r.path for r in app.routes
            if method in getattr(r, "methods", set()) and re.search(pattern, getattr(r, "path", ""))]


def main():
    out = {"mode": "notas" if NESTED else "candidato", "error": None}
    try:
        app, c = build_client()
        hs, hm = auth(c, SOFIA), auth(c, MARCUS)
        listing = c.get(routes(app, "GET", r"^/(candidates|candidatos)/?$")[0], headers=hs).json()
        target = next(x for x in listing if SECRET_NOTE in json.dumps(x, ensure_ascii=False))
        cid = target["id"]
        if not NESTED:
            found = routes(app, "GET", r"^/(candidates|candidatos)/\{[^}]+\}$")
            if not found:
                out["error"] = f"no hay ruta GET por id; rutas={[getattr(r, 'path', '') for r in app.routes]}"
            else:
                url = re.sub(r"\{[^}]+\}", str(cid), found[0])
                rm = c.get(url, headers=hm)
                out.update(route=found[0], sofia_status=c.get(url, headers=hs).status_code,
                           marcus_status=rm.status_code, anon_status=c.get(url).status_code,
                           leak=rm.status_code == 200 and SECRET_NOTE in rm.text)
        else:
            posts = routes(app, "POST", r"^/(candidates|candidatos)/\{[^}]+\}/\w+$")
            gets = routes(app, "GET", r"^/(candidates|candidatos)/\{[^}]+\}/\w+$")
            if not posts:
                out["error"] = f"no hay ruta anidada POST; rutas={[getattr(r, 'path', '') for r in app.routes]}"
            else:
                purl = re.sub(r"\{[^}]+\}", str(cid), posts[0])
                spec = app.openapi()["paths"][posts[0]]["post"]
                schema = (spec.get("requestBody") or {}).get("content", {}).get("application/json", {}).get("schema", {})
                if "$ref" in schema:
                    schema = app.openapi()["components"]["schemas"][schema["$ref"].split("/")[-1]]
                fields = [k for k, v in (schema.get("properties") or {}).items()
                          if (v.get("type") or (v.get("anyOf") or [{}])[0].get("type")) == "string"]
                body = lambda text: {f: text for f in fields} or {"texto": text}  # noqa: E731
                ra = c.post(purl, json=body("nota interna de sofia"), headers=hs)
                rb = c.post(purl, json=body("intruso de marcus"), headers=hm)
                out.update(post_route=posts[0], sofia_post=ra.status_code, marcus_post=rb.status_code,
                           leak_write=200 <= rb.status_code < 300)
                if gets:
                    rg = c.get(re.sub(r"\{[^}]+\}", str(cid), gets[0]), headers=hm)
                    out.update(get_route=gets[0], marcus_get=rg.status_code,
                               leak_read=rg.status_code == 200 and "nota interna de sofia" in rg.text)
                out["leak"] = bool(out.get("leak_write") or out.get("leak_read"))
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"[:300]
    print(json.dumps(out, ensure_ascii=False))


main()
