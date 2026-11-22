# Vibe Coding Profesional · repo del curso

El código, las herramientas y los checkpoints del curso **«Vibe Coding Profesional: de la idea a producción dirigiendo agentes de IA»**.

Este repo no es para leerlo: es para **replicar** cada video. Todo lo que ves correr en el curso corrió de verdad sobre este código.

## Empieza aquí

```bash
git clone https://github.com/victor-velazquez-ai/vibe-coding-profesional
cd vibe-coding-profesional
python verificar.py
```

- ¿No tienes Python? Corre `uv run python verificar.py`.
- Con `python verificar.py --taller` también corren las pruebas del taller.

Todo debe salir en ✓ antes de la sección 1. Cada ✗ trae al lado el comando que lo arregla. El detalle está en el **Kit S0 («Antes de empezar»)**.

## La historia (ficticia, declarada)

**Criba** es una startup de Austin con un SaaS B2B de reclutamiento: muchas empresas usan la misma plataforma para filtrar candidatos. Su CTO, **Tomás Reyes**, nos contrata para construir **Criba Match**, que ordena candidatos por vacante con un *fit score* hecho con IA. Lo más importante del sistema es que **una empresa nunca vea los candidatos de otra**.

## Qué hay aquí

| Carpeta | Qué es | Secciones |
|---|---|---|
| `taller/` | API de reclutamiento multiempresa hecha «a la vibe» con un solo prompt: Meridian Logistics (`sofia`) y Northstar Health (`marcus`). Aquí practicas antes de que llegue el cliente; en la sección 2 la vuelves profesional y en la 3 le das acceso controlado a tu agente | S1–S3 |
| `criba/` | El proyecto del cliente, Criba Match, construido PR a PR desde el plan aprobado | S4–S9 |
| `herramientas/` | Scripts para **medir** en vez de creer: `check_leak.py` (¿marcus puede ver un candidato de Meridian?), `mutate_authz.py` (mutation test del filtro por empresa), `uso_sesiones.py` (cuánto costó y cuánto leyó tu sesión) y los materiales del piloto de S2 en `s2/` | S1 en adelante |
| `verificar.py` | Revisa que tu equipo esté listo para el curso | S0 |

## Checkpoints: nunca te quedas atrás

Cada checkpoint es un **tag de git** con el código tal como queda en ese punto del curso. Todos traen `herramientas/`. Si te atoras, saltas al checkpoint y sigues desde ahí.

| Tag | Qué trae | Sección |
|---|---|---|
| `taller-vibe` | El prototipo vibe: FastAPI, login simple, 2 empresas, candidatos, 5 pruebas | S1 |
| `s2-memoria` | + ruff, mypy, poe, Postgres en Docker, Alembic, logs JSON con `request_id`, pidfile y la memoria del proyecto (`AGENTS.md` + `CLAUDE.md`). Desde aquí trae un bug de zona horaria **sembrado a propósito** (se declara en el video) | S2 |
| `taller-pro` | + guardrails: permisos allow/ask/deny, hooks en Python y el rol `escritor-tests` | S2 |
| `taller-ci` | + CI en GitHub Actions: `poe check` contra Postgres en UTC y el chequeo «ningún commit mezcla `tests/` con `app/`» | S3 |
| `taller-acceso` | + roles de base de datos del agente (`agente_lectura`, `agente_metricas`), `poe psql-agente` y los permisos de `gh` | S3 |
| `s4-inicio` | Criba Match antes de empezar: contexto del cliente, decisiones del kickoff y la llamada con Tomás | S4 |
| `s4-diseno` | + spec, arquitectura, mapa de fallas y ADR-001 | S4 |
| `plan-v1`, `s5-plan` | El plan en PRs, antes y después de la revisión adversarial | S5 |
| `criba-base` | + réplica mínima de la plataforma de Criba, la Etapa 0 construida (PR-01 a PR-07: aislamiento por empresa, cola con proveedor MOCK, E2E de humo) y los roles: `escritor-tests`, `constructor`, `revisor-pr` | S6 |
| `s6-…`, `s7-qa`, `s8-staging` | Criba Match, del primer PR a producción | S6–S8 (llegan con su sección) |

```bash
git tag                                            # lista los checkpoints
git switch -c mi-intento && git add -A && git commit -m "mi intento"   # guarda tu trabajo
git checkout taller-pro                            # salta al checkpoint
git diff mi-intento taller-pro                     # tu versión contra la del curso
```

Los ejercicios trabajan en **copias fuera del clon** (`git worktree add ../../vcp-… <tag>`) y abren el agente dentro de `taller/` de la copia, para que no vea `herramientas/`.

## Qué es real y qué es ilustración

- **Real:** cada sesión de agente, cada piloto con sus números, la CI y los PRs de este repo. Lo acelerado muestra su tiempo real y lo sembrado a propósito se declara.
- **Ilustración:** la nube de AWS (rol IAM, despliegue). No usamos una cuenta real: se explica con animaciones rotuladas «ilustración» y guías con enlaces a la documentación oficial.

## Licencia y uso

Material del curso para alumnos. Los nombres de empresas y personas son ficticios.
