# Cambios propuestos a `docs/decisiones.md` · 22-nov-2026 · proveedor y vacante

> **Qué es este archivo y por qué existe.** El código y los tests de PR-09 citan
> «N4, decisión de Víctor del 22-nov-2026» como la fuente de tres cosas —el
> proveedor, el modelo y el adaptador— y esa fuente **no tenía archivo en el
> repositorio**: solo vivía en `docs/prs/PR-09.md`, que es el cuerpo del PR.
> Es el hallazgo **M2** de la ronda de revisión de PR-09, y CLAUDE.md es
> explícito: «cita siempre la fuente: archivo y minuto de la llamada, o el ID de
> la decisión». La segunda decisión —la descripción de la vacante— llegó en la
> misma ronda y se registra aquí por la misma razón.
>
> **No se edita `docs/decisiones.md`.** Aquí se **propone** y se aplica por PR,
> igual que `llamadas/2026-11-21-cambios-decisiones.md` hace con D3 y D7-D23.
> Quién decide ya decidió —Víctor, en los dos casos, dentro de lo que N4 acotada
> le deja—; lo que falta es el PR que mueva el texto a la tabla y, en el primer
> caso, la **verificación escrita de Priya** antes de producción.

**Fuente de las dos:** Víctor, 22-nov-2026, en la sesión de PR-09. La primera
responde a la pregunta que N4 acotada le deja abierta («la elección del proveedor
la decide Víctor… solo proveedores que firmen retención cero y no entrenamiento»,
`llamadas/2026-11-21-cambios-decisiones.md` §2, §1b, §17). La segunda responde al
hallazgo 1 del cuerpo de PR-09, que es donde se descubrió el hueco.

---

## 1. El proveedor, el modelo y el adaptador (N4 ejercida)

**Decisión literal:**

> el modelo es **Claude**. En **este** repo del curso no hay clave de API, así que
> el cliente real es un adaptador que llama al CLI `claude -p` por **subproceso**,
> sin herramientas y sin sesión, con la versión fijada
> `claude-haiku-4-5-20251001`. En el proyecto real del cliente sería la API con su
> clave en una variable de entorno, nunca en el repo ni en la CI (F19). El **MOCK
> sigue siendo el modo por omisión y el único que la CI usa.**

**ID propuesto: D24.** Texto propuesto para la tabla:

> **Proveedor de modelo:** Claude, con la versión de modelo fijada en la
> invocación y **nunca el alias**. En el repositorio del curso el cliente real es
> un adaptador al CLI `claude -p` por subproceso, sin herramientas y sin sesión;
> en el proyecto del cliente sería la API con la clave en variable de entorno. El
> MOCK es el modo por omisión y el único que corre en CI. **No se habilita en
> producción** hasta que Priya Shah verifique por escrito retención cero y no
> entrenamiento (D3 modificado, condición b).

**Qué queda pendiente, y no lo cierra esta propuesta:**

- **la verificación escrita de Priya** (D3 modificado condición b, `SPEC.md`
  §Privacidad, `PLAN.md` §9 pregunta 2 y precondición 4 de la operación de carga,
  R2·I7). Sin ella el modo se queda en el MOCK. Es dependencia bloqueante con
  fecha —antes del 12-dic-2026— y no una aserción roja en `main`;
- **si el modelo pequeño basta.** Es un supuesto nuestro por costo (D12); lo mide
  CA14 sobre el conjunto dorado (PR-17) y lo decide Víctor. Cambiarlo es una
  línea y la versión que se registra sale del sobre del CLI, así que la fila de
  auditoría de D15/CA15 dice la verdad con cualquiera de los dos;
- **la pregunta abierta 11 de `PLAN.md` §9** («¿el MOCK es interruptor de
  producción para cortar gasto?») **sigue abierta**, y esta ronda le añade un
  dato: el modo se lee **una vez por proceso** (`lru_cache`), así que volver al
  MOCK es un **reinicio** y no un `export`. Si la respuesta a la pregunta 11 es
  «sí, es el interruptor de gasto», hace falta algo más que esta variable.

**Lo que esta decisión arrastra en `docs/`, y que esta propuesta no edita:**
`docs/fallas.md` dice en su encabezado que «el proveedor no está elegido» y que
**F23 y F31 hay que recalcularlas al elegirlo**. Elegido ya está; el recálculo es
de quien lleve el PR que aplique esta propuesta, no de PR-09.

---

## 2. La descripción de la vacante cruza la frontera, fuera del payload

**Decisión literal:**

> la descripción de la vacante es **dato de la empresa, no del candidato**. Viaja
> al proveedor junto al payload pseudonimizado del CV, como un **campo aparte del
> pedido**, y NUNCA dentro de `PayloadPseudonimizado` (CA2 sigue siendo sobre el
> candidato).

**No contradice ninguna decisión vigente y no necesita ID nuevo:** es `SPEC.md`
alcance 1 («por par candidato-vacante») y alcance 2 con **D13** («entradas: solo
el texto del CV y la descripción de la vacante») **cumplidos**, no cambiados. Lo
que había era un hueco de implementación que el propio PR-09 encontró y declaró:
`Proveedor.puntuar(payload, idioma)` no recibía la vacante, así que el adaptador
puntuaba un CV y no el par. Hasta PR-09 no se veía, porque el MOCK devuelve un
número fijo.

**Lo que la decisión fija, y por qué cada mitad importa:**

| Mitad | Qué fija | Qué protege |
|---|---|---|
| «viaja al proveedor» | el pedido son **tres** datos: payload, idioma y descripción | `SPEC.md` alcance 1 y 2, D13. Sin ella, **la medición de CA14** (PR-17) mide otra cosa, y «vacante sin descripción → sin score» (alcance 6, PR-11) no tiene sentido |
| «como campo aparte» | **nunca** dentro de `PayloadPseudonimizado` | **CA2.** Ese tipo es lo que la frontera exige y la fábrica única construye: si además llevara dato de la empresa, «pseudonimizado» dejaría de significar los seis datos del **candidato** y `exigir_payload` no tendría qué verificar |

**Aplicada en:** `app/match/configuracion.py` (el `Protocol`),
`app/match/repositories/match_repo.py::descripcion_de_vacante` (la lectura, con
el `empresa_id` del contexto: es el **primer dato de la empresa** que sale de
Criba, así que D4 y CA1 aplican igual), `app/match/services/scoring.py` y
`app/match/proveedor/cliente.py` (va por la **entrada estándar**, nunca en
`argv`). Tests: `tests/match/test_descripcion_de_vacante.py`.

**Lectura nuestra, declarada:** «junto al payload» se leyó como «por la entrada
estándar, en un bloque `<vacante>`», y no como «en el prompt del sistema». La
razón es la misma que para el CV y no cambia porque el dato sea de la empresa:
`argv` lo lee cualquier proceso de la máquina con `ps`, sale en los volcados y es
lo que `subprocess.TimeoutExpired` lleva dentro (F12). Si Víctor prefería lo
otro, es una línea y un test.

**Lo que esta decisión NO decide:** «vacante sin descripción → sin score con
motivo» es el test 1 de **PR-11** (`SPEC.md` alcance 6), y el recálculo cuando la
descripción cambia es **D23/CA9** con el lote de R1·B2 (PR-21, PR-23). Y queda
en pie la **pregunta abierta 12** (F18): si la versión del texto de la vacante
entra en la identidad del score. La clave de idempotencia de ADR-001 §Decisión 3
no la incluye, y esta decisión no la cambia.

---

## Quién aprueba qué

| Qué | Quién | Estado |
|---|---|---|
| Proveedor, modelo y adaptador (§1) | Víctor (N4 acotada) | **decidido** el 22-nov-2026 |
| Retención cero y no entrenamiento, por escrito | Priya Shah | **pendiente**, antes del 12-dic-2026 |
| Recálculo de F23 y F31 con el proveedor elegido | quien aplique esta propuesta | pendiente |
| La descripción de la vacante en el pedido (§2) | Víctor | **decidido** el 22-nov-2026 |
| Mover los textos a `docs/decisiones.md` | un PR propio | pendiente |
