"""MatchService: pseudonimiza, llama al proveedor, guarda score o motivo (PR-06, PR-08).

La versión mínima de la Etapa 0, con lo que **no** hace dicho en voz alta:

- **no decide qué sale de Criba**: eso es de `services/pseudonimizador.py` desde
  PR-08, y aquí queda una sola llamada (`_del_proveedor`). El payload es un
  `PayloadPseudonimizado` que este servicio **no puede construir** (CA2,
  `docs/arquitectura.md` §5.4);
- **no escribe la fila de auditoría por score** (hash del CV, versión de prompt y
  de modelo): PR-12;
- **no cuenta el gasto ni mira el techo**: PR-13;
- **no construye el prompt**: hoy no hay prompt, y de ahí sale el hueco de la
  clave de idempotencia que `cola/trabajos.py` declara.

- **no elige qué entra en el pedido por su cuenta**: son las dos entradas de
  `SPEC.md` alcance 2 y D13 —el texto del CV y la descripción de la vacante— y
  las dos salen del trabajo y del repositorio, no de un argumento del llamador
  (decisión de Víctor del 22-nov-2026 sobre el hallazgo 1 de PR-09,
  `docs/decisiones-propuestas/2026-11-22-proveedor-y-vacante.md` §2).

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

        respuesta = await self._del_proveedor(candidato, trabajo)
        return self._guardar(
            trabajo, respuesta.score, respuesta.razones, motivo=respuesta.motivo_sin_score
        )

    async def _del_proveedor(
        self, candidato: Candidato, trabajo: TrabajoDeMatch
    ) -> RespuestaDelProveedor:
        """La **única** llamada al proveedor que hay en Match, y el único sitio
        donde se construye el pedido que sale.

        Está extraída del cuerpo de `puntuar` a propósito (PR-08, `PLAN.md` §4):
        así la frontera —qué se le puede pasar al cliente— se cambia en un sitio y
        se lee en una línea, en vez de quedar en medio de la lógica de CA13.

        **El pedido son tres datos y no dos** desde la decisión de Víctor del
        22-nov-2026 (`docs/decisiones-propuestas/2026-11-22-proveedor-y-vacante.md`):
        el cuerpo pseudonimizado del candidato, el idioma y la **descripción de la
        vacante**, que es el par (candidato, vacante) de `SPEC.md` alcance 1 y las
        dos entradas del alcance 2 y D13. Los tres salen del **trabajo** y del
        repositorio con su contexto, no de un argumento del llamador: el
        `candidato_id`, el `vacante_id` y el idioma son columnas de la fila de la
        cola (F5, `docs/arquitectura.md` §5.3, ADR-001 §Decisión 1), y aquí no hay
        cookie que revalidar.

        La descripción **no entra en el payload** (CA2 sigue siendo sobre los seis
        datos del candidato) y este servicio no decide nada si está vacía: eso es
        «sin score con motivo» del alcance 6 y lo decide **PR-11**.
        """
        return await self._proveedor.puntuar(
            pseudonimizar(candidato),
            trabajo.idioma,
            self._repo.descripcion_de_vacante(trabajo.vacante_id),
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
