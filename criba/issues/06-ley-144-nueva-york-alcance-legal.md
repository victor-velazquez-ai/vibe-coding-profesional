# 06 · Alcance de la ley 144 de Nueva York para Criba Match

**Decide:** el abogado externo de Criba, vía Tomás. **No lo interpretamos nosotros.**

## Contexto

> **[03:29]** «Otra cosa, y esto me lo pasó el abogado: Northstar tiene hospitales en Nueva York, y allá hay una ley sobre herramientas automatizadas para contratar. La ciento cuarenta y cuatro, creo. Que si usas un algoritmo para filtrar candidatos tienes que hacer una auditoría de sesgo y avisarles a los candidatos. No sé bien qué aplica a nosotros. Lo vemos después, ¿no?»

> **[03:52]** Víctor: «Lo pongo como riesgo y como pregunta para tu abogado.»

Tomás sostiene que Match solo ordena:

> **[03:57]** «Solo ordena. El reclutador decide. Nunca queremos que el sistema descarte a nadie solo.»

Pero describió el uso real así:

> **[00:55]** «Abren la vacante, ven quién va arriba y le escriben.»

Si el reclutador contacta a los de arriba y no baja, el orden influye en la práctica aunque el sistema no descarte a nadie. Eso puede ser relevante para el criterio de la ley. **No sabemos si lo es: esa es exactamente la pregunta.**

Northstar opera en Nueva York y es el cliente de la demo del 15-ene ([04:53]).

## Criterio de aceptación

- [ ] Tomás obtiene del abogado externo, por escrito, si Match entra en el alcance de esa ley.
- [ ] La respuesta cubre: ¿hace falta auditoría de sesgo?, ¿hace falta avisar al candidato?, ¿con qué antelación?, ¿quién es el responsable, Criba o la empresa cliente?
- [ ] Está respondido si la respuesta llega antes o después del 15-ene, y si la demo con Northstar puede hacerse sin ella.
- [ ] Según la respuesta, se abren los issues de implementación (aviso al candidato, registro para auditoría de sesgo).
- [ ] Mientras no haya respuesta: se guardan entradas, salida, versión de prompt y versión de modelo de cada score, para que una auditoría posterior sea posible (delta RI8). Esto no depende de la respuesta legal.

Fuente: `llamadas/2026-11-20-tomas.md` [03:29], [03:52], [03:57], [00:55], [04:53]. Delta: P6, P11, C4, R4.
