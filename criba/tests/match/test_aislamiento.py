"""PR-04 · el punto único de acceso a datos (primera mitad de `test_aislamiento`).

Esto no prueba scoring: prueba que **ningún dato de Match se lee ni se escribe
sin un `empresa_id` que venga del contexto** (D4, CA1, F4,
`llamadas/2026-11-20-tomas.md` [03:25], `docs/arquitectura.md` §4) y que el
camino que lo viola **no existe en el repo**: la enumeración recorre toda la
aplicación, no solo `app/match/`.

Qué patrones detecta la regla (a) y cuáles no está en `docs/prs/PR-04.md`.

**La segunda mitad es de PR-05** y está al final del archivo: el recorrido de CA1
por **todos** los endpoints de Match con sesión de otra empresa y con contexto de
soporte, la lista sin nada de Match de una empresa sin anexo (CA3) y la mitad «ni
log suyo» de CA1 (R6·M6). El hiring manager y las cero llamadas al abrir viven en
`test_hiring_manager.py` y `test_vacante_no_espera.py`.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import logging
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.match.repositories import modelos
from app.match.repositories.contexto import (
    ContextoDeEmpresa,
    ContextoDeSistema,
    OperacionDeSistema,
    Origen,
    SinContexto,
)
from app.match.repositories.match_repo import (
    OPERACIONES_DE_SISTEMA,
    RepositorioDeMatch,
    RepositorioDeSistema,
)
from app.match.services.listado import LOG_DEL_LISTADO, ORDEN_POR_FECHA
from app.plataforma.sesion import ContextoEmpresa
from tests.match.conftest import (
    EmpresaDePrueba,
    Entrar,
    SesionDeSoporte,
    rutas_de_match,
    sembrar_score,
)
from tests.match.test_andamio import MODULOS_DE_MATCH as MODULOS_DEL_MAPA

RAIZ = Path(__file__).resolve().parents[2]
APP = RAIZ / "app"
MATCH = APP / "match"
REPOSITORIOS = MATCH / "repositories"
MIGRACIONES = RAIZ / "migrations"
FACHADA = "app.match.fachada"

# La regla (a) detecta **DML**: `select`/`insert`/`update`/`delete`, `text()` y
# `execute` con SQL crudo. El DDL de Alembic (`op.*`) queda fuera por ruta y por
# naturaleza (R6·I3): una migración no es una consulta de negocio y es el único
# sitio donde estas tablas se crean.
DML = frozenset({"select", "insert", "update", "delete", "text", "execute"})
MODELOS = tuple(
    nombre
    for nombre, valor in vars(modelos).items()
    if isinstance(valor, type) and getattr(valor, "__tablename__", "").startswith("match_")
)
PATRON_DE_MATCH = re.compile("|".join(("match_[a-z_]+", *MODELOS)))


def _contexto_de(empresa: EmpresaDePrueba, es_soporte: bool = False) -> ContextoDeEmpresa:
    """El contexto que una ruta construiría desde la cookie (`ContextoEmpresa`)."""
    return ContextoDeEmpresa.desde_la_peticion(
        ContextoEmpresa(empresa_id=empresa.empresa.id, es_soporte=es_soporte)
    )


def _archivos_python() -> list[Path]:
    """Toda la aplicación, también `tests/` y `migrations/`, menos el repositorio."""
    return [
        a for a in RAIZ.rglob("*.py") if ".venv" not in a.parts and REPOSITORIOS not in a.parents
    ]


def _dml_de_match(ruta: Path) -> list[str]:
    fuente = ruta.read_text(encoding="utf-8")
    es_migracion = MIGRACIONES in ruta.parents
    hallados: list[str] = []
    for nodo in ast.walk(ast.parse(fuente)):
        if not isinstance(nodo, ast.Call):
            continue
        destino = nodo.func
        atributo = isinstance(destino, ast.Attribute)
        nombre = destino.attr if atributo else getattr(destino, "id", "")
        if nombre not in DML:
            continue
        if es_migracion and atributo and getattr(destino.value, "id", "") == "op":  # type: ignore[union-attr]
            continue
        trozo = ast.get_source_segment(fuente, nodo) or ""
        if PATRON_DE_MATCH.search(trozo):
            hallados.append(f"{ruta.relative_to(RAIZ)}:{nodo.lineno}: {trozo.splitlines()[0]}")
    return hallados


def _imports_de_match(ruta: Path) -> set[str]:
    encontrados: set[str] = set()
    for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            encontrados |= {a.name for a in nodo.names if a.name.startswith("app.match")}
        elif isinstance(nodo, ast.ImportFrom) and (nodo.module or "").startswith("app.match"):
            if nodo.module == "app.match":
                encontrados |= {f"app.match.{a.name}" for a in nodo.names}
            else:
                encontrados.add(str(nodo.module))
    return encontrados


def _firmas_publicas_de_match() -> list[tuple[str, inspect.Signature]]:
    """Funciones y métodos **públicos** de los módulos del mapa de §2.

    Los nombres privados quedan fuera, y con ellos el `__init__` de los contextos
    tipados: ahí el entero entra **una vez**, desde la fila o desde la cookie. Es
    una exclusión por nombre, no una lista de funciones.
    """
    firmas: list[tuple[str, inspect.Signature]] = []
    for nombre_modulo in MODULOS_DEL_MAPA:
        modulo = importlib.import_module(nombre_modulo)
        for nombre, objeto in vars(modulo).items():
            if nombre.startswith("_") or getattr(objeto, "__module__", "") != nombre_modulo:
                continue
            if inspect.isclass(objeto):
                publicos = [m for m in vars(objeto) if not m.startswith("_")]
                for metodo in publicos:
                    valor = getattr(objeto, metodo)
                    if callable(valor):
                        firmas.append((f"{nombre}.{metodo}", inspect.signature(valor)))
            elif inspect.isfunction(objeto):
                firmas.append((f"{nombre_modulo}.{nombre}", inspect.signature(objeto)))
    return firmas


# --- 1 · el repositorio exige contexto -------------------------------------


def test_el_repositorio_no_se_puede_construir_sin_contexto_de_empresa(sesion: Session) -> None:
    """Error, **no valor por omisión** (D4, `docs/arquitectura.md` §4)."""
    contexto = inspect.signature(RepositorioDeMatch).parameters["contexto"]
    assert contexto.default is inspect.Parameter.empty, "el contexto tiene valor por omisión"
    with pytest.raises(SinContexto):
        RepositorioDeMatch(sesion, None)  # type: ignore[arg-type]
    with pytest.raises(SinContexto):
        ContextoDeEmpresa.desde_la_vacante(sesion, 0)


# --- 2 · la enumeración, sobre toda la aplicación ---------------------------


def test_ninguna_consulta_de_match_se_construye_fuera_del_repositorio() -> None:
    """Regla (a), sin lista blanca (CA1 segunda mitad, F4, R2·I3, R6·I3)."""
    archivos = _archivos_python()
    assert len(archivos) > 20, f"la enumeración no está mirando la aplicación: {len(archivos)}"
    sueltas = [hallado for archivo in archivos for hallado in _dml_de_match(archivo)]
    assert sueltas == [], "DML sobre `match_*` fuera de app/match/repositories/:\n" + "\n".join(
        sueltas
    )


def test_desde_la_plataforma_el_unico_import_de_match_es_la_fachada() -> None:
    """Regla (b): superficie cerrada por naturaleza, no por lista de llamadores.

    `migrations/` y `tests/` quedan fuera **por ruta**: Alembic necesita la
    metadata y los tests prueban internos (R3·I1).
    """
    prohibidos = {
        str(ruta.relative_to(RAIZ)): sorted(_imports_de_match(ruta) - {FACHADA})
        for ruta in sorted(APP.rglob("*.py"))
        if MATCH not in ruta.parents and _imports_de_match(ruta) - {FACHADA}
    }
    assert prohibidos == {}, f"importan internos de Match en vez de la fachada: {prohibidos}"


# --- 3 · dos empresas sembradas --------------------------------------------


def test_una_consulta_con_dos_empresas_devuelve_filas_de_una_sola(
    sesion: Session, northstar: EmpresaDePrueba, meridian: EmpresaDePrueba
) -> None:
    for empresa in (northstar, meridian):
        repo = RepositorioDeMatch(
            sesion, ContextoDeEmpresa.desde_la_vacante(sesion, empresa.vacante.id)
        )
        repo.guardar_score(empresa.candidato.id, empresa.vacante.id, 70, ["sintética"])
    northstar_repo = RepositorioDeMatch(sesion, _contexto_de(northstar))
    assert [s.empresa_id for s in northstar_repo.scores()] == [northstar.empresa.id]
    assert northstar_repo.score(meridian.candidato.id, meridian.vacante.id) is None


# --- 4 · el contexto de sistema, enumerado ---------------------------------


def test_el_contexto_de_sistema_habilita_tres_operaciones_y_ninguna_lee_scores(
    sesion: Session, northstar: EmpresaDePrueba
) -> None:
    """Las **tres** de I1: tomar trabajo, reconciliar y el gasto. Ni una cuarta."""
    assert len(OperacionDeSistema) == 3
    assert set(OPERACIONES_DE_SISTEMA) == set(OperacionDeSistema)
    publicas = {m for m in vars(RepositorioDeSistema) if not m.startswith("_")}
    assert publicas == set(OPERACIONES_DE_SISTEMA.values())
    assert [m for m in publicas if "score" in m or "razon" in m or "candidato" in m] == []

    sistema = ContextoDeSistema(OperacionDeSistema.TOMAR_TRABAJO)
    with pytest.raises(SinContexto):
        RepositorioDeMatch(sesion, sistema)  # type: ignore[arg-type]

    # El camino de la cola: la empresa sale de la fila del trabajo **ya tomada**
    # (F5, `docs/arquitectura.md` §5.3), no de un argumento.
    repo = RepositorioDeMatch(sesion, _contexto_de(northstar))
    trabajo = repo.crear_trabajo(northstar.candidato.id, northstar.vacante.id, "k1")
    tomado = RepositorioDeSistema(sesion, sistema).siguiente_trabajo_pendiente()
    assert tomado is not None and tomado.id == trabajo.id
    desde_el_trabajo = ContextoDeEmpresa.desde_el_trabajo(sesion, tomado.id)
    assert (desde_el_trabajo.empresa_id, desde_el_trabajo.origen) == (
        northstar.empresa.id,
        Origen.TRABAJO,
    )


# --- 5 · el contexto de soporte -------------------------------------------


def test_el_contexto_de_soporte_de_northstar_no_ve_nada_de_meridian(
    sesion: Session,
    aplicacion: FastAPI,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    sesion_soporte: SesionDeSoporte,
) -> None:
    """D6, CA17, R2·I1 · el mecanismo es el de la plataforma (hecho 3 de PR-01)."""
    cliente = sesion_soporte(northstar)  # POST /entrar con el slug: el camino real
    assert cliente.get(f"/vacantes/{northstar.vacante.id}").status_code == 200
    assert cliente.get(f"/vacantes/{meridian.vacante.id}").status_code == 404

    # Y la empresa del staff **nunca** viene de la URL. PR-05 trae la enumeración
    # de rutas de verdad —`app.routes` sola no ve los routers incluidos—, así que
    # esta aserción, que nació vacía, ya muerde.
    rutas = rutas_de_match(aplicacion)
    assert rutas and [r for r in rutas if "empresa" in r] == []

    soporte = _contexto_de(northstar, es_soporte=True)
    assert (soporte.es_soporte, soporte.origen) == (True, Origen.PETICION)
    repo = RepositorioDeMatch(sesion, soporte)
    with pytest.raises(SinContexto):
        repo.candidatos_de_vacante(meridian.vacante.id)
    assert repo.scores() == []


# --- 6 · desde la vacante, y ningún `empresa_id` entero --------------------


def test_desde_la_vacante_con_un_candidato_de_otra_empresa_falla_y_deja_cero_filas(
    sesion: Session, northstar: EmpresaDePrueba, meridian: EmpresaDePrueba
) -> None:
    with pytest.raises(SinContexto):
        ContextoDeEmpresa.desde_la_vacante(
            sesion, northstar.vacante.id, candidato_id=meridian.candidato.id
        )
    repo = RepositorioDeMatch(sesion, _contexto_de(northstar))
    with pytest.raises(SinContexto):
        repo.guardar_score(meridian.candidato.id, northstar.vacante.id, 70, [])
    # «Cero filas» **por empresa**, sobre las dos de la fixture (R6·I3).
    assert repo.scores() == []
    assert RepositorioDeMatch(sesion, _contexto_de(meridian)).scores() == []


def test_ninguna_funcion_de_match_acepta_un_empresa_id_entero() -> None:
    """Solo contextos tipados: el entero suelto es el argumento que se omite."""
    firmas = _firmas_publicas_de_match()
    assert len(firmas) > 10, f"el recorrido de firmas no está mirando Match: {len(firmas)}"
    enteros = [
        f"{nombre}({parametro.name}: {parametro.annotation})"
        for nombre, firma in firmas
        for parametro in firma.parameters.values()
        if "empresa" in parametro.name and str(parametro.annotation).startswith("int")
    ]
    assert enteros == [], f"`empresa_id` como argumento de llamador: {enteros}"


# --- 7 · desde el candidato (el contexto que PR-18 necesita) ---------------


def test_desde_el_candidato_solo_ve_lo_de_su_empresa(
    sesion: Session, northstar: EmpresaDePrueba, meridian: EmpresaDePrueba
) -> None:
    contexto = ContextoDeEmpresa.desde_el_candidato(sesion, northstar.candidato.id)
    assert (contexto.empresa_id, contexto.origen) == (northstar.empresa.id, Origen.CANDIDATO)
    repo = RepositorioDeMatch(sesion, contexto)
    repo.guardar_score(northstar.candidato.id, northstar.vacante.id, 61, ["sintética"])
    assert [s.candidato_id for s in repo.scores()] == [northstar.candidato.id]
    # Enumerar candidatos es una lectura **con empresa**, no una cuarta operación
    # de sistema (R4·M3): PR-16 la usa para el comando y para la cobertura.
    assert repo.candidatos_de_vacante(northstar.vacante.id) == [northstar.candidato.id]
    with pytest.raises(SinContexto):
        repo.candidatos_de_vacante(meridian.vacante.id)
    with pytest.raises(SinContexto):
        ContextoDeEmpresa.desde_el_candidato(sesion, 0)


# ===========================================================================
# PR-05 · la segunda mitad: el recorrido de rutas y el log
# ===========================================================================

# Lo único que la línea de log puede llevar (`docs/arquitectura.md` §2 y §3 paso
# 6). Es un conjunto cerrado a propósito: añadir un campo del candidato es rojo.
CAMPOS_DEL_LOG = frozenset(
    {"evento", "request_id", "empresa_id", "vacante_id", "orden", "con_score", "filas", "ms"}
)


def test_todo_endpoint_de_match_con_sesion_de_otra_empresa_responde_404(
    sesion: Session,
    aplicacion: FastAPI,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    entrar: Entrar,
    sesion_soporte: SesionDeSoporte,
) -> None:
    """CA1 · **404, nunca un 200 parcial**, en todos los endpoints de Match.

    Las rutas se **enumeran** (F34), así que el endpoint que PR-20 añada entra en
    este recorrido sin tocar el test. Y el mismo recorrido con una sesión de
    **staff en contexto de soporte de Northstar** pidiendo IDs de Meridian (R2·I1).
    """
    rutas = rutas_de_match(aplicacion)
    assert rutas, "no hay ninguna ruta de Match que recorrer: el 403 de CA18 sería vacío"
    assert [r for r in rutas if "empresa" in r] == [], "una ruta de Match toma la empresa de la URL"

    sembrar_score(sesion, northstar)
    de_meridian = entrar(meridian.reclutador)
    for ruta in rutas:
        respuesta = de_meridian.get(ruta.format(vacante_id=northstar.vacante.id))
        assert respuesta.status_code == 404, f"{ruta} con sesión de otra empresa"
        assert northstar.candidato.correo not in respuesta.text

    # La vista de la plataforma, que es por donde se llega a la lista (hecho 4).
    vista = de_meridian.get(f"/vacantes/{northstar.vacante.id}")
    assert vista.status_code == 404 and northstar.candidato.correo not in vista.text

    soporte = sesion_soporte(northstar)
    for ruta in rutas:
        respuesta = soporte.get(ruta.format(vacante_id=meridian.vacante.id))
        assert respuesta.status_code == 404, f"{ruta} con contexto de soporte de otra empresa"
        assert meridian.candidato.correo not in respuesta.text


def test_la_empresa_sin_anexo_ve_su_lista_entera_y_sin_nada_de_match(
    sesion: Session, meridian: EmpresaDePrueba, entrar: Entrar
) -> None:
    """CA3, D7 · Meridian abre su vacante: 200 con la lista de hoy y sin score.

    La comprobación que hace `encolar` —no llamar al proveedor— es de PR-10;
    ésta es la de la vista, que es la que Meridian ve el 15-ene.
    """
    sembrar_score(sesion, meridian, 88)
    respuesta = entrar(meridian.reclutador).get(f"/vacantes/{meridian.vacante.id}")
    assert respuesta.status_code == 200
    assert meridian.candidato.correo in respuesta.text
    assert 'data-testid="score"' not in respuesta.text


def test_la_linea_de_log_lleva_la_empresa_de_quien_pidio_y_nada_del_candidato(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    entrar: Entrar,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """CA1, la mitad «ni log suyo» (R6·M6).

    `docs/arquitectura.md` §2 describe una línea JSON con `request_id` y
    `empresa_id`; ningún paso de la Etapa 0 la emitía, así que esta mitad del
    criterio no tenía sobre qué asertar.
    """
    sembrar_score(sesion, northstar)
    with caplog.at_level(logging.INFO, logger=LOG_DEL_LISTADO):
        peticion = entrar(meridian.reclutador).get(f"/vacantes/{meridian.vacante.id}")
    assert peticion.status_code == 200

    lineas = [json.loads(r.getMessage()) for r in caplog.records if r.name == LOG_DEL_LISTADO]
    assert lineas, "`listar_vacante` no emitió ninguna línea de log"
    for linea in lineas:
        assert set(linea) == CAMPOS_DEL_LOG, "la línea de log lleva campos que no declara"
        assert linea["empresa_id"] == meridian.empresa.id
        assert linea["vacante_id"] == meridian.vacante.id
        assert linea["orden"] == ORDEN_POR_FECHA

    crudo = "\n".join(registro.getMessage() for registro in caplog.records)
    assert "candidato" not in crudo, "el log nombra al candidato"
    assert northstar.candidato.correo not in crudo
    assert [li for li in lineas if li["empresa_id"] == northstar.empresa.id] == []
