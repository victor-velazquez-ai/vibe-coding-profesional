# Criba Match

Repo del proyecto **Criba Match** para **Criba**, una startup de Austin, Texas, con un SaaS B2B de reclutamiento usado por unas 40 empresas.

> **Ficticio:** Criba, Tomás Reyes y sus clientes son ficticios. Se escribieron para el curso *Vibe Coding Profesional*.

## Qué hay aquí
- `docs/contexto.md`: cómo es hoy la plataforma de Criba.
- `docs/decisiones.md`: decisiones vigentes. Cada cambio se hace por PR y cita su fuente.
- `llamadas/`: transcripts de llamadas con el cliente y lo que sale de ellas.
- `issues/`: borradores de issues.
- `PLAN.md`: el plan de implementación, paso por paso (PR-01 → PR-26).
- `docs/prs/`: el cuerpo de cada PR entregado.
- `app/plataforma/`: **réplica mínima de la plataforma de Criba** (ver abajo).
- `app/match/`: el módulo **Criba Match**, en construcción.

## La réplica de la plataforma

La plataforma real de Criba es privada del cliente y no está en este repo. Para
poder construir y probar Match hay aquí una **réplica mínima**, fiel al stack y a
las entidades de `docs/contexto.md`: FastAPI, Postgres 16 con SQLAlchemy 2 y
Alembic, Jinja2 + HTMX y render en el servidor.

No es la plataforma de Criba: es lo justo para que Match tenga dónde engancharse
—login con sesión atada a una empresa, vacantes, candidatos, postulaciones,
subida de CV y el procedimiento de borrado—. **Todos sus datos son sintéticos.**

## Cómo se corre

```bash
docker compose up -d                              # Postgres 16 en el puerto 5434 (contenedor criba-db)
uv sync                                           # dependencias
uv run python -m app.plataforma.semilla           # migraciones + datos de desarrollo
uv run python -m uvicorn app.main:app --reload    # la app en http://127.0.0.1:8000
```

Usuarios de desarrollo (la contraseña de cada uno es **su nombre de usuario + `1234`**):

| Usuario | Rol | Empresa |
|---|---|---|
| `marcus` | reclutador | Northstar Health |
| `hm.northstar` | hiring manager | Northstar Health |
| `admin.northstar` | admin de empresa | Northstar Health |
| `sofia` | reclutadora | Meridian Logistics |
| `soporte` | staff de Criba | elige la empresa al entrar; el acceso queda auditado |

## Tests y comprobaciones

```bash
uv run python -m playwright install chromium      # una vez: el navegador del E2E de humo
uv run python -m pytest                           # la suite
uv run python -m poethepoet check                 # ruff check + ruff format --check + pytest
```

`uv sync` instala la librería de Playwright, **no los navegadores**: sin esa
primera orden el E2E de `tests/e2e/` falla al lanzar Chromium. El E2E levanta su
propio servidor y corre **al final de la suite**, por la razón escrita en
`tests/conftest.py`.

Las dos órdenes van por `python -m` a propósito: en la máquina de desarrollo
(Windows) la política de control de aplicaciones bloquea a veces los `.exe` de
los entornos virtuales.

Los tests corren contra `criba_test`, una base **separada** de la de desarrollo
en el mismo contenedor. Cada test corre dentro de una transacción que se revierte
al terminar.
