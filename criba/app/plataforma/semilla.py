"""Datos de desarrollo de la plataforma.

    uv run python -m app.plataforma.semilla

**Todo es sintético.** Nombres, correos, teléfonos y textos de CV están
inventados para este entorno: ningún dato real de cliente entra en el repo
(D3 modificado, D15, F12). Los correos usan el dominio reservado `.test`.

La contraseña de cada usuario es su nombre de usuario + `1234`
(`marcus1234`, `sofia1234`, …). Es un entorno de desarrollo y nada más.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.configuracion import ajustes
from app.db import Base, motor
from app.migracion import aplicar_migraciones
from app.plataforma.modelos import (
    AccesoSoporte,
    Candidato,
    Empresa,
    Etapa,
    NotaEntrevista,
    Postulacion,
    Rol,
    Usuario,
    Vacante,
)
from app.plataforma.seguridad import hash_contrasena

HOY = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)


def _cv(titular: str, anios: int, lineas: list[str]) -> str:
    cuerpo = "\n".join(f"- {linea}" for linea in lineas)
    return f"{titular}\n{anios} años de experiencia.\n\nExperiencia:\n{cuerpo}\n"


@dataclass(slots=True)
class CandidatoSemilla:
    nombre: str
    correo: str
    telefono: str
    links: list[str]
    cv_texto: str | None
    # Postulaciones: (índice de vacante dentro de la empresa, etapa, días de antigüedad)
    postulaciones: list[tuple[int, Etapa, int]] = field(default_factory=list)


@dataclass(slots=True)
class VacanteSemilla:
    titulo: str
    ciudad: str
    descripcion: str


@dataclass(slots=True)
class EmpresaSemilla:
    nombre: str
    slug: str
    usuarios: list[tuple[str, str, Rol]]
    vacantes: list[VacanteSemilla]
    candidatos: list[CandidatoSemilla]


NORTHSTAR = EmpresaSemilla(
    nombre="Northstar Health",
    slug="northstar-health",
    usuarios=[
        ("marcus", "Marcus Delgado Ortiz", Rol.RECLUTADOR),
        ("hm.northstar", "Rhea Lindqvist", Rol.HIRING_MANAGER),
        ("admin.northstar", "Clara Benavides Rooney", Rol.ADMIN_EMPRESA),
    ],
    vacantes=[
        VacanteSemilla(
            titulo="Enfermera/o de piso · turno nocturno",
            ciudad="Houston, TX",
            descripcion=(
                "Cuidado directo de pacientes en piso de medicina interna, turno nocturno de "
                "12 horas. Se requiere licencia de enfermería vigente en Texas (RN), soporte "
                "vital básico y al menos dos años en hospital. Se valora experiencia en "
                "telemetría y atención bilingüe español/inglés."
            ),
        ),
        VacanteSemilla(
            titulo="Coordinador/a administrativo de admisiones",
            ciudad="Dallas, TX",
            descripcion=(
                "Coordinación del área de admisiones: verificación de seguros, programación de "
                "citas y expedientes. Se requiere manejo de sistemas de expediente clínico "
                "electrónico, atención al paciente y bachillerato concluido."
            ),
        ),
        VacanteSemilla(
            titulo="Ingeniero/a de soporte de TI clínica",
            ciudad="Austin, TX",
            descripcion=(
                "Soporte de segundo nivel a los sistemas clínicos de la red de hospitales: "
                "integraciones HL7, estaciones de trabajo de piso y guardias rotativas. Se "
                "requiere Linux, redes y disposición a guardias."
            ),
        ),
    ],
    candidatos=[
        CandidatoSemilla(
            nombre="Alma Rivas Cordero",
            correo="alma.rivas@ejemplo.test",
            telefono="+1 713 555 0142",
            links=["https://ejemplo.test/perfil/alma-rivas"],
            cv_texto=_cv(
                "Enfermera registrada (RN), licencia de Texas vigente",
                7,
                [
                    "Piso de medicina interna, turno nocturno, hospital de 300 camas",
                    "Telemetría y manejo de vía central",
                    "Atención bilingüe español/inglés",
                    "Soporte vital básico y avanzado vigentes",
                ],
            ),
            postulaciones=[(0, Etapa.ENTREVISTA, 12)],
        ),
        CandidatoSemilla(
            nombre="Darnell Whitaker",
            correo="darnell.whitaker@ejemplo.test",
            telefono="+1 713 555 0188",
            links=[],
            cv_texto=_cv(
                "Enfermero registrado (RN), licencia multiestado",
                4,
                [
                    "Urgencias, turnos rotativos",
                    "Triaje y estabilización",
                    "Capacitación de personal nuevo",
                ],
            ),
            postulaciones=[(0, Etapa.EN_PROCESO, 9)],
        ),
        CandidatoSemilla(
            nombre="Ingrid Solórzano Paz",
            correo="ingrid.solorzano@ejemplo.test",
            telefono="+1 281 555 0213",
            links=["https://ejemplo.test/perfil/ingrid-solorzano"],
            cv_texto=_cv(
                "Enfermera registrada (RN), especialidad en cuidados intensivos",
                11,
                [
                    "Unidad de cuidados intensivos adultos",
                    "Ventilación mecánica y monitoreo hemodinámico",
                    "Supervisión de turno nocturno",
                    "Docencia clínica a residentes de enfermería",
                ],
            ),
            postulaciones=[(0, Etapa.POSTULADA, 5)],
        ),
        CandidatoSemilla(
            nombre="Tobías Nkemelu",
            correo="tobias.nkemelu@ejemplo.test",
            telefono="+1 832 555 0301",
            links=[],
            cv_texto=None,  # sin CV: el caso que la vista tiene que mostrar con motivo
            postulaciones=[(0, Etapa.POSTULADA, 3)],
        ),
        CandidatoSemilla(
            nombre="Priscila Okonjo-Vega",
            correo="priscila.okonjo@ejemplo.test",
            telefono="+1 214 555 0477",
            links=["https://ejemplo.test/perfil/priscila-okonjo"],
            cv_texto=_cv(
                "Enfermera registrada (RN) con experiencia administrativa",
                6,
                [
                    "Piso de medicina interna, turno mixto",
                    "Coordinación de altas y traslados",
                    "Verificación de seguros y expediente electrónico",
                ],
            ),
            # Dos postulaciones abiertas en la misma empresa: el caso de R2·I4.
            postulaciones=[(0, Etapa.POSTULADA, 2), (1, Etapa.EN_PROCESO, 8)],
        ),
        CandidatoSemilla(
            nombre="Héctor Balderas Quiroz",
            correo="hector.balderas@ejemplo.test",
            telefono="+1 214 555 0520",
            links=[],
            cv_texto=_cv(
                "Coordinador administrativo en salud",
                9,
                [
                    "Admisiones de hospital, 40 camas",
                    "Verificación de seguros y preautorizaciones",
                    "Programación de quirófano",
                ],
            ),
            postulaciones=[(1, Etapa.ENTREVISTA, 14)],
        ),
        CandidatoSemilla(
            nombre="Noemí Ferreira Lund",
            correo="noemi.ferreira@ejemplo.test",
            telefono="+1 469 555 0634",
            links=["https://ejemplo.test/perfil/noemi-ferreira"],
            cv_texto=_cv(
                "Asistente administrativa bilingüe",
                3,
                [
                    "Recepción y agenda de consultorio multiespecialidad",
                    "Expediente clínico electrónico",
                    "Facturación a aseguradoras",
                ],
            ),
            postulaciones=[(1, Etapa.POSTULADA, 4)],
        ),
        CandidatoSemilla(
            nombre="Sandra Appiah",
            correo="sandra.appiah@ejemplo.test",
            telefono="+1 469 555 0711",
            links=[],
            cv_texto=None,  # segundo caso sin CV
            postulaciones=[(1, Etapa.POSTULADA, 1)],
        ),
        CandidatoSemilla(
            nombre="Yusuf Barrantes",
            correo="yusuf.barrantes@ejemplo.test",
            telefono="+1 512 555 0808",
            links=["https://ejemplo.test/perfil/yusuf-barrantes"],
            cv_texto=_cv(
                "Ingeniero de soporte de sistemas clínicos",
                8,
                [
                    "Integraciones HL7 entre laboratorio y expediente electrónico",
                    "Linux, redes y monitoreo",
                    "Guardias rotativas de 24 horas",
                ],
            ),
            postulaciones=[(2, Etapa.ENTREVISTA, 11)],
        ),
        CandidatoSemilla(
            nombre="Lucía Montenegro Dahl",
            correo="lucia.montenegro@ejemplo.test",
            telefono="+1 512 555 0915",
            links=[],
            cv_texto=_cv(
                "Administradora de sistemas",
                5,
                [
                    "Estaciones de trabajo y directorio activo",
                    "Automatización con Python y Ansible",
                    "Mesa de ayuda de segundo nivel",
                ],
            ),
            postulaciones=[(2, Etapa.EN_PROCESO, 7)],
        ),
        CandidatoSemilla(
            nombre="Emeka Rosenthal",
            correo="emeka.rosenthal@ejemplo.test",
            telefono="+1 737 555 1022",
            links=["https://ejemplo.test/perfil/emeka-rosenthal"],
            cv_texto=_cv(
                "Especialista en redes hospitalarias",
                12,
                [
                    "Redes de campus en tres hospitales",
                    "Segmentación de dispositivos médicos",
                    "Cumplimiento HIPAA en la capa de red",
                ],
            ),
            postulaciones=[(2, Etapa.POSTULADA, 6)],
        ),
        CandidatoSemilla(
            nombre="Fernanda Isaza Trejo",
            correo="fernanda.isaza@ejemplo.test",
            telefono="+1 737 555 1130",
            links=[],
            cv_texto=_cv(
                "Soporte técnico de aplicaciones clínicas",
                2,
                [
                    "Mesa de ayuda de primer nivel",
                    "Capacitación a personal de piso",
                    "Documentación de incidentes",
                ],
            ),
            postulaciones=[(2, Etapa.POSTULADA, 1)],
        ),
    ],
)

MERIDIAN = EmpresaSemilla(
    nombre="Meridian Logistics",
    slug="meridian-logistics",
    usuarios=[("sofia", "Sofía Narváez Pineda", Rol.RECLUTADOR)],
    vacantes=[
        VacanteSemilla(
            titulo="Supervisor/a de patio · turno mixto",
            ciudad="Dallas, TX",
            descripcion=(
                "Supervisión de maniobras de patio y andenes: asignación de rampas, control de "
                "tiempos de carga y seguridad del personal. Se requiere experiencia en centro "
                "de distribución y manejo de sistemas de gestión de almacén."
            ),
        )
    ],
    candidatos=[
        CandidatoSemilla(
            nombre="Bruno Cafferata Lima",
            correo="bruno.cafferata@ejemplo.test",
            telefono="+1 214 555 2041",
            links=[],
            cv_texto=_cv(
                "Supervisor de centro de distribución",
                10,
                [
                    "Turnos de 60 personas en andén",
                    "Indicadores de tiempo de carga y descarga",
                    "Seguridad e higiene en patio de maniobras",
                ],
            ),
            postulaciones=[(0, Etapa.ENTREVISTA, 10)],
        ),
        CandidatoSemilla(
            nombre="Xiomara Beltrán Ruiz",
            correo="xiomara.beltran@ejemplo.test",
            telefono="+52 81 5555 3366",
            links=["https://ejemplo.test/perfil/xiomara-beltran"],
            cv_texto=_cv(
                "Coordinadora de logística de transporte",
                6,
                [
                    "Planeación de rutas Monterrey-Dallas",
                    "Sistema de gestión de almacén",
                    "Trato con transportistas y aduanas",
                ],
            ),
            postulaciones=[(0, Etapa.EN_PROCESO, 6)],
        ),
        CandidatoSemilla(
            nombre="Adrián Villalpando Sosa",
            correo="adrian.villalpando@ejemplo.test",
            telefono="+1 469 555 4188",
            links=[],
            cv_texto=None,
            postulaciones=[(0, Etapa.POSTULADA, 2)],
        ),
    ],
)

EMPRESAS = (NORTHSTAR, MERIDIAN)

STAFF_CRIBA = ("soporte", "Equipo de Soporte Criba")

# Notas de entrevista sintéticas: (correo del candidato, índice de postulación, texto)
NOTAS = (
    (
        "alma.rivas@ejemplo.test",
        0,
        "Entrevista telefónica de 20 min. Disponible para turno nocturno desde enero. "
        "Pide confirmación del diferencial de nocturno.",
    ),
    (
        "hector.balderas@ejemplo.test",
        0,
        "Buena lectura del flujo de admisiones. Queda pendiente la referencia del hospital "
        "anterior.",
    ),
    (
        "yusuf.barrantes@ejemplo.test",
        0,
        "Conoce HL7 de primera mano. Pregunta por la rotación de guardias.",
    ),
)


def _vaciar(sesion: Session) -> None:
    """Vacía las tablas y **reinicia los contadores de id**.

    Con `DELETE` las secuencias no se reinician y los IDs suben en cada
    resiembra: la vacante de enfermería deja de ser la 1 y cualquier nota
    («abre /vacantes/1») envejece mal.
    """
    tablas = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    sesion.execute(text(f"TRUNCATE {tablas} RESTART IDENTITY CASCADE"))


def sembrar(sesion: Session) -> None:
    _vaciar(sesion)
    sesion.flush()

    candidatos_por_correo: dict[str, Candidato] = {}
    postulaciones_por_candidato: dict[str, list[Postulacion]] = {}
    reclutador_por_empresa: dict[int, Usuario] = {}

    for datos in EMPRESAS:
        empresa = Empresa(nombre=datos.nombre, slug=datos.slug, creada_en=HOY - timedelta(days=400))
        sesion.add(empresa)
        sesion.flush()

        for nombre_usuario, nombre, rol in datos.usuarios:
            usuario = Usuario(
                empresa_id=empresa.id,
                usuario=nombre_usuario,
                nombre=nombre,
                rol=rol,
                hash_contrasena=hash_contrasena(f"{nombre_usuario}1234"),
            )
            sesion.add(usuario)
            sesion.flush()
            if rol is Rol.RECLUTADOR and empresa.id not in reclutador_por_empresa:
                reclutador_por_empresa[empresa.id] = usuario

        vacantes: list[Vacante] = []
        for indice, v in enumerate(datos.vacantes):
            vacante = Vacante(
                empresa_id=empresa.id,
                titulo=v.titulo,
                descripcion=v.descripcion,
                ciudad=v.ciudad,
                creada_en=HOY - timedelta(days=30 - indice * 4),
            )
            sesion.add(vacante)
            vacantes.append(vacante)
        sesion.flush()

        for c in datos.candidatos:
            candidato = Candidato(
                empresa_id=empresa.id,
                nombre=c.nombre,
                correo=c.correo,
                telefono=c.telefono,
                links=c.links,
                cv_texto=c.cv_texto,
                cv_actualizado_en=(HOY - timedelta(days=20)) if c.cv_texto else None,
                creado_en=HOY - timedelta(days=25),
            )
            sesion.add(candidato)
            sesion.flush()
            candidatos_por_correo[c.correo] = candidato

            postulaciones_por_candidato[c.correo] = []
            for indice_vacante, etapa, dias in c.postulaciones:
                postulacion = Postulacion(
                    empresa_id=empresa.id,
                    candidato_id=candidato.id,
                    vacante_id=vacantes[indice_vacante].id,
                    etapa=etapa,
                    creada_en=HOY - timedelta(days=dias),
                )
                sesion.add(postulacion)
                postulaciones_por_candidato[c.correo].append(postulacion)
            sesion.flush()

    staff = Usuario(
        empresa_id=None,
        usuario=STAFF_CRIBA[0],
        nombre=STAFF_CRIBA[1],
        rol=Rol.STAFF_CRIBA,
        hash_contrasena=hash_contrasena(f"{STAFF_CRIBA[0]}1234"),
    )
    sesion.add(staff)
    sesion.flush()

    for correo, indice, texto in NOTAS:
        candidato = candidatos_por_correo[correo]
        postulacion = postulaciones_por_candidato[correo][indice]
        autor = reclutador_por_empresa[candidato.empresa_id]
        sesion.add(
            NotaEntrevista(
                empresa_id=candidato.empresa_id,
                postulacion_id=postulacion.id,
                autor_id=autor.id,
                texto=texto,
                creada_en=HOY - timedelta(days=2),
            )
        )

    sesion.commit()


def resumen(sesion: Session) -> str:
    lineas = ["Semilla aplicada. Datos sintéticos.", ""]
    for tabla in (Empresa, Usuario, Vacante, Candidato, Postulacion, NotaEntrevista, AccesoSoporte):
        total = sesion.scalar(select(func.count()).select_from(tabla))
        lineas.append(f"  {tabla.__tablename__:<18} {total}")
    lineas += [
        "",
        "Usuarios (contraseña = usuario + '1234'):",
        "  marcus           reclutador      Northstar Health",
        "  hm.northstar     hiring manager  Northstar Health",
        "  admin.northstar  admin empresa   Northstar Health",
        "  sofia            reclutadora     Meridian Logistics",
        "  soporte          staff de Criba  elige empresa al entrar",
        "",
        "Arranca la app con:  uv run python -m uvicorn app.main:app --reload",
    ]
    return "\n".join(lineas)


def main() -> None:
    url = ajustes().url_bd
    print(f"Migrando {url} …")
    aplicar_migraciones(url)
    with Session(motor()) as sesion:
        sembrar(sesion)
        print(resumen(sesion))


if __name__ == "__main__":
    main()
