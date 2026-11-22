# Contexto: la plataforma de Criba (estado al 20-nov-2026)

Fuente: documento de kickoff que mandó Tomás Reyes (CTO) el 12-nov-2026.

## El negocio
- **Producto:** SaaS B2B de reclutamiento. Las empresas cliente publican vacantes, reciben candidatos y sus reclutadores los gestionan por etapas.
- **Clientes:** unas 40 empresas en EE.UU. y México. Las más grandes:
  - **Northstar Health**: hospitales en Texas y Nueva York. Es el cliente más grande y su renovación es en enero.
  - **Meridian Logistics**: opera en Dallas y Monterrey.
- **Uso:** unos 120 reclutadores activos, ~9.000 candidatos nuevos al mes y ~600 vacantes abiertas.

## La plataforma hoy
- **Stack:** Python 3.13 + FastAPI, Postgres 16 (SQLAlchemy 2 + Alembic), Jinja2 + HTMX. Se renderiza en el servidor.
- **Multiempresa:** todas las tablas de negocio llevan `empresa_id`, y la sesión de cada usuario está atada a una empresa.
- **Roles:**
  - reclutador: gestiona los candidatos de su empresa;
  - admin de empresa;
  - *hiring manager*: solo lectura, a nivel de vacante;
  - staff de Criba: soporte, con acceso auditado.
- **Entidades:** empresa, usuario, vacante, candidato (con su CV en texto y en PDF), etapa y notas de entrevista.
- **Cumplimiento:** auditoría **SOC 2 Type II** programada para marzo de 2027.

## El equipo
- Tomás Reyes (CTO), tres desarrolladores de backend, Dana (customer success) y Priya Shah (seguridad).
- Abogado externo para temas laborales y de privacidad.
- **Nosotros:** Víctor, ingeniero remoto contratado para construir **Criba Match** (unas 20 horas por semana).

## Criba Match (el encargo)
Un módulo nuevo: para cada vacante, ordenar a los candidatos con un **fit score** que explique por qué encaja cada uno.
