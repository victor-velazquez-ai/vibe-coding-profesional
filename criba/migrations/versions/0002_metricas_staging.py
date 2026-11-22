"""El esquema `metricas`: dos vistas agregadas y ningún dato del candidato.

Lo que el agente de métricas puede mirar en producción, y nada más. Las dos
vistas agregan lo que ya está en `match_scores` y `match_trabajos`:

- `metricas.scores_por_vacante`: por empresa, vacante y día, cuántos pares tienen
  score —**el `0` incluido**, que es un score de verdad—, cuántos de ellos son
  cero, cuántos quedaron «sin score» (CA13) y el promedio de los que lo tienen;
- `metricas.trabajos_por_estado`: por empresa, día de creación, estado y motivo,
  cuántas filas de la cola hay.

**Ninguna columna es un dato del candidato ni un identificador suyo, y ninguna de
las dos vistas lee uno** (CA2, CA16, D15, F12). Es la lista de lo que
`docs/arquitectura.md` §2 permite que salga de Criba —«`request_id`,
`empresa_id`, decisión tomada, latencia, versión de modelo y prompt»— leída para
una vista: dimensiones de empresa y de tiempo, conteos y un promedio. Ni
`candidato_id`, ni nombre, ni correo, ni teléfono, ni links, ni texto de CV, ni
las razones (dato derivado del candidato, F25), ni el hash del CV (identificador
suyo, CA16).

**El día se calcula en UTC y no en la zona del servidor** (`AT TIME ZONE 'UTC'`):
un agregado por día cuyo corte depende del `TimeZone` de la sesión que consulta
da dos respuestas distintas a la misma pregunta.

**El `GRANT` va condicionado a que el rol exista.** El rol `agente_metricas` es
del **clúster**, no de la base, y lo crea `staging/roles.sql` —una migración que
creara roles obligaría a correr Alembic con un superusuario—. Sin la condición,
`alembic upgrade` se rompería en toda base donde ese guion no corrió: la de test
de este repo incluida, o sea la suite entera.

**No crea ninguna tabla**, y por eso no tiene entrada en el inventario de borrado
de CA16 (F13, R6·M7): una vista no guarda filas, así que no hay nada que borrar en
ella. Cuando se borra un candidato desaparece de los dos agregados por sí solo,
porque desaparecen las filas que los agregados cuentan.

**Esto no es un PR de `PLAN.md`**: es la tarea de operación del staging local con
la configuración de producción (`RUNBOOK.md`).

Revision ID: 0002_metricas
Revises: 0001_match
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_metricas"
down_revision: str | None = "0001_match"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ESQUEMA = "metricas"
ROL = "agente_metricas"

# `IF NOT EXISTS` y `OR REPLACE` a propósito: `tests/conftest.py` recrea `public`
# en cada sesión de tests, y eso se lleva por cascada las vistas —que dependen de
# las tablas de `public`— pero **no** el esquema. Sin esto, el segundo
# `alembic upgrade` sobre la misma base fallaría con «el esquema ya existe».
CREAR_ESQUEMA = f"CREATE SCHEMA IF NOT EXISTS {ESQUEMA}"

# `count(s.score)` cuenta las filas con score **incluido el 0**; `n_score_cero`
# es su desglose y `score_promedio` promedia exactamente las mismas filas que
# `n_con_score` cuenta. Las tres juntas hacen que un «sin score» no se pueda leer
# como un cero (CA13) ni al revés.
VISTA_DE_SCORES = f"""
CREATE OR REPLACE VIEW {ESQUEMA}.scores_por_vacante AS
SELECT
    s.empresa_id,
    s.vacante_id,
    CAST(s.actualizado_en AT TIME ZONE 'UTC' AS date)       AS dia,
    count(s.score)                                          AS n_con_score,
    count(*) FILTER (WHERE s.score = 0)                     AS n_score_cero,
    count(*) FILTER (WHERE s.score IS NULL)                  AS n_sin_score,
    CAST(avg(s.score) AS double precision)                  AS score_promedio
FROM public.match_scores AS s
GROUP BY s.empresa_id, s.vacante_id, CAST(s.actualizado_en AT TIME ZONE 'UTC' AS date)
"""

# Agrupa por `creado_en` y no por `actualizado_en`: el día de un trabajo es el día
# en que **entró** a la cola. Con `actualizado_en`, el trabajo que nació ayer y se
# marcó hoy se contaría hoy, y la pregunta «cuántos entraron el día del incidente»
# dejaría de tener respuesta.
VISTA_DE_TRABAJOS = f"""
CREATE OR REPLACE VIEW {ESQUEMA}.trabajos_por_estado AS
SELECT
    t.empresa_id,
    CAST(t.creado_en AT TIME ZONE 'UTC' AS date) AS dia,
    t.estado,
    t.motivo,
    count(*)                                     AS n
FROM public.match_trabajos AS t
GROUP BY t.empresa_id, CAST(t.creado_en AT TIME ZONE 'UTC' AS date), t.estado, t.motivo
"""

# Postgres no tiene `GRANT … IF ROLE EXISTS`, así que la condición se pregunta al
# catálogo del clúster. `USAGE` sobre el esquema y `SELECT` sobre las dos vistas:
# nada más, y sobre nada de `public`.
PERMISOS_DEL_AGENTE = f"""
DO $permisos$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROL}') THEN
        GRANT USAGE ON SCHEMA {ESQUEMA} TO {ROL};
        GRANT SELECT ON {ESQUEMA}.scores_por_vacante TO {ROL};
        GRANT SELECT ON {ESQUEMA}.trabajos_por_estado TO {ROL};
    END IF;
END
$permisos$
"""


def upgrade() -> None:
    # F16 en mecanismo, como la 0001: crear una vista toma `ACCESS SHARE` sobre
    # las tablas que lee, y con una transacción larga encima falla en 3 s en vez
    # de encolarse.
    op.execute("SET lock_timeout = '3s'")
    op.execute(CREAR_ESQUEMA)
    op.execute(VISTA_DE_SCORES)
    op.execute(VISTA_DE_TRABAJOS)
    op.execute(PERMISOS_DEL_AGENTE)


def downgrade() -> None:
    # Las vistas **antes** del esquema, y el esquema sin `CASCADE`: así un objeto
    # que alguien añadiera a mano a `metricas` no se borra en silencio. Y antes
    # que el `downgrade` de la 0001, que es quien quita las tablas que estas dos
    # vistas leen: con las vistas en pie, ese `drop_table` fallaría.
    op.execute(f"DROP VIEW IF EXISTS {ESQUEMA}.trabajos_por_estado")
    op.execute(f"DROP VIEW IF EXISTS {ESQUEMA}.scores_por_vacante")
    op.execute(f"DROP SCHEMA IF EXISTS {ESQUEMA}")
