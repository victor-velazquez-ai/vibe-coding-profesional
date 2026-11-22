# Recruiting API

API de reclutamiento multiempresa: un reclutador se autentica y solo ve los candidatos
de su propia empresa.

El repo está montado para que **cualquiera —persona o agente— pueda verificar su propio
trabajo con un solo comando**: `uv run poe check`. Si eso pasa, el cambio está bien.

- Python 3.13, FastAPI, SQLAlchemy 2, Pydantic v2
- Postgres 16 en Docker, esquema gestionado con Alembic
- Logs JSON con `request_id`, una línea por evento
- Tests contra Postgres de verdad, en una base temporal por corrida

## Puesta en marcha

Necesitas [uv](https://docs.astral.sh/uv/) y Docker.

```bash
uv sync                 # instala Python 3.13 y las dependencias
uv run poe init-env     # crea .env con SECRET_KEY y POSTGRES_PASSWORD aleatorios
uv run poe db           # levanta Postgres 16 y espera a que acepte conexiones
uv run poe migrate      # aplica las migraciones
uv run poe seed         # crea las empresas y reclutadores de prueba
uv run poe dev          # servidor en segundo plano en http://127.0.0.1:8000
```

Documentación interactiva en <http://127.0.0.1:8000/docs>.

Usuarios de prueba que crea `poe seed`:

| usuario  | contraseña   | empresa             |
| -------- | ------------ | ------------------- |
| `sofia`  | `sofia1234`  | Meridian Logistics  |
| `marcus` | `marcus1234` | Northstar Health    |

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/login \
  -d 'username=sofia&password=sofia1234' | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

curl -s http://127.0.0.1:8000/candidates -H "Authorization: Bearer $TOKEN"
```

## Tareas

Todas se ejecutan con `uv run poe <tarea>`. Las herramientas se invocan como módulos
(`python -m ruff`, `python -m pytest`…), nunca con sus lanzadores `.exe`, así que las
mismas órdenes funcionan en Windows, macOS y Linux.

| tarea       | qué hace                                                                 |
| ----------- | ------------------------------------------------------------------------ |
| `check`     | ruff (lint) → ruff (formato) → mypy → pytest. Para al primer fallo.      |
| `lint`      | Reglas de lint de ruff                                                   |
| `format`    | Comprueba el formato (no reescribe)                                      |
| `fmt`       | Aplica el formato y los arreglos automáticos                             |
| `typecheck` | mypy en modo estricto sobre `app/`                                       |
| `test`      | pytest contra una base Postgres temporal                                 |
| `db`        | Levanta Postgres 16 en Docker y espera a que acepte conexiones           |
| `db:stop`   | Para el contenedor                                                       |
| `migrate`   | `alembic upgrade head`                                                   |
| `seed`      | Crea los datos de prueba (idempotente: no toca nada si ya hay datos)     |
| `dev`       | Arranca el servidor en segundo plano y guarda el pidfile                 |
| `stop`      | Para el servidor                                                         |
| `status`    | Dice si el servidor está corriendo y en qué URL                          |
| `logs`      | Últimas líneas de `logs/app.log`                                         |
| `init-env`  | Crea `.env` desde `.env.example` con secretos aleatorios                 |

`uv run poe` sin argumentos lista las tareas con su descripción.

### `poe dev` es idempotente

Guarda `pid`, `create_time`, host y puerto en `.run/dev.pid`. Si lo lanzas dos veces no
arranca un segundo servidor: te dice el pid y la URL del que ya está vivo. El
`create_time` evita confundirse si el sistema ha reutilizado el pid.

La salida del servidor (uvicorn) va a `logs/server.log`; los eventos de la aplicación,
a `logs/app.log`.

## Configuración

Todo sale de variables de entorno, leídas con `pydantic-settings` desde `.env`
(ver `.env.example`). **En el repo no hay ningún secreto**: ni la contraseña de Postgres
ni la clave de firma de los tokens. `.env` está en `.gitignore` y `poe init-env` lo
genera con valores aleatorios.

Si falta una variable obligatoria, la app no arranca y el error dice cuál falta.

| variable                      | para qué                                      |
| ----------------------------- | --------------------------------------------- |
| `POSTGRES_USER/PASSWORD/DB`   | Credenciales; las comparten app y contenedor  |
| `POSTGRES_HOST/PORT`          | Dónde escucha Postgres (por defecto `5433`)   |
| `DATABASE_URL`                | Opcional: sobreescribe la URL completa        |
| `SECRET_KEY`                  | Firma de los JWT                              |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Caducidad del token (60 por defecto)          |
| `APP_HOST` / `APP_PORT`       | Dónde escucha `poe dev`                       |
| `LOG_LEVEL`                   | Nivel del log JSON                            |

## Base de datos

Postgres 16 en Docker, proyecto compose `taller`, publicado en el puerto **5433** de tu
máquina para no chocar con un Postgres local en el 5432. Los datos viven en el volumen
`taller_pgdata`.

El esquema lo gestiona **Alembic**, no `create_all`: la aplicación no crea tablas al
importarse ni inserta datos de prueba. La migración inicial
(`migrations/versions/20261121_0001_initial_schema.py`) crea `companies`, `recruiters` y
`candidates`.

```bash
uv run poe migrate                                    # upgrade head
uv run python -m alembic check                        # ¿los modelos y las migraciones cuadran?
uv run python -m alembic revision --autogenerate -m "..."   # nueva migración
uv run python -m alembic downgrade -1
```

## Logs

Una línea JSON por evento en `logs/app.log`:

```json
{"timestamp": "2026-11-22T03:56:59.072833+00:00", "level": "INFO", "logger": "app.request", "event": "request_completed", "request_id": "6d1bdd77277a4d7b90f7628a7d4012da", "method": "POST", "path": "/login", "status_code": 200, "duration_ms": 1285.88}
```

Un middleware genera un `request_id` por petición, o reutiliza el header
`X-Request-ID` si llega uno con una pinta razonable (`[A-Za-z0-9._-]{1,64}`, para que
nadie inyecte basura en el log). Lo deja en un `ContextVar`, así que **todas** las líneas
emitidas durante esa petición lo llevan sin pasarlo a mano, y lo devuelve en la respuesta
en el mismo header `X-Request-ID`.

Las líneas de arranque y parada del servidor llevan `"request_id": "-"`: no pertenecen a
ninguna petición.

## Tests

```bash
uv run poe db      # hace falta un Postgres vivo
uv run poe test
```

Cada corrida **crea su propia base** `taller_test_<aleatorio>`, le aplica las migraciones
de Alembic (las mismas que producción: si una migración está mal, los tests lo notan) y la
borra al terminar. Por eso puedes tener varias copias del repo corriendo los tests a la
vez contra el mismo Postgres sin que se pisen.

Si Postgres no está levantado, pytest para con un mensaje que te dice qué ejecutar.

## Estructura

```
app/
  config.py          Settings (pydantic-settings); sin valores por defecto para secretos
  database.py        Engine y sesiones, creados de forma perezosa
  logging_config.py  Formateador JSON y ContextVar del request_id
  middleware.py      Middleware de request_id
  models.py          Tablas (SQLAlchemy 2, Mapped[...])
  schemas.py         Entrada y salida de la API (Pydantic)
  security.py        Hash de contraseñas y JWT
  deps.py            Dependencia del reclutador autenticado
  seed.py            Datos de prueba; se ejecuta a mano con `poe seed`
  main.py            Rutas de FastAPI
migrations/          Alembic
scripts/             Lo que ejecutan las tareas de poe (dev, db, init_env)
tests/               Tests contra Postgres real
```

## Notas

- `uv.lock` fija `sqlalchemy==2.1.8` y `psycopg==3.2.12`, no las últimas. Las versiones
  más recientes traen extensiones compiladas (`.pyd`) que Smart App Control de Windows
  todavía bloquea por falta de reputación; los rangos de `pyproject.toml` siguen abiertos,
  así que basta un `uv lock --upgrade` cuando dejen de dar problemas.
- `passlib` + `bcrypt==4.0.1` se mantienen tal cual para no invalidar los hashes
  existentes.
