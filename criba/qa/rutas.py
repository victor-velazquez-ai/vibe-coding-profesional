"""El mapa de lo que hay que atacar: las rutas de la app, con su método y sus campos.

    uv run python qa/rutas.py             # tabla legible
    uv run python qa/rutas.py --openapi   # el esquema OpenAPI, para schemathesis

En Criba el OpenAPI público está apagado (`openapi_url=None` en `app/fabrica.py`), y en
producción está bien así. Para la QA, el mismo mapa sale de la app sin exponer nada:
FastAPI lo genera desde las rutas. Se monta con Match encendido para que salgan también
las rutas de `/match`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("CRIBA_MATCH_ACTIVO", "1")

from app.fabrica import crear_app


def campos(operacion: dict[str, object], esquema: dict[str, object]) -> list[str]:
    nombres = [f"?{p['name']}" for p in operacion.get("parameters", []) if p.get("in") == "query"]  # type: ignore[union-attr, index]
    cuerpo = operacion.get("requestBody", {}).get("content", {})  # type: ignore[union-attr]
    for contenido in cuerpo.values():
        ref = contenido.get("schema", {}).get("$ref", "")
        modelo = esquema["components"]["schemas"].get(ref.rsplit("/", 1)[-1], {})  # type: ignore[index]
        requeridos = set(modelo.get("required", []))
        nombres += [n + ("*" if n in requeridos else "") for n in modelo.get("properties", {})]
    return nombres


def main() -> None:
    esquema = crear_app().openapi()
    if "--openapi" in sys.argv:
        print(json.dumps(esquema, ensure_ascii=False, indent=2))
        return
    print("Rutas de Criba (* = campo de formulario obligatorio, ?x = parámetro de query)\n")
    for ruta, operaciones in sorted(esquema["paths"].items()):
        for metodo, operacion in operaciones.items():
            print(f"{metodo.upper():<6} {ruta:<40} {' '.join(campos(operacion, esquema))}")


if __name__ == "__main__":
    main()
