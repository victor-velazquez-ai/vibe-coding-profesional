# Correo de seguimiento a Tomás · llamada del 20-nov-2026

**Para:** Tomás Reyes (CTO, Criba)
**Asunto:** Criba Match · lo que entendí de la llamada de ayer, y lo que necesito de ti

---

Hola Tomás:

Gracias por el tiempo de ayer. Te dejo lo que entendí, un punto que choca con lo que habíamos decidido en el kickoff, y las preguntas que necesito que me respondas. El detalle completo, con las citas minutadas, está en `llamadas/2026-11-20-tomas-delta.md` del repo.

## Qué entendí

Criba Match ordena, para cada vacante, a los candidatos con un score y la explicación de por qué. El score **solo ordena**: el reclutador decide y el sistema nunca descarta a nadie. Entra el CV y la descripción de la vacante. Lo usan tus ~120 reclutadores, sobre todo desde el celular. El objetivo es el 15 de enero: que un reclutador abra una vacante de Northstar y vea los candidatos ordenados con su score y su porqué, aunque sea básico.

Y lo primero de todo, como dijiste: que ningún cliente vea candidatos de otro, nunca. Eso lo construyo en un solo punto del código y con tests que fallen si alguien se lo salta.

## Qué cambia respecto del kickoff

**Un punto importante.** Me pediste mandar el CV completo al modelo, con nombre y todo, al proveedor que funcione mejor. En el kickoff quedó decidido (D3, con Priya) que los CVs y los datos personales **no salen de la infraestructura de Criba y que ningún tercero los procesa**, como compromiso contractual con los clientes enterprise y control de SOC 2.

Las dos cosas no pueden ser a la vez. No voy a elegir arquitectura ni proveedor hasta que tú y Priya me digan cuál de las dos vale. Lo que necesito es una decisión consciente, no que yo la tome por omisión: si hay que quedarse dentro de la infraestructura de Criba, se puede, pero es probable que el score sea peor que con un proveedor externo, y eso es justo lo que me dijiste que ya habían probado y no funcionó.

También se agregan al alcance tres cosas que no estaban en el kickoff: la explicación obligatoria del score, el bilingüe español/inglés real (Meridian) y el techo de costo.

## Lo que necesito de ti

1. **D3 vs. proveedor externo.** ¿Autorizan tú y Priya mandar CVs completos a OpenAI/Anthropic, o nos quedamos dentro de Criba? Esto bloquea todo lo demás, así que es lo primero.
2. **Techo de costo mensual.** El número del CFO para Match. Sin él no puedo dimensionar.
3. **Formato del score.** Porcentaje 0-100, semáforo, o los dos — lo que salga de tu conversación con Dana.
4. **Hiring managers.** ¿Ven el score y la explicación, o no?
5. **Idioma de la explicación.** ¿En el del reclutador que la lee, o en el del CV? Ojo que dentro de Meridian hay reclutadores en los dos idiomas.
6. **Ley 144 de Nueva York.** Necesito la respuesta de tu abogado por escrito, no mi interpretación. Northstar opera en NY y es el cliente de la demo, así que preferiría tenerla antes del 15 de enero.
7. **Alcance de la demo.** «Sus vacantes, aunque sea básico»: ¿cuántas vacantes y cuántos candidatos de Northstar tienen que estar puntuados el 15 de enero? Y si hay datos reales con los que pueda probar la calidad del score antes.

Un aviso sobre el calendario: con arranque el 1 de diciembre y 20 horas por semana, hasta el 15 de enero son unas 120 horas con las fiestas en medio. Es viable para lo que describiste como mínimo, pero depende de que la pregunta 1 se resuelva antes del arranque. Si llega más tarde, lo hablamos y ajustamos alcance.

Dos cosas más que apunté por mi cuenta y que no me pediste, para que las tengas en el radar: que Match no repita el problema del candidato que pidió el borrado (los scores y las explicaciones son datos nuevos que hay que poder borrar también), y que la vista funcione de verdad en el celular, que es donde trabajan tus reclutadores.

Dejé los 11 issues redactados con su criterio de aceptación. Cuando tenga las respuestas 1 a 5 te mando el plan hasta el 15 de enero.

Un saludo,
Víctor
