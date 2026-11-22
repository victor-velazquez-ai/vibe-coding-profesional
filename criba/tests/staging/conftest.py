"""Andamio de los tests del **staging local con la configuración de producción**.

Tarea de operación de la sección 8: no es un PR de `PLAN.md`, así que no cita CA
ninguno. Lo que fija es el contrato de tres piezas que todavía no existen:

1. una **migración nueva** crea el esquema `metricas` con dos vistas agregadas
   —`metricas.scores_por_vacante` y `metricas.trabajos_por_estado`—, y **ninguna
   de sus columnas es un dato del candidato ni un identificador suyo** (CA2, CA16,
   D15, F12, y la lista de lo que puede salir de Criba de `docs/arquitectura.md`
   §2: `request_id`, `empresa_id`, decisión, latencia y versiones — nada del
   candidato);
2. el rol del agente en producción, **`agente_metricas`**, lo crea
   `staging/roles.sql` —un guion del staging, **no** la migración— y la migración
   solo le da permisos **si el rol existe**;
3. un **E2E de humo contra el staging de verdad**, que se salta sin
   `CRIBA_URL_STAGING` (`tests/staging/test_humo_staging.py`).

**Por qué la preparación del rol es un callable y no una fixture que ya lo deja
listo** (igual que la fixture `cli` de PR-09, `tests/match/conftest.py`): lo que
falla mientras el staging no existe **es la preparación** —no hay
`staging/roles.sql` y no hay migración de métricas—, y un `assert` dentro de una
fixture se lee como un error de montaje. Así el rojo ocurre en el cuerpo del
test, que es donde se lee.

**Por qué estos tests leen las vistas con SQL.** Las vistas de `metricas` no son
un acceso de negocio de Match: no hay método de repositorio que las sirva —ni lo
habrá, porque quien las lee es un agente de producción con su propio rol de base
de datos y sin pasar por la app—. Las filas de `match_scores` y `match_trabajos`
que estos tests siembran **sí** entran por el repositorio (`repo_de`,
`tests/match/conftest.py`), que es lo que la regla (a) de PR-04 exige.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.match.repositories import modelos
from app.migracion import aplicar_migraciones, revertir_migraciones
from app.plataforma.modelos import Candidato
from tests.dobles.proveedor import RAZONES
from tests.match.conftest import (
    EmpresaDePrueba,
    activar_match,
    meridian,
    northstar,
    repo_de,
    sembrar_candidatos,
)

# Las tres fixtures de PR-03 que estos tests reusan, reexportadas para que pytest
# las registre en este directorio. El aislamiento entre empresas se prueba con
# **las mismas** Northstar (Match activo) y Meridian (sin anexo) que el resto de
# la suite: una pareja de empresas inventada aquí probaría otra cosa.
__all__ = ["activar_match", "meridian", "northstar"]

RAIZ = Path(__file__).resolve().parents[2]
ROLES_SQL = RAIZ / "staging" / "roles.sql"
MIGRACIONES = RAIZ / "migrations" / "versions"

ESQUEMA = "metricas"
VISTA_SCORES = "scores_por_vacante"
VISTA_TRABAJOS = "trabajos_por_estado"
VISTAS = (VISTA_SCORES, VISTA_TRABAJOS)
ROL = "agente_metricas"

# Las columnas del contrato, en orden. «Exactamente estas» es la mitad del
# control de privacidad: una columna de más es una fuga que nadie revisó.
COLUMNAS_DE_SCORES = (
    "empresa_id",
    "vacante_id",
    "dia",
    "n_con_score",
    "n_score_cero",
    "n_sin_score",
    "score_promedio",
)
COLUMNAS_DE_TRABAJOS = ("empresa_id", "dia", "estado", "motivo", "n")

# Datos del candidato, **leídos del modelo** y no escritos a mano: el día que
# `candidatos` gane una columna, este recorrido la cubre sin que nadie lo toque.
# Fuera quedan las tres que no son suyas: la clave, la empresa y la fecha de alta.
NO_SON_DEL_CANDIDATO = ("id", "empresa_id", "creado_en")
DATOS_DEL_CANDIDATO = (
    *(c.name for c in Candidato.__table__.columns if c.name not in NO_SON_DEL_CANDIDATO),
    # Las razones del score son dato derivado del candidato (F25, PR-02), y el
    # hash del CV es un identificador suyo (CA16): `match_auditoria_scores` no
    # tiene modelo, así que este nombre va escrito.
    modelos.ScoreDeMatch.razones.key,
    "hash_cv",
)
# Y en el **nombre de una columna** tampoco cabe un identificador del candidato.
IDENTIFICADORES_DEL_CANDIDATO = ("candidato_id", "candidato")

# Las tablas que el agente de métricas no puede ni leer ni escribir. Los dos
# nombres de Match salen de los modelos: así el recorrido sigue al esquema.
TABLAS_PROHIBIDAS = (
    "candidatos",
    "usuarios",
    modelos.ScoreDeMatch.__tablename__,
    modelos.TrabajoDeMatch.__tablename__,
)

# `42501` es `insufficient_privilege` de Postgres. Se mira el código y no solo el
# texto porque el mensaje viene en el idioma del servidor.
CODIGO_PERMISO_DENEGADO = "42501"

# **Mediodía UTC a propósito.** `dia` se calcula en la zona del servidor —UTC en
# el contenedor de `docker-compose.yml`— y una marca de medianoche caería en el
# día de antes o de después con cualquier otra zona.
MOMENTO_DE_HOY = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
MOMENTO_DE_AYER = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
DIA_DE_HOY = MOMENTO_DE_HOY.date()
DIA_DE_AYER = MOMENTO_DE_AYER.date()

MOTIVO_SIN_SCORE = "CV sin texto extraíble"
MOTIVO_DE_ERROR = "timeout del proveedor"


# --- el esquema `metricas`: existe, con qué columnas y con qué definición ----


def esquemas(sesion: Session) -> set[str]:
    """Los esquemas de la base de test, para que «no está» se lea como «no está»."""
    return {nombre for (nombre,) in sesion.execute(text("SELECT nspname FROM pg_namespace"))}


def relaciones_de_metricas(sesion: Session) -> dict[str, str]:
    """Lo que vive en el esquema `metricas`, con su clase de relación.

    Se pregunta a `pg_class` y no a `information_schema.views` porque una vista
    **materializada** (`relkind = 'm'`) no aparece en `information_schema` y es
    una implementación legítima de «vista agregada». Lo que el contrato no
    permite es una **tabla** (`'r'`): una copia de las filas no es un agregado.
    """
    consulta = text(
        "SELECT c.relname, c.relkind FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = :esquema AND c.relkind IN ('r', 'p', 'v', 'm')"
    )
    return {nombre: clase for nombre, clase in sesion.execute(consulta, {"esquema": ESQUEMA})}


def columnas_de(sesion: Session, vista: str) -> list[str]:
    """Las columnas de una relación de `metricas`, en su orden.

    Lista vacía si no existe: así el rojo de un criterio de columnas es una
    comparación que se lee, y no una excepción del driver.
    """
    consulta = text(
        "SELECT a.attname FROM pg_attribute a "
        "JOIN pg_class c ON c.oid = a.attrelid "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = :esquema AND c.relname = :vista "
        "AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum"
    )
    return [nombre for (nombre,) in sesion.execute(consulta, {"esquema": ESQUEMA, "vista": vista})]


def definicion_de(sesion: Session, vista: str) -> str:
    """El SQL de la vista, para mirar **lo que lee** y no solo lo que expone.

    La relación se resuelve con el **mismo** par `:esquema`/`:vista` sobre
    `pg_class` que `relaciones_de_metricas` y `columnas_de`, y no con un
    `:nombre::regclass`: en SQLAlchemy `::` **no** deja ver el parámetro —su
    detector es `(?<![:\\w\\x5c]):(\\w+)(?![:\\w])` y el `(?![:\\w])` descarta
    `:nombre` cuando le sigue `:`—, así que el texto salía literal y Postgres lo
    rechazaba con `42601` antes de mirar qué vista era. Con el `JOIN` hay una
    sola forma de nombrar una relación en este archivo y ninguna depende de
    `search_path` ni del entrecomillado de un nombre calificado a mano.

    El `assert` es la otra mitad: `pg_get_viewdef` de algo que no existe da
    `NULL`, y un `str(None)` se colaría como definición sin datos del candidato
    —el criterio de privacidad aprobaría **sin haber leído nada**—.
    """
    consulta = text(
        "SELECT pg_get_viewdef(c.oid, true) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = :esquema AND c.relname = :vista"
    )
    definicion = sesion.scalar(consulta, {"esquema": ESQUEMA, "vista": vista})
    assert definicion is not None, (
        f"no se pudo leer la definición de {ESQUEMA}.{vista}: no existe como vista. "
        "La crea la migración nueva del staging."
    )
    return str(definicion)


def exigir_la_vista(sesion: Session, vista: str) -> None:
    """El guardia que hace legible el rojo de los conteos.

    Sin él, «los conteos no cuadran» y «la migración no está» se ven igual: una
    excepción del driver sobre un esquema que no existe.
    """
    existentes = sorted(relaciones_de_metricas(sesion))
    assert vista in existentes, (
        f"no existe {ESQUEMA}.{vista}; en el esquema {ESQUEMA} hay {existentes}. "
        "La crea la migración nueva del staging."
    )


# --- leer las vistas --------------------------------------------------------


def agregado_de_scores(sesion: Session, empresa_id: int) -> list[tuple[object, ...]]:
    """`metricas.scores_por_vacante` de **una** empresa, por día y vacante."""
    consulta = text(
        f"SELECT {', '.join(COLUMNAS_DE_SCORES)} FROM {ESQUEMA}.{VISTA_SCORES} "
        "WHERE empresa_id = :empresa ORDER BY dia, vacante_id"
    )
    return [tuple(fila) for fila in sesion.execute(consulta, {"empresa": empresa_id})]


def agregado_de_trabajos(sesion: Session, empresa_id: int) -> list[tuple[object, ...]]:
    """`metricas.trabajos_por_estado` de **una** empresa, por día y estado."""
    consulta = text(
        f"SELECT {', '.join(COLUMNAS_DE_TRABAJOS)} FROM {ESQUEMA}.{VISTA_TRABAJOS} "
        "WHERE empresa_id = :empresa ORDER BY dia, estado, motivo"
    )
    return [tuple(fila) for fila in sesion.execute(consulta, {"empresa": empresa_id})]


def empresas_en_la_vista(sesion: Session, vista: str) -> set[int]:
    consulta = text(f"SELECT DISTINCT empresa_id FROM {ESQUEMA}.{vista}")
    return {int(fila) for (fila,) in sesion.execute(consulta)}


# --- sembrar filas, siempre por el repositorio ------------------------------


def sembrar_scores(
    sesion: Session,
    empresa: EmpresaDePrueba,
    puntuaciones: Sequence[int | None],
    momento: datetime,
) -> None:
    """Un score por candidato nuevo, todos con `actualizado_en = momento`.

    `None` es «sin score» con su motivo (CA13) y el `0` es un score de verdad:
    son los dos casos que el contrato pide sembrar, porque son los dos que un
    conteo mal escrito confunde.

    La fecha se fija **asignando el atributo** de la fila que devuelve el
    repositorio: no hay API para fijarla —en producción la pone el servidor— y
    una asignación no es una sentencia SQL, así que la regla (a) de PR-04 sigue
    cumpliéndose: toda escritura pasa por `repo_de`.
    """
    candidatos = sembrar_candidatos(sesion, empresa, len(puntuaciones))
    repo = repo_de(sesion, empresa)
    for candidato, puntos in zip(candidatos, puntuaciones, strict=True):
        fila = repo.guardar_score(
            candidato.id,
            empresa.vacante.id,
            puntos,
            RAZONES if puntos is not None else (),
            motivo_sin_score=None if puntos is not None else MOTIVO_SIN_SCORE,
        )
        fila.actualizado_en = momento
    sesion.flush()


def sembrar_trabajos(
    sesion: Session,
    empresa: EmpresaDePrueba,
    trabajos: Sequence[tuple[str, str | None]],
    momento: datetime,
) -> None:
    """Un trabajo por candidato nuevo, con su estado y motivo, creado en `momento`.

    `creado_en` se fija a mano por la misma razón que arriba, y aquí además
    importa: `marcar_trabajo` mueve `actualizado_en` a ahora, así que una vista
    que agrupara por la fecha equivocada daría el día de hoy para el trabajo que
    nació ayer.
    """
    candidatos = sembrar_candidatos(sesion, empresa, len(trabajos))
    repo = repo_de(sesion, empresa)
    for candidato, (estado, motivo) in zip(candidatos, trabajos, strict=True):
        fila = repo.crear_trabajo(
            candidato.id, empresa.vacante.id, f"clave-sintetica-{candidato.id}"
        )
        if estado != "pendiente":
            fila = repo.marcar_trabajo(fila.id, estado, motivo=motivo)
        fila.creado_en = momento
    sesion.flush()


# --- el rol `agente_metricas` -----------------------------------------------


def sentencias_de(guion: str) -> list[str]:
    """Parte un guion SQL en sentencias, **respetando los bloques `$…$`**.

    pg8000 habla el protocolo extendido y no acepta varias sentencias en un solo
    `execute`, así que el guion se parte aquí, como lo partiría `psql`. Un
    `split(';')` a secas rompería el `DO $$ … $$` con el que se crea un rol de
    forma idempotente, que es la única forma que hay: Postgres no tiene
    `CREATE ROLE IF NOT EXISTS`.
    """
    sin_comentarios = re.sub(r"--[^\n]*", "", guion)
    sentencias: list[str] = []
    actual: list[str] = []
    etiqueta: str | None = None
    for trozo in re.split(r"(\$[A-Za-z_]*\$|;)", sin_comentarios):
        if etiqueta is None and re.fullmatch(r"\$[A-Za-z_]*\$", trozo):
            etiqueta = trozo
        elif trozo == etiqueta:
            etiqueta = None
        elif trozo == ";" and etiqueta is None:
            sentencias.append("".join(actual).strip())
            actual = []
            continue
        actual.append(trozo)
    sentencias.append("".join(actual).strip())
    return [sentencia for sentencia in sentencias if sentencia]


def correr_el_guion_de_roles(motor: Engine) -> None:
    """Ejecuta `staging/roles.sql` como lo ejecutaría el staging.

    Los `assert` son del cuerpo del test que llama: el guion **no existe
    todavía**, y eso es el rojo del criterio, no un error de montaje.
    """
    relativa = ROLES_SQL.relative_to(RAIZ).as_posix()
    assert ROLES_SQL.is_file(), (
        f"falta {relativa}: el rol {ROL} lo crea el guion del staging, no la migración"
    )
    guion = ROLES_SQL.read_text(encoding="utf-8")
    assert ROL in guion, f"{relativa} no nombra el rol {ROL}"
    with motor.connect().execution_options(isolation_level="AUTOCOMMIT") as conexion:
        for sentencia in sentencias_de(guion):
            conexion.exec_driver_sql(sentencia)


def existe_el_rol(motor: Engine) -> bool:
    with motor.connect() as conexion:
        consulta = text("SELECT 1 FROM pg_roles WHERE rolname = :rol")
        return conexion.scalar(consulta, {"rol": ROL}) == 1


def reponer_el_public_de_produccion(motor: Engine) -> None:
    """Devuelve al esquema `public` el `USAGE` que `initdb` le da en producción.

    No es un arreglo del código bajo prueba: es **poner la base de test en el
    estado de producción** para que el recorrido de permisos mida lo que dice
    medir. `initdb` crea `public` con `GRANT USAGE … TO PUBLIC`, pero
    `tests/conftest.py` lo recrea con `CREATE SCHEMA public` —que no reproduce
    ese permiso—, y entonces `agente_metricas` no resuelve ni el nombre de la
    tabla: el error sería `42P01` («no existe») en vez de `42501` («permiso
    denegado»), y el test aprobaría por la razón equivocada. Comprobado contra
    Postgres 16: con el `USAGE` puesto, las cuatro tablas responden `42501`.
    """
    with motor.connect().execution_options(isolation_level="AUTOCOMMIT") as conexion:
        conexion.exec_driver_sql("GRANT USAGE ON SCHEMA public TO PUBLIC")


def migracion_de_metricas() -> Path:
    """La migración que crea el esquema `metricas`, buscada por su contenido.

    Por contenido y no por nombre de archivo para no fijar cómo se llama, y
    exigiendo **una sola**: dos migraciones tocando el mismo esquema es
    exactamente lo que nadie revisa.
    """
    candidatas = sorted(
        archivo
        for archivo in MIGRACIONES.glob("*.py")
        if ESQUEMA in archivo.read_text(encoding="utf-8")
    )
    assert len(candidatas) == 1, (
        f"se esperaba una sola migración que cree el esquema {ESQUEMA} y hay "
        f"{[a.name for a in candidatas]}"
    )
    return candidatas[0]


def reaplicar_la_migracion_de_metricas(url: str) -> None:
    """Vuelve a aplicar la migración de métricas: `downgrade` y `upgrade`.

    Hace falta porque el **permiso** lo da la migración y el **rol** lo crea el
    guion: la base de test se migró antes de que el rol existiera, así que el
    `GRANT` condicional no corrió. Esto es también lo que pasa en producción el
    día del despliegue, y en qué orden se hace es parte de lo que el staging
    tiene que dejar escrito.
    """
    anterior = re.search(
        r"^down_revision[^=]*=\s*[\"']([^\"']+)[\"']",
        migracion_de_metricas().read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert anterior is not None, "la migración de métricas no declara `down_revision`"
    revertir_migraciones(url, anterior.group(1))
    aplicar_migraciones(url)


@pytest.fixture
def preparar_el_agente(motor_test: Engine, url_bd_test: str) -> Iterator[Callable[[], Connection]]:
    """Devuelve el **preparador** de una conexión con `SET ROLE agente_metricas`.

    Preparador y no conexión ya abierta: los `assert` de «falta `roles.sql`» y
    «falta la migración» tienen que ocurrir en el cuerpo del test (igual que la
    fixture `cli` de PR-09).

    No pide la fixture `sesion`: estos tests no siembran nada —leer las vistas
    con cero filas ya ejerce el permiso— y así el `downgrade`/`upgrade` de la
    migración no se cruza con una transacción abierta sobre las mismas vistas.
    """
    abiertas: list[Connection] = []

    def preparar() -> Connection:
        correr_el_guion_de_roles(motor_test)
        reaplicar_la_migracion_de_metricas(url_bd_test)
        reponer_el_public_de_produccion(motor_test)
        conexion = motor_test.connect()
        abiertas.append(conexion)
        conexion.execute(text(f"SET ROLE {ROL}"))
        return conexion

    yield preparar
    for conexion in abiertas:
        conexion.rollback()
        conexion.close()


def error_al_ejecutar(conexion: Connection, sentencia: str) -> str:
    """Ejecuta algo que **tiene que fallar** y devuelve el error, o `""`.

    Cada sentencia va en su `SAVEPOINT`: un error de permisos aborta la
    transacción, y sin el savepoint la segunda tabla del recorrido fallaría por
    «transacción abortada» y el recorrido no probaría nada.
    """
    try:
        with conexion.begin_nested():
            conexion.execute(text(sentencia))
    except DBAPIError as error:
        return str(error)
    return ""


def es_permiso_denegado(error: str) -> bool:
    return CODIGO_PERMISO_DENEGADO in error or "permission denied" in error.lower()
