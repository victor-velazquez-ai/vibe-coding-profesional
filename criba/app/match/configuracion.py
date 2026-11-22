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

Nada de esto vive en una columna de `empresas`: PR-01 comprobó que la plataforma
no tiene dónde guardarlo (hechos 5 y 7) y F16 no se paga por un ajuste.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

VARIABLE_GLOBAL = "CRIBA_MATCH_ACTIVO"
VARIABLE_DE_EMPRESAS = "CRIBA_MATCH_EMPRESAS_ACTIVADAS"
VARIABLE_DE_IDIOMA = "CRIBA_MATCH_IDIOMA_POR_OMISION"
VERDADEROS = frozenset({"1", "si", "sí", "true", "on"})

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

    `payload` es `object` **a propósito**: el tipo de la frontera llega en PR-08,
    y estrecharlo ahí es la mitad del control de CA2 —«el cliente no acepta otra
    cosa», `docs/arquitectura.md` §5.4—. Asíncrono porque ADR-001 lo exige (T5).
    """

    async def puntuar(self, payload: object, idioma: str) -> RespuestaDelProveedor: ...


@dataclass(frozen=True, slots=True)
class AjustesDeMatch:
    """Inmutables: se leen una vez por proceso, como los de la plataforma."""

    activo: bool
    empresas_activadas: frozenset[str]
    idioma_por_omision: str

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
    `ajustes_match.cache_clear()`."""
    crudo = os.environ.get(VARIABLE_DE_EMPRESAS, "")
    return AjustesDeMatch(
        activo=os.environ.get(VARIABLE_GLOBAL, "").strip().lower() in VERDADEROS,
        empresas_activadas=frozenset(p.strip() for p in crudo.split(",") if p.strip()),
        idioma_por_omision=os.environ.get(VARIABLE_DE_IDIOMA, IDIOMA_POR_OMISION),
    )
