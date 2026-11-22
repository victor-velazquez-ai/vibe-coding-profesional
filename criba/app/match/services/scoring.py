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

from app.match.configuracion import Proveedor, RespuestaDelProveedor
from app.match.repositories.match_repo import RepositorioDeMatch
from app.match.repositories.modelos import ScoreDeMatch, TrabajoDeMatch
from app.match.services.pseudonimizador import pseudonimizar
from app.plataforma.modelos import Candidato

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

        respuesta = await self._del_proveedor(candidato, trabajo.idioma)
        return self._guardar(
            trabajo, respuesta.score, respuesta.razones, motivo=respuesta.motivo_sin_score
        )

    async def _del_proveedor(self, candidato: Candidato, idioma: str) -> RespuestaDelProveedor:
        """La **única** llamada al proveedor que hay en Match, y el único sitio
        donde se construye el cuerpo que sale.

        Está extraída del cuerpo de `puntuar` a propósito (PR-08, `PLAN.md` §4):
        así la frontera —qué se le puede pasar al cliente— se cambia en un sitio y
        se lee en una línea, en vez de quedar en medio de la lógica de CA13.
        """
        return await self._proveedor.puntuar(pseudonimizar(candidato), idioma)

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
