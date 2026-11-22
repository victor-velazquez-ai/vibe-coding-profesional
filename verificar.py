#!/usr/bin/env python3
"""verificar.py · ¿Tu equipo está listo para «Vibe Coding Profesional»?

Uso:
    python verificar.py              revisa las herramientas del curso
    python verificar.py --taller     además corre las pruebas del taller (uv run pytest -q)

Si no tienes Python instalado:  uv run python verificar.py

Solo usa la biblioteca estándar y funciona igual en Windows, macOS y Linux.
Sale con código 0 si todo lo obligatorio está en verde y con 1 si falta algo.
"""
from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Claude Code: Fable 5.2 exige 2.1.321 o superior (Opus 5.5 ≥ 2.1.280, Sonnet 5.5 ≥ 2.1.284,
# Haiku 5.5 ≥ 2.1.293). Con una versión anterior, los alias opus/sonnet/haiku/fable apuntan a
# modelos más viejos que los del curso. Fuente: code.claude.com/docs/en/model-config
CLAUDE_MIN = (2, 1, 321)
PYTHON_DEFAULT_SPEC = ">=3.13"

# Subprocesos en UTF-8: en Windows, pytest se cae al imprimir acentos a un pipe en cp1252.
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

OK, WARN, FAIL = "ok", "warn", "fail"


# ── salida ──────────────────────────────────────────────────────────────────────────────────
def _setup_console() -> dict:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    enc = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        "✓✗⚠→·".encode(enc)
        sym = {OK: "✓", WARN: "⚠", FAIL: "✗", "arrow": "→", "dot": "·"}
    except (UnicodeEncodeError, LookupError):
        sym = {OK: "OK", WARN: "!!", FAIL: "XX", "arrow": "->", "dot": "-"}
    color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    if color and os.name == "nt":
        os.system("")  # activa los colores ANSI en la consola de Windows 10+
    paint = {OK: "\033[32m", WARN: "\033[33m", FAIL: "\033[31m", "dim": "\033[2m", "end": "\033[0m"}
    if not color:
        paint = {k: "" for k in paint}
    return {"sym": sym, "c": paint}


UI: dict = {}


def line(status: str, label: str, detail: str = "", hint: str = "") -> None:
    s, c = UI["sym"], UI["c"]
    text = f"  {c[status]}{s[status]}{c['end']} {label}"
    if detail:
        text += f" {c['dim']}{s['dot']} {detail}{c['end']}"
    print(text)
    if hint and status != OK:
        for i, h in enumerate(hint.splitlines()):
            lead = f"{s['arrow']} " if i == 0 else "  "
            print(f"      {c[status]}{lead}{c['end']}{h}")


# ── utilidades ──────────────────────────────────────────────────────────────────────────────
def run(cmd: list, cwd: Path | None = None, timeout: int = 60) -> subprocess.CompletedProcess | None:
    """Corre un comando; None si el programa no existe. Nunca lanza excepción."""
    exe = shutil.which(cmd[0])
    if not exe:
        return None
    try:
        return subprocess.run([exe, *cmd[1:]], cwd=cwd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout, env=ENV)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", f"tardó más de {timeout} s")
    except OSError as e:
        return subprocess.CompletedProcess(cmd, 126, "", str(e))


def version_of(text: str) -> tuple | None:
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    return tuple(int(x or 0) for x in m.groups()) if m else None


def vstr(v: tuple) -> str:
    return ".".join(str(x) for x in v)


def os_name() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


INSTALL = {
    "uv": {
        "windows": 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"',
        "macos": "curl -LsSf https://astral.sh/uv/install.sh | sh",
        "linux": "curl -LsSf https://astral.sh/uv/install.sh | sh",
    },
    "git": {
        "windows": "winget install --id Git.Git -e   (Git for Windows: trae Git Bash, que usa Claude Code)",
        "macos": "xcode-select --install   (o: brew install git)",
        "linux": "sudo apt install git   (o el gestor de paquetes de tu distro)",
    },
    "gh": {
        "windows": "winget install --id GitHub.cli -e",
        "macos": "brew install gh",
        "linux": "https://github.com/cli/cli#installation",
    },
    "docker": {
        "windows": "Docker Desktop, https://docs.docker.com/desktop/",
        "macos": "Docker Desktop, https://docs.docker.com/desktop/",
        "linux": "Docker Engine, https://docs.docker.com/engine/install/",
    },
    "claude": {
        "windows": "irm https://claude.ai/install.ps1 | iex   (en PowerShell)",
        "macos": "curl -fsSL https://claude.ai/install.sh | bash",
        "linux": "curl -fsSL https://claude.ai/install.sh | bash",
    },
}


def install_hint(tool: str) -> str:
    return "Instálalo: " + INSTALL[tool][os_name()]


# ── chequeos ────────────────────────────────────────────────────────────────────────────────
def check_system() -> str:
    if sys.platform == "win32":
        build = sys.getwindowsversion().build  # type: ignore[attr-defined]
        name = f"Windows {'11' if build >= 22000 else '10'} (build {build})"
        if build < 17763:
            line(FAIL, "Sistema", name, "Claude Code necesita Windows 10 versión 1809 (build 17763) o superior.")
            return FAIL
        line(OK, "Sistema", name)
        return OK
    if sys.platform == "darwin":
        mac = platform.mac_ver()[0] or "?"
        v = version_of(mac)
        if v and v[0] < 13:
            line(FAIL, "Sistema", f"macOS {mac}", "Claude Code necesita macOS 13 o superior.")
            return FAIL
        line(OK, "Sistema", f"macOS {mac}")
        return OK
    pretty = "Linux"
    try:
        for row in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if row.startswith("PRETTY_NAME="):
                pretty = row.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    if "microsoft" in platform.release().lower():
        pretty += " (WSL)"
    line(OK, "Sistema", pretty)
    return OK


def check_uv() -> str:
    r = run(["uv", "--version"])
    if r is None or r.returncode != 0:
        line(FAIL, "uv no está instalado", "", install_hint("uv") + "\nCon uv no necesitas instalar Python a mano: él descarga la versión correcta.")
        return FAIL
    line(OK, "uv", vstr(version_of(r.stdout) or (0,)))
    return OK


def python_spec(root: Path) -> tuple:
    """requires-python del taller (la fuente de verdad); si no hay taller, el del plan."""
    pp = root / "taller" / "pyproject.toml"
    if not pp.exists():
        return PYTHON_DEFAULT_SPEC, "plan del curso"
    text = pp.read_text(encoding="utf-8")
    try:
        import tomllib  # Python 3.11+
        spec = tomllib.loads(text).get("project", {}).get("requires-python")
    except ImportError:
        m = re.search(r'^requires-python\s*=\s*"([^"]+)"', text, re.M)
        spec = m.group(1) if m else None
    return (spec or PYTHON_DEFAULT_SPEC), "taller/pyproject.toml"


def satisfies(v: tuple, spec: str) -> bool:
    """Solo para especificaciones simples (>=, >, ==, <, <=, separadas por comas)."""
    for part in spec.split(","):
        m = re.match(r"\s*(>=|<=|==|>|<|~=)\s*([\d.]+)", part)
        if not m:
            continue
        op, ref = m.group(1), version_of(m.group(2)) or (0,)
        n = max(len(ref), 2)
        a, b = tuple(v[:n]), tuple(ref[:n])
        ok = {">=": a >= b, "<=": a <= b, "==": a == b, ">": a > b, "<": a < b, "~=": a >= b}[op]
        if not ok:
            return False
    return True


def check_python(root: Path, uv_ok: bool) -> str:
    spec, source = python_spec(root)
    label = f"Python para el taller ({spec})"
    if uv_ok:
        r = run(["uv", "python", "find", spec], cwd=root)
        if r is not None and r.returncode == 0 and r.stdout.strip():
            exe = r.stdout.strip().splitlines()[-1]
            v = run([exe, "-c", "import platform; print(platform.python_version())"])
            shown = v.stdout.strip() if v is not None and v.returncode == 0 else exe
            line(OK, label, f"{shown} (uv la encuentra)")
            return OK
        want = re.search(r"[\d]+\.[\d]+", spec)
        line(WARN, label, "aún no la tienes",
             f"uv la descargará sola al correr `uv sync` (necesitas internet).\nO hazlo ya: uv python install {want.group(0) if want else ''}".rstrip())
        return WARN
    here = sys.version_info[:3]
    if satisfies(here, spec):
        line(OK, label, f"{vstr(here)} (sin uv)")
        return OK
    line(FAIL, label, f"tienes {vstr(here)}", "Instala uv (arriba): él descarga la versión que pide el taller.")
    return FAIL


def git_bash_found(git_exe: str) -> bool:
    if git_exe:
        root = Path(git_exe).resolve().parent.parent  # …\Git\cmd\git.exe -> …\Git
        if (root / "bin" / "bash.exe").exists():
            return True
    bash = shutil.which("bash") or ""
    return bool(bash) and "system32" not in bash.lower()  # System32\bash.exe es el lanzador de WSL


def check_git() -> list:
    r = run(["git", "--version"])
    if r is None or r.returncode != 0:
        line(FAIL, "git no está instalado", "", install_hint("git"))
        return [FAIL]
    line(OK, "git", vstr(version_of(r.stdout) or (0,)))
    if sys.platform == "win32" and not git_bash_found(shutil.which("git") or ""):
        line(WARN, "Git Bash no aparece", "", "Claude Code usa Git Bash para su herramienta Bash; sin él usa PowerShell.\nInstala Git for Windows: winget install --id Git.Git -e")
        return [OK, WARN]
    return [OK]


def check_gh() -> list:
    r = run(["gh", "--version"])
    if r is None or r.returncode != 0:
        line(FAIL, "GitHub CLI (gh) no está instalado", "", install_hint("gh") + "\nLo usas desde la sección 3.")
        return [FAIL]
    line(OK, "GitHub CLI (gh)", vstr(version_of(r.stdout) or (0,)))
    a = run(["gh", "auth", "status"], timeout=30)
    if a is not None and a.returncode == 0:
        line(OK, "gh con sesión iniciada")
        return [OK, OK]
    line(WARN, "gh sin sesión", "", "Corre: gh auth login   (lo necesitas en la sección 3)")
    return [OK, WARN]


def check_docker() -> list:
    r = run(["docker", "--version"])
    if r is None or r.returncode != 0:
        line(FAIL, "Docker no está instalado", "", install_hint("docker") + "\nDesde la sección 2, Postgres 16 corre en Docker.")
        return [FAIL]
    line(OK, "Docker", vstr(version_of(r.stdout) or (0,)))
    out = [OK]
    d = run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=30)
    if d is not None and d.returncode == 0 and d.stdout.strip():
        line(OK, "Docker está corriendo", f"servidor {d.stdout.strip()}")
        out.append(OK)
    else:
        start = "sudo systemctl start docker" if os_name() == "linux" else "abre Docker Desktop"
        line(FAIL, "Docker está instalado pero no está corriendo", "", f"Arráncalo ({start}) y vuelve a correr: python verificar.py")
        out.append(FAIL)
    c = run(["docker", "compose", "version", "--short"], timeout=30)
    if c is not None and c.returncode == 0 and c.stdout.strip():
        line(OK, "Docker Compose", c.stdout.strip().lstrip("v"))
        out.append(OK)
    else:
        line(FAIL, "Falta Docker Compose (el comando `docker compose`)", "", "Docker Desktop ya lo trae; en Linux: https://docs.docker.com/compose/install/linux/")
        out.append(FAIL)
    return out


def check_claude() -> str:
    r = run(["claude", "--version"], timeout=60)
    if r is None or r.returncode != 0:
        line(FAIL, "Claude Code no está instalado", "",
             install_hint("claude") + "\nNecesitas un plan Pro, Max, Ultra, Team o Enterprise, o una cuenta de Console.")
        return FAIL
    v = version_of(r.stdout)
    if not v:
        line(WARN, "Claude Code", "no pude leer la versión", "Corre: claude --version")
        return WARN
    if v < CLAUDE_MIN:
        line(FAIL, f"Claude Code {vstr(v)}", f"el curso necesita {vstr(CLAUDE_MIN)} o más",
             "Corre: claude update\n(con una versión anterior, opus/sonnet/haiku/fable apuntan a modelos más viejos)")
        return FAIL
    line(OK, "Claude Code", vstr(v))
    return OK


def check_taller(root: Path) -> str:
    taller = root / "taller"
    if not (taller / "pyproject.toml").exists():
        line(FAIL, "No encuentro taller/", str(taller), "Corre verificar.py desde la raíz del repo del curso.")
        return FAIL
    branch = run(["git", "describe", "--tags", "--always"], cwd=taller)
    where = branch.stdout.strip() if branch is not None and branch.returncode == 0 else "checkout actual"
    print(f"    corriendo `uv run pytest -q` en taller/ ({where})…", flush=True)
    r = run(["uv", "run", "pytest", "-q", "-p", "no:cacheprovider"], cwd=taller, timeout=900)
    if r is None:
        line(FAIL, "Pruebas del taller", "falta uv", install_hint("uv"))
        return FAIL
    lines = [x for x in (r.stdout + "\n" + r.stderr).splitlines() if x.strip()]
    summary = next((x for x in reversed(lines) if re.search(r"\d+ (passed|failed|error)", x)), lines[-1] if lines else "")
    summary = summary.strip("= ").strip()
    if r.returncode == 0:
        line(OK, "Pruebas del taller", summary)
        return OK
    tail = "\n".join(lines[-6:])
    line(FAIL, "Pruebas del taller", summary or f"código {r.returncode}",
         "Revisa la salida de abajo. Si el checkpoint usa Postgres, levanta la base primero (kit S2).\n" + tail)
    return FAIL


# ── main ────────────────────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="Revisa que tu equipo esté listo para el curso.")
    ap.add_argument("--taller", action="store_true", help="además corre las pruebas del taller")
    ap.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parent,
                    help="carpeta del repo del curso (por defecto, la de este script)")
    args = ap.parse_args()
    UI.update(_setup_console())
    root = args.raiz.resolve()

    print("\nVerificando tu equipo para «Vibe Coding Profesional»…\n")
    results: list = []
    results.append(check_system())
    uv = check_uv()
    results.append(uv)
    results.append(check_python(root, uv == OK))
    results += check_git()
    results += check_gh()
    results += check_docker()
    results.append(check_claude())
    if args.taller:
        results.append(check_taller(root))

    n_ok, n_warn, n_fail = (results.count(x) for x in (OK, WARN, FAIL))
    s, c = UI["sym"], UI["c"]
    print(f"\nResultado: {n_ok} {s[OK]} {s['dot']} {n_warn} {s[WARN]} {s['dot']} {n_fail} {s[FAIL]}")
    if n_fail:
        msg = "Falta 1 cosa. Arréglala con la pista" if n_fail == 1 else f"Faltan {n_fail} cosas. Arréglalas con las pistas"
        print(f"{c[FAIL]}{s[FAIL]} {msg} de arriba{c['end']} y vuelve a correr: python verificar.py\n")
        return 1
    extra = " (los avisos ⚠ no bloquean)" if n_warn and s[WARN] == "⚠" else (" (los avisos no bloquean)" if n_warn else "")
    print(f"{c[OK]}{s[OK]} Todo listo{extra}. Nos vemos en la sección 1.{c['end']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
