"""La frontera de pseudonimización.

Nombre, correo, teléfono, dirección, links y fotos: los seis datos de §1a
(PR-08, CA2).

**Commit estructural:** aquí solo se ha *movido* la construcción del cuerpo que
sale hacia el proveedor, que hasta ahora vivía en `services/scoring.py::_payload`
(PR-06). El cuerpo sigue siendo el mismo `dict` con el texto del CV tal cual y
nadie limpia nada todavía: la conducta no cambia, y por eso los mismos tests
pasan antes y después (`PLAN.md` §4). Lo que gana el movimiento es que la
frontera tenga ya su módulo del mapa de §2, para que el commit de comportamiento
sea la frontera y nada más.
"""

from __future__ import annotations

from app.plataforma.modelos import Candidato


def pseudonimizar(candidato: Candidato) -> dict[str, str]:
    """El cuerpo que se le pasa al proveedor.

    Recibe el **candidato** y no solo su texto porque los seis datos de §1a viven
    en sus campos (`nombre`, `correo`, `telefono`, `links`) y es desde ahí desde
    donde se limpian del texto libre (R1·B3). Hoy no limpia nada.
    """
    return {"cv": candidato.cv_texto or ""}
