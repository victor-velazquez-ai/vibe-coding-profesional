"""Guardrail, capa 1 (hook PreToolUse sobre Edit|Write|MultiEdit|NotebookEdit).

El constructor no edita tests/: los tests los escribe el rol escritor-tests.
Salir con código 2 bloquea la herramienta; lo que se imprime en stderr le llega al agente.

Esta capa NO basta: con Bash (sed, python…) el agente puede reescribir un test sin pasar
por Edit. La capa 2 está en check_antes_de_terminar.py: compara tests/ contra el commit
del escritor de tests. Verifica el resultado, no la herramienta.
"""

import json
import os
import sys

sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

# La sesión del escritor de tests se lanza con TALLER_ROL=escritor-tests.
# El agente no puede cambiar esta variable: viene del proceso de Claude Code, no de su Bash.
if os.environ.get("TALLER_ROL") == "escritor-tests":
    sys.exit(0)

datos = json.load(sys.stdin)
entrada = datos.get("tool_input") or {}
ruta = entrada.get("file_path") or entrada.get("notebook_path") or ""
if not ruta:
    sys.exit(0)

raiz = os.environ.get("CLAUDE_PROJECT_DIR") or datos.get("cwd") or os.getcwd()
carpeta_tests = os.path.normcase(os.path.join(os.path.abspath(raiz), "tests")) + os.sep
destino = os.path.normcase(os.path.abspath(os.path.join(raiz, ruta)))

if destino.startswith(carpeta_tests):
    relativa = os.path.relpath(destino, os.path.normcase(os.path.abspath(raiz))).replace("\\", "/")
    print(
        f"GUARDRAIL tests/: no puedes editar {relativa}. Los tests los escribe el rol "
        "escritor-tests. Si un test está mal o es imposible de cumplir, no lo cambies: "
        "explica cuál y por qué, y detente.",
        file=sys.stderr,
    )
    sys.exit(2)
sys.exit(0)
