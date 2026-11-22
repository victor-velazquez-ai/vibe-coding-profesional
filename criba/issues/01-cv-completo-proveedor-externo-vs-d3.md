# 01 · Resolver: mandar el CV completo a un proveedor externo contradice D3

**Bloqueante.** Hasta que esto se resuelva no se elige arquitectura de scoring ni proveedor.

## Contexto

En la llamada del 20-nov, Tomás pidió:

> **[02:14]** «mándale el CV completo al modelo. Todo, con nombre, con todo. Probamos con un proveedor recortando cosas y el score salía malísimo. Que lo lea todo, y que lo haga el proveedor que funcione mejor: OpenAI, Anthropic, el que sea. Eso decídelo tú.»

Eso contradice directamente una decisión vigente:

> **D3** (`docs/decisiones.md`, kickoff 12-nov, Priya Shah): «los CVs y los datos personales de los candidatos **no salen de la infraestructura de Criba**. Ningún tercero los procesa. Es un compromiso contractual con los clientes enterprise y un control de SOC 2.»

Tomás no mencionó D3 en la llamada, así que no sabemos si la está cambiando a propósito. La auditoría SOC 2 Type II es en marzo de 2027 (`docs/contexto.md`).

La decisión es de Tomás **con Priya Shah**, no nuestra. Nosotros documentamos las opciones.

## Criterio de aceptación

- [ ] Están documentadas, con su costo en calidad de score, en tiempo de desarrollo y en riesgo, al menos estas tres opciones:
  1. proveedor externo con CV completo (requiere cambiar D3);
  2. modelo que corre dentro de la infraestructura de Criba;
  3. proveedor externo con CV desidentificado — Tomás ya dijo [02:14] que así «el score salía malísimo», hay que registrar ese antecedente.
- [ ] Tomás y Priya Shah responden por escrito cuál se toma.
- [ ] Si se toma la opción 1: hay confirmación de que los contratos enterprise y el alcance de SOC 2 lo permiten, y D3 se modifica **por PR** citando esta llamada.
- [ ] Si no se toma la opción 1: queda escrito que el score puede ser peor y que Tomás lo acepta.
- [ ] Ninguna línea de código manda datos de candidato a un tercero antes de esta respuesta.

Fuente: `llamadas/2026-11-20-tomas.md` [02:14]; `docs/decisiones.md` D3. Delta: C1, P1, R3.
