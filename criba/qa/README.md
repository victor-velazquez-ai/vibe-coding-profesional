# QA agéntica de Criba Match (sección 7)

Los agentes de QA **exploran**; los tests **protegen**. Una pasada de QA termina en un triage (`TRIAGE.md`), y lo que se arregla entra primero como E2E en rojo en `tests/e2e/`.

| Rol | Se abre con | Prueba | Escribe en |
|---|---|---|---|
| QA de backend | `claude --agent qa-backend` | cada ruta con `curl`, dos empresas y cuatro roles, contra `SPEC.md` | solo `qa/` |
| QA de frontend | `claude --agent qa-frontend --mcp-config qa/mcp-playwright.json` | los flujos con navegador (Playwright MCP), escritorio y móvil a 360 px, con capturas y video | solo `qa/` |

Los dos son de caja negra: no leen `app/`, `tests/` ni `migrations/`. Los hooks les impiden escribir fuera de `qa/`, y el hook `Stop` no los atrapa con un rojo ajeno.

## Una pasada

```bash
docker compose up -d
uv run python qa/preparar.py          # resiembra criba_dev y deja los scores (MOCK) calculados
CRIBA_MATCH_ACTIVO=1 CRIBA_MATCH_EMPRESAS_ACTIVADAS=northstar-health \
  uv run python -m uvicorn app.main:app --port 8000
```

En otra terminal:

```bash
uv run python qa/rutas.py             # el mapa: el OpenAPI público está apagado
claude --agent qa-backend   "Haz la pasada de QA de backend de hoy contra http://127.0.0.1:8000."
claude --agent qa-frontend --mcp-config qa/mcp-playwright.json \
       "Haz la pasada de QA de frontend de hoy. La app corre en http://127.0.0.1:8000."
```

- **Antes de cada pasada, `qa/preparar.py`.** Las dos QA escriben datos (postulan, suben CVs, borran), y una QA que corre sobre la basura de otra reporta basura. Si corren a la vez, que cada una tenga su base y su servidor.
- **Scores reales** en vez del MOCK: `uv run python qa/preparar.py --proveedor claude_cli` (unos 0,01 USD por CV con el modelo detrás de `claude -p`).
- **En Windows:** usa `qa/mcp-playwright.windows.json` (`cmd /c npx`). Y la QA de backend antepone `MSYS_NO_PATHCONV=1` a cada `curl` en Git Bash (ver `TRIAGE.md`, BUG-5).
- **El video** queda en `qa/video/` y no se versiona; las capturas sí, en `qa/capturas/`.

## Amplitud: schemathesis

```bash
uv run python qa/rutas.py --openapi > qa/salida/openapi.json
uv run --no-project --with schemathesis --with "hypothesis<6.150" python -m schemathesis.cli run \
  qa/salida/openapi.json --url http://127.0.0.1:8000 -H "Cookie: criba_sesion=<la cookie de marcus>" --max-examples 30
```

El fuzzing da amplitud (140 casos en 5 s, y encontró un 500 con IDs mayores que `bigint`); el agente da criterio (encontró que borrar con un `vacante_id` ajeno borra y responde 404). Ninguno de los dos vio la redirección abierta: la encontró el triage.

> En Windows, Smart App Control puede bloquear binarios recién publicados (`os error 4551`): por eso `python -m schemathesis.cli` y no `schemathesis.exe`, y por eso `hypothesis<6.150`, la última versión sin extensión nativa.
