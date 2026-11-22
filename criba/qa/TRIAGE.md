# Triage de la QA · 22-nov-2026

Los agentes de QA prueban contra `SPEC.md`, no contra `PLAN.md`: no saben qué está construido. El triage lo hace un humano, y cada hallazgo termina en uno de cuatro sitios: **se arregla ahora** (con un test primero), **ya está en el plan**, **issue** o **no es un bug**.

Informes: `reportes/2026-11-22-backend.md` (qa-backend, caja negra con `curl`) y `reportes/2026-11-22-frontend.md` (qa-frontend, Playwright MCP, con capturas en `capturas/`). Además, una corrida de schemathesis contra el mismo entorno.

| Hallazgo | Severidad (QA) | Decisión | Dónde |
|---|---|---|---|
| Frontend BUG-3 · la vacante desborda a 360 px (CA19): `scrollWidth` 979 contra 360 | crítica | **Se arregla ahora** | E2E primero (PR de E2E) |
| Backend BUG-2 · borrar con un `vacante_id` ajeno **borra igual y responde 404** | alta | **Se arregla ahora** | E2E primero (PR de E2E) |
| Frontend BUG-1 y Backend BUG-3 · no hay orden por score ni «Pendientes» (CA8) | crítica | Ya está en el plan | PR-20 |
| Frontend BUG-2 y Backend BUG-4 · no se ven las tres razones | crítica | Ya está en el plan | PR-20 (la vista real) |
| Backend BUG-1 · borrar un candidato **con score** da 500 | crítica | Ya está en el plan, y confirma la regla 1.7: ningún dato real se puntúa antes de que el borrado de Match esté en verde | PR-18 |
| Backend BUG-6 · subir CV con un `vacante_id` de otra vacante devuelve el fragmento equivocado | baja | Issue | — |
| schemathesis · un ID mayor que `bigint` (9223372036854775808) da **500** en 4 rutas | baja | Issue | — |
| Backend BUG-5 · «el login ignora `destino`» | media | **No es un bug** | ver abajo |

## Lo que encontró el triage y no la QA

**BUG-5 no existe.** Al reproducirlo fuera de la sesión del agente, con `MSYS_NO_PATHCONV=1`, el login sí respeta `destino=/vacantes/3`. El agente corrió `curl` en Git Bash, que convierte los argumentos que parecen rutas POSIX (`/vacantes/3` → una ruta de Windows). Lo reprodujo dos veces, como pide su rol, pero las dos en la misma terminal.

**La misma causa escondía un bug real: redirección abierta en el login.** Con `destino=//example.com`, el login responde `303` con `Location: //example.com`, y el navegador sale de Criba a otro dominio. Es el enlace de phishing perfecto: una URL de Criba que, después de un login legítimo, termina en otra parte. El agente nunca probó `//`, y aunque lo hubiera probado, su terminal lo habría convertido en `/example.com`. **Se arregla ahora**, con su E2E.

**Lección para el rol de QA:** en Windows, `curl` desde Git Bash con `MSYS_NO_PATHCONV=1`, o desde PowerShell. Y un hallazgo que depende de la terminal se reproduce con otra.
