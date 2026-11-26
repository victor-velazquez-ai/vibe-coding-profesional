"""Los dos hallazgos de la revisión adversarial de «staging-local» (op-staging).

Esta tarea no tiene número de `PLAN.md` (es de la sección 8, «staging-local»);
el cuerpo del PR está en `docs/prs/staging-local.md` y su revisión señaló, entre
otros, estos dos huecos de `app/registro.py` + `app/match/services/listado.py` +
`app/match/cola/ejecutor.py` — ninguno de los tres tiene un solo test hoy:

1. **bloqueante** · `SoloNuestrosLoggers` (`app/registro.py`) solo deja pasar al
   archivo los loggers `app` o `app.*`. El logger del camino de **lectura**
   (`services/listado.py`) es `criba.match.listado`
   (`LOG_DEL_LISTADO`) — no empieza por `app.` —, así que la línea
   `match.listar_vacante` nunca llega a `staging/logs/app.jsonl`, aunque
   `RUNBOOK.md` §2 dice que sí («web | staging/logs/app.jsonl | una línea por
   vista de vacante»). El logger del camino de **escritura**
   (`app.match.cola.ejecutor`, `LOG_DEL_EJECUTOR`) sí empieza por `app.` y sí
   llega: la asimetría es justo lo que este test mide, con la misma vara para
   los dos;
2. **importante** · ni la línea `match.trabajo_cerrado` (`_registrar_cierre`,
   `cola/ejecutor.py`) ni la de `match.listar_vacante` (`_registrar`,
   `services/listado.py`) tienen un test que mire sus campos. Los dos son los
   controles de privacidad que el PR reclama (CA1 «ni log suyo», D15, F12) y
   los dos están, hoy, sin red: revertir el código no pone en rojo ningún test
   de la suite.

Lo que **no** hay aquí, a propósito: un test de `app/main.py`, de
`app/match/comandos/ejecutor.py` o de la sesión larga del bucle — la revisión
los señala como «importante» pero no son los dos que se pidió cubrir, y
escribirlos sin que alguien lo pida es inventar alcance (CLAUDE.md: «no
inventes requisitos»).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.match.cola.ejecutor import EVENTO_DE_CIERRE, LOG_DEL_EJECUTOR, una_pasada
from app.match.cola.trabajos import encolar
from app.match.services.listado import LOG_DEL_LISTADO, listar_vacante
from app.plataforma.modelos import Rol
from app.plataforma.sesion import ContextoEmpresa
from app.registro import VARIABLE_DE_DIRECTORIO, configurar_logs
from tests.dobles.proveedor import ProveedorContado
from tests.match.conftest import EmpresaDePrueba, sembrar_score

NOMBRE_DEL_PROCESO_WEB = "app"

# Los seis campos que RUNBOOK.md §2 promete para la línea de trabajo cerrado,
# más `evento` (que identifica la línea y no es dato del candidato).
CAMPOS_DE_TRABAJO_CERRADO = {
    "evento",
    "trabajo_id",
    "empresa_id",
    "vacante_id",
    "estado",
    "motivo",
    "ms",
}


@pytest.fixture
def raiz_de_logging_intacta() -> Iterator[None]:
    """Devuelve el logger raíz a como estaba, para no ensuciar el resto de la suite.

    `configurar_logs` marca sus manejadores con el nombre `criba` y, si ya hay
    uno puesto, no añade otro (`app/registro.py:MARCA`): sin este aislamiento,
    el primer test de la suite que llame a `configurar_logs` deja el archivo
    fijado para siempre y los siguientes no abrirían uno nuevo en su propio
    `tmp_path`.
    """
    raiz = logging.getLogger()
    manejadores_previos = list(raiz.handlers)
    nivel_previo = raiz.level
    yield
    for manejador in list(raiz.handlers):
        if manejador not in manejadores_previos:
            raiz.removeHandler(manejador)
            manejador.close()
    raiz.setLevel(nivel_previo)


def _lineas_del_archivo(archivo: Path) -> list[dict[str, object]]:
    if not archivo.exists():
        return []
    return [
        json.loads(linea)
        for linea in archivo.read_text(encoding="utf-8").splitlines()
        if linea.strip()
    ]


# --- 1 · bloqueante: el camino de lectura no llega al archivo ---------------


def test_la_linea_del_camino_de_lectura_llega_al_archivo_de_logs_igual_que_la_del_ejecutor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raiz_de_logging_intacta: None,
) -> None:
    """RUNBOOK.md §2: «web | staging/logs/app.jsonl | una línea por vista de
    vacante (match.listar_vacante)».

    `SoloNuestrosLoggers` (`app/registro.py`) solo deja pasar `record.name`
    igual a `app` o que empiece por `app.`. El logger del camino de lectura es
    `criba.match.listado` (`services/listado.py:LOG_DEL_LISTADO`): no cumple
    ese prefijo, así que su línea no debería llegar — y hoy no llega — al
    archivo que el proceso web escribe con `CRIBA_LOG_DIR`. El del ejecutor
    (`app.match.cola.ejecutor`) sí lo cumple y sí llega: por eso el mismo test
    comprueba los dos, con la misma vara, para que la asimetría se vea.
    """
    monkeypatch.setenv(VARIABLE_DE_DIRECTORIO, str(tmp_path))
    archivo = configurar_logs(NOMBRE_DEL_PROCESO_WEB)
    assert archivo is not None, "con CRIBA_LOG_DIR puesta, configurar_logs tiene que dar un archivo"

    logging.getLogger(LOG_DEL_LISTADO).info(json.dumps({"evento": "match.listar_vacante"}))
    logging.getLogger(LOG_DEL_EJECUTOR).info(json.dumps({"evento": EVENTO_DE_CIERRE}))

    eventos = {linea.get("evento") for linea in _lineas_del_archivo(archivo)}
    assert EVENTO_DE_CIERRE in eventos, (
        "la línea del ejecutor no llegó al archivo del proceso web: si esto falla, el problema "
        "ya no es solo del camino de lectura y hay que mirar el filtro entero"
    )
    assert "match.listar_vacante" in eventos, (
        f"la línea del camino de lectura (logger {LOG_DEL_LISTADO!r}) no llegó a {archivo}: "
        "SoloNuestrosLoggers solo deja pasar 'app' o 'app.*', y ese logger no empieza por ese "
        "prefijo, así que staging/logs/app.jsonl nace sin su mitad de lectura (RUNBOOK.md §2)"
    )


# --- 2 · importante: ninguna de las dos líneas lleva un dato del candidato --


def test_la_linea_de_listar_vacante_no_lleva_ningun_dato_del_candidato(
    sesion: Session,
    northstar: EmpresaDePrueba,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """CA1 «ni log suyo», D15, F12 · `services/listado.py:_registrar`.

    Se ejecuta el camino de lectura de verdad —con un candidato real, con
    nombre, correo y teléfono, y con un score ya guardado para que la rama de
    `con_match=True` se recorra— y se comprueba que ninguno de esos datos
    aparece en la línea que `_registrar` escribe. `_registrar` solo recibe el
    contexto de empresa, el `vacante_id`, el booleano de si hay Match, el
    número de filas y la latencia: nunca un candidato ni una fila de score, y
    este test es la red que lo deja escrito.
    """
    candidato = northstar.candidato
    sembrar_score(sesion, northstar)

    caplog.set_level(logging.INFO)
    contexto = ContextoEmpresa(empresa_id=northstar.empresa.id, es_soporte=False)
    lista = listar_vacante(sesion, contexto, northstar.vacante.id, rol=Rol.RECLUTADOR)

    assert lista is not None, "la vacante de Northstar tiene que resolver con su propio contexto"
    assert lista.muestra_score, (
        "con Match activo y rol reclutador, la rama con score tiene que correr"
    )

    registros = [r for r in caplog.records if r.name == LOG_DEL_LISTADO]
    assert registros, (
        "listar_vacante no registró ninguna línea: el control no estaría probando nada"
    )
    datos = json.loads(registros[-1].getMessage())
    assert datos.get("evento") == "match.listar_vacante"

    texto = registros[-1].getMessage()
    for dato, etiqueta in (
        (candidato.nombre, "nombre"),
        (candidato.correo, "correo"),
        (candidato.telefono, "teléfono"),
    ):
        assert dato not in texto, (
            f"la línea de match.listar_vacante lleva el {etiqueta} del candidato"
        )
    assert "candidato_id" not in datos, "la línea de match.listar_vacante nombra al candidato"


async def test_la_linea_de_trabajo_cerrado_no_lleva_ningun_dato_del_candidato(
    sesion: Session,
    northstar: EmpresaDePrueba,
    proveedor_contado: ProveedorContado,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """CA1 «ni log suyo», D15, F12 · `cola/ejecutor.py:_registrar_cierre`.

    Se encola y se procesa un trabajo real —del candidato de Northstar, con su
    nombre, correo y teléfono— y se comprueba que la línea de
    `match.trabajo_cerrado` trae **exactamente** los seis campos que
    `RUNBOOK.md` §2 promete (más `evento`) y ninguno de los tres datos del
    candidato. `_registrar_cierre` recibe la fila de `match_trabajos`, que sí
    tiene `candidato_id`: que no aparezca en la línea es una decisión del
    código, no una imposibilidad del tipo, y por eso hace falta un test.
    """
    candidato = northstar.candidato
    trabajo = encolar(sesion, northstar.vacante.id, candidato.id)
    assert trabajo is not None, "con Match activo para Northstar, encolar tiene que crear la fila"

    caplog.set_level(logging.INFO)
    hechos = await una_pasada(sesion, proveedor_contado)
    assert hechos == 1, "una_pasada tenía un trabajo pendiente que tomar"

    registros = [r for r in caplog.records if r.name == LOG_DEL_EJECUTOR]
    assert registros, "una_pasada no registró ninguna línea de cierre: el control no probaría nada"
    texto = registros[-1].getMessage()
    datos = json.loads(texto)
    assert datos.get("evento") == EVENTO_DE_CIERRE

    assert set(datos) == CAMPOS_DE_TRABAJO_CERRADO, (
        f"la línea de {EVENTO_DE_CIERRE} trae {sorted(datos)}, y el contrato de RUNBOOK.md §2 es "
        f"exactamente {sorted(CAMPOS_DE_TRABAJO_CERRADO)}: un campo de más es una fuga que nadie "
        "revisó"
    )
    for dato, etiqueta in (
        (candidato.nombre, "nombre"),
        (candidato.correo, "correo"),
        (candidato.telefono, "teléfono"),
    ):
        assert dato not in texto, (
            f"la línea de {EVENTO_DE_CIERRE} lleva el {etiqueta} del candidato"
        )
