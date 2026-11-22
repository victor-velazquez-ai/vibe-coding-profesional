"""Mutation test del ejercicio S1-E1: quita el chequeo de empresa que AGREGÓ el agente y corre sus pruebas.
Si ninguna prueba falla, el aislamiento entre empresas no está protegido por ningún test.
Uso (dentro de tu copia del taller): uv run python ../herramientas/mutate_authz.py"""
import json, re, subprocess, pathlib, shutil

import os
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

def sh(*a):
    # UTF-8 everywhere: on Windows pytest otherwise crashes printing accents to a pipe (cp1252)
    return subprocess.run(a, capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV)

sh("git", "add", "-A", "-N", "--", "app")
diff = sh("git", "diff", "-U0", "--relative", "taller-vibe", "--", "app").stdout
added = {}  # file -> set of added line texts
cur = None
for line in diff.splitlines():
    if line.startswith("+++ b/"):
        cur = line[6:]
    elif line.startswith("+") and not line.startswith("+++") and cur:
        added.setdefault(cur, set()).add(line[1:])

# The tenant check: "Candidate.company_id == recruiter.company_id", "c.company_id != user.company_id",
# "Candidate.company_id == company_id"… (company/empresa/tenant). A whole comparison becomes True/False.
_SIDE = r"(?:\w+\.)*\w+"
_KEY = r"(?:company_id|empresa_id|tenant_id)"
PAT_EQ = re.compile(rf"(?:\w+\.)*{_KEY}\s*==\s*{_SIDE}|{_SIDE}\s*==\s*(?:\w+\.)*{_KEY}")
PAT_NE = re.compile(rf"(?:\w+\.)*{_KEY}\s*!=\s*{_SIDE}|{_SIDE}\s*!=\s*(?:\w+\.)*{_KEY}")
# filter_by(id=..., company_id=recruiter.company_id) -> the kwarg is dropped
PAT_KW = re.compile(rf",\s*{_KEY}\s*=\s*{_SIDE}|{_KEY}\s*=\s*{_SIDE}\s*,\s*")
mutated, backups = 0, {}
for f, lines in added.items():
    p = pathlib.Path(f)
    if not p.exists():
        continue
    src = p.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = False
    for i, l in enumerate(src):
        if l.rstrip("\r\n") in lines and (PAT_EQ.search(l) or PAT_NE.search(l) or ("filter_by" in l and PAT_KW.search(l))):
            new = PAT_NE.sub("False", PAT_EQ.sub("True", l))
            if "filter_by" in new:
                new = PAT_KW.sub("", new)
            if new != l:
                src[i] = new; changed = True; mutated += 1
    if changed:
        backups[f] = p.read_text(encoding="utf-8")
        p.write_text("".join(src), encoding="utf-8")

res = {"mutated_checks": mutated, "tests_failed_after_mutation": None, "protected": None}
if mutated:
    r = sh("uv", "run", "-q", "python", "-m", "pytest", "-q", "-p", "no:cacheprovider")
    out = r.stdout + r.stderr
    if re.search(r"\d+ (passed|failed)", out):
        m = re.search(r"(\d+) failed", out)
        res["tests_failed_after_mutation"] = int(m.group(1)) if m else 0
        res["protected"] = res["tests_failed_after_mutation"] > 0
        res["summary"] = (r.stdout.strip().splitlines() or [""])[-1][:120]
    else:  # pytest never ran (blocked launcher, import error...): say so instead of a false verdict
        res["error"] = out.strip()[-300:]
for f, txt in backups.items():
    pathlib.Path(f).write_text(txt, encoding="utf-8")
print(json.dumps(res))
