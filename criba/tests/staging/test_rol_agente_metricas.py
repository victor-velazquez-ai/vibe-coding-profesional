"""Staging · el rol del agente en producción: `agente_metricas`.

El agente que mira las métricas en producción entra con **su propio rol de base
de datos**, no con el usuario de la aplicación. Cinco criterios, uno por test:

1. el rol lo crea **`staging/roles.sql`**, un guion del staging, y **ninguna
   migración** lo crea: una migración que crea roles obliga a correr Alembic con
   un superusuario, y los roles son del clúster y no de la base;
2. la migración le da permisos **solo si el rol existe**: sin esa condición,
   `alembic upgrade` falla en cualquier base sin el rol —la de test incluida— y
   nadie puede ni correr la suite;
3. con el rol puesto, **`SELECT` sobre las dos vistas funciona**;
4. con el rol puesto, **`SELECT` sobre `candidatos`, `match_scores`,
   `match_trabajos` y `usuarios` falla** con permiso denegado (CA2, CA16, D15: el
   agente de métricas no tiene por qué poder leer un CV, un score ni un usuario);
5. con el rol puesto, **`INSERT`, `UPDATE` y `DELETE` fallan** en esas cuatro
   tablas: el rol es de lectura de agregados y nada más;
6. el guion del staging es **idempotente**: se corre en cada despliegue.

**Por qué estos tests no piden la fixture `sesion`.** El permiso lo da la
migración y el rol lo crea el guion, así que la preparación vuelve a aplicar la
migración (`reaplicar_la_migracion_de_metricas`), y eso quita y pone las vistas:
no puede cruzarse con una transacción abierta que las tenga tomadas. Leer las
vistas con cero filas ya ejerce el permiso, que es lo que estos criterios miden.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest
from sqlalchemy import Connection, Engine

from tests.staging.conftest import (
    ESQUEMA,
    MIGRACIONES,
    RAIZ,
    ROL,
    ROLES_SQL,
    TABLAS_PROHIBIDAS,
    VISTAS,
    correr_el_guion_de_roles,
    error_al_ejecutar,
    es_permiso_denegado,
    existe_el_rol,
    migracion_de_metricas,
    reaplicar_la_migracion_de_metricas,
)

PATRON_DE_CREAR_ROL = re.compile(r"create\s+role", re.IGNORECASE)
PATRON_DE_GRANT = re.compile(r"\bgrant\b", re.IGNORECASE)
# La única forma de condicionar un `GRANT` a que el rol exista es preguntarle al
# catálogo del clúster. Si la migración no lo nombra, el `GRANT` es incondicional.
PATRON_DE_CONDICION = re.compile(r"pg_roles", re.IGNORECASE)

ESCRITURAS = (
    'INSERT INTO "{tabla}" DEFAULT VALUES',
    'UPDATE "{tabla}" SET empresa_id = empresa_id',
    'DELETE FROM "{tabla}"',
)


# --- 1 · quién crea el rol --------------------------------------------------


def test_el_rol_lo_crea_el_guion_del_staging_y_no_una_migracion() -> None:
    """`staging/roles.sql` crea el rol; ninguna migración lo hace."""
    relativa = ROLES_SQL.relative_to(RAIZ).as_posix()
    assert ROLES_SQL.is_file(), f"falta {relativa}: ahí vive la creación del rol {ROL}"

    guion = ROLES_SQL.read_text(encoding="utf-8")
    assert PATRON_DE_CREAR_ROL.search(guion), f"{relativa} no crea ningún rol"
    assert ROL in guion, f"{relativa} no crea el rol {ROL}"

    culpables = [
        archivo.name
        for archivo in sorted(MIGRACIONES.glob("*.py"))
        if PATRON_DE_CREAR_ROL.search(archivo.read_text(encoding="utf-8"))
    ]
    assert culpables == [], (
        f"estas migraciones crean un rol, y los roles son del clúster: {culpables}. "
        f"El rol {ROL} lo crea {relativa}."
    )


# --- 2 · el permiso, solo si el rol existe ----------------------------------


def test_la_migracion_le_da_permisos_solo_si_el_rol_existe(url_bd_test: str) -> None:
    """El `GRANT` condicionado, y la migración reaplicable sin romperse.

    Las dos mitades del criterio: que la migración **nombre la condición** —un
    `GRANT` incondicional deja `alembic upgrade` roto en toda base sin el rol— y
    que volver a aplicarla no falle con el estado que tenga el clúster. La base
    de test se migra en `tests/conftest.py` **antes** de que el rol exista, así
    que la suite entera es la otra prueba de esta mitad.
    """
    fuente = migracion_de_metricas().read_text(encoding="utf-8")
    assert PATRON_DE_GRANT.search(fuente), (
        "la migración de métricas no da ningún permiso: el rol no podría leer las vistas"
    )
    assert PATRON_DE_CONDICION.search(fuente), (
        f"la migración da el permiso sin comprobar que el rol {ROL} existe (`pg_roles`): "
        "así `alembic upgrade` falla en cualquier base donde el guion del staging no corrió"
    )

    reaplicar_la_migracion_de_metricas(url_bd_test)


# --- 3 · el rol lee las dos vistas -----------------------------------------


def test_con_el_rol_del_agente_se_pueden_leer_las_dos_vistas(
    preparar_el_agente: Callable[[], Connection],
) -> None:
    conexion = preparar_el_agente()
    for vista in VISTAS:
        error = error_al_ejecutar(conexion, f"SELECT * FROM {ESQUEMA}.{vista}")
        assert error == "", f"el rol {ROL} no puede leer {ESQUEMA}.{vista}: {error}"


# --- 4 · el rol no lee las tablas con datos del candidato ------------------


@pytest.mark.parametrize("tabla", TABLAS_PROHIBIDAS)
def test_con_el_rol_del_agente_el_select_a_las_tablas_del_candidato_falla(
    preparar_el_agente: Callable[[], Connection], tabla: str
) -> None:
    """Las cuatro tablas, una por caso: así el rojo dice **cuál** se puede leer."""
    conexion = preparar_el_agente()
    error = error_al_ejecutar(conexion, f'SELECT * FROM "{tabla}"')
    assert es_permiso_denegado(error), (
        f"el rol {ROL} puede leer {tabla}: {error or 'la consulta funcionó'}"
    )


# --- 5 · el rol no escribe en ninguna de ellas -----------------------------


@pytest.mark.parametrize("tabla", TABLAS_PROHIBIDAS)
def test_con_el_rol_del_agente_insertar_actualizar_o_borrar_falla(
    preparar_el_agente: Callable[[], Connection], tabla: str
) -> None:
    """Las tres escrituras sobre cada tabla.

    Cada una va en su `SAVEPOINT` y la transacción se revierte al cerrar la
    conexión, así que ni el caso en que el permiso **esté mal dado** deja nada
    escrito en la base de test.
    """
    conexion = preparar_el_agente()
    for plantilla in ESCRITURAS:
        sentencia = plantilla.format(tabla=tabla)
        error = error_al_ejecutar(conexion, sentencia)
        assert es_permiso_denegado(error), (
            f"el rol {ROL} pudo ejecutar «{sentencia}»: {error or 'sin error'}"
        )


# --- 6 · el guion del staging se puede correr dos veces --------------------


def test_el_guion_del_staging_deja_creado_el_rol_y_es_idempotente(motor_test: Engine) -> None:
    """Correr `staging/roles.sql` dos veces seguidas no puede fallar.

    Es el guion de cada despliegue de staging y Postgres no tiene
    `CREATE ROLE IF NOT EXISTS`: un `CREATE ROLE` a secas revienta la segunda
    vez, y lo que se abandona entonces es el guion, no el despliegue.
    """
    correr_el_guion_de_roles(motor_test)
    assert existe_el_rol(motor_test), f"{ROLES_SQL.name} no dejó creado el rol {ROL}"

    correr_el_guion_de_roles(motor_test)
    assert existe_el_rol(motor_test), f"{ROLES_SQL.name} no se puede correr dos veces"
