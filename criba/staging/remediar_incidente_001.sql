-- Remediación de datos del incidente 001 (22-nov-2026).
--
-- **No la corre este PR ni ningún agente.** Es para el rol **dueño** de la base
-- (el mismo que corre las migraciones, `poe staging-migrar`; `criba_app` no
-- tiene permiso de DDL ni falta que le hace aquí, pero esto es una operación de
-- datos con criterio humano, no un paso automático de despliegue) y queda
-- registrada en el postmortem con su fecha y quién la corrió
-- (`postmortems/PLANTILLA.md`, `RUNBOOK.md` §3: «si el arreglo es de
-- operación... va al postmortem con dueño y fecha»).
--
-- Qué arregla: los 7 pares candidato-vacante de `empresa_id` de Northstar a los
-- que el camino de excepción viejo (commit `8ee8160`, antes de este PR) les
-- escribió `match_scores.score = 0` con la razón exacta «No se pudo evaluar
-- automáticamente.». Ese cero ya no lo escribe ningún camino de `app/`
-- (`comportamiento: un fallo del proveedor nunca se convierte en un score`,
-- incidente-001), pero las 7 filas que el bug dejó **siguen en la base** y
-- siguen leyéndose como scores de verdad en la vista de la vacante y en
-- `metricas.scores_por_vacante`.
--
-- Qué NO arregla: si alguno de los 7 pares tenía un score bueno **antes** del
-- fallo, ese número ya no existe — `guardar_score` actualiza la fila del par
-- (CA9(a)) y lo pisó el camino de excepción. No hay a dónde volver: el camino
-- que sigue este script es el único que CA13 permite, «sin score» con motivo,
-- y de ahí a un score nuevo cuando el trabajo re-encolado corra.
--
-- Cómo usarlo, paso por paso y SIN automatizar el paso 3:
--
--   1. Reemplazar `:empresa_id` por el id de **una sola empresa** (aquí,
--      Northstar). El filtro por empresa no es opcional: es el requisito
--      número uno del cliente, y correrlo sin `WHERE empresa_id = ...` sobre
--      las dos CTE de abajo mezclaría la remediación de dos empresas en una
--      sola corrida.
--   2. Correr el bloque 1 (la consulta, de solo lectura) y **leer el número de
--      filas antes de seguir**. Si no son 7, parar: algo del alcance del
--      incidente cambió desde `docs/prs/incidente-001.md` y hace falta
--      entender antes de arreglar (`RUNBOOK.md` §2-3).
--   3. Con el número verificado, correr el bloque 2 dentro de una transacción
--      y hacer `COMMIT` a mano después de revisar el resultado. Si algo no
--      cuadra, `ROLLBACK` y no `COMMIT`: igual que con cualquier arreglo de
--      incidente, dos pasos (score y re-encolado) son más fáciles de revisar
--      separados que de deshacer juntos.
--
-- La razón se compara **exacta**, no con `ILIKE '%...%'`: una coincidencia
-- parcial se llevaría por delante cualquier fila de otro motivo que empiece o
-- contenga el mismo texto, y CA13 exige saber qué motivo es cada uno.

-- --- bloque 1 · solo lectura, para verificar el alcance antes de tocar nada --

SELECT
    s.id AS score_id,
    s.candidato_id,
    s.vacante_id,
    s.idioma,
    t.id AS trabajo_id,
    t.estado AS estado_trabajo
FROM match_scores AS s
LEFT JOIN match_trabajos AS t
    ON t.empresa_id = s.empresa_id
    AND t.candidato_id = s.candidato_id
    AND t.vacante_id = s.vacante_id
    AND t.idioma = s.idioma
    AND t.estado = 'error'
WHERE s.empresa_id = :empresa_id
    AND s.score = 0
    AND s.estado = 'listo'
    AND s.razones = '["No se pudo evaluar automáticamente."]'::jsonb
ORDER BY s.id;

-- --- bloque 2 · la remediación, dentro de una transacción -------------------

BEGIN;

-- 2a. Las filas sucias de `match_scores`: de «score falso» a «sin score», que
--     es el único estado que CA13 permite para un par que nadie puntuó. No se
--     borra la fila (CA16 y la auditoría siguen sabiendo que existió un
--     intento); se corrige su contenido.
WITH sucias AS (
    SELECT id, candidato_id, vacante_id, idioma
    FROM match_scores
    WHERE empresa_id = :empresa_id
        AND score = 0
        AND estado = 'listo'
        AND razones = '["No se pudo evaluar automáticamente."]'::jsonb
)
UPDATE match_scores AS s
SET
    score = NULL,
    razones = '[]'::jsonb,
    estado = 'sin_score',
    motivo_sin_score = 'Incidente 001: era un cero falso del camino de error, no un score. Reencolado.',
    actualizado_en = now()
FROM sucias
WHERE s.id = sucias.id
RETURNING s.id, s.candidato_id, s.vacante_id, s.idioma;

-- 2b. Los trabajos que cerraron en `error` para esos mismos pares: de vuelta a
--     `pendiente`, para que el ejecutor los tome en su próxima pasada. No se
--     inserta un trabajo nuevo: el que ya existe tiene la `clave_idempotencia`
--     de ese par y `uq_match_trabajos_idempotencia` (empresa_id,
--     clave_idempotencia) rechazaría una segunda fila para el mismo par con el
--     mismo CV. Reabrir la fila que ya existe es el único camino sin chocar
--     con esa restricción.
WITH afectados AS (
    SELECT candidato_id, vacante_id, idioma
    FROM match_scores
    WHERE empresa_id = :empresa_id
        AND score IS NULL
        AND estado = 'sin_score'
        AND motivo_sin_score = 'Incidente 001: era un cero falso del camino de error, no un score. Reencolado.'
)
UPDATE match_trabajos AS t
SET
    estado = 'pendiente',
    motivo = NULL,
    actualizado_en = now()
FROM afectados
WHERE t.empresa_id = :empresa_id
    AND t.candidato_id = afectados.candidato_id
    AND t.vacante_id = afectados.vacante_id
    AND t.idioma = afectados.idioma
    AND t.estado = 'error'
RETURNING t.id, t.candidato_id, t.vacante_id, t.idioma;

-- Revisar las dos salidas de `RETURNING` arriba: tienen que ser las mismas 7
-- filas (por candidato_id, vacante_id, idioma) que el bloque 1 mostró. Si
-- coinciden, COMMIT. Si no, ROLLBACK y entender por qué antes de reintentar.

-- COMMIT;
