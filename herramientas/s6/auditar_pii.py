"""Auditoría de la frontera de pseudonimización (S6 · 6.1 y kit S6-E1).

Tus tests están en verde. Esto es lo que hace un senior después: pasarle al pseudonimizador
diez CVs con los formatos que aparecen en CVs reales de EE.UU. y México, y mirar qué sale.
No es un test: es la pregunta «¿qué no imaginó la spec?».

Uso, desde la carpeta criba/ de tu copia:
    uv run python ../herramientas/s6/auditar_pii.py

Los CVs son SINTÉTICOS y ficticios (correos en example.com, teléfonos con 555 o 0000).
"""

from __future__ import annotations

import json
import os
import sys
import unicodedata

sys.path.insert(0, os.getcwd())
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cvs_auditoria import CVS  # noqa: E402

try:
    from app.match.services.pseudonimizador import pseudonimizar
    from app.plataforma.modelos import Candidato
except ImportError as e:  # pragma: no cover
    print(f"No encuentro el pseudonimizador ({e}). Corre esto desde criba/ con el PR-08 hecho.")
    sys.exit(2)


def plano(s: str) -> str:
    """Minúsculas y sin acentos: una fuga es una fuga aunque cambie una tilde."""
    s = unicodedata.normalize("NFKD", s.casefold())
    return "".join(c for c in s if not unicodedata.combining(c))


def texto_enviado(payload: object) -> str:
    """Todo lo que el payload lleva al proveedor, sea cual sea su forma."""
    for campo in ("cuerpo", "cv", "texto", "cv_texto", "contenido"):
        valor = getattr(payload, campo, None)
        if valor is None:
            continue
        if callable(valor):
            valor = valor()
        if isinstance(valor, str):
            return valor
        return json.dumps(valor, ensure_ascii=False, default=lambda o: dict(o) if hasattr(o, "keys") else str(o))
    sys.exit(f"No sé leer lo que envía {type(payload).__name__}: dime qué campo o método lo expone.")


def main() -> None:
    filas = []
    for caso in CVS:
        candidato = Candidato(empresa_id=0, cv_texto=caso["texto"], **caso["campos"])
        enviado = texto_enviado(pseudonimizar(candidato))
        fugas = [d for d in caso["pii"] if plano(d) in plano(enviado)]
        filas.append({"id": caso["id"], "fugas": fugas, "enviado": enviado})
        marca = "FUGA " if fugas else "ok   "
        print(f"{marca} {caso['id']:<34} {', '.join(fugas)}")
    con_fuga = sum(1 for f in filas if f["fugas"])
    datos = sum(len(f["fugas"]) for f in filas)
    total = sum(len(c["pii"]) for c in CVS)
    print(f"\n{con_fuga} de {len(CVS)} CVs dejan salir algo · {datos} de {total} datos personales")
    if "--json" in sys.argv:
        print(json.dumps(filas, ensure_ascii=False))


if __name__ == "__main__":
    main()
