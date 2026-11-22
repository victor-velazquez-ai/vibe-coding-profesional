"""MatchService: pseudonimiza, llama al proveedor, guarda score o motivo (PR-06, PR-08).

La versión mínima de la Etapa 0, con lo que **no** hace dicho en voz alta:

- **no pseudonimiza**: el payload es el texto del CV tal cual, y eso solo es
  aceptable porque el único proveedor que existe es el MOCK, que no sale del
  proceso (regla 1.5). La frontera de tipos —un payload que el cliente del
  proveedor no pueda construir sin pasar por el pseudonimizador— es **PR-08**, y
  hasta entonces no se habilita ningún cliente real;
- **no escribe la fila de auditoría por score** (hash del CV, versión de prompt y
  de modelo): PR-12;
- **no cuenta el gasto ni mira el techo**: PR-13;
- **no construye el prompt**: hoy no hay prompt, y de ahí sale el hueco de la
  clave de idempotencia que `cola/trabajos.py` declara.

Lo que sí hace, y es de este paso: **CA13 en el estado**. O hay score, o hay
«sin score» con su motivo visible; nunca un cero en lugar de un score. Un
candidato sin texto de CV es el caso corriente de esa segunda mitad (F21) y la
razón de que CA20 pida motivo y no una celda vacía.
"""

from __future__ import annotations

from app.match.configuracion import Proveedor
from app.match.repositories.match_repo import RepositorioDeMatch
from app.match.repositories.modelos import ScoreDeMatch, TrabajoDeMatch

SIN_TEXTO_DE_CV = "Sin texto de CV extraíble"


class MatchService:
    """Puntúa un trabajo de la cola y guarda su resultado. Una fila, un score."""

    def __init__(self, repo: RepositorioDeMatch, proveedor: Proveedor) -> None:
        self._repo = repo
        self._proveedor = proveedor

    async def puntuar(self, trabajo: TrabajoDeMatch) -> ScoreDeMatch:
        """Del trabajo salen las tres cosas que esto necesita: candidato, vacante
        e idioma. El `empresa_id` ya está en el contexto del repositorio, tomado
        de la fila de la cola (F5, `docs/arquitectura.md` §5.3)."""
        candidato = self._repo.candidato(trabajo.candidato_id)
        if candidato is None or not candidato.tiene_cv:
            return self._guardar(trabajo, None, (), motivo=SIN_TEXTO_DE_CV)

        respuesta = await self._proveedor.puntuar(_payload(candidato.cv_texto), trabajo.idioma)
        return self._guardar(
            trabajo, respuesta.score, respuesta.razones, motivo=respuesta.motivo_sin_score
        )

    def _guardar(
        self,
        trabajo: TrabajoDeMatch,
        score: int | None,
        razones: tuple[str, ...],
        *,
        motivo: str | None,
    ) -> ScoreDeMatch:
        return self._repo.guardar_score(
            trabajo.candidato_id,
            trabajo.vacante_id,
            score,
            razones,
            idioma=trabajo.idioma,
            motivo_sin_score=motivo if score is None else None,
        )


def _payload(cv: str | None) -> dict[str, str]:
    """El cuerpo que se le pasa al proveedor.

    Es un `dict` y no un tipo con constructor privado **a propósito**: el tipo de
    la frontera es PR-08 y estrecharlo aquí sería escribir ese paso a medias. El
    `Protocol` del proveedor ya declara `payload: object` por la misma razón
    (PR-03, `docs/arquitectura.md` §5.4).
    """
    return {"cv": cv or ""}
