"""PR-PERF-1 · ronda 1, I1 · la **mitad de base de datos** del cambio nº 1.

`tests/match/test_lista_sin_cv_texto.py` mira el HTML de la respuesta, así que
cubre la mitad visible del cambio nº 1 de `perf/MEDICION.md` §6: que el
`cv_texto` no viaje al navegador. La otra mitad —la que mueve el número que §6
nº 1 promete, la **fase SQL** (19,5 → 8,7 ms)— no la cubre nadie: si
`candidatos_de_vacante` volviera a `select(Candidato, Postulacion, …)` y el largo
se calculara en Python con `len(c.cv_texto or '')`, la plantilla pintaría
exactamente el mismo HTML, los ocho tests del PR seguirían verdes y los **10,5 ms
de driver** que §5.1 atribuye a la columna del CV (medida 2 contra medida 3)
volverían íntegros.

Lo que se asercia, entonces, es la sentencia: la consulta de la lista **no
proyecta la columna `candidatos.cv_texto`**; del CV solo cruza un número,
calculado por una función de SQL sobre esa columna (`length(…)` hoy).

**Alcance, dicho en voz alta.** La aserción es sobre la consulta de la lista y
**solo** sobre ella, no sobre todas las sentencias de `GET /vacantes/{id}`: el
`<select>` de «añadir un candidato» (`candidatos_sin_postular_a`) sigue trayendo
el `cv_texto` de todos los candidatos de la empresa, y eso es el cambio **nº 4**
de §6 (§5.3), que este PR declara fuera de alcance. Un guardia global nacería
rojo por un cambio que nadie pidió aquí.

**No se escribe el SQL a mano**: la sentencia de la lista se reconoce por su
`JOIN postulaciones`, que es el mismo criterio con el que `perf/perfil.py`
(`NOMBRES_DE_CONSULTA`) separa esas dos consultas sobre `candidatos`. Y tampoco
se exige `length` por su nombre: vale cualquier función de SQL sobre la columna
—`btrim` anidado, por ejemplo, que es lo que el hallazgo M1 propone—, porque lo
que se protege es que el texto no cruce, no cómo se cuente.

Multiempresa, como siempre: la comprobación se hace con la sesión de Northstar
sobre su vacante y con la de Meridian sobre la suya, y cada una ve solo a sus
candidatos (CA1, D4, [03:03]).

Fuentes: `perf/MEDICION.md` §5.1 (medidas 2 y 3), §5.2, §6 nº 1 y nº 4, §5.3;
`SPEC.md` CA1, CA5, CA8; `docs/fallas.md` F27; `docs/prs/PR-PERF-1.md`
(«Tres decisiones de construcción», riesgo 4).
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.plataforma.repositorio import RepositorioEmpresa
from tests.match.conftest import EmpresaDePrueba, Entrar, sembrar_candidatos
from tests.match.test_vacante_no_espera import contar_consultas

CUANTOS = 6
COLUMNA = "candidatos.cv_texto"
# El `JOIN postulaciones` es lo único que distingue la consulta de la lista de la
# del `<select>`: las dos salen de `candidatos` (`perf/perfil.py`).
MARCAS_DE_LA_LISTA = ("FROM candidatos", "JOIN postulaciones")


def _proyeccion(sentencia: str) -> str:
    """Lo que va entre el primer `SELECT` y su `FROM`: las columnas que cruzan.

    Se corta en el primer `\\nFROM` de nivel superior; las subconsultas
    correlacionadas (el conteo de notas, F27) traen su propio `FROM` más
    adentro y no estorban, porque no mencionan `candidatos`.
    """
    cuerpo = sentencia.split("SELECT", 1)[1]
    return re.split(r"\bFROM\b", cuerpo)[0]


def _apariciones(proyeccion: str) -> tuple[list[str], list[str]]:
    """Las apariciones de `candidatos.cv_texto`, partidas en desnudas y envueltas.

    Desnuda = proyectada tal cual (`…, candidatos.cv_texto, …`), que es lo que
    hace cruzar el texto entero. Envuelta = dentro de una llamada de función
    (`length(candidatos.cv_texto)`), que es lo que cruza un entero.
    """
    desnudas, envueltas = [], []
    for aparicion in re.finditer(re.escape(COLUMNA), proyeccion):
        antes = proyeccion[: aparicion.start()].rstrip()
        contexto = proyeccion[max(0, aparicion.start() - 40) : aparicion.end() + 20]
        (envueltas if antes.endswith("(") else desnudas).append(contexto)
    return desnudas, envueltas


def _sentencia_de_la_lista(sentencias: list[str]) -> str:
    """La sentencia de `candidatos_de_vacante`, y exactamente una."""
    de_la_lista = [s for s in sentencias if all(marca in s for marca in MARCAS_DE_LA_LISTA)]
    assert len(de_la_lista) == 1, (
        f"se esperaba una sola consulta de la lista y hay {len(de_la_lista)} "
        f"de {len(sentencias)} sentencias:\n" + "\n---\n".join(sentencias)
    )
    return de_la_lista[0]


def test_la_consulta_de_la_lista_no_proyecta_la_columna_cv_texto(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    entrar: Entrar,
) -> None:
    """§6 nº 1, la mitad de SQL · del CV cruza un número, nunca el texto.

    Es el único control de este PR que mira la **fase SQL**, que es el número que
    §6 nº 1 promete mover (19,5 → 8,7 ms, §5.1 sondeo y medidas 2 contra 3).
    """
    for empresa, ajena in ((northstar, meridian), (meridian, northstar)):
        repo = RepositorioEmpresa(sesion, empresa.empresa.id)
        for indice, candidato in enumerate(sembrar_candidatos(sesion, empresa, CUANTOS)):
            repo.guardar_cv(candidato.id, f"CV sintético {indice}. " + "relleno. " * 30)
        sesion.flush()

        cliente = entrar(empresa.reclutador)
        with contar_consultas(sesion) as sentencias:
            respuesta = cliente.get(f"/vacantes/{empresa.vacante.id}")
        assert respuesta.status_code == 200, f"{empresa.slug} recibió {respuesta.status_code}"
        assert ajena.candidato.correo not in respuesta.text, (
            f"{empresa.slug} ve un candidato de {ajena.slug}"
        )

        sentencia = _sentencia_de_la_lista(sentencias)
        desnudas, envueltas = _apariciones(_proyeccion(sentencia))
        assert desnudas == [], (
            f"la consulta de la lista de {empresa.slug} proyecta `{COLUMNA}` tal cual: el texto "
            "del CV cruza el driver por cada fila (perf/MEDICION.md §5.1, 10,5 ms de 24,9 ms)\n"
            + "\n".join(desnudas)
            + f"\n\nsentencia completa:\n{sentencia}"
        )
        assert envueltas, (
            f"la consulta de la lista de {empresa.slug} no calcula nada sobre `{COLUMNA}` en "
            "Postgres: el largo que la lista pinta tiene que salir de una función de SQL "
            f"—`length(…)`— y no de traerse el texto (perf/MEDICION.md §6 nº 1)\n{sentencia}"
        )
