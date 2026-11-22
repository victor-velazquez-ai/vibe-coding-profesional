"""PR-02 · el esquema de Match y su inventario de borrado.

Esto no prueba conducta de scoring: prueba **el esquema y su inventario**, que es
el control de F13 y F25 y la segunda mitad de CA16. Toda tabla que creen las
migraciones tiene entrada en el inventario —**también las que no guardan nada del
candidato**, R6·M7—, las razones están declaradas como dato del candidato (F25),
las migraciones van y vuelven, y **ninguna clave ajena declara `ON DELETE
CASCADE`** (R3·M2): con cascada, el borrado de la plataforma se lleva las tablas
de Match antes del gancho de PR-18 y CA16 queda verde sola.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from sqlalchemy import Engine, inspect

from app.match.borrado import inventario
from app.migracion import aplicar_migraciones, revertir_migraciones

RAIZ = Path(__file__).resolve().parents[2]
MIGRACIONES = RAIZ / "migrations" / "versions"
DOCUMENTO = RAIZ / "docs" / "inventario-borrado.md"
PLATAFORMA = "0000_plataforma"  # la revisión anterior a la de Match


def _migraciones_de_match() -> list[Path]:
    return sorted(MIGRACIONES.glob("*_match_*.py"))


def _tablas_creadas_por_las_migraciones() -> set[str]:
    """Las tablas de `op.create_table("…")`, leídas del árbol sintáctico.

    Enumerar la base por el prefijo `match_` no bastaría: una tabla de Match con
    otro nombre sería invisible aquí, y F13 es exactamente eso.
    """
    tablas: set[str] = set()
    for archivo in _migraciones_de_match():
        for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
            if not (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)):
                continue
            if nodo.func.attr != "create_table" or not nodo.args:
                continue
            if isinstance(nodo.args[0], ast.Constant):
                tablas.add(str(nodo.args[0].value))
    return tablas


# En tiempo de colección: así cada tabla es un caso con nombre propio en la salida.
TABLAS_DE_LAS_MIGRACIONES = sorted(_tablas_creadas_por_las_migraciones())


@pytest.fixture(scope="module")
def tablas_en_la_base(motor_test: Engine) -> set[str]:
    return {t for t in inspect(motor_test).get_table_names() if t.startswith("match_")}


@pytest.mark.parametrize("tabla", TABLAS_DE_LAS_MIGRACIONES)
def test_cada_tabla_que_crea_una_migracion_esta_en_el_inventario(
    tabla: str, motor_test: Engine
) -> None:
    """F13, CA16 segunda mitad. Sin exclusiones: también las tablas sin datos del candidato."""
    entrada = inventario.entrada(tabla)
    assert entrada is not None, (
        f"La migración crea `{tabla}` y no está en el inventario de borrado. "
        "Si no guarda nada del candidato, la entrada va igual, con «ninguna» y su razón."
    )
    assert entrada.por_que.strip(), f"La entrada de `{tabla}` no dice por qué"
    # Un inventario que nombra columnas que ya no existen no protege nada:
    reales = {c["name"] for c in inspect(motor_test).get_columns(tabla)}
    assert set(entrada.columnas) <= reales, f"{tabla}: {entrada.columnas} vs {sorted(reales)}"
    # Y CA16 pide el inventario **en el repo**, legible por una persona.
    documento = DOCUMENTO.read_text(encoding="utf-8")
    for nombre in (tabla, *entrada.columnas):
        assert nombre in documento, f"`{nombre}` no está en {DOCUMENTO.name}"


def test_el_inventario_y_la_base_coinciden(tablas_en_la_base: set[str]) -> None:
    """Ni tablas de Match fuera del inventario, ni entradas que ya no existen."""
    assert _migraciones_de_match(), f"Ninguna migración `*_match_*.py` en {MIGRACIONES}"
    assert tablas_en_la_base <= set(inventario.tablas())
    assert set(inventario.tablas()) == set(TABLAS_DE_LAS_MIGRACIONES)


def test_las_razones_estan_declaradas_como_dato_del_candidato() -> None:
    """F25: las razones citan evidencia del CV y viven en la tabla de scores."""
    entrada = inventario.entrada("match_scores")
    assert entrada is not None
    assert "razones" in entrada.columnas


def test_ninguna_clave_ajena_de_match_declara_on_delete_cascade(
    motor_test: Engine, tablas_en_la_base: set[str]
) -> None:
    """R3·M2, en el esquema real y en el texto de la migración.

    Las dos mitades hacen falta: el inspector dice qué hay hoy en la base; el
    texto atrapa el `ondelete="CASCADE"` de una migración que aún no se aplicó.
    """
    inspector = inspect(motor_test)
    for tabla in sorted(tablas_en_la_base):
        for fk in inspector.get_foreign_keys(tabla):
            cascada = (fk.get("options") or {}).get("ondelete")
            assert not cascada, f"{tabla}.{fk['constrained_columns']} declara ON DELETE {cascada}"
    for archivo in _migraciones_de_match():
        declarados = re.findall(r"ondelete\s*=\s*[\"'](\w+)", archivo.read_text(encoding="utf-8"))
        assert not [v for v in declarados if v.upper() == "CASCADE"], (
            f"{archivo.name} declara ON DELETE CASCADE"
        )


def test_las_migraciones_de_match_van_y_vuelven(
    motor_test: Engine, url_bd_test: str, tablas_en_la_base: set[str]
) -> None:
    """`migrate down` y `migrate up` de la 0001, dejando el esquema como estaba.

    Se revierte solo hasta la plataforma: las tablas de negocio no se tocan.
    """
    assert tablas_en_la_base, "No hay ninguna tabla de Match en la base de test"
    try:
        revertir_migraciones(url_bd_test, PLATAFORMA)
        motor_test.dispose()  # las conexiones del pool tienen sentencias preparadas
        tablas = inspect(motor_test).get_table_names()
        assert [t for t in tablas if t.startswith("match_")] == [], "quedaron tablas atrás"
        assert "candidatos" in tablas, "`migrate down` se llevó una tabla de negocio"
    finally:
        aplicar_migraciones(url_bd_test)
        motor_test.dispose()

    vueltas = {t for t in inspect(motor_test).get_table_names() if t.startswith("match_")}
    assert vueltas == tablas_en_la_base
