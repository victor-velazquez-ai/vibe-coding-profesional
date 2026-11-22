"""Hook PreToolUse sobre Bash: nada sale a GitHub con rutas de tu máquina ni tu usuario.

Lo que se publica en un PR, un issue o un comentario queda en el historial de ediciones
aunque después lo corrijas. Por eso se revisa ANTES: si el comando es `gh pr|issue
create|edit|comment` y su cuerpo (en línea o en `--body-file`) lleva una ruta absoluta de
usuario o tu nombre de usuario, la herramienta no se ejecuta y tu agente recibe el motivo.
"""

import json
import os
import re
import sys
from pathlib import Path

sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

datos = json.load(sys.stdin)
comando = (datos.get("tool_input") or {}).get("command") or ""
if not re.search(r"\bgh\s+(pr|issue)\s+(create|edit|comment)\b", comando):
    sys.exit(0)

textos = [comando]
for m in re.finditer(r"--body-file[= ]+(\"[^\"]+\"|'[^']+'|\S+)", comando):
    archivo = Path(datos.get("cwd") or ".", m.group(1).strip("\"'"))
    if archivo.is_file():
        textos.append(archivo.read_text(encoding="utf-8", errors="replace"))

patrones = [r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s…]+", r"/home/[^/\s]+", r"/Users/[^/\s]+"]
usuario = os.environ.get("USERNAME") or os.environ.get("USER") or ""
if len(usuario) >= 3:
    patrones.append(re.escape(usuario))
hallados = sorted({m.group(0) for t in textos for p in patrones for m in re.finditer(p, t, re.I)})
if not hallados:
    sys.exit(0)
print(
    f"GUARDRAIL publicar: el cuerpo lleva {len(hallados)} ruta(s) o nombre(s) de usuario de tu "
    "máquina. Cámbialos por rutas relativas al repo (o por …) y vuelve a intentarlo: lo que se "
    "publica en GitHub queda en el historial aunque después lo edites.",
    file=sys.stderr,
)
sys.exit(2)
