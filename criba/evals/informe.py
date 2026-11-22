"""El informe: pass^1, pass^k, el total, y las dos formas de enseñarlo.

**Por qué dos cifras y no una.** El arnés corre cada caso **k veces** porque un
modelo no es determinista, y las dos dicen cosas distintas:

- **pass^1** = aciertos / k. La probabilidad de acertar una vez;
- **pass^k** = los **k** intentos bien. Es lo único que vale para un criterio que
  en producción se cumple en **cada** llamada —no mencionar la edad (fs-26), no
  obedecer al CV (fs-28)—, y es la cifra que un promedio esconde: tres casos con
  2/3 dan un pass^1 del 67 % y un pass^k de cero.

Las dos son **fracciones** en los dos niveles, el del caso y el total, para que
quien lea el informe pueda sumarlas; y `casos` e `intentos` van al lado para que un
50 % no se lea sin saber que son dos casos.

**El costo y el modelo entran por parámetros opcionales** y no se calculan aquí:
los pone el proveedor, no el calificador (`corredor.py` los recoge). Un informe sin
ellos sigue siendo un informe —es el caso de los tests, que califican respuestas
fabricadas a mano—; con el proveedor real son la mitad de la razón de mirarlo.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from evals.calificacion import Calificacion

# Lo que se enseña de un caso que no pasó: los motivos del **primer** intento que
# falló. Enteros serían k veces el mismo texto en el caso corriente —un caso que
# falla, falla por lo mismo en los tres intentos— y el informe dejaría de leerse.
INTENTOS_CON_MOTIVO = 1


@dataclass(frozen=True, slots=True)
class ResultadoDeCaso:
    """Los k intentos de un caso, contados."""

    caso_id: str
    k: int
    aciertos: int
    pass_1: float
    pass_k: bool
    calificaciones: tuple[Calificacion, ...]

    @property
    def motivos(self) -> tuple[str, ...]:
        """Por qué no pasó, del primer intento que falló."""
        fallos = [una for una in self.calificaciones if not una.paso]
        return tuple(motivo for una in fallos[:INTENTOS_CON_MOTIVO] for motivo in una.motivos)


@dataclass(frozen=True, slots=True)
class Totales:
    """El total de la pasada. `pass_k` es la **fracción de casos** con los k bien."""

    casos: int
    intentos: int
    aciertos: int
    pass_1: float
    pass_k: float
    costo_usd: float | None = None
    modelos: tuple[str, ...] = ()


def _fraccion(parte: int, total: int) -> float:
    """La fracción, y **0.0 cuando no hay nada que dividir**.

    Pasa de verdad: `--casos` vacío, o una pasada que se corta antes del primer
    intento. Un `ZeroDivisionError` dentro del informe perdería los resultados ya
    obtenidos, que es justo lo que no se puede permitir con el proveedor real: esos
    intentos ya se pagaron.
    """
    return parte / total if total else 0.0


def resumir_caso(caso_id: str, calificaciones: Iterable[Calificacion]) -> ResultadoDeCaso:
    """Las k calificaciones de un caso → pass^1 y pass^k.

    `pass_k` exige que **haya** intentos: cero intentos no son «los k bien».
    """
    intentos = tuple(calificaciones)
    aciertos = sum(1 for una in intentos if una.paso)
    return ResultadoDeCaso(
        caso_id=caso_id,
        k=len(intentos),
        aciertos=aciertos,
        pass_1=_fraccion(aciertos, len(intentos)),
        pass_k=bool(intentos) and aciertos == len(intentos),
        calificaciones=intentos,
    )


def totales(
    resultados: Sequence[ResultadoDeCaso],
    *,
    costo_usd: float | None = None,
    modelos: Iterable[str] = (),
) -> Totales:
    """El total de la pasada: los intentos de todos los casos y los casos enteros."""
    intentos = sum(uno.k for uno in resultados)
    aciertos = sum(uno.aciertos for uno in resultados)
    enteros = sum(1 for uno in resultados if uno.pass_k)
    return Totales(
        casos=len(resultados),
        intentos=intentos,
        aciertos=aciertos,
        pass_1=_fraccion(aciertos, intentos),
        pass_k=_fraccion(enteros, len(resultados)),
        costo_usd=costo_usd,
        modelos=tuple(modelos),
    )


# --- las dos formas de enseñarlo -------------------------------------------


def _marca(valor: bool | None) -> str:
    """`None` se enseña como «—» y no como «no»: la dimensión no se calificó."""
    return {True: "si", False: "NO", None: "—"}[valor]


def lineas(resultados: Sequence[ResultadoDeCaso], total: Totales) -> list[str]:
    """El informe que se lee en la terminal, caso por caso.

    Una línea por caso con las cuatro dimensiones del **último** intento y las dos
    cifras, más los motivos del primer intento que falló. Las dimensiones se
    enseñan porque «pass^1 = 0/3» sin ellas obliga a abrir el JSON para saber si
    falló la banda o una mención prohibida.
    """
    salida = [
        f"{'caso':<8} {'banda':<16} {'bnd':>3} {'men':>3} {'inv':>3} {'iny':>3} "
        f"{'pass^1':>8} {'pass^k':>6}"
    ]
    for uno in resultados:
        ultima = uno.calificaciones[-1] if uno.calificaciones else None
        banda = ultima.banda if ultima else "—"
        salida.append(
            f"{uno.caso_id:<8} {banda:<16} "
            f"{_marca(ultima.banda_ok) if ultima else '—':>3} "
            f"{_marca(ultima.menciones_ok) if ultima else '—':>3} "
            f"{_marca(ultima.invariante_ok) if ultima else '—':>3} "
            f"{_marca(ultima.inyeccion_ok) if ultima else '—':>3} "
            f"{uno.aciertos}/{uno.k} ({uno.pass_1:.0%}){'':>1} "
            f"{'si' if uno.pass_k else 'NO':>6}"
        )
        for motivo in uno.motivos:
            salida.append(f"{'':<8}   · {motivo}")
    salida.append(
        f"TOTAL    {total.casos} casos · {total.intentos} intentos · "
        f"pass^1 {total.aciertos}/{total.intentos} ({total.pass_1:.0%}) · "
        f"pass^k {total.pass_k:.0%}"
    )
    return salida


def como_json(
    resultados: Sequence[ResultadoDeCaso],
    total: Totales,
    *,
    cabecera: dict[str, object],
) -> dict[str, object]:
    """El informe que se guarda en `evals/resultados/`.

    Lleva **las k calificaciones de cada caso y sus motivos**, no solo el resumen:
    la pregunta que se le hace a un informe guardado dos semanas después es «¿qué
    contestó el modelo en el intento que falló?», y un pass^1 del 67 % no la
    contesta. Lo que **no** lleva es el texto de ninguna respuesta del modelo ni el
    de ningún CV: los casos son sintéticos, pero el formato del informe es el que
    mañana se usará con el conjunto dorado de CA14, que son datos del cliente
    (D3 modificado, D15, F12).
    """
    return {
        **cabecera,
        "total": {
            "casos": total.casos,
            "intentos": total.intentos,
            "aciertos": total.aciertos,
            "pass_1": total.pass_1,
            "pass_k": total.pass_k,
            "costo_usd": total.costo_usd,
            "modelos": list(total.modelos),
        },
        "casos": [
            {
                "caso_id": uno.caso_id,
                "k": uno.k,
                "aciertos": uno.aciertos,
                "pass_1": uno.pass_1,
                "pass_k": uno.pass_k,
                "intentos": [
                    {
                        "banda": una.banda,
                        "banda_ok": una.banda_ok,
                        "menciones_ok": una.menciones_ok,
                        "invariante_ok": una.invariante_ok,
                        "inyeccion_ok": una.inyeccion_ok,
                        "paso": una.paso,
                        "motivos": list(una.motivos),
                    }
                    for una in uno.calificaciones
                ],
            }
            for uno in resultados
        ],
    }
