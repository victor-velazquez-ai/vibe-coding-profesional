"""Crea un `.env` local a partir de `.env.example`, con secretos generados.

No sobreescribe un `.env` existente.
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


def main() -> int:
    if TARGET.exists():
        print(f".env ya existe en {TARGET}: no se toca.")
        return 0
    if not EXAMPLE.exists():
        print(f"No encuentro {EXAMPLE}", file=sys.stderr)
        return 1

    lines = []
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and not value.strip() and key.strip() in GENERATED:
            line = f"{key.strip()}={GENERATED[key.strip()]()}"
        lines.append(line)

    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f".env creado en {TARGET} con SECRET_KEY y POSTGRES_PASSWORD aleatorios.")
    print("Si ya tenias el contenedor creado, recrealo: uv run poe db:stop && uv run poe db")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
