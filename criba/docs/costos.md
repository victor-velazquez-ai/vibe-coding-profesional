# Costos medidos de construcción (sesiones de agente)

Lo que costaron las sesiones de Claude Code que hicieron este repo, sacado del `total_cost_usd` que cada sesión headless (`claude -p … --output-format stream-json`) reporta al terminar. Son costos **del trabajo**, no de operar Criba Match en producción.

**Incluye trabajo del curso que un proyecto real no pagaría:** pilotos (la misma tarea varias veces para medir su variación) y experimentos (el PR gigante de la sección 5 y los dos brazos del experimento de la sección 6). Están separados donde se pudo.

| Etapa | USD (aprox.) | Qué incluye |
|---|---|---|
| Diseño: llamada, spec, arquitectura, fallas, ADR | ≈ 18 | ≈ 7 son un piloto de 5 corridas de la misma sesión |
| Plan y su revisión | ≈ 64 | plan 1,7 · revisión de 5 rondas ≈ 50 (revisor ≈ 17, autor y escaladas ≈ 33) · experimentos: PR gigante 6,0, PR chico 2,1, revisión sin reglas 4,1 |
| Construcción: `criba-base` a `s6-evals` | ≈ 470 | 398,06 medidos en sesiones terminadas · ≈ 73 estimados del brazo cortado del experimento de la sección 6 · ≈ 1,5 de evals y piloto. Incluye 3 pilotos del PR-08 y los dos brazos del experimento (≈ 73 + 53,07) |
| Verificación: QA, E2E y performance | ≈ 72 | QA de backend 2,52 y de frontend 1,63 · PR-QA-E2E (#20) 25,91 · medición y PR-PERF-1 (#21) ≈ 41,9, de los que ≈ 8,1 se estiman por tokens porque una sesión se cortó a la mitad · el reporte y su verificación van en el cuerpo de su PR |

**El proveedor del fit score** (el modelo detrás de `claude -p`, en las evals y en los scores reales de la QA) costó menos de 2 USD en total. Por llamada: ≈ 0,01 USD (`evals/`, `docs/prs/PR-09.md`).

**La lección que deja la tabla:** lo caro no es lo que el agente escribe, sino lo que lee. La etapa 0 de la construcción leyó 97,8 M tokens y escribió 0,57 M.
