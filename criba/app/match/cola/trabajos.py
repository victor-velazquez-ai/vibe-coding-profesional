"""Encolar y tomar trabajos. El `SELECT … FOR UPDATE SKIP LOCKED` vive en
`repositories/match_repo.py` (PR-06, PR-14, PLAN.md §2 R1·I1).

Este módulo **no construye ninguna consulta**: le pide métodos de negocio al
repositorio, que es el único punto de acceso a datos de Match (CA1, D4, R1·I1).

Lo que `encolar` hace, y lo que todavía no:

- deriva el `empresa_id` del **constructor de contexto «desde la vacante»**
  (PR-04, R2·I5). No es un argumento: el gancho de subida de CV corre antes de
  que exista la fila de la cola y la ruta de postulación pública no tiene cookie
  de empresa, así que un `empresa_id` de llamador es el que el siguiente omite o
  confunde (§4 de `docs/arquitectura.md`, D4);
- escribe en **la transacción de la ruta** y no hace `commit()` (R6·I2);
- **comprueba la activación por empresa antes del `INSERT`** (PR-10, R2·M2, D7):
  CA3 prohíbe «ningún registro de Match» y no solo «ninguna llamada», así que la
  comprobación no puede esperar a que el ejecutor tome la fila. La decide el
  repositorio —`empresa_activada`, el punto único de acceso a datos—, no esta
  función y no el gancho que la llama: los dos ganchos de PR-06 y el comando de
  la carga (PR-16) entran por aquí y **ninguno trae regla propia**;
- **no toma lease, no cuenta intentos y no reintenta**: PR-14.
"""

from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app.match.configuracion import ajustes_match
from app.match.repositories.contexto import (
    ContextoDeEmpresa,
    ContextoDeSistema,
    OperacionDeSistema,
)
from app.match.repositories.match_repo import RepositorioDeMatch, RepositorioDeSistema
from app.match.repositories.modelos import TrabajoDeMatch
from app.plataforma.repositorio import RepositorioEmpresa

LARGO_DEL_HASH = 16


def clave_de_idempotencia(candidato_id: int, vacante_id: int, cv: str | None, idioma: str) -> str:
    """ADR-001 §Decisión 3: (candidato, vacante, **hash de CV**, versión de prompt).

    El cuarto componente de la ADR es la **versión de prompt**, que en la Etapa 0
    no existe: no hay prompt hasta PR-09 y su versión se persiste en PR-12. El
    cuarto componente que este paso sí tiene es el **idioma** del trabajo, que es
    parte de la clave natural del score desde PR-02 (R2·I4). Sustituirlo por la
    versión de prompt es de PR-12; precisar la clave de la ADR tiene su propio PR
    (R1·B2) y este módulo no lo adelanta.

    Del CV va el **hash**, nunca el texto: D15 y F12 valen también para una clave.
    """
    huella = hashlib.sha256((cv or "").encode("utf-8")).hexdigest()[:LARGO_DEL_HASH]
    return f"{candidato_id}:{vacante_id}:{huella}:{idioma}"


def encolar(bd: Session, vacante_id: int, candidato_id: int) -> TrabajoDeMatch | None:
    """Encola el par (candidato, vacante). `None` si Match está apagado.

    Con el **interruptor global apagado** —su valor por omisión fuera de tests
    (R4·I1, R6·I5)— no toca la base de datos: ni una fila, ni una consulta. Eso
    es lo que hace que la regla 1.7 no dependa de la memoria de nadie entre el
    5-dic y la operación de PR-16.

    Y `None` también **sin la activación por empresa** (D7, CA3): el `INSERT` no
    se hace. Devolver `None` y no levantar una excepción es deliberado y es la
    mitad de D7 que se lee mal: D7 apaga Match para Meridian, no a Meridian. Un
    `encolar` que explotara convertiría CA3 en un 500 en la ruta de subida de CV
    de las 39 empresas sin anexo, que siguen siendo clientes de Criba y siguen
    subiendo CVs todos los días.
    """
    if not ajustes_match().activo:
        return None

    contexto = ContextoDeEmpresa.desde_la_vacante(bd, vacante_id, candidato_id=candidato_id)
    repo = RepositorioDeMatch(bd, contexto)
    # D7 y CA3, **antes de cualquier escritura** (PR-10, R2·I2): quien decide es
    # el repositorio y el contexto es el de la fila de la vacante, así que este
    # camino no necesita cookie —el gancho de postulación no la tiene— y el
    # `empresa_id` sobre el que se evalúa D7 no lo elige ningún llamador.
    if not repo.empresa_activada():
        return None

    candidato = repo.candidato(candidato_id)
    empresa = RepositorioEmpresa(bd, contexto.empresa_id).empresa()
    idioma = ajustes_match().idioma_de(empresa.slug if empresa is not None else "")

    clave = clave_de_idempotencia(
        candidato_id, vacante_id, candidato.cv_texto if candidato else None, idioma
    )
    # El esquema ya trae `uq_match_trabajos_idempotencia` (PR-02), así que un CV
    # subido dos veces sin cambios chocaría con la restricción y la ruta
    # respondería 500. Lo mínimo que PR-06 necesita es no duplicar: la carrera
    # entre dos peticiones simultáneas y el reintento son de PR-14.
    existente = repo.trabajo_por_clave(clave)
    if existente is not None:
        return existente
    return repo.crear_trabajo(candidato_id, vacante_id, clave, idioma=idioma)


def tomar(bd: Session) -> TrabajoDeMatch | None:
    """El siguiente trabajo pendiente, con el **contexto de sistema** (a).

    Es la primera de las tres operaciones sin empresa de PR-04: al tomar la fila
    todavía no se sabe de qué empresa es. El `empresa_id` sale **después**, de la
    fila ya tomada (`ContextoDeEmpresa.desde_el_trabajo`, F5, §5.3).
    """
    sistema = RepositorioDeSistema(bd, ContextoDeSistema(OperacionDeSistema.TOMAR_TRABAJO))
    return sistema.siguiente_trabajo_pendiente()
