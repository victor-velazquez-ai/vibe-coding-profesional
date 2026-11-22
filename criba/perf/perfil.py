"""Dónde se va el tiempo de la vista de vacante: consultas, render y bytes.

    uv run --with locust python -m perf.perfil

Locust dice *cuánto* tarda la vista (`perf/locustfile.py`); esto dice *en qué*.
Mide tres cosas por petición y las separa:

1. **Consultas SQL por petición**: cuántas, cuáles y cuánto suman. Es el número
   que decide si hay un N+1 —si crece con las 500 filas— y el que
   `app/match/services/listado.py` promete que no crece («una consulta para toda
   la lista»). Medirlo es la única forma de saber si eso sigue siendo verdad.
2. **Tiempo de render** de la plantilla Jinja.
3. **Tamaño de la respuesta** en bytes, y cuánto de ese tamaño es texto de CV.

Lo que queda —total menos SQL menos render— es el resto del camino: ASGI,
dependencias de FastAPI, cookie y serialización del cuerpo.

**Sin tocar la app.** Las dos sondas se enganchan desde aquí:

- las consultas, por los eventos `before/after_cursor_execute` de la **clase**
  `Engine` de SQLAlchemy, que es el gancho público para esto y no obliga a pasar
  por `app/db.py`;
- el render, envolviendo `jinja2.environment.Template.render` en memoria, en este
  proceso y solo mientras corre el perfil.

Ninguna de las dos escribe en `app/`, y por eso lo que se mide es exactamente el
código que corre en el servidor de medición. La petición se hace **en proceso**
con el `TestClient` de Starlette: así el número no lleva dentro el `loopback` ni
el `accept` de uvicorn, que es justo lo que `SPEC.md` llama «del lado del
servidor» en CA5.

Los **controles** son la mitad del diagnóstico. Medir solo la vista de `marcus`
dice que tarda; compararla con las mismas 500 filas renderizadas con menos HTML
por fila —el hiring manager, que por CA18 no ve score ni puede escribir, y el
fragmento propio de Match, que pinta tres columnas— dice *qué parte* del HTML
cuesta. Y la misma vista con 4 filas separa el costo fijo del costo por fila.

Y los **sondeos** del final cierran la pregunta que el reparto por fases deja
abierta: de los milisegundos que se van en «SQL», ¿cuántos son de Postgres y
cuántos del camino de vuelta? La respuesta cambia por completo qué habría que
optimizar, así que se mide y no se supone.
"""

from __future__ import annotations

import statistics
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import jinja2.environment
from sqlalchemy import Engine, event, func, select
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.configuracion import ajustes
from app.db import motor
from app.fabrica import crear_app
from app.plataforma.modelos import Candidato, Postulacion
from app.plataforma.repositorio import RepositorioEmpresa

CALENTAMIENTO = 5
MUESTRAS = 40
REPETICIONES_DEL_SONDEO = 20
PRESUPUESTO_MS = 300  # CA5 y la tabla de «Rendimiento (números medibles)».
EMPRESA_NORTHSTAR = 1
MARCA_DE_FILA = 'data-testid="fila-candidato"'
MARCA_DE_FILA_MATCH = 'data-testid="fila-match"'

# Qué método del repositorio es cada sentencia. Se busca por subcadena y en este
# orden: la lista y el `<select>` leen las dos de `candidatos`, y solo las
# distingue el `JOIN`.
NOMBRES_DE_CONSULTA = (
    ("JOIN postulaciones", "candidatos_de_vacante · la lista de la vista"),
    ("FROM candidatos", "candidatos_sin_postular_a · el <select> de «añadir»"),
    ("FROM match_scores", "scores_de_vacante · los scores ya guardados"),
    ("FROM vacantes", "vacante · la cabecera de la página"),
    ("FROM empresas", "empresa_activada · la comprobación de D7/CA3"),
)


def nombre_de(sentencia: str) -> str:
    for marca, nombre in NOMBRES_DE_CONSULTA:
        if marca in sentencia:
            return nombre
    return "sin clasificar"


@dataclass(slots=True)
class Consulta:
    """Una sentencia tal como salió al driver, con sus parámetros y su duración."""

    sentencia: str
    parametros: Any
    ms: float


@dataclass(slots=True)
class Sonda:
    """Lo que las dos sondas acumulan durante **una** petición."""

    consultas: list[Consulta] = field(default_factory=list)
    render_ms: float = 0.0
    renders: int = 0
    _comienzo: float = 0.0

    def reiniciar(self) -> None:
        self.consultas = []
        self.render_ms = 0.0
        self.renders = 0

    @property
    def sql_ms(self) -> float:
        return sum(c.ms for c in self.consultas)


SONDA = Sonda()


def instalar_sondas() -> None:
    """Engancha las dos sondas. Se llama una vez por proceso.

    Los eventos van sobre la **clase** `Engine` y no sobre la instancia: el motor
    de la app se crea con `lru_cache` dentro de `app.db.motor()`, y engancharse a
    la clase no obliga a importarlo antes ni a modificar nada.
    """

    @event.listens_for(Engine, "before_cursor_execute")
    def _antes(conn, cursor, statement, parameters, context, executemany):
        SONDA._comienzo = time.perf_counter()

    @event.listens_for(Engine, "after_cursor_execute")
    def _despues(conn, cursor, statement, parameters, context, executemany):
        SONDA.consultas.append(
            Consulta(
                sentencia=" ".join(statement.split()),
                parametros=parameters,
                ms=(time.perf_counter() - SONDA._comienzo) * 1000,
            )
        )

    render_original = jinja2.environment.Template.render

    def render_cronometrado(self, *args: Any, **kwargs: Any) -> str:
        comienzo = time.perf_counter()
        try:
            return render_original(self, *args, **kwargs)
        finally:
            SONDA.render_ms += (time.perf_counter() - comienzo) * 1000
            SONDA.renders += 1

    jinja2.environment.Template.render = render_cronometrado  # type: ignore[method-assign]


@dataclass(frozen=True, slots=True)
class Escenario:
    """Una ruta medida con la sesión de un usuario, y por qué está en la lista."""

    etiqueta: str
    usuario: str
    ruta: str
    marca: str
    porque: str


ESCENARIOS = (
    Escenario(
        etiqueta="CA5 · marcus abre la vacante de 500",
        usuario="marcus",
        ruta="/vacantes/1",
        marca=MARCA_DE_FILA,
        porque="la petición del SLO: reclutador, 500 filas, score y acciones de escritura",
    ),
    Escenario(
        etiqueta="control · hiring manager, 500 filas sin score ni textarea",
        usuario="hm.northstar",
        ruta="/vacantes/1",
        marca=MARCA_DE_FILA,
        porque="CA18 le quita score y escritura: mismas 500 filas con mucho menos HTML por fila",
    ),
    Escenario(
        etiqueta="control · fragmento de Match, 500 filas en 3 columnas",
        usuario="marcus",
        ruta="/match/vacantes/1/lista",
        marca=MARCA_DE_FILA_MATCH,
        porque="mismas 500 filas y casi las mismas consultas, sin CV ni formularios",
    ),
    Escenario(
        etiqueta="control · la misma vista con 4 filas",
        usuario="marcus",
        ruta="/vacantes/2",
        marca=MARCA_DE_FILA,
        porque="separa el costo fijo de la petición del costo por fila",
    ),
)


@dataclass(slots=True)
class Medicion:
    """Las muestras de un escenario, ya separadas por fase."""

    escenario: Escenario
    total_ms: list[float] = field(default_factory=list)
    sql_ms: list[float] = field(default_factory=list)
    render_ms: list[float] = field(default_factory=list)
    consultas: list[int] = field(default_factory=list)
    bytes_: int = 0
    filas: int = 0
    por_sentencia: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    repeticiones: Counter[str] = field(default_factory=Counter)
    ultima: list[Consulta] = field(default_factory=list)


def _percentil(valores: list[float], fraccion: float) -> float:
    ordenados = sorted(valores)
    indice = min(len(ordenados) - 1, round(fraccion * (len(ordenados) - 1)))
    return ordenados[indice]


def _entrar(cliente: TestClient, usuario: str) -> None:
    respuesta = cliente.post(
        "/entrar",
        data={"usuario": usuario, "contrasena": f"{usuario}1234", "destino": "/vacantes"},
        follow_redirects=False,
    )
    if respuesta.status_code != 303:
        raise RuntimeError(
            f"{usuario!r} no entró: /entrar devolvió {respuesta.status_code}. "
            "¿La base de medición tiene la semilla de la plataforma?"
        )


def medir(escenario: Escenario) -> Medicion:
    """`CALENTAMIENTO` peticiones para calentar y `MUESTRAS` para medir.

    El calentamiento no es cortesía: la primera petición compila las plantillas
    Jinja y abre la conexión del pool, y meter eso en el p95 mediría el arranque
    del proceso y no la vista.
    """
    medicion = Medicion(escenario=escenario)
    with TestClient(crear_app()) as cliente:
        _entrar(cliente, escenario.usuario)

        for _ in range(CALENTAMIENTO):
            cliente.get(escenario.ruta).raise_for_status()

        for numero in range(MUESTRAS):
            SONDA.reiniciar()
            comienzo = time.perf_counter()
            respuesta = cliente.get(escenario.ruta)
            total = (time.perf_counter() - comienzo) * 1000
            respuesta.raise_for_status()

            if SONDA.renders == 0:
                raise RuntimeError(
                    "La sonda de render no capturó nada: Template.render no se llamó. "
                    "La envoltura de jinja2 dejó de valer y el número de render sería un 0 falso."
                )
            medicion.total_ms.append(total)
            medicion.sql_ms.append(SONDA.sql_ms)
            medicion.render_ms.append(SONDA.render_ms)
            medicion.consultas.append(len(SONDA.consultas))
            for sentencia, ms in _por_sentencia(SONDA.consultas).items():
                medicion.por_sentencia[sentencia].append(ms)
            medicion.repeticiones.update(
                {s: n for s, n in Counter(c.sentencia for c in SONDA.consultas).items() if n > 1}
            )
            if numero == 0:
                medicion.bytes_ = len(respuesta.content)
                medicion.filas = respuesta.text.count(escenario.marca)
            medicion.ultima = list(SONDA.consultas)
    return medicion


def _por_sentencia(consultas: list[Consulta]) -> dict[str, float]:
    """Suma los milisegundos de una petición por sentencia distinta."""
    acumulado: dict[str, float] = defaultdict(float)
    for consulta in consultas:
        acumulado[consulta.sentencia] += consulta.ms
    return acumulado


def informe_de(medicion: Medicion) -> str:
    e = medicion.escenario
    total, sql, render = medicion.total_ms, medicion.sql_ms, medicion.render_ms
    resto = [t - s - r for t, s, r in zip(total, sql, render, strict=True)]
    lineas = [
        f"### {e.etiqueta}",
        f"    {e.usuario} GET {e.ruta} · {medicion.filas} filas renderizadas",
        f"    por qué está medido: {e.porque}",
        "",
        f"    bytes de la respuesta    {medicion.bytes_:>12,}",
        f"    bytes por fila           {medicion.bytes_ // max(1, medicion.filas):>12,}",
        f"    consultas por petición   {min(medicion.consultas):>12}"
        f" (min) … {max(medicion.consultas)} (max)",
        "",
        f"    {'fase':<10}{'p50 ms':>9}{'p95 ms':>9}{'p99 ms':>9}{'media':>9}{'% del p50':>11}",
        f"    {'-' * 56}",
    ]
    p50_total = _percentil(total, 0.50)
    for nombre, valores in (("total", total), ("SQL", sql), ("render", render), ("resto", resto)):
        lineas.append(
            f"    {nombre:<10}{_percentil(valores, 0.50):>9.1f}{_percentil(valores, 0.95):>9.1f}"
            f"{_percentil(valores, 0.99):>9.1f}{statistics.fmean(valores):>9.1f}"
            f"{100 * _percentil(valores, 0.50) / p50_total:>10.0f}%"
        )
    lineas += [
        "",
        f"    veredicto del presupuesto de CA5 ({PRESUPUESTO_MS} ms sobre el p95): "
        f"{'DENTRO' if _percentil(total, 0.95) < PRESUPUESTO_MS else 'FUERA'}",
        "",
        f"    consultas, media de las {MUESTRAS} muestras:",
    ]
    for sentencia, muestras in sorted(
        medicion.por_sentencia.items(), key=lambda par: -statistics.fmean(par[1])
    ):
        lineas.append(f"      {statistics.fmean(muestras):>7.1f} ms  {nombre_de(sentencia)}")
    lineas.append(
        "    sentencias repetidas dentro de una misma petición (señal de N+1): "
        + (
            "ninguna"
            if not medicion.repeticiones
            else ", ".join(f"{nombre_de(s)} ({n} veces)" for s, n in medicion.repeticiones.items())
        )
    )
    return "\n".join(lineas)


def composicion_del_cuerpo(bd: Session, vacante_id: int = 1) -> str:
    """De qué está hecho 1,5 MB: filas, texto de CV y el resto del HTML."""
    filas, suma_cv = bd.execute(
        select(
            func.count(Postulacion.id),
            func.coalesce(func.sum(func.length(Candidato.cv_texto)), 0),
        )
        .join(Candidato, Candidato.id == Postulacion.candidato_id)
        .where(Postulacion.vacante_id == vacante_id)
    ).one()
    return (
        f"    filas de la vacante {vacante_id}: {filas}\n"
        f"    suma de `cv_texto` de esas filas: {suma_cv:,} caracteres\n"
        "    `_candidatos.html` mete `cv_texto` completo dentro de un <textarea> por fila,\n"
        "    así que esos caracteres son bytes de la respuesta de cada apertura de vacante."
    )


def _mediana_de(hacer: Callable[[], object], repeticiones: int = REPETICIONES_DEL_SONDEO) -> float:
    tiempos = []
    for _ in range(repeticiones):
        comienzo = time.perf_counter()
        hacer()
        tiempos.append((time.perf_counter() - comienzo) * 1000)
    return statistics.median(tiempos)


def _tiempo_de_postgres(bd: Session, consulta: Consulta) -> tuple[float, str]:
    """`EXPLAIN (ANALYZE, BUFFERS)` de la sentencia **tal como la mandó la app**.

    Se reusa la sentencia capturada y sus parámetros en vez de reescribir el
    `select` aquí: una copia del SQL del repositorio dentro del perfilador
    envejece mal y acabaría explicando una consulta que la app ya no hace.
    """
    cursor = bd.connection().connection.cursor()
    cursor.execute(f"EXPLAIN (ANALYZE, BUFFERS) {consulta.sentencia}", consulta.parametros)
    plan = [fila[0] for fila in cursor.fetchall()]
    ejecucion = next(
        float(linea.split(":")[1].strip().split(" ")[0])
        for linea in plan
        if linea.startswith("Execution Time:")
    )
    return ejecucion, "\n".join(f"      {linea}" for linea in plan)


def comparativa_app_vs_postgres(bd: Session, medicion: Medicion) -> str:
    """Las cinco consultas de la vista, cronometradas dos veces.

    A la izquierda lo que la app tarda en cada sentencia, medido desde los
    eventos del motor —o sea: mandar, esperar, traer las filas y decodificarlas—;
    a la derecha lo que Postgres dice que tardó en ejecutarla. La diferencia es
    tiempo que **no** está en la base de datos y que ningún índice arregla, y es
    el número del que cuelga todo el diagnóstico de `perf/MEDICION.md`.
    """
    medias = {s: statistics.fmean(v) for s, v in medicion.por_sentencia.items()}
    por_sentencia = {c.sentencia: c for c in medicion.ultima}
    lineas = [
        f"    {'consulta':<54}{'app':>10}{'Postgres':>11}{'fuera de PG':>13}",
        f"    {'-' * 88}",
    ]
    total_app = total_pg = 0.0
    for sentencia, ms_app in sorted(medias.items(), key=lambda par: -par[1]):
        ms_pg, _ = _tiempo_de_postgres(bd, por_sentencia[sentencia])
        total_app += ms_app
        total_pg += ms_pg
        lineas.append(
            f"    {nombre_de(sentencia):<54}{ms_app:>8.1f}ms{ms_pg:>9.2f}ms"
            f"{100 * (1 - ms_pg / ms_app):>12.0f}%"
        )
    lineas.append(
        f"    {'suma de las consultas de la petición':<54}{total_app:>8.1f}ms"
        f"{total_pg:>9.2f}ms{100 * (1 - total_pg / total_app):>12.0f}%"
    )
    return "\n".join(lineas)


def sondeo_de_la_lista(bd: Session, consulta: Consulta) -> str:
    """De los milisegundos de «SQL», ¿cuántos son de Postgres?

    Cuatro medidas de **la misma lista de 500 filas**, de dentro hacia fuera:

    1. lo que Postgres dice que tardó en ejecutarla (`EXPLAIN ANALYZE`);
    2. el driver `pg8000` con un cursor crudo, sin SQLAlchemy: ejecutar, traer
       las 500 filas y decodificarlas en Python;
    3. el mismo cursor crudo pidiendo **las columnas que la lista muestra** en vez
       de la fila entera: sin `cv_texto`, sin `links` y sin `cv_actualizado_en`.
       Es la hipótesis de arreglo, medida antes de arreglar nada;
    4. el repositorio de la plataforma, que es lo que la vista llama de verdad:
       lo anterior más construir 500 objetos `Candidato` y 500 `Postulacion`.

    La diferencia entre (1) y (4) es el presupuesto que no está en la base de
    datos, y la diferencia entre (2) y (3) dice cuánto de eso es el texto del CV.
    """
    ms_postgres, plan = _tiempo_de_postgres(bd, consulta)

    crudo = bd.connection().connection

    def cursor_completo() -> None:
        cursor = crudo.cursor()
        cursor.execute(consulta.sentencia, consulta.parametros)
        cursor.fetchall()

    # Las columnas que `_candidatos.html` pinta de verdad: nombre, correo,
    # teléfono, el **largo** del CV (la plantilla muestra «N caracteres»), la
    # etapa, la fecha y el conteo de notas. Ni el texto del CV ni `links`.
    sin_cv = (
        "SELECT candidatos.id, candidatos.nombre, candidatos.correo, candidatos.telefono, "
        "length(candidatos.cv_texto), postulaciones.id, postulaciones.etapa, "
        "postulaciones.creada_en, (SELECT count(notas_entrevista.id) FROM notas_entrevista "
        "WHERE notas_entrevista.postulacion_id = postulaciones.id) "
        "FROM candidatos JOIN postulaciones ON postulaciones.candidato_id = candidatos.id "
        "WHERE postulaciones.empresa_id = 1 AND candidatos.empresa_id = 1 "
        "AND postulaciones.vacante_id = 1 "
        "ORDER BY postulaciones.creada_en DESC, postulaciones.id DESC"
    )

    def cursor_sin_cv() -> None:
        cursor = crudo.cursor()
        cursor.execute(sin_cv)
        cursor.fetchall()

    repo = RepositorioEmpresa(bd, EMPRESA_NORTHSTAR)

    def por_el_repositorio() -> None:
        bd.expunge_all()
        repo.candidatos_de_vacante(1)

    medidas = (
        ("1 · Postgres, Execution Time de EXPLAIN ANALYZE", ms_postgres),
        ("2 · driver pg8000, cursor crudo, fila completa", _mediana_de(cursor_completo)),
        ("3 · driver pg8000, solo las columnas que la lista muestra", _mediana_de(cursor_sin_cv)),
        (
            "4 · RepositorioEmpresa.candidatos_de_vacante (lo que corre)",
            _mediana_de(por_el_repositorio),
        ),
    )
    lineas = [f"    {etiqueta:<60}{ms:>8.1f} ms" for etiqueta, ms in medidas]
    lineas += [
        "",
        f"    fuera de Postgres: {medidas[3][1] - ms_postgres:.1f} ms de los "
        f"{medidas[3][1]:.1f} ms ({100 * (1 - ms_postgres / medidas[3][1]):.0f} %)",
        f"    atribuible al texto del CV en el cursor crudo: "
        f"{medidas[1][1] - medidas[2][1]:.1f} ms",
        "",
        "    el plan de Postgres, para que el número 1 no sea una afirmación:",
        plan,
    ]
    return "\n".join(lineas)


def sondeo_del_select_de_disponibles(bd: Session) -> str:
    """El quinto `SELECT` de la vista, el que no escala con las 500 filas.

    `contexto_candidatos` llama a `candidatos_sin_postular_a` para llenar el
    `<select>` de «añadir un candidato», y eso trae **todos los candidatos de la
    empresa que no están postulados a esta vacante, con su `cv_texto` entero**.
    En la vacante 1 de esta siembra casi todos están postulados, así que devuelve
    pocas filas y la medición de CA5 **no lo ve**. En cualquier otra vacante de la
    misma empresa devuelve el resto del padrón.
    """
    repo = RepositorioEmpresa(bd, EMPRESA_NORTHSTAR)

    def leer(vacante_id: int) -> Callable[[], object]:
        """Una fábrica y no un `lambda` dentro del bucle: el `lambda` capturaría
        la variable del bucle y las tres vacantes se medirían con la última."""

        def hacer() -> object:
            bd.expunge_all()
            return repo.candidatos_sin_postular_a(vacante_id)

        return hacer

    lineas = []
    for vacante_id in (1, 2, 3):
        bd.expunge_all()
        filas = len(repo.candidatos_sin_postular_a(vacante_id))
        ms = _mediana_de(leer(vacante_id))
        lineas.append(f"    vacante {vacante_id}: {filas:>4} filas en el <select>  {ms:>7.1f} ms")
    total = bd.scalar(
        select(func.count(Candidato.id)).where(Candidato.empresa_id == EMPRESA_NORTHSTAR)
    )
    lineas.append(f"    candidatos de Northstar en la base de medición: {total}")
    return "\n".join(lineas)


def main() -> None:
    instalar_sondas()
    print(f"Base: {ajustes().url_bd}")
    print(f"Muestras por escenario: {MUESTRAS} (más {CALENTAMIENTO} de calentamiento)")
    print("Peticiones en proceso con TestClient: sin loopback y sin uvicorn.\n")

    mediciones = [medir(escenario) for escenario in ESCENARIOS]
    for medicion in mediciones:
        print(informe_de(medicion))
        print()

    print("### De qué está hecho el cuerpo de la respuesta\n")
    with Session(motor()) as bd:
        print(composicion_del_cuerpo(bd))
        print()
        print("### Sondeo · cada consulta de la vista de CA5: la app contra Postgres\n")
        print(comparativa_app_vs_postgres(bd, mediciones[0]))
        print()
        la_lista = max(
            (c for c in mediciones[0].ultima if "JOIN postulaciones" in c.sentencia),
            key=lambda c: c.ms,
        )
        print("### Sondeo · los ~40 ms de «SQL» de la lista, de dentro hacia fuera\n")
        print(sondeo_de_la_lista(bd, la_lista))
        print()
        print("### Sondeo · el <select> de «añadir un candidato», que CA5 no ve\n")
        print(sondeo_del_select_de_disponibles(bd))


if __name__ == "__main__":
    main()
