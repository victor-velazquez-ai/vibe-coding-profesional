"""Guardrail, capa 1 (PreToolUse sobre Edit|Write|MultiEdit|NotebookEdit): cada rol, lo suyo.

El rol lo dice Claude Code en la entrada del hook (`agent_type`: la sesión se lanzó con
`claude --agent <rol>`). No es una variable de entorno: tu agente no lo puede cambiar.

- escritor-tests: solo escribe en tests/.
- revisor-pr y revisor-plan: no escriben nada.
- qa-* (sección 7): solo escriben en qa/ (informes, capturas, videos).
- cualquier otro (constructor, tú sin rol): todo menos tests/.

Esta capa no basta: con Bash (sed, python…) se puede reescribir un archivo sin pasar por
Edit. La capa 2 está en terminado.py: verifica el resultado con git, no la herramienta.
Salir con 2 bloquea la herramienta; lo que se imprime en stderr le llega al agente.
"""

import json
import os
import sys

sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

datos = json.load(sys.stdin)
rol = datos.get("agent_type") or "sin rol"
entrada = datos.get("tool_input") or {}
ruta = entrada.get("file_path") or entrada.get("notebook_path") or ""
if not ruta:
    sys.exit(0)

raiz = os.path.abspath(os.environ.get("CLAUDE_PROJECT_DIR") or datos.get("cwd") or ".")
raiz = os.path.normcase(raiz)
destino = os.path.normcase(os.path.abspath(os.path.join(raiz, ruta)))
relativa = os.path.relpath(destino, raiz).replace("\\", "/")
en_tests = relativa.startswith("tests/")

if rol in ("revisor-pr", "revisor-plan"):
    motivo = f"el rol {rol} es de solo lectura: no escribe {relativa}. Repórtalo en tu respuesta."
elif rol.startswith("qa-"):
    if relativa.startswith("qa/"):
        sys.exit(0)
    motivo = f"la QA solo escribe en qa/, no en {relativa}. Lo que encuentres va en tu informe."
elif rol == "escritor-tests" and not en_tests:
    motivo = (
        f"el escritor de tests solo escribe en tests/, no en {relativa}. "
        "Si hace falta código, dilo en tu respuesta."
    )
elif rol != "escritor-tests" and en_tests:
    motivo = (
        f"no puedes editar {relativa}. Los tests los escribe el rol escritor-tests. Si un test "
        "está mal o es imposible de cumplir, no lo cambies: explica cuál y por qué, y detente."
    )
else:
    sys.exit(0)
print(f"GUARDRAIL ({rol}): {motivo}", file=sys.stderr)
sys.exit(2)
