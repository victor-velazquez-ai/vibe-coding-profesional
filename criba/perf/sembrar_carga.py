"""Deja la vacante 1 de Northstar con 500 candidatos postulados y con score.

    uv run --with locust python -m perf.sembrar_carga

Es la **precondición de CA5** (`SPEC.md`: «dada esa misma vacante de 500
candidatos … el p95 es menor que 300 ms») y de CA4. No mide nada: solo pone la
base en el estado que la medición necesita.

**Todo es sintético.** Nombres, correos, teléfonos y textos de CV están
inventados aquí mismo con un generador determinista; ningún dato real de cliente
entra en el repo (D3 modificado, D15). Los correos usan el dominio reservado
`.test`, como `app/plataforma/semilla.py`.

Tres propiedades que importan para que la medición se pueda repetir:

- **Idempotente.** Se cuenta lo que ya hay y se añade solo lo que falta. Correrlo
  dos veces deja exactamente lo mismo: la clave natural es el correo
  (`uq_candidatos_empresa_correo`) y el par (`uq_postulacion`).
- **Determinista.** El candidato número N siempre recibe el mismo nombre, el
  mismo CV, el mismo largo de CV y el mismo score, porque todos sus datos salen
  de un generador sembrado con N. Dos corridas miden sobre los mismos bytes.
- **Solo contra `criba_perf`.** Si `CRIBA_URL_BD` apunta a otra base —`criba_dev`
  o `criba_test`— aborta antes de escribir. Esta siembra mete 495 filas de
  candidato y no es lo que nadie quiere en su base de desarrollo.

Qué cuenta como «500 candidatos»: el objetivo es el **total de postulaciones de
la vacante 1**, que es el número de filas que la vista renderiza y el número que
nombra CA5. La semilla de desarrollo ya deja 5 ahí, así que este script añade
495. De los 500, 499 quedan con score: el que no es *Tobías Nkemelu*, que viene
de la semilla sin CV y por eso tiene que seguir sin score (CA13, «nunca un
cero»). Esa fila es además la única que ejerce la rama `'—'` de la plantilla.
"""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.configuracion import ajustes
from app.db import motor
from app.match.repositories.contexto import ContextoDeEmpresa
from app.match.repositories.match_repo import RepositorioDeMatch
from app.plataforma.modelos import Candidato, Empresa, Etapa, Postulacion, Vacante

BASE_ESPERADA = "criba_perf"
SLUG = "northstar-health"
VACANTE = 1
TOTAL = 500
DOMINIO = "perf.test"
PREFIJO_CORREO = "carga-"
# La vista ordena por `creada_en desc`: si todas las postulaciones nacieran en el
# mismo instante el orden lo decidiría el id y el ORDER BY dejaría de ser realista.
HOY = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)
DIAS_DE_ANTIGUEDAD = 120

NOMBRES = (
    "Alma", "Beatriz", "Camila", "Darnell", "Elena", "Fabián", "Gabriela", "Héctor",
    "Ingrid", "Joaquín", "Karla", "Lucía", "Mateo", "Noemí", "Omar", "Priscila",
    "Quetzal", "Rodrigo", "Sandra", "Tobías", "Ulises", "Valeria", "Wendy", "Ximena",
    "Yusuf", "Zoé", "Emeka", "Fernanda", "Nadia", "Óscar",
)  # fmt: skip
APELLIDOS = (
    "Rivas", "Whitaker", "Solórzano", "Nkemelu", "Okonjo", "Balderas", "Ferreira",
    "Appiah", "Barrantes", "Montenegro", "Rosenthal", "Isaza", "Quiroz", "Lund",
    "Cordero", "Delgado", "Benavides", "Lindqvist", "Cafferata", "Beltrán",
)  # fmt: skip

TITULARES = (
    "Enfermera/o registrado (RN), licencia de Texas vigente",
    "Enfermera/o registrado (RN), licencia multiestado",
    "Enfermera/o registrado (RN), especialidad en cuidados intensivos",
    "Enfermera/o vocacional con licencia (LVN)",
    "Enfermera/o registrado (RN) con experiencia administrativa",
)
UNIDADES = (
    "piso de medicina interna",
    "urgencias",
    "unidad de cuidados intensivos adultos",
    "piso quirúrgico",
    "telemetría",
    "unidad de maternidad",
    "oncología ambulatoria",
    "hemodiálisis",
)
TAREAS = (
    "Cuidado directo de pacientes en turnos de 12 horas, proporción 1:5",
    "Triaje, estabilización y traslado a unidad de cuidados intensivos",
    "Monitoreo hemodinámico y manejo de vía central",
    "Administración de medicamentos de alto riesgo con doble verificación",
    "Registro en expediente clínico electrónico y entrega de turno estructurada",
    "Educación al paciente y a la familia sobre el plan de alta",
    "Capacitación de personal de nuevo ingreso y de estudiantes de enfermería",
    "Participación en el comité de prevención de caídas de la unidad",
    "Manejo de ventilación mecánica no invasiva",
    "Coordinación de altas y traslados con trabajo social",
    "Atención bilingüe español/inglés a pacientes y familiares",
    "Soporte vital básico y avanzado vigentes, recertificación anual",
)
CERTIFICACIONES = (
    "BLS (American Heart Association)",
    "ACLS (American Heart Association)",
    "PALS",
    "NIHSS",
    "Certificación en telemetría",
    "Manejo de catéter venoso central",
)
RAZONES = (
    "Licencia de enfermería de Texas vigente, que la vacante exige",
    "{anios} años en {unidad}, por encima de los dos años pedidos",
    "Experiencia declarada en turno nocturno de 12 horas",
    "Atención bilingüe español/inglés, que la vacante valora",
    "Certificación de telemetría, mencionada como deseable",
    "Sin experiencia hospitalaria declarada en los últimos tres años",
    "No menciona soporte vital básico vigente",
    "El CV no indica disponibilidad para turno nocturno",
)
ETAPAS = (Etapa.POSTULADA, Etapa.EN_PROCESO, Etapa.ENTREVISTA)
PESOS_DE_ETAPA = (80, 15, 5)


@dataclass(frozen=True, slots=True)
class CandidatoDeCarga:
    """Todo lo de un candidato sintético, sorteado una sola vez.

    Un único punto de sorteo para que «determinista» sea comprobable: el índice
    entra, los bytes salen, y nada de lo que se guarda depende del orden en que
    se llame a los generadores.
    """

    indice: int
    nombre: str
    correo: str
    telefono: str
    cv_texto: str
    cv_actualizado_en: datetime
    creado_en: datetime
    etapa: Etapa
    postulada_en: datetime
    score: int
    razones: tuple[str, ...]


def _cv(rnd: random.Random, anios: int) -> str:
    """Un CV sintético de largo realista.

    El largo **es un parámetro de la medición y no un detalle**: la plantilla de
    la vista mete `cv_texto` completo dentro de un `<textarea>` por fila, así que
    estos caracteres son bytes de la respuesta. Se declara en `perf/MEDICION.md`
    §Entorno, junto con la sensibilidad del resultado a ese número.
    """
    lineas = [
        rnd.choice(TITULARES),
        f"{anios} años de experiencia en hospital.",
        "",
        "Experiencia:",
    ]
    for _ in range(rnd.randint(4, 7)):
        unidad = rnd.choice(UNIDADES).capitalize()
        camas = rnd.choice((80, 120, 180, 240, 300, 420))
        desde = rnd.randint(2012, 2022)
        lineas.append(
            f"- {unidad}, hospital de {camas} camas "
            f"({desde}-{desde + rnd.randint(1, 4)}). {rnd.choice(TAREAS)}."
        )
    lineas += ["", "Certificaciones:"]
    lineas += [
        f"- {cert}, vigente hasta {rnd.randint(2027, 2029)}."
        for cert in rnd.sample(CERTIFICACIONES, rnd.randint(2, 4))
    ]
    lineas += [
        "",
        "Formación:",
        f"- Licenciatura en enfermería, {rnd.randint(2008, 2021)}.",
        f"- Licencia RN número {rnd.randint(100000, 999999)}, Texas, vigente.",
        "",
        "Idiomas: español e inglés.",
        f"Disponibilidad: turno {rnd.choice(('nocturno', 'mixto', 'rotativo'))}, inicio inmediato.",
    ]
    return "\n".join(lineas) + "\n"


def datos_de(indice: int) -> CandidatoDeCarga:
    """El candidato número `indice`, siempre igual: el generador se siembra con él."""
    rnd = random.Random(f"criba-perf-{indice}")
    anios = rnd.randint(1, 18)
    nombre = f"{rnd.choice(NOMBRES)} {rnd.choice(APELLIDOS)} {rnd.choice(APELLIDOS)}"
    unidad = rnd.choice(UNIDADES)
    return CandidatoDeCarga(
        indice=indice,
        nombre=f"{nombre} [carga {indice:04d}]",
        correo=f"{PREFIJO_CORREO}{indice:04d}@{DOMINIO}",
        telefono=f"+1 713 555 {rnd.randint(1000, 9999)}",
        cv_texto=_cv(rnd, anios),
        cv_actualizado_en=HOY - timedelta(days=rnd.randint(1, 60)),
        creado_en=HOY - timedelta(days=rnd.randint(1, DIAS_DE_ANTIGUEDAD)),
        etapa=rnd.choices(ETAPAS, weights=PESOS_DE_ETAPA)[0],
        postulada_en=HOY
        - timedelta(days=rnd.randint(0, DIAS_DE_ANTIGUEDAD), hours=rnd.randint(0, 23)),
        score=rnd.randint(30, 97),
        razones=tuple(r.format(anios=anios, unidad=unidad) for r in rnd.sample(RAZONES, 3)),
    )


def _exigir_base_de_medicion() -> None:
    url = ajustes().url_bd
    if not url.endswith(f"/{BASE_ESPERADA}"):
        sys.exit(
            f"CRIBA_URL_BD apunta a {url!r} y esta siembra solo corre contra "
            f"{BASE_ESPERADA!r}. No se escribió nada."
        )


def _vacante_de_northstar(bd: Session, vacante_id: int) -> Vacante:
    empresa = bd.scalars(select(Empresa).where(Empresa.slug == SLUG)).one_or_none()
    if empresa is None:
        sys.exit(f"No hay empresa {SLUG!r} en la base. Corre primero la semilla de la plataforma.")
    vacante = bd.scalars(
        select(Vacante).where(Vacante.id == vacante_id, Vacante.empresa_id == empresa.id)
    ).one_or_none()
    if vacante is None:
        sys.exit(f"La vacante {vacante_id} no existe o no es de {SLUG!r}. No se escribió nada.")
    return vacante


def _postulados(bd: Session, empresa_id: int, vacante_id: int) -> int:
    return (
        bd.scalar(
            select(func.count(Postulacion.id)).where(
                Postulacion.empresa_id == empresa_id, Postulacion.vacante_id == vacante_id
            )
        )
        or 0
    )


def _repositorio_de_match(bd: Session, vacante_id: int) -> RepositorioDeMatch:
    return RepositorioDeMatch(bd, ContextoDeEmpresa.desde_la_vacante(bd, vacante_id))


def _con_score(bd: Session, vacante_id: int) -> int:
    """Cuántos candidatos de la vacante tienen score, **por el repositorio**.

    Un `select(func.count(…))` sobre `ScoreDeMatch` aquí sería más corto y sería
    una segunda puerta a las tablas de Match: la regla (a) de PR-04 la enumera
    sobre **todo** el repo y sin lista blanca, así que
    `tests/match/test_aislamiento.py::test_ninguna_consulta_de_match_se_construye_fuera_del_repositorio`
    falla —y hace bien— también por un script de medición. El conteo distinto se
    hace en Python sobre lo que devuelve `scores_de_vacante`: son 499 filas una
    vez al final de la siembra, no está en ningún camino caliente.
    """
    scores = _repositorio_de_match(bd, vacante_id).scores_de_vacante(vacante_id)
    return len({fila.candidato_id for fila in scores})


def sembrar(bd: Session, *, vacante_id: int = VACANTE, total: int = TOTAL) -> dict[str, int]:
    """Lleva la vacante a `total` postulaciones y devuelve el conteo de lo hecho."""
    vacante = _vacante_de_northstar(bd, vacante_id)
    empresa_id = vacante.empresa_id
    antes = _postulados(bd, empresa_id, vacante_id)

    ya = set(
        bd.scalars(
            select(Candidato.correo).where(
                Candidato.empresa_id == empresa_id,
                Candidato.correo.like(f"{PREFIJO_CORREO}%@{DOMINIO}"),
            )
        )
    )
    # Los índices que faltan, en orden: si alguien borró a mano el candidato 7,
    # la siguiente corrida vuelve a crear el 7 y no un 496.
    pendientes = [datos_de(i) for i in range(1, total + 1)]
    pendientes = [d for d in pendientes if d.correo not in ya][: max(0, total - antes)]

    filas: list[tuple[Candidato, CandidatoDeCarga]] = []
    for datos in pendientes:
        candidato = Candidato(
            empresa_id=empresa_id,
            nombre=datos.nombre,
            correo=datos.correo,
            telefono=datos.telefono,
            links=[],
            cv_texto=datos.cv_texto,
            cv_actualizado_en=datos.cv_actualizado_en,
            creado_en=datos.creado_en,
        )
        bd.add(candidato)
        filas.append((candidato, datos))
    bd.flush()

    for candidato, datos in filas:
        bd.add(
            Postulacion(
                empresa_id=empresa_id,
                candidato_id=candidato.id,
                vacante_id=vacante_id,
                etapa=datos.etapa,
                creada_en=datos.postulada_en,
            )
        )
    bd.flush()

    # El score por el mismo camino que lo escribe producción: el repositorio de
    # Match con contexto de empresa. Así la fila tiene la forma que la vista lee
    # —estado, idioma, razones— y no una inventada por este script.
    repo = _repositorio_de_match(bd, vacante_id)
    for candidato, datos in filas:
        repo.guardar_score(candidato.id, vacante_id, datos.score, datos.razones)
    bd.commit()

    return {
        "postulados_antes": antes,
        "candidatos_creados": len(filas),
        "scores_guardados": len(filas),
        "postulados_ahora": _postulados(bd, empresa_id, vacante_id),
        "con_score_ahora": _con_score(bd, vacante_id),
    }


def resumen(bd: Session, vacante_id: int, hecho: dict[str, int]) -> str:
    vacante = _vacante_de_northstar(bd, vacante_id)
    largos = list(
        bd.scalars(
            select(func.length(Candidato.cv_texto))
            .join(Postulacion, Postulacion.candidato_id == Candidato.id)
            .where(Postulacion.vacante_id == vacante_id, Candidato.cv_texto.is_not(None))
        )
    )
    lineas = [
        f"Base: {ajustes().url_bd}",
        f"Vacante {vacante_id}: {vacante.titulo}",
        "",
        *(f"  {clave:<20} {valor}" for clave, valor in hecho.items()),
        "",
        f"  cv_texto: {len(largos)} con texto, min {min(largos)}, "
        f"media {round(sum(largos) / len(largos))}, max {max(largos)} caracteres",
        f"  suma de cv_texto de la vacante: {sum(largos)} caracteres",
    ]
    return "\n".join(lineas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Siembra de carga para medir CA5.")
    parser.add_argument("--vacante", type=int, default=VACANTE)
    parser.add_argument("--total", type=int, default=TOTAL)
    args = parser.parse_args()

    _exigir_base_de_medicion()
    with Session(motor()) as bd:
        hecho = sembrar(bd, vacante_id=args.vacante, total=args.total)
        print(resumen(bd, args.vacante, hecho))


if __name__ == "__main__":
    main()
