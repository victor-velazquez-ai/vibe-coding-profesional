# Postmortem 001 · Candidatos con score 0 en Northstar

> **Provocado a propósito para el curso (video 8.2) y declarado.** En el staging local, que hace de producción, sembramos dos cambios: el camino de error del ejecutor que guarda un 0 (commit «cola: si el proveedor falla, el candidato no se queda sin fila en la vista») y un tope de tokens en `staging/staging.env` («para cortar gasto»). El disparador, el diagnóstico, el arreglo y la verificación que siguen son reales.
>
> Sin culpables: la pregunta no es quién se equivocó, sino qué dejó pasar el error.

## Qué pasó
Siete pares candidato–vacante de Northstar mostraron **score 0** en la vista de vacante. No era un score: era un fallo del proveedor que nuestro código guardó como si lo fuera. Con el orden por fecha de hoy el 0 no ocultaba a nadie, pero con el orden por score de PR-20 los habría mandado al fondo de la lista: en la práctica, descartados (CA13, N1).

## Línea de tiempo (UTC, 22-nov-2026)
| Hora | Qué |
|---|---|
| 21-nov | Se agrega `CLAUDE_CODE_MAX_OUTPUT_TOKENS=800` al staging «para cortar gasto». Ya estaba desplegado el camino de error que guarda un 0, sin test que lo cubriera. |
| 17:14–17:24 | 19 trabajos de Northstar: 12 `listo`, **7 `error`** (`ErrorDelProveedor`, `decision=codigo_de_salida`, ~32 s cada uno). Los 7 dejan un 0. |
| (llamada) | Tomás: «a algunos candidatos les sale cero desde ayer». |
| contención | Match apagado con su interruptor (`CRIBA_MATCH_ACTIVO=0`, RUNBOOK §1) y reinicio: la vista vuelve a la lista de hoy, sin scores. |
| triage | Sesión con el rol de producción (logs, código, `agente_metricas`): 3 hipótesis, 2 confirmadas, 1 descartada. 809 s. |
| arreglo | Escritor de tests → constructor → revisor (rondas en `docs/prs/incidente-001.md`) → CI. |
| verificación | Ceros falsos borrados, trabajos reencolados, la misma vacante larga puntuada; E2E de humo contra el staging en verde. |

## Impacto
- 7 de 19 trabajos; vacante de UCI en Houston (5 de 6) y una vacante corta (2 de 4). Solo Northstar, la única empresa activada.
- Ningún dato cruzado entre empresas. Ningún dato personal en logs ni en métricas.

## Causa raíz
Dos causas, y hacen falta las dos:
1. **El código convertía un error en un dato válido.** El camino de excepción del ejecutor guardaba `score=0` con estado `listo` (viola CA13: «nunca un cero en lugar de un score»). Ningún test cubría el camino de error del ejecutor.
2. **Un tope que no era lo que parecía.** `CLAUDE_CODE_MAX_OUTPUT_TOKENS` no limita el gasto: limita la respuesta. Con una vacante larga, el modelo pasa el tope y el CLI termina con error (en nuestras mediciones, el CLI nunca entregó un JSON a medias: o error explícito o respuesta completa). El tope de gasto ya existía en el adaptador (`--max-budget-usd` por llamada).

## Qué funcionó
- El interruptor global (PR-05) contuvo en un reinicio, sin desplegar nada.
- El rol `agente_metricas` alcanzó para diagnosticar sin ver un solo dato de un candidato.
- Pedir 3 hipótesis con su refutación: la del «modelo da 0 de verdad» cayó con un 65 en la misma vacante.

## Qué no funcionó
- El guardarraíl `Stop` le exigió dejar la suite en verde a la sesión de triage, que tenía prohibido cambiar nada. El hook no tenía una rama para el rol de producción.
- Ninguna alerta: avisó la clienta, un día después.

## Acciones
| Acción | Dueño | Estado |
|---|---|---|
| Test: un fallo del proveedor nunca escribe un score ni pisa uno anterior (con el sobre real del CLI al pasar el tope) | escritor de tests | hecho, en el PR del arreglo |
| Arreglo del ejecutor: error → trabajo en `error` con motivo, sin score | constructor | hecho |
| Quitar el tope de tokens del staging y documentar por qué no es un tope de gasto | Víctor | hecho; un tope de tokens de verdad es F7 y su pregunta abierta |
| Remediación de datos: borrar los ceros falsos y reencolar | Víctor | hecho en el staging (`staging/remediar_incidente_001.sql`) |
| Quién reencola los trabajos en `error` (reintentos) | PR-14 | pregunta abierta 17 de `PLAN.md` §9 |
| Test de CI con el sobre real del CLI (issue #11) | escritor de tests | primer caso hecho; falta el resto del camino real |
| Rama del hook `Stop` para el rol de producción | Víctor | pendiente |
| Alerta: un pico de `error` en `metricas.trabajos_por_estado` | PR-15 | pendiente |
| Línea en el RUNBOOK: «un error nunca se guarda como dato» | Víctor | hecho |
