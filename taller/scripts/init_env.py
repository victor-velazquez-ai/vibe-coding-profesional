"""Crea un `.env` local a partir de `.env.example`, con secretos generados.

Si `.env` ya existe, no toca lo que tiene: solo agrega las claves generadas que le falten
(por ejemplo, las contraseñas de los roles del agente que llegaron en la sección 3).
"""

import secrets
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = PROJECT_ROOT / ".env.example"
TARGET = PROJECT_ROOT / ".env"

GENERATED = {
    "SECRET_KEY": lambda: secrets.token_urlsafe(48),
    "POSTGRES_PASSWORD": lambda: secrets.token_urlsafe(24),
    "AGENTE_LECTURA_PASSWORD": lambda: secrets.token_urlsafe(24),
    "AGENTE_METRICAS_PASSWORD": lambda: secrets.token_urlsafe(24),
}


def _keys(text: str) -> set[str]:
    return {line.partition("=")[0].strip() for line in text.splitlines() if "=" in line}


def completar(existente: str) -> list[str]:
    """Líneas `CLAVE=valor` para las claves generadas que faltan en un `.env` existente."""
    tiene = _keys(existente)
    return [f"{k}={gen()}" for k, gen in GENERATED.items() if k not in tiene]


def main() -> int:
    if not EXAMPLE.exists():
        print(f"No encuentro {EXAMPLE}", file=sys.stderr)
        return 1

    if TARGET.exists():
        actual = TARGET.read_text(encoding="utf-8")
        nuevas = completar(actual)
        if not nuevas:
            print(f".env ya existe en {TARGET} y está completo: no se toca.")
            return 0
        sep = "" if actual.endswith("\n") else "\n"
        TARGET.write_text(actual + sep + "\n".join(nuevas) + "\n", encoding="utf-8")
        nombres = ", ".join(n.partition("=")[0] for n in nuevas)
        print(f".env ya existía: le agregué {nombres}. Lo demás no se tocó.")
        return 0

    lines = []
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and not value.strip() and key.strip() in GENERATED:
            line = f"{key.strip()}={GENERATED[key.strip()]()}"
        lines.append(line)

    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f".env creado en {TARGET} con secretos aleatorios.")
    print("Si ya tenias el contenedor creado, recrealo: uv run poe db:stop && uv run poe db")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
