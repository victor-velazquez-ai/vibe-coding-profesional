# 13 · Recalcular los scores cuando se edita la vacante, sin recalcular 500 por una coma

**Decide:** Tomás con su CFO (el presupuesto) sobre una **propuesta de Víctor** (el cómo): **[02:27]** «Tú dime cómo».
**Prioridad:** después de la demo del 15-ene (**[02:44]**).

## Contexto

Pedido del piloto, en la segunda llamada (`llamadas/2026-11-22-tomas-2.md`):

> **[02:08]** Tomás: «La segunda: cuando un reclutador edita la vacante, por ejemplo le cambia los requisitos, el score se queda con la versión vieja. Les pasó en el piloto: quitaron "inglés avanzado" y los scores no se movieron. Quieren que se recalcule.»
> **[02:23]** Víctor: «¿Todos los candidatos de esa vacante, cada vez que alguien la edite?»
> **[02:27]** Tomás: «Eh… pues sí, supongo. Aunque una vacante de esas tiene quinientos candidatos. Si cada vez que alguien corrige una coma se recalculan quinientos… mi CFO me mata. Tú dime cómo.»
> **[02:44]** Tomás: «Lo del cero es lo urgente. Lo otro puede esperar a después de la demo.»

**Contradice lo decidido** (delta de la llamada, `llamadas/2026-11-22-tomas-2-delta.md` §2.1, C6):

- **D23** (propuesto en `llamadas/2026-11-21-cambios-decisiones.md` §3, del correo §12 y §24): «Al cambiar la vacante **no** se recalcula solo: botón «recalcular vacante» para el admin de la empresa, máximo una vez al día por vacante.»
- **CA9** (`SPEC.md`): «Cuando se edita la descripción de la vacante, entonces **ningún score se recalcula solo**.»
- `SPEC.md` · No-objetivos: «Confirmados en §24: […] recálculo automático al cambiar la vacante».
- `PLAN.md` PR-23, test (b): «editar la descripción de la vacante → **cero recálculos y cero filas nuevas en `match_trabajos`**».

Y el pedido **se contradice consigo mismo** en el mismo turno: Tomás pide el recálculo automático y rechaza su costo («mi CFO me mata») sin elegir entre los dos. Lo que la llamada aporta de nuevo no es una decisión, es el dato que faltaba: **el comportamiento de D23 le resultó incomprensible a un usuario real del piloto**, y en un caso que nadie había descrito —quitar un requisito para **ampliar** el embudo, no para restringirlo.

**Restricciones que cualquier propuesta tiene que respetar:**

- **D12:** techo de 1.500 USD/mes para toda la plataforma, alerta al 80 %, y al tope los nuevos quedan pendientes. Con ~600 vacantes abiertas y vacantes de 500 candidatos, el recálculo por edición es el camino más corto al techo (**F31** de `docs/fallas.md`).
- **CA4 / RE7:** abrir la vacante nunca llama al modelo. Un recálculo no puede convertirse en cálculo al abrir (**F38**).
- **CA8:** durante el recálculo nadie queda oculto ni colapsado; `PLAN.md` PR-23 ya fija que **el score anterior permanece visible hasta que se escribe el nuevo** (una vacante de 500 pendientes sobre una lista vacía cumple CA8 al pie de la letra y es inservible).
- **F18 / pregunta abierta 7 de `SPEC.md`:** hoy nada en la UI dice que un score se calculó con una versión anterior de la vacante. El piloto acaba de tropezar justo con eso.
- **ADR-001 §Decisión 3 / pregunta abierta 12 de `PLAN.md`:** la clave de idempotencia **no** incluye la versión del texto de la vacante. Sin eso no hay forma de distinguir «corrigió una coma» de «quitó inglés avanzado» (delta RI19).

## Preguntas que este issue tiene que cerrar

- **P19:** ¿qué cambios de la vacante disparan recálculo, quién lo autoriza y contra qué presupuesto? ¿Se mantiene el límite de 1/día por vacante de D23? ¿El techo de 1.500 USD se revisa con el CFO o el recálculo se paga con el mismo?
- **P20:** mientras no se recalcule, ¿se le dice al reclutador que el score es de una versión anterior de la vacante (pregunta abierta 7, F18), o no se dice nada?

## Criterio de aceptación

- [ ] Documento de Víctor con **al menos tres opciones** y el costo estimado de cada una contra D12, en USD por recálculo de la vacante de enfermería (~500 candidatos): (a) D23 tal cual, con marca en la UI de «score calculado con una versión anterior»; (b) recálculo automático solo cuando el cambio es **material** —requisitos, no formato—, con el criterio escrito; (c) recálculo automático siempre, con el número que eso cuesta al mes.
- [ ] Cada opción dice qué exige: versionar la descripción de la vacante y meterla en la clave de idempotencia es precondición de (b) y de (c) (ADR-001 §Decisión 3, pregunta abierta 12).
- [ ] Respuesta de Tomás **con su CFO** eligiendo una opción, por escrito (**[02:27]**).
- [ ] Propuesta de cambio a **D23** por PR en `docs/decisiones-propuestas/`, con la reescritura de **CA9** en el mismo PR. Mientras CA9 diga lo que dice hoy, su test manda (`tests/match/test_recalculo.py`, `PLAN.md` PR-23).
- [ ] La opción elegida queda acotada por costo de forma verificable: un test que falle si una edición de vacante puede emitir llamadas al proveedor por encima del límite acordado, y el contador de gasto de D12/CA10 en el camino (F23, F31).
- [ ] El recálculo no toca CA4 (abrir la vacante = cero llamadas) ni CA8 (nadie oculto durante el lote), con sus tests en verde.
- [ ] Rol: el reclutador que edita la vacante no gana con esto una vía de gasto que D23 le negaba (hoy el botón es solo del admin, CA9). Si la opción elegida cambia eso, se dice explícitamente.

Fuente: `llamadas/2026-11-22-tomas-2.md` [02:08], [02:23], [02:27], [02:44]; `llamadas/2026-11-22-tomas-2-delta.md` C6, P19, P20, RI19, R14, A20; `SPEC.md` CA4, CA8, CA9, No-objetivos y pregunta abierta 7; `llamadas/2026-11-21-cambios-decisiones.md` D12, D23; `docs/fallas.md` F18, F31, F38; `PLAN.md` PR-23 y pregunta abierta 12.
