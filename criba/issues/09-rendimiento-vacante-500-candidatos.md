# 09 · Una vacante con 500+ candidatos tiene que abrir rápido

## Contexto

> **[00:16]** «Una vacante de enfermería de Northstar recibió quinientos y pico la semana pasada.»

> **[04:06]** «Unos nueve mil candidatos nuevos al mes en toda la plataforma. Vacantes abiertas, unas seiscientas. Y la de enfermería que te dije, quinientos. Que abra rápido aunque tenga quinientos.»

Y el uso real es desde el celular:

> **[00:55]** «la mayoría ni se sienta en la compu: revisan todo desde el celular, entre entrevista y entrevista, en el coche, donde sea. Abren la vacante, ven quién va arriba y le escriben.»

La plataforma se renderiza en el servidor con Jinja2 + HTMX (D2), así que el coste de la página es del servidor, y la red del reclutador suele ser mala.

Nadie definió un número de "rápido". Pendiente de acordar.

## Criterio de aceptación

- [ ] Existe un escenario de prueba con una vacante de 500+ candidatos puntuados.
- [ ] Esa vacante abre sin consultas N+1 y sin ninguna llamada al modelo en el camino (ver issue `03`).
- [ ] El orden por score se resuelve en Postgres, con índice, y filtrando por `empresa_id` (ver issue `02`).
- [ ] La primera pantalla carga lo de arriba — que es lo que mira el reclutador, [00:55] — y el resto pagina o carga por demanda con HTMX.
- [ ] Hay un objetivo de tiempo acordado con Tomás y medido, no solo "rápido".
- [ ] Verificado en una pantalla de celular y con red lenta (delta RI1, R9).

Fuente: `llamadas/2026-11-20-tomas.md` [00:16], [04:06], [00:55]; `docs/decisiones.md` D2. Delta: RE8, RI1, RI2, R9.
