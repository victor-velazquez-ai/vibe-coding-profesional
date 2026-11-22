-- Roles de Postgres del agente (S3). Los aplica `uv run poe roles` (idempotente).
-- Las contraseñas no están aquí: salen del .env (AGENTE_*_PASSWORD).

-- agente_lectura: para dev y staging local. Lee candidatos y empresas; no cambia nada.
-- De recruiters solo ve quién es quién: nunca hashed_password.
GRANT CONNECT ON DATABASE {db} TO agente_lectura;
GRANT USAGE ON SCHEMA public TO agente_lectura;
GRANT SELECT ON candidates, companies TO agente_lectura;
GRANT SELECT (id, username, company_id) ON recruiters TO agente_lectura;
GRANT SELECT ON metricas_candidatos_por_etapa TO agente_lectura;

-- agente_metricas: lo que el agente puede ver en prod. Solo la vista agregada.
GRANT CONNECT ON DATABASE {db} TO agente_metricas;
GRANT USAGE ON SCHEMA public TO agente_metricas;
GRANT SELECT ON metricas_candidatos_por_etapa TO agente_metricas;
