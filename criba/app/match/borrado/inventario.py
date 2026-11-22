"""Inventario de borrado, legible por el test (PR-02, CA16, F13, F25).

Es la **segunda mitad de CA16**: «el inventario de dónde vive cada dato está en
el repo». Vive en código para que `tests/match/test_inventario_migraciones.py` lo
lea y falle cuando una migración nueva cree una tabla que nadie añadió (F13: «nos
tardamos dos semanas en encontrar dónde estaba todo», [04:35]).
`docs/inventario-borrado.md` dice lo mismo para leer con los ojos, y el test
exige que coincidan. **Toda** tabla `match_*` tiene entrada, también las que no
guardan nada del candidato (R6·M7): una tabla ausente es indistinguible de una
olvidada, y entonces `columnas` va vacío y `por_que` dice por qué. Quién recorre
esto para borrar: PR-18. Este paso solo declara el mapa.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Entrada:
    """Una tabla de Match, qué guarda del candidato y por qué eso es dato suyo."""

    tabla: str
    columnas: tuple[str, ...]
    por_que: str


INVENTARIO: tuple[Entrada, ...] = (
    Entrada(
        tabla="match_scores",
        columnas=("candidato_id", "score", "razones", "motivo_sin_score"),
        por_que=(
            "`candidato_id` apunta a él, `score` y `motivo_sin_score` derivan de su CV, y "
            "**`razones` es texto del CV** y puede citar evidencia textual (RI5, F25)."
        ),
    ),
    Entrada(
        tabla="match_trabajos",
        columnas=("candidato_id", "clave_idempotencia", "motivo"),
        por_que=(
            "CA16 nombra «entradas en la cola». La `clave_idempotencia` lleva dentro el "
            "hash de su CV (ADR-001 §Decisión 3): un identificador que apunta a él."
        ),
    ),
    Entrada(
        tabla="match_auditoria_scores",
        columnas=("candidato_id", "hash_cv"),
        por_que=(
            "`hash_cv` es el identificador que el test de CA16 busca junto al "
            "`candidato_id`; aquí no hay texto del CV (D15, CA15). **Si la fila sobrevive "
            "anonimizada lo decide Priya** (pregunta abierta 3 de `SPEC.md`)."
        ),
    ),
    Entrada(
        tabla="match_gasto_mes",
        columnas=(),
        por_que=(
            "**Ninguna, y por qué:** contador del gasto del mes de toda la plataforma "
            "(D12, CA10), agregado por mes y etiqueta de uso. Sin `empresa_id`, sin "
            "`candidato_id` y sin nada de un CV: dice cuánto, no de quién (R6·M7)."
        ),
    ),
)


def tablas() -> tuple[str, ...]:
    return tuple(e.tabla for e in INVENTARIO)


def entrada(tabla: str) -> Entrada | None:
    return next((e for e in INVENTARIO if e.tabla == tabla), None)
