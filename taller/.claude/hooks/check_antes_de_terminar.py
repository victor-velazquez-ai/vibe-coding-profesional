"""Hook Stop: el agente no termina en rojo.

1. Capa 2 del guardrail de tests: compara tests/ contra el último commit del escritor de
   tests (el que lleva la línea "Rol: escritor-tests"). Atrapa el cambio venga de donde
   venga: Edit, sed, un script de Python, git checkout…
2. Corre `uv run poe check`.

Si algo falla, sale con 2: el agente no puede terminar y recibe el motivo en stderr.
Guarda contra bucles: como mucho MAX_BLOQUEOS por sesión. Después lo deja terminar,
y el trabajo queda en rojo (y tu reporte lo tiene que decir).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

MAX_BLOQUEOS = 3

sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
datos = json.load(sys.stdin)
raiz = Path(os.environ.get("CLAUDE_PROJECT_DIR") or datos.get("cwd") or ".")
estado = raiz / ".claude" / "estado"
estado.mkdir(parents=True, exist_ok=True)
contador = estado / f"stop-{datos.get('session_id', 'sin-sesion')}.txt"
bloqueos = int(contador.read_text()) if contador.exists() else 0


def correr(*comando: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        comando, cwd=raiz, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


problemas = []
base = correr("git", "log", "-1", "--format=%H", "--grep=Rol: escritor-tests").stdout.strip()
if base:
    cambiados = set(correr("git", "diff", "--name-only", base, "--", "tests").stdout.split())
    nuevos = correr("git", "ls-files", "--others", "--exclude-standard", "--", "tests").stdout
    cambiados |= set(nuevos.split())
    if cambiados:
        problemas.append(
            f"GUARDRAIL stop: tests/ cambió respecto al commit del escritor de tests "
            f"({base[:7]}): {', '.join(sorted(cambiados))}. Restáuralo con "
            f"`git checkout {base[:7]} -- tests/` y, si un test está mal, explícalo en tu "
            "respuesta en lugar de cambiarlo."
        )

check = correr("uv", "run", "--quiet", "poe", "check")
if check.returncode != 0:
    cola = "\n".join((check.stdout + check.stderr).strip().splitlines()[-30:])
    problemas.append(
        "GUARDRAIL stop: `uv run poe check` está en rojo. No termines en rojo: arréglalo, "
        "o explica qué falla y por qué no se puede arreglar.\n" + cola
    )

if not problemas:
    contador.unlink(missing_ok=True)
    sys.exit(0)
if bloqueos >= MAX_BLOQUEOS:
    print(
        f"GUARDRAIL stop: ya bloqueé {MAX_BLOQUEOS} veces; te dejo terminar para no entrar "
        "en bucle. El trabajo queda EN ROJO: dilo en tu respuesta.",
        file=sys.stderr,
    )
    sys.exit(0)
contador.write_text(str(bloqueos + 1))
print("\n\n".join(problemas), file=sys.stderr)
sys.exit(2)
