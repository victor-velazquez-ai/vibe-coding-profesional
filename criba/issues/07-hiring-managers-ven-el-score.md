# 07 · ¿Los hiring managers ven el score?

**Decide:** Tomás. Él mismo pidió anotarlo.

## Contexto

> **[01:18]** Víctor: «¿Y los hiring managers de tus clientes también entran?»
> **[01:18]** Tomás: «Algunos sí, con acceso de solo lectura. Eh… ¿deberían ver el score? No sé. Ahorita no lo hemos decidido. Ponlo en tu lista.»

Según `docs/contexto.md`, el rol *hiring manager* es de solo lectura y a nivel de vacante.

Afecta al modelo de permisos y a la vista de la vacante, que es lo de la demo del 15-ene. Si la respuesta tarda, lo prudente es que en la demo el score **no** se muestre a hiring managers y se habilite después.

## Criterio de aceptación

- [ ] Tomás responde si el rol *hiring manager* ve el score, la explicación, las dos cosas o ninguna.
- [ ] Si ve la explicación: está considerado que la explicación cita contenido del CV, y que eso amplía lo que ese rol puede leer hoy.
- [ ] El permiso queda implementado como una regla explícita por rol, no como un detalle de la plantilla.
- [ ] Hay un test por rol: reclutador, admin de empresa, hiring manager y staff de Criba.
- [ ] Para el staff de Criba, el acceso al score y a la explicación queda auditado, igual que exige D6 (delta RI11).
- [ ] La decisión se propone para `docs/decisiones.md` por PR.

Fuente: `llamadas/2026-11-20-tomas.md` [01:18]; `docs/contexto.md` (roles); `docs/decisiones.md` D6. Delta: P2, RI11.
