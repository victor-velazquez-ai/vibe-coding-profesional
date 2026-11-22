"""Hook Stop: nadie termina en rojo, y nadie cambia el contrato de otro rol.

- escritor-tests: sus tests DEBEN estar en rojo (es su trabajo), así que no se le corre
  `poe check`. Solo se comprueba que no tocó nada fuera de tests/.
- qa-* (sección 7): la QA observa y reporta; un rojo ajeno no la puede dejar atrapada. No se
  le corre `poe check`: solo se comprueba que no tocó app/, tests/ ni migrations/.
- revisor-pr y revisor-plan: solo leen; nada que comprobar.
- cualquier otro: (1) tests/ igual que en el último commit del escritor de tests (línea
  "Rol: escritor-tests"), y (2) `poe check` en verde.

Si algo falla, sale con 2 y le devuelve al agente SOLO lo que necesita: los tests que
fallaron, las reglas de lint rotas y la línea final; no 300 líneas de log que se le comen
el contexto. Como mucho MAX_BLOQUEOS por sesión; después lo deja terminar, en rojo.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

MAX_BLOQUEOS = 3
TESTS = r"^(criba/)?tests/"
CODIGO = r"^(criba/)?(app|tests|migrations)/"

sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
datos = json.load(sys.stdin)
rol = datos.get("agent_type") or "sin rol"
raiz = Path(os.environ.get("CLAUDE_PROJECT_DIR") or datos.get("cwd") or ".")
if rol in ("revisor-pr", "revisor-plan"):
    sys.exit(0)

estado = raiz / ".claude" / "estado"
estado.mkdir(parents=True, exist_ok=True)
contador = estado / f"stop-{datos.get('session_id', 'sin-sesion')}.txt"
bloqueos = int(contador.read_text()) if contador.exists() else 0


def correr(*comando: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        comando, cwd=raiz, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def cambiados_desde(base: str, carpeta: str) -> set[str]:
    rastreados = set(correr("git", "diff", "--name-only", base, "--", carpeta).stdout.split())
    otros = correr("git", "ls-files", "--others", "--exclude-standard", "--", carpeta).stdout
    return rastreados | set(otros.split())


def resumen(salida: str) -> str:
    """Lo mínimo que un agente necesita: qué falló y dónde, más la línea final."""
    lineas = salida.splitlines()
    fallos = [x for x in lineas if x.startswith(("FAILED ", "ERROR "))][:10]
    lint = [x.strip() for x in lineas if re.match(r"^([A-Z]+\d+ |\s*--> )", x)][:12]
    final = [x for x in lineas if re.search(r"\d+ (passed|failed|error)", x)][-1:]
    partes = fallos + lint + final
    return "\n".join(partes) if partes else "\n".join(lineas[-15:])


problemas = []
if rol.startswith("qa-"):
    tocados = {r for r in cambiados_desde("HEAD", ".") if re.match(CODIGO, r)}
    if tocados:
        problemas.append(
            f"GUARDRAIL stop: la QA no cambia código ni tests: {', '.join(sorted(tocados))}. "
            "Repórtalo en tu informe."
        )
elif rol == "escritor-tests":
    fuera = {r for r in cambiados_desde("HEAD", ".") if not re.match(TESTS, r)}
    if "Rol: escritor-tests" in correr("git", "log", "-1", "--format=%B").stdout:
        ultimo = correr("git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD")
        fuera |= {r for r in ultimo.stdout.split() if not re.match(TESTS, r)}
    if fuera:
        problemas.append(
            "GUARDRAIL stop: el escritor de tests tocó fuera de tests/: "
            f"{', '.join(sorted(fuera))}."
        )
else:
    base = correr("git", "log", "-1", "--format=%H", "--grep=Rol: escritor-tests", "--", ".")
    base_sha = base.stdout.strip()
    if base_sha:
        tocados = cambiados_desde(base_sha, "tests")
        if tocados:
            problemas.append(
                "GUARDRAIL stop: tests/ cambió respecto al commit del escritor de tests "
                f"({base_sha[:7]}): {', '.join(sorted(tocados))}. Restáuralo con "
                f"`git checkout {base_sha[:7]} -- tests/` y, si un test está mal, explícalo en "
                "tu respuesta en lugar de cambiarlo."
            )
    check = correr("uv", "run", "--quiet", "python", "-m", "poethepoet", "check")
    if check.returncode != 0:
        problemas.append(
            "GUARDRAIL stop: `poe check` está en rojo. No termines en rojo: arréglalo, o explica "
            "qué falla y por qué no se puede arreglar.\n" + resumen(check.stdout + check.stderr)
        )

if not problemas:
    contador.unlink(missing_ok=True)
    sys.exit(0)
if bloqueos >= MAX_BLOQUEOS:
    print(
        f"GUARDRAIL stop: ya bloqueé {MAX_BLOQUEOS} veces; te dejo terminar. "
        "El trabajo queda EN ROJO: dilo en tu respuesta.",
        file=sys.stderr,
    )
    sys.exit(0)
contador.write_text(str(bloqueos + 1))
print("\n\n".join(problemas), file=sys.stderr)
sys.exit(2)
