"""Configuración de Match: lo que no cabe en una migración sobre tablas de negocio (F16).

Tres declaraciones **sin conducta**, que PR-03 añade aquí (R6·M2, R6·M3) porque
sus fixtures las necesitan antes de que exista quien las evalúe: el **estado de
activación por empresa** —«Match activado + anexo de subprocesador firmado»— con
valor por omisión **«ninguna empresa activada»**, que evalúa PR-10 dentro de
`encolar` (R4·I1, D7, CA3); el **idioma por omisión por empresa**, hoy `'en'`,
que PR-22 sustituye por el del usuario (R3·I3, R6·M3, D11, CA11); y el
**`Protocol` del proveedor**, que implementan el MOCK (PR-06), el doble de los
tests (PR-03) y el cliente real (PR-09).

El **interruptor global** (`CRIBA_MATCH_ACTIVO`, apagado por omisión fuera de
tests) es otra cosa —apaga Match entero— y lo añade **PR-05**, porque su test 6
lo necesita: con el interruptor apagado, `montar` no monta los endpoints bajo
`/match` y `listar_vacante` devuelve **la lista de hoy** (R4·I1, R6·I5, R6·B1).
Lo que apaga de `encolar`, del bucle del ejecutor y de los dos ganchos es de
PR-06. Lo que **no** apaga nunca es la vista de vacante de la plataforma: con el
interruptor apagado responde 200, siempre.

Y el **modo de proveedor** (`CRIBA_MATCH_PROVEEDOR`, el **MOCK** por omisión), que
añade **PR-09**: qué proveedor usa Match es configuración de entorno, como los
otros tres estados, y por eso el nombre de la variable y sus dos valores se
declaran aquí. La **fábrica** que los lee vive en `proveedor/cliente.py`, porque
este módulo no puede importar al adaptador sin un ciclo.

Nada de esto vive en una columna de `empresas`: PR-01 comprobó que la plataforma
no tiene dónde guardarlo (hechos 5 y 7) y F16 no se paga por un ajuste.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from app.match.proveedor.payload import PayloadPseudonimizado

VARIABLE_GLOBAL = "CRIBA_MATCH_ACTIVO"
VARIABLE_DE_EMPRESAS = "CRIBA_MATCH_EMPRESAS_ACTIVADAS"
VARIABLE_DE_IDIOMA = "CRIBA_MATCH_IDIOMA_POR_OMISION"
VERDADEROS = frozenset({"1", "si", "sí", "true", "on"})

# **Qué proveedor usa Match**, y es la cuarta declaración de este módulo (PR-09).
# Vive aquí y no en el adaptador por la misma razón que las otras tres: es
# configuración por **variable de entorno**, nunca una constante en el código
# (F19, R6·I5). La **fábrica** que la lee sí vive en el adaptador
# (`proveedor/cliente.py`): este módulo no puede importarlo —el adaptador importa
# de aquí `Proveedor` y `RespuestaDelProveedor`— y un ciclo de imports sería el
# precio de tenerlo todo junto.
#
# El valor por omisión es el **MOCK**, que no sale del proceso, y es el único que
# la CI corre (N4 acotada, decisión de Víctor del 22-nov-2026, registrada en
# `docs/decisiones-propuestas/2026-11-22-proveedor-y-vacante.md` §1;
# `docs/arquitectura.md` §2).
# Es la misma forma que la activación por empresa (R4·I1) y el interruptor global
# (R6·I5): un entorno nuevo, o un despliegue al que se le olvidó la variable, nace
# en el modo que no puede sacar un CV de Criba.
VARIABLE_DE_MODO = "CRIBA_MATCH_PROVEEDOR"
MODO_MOCK = "mock"
# `claude_cli` y no `claude`: el valor nombra **el adaptador**, no al proveedor, y
# el adaptador de este repo es el CLI por subproceso (N4). Que los dos no se
# confundan es parte del control: ningún valor parecido —`claude`, `real`,
# `produccion`— selecciona el cliente real, así que una errata en la variable no
# saca CVs de Criba.
MODO_CLAUDE_CLI = "claude_cli"

# **Supuesto nuestro** (R6·M3): la única empresa activada en la v1 opera en
# Estados Unidos (D20, `SPEC.md` §10). `usuarios.idioma` no existe (hecho 8 de
# PR-01), así que PR-06 escribe este valor en cada trabajo y PR-22 lo sustituye.
IDIOMA_POR_OMISION = "en"


@dataclass(frozen=True, slots=True)
class RespuestaDelProveedor:
    """Score 0-100 con tres razones, o «sin score» con motivo y nunca un cero (CA13)."""

    score: int | None
    razones: tuple[str, ...]
    version_modelo: str
    motivo_sin_score: str | None = None


class Proveedor(Protocol):
    """Lo único que Match le pide a un proveedor de modelos.

    `payload` es un **`PayloadPseudonimizado`** desde PR-08, y eso es la mitad del
    control de CA2: «el cliente del proveedor no acepta otra cosa que un payload
    ya pseudonimizado» (`docs/arquitectura.md` §5.4). La otra mitad es el rechazo
    en ejecución, `exigir_payload`, que toda implementación llama en su primera
    línea: una anotación no es un control. Asíncrono porque ADR-001 lo exige (T5).

    **`descripcion_de_vacante` es el tercer dato del pedido**, y es dato de la
    **empresa**, no del candidato (decisión de Víctor del 22-nov-2026 sobre el
    hallazgo 1 de `docs/prs/PR-09.md`, propuesta en
    `docs/decisiones-propuestas/2026-11-22-proveedor-y-vacante.md`). Va aquí y no
    dentro de `PayloadPseudonimizado` porque ese tipo es **lo que la frontera
    exige y la fábrica única construye**: si además llevara dato de la empresa,
    «pseudonimizado» dejaría de significar los seis datos del candidato de CA2 y
    `exigir_payload` no tendría qué verificar. Sin este dato el modelo responde a
    «¿qué tan bueno es este CV?», que no es la pregunta: `SPEC.md` alcance 1
    puntúa el par (candidato, vacante) y el alcance 2 y D13 enumeran las entradas
    —«solo el texto del CV y la descripción de la vacante»—.

    **Tiene valor por omisión** por una razón escrita: el recorrido de
    implementaciones de CA2 (`tests/match/test_pseudonimizacion.py`) llama
    `puntuar(cuerpo, idioma)` con dos argumentos para comprobar que la frontera
    rechaza un cuerpo crudo, y ese rechazo tiene que ocurrir antes de que importe
    qué vacante era. Lo que hace una implementación con la descripción vacía
    —«vacante sin descripción → sin score con motivo», `SPEC.md` alcance 6— es de
    **PR-11** y no se decide aquí.
    """

    async def puntuar(
        self,
        payload: PayloadPseudonimizado,
        idioma: str,
        descripcion_de_vacante: str = "",
    ) -> RespuestaDelProveedor: ...


@dataclass(frozen=True, slots=True)
class AjustesDeMatch:
    """Inmutables: se leen una vez por proceso, como los de la plataforma."""

    activo: bool
    empresas_activadas: frozenset[str]
    idioma_por_omision: str
    modo_proveedor: str

    def match_activado(self, slug: str) -> bool:
        """D7 y CA3 en un solo estado, porque el plan trata las dos condiciones
        —activado **y** anexo firmado— como una (R4·I1)."""
        return slug in self.empresas_activadas

    def idioma_de(self, slug: str) -> str:
        """Devuelve el de omisión para toda empresa: hoy no hay dónde guardar uno
        distinto (hecho 5 de PR-01). Recibe la empresa para que PR-22 no cambie
        la firma."""
        return self.idioma_por_omision


@lru_cache(maxsize=1)
def ajustes_match() -> AjustesDeMatch:
    """Variable de entorno y no constante (R6·I5), y **vacía por omisión**: una
    empresa nueva, o un entorno nuevo, nace apagada. Los tests invalidan con
    `ajustes_match.cache_clear()`.

    `lru_cache` significa **una lectura por proceso**, y eso hay que decirlo
    donde se lee (R?·M1): cambiar cualquiera de estas cuatro variables en el
    entorno de un proceso ya arrancado **no cambia nada hasta reiniciarlo**. Vale
    para el interruptor global, para la activación por empresa y para el modo de
    proveedor: volver al MOCK para cortar gasto —pregunta abierta 11 de `PLAN.md`
    §9— es un reinicio, no un `export`."""
    crudo = os.environ.get(VARIABLE_DE_EMPRESAS, "")
    return AjustesDeMatch(
        activo=os.environ.get(VARIABLE_GLOBAL, "").strip().lower() in VERDADEROS,
        empresas_activadas=frozenset(p.strip() for p in crudo.split(",") if p.strip()),
        idioma_por_omision=os.environ.get(VARIABLE_DE_IDIOMA, IDIOMA_POR_OMISION),
        # Sin variable, o con la variable vacía, **el MOCK** (PR-09). El `or` es
        # el valor por omisión y no un `if` del llamador: así la fábrica del
        # adaptador compara contra un modo siempre declarado.
        modo_proveedor=os.environ.get(VARIABLE_DE_MODO, "").strip().lower() or MODO_MOCK,
    )
