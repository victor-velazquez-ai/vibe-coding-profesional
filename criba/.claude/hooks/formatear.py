"""Hook PostToolUse sobre Edit|Write|MultiEdit: formatea con ruff cada .py que toca el agente.

Nunca bloquea (siempre sale con 0): formatear es una ayuda, no una ley.
"""

import json
import subprocess
import sys

datos = json.load(sys.stdin)
ruta = (datos.get("tool_input") or {}).get("file_path") or ""
if ruta.endswith(".py"):
    subprocess.run(
        ["uv", "run", "--quiet", "python", "-m", "ruff", "format", ruta],
        capture_output=True,
        check=False,
    )
sys.exit(0)
