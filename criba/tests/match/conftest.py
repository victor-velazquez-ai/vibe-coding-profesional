"""PR-03 · fixtures de dos empresas, sesión y doble del proveedor.

Dos empresas —**Northstar con Match activo, Meridian sin anexo** (D7)— con un
reclutador, un admin y un hiring manager cada una, y **un único staff de Criba
sin empresa**: lo único que el CHECK `ck_usuarios_staff_sin_empresa` permite y lo
que D6 dice (R6·M1). El helper de sesión entra por **`POST /entrar`**, el camino
de producción, así que la de soporte queda atada a una empresa, con
`es_soporte=True` y su fila en `accesos_soporte` (hecho 3 de PR-01).

Todo el material es **sintético** (D3 modificado, D15, F12).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from itertools import count
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.match.configuracion import VARIABLE_DE_EMPRESAS, VARIABLE_GLOBAL, ajustes_match
from app.match.repositories.contexto import ContextoDeEmpresa
from app.match.repositories.match_repo import RepositorioDeMatch
from app.match.repositories.modelos import ScoreDeMatch
from app.match.routers.vacante import PREFIJO
from app.plataforma.modelos import Candidato, Empresa, Postulacion, Rol, Usuario, Vacante
from app.plataforma.seguridad import hash_contrasena
from app.plataforma.sesion import ContextoEmpresa
from tests.dobles.proveedor import RAZONES, ProveedorContado

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
# Los dos últimos los añade PR-08: la guardia de «el archivo se declara
# sintético» de PR-03 tiene que cubrir también las fixtures de PII, que son las
# que más se parecen a un CV real (F12).
# Los dos últimos los añade la auditoría de CVs sintéticos del 22-nov-2026 (las
# dos fugas de CA2: el nombre sin acentos y el archivo de la foto adjunta).
ARCHIVOS_DE_CV = (
    "enfermeria_es",
    "enfermeria_en",
    "pii_en_texto_libre_es",
    "pii_en_texto_libre_en",
    "pii_sin_acentos_es",
    "pii_foto_adjunta_es",
)
CONTRASENA = "prueba1234"
DESCRIPCION = "Piso de medicina interna, turno nocturno. Licencia RN vigente en Texas."
_ROLES = ((Rol.RECLUTADOR, "rec"), (Rol.ADMIN_EMPRESA, "adm"), (Rol.HIRING_MANAGER, "hm"))
_SECUENCIA = count(1)


def cv(nombre: str) -> str:
    return (FIXTURES / f"cv_{nombre}.md").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _hash() -> str:
    """`scrypt` una sola vez por sesión de tests: son siete usuarios por test."""
    return hash_contrasena(CONTRASENA)


@dataclass(frozen=True, slots=True)
class EmpresaDePrueba:
    """Una empresa con lo mínimo para que un par (candidato, vacante) exista."""

    empresa: Empresa
    reclutador: Usuario
    admin: Usuario
    hiring_manager: Usuario
    vacante: Vacante
    candidato: Candidato

    @property
    def slug(self) -> str:
        return self.empresa.slug


SesionDeSoporte = Callable[[EmpresaDePrueba], TestClient]
Entrar = Callable[..., TestClient]


def _crear_empresa(sesion: Session, nombre: str, slug: str, archivo: str) -> EmpresaDePrueba:
    empresa = Empresa(nombre=nombre, slug=slug)
    sesion.add(empresa)
    sesion.flush()
    usuarios = [
        Usuario(
            empresa_id=empresa.id,
            usuario=f"{prefijo}.{slug}",
            nombre=f"{rol.value} de prueba · {nombre}",
            rol=rol,
            hash_contrasena=_hash(),
        )
        for rol, prefijo in _ROLES
    ]
    vacante = Vacante(
        empresa_id=empresa.id,
        titulo="Enfermera/o de piso · turno nocturno",
        descripcion=DESCRIPCION,
        ciudad="Houston, TX",
    )
    candidato = Candidato(
        empresa_id=empresa.id,
        nombre="Valentina Sintetica",
        correo=f"valentina@{slug}.test",
        telefono="+1 713 555 0100",
        links=[],
        cv_texto=cv(archivo),
    )
    sesion.add_all([*usuarios, vacante, candidato])
    sesion.flush()
    sesion.add(Postulacion(empresa_id=empresa.id, candidato_id=candidato.id, vacante_id=vacante.id))
    sesion.flush()
    return EmpresaDePrueba(empresa, *usuarios, vacante, candidato)


@pytest.fixture
def activar_match(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[str], None]]:
    """El estado por empresa de R4·I1: encendido **solo** donde el test lo pida."""
    activadas: set[str] = set()
    monkeypatch.delenv(VARIABLE_DE_EMPRESAS, raising=False)
    ajustes_match.cache_clear()

    def activar(slug: str) -> None:
        activadas.add(slug)
        monkeypatch.setenv(VARIABLE_DE_EMPRESAS, ",".join(sorted(activadas)))
        ajustes_match.cache_clear()

    yield activar
    ajustes_match.cache_clear()


@pytest.fixture
def northstar(sesion: Session, activar_match: Callable[[str], None]) -> EmpresaDePrueba:
    """Match activo y anexo de subprocesador firmado (D7)."""
    empresa = _crear_empresa(sesion, "Northstar Health", "northstar-health", "enfermeria_es")
    activar_match(empresa.slug)
    return empresa


@pytest.fixture
def meridian(sesion: Session, activar_match: Callable[[str], None]) -> EmpresaDePrueba:
    """**Sin anexo**: Match apagado (D7, CA3). No llamar a `activar_match` *es* la aserción."""
    return _crear_empresa(sesion, "Meridian Logistics", "meridian-logistics", "enfermeria_en")


@pytest.fixture
def staff(sesion: Session) -> Usuario:
    """Un único staff de Criba, **sin empresa** (D6, R6·M1)."""
    usuario = Usuario(
        empresa_id=None,
        usuario="soporte",
        nombre="Soporte",
        rol=Rol.STAFF_CRIBA,
        hash_contrasena=_hash(),
    )
    sesion.add(usuario)
    sesion.flush()
    return usuario


@pytest.fixture
def entrar(aplicacion: FastAPI) -> Iterator[Entrar]:
    """Abre una sesión por `POST /entrar`. Varias a la vez, cada una su cookie."""
    abiertos: list[TestClient] = []

    def _entrar(usuario: Usuario, empresa: Empresa | None = None) -> TestClient:
        cliente = TestClient(aplicacion)
        abiertos.append(cliente)
        datos = {"usuario": usuario.usuario, "contrasena": CONTRASENA}
        if empresa is not None:
            datos["empresa"] = empresa.slug
        respuesta = cliente.post("/entrar", data=datos, follow_redirects=False)
        assert respuesta.status_code == 303, f"el login falló con {respuesta.status_code}"
        return cliente

    yield _entrar
    for cliente in abiertos:
        cliente.close()


@pytest.fixture
def sesion_reclutador_northstar(entrar: Entrar, northstar: EmpresaDePrueba) -> TestClient:
    return entrar(northstar.reclutador)


@pytest.fixture
def sesion_soporte(entrar: Entrar, staff: Usuario) -> SesionDeSoporte:
    """Sesión de soporte sobre una empresa, por el camino de producción (R6·M1)."""
    return lambda empresa: entrar(staff, empresa.empresa)


@pytest.fixture
def proveedor_contado() -> ProveedorContado:
    """El doble por omisión: cuenta llamadas y no sale de la red."""
    return ProveedorContado()


# --- PR-05 · la vista de vacante -------------------------------------------


@pytest.fixture
def apagar_match(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """El interruptor **global** apagado, que es su valor por omisión fuera de
    tests (R6·I5). Se pide **antes** que `aplicacion`: `montar` lo lee al crear
    la app, así que el orden de los parámetros del test es la aserción."""
    monkeypatch.delenv(VARIABLE_GLOBAL, raising=False)
    ajustes_match.cache_clear()
    yield
    ajustes_match.cache_clear()


def rutas_de_match(aplicacion: FastAPI) -> list[str]:
    """Las rutas montadas bajo `/match`, **enumeradas y no escritas a mano**.

    El recorrido de CA1 y el 403 de CA18 las recorren, así que un endpoint nuevo
    entra en los dos tests sin que nadie los toque (F34).
    """
    return sorted({ruta for ruta in _caminos(aplicacion.routes) if ruta.startswith(PREFIJO)})


def _caminos(rutas: Iterable[object]) -> Iterator[str]:
    """Las rutas de la app, **también las de los routers incluidos**.

    En starlette 1.x `include_router` deja un `_IncludedRouter` en `app.routes` y
    los `path` viven dentro, en su `original_router`. Mirar solo `app.routes`
    devuelve una lista vacía, y un recorrido vacío pasa sin decir nada: es el
    defecto que la aserción de rutas de PR-04 tenía y que este helper cierra.
    """
    for ruta in rutas:
        incluido = getattr(ruta, "original_router", None)
        if incluido is not None:
            yield from _caminos(incluido.routes)
        camino = getattr(ruta, "path", None)
        if isinstance(camino, str):
            yield camino


def repo_de(sesion: Session, empresa: EmpresaDePrueba) -> RepositorioDeMatch:
    """El repositorio de Match de esa empresa, con el contexto de la cookie.

    Es la forma en que los tests observan `match_*` **sin construir SQL** y por
    empresa (R6·I3): «cero filas» global pasaría aunque la fila se hubiera
    escrito con el `empresa_id` cambiado.
    """
    return RepositorioDeMatch(
        sesion,
        ContextoDeEmpresa.desde_la_peticion(
            ContextoEmpresa(empresa_id=empresa.empresa.id, es_soporte=False)
        ),
    )


def sembrar_score(
    sesion: Session, empresa: EmpresaDePrueba, puntos: int = 72, candidato: Candidato | None = None
) -> ScoreDeMatch:
    """Un score **ya guardado**, por el repositorio y con contexto de empresa.

    Ya guardado es la mitad de CA4: la vista se construye solo con esto. Quién lo
    calcula es de PR-06; el idioma, el declarado en PR-03.
    """
    repo = RepositorioDeMatch(
        sesion, ContextoDeEmpresa.desde_la_vacante(sesion, empresa.vacante.id)
    )
    elegido = candidato or empresa.candidato
    return repo.guardar_score(elegido.id, empresa.vacante.id, puntos, RAZONES)


def sembrar_candidatos(
    sesion: Session, empresa: EmpresaDePrueba, cuantos: int, *, postular: bool = True
) -> list[Candidato]:
    """Candidatos sintéticos de la empresa, con o sin postulación a su vacante."""
    # El número sale de un contador global y no de `range(cuantos)`: dos llamadas
    # en el mismo test chocarían con `uq_candidatos_empresa_correo`.
    nuevos = [
        Candidato(
            empresa_id=empresa.empresa.id,
            nombre=f"Candidato sintético {indice}",
            correo=f"sintetico-{indice}@{empresa.slug}.test",
            links=[],
            cv_texto="CV sintético de relleno.",
        )
        for indice in (next(_SECUENCIA) for _ in range(cuantos))
    ]
    sesion.add_all(nuevos)
    sesion.flush()
    if postular:
        sesion.add_all(
            [
                Postulacion(
                    empresa_id=empresa.empresa.id,
                    candidato_id=candidato.id,
                    vacante_id=empresa.vacante.id,
                )
                for candidato in nuevos
            ]
        )
        sesion.flush()
    return nuevos
