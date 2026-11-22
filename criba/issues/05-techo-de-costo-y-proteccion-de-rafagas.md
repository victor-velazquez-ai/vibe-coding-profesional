# 05 · Techo de costo mensual y protección contra ráfagas

## Contexto

> **[04:18]** Víctor: «¿Costos? Cada score es una llamada a un modelo.»
> **[04:21]** Tomás: «Uf, sí. Mi CFO ya me preguntó. No tengo un número. Que no se dispare, eso sí. Si alguien sube mil CVs de golpe, no quiero una factura de miles de dólares.»
> **[04:32]** Víctor: «Lo dejo como pregunta: un techo mensual.» → **[04:35]** Tomás: «Va.»

Volumen de referencia: **~9.000 candidatos nuevos al mes** y **~600 vacantes abiertas** ([04:06], coincide con `docs/contexto.md`).

Hacen falta dos cosas distintas: un número del CFO (lo da Tomás) y los controles técnicos para no pasarlo (los hace Víctor).

## Criterio de aceptación

- [ ] Tomás entrega un techo de costo mensual en dólares para Match.
- [ ] Está documentada una estimación de costo por score y de costo mensual con el volumen real, para contrastarla con ese techo.
- [ ] Un mismo par (CV, vacante) no se puntúa dos veces: hay cache y re-puntuar es una acción explícita (delta RI3).
- [ ] Hay un límite de ráfaga por empresa: subir 1.000 CVs de golpe encola el trabajo y no genera 1.000 llamadas inmediatas (delta RI4).
- [ ] Hay un corte y una alerta al acercarse al techo mensual, y está definido qué pasa al llegar: se encola, se degrada o se detiene.
- [ ] Está respondido si Match se enciende para las ~40 empresas o solo para Northstar hasta pasada la demo (delta P12) — cambia el costo por completo.

Fuente: `llamadas/2026-11-20-tomas.md` [04:18]–[04:35], [04:06]. Delta: RE9, P5, P12, R5.
