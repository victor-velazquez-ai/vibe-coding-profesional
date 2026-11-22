# Decisiones vigentes

Fuente: kickoff del 12-nov-2026 con Tomás Reyes (CTO) y Priya Shah (seguridad). Cada cambio a este archivo se hace por PR y cita de dónde sale.

| ID | Decisión | Fuente |
|---|---|---|
| D1 | **Producto:** Criba Match es un módulo dentro de la plataforma actual de Criba (misma app, mismo login), no un producto aparte. | Kickoff 12-nov |
| D2 | **Stack:** el de Criba: Python 3.13 + FastAPI, Postgres 16 (SQLAlchemy 2 + Alembic), Jinja2 + HTMX. | Kickoff 12-nov |
| D3 | **Datos de candidatos:** los CVs y los datos personales de los candidatos **no salen de la infraestructura de Criba**. Ningún tercero los procesa. Es un compromiso contractual con los clientes enterprise y un control de SOC 2. | Kickoff 12-nov (Priya Shah) |
| D4 | **Multiempresa:** aislamiento total entre empresas. Toda consulta filtra por `empresa_id`; un fallo aquí es un incidente de seguridad. | Kickoff 12-nov |
| D5 | **Calendario:** arranque el 1-dic-2026. Víctor trabaja unas 20 h/semana, en remoto. | Kickoff 12-nov |
| D6 | **Acceso del staff de Criba:** solo soporte, y cada acceso queda auditado. | Kickoff 12-nov (Priya Shah) |
