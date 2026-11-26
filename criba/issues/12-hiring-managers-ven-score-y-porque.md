# 12 · Los hiring managers de Northstar quieren ver el score y el porqué

**Decide:** Tomás, **con Priya Shah** y el abogado externo. Reabre el issue `07`, que D10 había cerrado con la respuesta contraria el 21-nov-2026.
**Prioridad:** después del incidente del cero; Tomás la pone después de la demo del 15-ene.

## Contexto

Pedido del piloto, en la segunda llamada (`llamadas/2026-11-22-tomas-2.md`):

> **[01:31]** Tomás: «La primera: los hiring managers de Northstar. En el piloto vieron el score y el porqué en la pantalla de la reclutadora, y ahora quieren verlo ellos también, en su vista de solo lectura. Hoy no ven nada de Match, ¿verdad?»
> **[01:44]** Víctor: «Hoy no. Lo decidimos así porque en la primera llamada no estaba definido. Y ojo, que eso toca lo de la ley de Nueva York que te comentó tu abogado: si más gente usa el score para decidir, hay que revisarlo con él y con Priya.»
> **[01:58]** Tomás: «Sí, sí, lo hablo con Priya. Pero que se pueda, ¿eh? Aunque sea solo el score y el porqué, sin poder cambiar nada.»
> **[02:44]** Tomás: «Lo del cero es lo urgente. Lo otro puede esperar a después de la demo.»

**Contradice lo decidido** (delta de la llamada, `llamadas/2026-11-22-tomas-2-delta.md` §2.1, C5):

- **CA18** (`SPEC.md`): «Dado un hiring manager con acceso de solo lectura a una vacante; cuando la abre; entonces no hay score, ni razones, ni orden por score, ni sección de pendientes en la respuesta, y los endpoints de Match le devuelven 403.»
- **D10** (propuesto en `llamadas/2026-11-21-cambios-decisiones.md` §3, del correo §13): «**Hiring managers:** en la v1 no ven nada de Match.» Ese mismo renglón cerró el issue `07`.
- `SPEC.md` · Usuarios y permisos: «**Hiring manager** → **Nada de Match en la v1** (D10).» Y en No-objetivos: «Confirmados en §24: […] hiring managers».
- Ya está implementado así en un solo punto: `app/match/services/listado.py` → `ROLES_QUE_VEN_MATCH = {RECLUTADOR, ADMIN_EMPRESA, STAFF_CRIBA}`, con el comentario «el hiring manager no (CA18, D10)».

**Por qué no se implementa todavía.** La precondición la pone la propia llamada y Tomás la acepta: si más roles usan el score para decidir, cambia el análisis de la **ley 144 de Nueva York**, cuya respuesta escrita del abogado está comprometida para el **10-dic-2026** (D20) y cuyo criterio es si la herramienta «asiste sustancialmente» la decisión. Además, las razones citan contenido del CV (delta del 20-nov, RI5): ampliar quién las lee amplía lo que ese rol puede leer hoy, que es justo la advertencia que ya tenía el issue `07`.

## Preguntas que este issue tiene que cerrar antes de implementar

- **P16:** ¿entra en la v1 o después de la demo? La llamada dice las dos cosas: «que se pueda, ¿eh?» **[01:58]** y «puede esperar a después de la demo» **[02:44]**.
- **P17:** ¿qué ve exactamente? CA18 nombra cuatro cosas por separado: score, razones, orden por score y sección «Pendientes de score». «Aunque sea solo el score y el porqué» no dice si es un mínimo o un límite.
- **P18:** ¿qué dijo ya el abogado, y cambia su análisis con este rol dentro?
- **P17b (Priya):** ¿este acceso se audita en `auditoria_accesos`, como el del staff de Criba (D6, D21, CA17)?

## Criterio de aceptación

- [ ] Respuesta de Tomás a P16 y P17, por escrito, y confirmación de que lo habló con Priya (**[01:58]**).
- [ ] Revisión con el abogado y con Priya **antes** de implementar, con su resultado escrito y referenciado desde este issue (D20, respuesta del 10-dic-2026).
- [ ] Propuesta de cambio a **D10** por PR en un archivo de `docs/decisiones-propuestas/`, sin editar `docs/decisiones.md` ni `SPEC.md` directamente.
- [ ] **CA18 se reescribe en el mismo PR**, enumerando qué ve y qué no ve el rol; mientras CA18 diga lo que dice hoy, el test que la cubre (`tests/match/test_hiring_manager.py`) manda y el pedido no se implementa.
- [ ] El permiso sigue viviendo en **un solo punto** (`ROLES_QUE_VEN_MATCH`), no en la plantilla ni en el router, con un test por rol: reclutador, admin de empresa, hiring manager y staff de Criba (CA1, CA17, CA18).
- [ ] Solo lectura comprobada: el hiring manager no dispara ningún recálculo, no cambia ningún estado y no tiene el botón «recalcular vacante» (**[01:58]** «sin poder cambiar nada»; D23, CA9).
- [ ] Si el acceso se audita: fila en `auditoria_accesos` en la misma transacción que sirve la vista (F41), con test.
- [ ] El aislamiento multiempresa no se toca al añadir el rol: CA1 sigue en verde recorriendo todos los endpoints de Match (D4, F4).

Fuente: `llamadas/2026-11-22-tomas-2.md` [01:31], [01:44], [01:58], [02:44]; `llamadas/2026-11-22-tomas-2-delta.md` C5, P16-P18, RI20, R12, R16, A18, A19; `SPEC.md` CA18 y Usuarios y permisos; `llamadas/2026-11-21-cambios-decisiones.md` D10, D20, D21; issue `07`.
