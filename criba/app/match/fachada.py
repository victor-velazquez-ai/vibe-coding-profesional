"""La frontera entre la plataforma y Match.

Es **lo único importable desde `app/` fuera de `app/match/`** (PLAN.md §2, R3·I1;
regla (b) del test de enumeración de PR-04), y su superficie es cerrada por
naturaleza: lo que la plataforma puede hacer con Match es lo que esta lista dice,
no lo que una lista blanca de llamadores permita.

**PR-05 tomó la opción (b) de R3·I2** (la vista de la plataforma delega el listado
en Match), así que la superficie cerrada es de **cuatro** símbolos y
`listar_vacante` es uno de ellos. El porqué de la opción (b), en
`docs/prs/PR-05.md`.

**Las cuatro firmas reciben la sesión de la petición** (R6·I2, corregido por
PR-06): en esta plataforma la sesión viene por `Depends(crear_sesion)` y el
`commit()` lo hace la ruta, así que Match escribe en **su** transacción y no abre
ninguna propia. La superficie cerrada no cambia por esto: siguen siendo cuatro
símbolos, y la regla (b) del test de enumeración de PR-04 no se toca.

`borrar_candidato` todavía no trae conducta: existe para fijar la firma y falla a
propósito. Lo que hace llega en PR-18.
"""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.match.cola import trabajos as cola
from app.match.configuracion import ajustes_match
from app.match.routers.vacante import router as _router_de_match
from app.match.services.listado import listar_vacante

__all__ = ["borrar_candidato", "encolar", "listar_vacante", "montar"]


def montar(app: FastAPI) -> None:
    """Monta Match en la aplicación. La factoría no importa nada más de Match.

    **Con el interruptor global apagado no monta nada** —y apagado es su valor
    por omisión fuera de tests (R4·I1, R6·I5)—, así que los endpoints bajo
    `/match` no existen.

    **El alcance del no-op, enumerado (R6·B1):** el interruptor apaga **esto**
    —los endpoints bajo `/match`—, `encolar` y el bucle del ejecutor. Y **nunca**
    la vista de vacante de la plataforma: `listar_vacante` apagada devuelve la
    lista de hoy —por fecha de postulación, sin score, sin razones, sin orden por
    score y sin sección de pendientes—, que es la misma respuesta que CA18 define
    para el hiring manager y CA3 para Meridian. `GET /vacantes/{vacante_id}`
    responde **200 con el interruptor apagado, siempre**.
    """
    app.state.match_montado = ajustes_match().activo
    if not app.state.match_montado:
        return
    app.include_router(_router_de_match)


def encolar(bd: Session, vacante_id: int, candidato_id: int) -> None:
    """Encola el trabajo de puntuación del par (candidato, vacante).

    El `empresa_id` **no es un argumento**: lo deriva el repositorio de la fila de
    la vacante (PR-04, constructor «desde la vacante», R2·I5).

    `bd` es **la sesión de la petición** (R6·I2), la que la ruta recibe por
    `Depends(crear_sesion)`: el trabajo se inserta en la **misma transacción** que
    la escritura de la plataforma y aquí no se hace `commit()` —el `bd.commit()`
    sigue siendo de la ruta—. Con una sesión propia abierta por `motor()`, el
    `INSERT` en `match_trabajos` y el `UPDATE` del CV no compartirían transacción
    (trabajo huérfano o CV sin trabajo) y en los tests no vería lo sembrado
    dentro del savepoint de `tests/conftest.py`.

    Con el **interruptor global apagado** no encola nada y no toca la base de
    datos (R4·I1, R6·B1). La comprobación de activación **por empresa** entra
    dentro de esta misma función en PR-10 (D7, CA3).
    """
    cola.encolar(bd, vacante_id, candidato_id)


def borrar_candidato(bd: Session, candidato_id: int) -> None:
    """Borra todo lo que Match derivó de un candidato, recorriendo el inventario.

    La llama el **procedimiento de borrado de la plataforma**
    (`RepositorioEmpresa.borrar_candidato`), antes de borrar la fila del
    candidato, y por eso recibe **su misma sesión** (R6·I2): el recorrido y el
    borrado de la fila del candidato son una sola transacción. Llega en PR-18
    (CA16, D15, R2·B2).
    """
    raise NotImplementedError("Llega en PR-18 (borrado del candidato).")
