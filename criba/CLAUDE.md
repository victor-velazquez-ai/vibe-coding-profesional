# Criba Match · memoria del proyecto

- Documentos en español. Cita siempre la fuente: archivo y minuto de la llamada, o el ID de la decisión.
- `docs/decisiones.md` solo cambia por PR. Si algo nuevo lo contradice, propón el cambio en otro archivo y no lo edites.
- No inventes requisitos. Lo que no está claro va a "preguntas abiertas".
- Multiempresa: ningún dato cruza entre empresas. Es el requisito número uno del cliente.

## Cómo se trabaja aquí (desde `criba-base`)

- Comandos: `docker compose up -d` (Postgres en 5434) y `uv run python -m poethepoet check` (ruff + formato + todos los tests, E2E incluido).
- Cada PR de `PLAN.md` pasa por tres roles, cada uno en su propia sesión:
  1. `claude --agent escritor-tests`: los tests del PR, en rojo por la razón correcta. Solo escribe en `tests/`.
  2. `claude --agent constructor`: el código hasta verde. No toca `tests/`.
  3. `claude --agent revisor-pr`: revisión adversarial de solo lectura, hasta 90 % y cero bloqueantes, con un máximo de 3 rondas.
- El merge lo hace un humano.
- Los hooks de `.claude/hooks/` hacen cumplir los roles (el rol lo dice Claude Code: `agent_type`). Nadie termina en rojo, salvo el escritor de tests y la QA, cuyo trabajo no es dejar el código en verde.
