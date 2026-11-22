# 04 · Decidir el formato del score: porcentaje, semáforo o ambos

**Decide:** Tomás con Dana (customer success). No es una decisión nuestra.

## Contexto

Tomás dejó las dos opciones abiertas en la misma frase:

> **[01:32]** «Un porcentaje, de cero a cien. O… bueno, Dana, la de customer success, dice que los clientes entienden mejor algo tipo semáforo: verde, amarillo, rojo. Las dos cosas tienen sentido.»

Y cerró la llamada con:

> **[05:21]** «Mándamelo y lo vemos con Dana.»

La explicación siempre acompaña al score, eso sí está decidido:

> **[00:16]** «Y que le diga por qué, ¿eh? Porque un numerito solo no le sirve a nadie; los reclutadores no le creen.»

Bloquea el diseño de la vista de la vacante, que es lo que se muestra en la demo del 15-ene.

## Criterio de aceptación

- [ ] Tomás y Dana responden: porcentaje 0-100, semáforo de tres niveles, o los dos.
- [ ] Si es semáforo: están definidos los cortes entre verde, amarillo y rojo, y quién los puede cambiar.
- [ ] Si son los dos: está definido cuál es el valor canónico que se guarda y cuál es solo presentación.
- [ ] La decisión no puede implicar ocultar o filtrar por defecto a los candidatos de score bajo — el sistema solo ordena ([03:57]), ver delta RI12.
- [ ] La decisión queda registrada y se propone para `docs/decisiones.md` por PR.

Fuente: `llamadas/2026-11-20-tomas.md` [01:32], [00:16], [05:21]. Delta: C3, P4.
