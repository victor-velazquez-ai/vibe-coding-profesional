"""PR-PERF-1 · ronda 1, M1 · «tiene CV» quiere decir lo mismo en los dos sitios.

El cambio nº 1 de `perf/MEDICION.md` §6 dejó dos definiciones de lo mismo:

- `Candidato.tiene_cv` (`app/plataforma/modelos.py`): `bool(cv_texto and cv_texto.strip())`;
- `CandidatoDeLista.tiene_cv` (`app/plataforma/repositorio.py`): `largo_cv > 0`.

Divergen en un caso: un CV formado **solo por espacios en blanco**. El modelo
dice «sin CV» y la lista de la vacante diría «3 caracteres», o sea lo contrario,
para el mismo candidato y en la misma página —el `<select>` de «añadir un
candidato» pinta `· sin CV` leyendo el modelo, y la tabla pinta el largo leyendo
la proyección—. `docs/prs/PR-PERF-1.md` lo declara como el único cambio de
conducta que ningún test pide; esto es ese test.

Hoy la interfaz no llega a ese estado —`subir_cv` recorta y rechaza con 422 un
`cv_texto` que queda vacío, y es el único camino a `guardar_cv`—, así que el caso
se siembra **escribiendo el candidato directamente**, que es por donde entraría de
verdad: una siembra, una importación o el comando de carga.

**Qué fija este test y qué deja libre.** Fija la equivalencia: la fila dice «sin
CV» exactamente cuando `Candidato.tiene_cv` es falso. **No** fija el número de
caracteres que se pinta cuando sí hay CV, a propósito: si el arreglo fuera
`length(btrim(cv_texto))`, un CV con espacios alrededor pintaría un largo
distinto al de hoy, y eso ni lo pide ni lo prohíbe este hallazgo (el largo exacto
del CV de fixture ya lo asercia
`tests/match/test_lista_sin_cv_texto.py::test_abrir_la_vacante_no_trae_el_cv_texto_de_ningun_candidato`,
que es contrato y no se toca). Las dos salidas que M1 nombra —contar sobre el
texto recortado, o un segundo dato para el booleano— pasan este test.

Multiempresa, como siempre: el mismo padrón sembrado en las dos empresas, cada
reclutadora sobre su vacante, y ninguna ve una fila de la otra (CA1, D4).

Fuentes: `app/plataforma/modelos.py` (`Candidato.tiene_cv`),
`app/plataforma/repositorio.py` (`CandidatoDeLista.tiene_cv`),
`app/plataforma/plantillas/_candidatos.html` (la insignia «sin CV» / «N
caracteres»), `docs/prs/PR-PERF-1.md` (decisión de construcción 3), `SPEC.md`
CA1, CA8.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.plataforma.modelos import Candidato
from tests.match.conftest import EmpresaDePrueba, Entrar, sembrar_candidatos

# Cada caso es (etiqueta, texto del CV). Los tres primeros son «sin CV» para el
# modelo; los dos últimos, «con CV». El de espacios alrededor está para que el
# test no se cierre sobre un largo concreto (ver el docstring del módulo).
CASOS: tuple[tuple[str, str | None], ...] = (
    ("sin texto", None),
    ("cadena vacía", ""),
    ("solo espacios", "   "),
    ("solo blancos de varios tipos", "\n\t  \r\n"),
    ("texto con blancos alrededor", "  Enfermera titulada sintética.  "),
    ("texto normal", "Enfermera titulada sintética, piso de medicina interna."),
)


def _fila_de(html: str, candidato: Candidato) -> str:
    """El trozo de HTML de la fila de ese candidato, buscado por su correo."""
    trozos = [t for t in html.split('data-testid="fila-candidato"')[1:] if candidato.correo in t]
    assert len(trozos) == 1, f"el candidato {candidato.id} sale {len(trozos)} veces en la lista"
    return trozos[0]


def _sembrar_casos(sesion: Session, empresa: EmpresaDePrueba) -> list[tuple[str, Candidato]]:
    """Un candidato postulado por caso, con el `cv_texto` escrito a mano.

    A mano y no por `guardar_cv` porque el camino de la interfaz no deja llegar
    aquí (`subir_cv` recorta y da 422): el caso entra por una siembra o una
    importación, que es justo lo que M1 señala. Todo sintético (D3 modificado,
    D15, F12).
    """
    candidatos = sembrar_candidatos(sesion, empresa, len(CASOS))
    for (_, texto), candidato in zip(CASOS, candidatos, strict=True):
        candidato.cv_texto = texto
    sesion.flush()
    return [(etiqueta, c) for (etiqueta, _), c in zip(CASOS, candidatos, strict=True)]


def test_un_cv_de_solo_espacios_sale_como_sin_cv_igual_que_en_el_modelo(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    entrar: Entrar,
) -> None:
    """M1 · la insignia de la fila dice lo que `Candidato.tiene_cv` dice.

    Un solo render por empresa y una comprobación por caso: así el fallo nombra
    el caso que diverge en vez de un «no está en el HTML».
    """
    for empresa, ajena in ((northstar, meridian), (meridian, northstar)):
        casos = _sembrar_casos(sesion, empresa)
        cliente: TestClient = entrar(empresa.reclutador)
        respuesta = cliente.get(f"/vacantes/{empresa.vacante.id}")
        assert respuesta.status_code == 200, f"{empresa.slug} recibió {respuesta.status_code}"
        assert ajena.candidato.correo not in respuesta.text, (
            f"{empresa.slug} ve un candidato de {ajena.slug}"
        )

        for etiqueta, candidato in casos:
            fila = _fila_de(respuesta.text, candidato)
            dice_sin_cv = "sin CV" in fila
            donde = f"{empresa.slug} · {etiqueta} ({candidato.cv_texto!r})"
            assert dice_sin_cv == (not candidato.tiene_cv), (
                f"{donde}: la lista dice {'«sin CV»' if dice_sin_cv else '«N caracteres»'} y "
                f"Candidato.tiene_cv es {candidato.tiene_cv}. Las dos definiciones de «tiene CV» "
                "tienen que coincidir (ronda 1, M1)"
            )
            assert ("caracteres" in fila) == candidato.tiene_cv, (
                f"{donde}: la insignia del largo y Candidato.tiene_cv no concuerdan"
            )
