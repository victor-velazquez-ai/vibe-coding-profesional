-- Los dos roles del staging local, con los permisos que tendrían en producción.
--
-- Lo corre el **dueño de la base** (`POSTGRES_USER` del contenedor) y lo monta
-- `docker-compose.staging.yml` en `/docker-entrypoint-initdb.d/`, así que se
-- ejecuta al inicializar el volumen. Es **idempotente** a propósito: se vuelve a
-- correr en cada despliegue de staging y Postgres no tiene
-- `CREATE ROLE IF NOT EXISTS`, así que un `CREATE ROLE` a secas revienta la
-- segunda vez y lo que se abandona entonces es el guion, no el despliegue.
--
-- Los roles son del **clúster**, no de la base, y por eso no los crea ninguna
-- migración: una migración que creara roles obligaría a correr Alembic con un
-- superusuario. La migración `0002_metricas_staging.py` solo da el permiso sobre
-- `metricas`, y condicionado a que el rol ya exista.
--
-- **Las contraseñas de aquí son valores de una máquina local, no secretos de
-- producción.** Este contenedor escucha en 127.0.0.1:5455 y sus datos son
-- sintéticos (D3 modificado, D15, F12). En producción las dos contraseñas salen
-- del gestor de secretos y no de un archivo del repo (F19).

-- 1 · los dos roles.
--
--    `criba_app` es **lo que usa la app**: lee y escribe datos y no puede hacer
--    DDL. Que no pueda es por omisión y no por confianza: no es dueña de ninguna
--    tabla y no tiene `CREATE` en ningún esquema, así que un `ALTER TABLE` suyo
--    falla con permiso denegado. Las migraciones las corre el dueño.
--
--    `agente_metricas` es el rol del agente que mira las métricas: aquí nace
--    **sin un solo permiso sobre datos**. El único que llega a tener lo da la
--    migración del esquema `metricas`, y es `SELECT` sobre sus dos vistas.
DO $roles$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'criba_app') THEN
        CREATE ROLE criba_app
            LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS
            PASSWORD 'criba_app_staging_local';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agente_metricas') THEN
        CREATE ROLE agente_metricas
            LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS
            PASSWORD 'agente_metricas_staging_local';
    END IF;
END
$roles$;

-- 2 · nadie crea objetos en `public` salvo su dueño.
--
--    En Postgres 15+ este permiso ya no viene puesto, así que esto es explícito
--    y no un arreglo: es el mecanismo por el que «`criba_app` sin DDL» se
--    cumple, y queda escrito donde se lee. El `USAGE` de `PUBLIC` que `initdb`
--    sí da no se toca: sin él, un `SELECT` a una tabla prohibida respondería
--    «no existe» en vez de «permiso denegado».
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- 3 · `criba_app`: las cuatro operaciones de datos, sobre lo que ya existe.
--
--    Al inicializar el volumen todavía no hay ninguna tabla —las crea la
--    migración, después—, así que estas tres líneas no conceden nada la primera
--    vez. Están igual porque el guion se vuelve a correr sobre una base ya
--    migrada, y ahí sí.
GRANT USAGE ON SCHEMA public TO criba_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO criba_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO criba_app;

-- 4 · y sobre lo que el dueño cree **después**.
--
--    Es lo que hace que el orden «levantar → migrar como dueño → arrancar la
--    app» funcione sin volver a tocar permisos: la tabla que añada la próxima
--    migración nace legible y escribible por `criba_app`. El dueño se lee de
--    `current_user` y no se escribe a mano: `ALTER DEFAULT PRIVILEGES` exige un
--    nombre de rol, no una expresión, así que va por `format`.
DO $privilegios$
BEGIN
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
        'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO criba_app',
        current_user
    );
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
        'GRANT USAGE, SELECT ON SEQUENCES TO criba_app',
        current_user
    );
END
$privilegios$;
