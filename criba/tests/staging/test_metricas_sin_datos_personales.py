"""Staging · el esquema `metricas` y sus dos vistas agregadas, sin datos personales.

Siete criterios, uno por test:

1. la migración nueva crea el esquema `metricas` con **las dos vistas** y ninguna
   tabla;
2. `metricas.scores_por_vacante` expone **exactamente** sus siete columnas;
3. `metricas.trabajos_por_estado` expone **exactamente** sus cinco columnas;
4. **ninguna columna de las vistas es un dato del candidato ni un identificador
   suyo**, y ninguna de las dos **lee** un dato suyo (CA2, CA16, D15, F12, y lo
   que `docs/arquitectura.md` §2 permite que salga de Criba: `request_id`,
   `empresa_id`, decisión, latencia y versiones — nada del candidato);
5. los conteos de scores cuadran con las filas sembradas, **con la fila de score
   0 y la fila sin score** dentro;
6. los conteos de trabajos cuadran por día, estado y motivo, y el día es el de
   `creado_en`;
7. **las vistas no mezclan empresas**: lo de Northstar no entra en el agregado de
   Meridian ni al contrario.

Y uno más, el octavo, que no es de privacidad sino de operación: la migración va
y vuelve sobre la base de test, como exige el test 3 de PR-02 para la 0001.

**Qué lectura de `n_con_score` fija este archivo, porque el contrato admite dos.**
Aquí `n_con_score` cuenta **todas** las filas con score —el `0` incluido—,
`n_score_cero` es el desglose de cuántas de ellas son cero, y `score_promedio` es
el promedio de las mismas filas que `n_con_score` cuenta. Con los números
sembrados (80, 40, 0 y una sin score) la otra lectura posible —«con score» como
«con score distinto de cero»— daría 2 y 60.0, así que el test distingue las dos y
deja la elección escrita en un sitio.

Todo el material es **sintético** (D3 modificado, D15, F12).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.match.conftest import EmpresaDePrueba
from tests.staging.conftest import (
    COLUMNAS_DE_SCORES,
    COLUMNAS_DE_TRABAJOS,
    DATOS_DEL_CANDIDATO,
    DIA_DE_AYER,
    DIA_DE_HOY,
    ESQUEMA,
    IDENTIFICADORES_DEL_CANDIDATO,
    MOMENTO_DE_AYER,
    MOMENTO_DE_HOY,
    MOTIVO_DE_ERROR,
    VISTA_SCORES,
    VISTA_TRABAJOS,
    VISTAS,
    agregado_de_scores,
    agregado_de_trabajos,
    columnas_de,
    definicion_de,
    empresas_en_la_vista,
    esquemas,
    exigir_la_vista,
    reaplicar_la_migracion_de_metricas,
    relaciones_de_metricas,
    sembrar_scores,
    sembrar_trabajos,
)

# 80, 40 y 0 promedian **40 exacto**, así que el promedio se puede comparar sin
# tolerancia; y el 0 y el `None` son los dos casos que un conteo mal escrito
# confunde entre sí (CA13: un «sin score» nunca se muestra como cero).
PUNTOS_DE_HOY = (80, 40, 0, None)
PUNTOS_DE_AYER = (60,)
PUNTOS_DE_MERIDIAN = (55,)

# El trabajo con error nace **ayer** y se marca hoy: así una vista que agrupara
# por `actualizado_en` en vez de por `creado_en` lo contaría en el día de hoy.
TRABAJOS_DE_HOY = (("pendiente", None), ("pendiente", None), ("listo", None))
TRABAJOS_DE_AYER = (("error", MOTIVO_DE_ERROR),)


# --- 1 · el esquema y las dos vistas ----------------------------------------


def test_la_migracion_crea_el_esquema_metricas_con_las_dos_vistas_agregadas(
    sesion: Session,
) -> None:
    """Las dos vistas, y **ninguna tabla**: una copia de las filas no es un agregado."""
    assert ESQUEMA in esquemas(sesion), (
        f"no existe el esquema {ESQUEMA}: lo crea la migración nueva del staging"
    )

    relaciones = relaciones_de_metricas(sesion)
    assert sorted(relaciones) == sorted(VISTAS)
    assert set(relaciones.values()) <= {"v", "m"}, (
        f"en {ESQUEMA} hay algo que no es una vista: {relaciones}"
    )


# --- 2 y 3 · las columnas, exactamente las del contrato ---------------------


def test_scores_por_vacante_expone_exactamente_las_siete_columnas_del_contrato(
    sesion: Session,
) -> None:
    exigir_la_vista(sesion, VISTA_SCORES)
    assert tuple(columnas_de(sesion, VISTA_SCORES)) == COLUMNAS_DE_SCORES


def test_trabajos_por_estado_expone_exactamente_las_cinco_columnas_del_contrato(
    sesion: Session,
) -> None:
    exigir_la_vista(sesion, VISTA_TRABAJOS)
    assert tuple(columnas_de(sesion, VISTA_TRABAJOS)) == COLUMNAS_DE_TRABAJOS


# --- 4 · ni una columna ni una lectura con dato del candidato ---------------


@pytest.mark.parametrize("vista", VISTAS)
def test_ninguna_vista_expone_ni_lee_un_dato_del_candidato(sesion: Session, vista: str) -> None:
    """Las dos mitades del criterio, porque la primera sola no basta.

    Una vista puede llamar `n` a una columna y meter dentro el nombre del
    candidato, así que además de los **nombres** se mira **lo que la vista lee**
    (`pg_get_viewdef`): ni `nombre`, ni `correo`, ni `telefono`, ni `links`, ni
    texto de CV, ni razones, ni hash del CV.

    Lo que sí se admite en la definición es `candidato_id` **dentro de un
    agregado** —un `count(DISTINCT …)` no expone a nadie—; lo que no se admite es
    que salga como columna, y de eso se encarga la primera mitad.
    """
    exigir_la_vista(sesion, vista)

    columnas = columnas_de(sesion, vista)
    for columna in columnas:
        prohibidos = [
            dato
            for dato in (*DATOS_DEL_CANDIDATO, *IDENTIFICADORES_DEL_CANDIDATO)
            if dato in columna.lower()
        ]
        assert prohibidos == [], (
            f"{ESQUEMA}.{vista} expone la columna {columna!r}, que es dato o identificador "
            f"del candidato ({prohibidos})"
        )

    definicion = definicion_de(sesion, vista).lower()
    leidos = [dato for dato in DATOS_DEL_CANDIDATO if dato in definicion]
    assert leidos == [], f"la definición de {ESQUEMA}.{vista} lee datos del candidato: {leidos}"


# --- 5 · los conteos de scores, con el cero y el sin score ------------------


def test_los_conteos_de_scores_por_vacante_cuadran_con_las_filas_sembradas(
    sesion: Session, northstar: EmpresaDePrueba
) -> None:
    """Cuatro filas hoy —80, 40, 0 y una sin score— y una de ayer, agrupadas por día.

    `n_con_score` cuenta las tres con score (el 0 es un score), `n_score_cero`
    una, `n_sin_score` una y el promedio es (80 + 40 + 0) / 3 = 40.
    """
    sembrar_scores(sesion, northstar, PUNTOS_DE_HOY, MOMENTO_DE_HOY)
    sembrar_scores(sesion, northstar, PUNTOS_DE_AYER, MOMENTO_DE_AYER)
    exigir_la_vista(sesion, VISTA_SCORES)

    empresa_id, vacante_id = northstar.empresa.id, northstar.vacante.id
    assert agregado_de_scores(sesion, empresa_id) == [
        (empresa_id, vacante_id, DIA_DE_AYER, 1, 0, 0, 60.0),
        (empresa_id, vacante_id, DIA_DE_HOY, 3, 1, 1, 40.0),
    ]


# --- 6 · los conteos de trabajos, por día, estado y motivo ------------------


def test_los_conteos_de_trabajos_por_estado_cuadran_con_las_filas_sembradas(
    sesion: Session, northstar: EmpresaDePrueba
) -> None:
    """Tres trabajos de hoy y el que falló ayer, con su motivo y su día de creación."""
    sembrar_trabajos(sesion, northstar, TRABAJOS_DE_HOY, MOMENTO_DE_HOY)
    sembrar_trabajos(sesion, northstar, TRABAJOS_DE_AYER, MOMENTO_DE_AYER)
    exigir_la_vista(sesion, VISTA_TRABAJOS)

    empresa_id = northstar.empresa.id
    assert agregado_de_trabajos(sesion, empresa_id) == [
        (empresa_id, DIA_DE_AYER, "error", MOTIVO_DE_ERROR, 1),
        (empresa_id, DIA_DE_HOY, "listo", None, 1),
        (empresa_id, DIA_DE_HOY, "pendiente", None, 2),
    ]


# --- 7 · multiempresa: ningún agregado cruza de empresa ---------------------


def test_las_vistas_no_mezclan_empresas_ni_en_un_sentido_ni_en_el_otro(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    activar_match: Callable[[str], None],
) -> None:
    """El requisito número uno del cliente, en las vistas del agente (D4, CA1).

    Meridian se **activa a propósito** para que su fila sea legítima (igual que
    `test_camino_escritura.py` hace con F5): sin dos empresas con datos de Match
    no se puede medir que el agregado no cruce. Y con el agregado mezclado los
    números no cuadrarían en ninguno de los dos lados, que es lo que se asercia.
    """
    activar_match(meridian.slug)

    sembrar_scores(sesion, northstar, PUNTOS_DE_HOY, MOMENTO_DE_HOY)
    sembrar_trabajos(sesion, northstar, TRABAJOS_DE_HOY, MOMENTO_DE_HOY)
    sembrar_scores(sesion, meridian, PUNTOS_DE_MERIDIAN, MOMENTO_DE_HOY)
    sembrar_trabajos(sesion, meridian, TRABAJOS_DE_AYER, MOMENTO_DE_AYER)
    for vista in VISTAS:
        exigir_la_vista(sesion, vista)

    de_northstar, de_meridian = northstar.empresa.id, meridian.empresa.id
    assert agregado_de_scores(sesion, de_northstar) == [
        (de_northstar, northstar.vacante.id, DIA_DE_HOY, 3, 1, 1, 40.0)
    ]
    assert agregado_de_scores(sesion, de_meridian) == [
        (de_meridian, meridian.vacante.id, DIA_DE_HOY, 1, 0, 0, 55.0)
    ]
    assert agregado_de_trabajos(sesion, de_northstar) == [
        (de_northstar, DIA_DE_HOY, "listo", None, 1),
        (de_northstar, DIA_DE_HOY, "pendiente", None, 2),
    ]
    assert agregado_de_trabajos(sesion, de_meridian) == [
        (de_meridian, DIA_DE_AYER, "error", MOTIVO_DE_ERROR, 1)
    ]
    for vista in VISTAS:
        assert empresas_en_la_vista(sesion, vista) == {de_northstar, de_meridian}


# --- 8 · la migración va y vuelve -------------------------------------------


def test_la_migracion_de_metricas_va_y_vuelve_sobre_la_base_de_test(
    motor_test: Engine, url_bd_test: str
) -> None:
    """Como el test 3 de PR-02 para la 0001: `downgrade` y `upgrade`, **dos veces**.

    No es cosmético: el `downgrade` es lo que deja volver atrás un despliegue de
    staging sin borrar la base, y una vista olvidada en el `downgrade` convierte
    el segundo `upgrade` en un «ya existe». Por eso la vuelta se da dos veces y
    después se comprueba que las dos vistas siguen ahí.

    No pide la fixture `sesion` a propósito: el `downgrade` quita las vistas y no
    puede cruzarse con una transacción que las tenga tomadas.
    """
    reaplicar_la_migracion_de_metricas(url_bd_test)
    reaplicar_la_migracion_de_metricas(url_bd_test)

    with Session(motor_test) as nueva:
        assert sorted(relaciones_de_metricas(nueva)) == sorted(VISTAS)
