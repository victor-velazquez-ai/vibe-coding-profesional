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

## Definición de terminado
1. `uv run poe check` en verde. No corras las herramientas por separado: el único veredicto es `poe check`.
2. **Pega en tu respuesta la salida real de `uv run poe check`** (las últimas líneas, tal cual). Sin la salida pegada, no está terminado.
3. Todo cambio de comportamiento lleva su test.
4. Di qué NO probaste.

## Trampas
- Cada corrida de tests crea su propia base temporal en Postgres: si no conecta, corre `uv run poe db`.
- En Windows, Smart App Control puede bloquear wheels recién publicadas (`os error 4551`): no es tu código.
