"""PR-01 · el andamio de Match.

Esto no prueba conducta de Match: Match todavía no hace nada. Prueba que existe
**dónde escribirlo** y **cómo correr los tests**, que es el objetivo del paso:

- la app se crea y el router de Match está montado por la fachada;
- la fachada expone una superficie **cerrada** (PLAN.md §2, R3·I1);
- los paquetes de §2 existen y se importan;
- la base de datos de test levanta y se revierte entre tests.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.match import fachada
from app.plataforma.modelos import Empresa

# Los paquetes y módulos del mapa de archivos de PLAN.md §2.
MODULOS_DE_MATCH = (
    "app.match",
    "app.match.fachada",
    "app.match.configuracion",
    "app.match.routers",
    "app.match.routers.vacante",
    "app.match.services",
    "app.match.services.listado",
    "app.match.services.scoring",
    "app.match.services.pseudonimizador",
    "app.match.services.gasto",
    "app.match.services.recalculo",
    "app.match.repositories",
    "app.match.repositories.contexto",
    "app.match.repositories.match_repo",
    "app.match.repositories.modelos",
    "app.match.proveedor",
    "app.match.proveedor.payload",
    "app.match.proveedor.cliente",
    "app.match.proveedor.mock",
    "app.match.cola",
    "app.match.cola.trabajos",
    "app.match.cola.ejecutor",
    "app.match.comandos",
    "app.match.comandos.carga_inicial",
    "app.match.comandos.cobertura",
    "app.match.borrado",
    "app.match.borrado.inventario",
    "app.match.borrado.borrar_candidato",
)

# La superficie cerrada de la fachada. El cuarto símbolo lo añadió **PR-05** al
# tomar la opción (b) de R3·I2: la vista de la plataforma delega el listado.
SUPERFICIE_DE_LA_FACHADA = ("borrar_candidato", "encolar", "listar_vacante", "montar")


def test_la_app_se_crea(aplicacion: FastAPI) -> None:
    assert isinstance(aplicacion, FastAPI)


def test_el_router_de_match_esta_montado(aplicacion: FastAPI) -> None:
    """La factoría monta Match por la fachada, y la fachada lo deja declarado."""
    assert aplicacion.state.match_montado is True


def test_una_ruta_inexistente_de_match_responde_404(cliente: TestClient) -> None:
    assert cliente.get("/match/no-existe").status_code == 404


@pytest.mark.parametrize("nombre", MODULOS_DE_MATCH)
def test_el_modulo_del_mapa_de_archivos_existe(nombre: str) -> None:
    assert importlib.import_module(nombre) is not None


def test_la_fachada_expone_una_superficie_cerrada() -> None:
    """Lo único importable desde fuera de `app/match/` (PLAN.md §2, PR-04 regla b)."""
    assert tuple(sorted(fachada.__all__)) == SUPERFICIE_DE_LA_FACHADA


def _modulos_de_match_importados(ruta: Path) -> set[str]:
    """Los módulos `app.match.*` que un archivo importa, leídos del árbol sintáctico.

    Mirar `vars()` del módulo ya importado no sirve: `from app.match.routers.vacante
    import router` deja un `APIRouter` sin rastro del módulo de origen.
    """
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    encontrados: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            encontrados |= {a.name for a in nodo.names if a.name.startswith("app.match")}
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            if nodo.module == "app.match":
                encontrados |= {f"app.match.{a.name}" for a in nodo.names}
            elif nodo.module.startswith("app.match"):
                encontrados.add(nodo.module)
    return encontrados


def test_la_plataforma_solo_importa_la_fachada_de_match() -> None:
    """La factoría monta Match por la fachada y no importa ningún interno.

    Es la precondición de la regla (b) del test de enumeración de PR-04: si la
    factoría importara `app.match.routers`, ese test nacería rojo y la salida
    fácil sería la lista blanca que existe para no tener (§2, R3·I1).
    """
    fabrica = Path(importlib.import_module("app.fabrica").__file__ or "")
    assert _modulos_de_match_importados(fabrica) == {"app.match.fachada"}


def test_la_base_de_test_no_es_la_de_desarrollo(url_bd_test: str) -> None:
    from app.configuracion import ajustes

    assert url_bd_test != ajustes().url_bd
    assert url_bd_test.endswith("_test")


def test_la_base_de_test_levanta_con_el_esquema_aplicado(sesion: Session) -> None:
    assert sesion.scalar(select(func.count()).select_from(Empresa)) == 0


# Los dos de abajo van en pareja y en este orden: el primero escribe, el segundo
# comprueba que la reversión se llevó lo escrito. Si se invierten, no prueban nada.


def test_1_escribe_una_empresa(sesion: Session) -> None:
    sesion.add(Empresa(nombre="Empresa de prueba", slug="empresa-de-prueba"))
    sesion.commit()  # un commit del código bajo prueba cae en un savepoint
    assert sesion.scalar(select(func.count()).select_from(Empresa)) == 1


def test_2_la_transaccion_del_test_anterior_se_revirtio(sesion: Session) -> None:
    assert sesion.scalar(select(func.count()).select_from(Empresa)) == 0
