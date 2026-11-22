# Inventario de borrado de Criba Match

Dónde vive cada dato que Match deriva de un candidato. Es la **segunda mitad de
CA16** («el inventario de dónde vive cada dato está en el repo») y la mitigación
que `docs/fallas.md` asigna a **F13** y a **F25**.

Este documento es el inventario para leer con los ojos; el que el código recorre
vive en **`app/match/borrado/inventario.py`**, y
`tests/match/test_inventario_migraciones.py` falla si los dos no dicen lo mismo o
si una migración crea una tabla que no está en ninguno de los dos. **Toda tabla
`match_*` tiene entrada, también las que no guardan nada del candidato** (PR-02,
ronda 6 M7): una tabla ausente es indistinguible de una olvidada.

Quién recorre esto para borrar de verdad: **PR-18**, dentro de
`RepositorioEmpresa.borrar_candidato` y **antes** de que se borre la fila del
candidato (`docs/prs/PR-01.md`, hecho 2). Ninguna clave ajena de Match declara `ON
DELETE CASCADE`, así que nada de esto se borra solo (ronda 3 M2).

## Las cuatro tablas · 22-nov-2026, migración `0001_match_inicial.py`

| Tabla | Columnas con dato derivado del candidato | Por qué es dato suyo |
|---|---|---|
| `match_scores` | `candidato_id`, `score`, `razones`, `motivo_sin_score` | `candidato_id` apunta a él; `score` y `motivo_sin_score` son juicios derivados de su CV; y **`razones` es texto derivado del CV**, que puede citar evidencia textual (RI5). F25 avisa de que las razones se quedan atrás cuando el inventario se escribe pensando solo en el número. |
| `match_trabajos` | `candidato_id`, `clave_idempotencia`, `motivo` | CA16 nombra «entradas en la cola» entre lo que hay que borrar. La `clave_idempotencia` lleva dentro el **hash de su CV** (`docs/adr/ADR-001.md` §Decisión 3), o sea un identificador que apunta a él; `motivo` describe por qué su CV no se pudo puntuar. |
| `match_auditoria_scores` | `candidato_id`, `hash_cv` | `hash_cv` es el identificador que el test de CA16 busca junto al `candidato_id`. Aquí no hay texto del CV (D15, CA15). |
| `match_gasto_mes` | **ninguna** | Contador del gasto del mes de **toda la plataforma** (D12, CA10), agregado por mes y etiqueta de uso. No tiene `empresa_id`, ni `candidato_id`, ni nada derivado de un CV: una fila dice cuánto se gastó en un mes, no de quién. |

## Lo que este inventario no decide

- **¿La fila de `match_auditoria_scores` sobrevive al borrado, anonimizada?** Es
  la **pregunta abierta 3 de `SPEC.md`** y la **decide Priya** con el criterio de
  SOC 2: CA15 (guardar para auditar) y CA16 (borrar todo en 7 días) empujan en
  direcciones opuestas. Hasta que decida, la tabla entra en el recorrido de PR-18
  como cualquier otra, y lo que este paso garantiza es que la decisión siga
  siendo suya: sin `ON DELETE CASCADE`, el esquema no la toma por ella en enero.
  Las dos aserciones de ese caso en `tests/match/test_borrado_candidato.py` van
  con `xfail(strict=True, reason='pregunta 2 §9, Priya')`, y **con esos
  marcadores no se puntúa ni un candidato real** (PLAN.md §1 regla 7).
  Dependencia bloqueante: **antes del 12-dic-2026**.
- **Las tablas que Match añada después.** El control no es este documento: es el
  test, que falla en la migración que las crea.
