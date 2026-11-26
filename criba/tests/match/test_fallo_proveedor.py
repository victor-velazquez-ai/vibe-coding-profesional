"""CA6 y CA13 · el proveedor caído no deja un cero en la vacante (incidente 001).

El archivo que `SPEC.md` CA6 nombra —«doble que lanza timeout y error 500;
verifica el estado del candidato y el 200 de la vista»— y que hasta el incidente
001 no existía: `tests/match/test_camino_escritura.py` cierra el circuito feliz de
PR-06 y **no tiene ningún caso de error**, así que el camino de excepción de
`una_pasada` entró sin un test que lo ejerciera (commit `8ee8160`, diagnóstico de
la sesión de triage del 22-nov-2026, §4 «qué falló aquí»).

Qué criterio sostiene cada test, porque ninguno es sobre «excepciones»:

- **CA13** (`SPEC.md:91-93`, «Sin score, nunca un cero»): o hay score, o hay «sin
  score» con su motivo. Cuando el proveedor falla no hay ninguna de las dos
  cosas que escribir, así que **no se escribe fila de score**: ni un 0, ni razones
  vacías. Es la falla **F8** del mapa, con su escenario escrito desde noviembre:
  «si se guarda un 0, se viola CA13: un cero se lee como *no encaja*»
  (`docs/fallas.md:75`). Y es el criterio de terminado de **PR-11**: «no existe
  ningún camino que escriba `score = 0`» (`PLAN.md` PR-11);
- **CA6** (`SPEC.md:63-65`): la vista responde 200 y el candidato sigue ahí, sin
  score. Un 0 guardado con `estado="listo"` (`match_repo.py:267`) lo saca de los
  pendientes y lo pinta como un candidato puntuado con la peor nota posible;
- **CA9(a)** en su mitad destructiva: `guardar_score` **actualiza** la fila
  existente, así que un fallo del proveedor sobre un par que ya tenía un score
  bueno se lo lleva. El alcance del incidente son 7 pares; con un re-puntuado por
  CV nuevo (CA9(a)) serían 7 scores **perdidos**;
- **CA1** (`SPEC.md:43-45`, el requisito número uno): el cero falso de Northstar
  no se ve desde Meridian, ni al contrario. Las dos empresas de la fixture fallan
  a propósito en los dos primeros tests y el cuarto recorre los endpoints.

Lo que estos tests **no** deciden, porque `PLAN.md` no lo decide y el escritor de
tests no adivina: si el par queda **sin fila** —el candidato en «Pendientes de
score» por ausencia, que es lo que CA6 describe y lo que `PLAN.md` PR-11 llama
causa transitoria— o con una fila `score=None` + `estado="sin_score"` + motivo.
Las dos formas cumplen CA13 y la tabla de estados de PR-11 reparte por causa. Lo
único que se exige aquí es lo que CA13 no deja negociar: **ninguna fila de score
con un número que nadie calculó**, y el score anterior intacto.

La **sección «Pendientes de score»** de CA8 no se asercia aquí: es de PR-20 y hoy
no existe. Lo que se asercia es lo que la reclutadora de Northstar vio el 22-nov
y lo que no tiene que volver a ver: un número en la celda de score de un
candidato que nadie puntuó.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.match.cola.ejecutor import pasadas, una_pasada
from app.match.cola.trabajos import encolar
from app.match.configuracion import IDIOMA_POR_OMISION
from tests.dobles.cli import adaptador
from tests.dobles.proveedor import RAZONES, ProveedorContado
from tests.match.conftest import (
    EmpresaDePrueba,
    Entrar,
    repo_de,
    rutas_de_match,
    sembrar_score,
)

# El mensaje del fallo del proveedor. Es sintético y **largo**, para que se vea si
# alguien lo copia al `motivo` de la fila o a una línea de log: el mensaje de una
# excepción del subproceso lleva dentro `argv` y la salida parcial del modelo, o
# sea el prompt y el CV (F12, D15, `cliente.py:27-32`).
MENSAJE_DEL_FALLO = "fallo sintético del proveedor, con la línea de órdenes dentro"

# La celda de score tal como la pintan los dos fragmentos que la tienen
# (`app/plataforma/plantillas/_candidatos.html` y
# `app/match/templates/match/_lista.html`): `—` si no hay score, el número si lo
# hay. Es lo que la reclutadora lee, y por eso es lo que se asercia.
CELDA_DE_SCORE = re.compile(r'data-testid="score">([^<]*)<')


def celdas_de_score(html: str) -> list[str]:
    return [celda.strip() for celda in CELDA_DE_SCORE.findall(html)]


def numeros_en_la_vista(html: str) -> list[str]:
    """Las celdas de score que muestran **un número**, que es lo que CA13 prohíbe
    cuando nadie puntuó: un 0 junto al nombre de una enfermera se lee como «no
    encaja» (F8) y no como «todavía no se pudo calcular»."""
    return [celda for celda in celdas_de_score(html) if celda.isdigit()]


def _con_descendientes(clase: type[BaseException]) -> Iterator[type[BaseException]]:
    yield clase
    for hija in clase.__subclasses__():
        yield from _con_descendientes(hija)


# **Enumerados, no escritos a mano** (el patrón de `rutas_de_match`, F34): el
# error tipado que PR-09 añada mañana entra en este recorrido sin tocar el test.
# Hoy son tres: `ErrorDelProveedor` (código de salida distinto de 0, CLI ausente),
# `TiempoDeEsperaDelProveedor` y `RespuestaInvalidaDelProveedor`. Los tres son
# «cualquier error tipado del adaptador», que es la puerta por la que el incidente
# 001 entró: 7 de 19 llamadas con `decision=codigo_de_salida`.
ERRORES_TIPADOS = tuple(sorted(set(_con_descendientes(adaptador().error)), key=str))


# --- 1 · CA13 · un fallo del proveedor no escribe ninguna fila de score -----


@pytest.mark.parametrize("error", ERRORES_TIPADOS, ids=[c.__name__ for c in ERRORES_TIPADOS])
async def test_un_error_tipado_del_proveedor_deja_el_trabajo_en_error_y_cero_filas_de_score(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    activar_match: Callable[[str], None],
    error: type[BaseException],
) -> None:
    """CA13, F8, PR-11 · el trabajo en `error` con su motivo, y **nada** de score.

    El camino exacto del incidente 001 visto desde el bucle: el proveedor falla y
    `una_pasada` entra en su camino de excepción. Lo que tiene que quedar es la
    fila de la cola en `error` con un motivo —el de la cola, no uno que se le
    muestre al candidato— y **ninguna fila en `match_scores`** para ese par.

    Hoy queda un `score=0` con `estado="listo"` y la razón «No se pudo evaluar
    automáticamente.» (`ejecutor.py:103-112` + `match_repo.py:267`), que para la
    vista y para `metricas.scores_por_vacante` es un score de verdad: son los 7
    ceros de las vistas de staging, uno por cada trabajo en `ErrorDelProveedor`.

    **Las dos empresas fallan a propósito** (CA1, R6·I3): «cero filas» se asercia
    por empresa, porque en global pasaría igual con el `empresa_id` cambiado.

    Y el motivo de la fila **no cita el mensaje del proveedor**: ese mensaje lleva
    `argv` y la salida parcial del modelo, o sea el prompt y el CV (F12, D15).
    """
    activar_match(meridian.slug)
    encolar(sesion, northstar.vacante.id, northstar.candidato.id)
    encolar(sesion, meridian.vacante.id, meridian.candidato.id)
    proveedor = ProveedorContado(fallo=error(MENSAJE_DEL_FALLO))

    assert await pasadas(sesion, proveedor) == 2, "el bucle no cerró los dos trabajos"
    assert proveedor.llamadas == 2

    for empresa in (northstar, meridian):
        repo = repo_de(sesion, empresa)
        trabajos = repo.trabajos()
        assert [t.estado for t in trabajos] == ["error"], f"{empresa.slug}: la cola no se cerró"
        assert trabajos[0].motivo, f"{empresa.slug}: el trabajo quedó en error sin motivo"
        assert MENSAJE_DEL_FALLO not in trabajos[0].motivo, (
            "el motivo de la fila cita el mensaje del proveedor, que lleva `argv` y la salida "
            "parcial del modelo dentro (F12, D15)"
        )
        assert repo.scores() == [], (
            f"{empresa.slug}: el proveedor falló y se escribió una fila de score igual: "
            f"{[(s.score, s.estado, s.motivo_sin_score) for s in repo.scores()]}. CA13 dice que "
            "o hay score, o hay «sin score» con su motivo; un 0 con estado «listo» es un score "
            "que nadie calculó (F8, `docs/fallas.md:75`)"
        )


# --- 2 · CA9(a) · el score que ya estaba no se pisa -------------------------


async def test_un_fallo_del_proveedor_no_pisa_el_score_que_el_par_ya_tenia(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
) -> None:
    """CA9(a) y CA13 · el agravante del alcance del incidente 001.

    `guardar_score` **actualiza la fila existente** del par (empresa, candidato,
    vacante, idioma) — `match_repo.py:264-271`, y está bien que lo haga: CA9(a)
    dice que un CV nuevo vuelve a puntuar el par. Lo que no puede pasar es que el
    camino de excepción use esa puerta: un candidato con un 72 legítimo que sube
    un CV nuevo y pilla el minuto en que el proveedor falla **pierde el 72** y se
    queda con el cero falso. En las vistas de staging eso no se distingue de un
    par que nunca se puntuó, y por eso el diagnóstico lo pone en el alcance.

    Las tres cosas tienen que seguir como estaban: el número, el estado y las
    razones del modelo. Y el trabajo, en `error`: el score viejo intacto no es
    excusa para cerrar el trabajo como si se hubiera puntuado.
    """
    previo = sembrar_score(sesion, northstar, 72)
    assert (previo.score, previo.estado, previo.idioma) == (72, "listo", IDIOMA_POR_OMISION)

    encolar(sesion, northstar.vacante.id, northstar.candidato.id)
    proveedor = ProveedorContado(fallo=adaptador().error(MENSAJE_DEL_FALLO))
    assert await una_pasada(sesion, proveedor) == 1
    assert proveedor.llamadas == 1

    repo = repo_de(sesion, northstar)
    assert [t.estado for t in repo.trabajos()] == ["error"]
    scores = repo.scores()
    assert len(scores) == 1, f"el fallo añadió filas de score: {len(scores)}"
    quedo = scores[0]
    assert (quedo.score, quedo.estado, tuple(quedo.razones), quedo.motivo_sin_score) == (
        72,
        "listo",
        RAZONES,
        None,
    ), (
        "el fallo del proveedor pisó el score que el par ya tenía: la reclutadora abre la "
        "vacante y el candidato que tenía 72 aparece con lo que escribió el camino de "
        "excepción (CA9(a), CA13)"
    )
    assert repo_de(sesion, meridian).scores() == [], "una fila de score cruzó de empresa"


# --- 3 · CA6 · la vista responde 200 y sin un número en la celda ------------


async def test_con_el_proveedor_caido_la_vacante_responde_200_y_sin_un_numero_de_score(
    sesion: Session,
    northstar: EmpresaDePrueba,
    entrar: Entrar,
) -> None:
    """CA6 (`SPEC.md:63-65`) · «la página responde 200 y el candidato aparece».

    Es lo que la reclutadora de Northstar vio el 22-nov y lo que no tiene que
    volver a ver: su enfermera en la lista con un **0** en la celda de score. Las
    dos superficies donde esa celda se pinta: la vista de vacante de la plataforma
    —`GET /vacantes/{id}`, hecho 4 de PR-01, que es por donde se llega— y el
    fragmento propio de Match.

    Se asercia «ninguna celda de score con un número» y no «la celda dice `—`»: el
    texto de la celda sin score es de PR-20 (motivo visible) y este test no
    anticipa su forma. La sección «Pendientes de score» de CA8 tampoco se asercia
    aquí por lo mismo.
    """
    encolar(sesion, northstar.vacante.id, northstar.candidato.id)
    proveedor = ProveedorContado(fallo=adaptador().error(MENSAJE_DEL_FALLO))
    assert await una_pasada(sesion, proveedor) == 1

    cliente = entrar(northstar.reclutador)
    vista = cliente.get(f"/vacantes/{northstar.vacante.id}")
    assert vista.status_code == 200, "el proveedor caído rompió la vista de la vacante (CA6)"
    assert northstar.candidato.correo in vista.text, "el candidato desapareció de su vacante"

    fragmento = cliente.get(f"/match/vacantes/{northstar.vacante.id}/lista")
    assert fragmento.status_code == 200
    for donde, html in (("la vista de vacante", vista.text), ("el fragmento", fragmento.text)):
        assert celdas_de_score(html), f"{donde}: no se pintó la columna de score"
        assert numeros_en_la_vista(html) == [], (
            f"{donde}: hay un número en la celda de score de un candidato que nadie puntuó "
            f"({numeros_en_la_vista(html)}). Un cero se lee como «no encaja» (F8) y CA13 lo "
            "prohíbe: o score, o «sin score» con motivo"
        )


# --- 4 · CA1 · el cero falso no cruza de empresa ----------------------------


async def test_el_fallo_del_proveedor_no_deja_nada_que_la_otra_empresa_pueda_ver(
    sesion: Session,
    aplicacion: FastAPI,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    activar_match: Callable[[str], None],
    entrar: Entrar,
) -> None:
    """CA1 (el requisito número uno) · 404 en los dos sentidos, y cero filas.

    El incidente 001 fue de una sola empresa —7 pares, todos de `empresa_id=1`—, y
    esa es la mitad que las vistas de staging confirmaron. La otra mitad hay que
    sostenerla con un test: el camino de excepción escribe por el repositorio con
    el contexto de la **fila de la cola** (F5), así que una empresa equivocada ahí
    pondría el cero falso en la vacante de otro cliente.

    Las rutas de Match se **enumeran** (F34), igual que en `test_aislamiento.py`:
    el endpoint que PR-20 añada entra en el recorrido sin tocar este test.
    """
    activar_match(meridian.slug)
    encolar(sesion, northstar.vacante.id, northstar.candidato.id)
    encolar(sesion, meridian.vacante.id, meridian.candidato.id)
    assert await pasadas(sesion, ProveedorContado(fallo=adaptador().error(MENSAJE_DEL_FALLO))) == 2

    rutas = rutas_de_match(aplicacion)
    assert rutas, "no hay ninguna ruta de Match que recorrer"
    for mia, ajena in ((northstar, meridian), (meridian, northstar)):
        cliente = entrar(mia.reclutador)
        for ruta in (*rutas, "/vacantes/{vacante_id}"):
            respuesta = cliente.get(ruta.format(vacante_id=ajena.vacante.id))
            assert respuesta.status_code == 404, (
                f"{ruta} con sesión de {mia.slug} y un id de {ajena.slug}: {respuesta.status_code}"
            )
            assert ajena.candidato.correo not in respuesta.text
        repo = repo_de(sesion, mia)
        assert repo.scores() == [], (
            f"{mia.slug}: el fallo del proveedor dejó una fila de score "
            f"{[(s.score, s.estado) for s in repo.scores()]}, que es el cero falso del "
            "incidente 001 (CA13)"
        )
