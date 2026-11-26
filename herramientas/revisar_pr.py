"""Revisor de PR con tu agente: comenta, nunca aprueba (sección 8, video 8.1).

Corre `claude -p` en modo solo lectura sobre un PR y publica un comentario con
`gh pr comment`. Nunca usa `gh pr review --approve` ni `--request-changes`: el merge
lo decide una persona y el check que bloquea es la CI.

**Es un script local, no un check de GitHub Actions**, y el curso lo dice así: corre
con tu sesión de Claude Code, sin clave de API. En un proyecto de cliente va en la CI
(la acción oficial de Claude Code con una clave de API, o con un token de suscripción
de `claude setup-token`: ver el kit S8-E1).

Uso (desde la raíz del repo del curso):
  python -I herramientas/revisar_pr.py <numero> [--model opus] [--publicar] [--max-usd 2.00]

- Sin `--publicar` solo imprime el comentario (ensayo).
- Tu agente lee el diff **y** una copia de la rama del PR (`git worktree`, fuera del
  repo, que se borra al terminar) con herramientas de solo lectura: Read, Grep y Glob.
  Sin Bash: no corre nada, no cambia nada.
"""

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

RUBRICA = """Eres el revisor de PRs de este repo. Solo lees: no puedes ejecutar nada ni aprobar.
Tienes el diff abajo y, en tu directorio de trabajo, una copia de la rama del PR para leer
el contexto (Read, Grep, Glob). Revisa con esta rúbrica:
1. ¿Hace lo que dice el PR, ni más ni menos? (alcance)
2. Autorización multiempresa: ¿algún camino lee o escribe datos de otra empresa?
3. Errores: ¿algún `except` o valor por omisión convierte un fallo en un dato "válido"
   (por ejemplo, un score 0)?
4. Tests: ¿qué test fallaría si se revierte el cambio? Si ninguno, dilo.
5. Evidencia: ¿la descripción trae la salida real de las pruebas? No la des por buena:
   di qué comando hay que volver a correr.
Reporta solo hallazgos concretos, con archivo y línea. Si no encuentras nada importante,
dilo sin inventar. Tu confianza (0-100) es en que el PR se puede fusionar tal cual."""

ESQUEMA = {
    "type": "object",
    "properties": {
        "resumen": {"type": "string"},
        "confianza": {"type": "integer", "minimum": 0, "maximum": 100},
        "hallazgos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severidad": {"type": "string", "enum": ["bloqueante", "importante", "menor"]},
                    "archivo": {"type": "string"},
                    "linea": {"type": "string"},
                    "descripcion": {"type": "string"},
                    "como_verificar": {"type": "string"},
                },
                "required": ["severidad", "archivo", "descripcion", "como_verificar"],
            },
        },
        "test_que_falla_si_se_revierte": {"type": "string"},
    },
    "required": ["resumen", "confianza", "hallazgos", "test_que_falla_si_se_revierte"],
}
VARIABLES_DEL_ANFITRION = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT", "VIRTUAL_ENV")


def claude_exe() -> str:
    w = shutil.which("claude")
    if w and w.lower().endswith(".cmd"):  # npm en Windows: el .cmd no acepta saltos de línea
        real = pathlib.Path(w).parent / "node_modules/@anthropic-ai/claude-code/bin/claude.exe"
        if real.exists():
            return str(real)
    return w or "claude"


def run(*args: str, cwd: str | None = None) -> str:
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("numero")
    ap.add_argument("--model", default="opus")
    ap.add_argument("--max-usd", default="2.00")
    ap.add_argument("--publicar", action="store_true")
    a = ap.parse_args()

    info = json.loads(run("gh", "pr", "view", a.numero, "--json", "title,body,headRefName,baseRefName"))
    diff = run("gh", "pr", "diff", a.numero)
    prompt = (
        f"{RUBRICA}\n\nPR #{a.numero}: {info['title']} ({info['headRefName']} → {info['baseRefName']})\n"
        f"Descripción:\n{info.get('body') or '(vacía)'}\n\nDIFF:\n{diff}"
    )
    env = {k: v for k, v in os.environ.items() if k not in VARIABLES_DEL_ANFITRION}
    copia = pathlib.Path(tempfile.mkdtemp(prefix="revision-pr-"))
    shutil.rmtree(copia)  # git worktree quiere crear la carpeta
    run("git", "fetch", "-q", "origin", info["headRefName"])
    run("git", "worktree", "add", "-q", "--detach", str(copia), "FETCH_HEAD")
    try:
        p = subprocess.run(
            [claude_exe(), "-p", "--model", a.model, "--output-format", "json",
             "--tools", "Read,Grep,Glob", "--allowedTools", "Read", "Grep", "Glob",
             "--json-schema", json.dumps(ESQUEMA),
             "--setting-sources", "", "--strict-mcp-config",
             "--no-session-persistence", "--max-budget-usd", a.max_usd],
            # El prompt va por la entrada estándar: un diff grande no cabe en la línea de
            # órdenes de Windows (WinError 206), y en argv lo vería cualquier proceso.
            input=prompt, cwd=copia, env=env, capture_output=True, text=True, encoding="utf-8",
        )
    finally:
        run("git", "worktree", "remove", "--force", str(copia))
    try:
        res = json.loads(p.stdout)
    except json.JSONDecodeError:
        sys.exit(f"claude -p no devolvió JSON (exit {p.returncode})")
    if res.get("is_error") or "structured_output" not in res:
        # Un error NO es una revisión vacía: se reporta y se sale con código distinto de 0.
        sys.exit(f"revisión fallida: subtype={res.get('subtype')} terminal={res.get('terminal_reason')} "
                 f"errors={res.get('errors')}")
    r = res["structured_output"]
    modelos = ",".join(res.get("modelUsage", {}) or [a.model])

    lineas = [
        "### Revisión de tu agente (comenta, no aprueba)",
        f"**Confianza para fusionar:** {r['confianza']} % · modelo `{modelos}` · "
        f"costo {res.get('total_cost_usd', 0):.2f} USD · {res.get('duration_ms', 0) / 1000:.0f} s",
        "", r["resumen"], "",
    ]
    if r["hallazgos"]:
        lineas += ["| Severidad | Dónde | Hallazgo | Cómo verificarlo |", "|---|---|---|---|"]
        for h in r["hallazgos"]:
            donde = f"`{h['archivo']}`" + (f":{h['linea']}" if h.get("linea") else "")
            fila = [h["severidad"], donde, h["descripcion"], h["como_verificar"]]
            lineas.append("| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in fila) + " |")
    else:
        lineas.append("Sin hallazgos importantes.")
    lineas += [
        "", f"**¿Qué test falla si se revierte?** {r['test_que_falla_si_se_revierte']}", "",
        "_Script local (`herramientas/revisar_pr.py`), no un check de la CI. "
        "El merge lo decide una persona; el check que bloquea es la CI._",
    ]
    cuerpo = "\n".join(lineas)
    # Nada de rutas de esta máquina en un comentario público: la copia temporal y la
    # carpeta del usuario se reemplazan antes de publicar (lo mismo que el hook de `gh`).
    for ruta in (str(copia), str(copia).replace("\\", "/")):
        cuerpo = cuerpo.replace(ruta + os.sep, "").replace(ruta + "/", "").replace(ruta, ".")
    cuerpo = re.sub(r"(?i)([a-z]:[\\/]|/)(users|home)[\\/][^\\/\s`|]+", "~", cuerpo)
    with open(pathlib.Path(tempfile.gettempdir()) / f"revision-pr-{a.numero}.json", "w", encoding="utf-8") as f:
        json.dump({"revision": r, "costo_usd": res.get("total_cost_usd"), "ms": res.get("duration_ms"),
                   "modelos": modelos}, f, ensure_ascii=False, indent=2)
    if not a.publicar:
        print(cuerpo)
        return
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(cuerpo)
    print(run("gh", "pr", "comment", a.numero, "--body-file", f.name).strip())
    os.unlink(f.name)


if __name__ == "__main__":
    main()
