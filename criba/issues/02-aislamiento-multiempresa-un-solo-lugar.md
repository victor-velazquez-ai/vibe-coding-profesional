# 02 · Aislamiento multiempresa en un solo lugar del código, con tests

## Contexto

Es el requisito número uno del cliente. Tomás, sobre lo que más le preocupa:

> **[03:03]** «Lo más importante de todo, y te lo digo en serio: que ningún cliente vea candidatos de otro. Nunca. Si un reclutador de Meridian llega a ver un candidato de Northstar, Northstar nos cancela el contrato ese mismo día, y es nuestro cliente más grande. Tenemos la auditoría de SOC 2 en marzo y esto es lo primero que van a revisar.»

Acordado en la llamada cómo se hace:

> **[03:25]** Víctor: «Eso va con test y en un solo lugar del código.» → **[03:29]** Tomás: «Eso.»

Refuerza D4 (`docs/decisiones.md`): toda consulta filtra por `empresa_id`; un fallo aquí es un incidente de seguridad.

Match agrega superficies nuevas donde se puede filtrar algo: la tabla de scores, el texto del prompt, la explicación generada y los logs de la llamada al modelo.

## Criterio de aceptación

- [ ] Todo acceso a datos de Match pasa por un único punto que exige `empresa_id`; no hay forma de construir una consulta de Match sin él.
- [ ] Hay un test que falla si se agrega una consulta que no filtra por empresa.
- [ ] Hay un test de integración con dos empresas cargadas (Northstar y Meridian ficticias) que verifica que la vacante, el score y la explicación de una no son visibles ni enumerables desde la sesión de la otra.
- [ ] El prompt, el payload al modelo y los logs se verifican: no mezclan datos de dos empresas en una misma llamada.
- [ ] Lo anterior está escrito de forma que se pueda mostrar como evidencia en la auditoría de SOC 2 de marzo 2027.

Fuente: `llamadas/2026-11-20-tomas.md` [03:03], [03:25], [03:29]; `docs/decisiones.md` D4. Delta: N9, RE5, R2.
