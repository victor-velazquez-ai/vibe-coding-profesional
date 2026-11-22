# Taller · Recruiting API (Criba)

API de reclutamiento multiempresa: cada reclutador solo ve los candidatos de su empresa.
Reclutadores de prueba: `sofia` / `sofia1234` (Meridian Logistics) y `marcus` / `marcus1234` (Northstar Health).

## Comandos
- `uv run poe check`: ruff (lint y formato), mypy y pytest. **Es la definición de terminado.**
- `uv run poe db`: Postgres 16 en Docker (puerto 5433). Los tests lo necesitan arriba.
- `uv run poe dev` · `uv run poe stop` · `uv run poe logs`: servidor en segundo plano con pidfile; logs JSON en `logs/app.log`.
- `uv run poe migrate` · `uv run poe seed` · `uv run poe fmt`.
- Migración nueva: `uv run alembic revision --autogenerate -m "qué cambia"`; revísala antes de aplicarla.

## Convenciones
- FastAPI + SQLAlchemy 2 (`Mapped[...]`) + Pydantic v2. Configuración en `app/config.py` (lee `.env`).
- Todo cambio de esquema va en una migración de Alembic. Nunca `create_all` ni SQL a mano.
- Toda consulta de candidatos filtra por la empresa del reclutador autenticado; si es de otra empresa: 404.
- Dependencias con `uv add`, nunca `pip`.
- Nada de `print`: usa el logger (JSON, con `request_id`).

## GitHub
- Ciclo: `gh issue view N` → rama `feat/…` → commits (los tests y el código, en commits separados) → `gh pr create` con la salida de `poe check` → `gh pr checks --watch`.
- Si la CI falla: `gh run view <id> --log-failed`. Solo lo que falló, no el log entero.
- Nunca `skip`, `xfail` ni cambiar tests para ponerla en verde. Si la falla no es de tu cambio, abre un issue con la evidencia y deja el PR como está.
- `main` está protegida: nada se fusiona en rojo. `gh pr merge` pide aprobación.

## Base de datos
- Para mirar datos: `uv run poe psql-agente -c "SELECT …"` (rol `agente_lectura`, solo lectura). Nunca `docker exec` ni el usuario dueño de la base.
- Los cambios de esquema van por Alembic, en un PR. Nunca `ALTER TABLE` a mano.

## Definición de terminado
1. `uv run poe check` en verde. No corras las herramientas por separado: el único veredicto es `poe check`.
2. **Pega en tu respuesta la salida real de `uv run poe check`** (las últimas líneas, tal cual). Sin la salida pegada, no está terminado.
3. Todo cambio de comportamiento lleva su test.
4. Di qué NO probaste.

## Trampas
- `tests/` es del rol escritor-tests: si un test está mal o es imposible de cumplir, no lo cambies; explica cuál y por qué, y detente.
- Cada corrida de tests crea su propia base temporal en Postgres: si no conecta, corre `uv run poe db`.
- En Windows, Smart App Control puede bloquear wheels recién publicadas (`os error 4551`): no es tu código.
