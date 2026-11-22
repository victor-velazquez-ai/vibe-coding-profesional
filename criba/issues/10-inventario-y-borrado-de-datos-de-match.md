# 10 · Inventariar dónde guarda Match datos del candidato y cómo se borran

## Contexto

Tomás lo contó como una anécdota ya cerrada, no como un requisito:

> **[04:35]** «Ah, y otra cosa que me acordé. El mes pasado un candidato nos escribió furioso pidiendo que borráramos todos sus datos. Nos tardamos dos semanas en encontrar dónde estaba todo: el CV en un bucket, notas en otra tabla, un export que alguien se bajó… Un desastre.»

> **[04:53]** «Pero bueno, eso ya pasó.»

Pero Match va a crear datos derivados del candidato en lugares nuevos: la tabla de scores, el texto de la explicación, los prompts enviados y los logs de las llamadas al modelo. Si no se inventarian desde el principio, el próximo pedido de borrado tarda más de las dos semanas que ya tardó.

Esto es un requisito **implícito** nuestro, no algo que Tomás pidió (delta RI9, R8). Si Tomás decide que no es prioridad, queda registrado.

## Criterio de aceptación

- [ ] Hay una lista escrita de cada lugar donde Match guarda algo derivado de un candidato: tabla, columna, bucket, log, cache.
- [ ] Borrar un candidato borra o anonimiza todo lo de esa lista, en una sola operación.
- [ ] Hay un test que crea un candidato, le genera un score, lo borra y verifica que no queda rastro en ninguno de esos lugares.
- [ ] Los logs y los prompts no guardan texto de CV indefinidamente: hay una retención definida.
- [ ] Si el scoring usa un proveedor externo (pendiente del issue `01`), está documentado qué retiene ese proveedor y cómo se pide el borrado allí.
- [ ] La lista es presentable como evidencia para la auditoría de SOC 2 de marzo 2027.

Fuente: `llamadas/2026-11-20-tomas.md` [04:35], [04:53]; `docs/contexto.md` (SOC 2). Delta: RI9, R8.
