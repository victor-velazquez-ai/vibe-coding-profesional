#!/usr/bin/env python3
"""uso_sesiones.py: cuánto costó una sesión de agente, y cuánto leyó para escribir tan poco.

Lee capturas de Claude Code en formato stream-json, es decir, lo que produce:

    claude -p "tu tarea" --output-format stream-json --verbose > sesion.jsonl

Por sesión reporta:
- modelos;
- llamadas al modelo (hilo principal y subagentes);
- tokens leídos (entrada + escritura de caché + lectura de caché) y tokens escritos (salida);
- costo y duración;
- herramientas usadas y subagentes;
- cuántas veces releyó los mismos archivos.

Por grupo (p. ej. las 10 corridas de un piloto) da los totales y promedios, y separa
el costo en lectura de caché, escritura de caché, entrada y salida.

Uso:
    python -I uso_sesiones.py sesion.jsonl
    python -I uso_sesiones.py capturas/                  # todas las .jsonl (recursivo)
    python -I uso_sesiones.py capturas/ --md > uso.md    # tablas en Markdown
    python -I uso_sesiones.py capturas/ --json > uso.json
    python -I uso_sesiones.py capturas/ --agrupar carpeta
    python -I uso_sesiones.py capturas/ --detalle        # + archivos releídos por sesión
    python -I uso_sesiones.py capturas/ --md --salida uso.md   # escribe el archivo en UTF-8

Solo biblioteca estándar; Python 3.9 o superior; Windows, macOS y Linux.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# Estructura de precios de lista de Anthropic, relativa al precio de ENTRADA de cada modelo.
LEER_CACHE = 0.10        # leer contexto que ya estaba en caché
ESCRIBIR_CACHE_5M = 1.25  # escribir caché que dura 5 minutos
ESCRIBIR_CACHE_1H = 2.00  # escribir caché que dura 1 hora
RATIO_SALIDA = 5.0        # salida = 5x entrada en los modelos Claude actuales; se verifica con tus datos
TOLERANCIA_PRECIO = 0.02  # si el precio implícito varía más de 2 % entre sesiones, se avisa

HERRAMIENTAS_AGENTE = {"Agent", "Task"}
HERRAMIENTAS_SHELL = {"Bash", "PowerShell"}
LECTORES_SHELL = {"cat", "type", "get-content", "gc", "head", "tail", "less", "more", "bat"}


class NoEsSesion(Exception):
    """El archivo no es una captura stream-json de Claude Code (o está vacío)."""


# ---------------------------------------------------------------- lectura

def cargar(path: Path) -> tuple[list[dict], int]:
    objs, malas = [], 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                o = json.loads(raw)
            except json.JSONDecodeError:
                malas += 1  # p. ej. advertencias de la terminal mezcladas en la salida
                continue
            if isinstance(o, dict):
                objs.append(o)
    return objs, malas


def segundos_sidecar(path: Path) -> float | None:
    """capture.sh guarda junto a la .jsonl un .ts con los ms de llegada de cada línea."""
    ts = path.with_suffix(".ts")
    if not ts.exists():
        return None
    try:
        vals = [int(x) for x in ts.read_text(encoding="utf-8").split()]
    except (ValueError, OSError):
        return None  # p. ej. un archivo TypeScript con el mismo nombre: no es un sidecar
    return vals[-1] / 1000 if vals else None


def fecha(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def normalizar_ruta(p: str) -> str:
    p = p.strip().replace("\\", "/").rstrip("/")
    if re.match(r"^[A-Za-z]:/", p) or "\\" in p:
        p = p.lower()  # Windows no distingue mayúsculas en rutas
    return p


def lecturas_shell(cmd: str) -> int:
    """Heurística: comandos de shell que leen archivos (cat, Get-Content, head, sed -n…)."""
    n = 0
    for seg in re.split(r"&&|\|\||;|\|", cmd or ""):
        w = seg.strip().split()
        if not w:
            continue
        primero = w[0].lower()
        if primero in LECTORES_SHELL or (primero == "sed" and "-n" in w):
            n += 1
    return n


# ---------------------------------------------------------------- análisis de una sesión

def analizar(path: Path) -> dict:
    objs, malas = cargar(path)
    if not objs:
        raise NoEsSesion("archivo vacío" if malas == 0 else "sin líneas JSON válidas")
    init = next((o for o in objs if o.get("type") == "system" and o.get("subtype") == "init"), None)
    resultados = [o for o in objs if o.get("type") == "result"]
    if init is None and not resultados and not any(o.get("type") == "assistant" for o in objs):
        raise NoEsSesion("no es una sesión de Claude Code (stream-json)")

    avisos: list[str] = []
    if malas:
        avisos.append(f"{malas} líneas no-JSON ignoradas")

    # Mensajes del modelo. Cada mensaje llega partido en varias líneas (un bloque por línea) con la
    # misma "usage": se deduplica por id. Los tokens de entrada/caché de cada línea son finales;
    # los de salida NO (vienen parciales durante el streaming), por eso la salida sale del "result".
    msgs: dict[str, dict] = {}
    usos: dict[str, tuple[str, dict, str | None]] = {}
    for i, o in enumerate(objs):
        if o.get("type") != "assistant":
            continue
        m = o.get("message") or {}
        modelo = m.get("model") or "?"
        if modelo.startswith("<"):  # mensajes sintéticos (errores de la API, etc.): no son llamadas
            continue
        mid = m.get("id") or o.get("uuid") or f"linea-{i}"
        rec = msgs.setdefault(mid, {"modelo": modelo, "usage": {}, "padre": o.get("parent_tool_use_id")})
        if m.get("usage"):
            rec["usage"] = m["usage"]
        for b in m.get("content") or []:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                usos[b.get("id") or f"{mid}-{len(usos)}"] = (b.get("name") or "?", b.get("input") or {}, o.get("parent_tool_use_id"))

    def ctx(u: dict) -> int:
        return (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0)

    principal = [r for r in msgs.values() if not r["padre"]]
    sub = [r for r in msgs.values() if r["padre"]]
    contextos = [ctx(r["usage"]) for r in principal if r["usage"]]

    # Escrituras de caché de 5 min vs 1 h, por modelo (cuestan distinto).
    cache_split: dict[str, list[int]] = {}
    for r in msgs.values():
        cc = (r["usage"] or {}).get("cache_creation") or {}
        s = cache_split.setdefault(r["modelo"], [0, 0])
        s[0] += cc.get("ephemeral_5m_input_tokens") or 0
        s[1] += cc.get("ephemeral_1h_input_tokens") or 0

    # Tokens por hilo (entrada + caché), útiles para ver cuánto lee un subagente.
    leidos_sub = sum(ctx(r["usage"]) for r in sub)
    leidos_principal = sum(ctx(r["usage"]) for r in principal)

    # Herramientas
    herr = Counter(n for n, _, _ in usos.values())
    herr_sub = Counter(n for n, _, p in usos.values() if p)
    lect_p, lect_s = Counter(), Counter()
    shell = 0
    for nombre, inp, padre in usos.values():
        if nombre == "Read":
            ruta = normalizar_ruta(str(inp.get("file_path") or inp.get("path") or ""))
            (lect_s if padre else lect_p)[ruta] += 1
        elif nombre in HERRAMIENTAS_SHELL:
            shell += lecturas_shell(str(inp.get("command") or ""))
    todas = lect_p + lect_s
    total_lect = sum(todas.values())
    releidos = {r: (lect_p[r], lect_s[r]) for r, n in todas.items() if n > 1}

    subagentes = sum(1 for n, _, p in usos.values() if n in HERRAMIENTAS_AGENTE and not p)
    subagentes = max(subagentes, sum(1 for o in objs if o.get("subtype") == "task_started" and o.get("task_type") == "local_agent"))
    for r in resultados:
        subagentes = max(subagentes, ((r.get("subagent_stats") or {}).get("spawned") or 0))

    denegados = {o.get("tool_use_id") for o in objs if o.get("type") == "system" and o.get("subtype") == "permission_denied"}
    for r in resultados:
        denegados |= {d.get("tool_use_id") for d in (r.get("permission_denials") or [])}
    denegados.discard(None)

    # Totales: el último "result" trae modelUsage ACUMULADO de la sesión (incluye subagentes,
    # llamadas internas pequeñas del CLI y, si la sesión fue reanudada, también lo anterior).
    ultimo = resultados[-1] if resultados else {}
    model_usage = {k: dict(v) for k, v in (ultimo.get("modelUsage") or {}).items()}
    costo = ultimo.get("total_cost_usd")
    if not resultados:
        avisos.append("sin línea result: sesión cortada; costo y salida desconocidos")
    elif ultimo.get("is_error") or ultimo.get("subtype") != "success":
        avisos.append(f"terminó con estado '{ultimo.get('subtype')}' (is_error={ultimo.get('is_error')})")

    # Duración (reloj de pared)
    pared = segundos_sidecar(path)
    marcas = [t for t in (fecha(o.get("timestamp")) for o in objs) if t]
    span = (max(marcas) - min(marcas)) if len(marcas) >= 2 else 0.0
    suma_dur = sum((r.get("duration_ms") or 0) for r in resultados) / 1000
    if pared is None:
        pared = max(suma_dur, span) or None

    timing = (init or {}).get("startup_timing") or {}
    reanudada = any(k.startswith("resume_") for k in (timing.get("phases") or {}))
    inicio = timing.get("time_origin_ms")
    inicio = inicio / 1000 if inicio else (min(marcas) if marcas else 0.0)

    plan = None
    for o in objs:
        if o.get("type") == "rate_limit_event":
            info = o.get("rate_limit_info") or {}
            ventanas = info.get("unifiedWindows") or {}
            if ventanas:
                k, v = next(iter(ventanas.items()))
                plan = {"ventana": k, "uso": v.get("utilization")}
            break

    return {
        "archivo": str(path),
        "session_id": (init or {}).get("session_id") or ultimo.get("session_id"),
        "modelo_principal": (init or {}).get("model") or (principal[0]["modelo"] if principal else None),
        "facturacion": "suscripción (costo = equivalente a precio de API)" if (init or {}).get("apiKeySource") == "none" else "API key",
        "permisos": (init or {}).get("permissionMode"),
        "reanudada": reanudada,
        "inicio": inicio,
        "estado": ("error" if ultimo.get("is_error") else (ultimo.get("subtype") or "?")) if resultados else "incompleta",
        "resultados": len(resultados),
        "turnos_cli": ultimo.get("num_turns"),
        "llamadas": len(principal),
        "llamadas_sub": len(sub),
        # Piso: lo que carga la PRIMERA llamada antes de leer tu código (prompt de sistema,
        # herramientas, CLAUDE.md, tu instrucción). Se vuelve a pagar en cada llamada.
        "contexto_inicial": contextos[0] if contextos else None,
        "contexto_medio": round(statistics.mean(contextos)) if contextos else None,
        "contexto_max": max(contextos) if contextos else None,
        "leidos_principal": leidos_principal,
        "leidos_sub": leidos_sub,
        "model_usage": model_usage,
        "_acum_usage": {k: dict(v) for k, v in model_usage.items()},
        "_acum_costo": costo,
        "costo_usd": costo,
        "cache_split": cache_split,
        "duracion_s": round(pared, 1) if pared else None,
        "herramientas": dict(herr.most_common()),
        "herramientas_sub": dict(herr_sub.most_common()),
        "subagentes": subagentes,
        "lecturas": total_lect,
        "archivos_leidos": len(todas),
        "relecturas": total_lect - len(todas),
        "releidos_entre_agentes": len(set(lect_p) & set(lect_s)),
        "releidos": releidos,
        "lecturas_shell": shell,
        "denegados": len(denegados),
        "uso_plan_al_inicio": plan,
        "avisos": avisos,
    }


# ---------------------------------------------------------------- sesiones reanudadas y costo

def descontar_reanudadas(sesiones: list[dict]) -> None:
    """Una sesión reanudada (--resume / --continue) trae modelUsage y costo ACUMULADOS desde
    el inicio de la sesión original. Si la corrida anterior está entre los archivos, se resta."""
    por_id: dict[str, list[dict]] = {}
    for s in sorted(sesiones, key=lambda s: s["inicio"]):
        sid = s["session_id"]
        previas = [p for p in por_id.get(sid, []) if p["_acum_costo"] is not None] if sid else []
        if previas:
            prev = previas[-1]
            for modelo, v in s["model_usage"].items():
                pv = prev["_acum_usage"].get(modelo) or {}
                for k in ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens", "costUSD", "thinkingTokens"):
                    if isinstance(v.get(k), (int, float)) and isinstance(pv.get(k), (int, float)):
                        v[k] = max(v[k] - pv[k], 0)
            if s["costo_usd"] is not None:
                s["costo_usd"] = max(s["costo_usd"] - prev["_acum_costo"], 0.0)
            s["avisos"].append(f"reanuda la sesión de {Path(prev['archivo']).name}: se descontó lo anterior")
        elif s["reanudada"]:
            s["avisos"].append("reanudada: el costo INCLUYE la sesión anterior (no está entre los archivos)")
        if sid:
            por_id.setdefault(sid, []).append(s)


def desglosar(s: dict, ratio: float) -> None:
    """Separa el costo de cada modelo en lectura de caché, escritura de caché, entrada y salida.
    Usa la estructura de precios de lista (lectura 0.1x, escritura 1.25x/2x, salida = ratio x)
    y deja que TUS datos fijen el precio de entrada: precio = costo / tokens ponderados."""
    partes = {"lectura_cache": 0.0, "escritura_cache": 0.0, "entrada": 0.0, "salida": 0.0}
    precios = {}
    ok = True
    for modelo, v in s["model_usage"].items():
        costo = v.get("costUSD")
        if not costo:
            continue
        ent = v.get("inputTokens") or 0
        sal = v.get("outputTokens") or 0
        lee = v.get("cacheReadInputTokens") or 0
        esc = v.get("cacheCreationInputTokens") or 0
        c5, c1 = s["cache_split"].get(modelo, [0, 0])
        if c5 + c1 > esc > 0:  # descuadre (p. ej. tras descontar una reanudada): se prorratea
            f = esc / (c5 + c1)
            c5, c1 = c5 * f, c1 * f
        c5 += max(esc - c5 - c1, 0)  # lo no detallado se asume de 5 minutos (el valor por defecto)
        peso = ent + LEER_CACHE * lee + ESCRIBIR_CACHE_5M * c5 + ESCRIBIR_CACHE_1H * c1 + ratio * sal
        if peso <= 0:
            ok = False
            continue
        p = costo / peso
        precios[modelo] = p * 1e6
        partes["lectura_cache"] += p * LEER_CACHE * lee
        partes["escritura_cache"] += p * (ESCRIBIR_CACHE_5M * c5 + ESCRIBIR_CACHE_1H * c1)
        partes["entrada"] += p * ent
        partes["salida"] += p * ratio * sal
    s["desglose_usd"] = {k: round(v, 6) for k, v in partes.items()} if ok and precios else None
    s["precio_entrada_implicito"] = {k: round(v, 4) for k, v in precios.items()}


def tokens(s: dict) -> dict:
    t = {"entrada": 0, "salida": 0, "lectura_cache": 0, "escritura_cache": 0, "pensamiento": 0}
    for v in s["model_usage"].values():
        t["entrada"] += v.get("inputTokens") or 0
        t["salida"] += v.get("outputTokens") or 0
        t["lectura_cache"] += v.get("cacheReadInputTokens") or 0
        t["escritura_cache"] += v.get("cacheCreationInputTokens") or 0
        t["pensamiento"] += v.get("thinkingTokens") or 0
    t["leidos"] = t["entrada"] + t["lectura_cache"] + t["escritura_cache"]
    return t


# ---------------------------------------------------------------- grupos

def clave_grupo(path: Path, raiz: Path, modo: str) -> str:
    try:
        rel = path.resolve().relative_to(raiz.resolve())
    except ValueError:
        rel = Path(path.name)
    carpeta = rel.parent.as_posix()
    carpeta = "" if carpeta == "." else carpeta
    if modo == "carpeta":
        return carpeta or "."
    if modo == "ninguno":
        return rel.with_suffix("").as_posix()
    base = re.sub(r"[-_ ]?\d+$", "", path.stem) or path.stem  # vibe-01 … vibe-10 -> vibe
    return f"{carpeta}/{base}" if carpeta else base


def resumir(nombre: str, ss: list[dict]) -> dict:
    con = [s for s in ss if s["costo_usd"] is not None]
    costos = [s["costo_usd"] for s in con]
    durs = [s["duracion_s"] for s in ss if s["duracion_s"]]
    tk = [s["tokens"] for s in con]
    leidos = sum(t["leidos"] for t in tk)
    salida = sum(t["salida"] for t in tk)
    partes = {"lectura_cache": 0.0, "escritura_cache": 0.0, "entrada": 0.0, "salida": 0.0}
    for s in con:
        for k, v in (s.get("desglose_usd") or {}).items():
            partes[k] += v
    precios: dict[str, list[float]] = {}
    for s in con:
        for m, p in s["precio_entrada_implicito"].items():
            precios.setdefault(m, []).append(p)
    modelos = Counter(s["modelo_principal"] for s in ss)
    return {
        "grupo": nombre,
        "sesiones": len(ss),
        "con_costo": len(con),
        "modelo": ", ".join(m or "?" for m, _ in modelos.most_common()),
        "costo_total": round(sum(costos), 4) if costos else None,
        "costo_medio": round(statistics.mean(costos), 4) if costos else None,
        "costo_min": round(min(costos), 4) if costos else None,
        "costo_max": round(max(costos), 4) if costos else None,
        "duracion_media_s": round(statistics.mean(durs), 1) if durs else None,
        "duracion_total_s": round(sum(durs), 1) if durs else None,
        "llamadas_medias": round(statistics.mean(s["llamadas"] + s["llamadas_sub"] for s in ss), 1),
        "contexto_inicial_medio": round(statistics.mean(c)) if (c := [s["contexto_inicial"] for s in ss if s["contexto_inicial"]]) else None,
        "contexto_medio": round(statistics.mean(c)) if (c := [s["contexto_medio"] for s in ss if s["contexto_medio"]]) else None,
        "leidos_medios": round(leidos / len(tk)) if tk else None,
        "salida_media": round(salida / len(tk)) if tk else None,
        "pct_lectura_cache": round(100 * sum(t["lectura_cache"] for t in tk) / leidos, 1) if leidos else None,
        "leidos_por_escrito": round(leidos / salida) if salida else None,
        "relecturas_medias": round(statistics.mean(s["relecturas"] for s in ss), 1),
        "con_subagentes": sum(1 for s in ss if s["subagentes"]),
        "denegados": sum(s["denegados"] for s in ss),
        "desglose_usd": {k: round(v, 4) for k, v in partes.items()},
        "pct_costo_contexto": round(100 * (partes["lectura_cache"] + partes["escritura_cache"] + partes["entrada"]) / sum(partes.values()), 1) if sum(partes.values()) else None,
        "precio_entrada_implicito": {m: [round(min(v), 3), round(max(v), 3)] for m, v in precios.items()},
    }


# ---------------------------------------------------------------- formato

def k(n: float | int | None) -> str:
    if n is None:
        return "–"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(int(n))


def usd(x: float | None, d: int = 3) -> str:
    return "–" if x is None else f"${x:.{d}f}"


def mmss(sec: float | None) -> str:
    if not sec:
        return "–"
    sec = int(round(sec))
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


def corto_modelo(m: str | None) -> str:
    if not m:
        return "?"
    m = re.sub(r"^claude-", "", m)
    return re.sub(r"-\d{8}$", "", m)


def herramientas_txt(h: dict, n: int = 4) -> str:
    items = list(h.items())
    txt = " · ".join(f"{a} {b}" for a, b in items[:n])
    return txt + (" · …" if len(items) > n else "")


def tabla(titulos: list[str], filas: list[list[str]], md: bool, derecha: set[int] = frozenset()) -> str:
    if md:
        sep = ["---:" if i in derecha else "---" for i in range(len(titulos))]
        out = ["| " + " | ".join(titulos) + " |", "|" + "|".join(sep) + "|"]
        out += ["| " + " | ".join(f) + " |" for f in filas]
        return "\n".join(out)
    anchos = [max(len(str(x)) for x in col) for col in zip(titulos, *filas)]
    def linea(f):
        return "  ".join((str(x).rjust(w) if i in derecha else str(x).ljust(w)) for i, (x, w) in enumerate(zip(f, anchos)))
    return "\n".join([linea(titulos), linea(["-" * w for w in anchos])] + [linea(f) for f in filas])


def informe(sesiones: list[dict], grupos: list[dict], total: dict, omitidos: list[tuple[str, str]], md: bool, detalle: bool) -> str:
    h = (lambda t: f"\n## {t}\n") if md else (lambda t: f"\n== {t} ==\n")
    out = []
    out.append("# Uso de las sesiones" if md else "USO DE LAS SESIONES")
    out.append(h("Por sesión"))
    filas = []
    for s in sesiones:
        t = s["tokens"]
        llam = f"{s['llamadas']}" + (f" (+{s['llamadas_sub']} sub)" if s["llamadas_sub"] else "")
        filas.append([
            s["nombre"], corto_modelo(s["modelo_principal"]), llam,
            k(t["leidos"]) if s["costo_usd"] is not None else "–",
            (f"{100 * t['lectura_cache'] / t['leidos']:.0f} %" if t["leidos"] else "–"),
            k(t["salida"]) if s["costo_usd"] is not None else "–",
            usd(s["costo_usd"]), mmss(s["duracion_s"]),
            f"{s['lecturas']} ({s['relecturas']})",
            str(s["subagentes"]) if s["subagentes"] else "–",
            herramientas_txt(s["herramientas"]),
        ])
    out.append(tabla(["Sesión", "Modelo", "Llamadas", "Tokens leídos", "de caché", "Escritos", "Costo", "Duración",
                      "Read (relecturas)", "Subagentes", "Herramientas"], filas, md, derecha={2, 3, 4, 5, 6, 7, 8}))

    out.append(h("Por grupo"))
    filas = []
    for g in grupos + [total]:
        filas.append([
            g["grupo"], str(g["sesiones"]) + (f" ({g['con_costo']} con costo)" if g["con_costo"] != g["sesiones"] else ""),
            corto_modelo(g["modelo"]) if "," not in g["modelo"] else "varios",
            usd(g["costo_total"], 2), f"{usd(g['costo_medio'])} ({usd(g['costo_min'])}–{usd(g['costo_max'])})",
            mmss(g["duracion_media_s"]), f"{g['llamadas_medias']:.1f}",
            k(g["leidos_medios"]), f"{g['pct_lectura_cache']:.0f} %" if g["pct_lectura_cache"] is not None else "–",
            k(g["salida_media"]),
            f"{g['leidos_por_escrito']}:1" if g["leidos_por_escrito"] else "–",
            k(g["contexto_inicial_medio"]), k(g["contexto_medio"]),
            f"{g['relecturas_medias']:.1f}", str(g["denegados"]),
        ])
    out.append(tabla(["Grupo", "Sesiones", "Modelo", "Costo total", "Costo medio (mín–máx)", "Duración media", "Llamadas",
                      "Leídos (media)", "de caché", "Escritos (media)", "Leídos:escritos", "Contexto 1ª llamada",
                      "Contexto por llamada", "Relecturas", "Permisos denegados"], filas, md,
                     derecha={3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14}))

    out.append(h("¿En qué se fue el dinero?"))
    filas = []
    for g in grupos + [total]:
        d = g["desglose_usd"]
        tot = sum(d.values()) or 1
        pct = lambda x: f"{usd(x, 2)} ({100 * x / tot:.0f} %)"
        precios = "; ".join(f"{corto_modelo(m)} ${a:.2f}" + (f"–{b:.2f}" if abs(b - a) / a > 0.005 else "") + "/M"
                            for m, (a, b) in sorted(g["precio_entrada_implicito"].items()))
        filas.append([g["grupo"], pct(d["lectura_cache"]), pct(d["escritura_cache"]), pct(d["entrada"]), pct(d["salida"]),
                      f"{g['pct_costo_contexto']} %" if g["pct_costo_contexto"] is not None else "–", precios or "–"])
    out.append(tabla(["Grupo", "Leer caché", "Escribir caché", "Entrada", "Salida (incl. pensamiento)", "Costo de LEER",
                      "Precio entrada implícito"], filas, md, derecha={1, 2, 3, 4, 5}))

    if detalle:
        out.append(h("Detalle: archivos releídos y subagentes"))
        for s in sesiones:
            if not s["releidos"] and not s["subagentes"]:
                continue
            out.append(f"- **{s['nombre']}**" if md else f"* {s['nombre']}")
            if s["subagentes"]:
                out.append(f"  - subagentes: {s['subagentes']} · tokens leídos por subagentes: {k(s['leidos_sub'])} "
                           f"de {k(s['leidos_sub'] + s['leidos_principal'])} · herramientas de subagentes: {herramientas_txt(s['herramientas_sub'], 6) or '–'}")
            for ruta, (p, sb) in sorted(s["releidos"].items(), key=lambda x: -sum(x[1])):
                quien = f"{p} principal" + (f" + {sb} subagente" if sb else "")
                out.append(f"  - `{Path(ruta).name}` leído {p + sb} veces ({quien})")

    notas = []
    for s in sesiones:
        for a in s["avisos"]:
            notas.append(f"{s['nombre']}: {a}")
    for nombre, motivo in omitidos:
        notas.append(f"{nombre}: omitido ({motivo})")
    fact = {s["facturacion"] for s in sesiones}
    out.append(h("Notas"))
    notas_fijas = [
        "Tokens leídos = entrada + escritura de caché + lectura de caché: todo lo que el modelo tuvo que leer, llamada por llamada.",
        "Escritos = tokens de salida (incluye el pensamiento). Read (relecturas) = lecturas con la herramienta Read (cuántas repitieron un archivo ya leído).",
        "Contexto 1ª llamada = lo que el agente carga antes de leer tu código (sistema, herramientas, CLAUDE.md, tu instrucción); "
        "contexto por llamada = promedio del hilo principal. Ese contexto se vuelve a leer en CADA llamada.",
        "El desglose usa la estructura de precios de lista (leer caché 0.1x, escribir 1.25x a 5 min o 2x a 1 h, salida 5x la entrada); "
        "el precio de entrada sale de tus datos. Si varía entre sesiones del mismo modelo, revisa --ratio-salida.",
    ]
    if any("suscripción" in f for f in fact):
        notas_fijas.append("Con suscripción (Pro/Max) no pagas este costo por sesión: es el equivalente a precio de API, útil para comparar.")
    for n in notas_fijas + notas:
        out.append(f"- {n}")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    for flujo in (sys.stdout, sys.stderr):  # consolas de Windows (cp1252) no imprimen acentos
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Cuánto costó y cuánto leyó cada sesión de agente (capturas stream-json de Claude Code).")
    ap.add_argument("rutas", nargs="+", help="archivos .jsonl o carpetas (se buscan .jsonl recursivamente)")
    ap.add_argument("--md", action="store_true", help="tablas en Markdown")
    ap.add_argument("--json", action="store_true", help="todo en JSON")
    ap.add_argument("--agrupar", choices=["prefijo", "carpeta", "ninguno"], default="prefijo",
                    help="prefijo (por defecto): vibe-01…vibe-10 -> 'vibe'; carpeta: por carpeta; ninguno")
    ap.add_argument("--detalle", action="store_true", help="lista los archivos releídos y el trabajo de los subagentes")
    ap.add_argument("--ratio-salida", type=float, default=RATIO_SALIDA, help="precio de salida / precio de entrada (por defecto 5)")
    ap.add_argument("--salida", metavar="ARCHIVO", help="escribe el informe en ARCHIVO (UTF-8) en vez de la pantalla")
    a = ap.parse_args(argv)
    if a.salida:  # mejor que "> archivo": PowerShell 5 redirige en UTF-16
        sys.stdout = open(a.salida, "w", encoding="utf-8", newline="\n")

    archivos: list[tuple[Path, Path]] = []
    for r in a.rutas:
        p = Path(r)
        if p.is_dir():
            archivos += [(f, p) for f in sorted(p.rglob("*.jsonl"))]
        elif p.exists():
            archivos.append((p, p.parent))
        else:
            print(f"no existe: {r}", file=sys.stderr)
            return 2
    sesiones, omitidos = [], []
    for f, raiz in archivos:
        try:
            nombre = f.resolve().relative_to(raiz.resolve()).with_suffix("").as_posix()
        except ValueError:
            nombre = f.stem
        try:
            s = analizar(f)
        except NoEsSesion as e:
            omitidos.append((nombre, str(e)))
            continue
        s["nombre"] = nombre
        s["grupo"] = clave_grupo(f, raiz, a.agrupar)
        sesiones.append(s)
    if not sesiones:
        print("No encontré sesiones stream-json de Claude Code.", file=sys.stderr)
        for nombre, motivo in omitidos:
            print(f"  {nombre}: {motivo}", file=sys.stderr)
        return 1

    descontar_reanudadas(sesiones)
    for s in sesiones:
        desglosar(s, a.ratio_salida)
        s["tokens"] = tokens(s)
    # Verificación: el precio de entrada implícito debería ser el mismo en todas las sesiones de un modelo.
    por_modelo: dict[str, list[float]] = {}
    for s in sesiones:
        for m, p in s["precio_entrada_implicito"].items():
            por_modelo.setdefault(m, []).append(p)
    alertas = []
    for m, ps in por_modelo.items():
        if len(ps) > 1 and (max(ps) - min(ps)) / min(ps) > TOLERANCIA_PRECIO:
            alertas.append(f"precio implícito de {m} varía {min(ps):.3f}–{max(ps):.3f} $/M: el desglose es aproximado")

    orden = sorted({s["grupo"] for s in sesiones})
    grupos = [resumir(g, [s for s in sesiones if s["grupo"] == g]) for g in orden]
    total = resumir("TOTAL", sesiones)

    if a.json:
        limpio = [{k2: v for k2, v in s.items() if not k2.startswith("_")} for s in sesiones]
        json.dump({"sesiones": limpio, "grupos": grupos, "total": total, "omitidos": omitidos, "alertas": alertas,
                   "supuestos": {"leer_cache": LEER_CACHE, "escribir_cache_5m": ESCRIBIR_CACHE_5M,
                                 "escribir_cache_1h": ESCRIBIR_CACHE_1H, "ratio_salida": a.ratio_salida}},
                  sys.stdout, ensure_ascii=False, indent=1)
        print()
        return 0
    texto = informe(sesiones, grupos, total, omitidos, a.md, a.detalle)
    if alertas:
        texto += "".join(f"- ALERTA: {x}\n" for x in alertas)
    sys.stdout.write(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
