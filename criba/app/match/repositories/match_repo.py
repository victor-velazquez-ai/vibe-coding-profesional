"""El ÚNICO punto de acceso a datos de Match (PR-04; D4, CA1, F4, §4).

Dos clases, y ninguna tercera:

- `RepositorioDeMatch`, que no existe sin un `ContextoDeEmpresa` y filtra por
  `empresa_id` en cada consulta;
- `RepositorioDeSistema`, que habilita **exactamente** las tres operaciones de
  `OperacionDeSistema` y no sabe leer candidatos, scores ni razones.

Toda sentencia SQL de Match vive en este paquete: la regla (a) del test de
enumeración lo comprueba por ruta sobre toda la aplicación.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.match.configuracion import IDIOMA_POR_OMISION, ajustes_match
from app.match.repositories.contexto import (
    ContextoDeEmpresa,
    ContextoDeSistema,
    OperacionDeSistema,
    SinContexto,
)
from app.match.repositories.modelos import GastoDelMes, ScoreDeMatch, TrabajoDeMatch
from app.plataforma.modelos import Candidato, Empresa, Postulacion, Vacante

# La enumeración de I1 **en código**: cada operación de sistema y el único método
# que la habilita. Una cuarta entrada aquí es una cuarta línea en el diff.
OPERACIONES_DE_SISTEMA: dict[OperacionDeSistema, str] = {
    OperacionDeSistema.TOMAR_TRABAJO: "siguiente_trabajo_pendiente",
    OperacionDeSistema.RECONCILIAR: "trabajos_a_reconciliar",
    OperacionDeSistema.GASTO: "gasto_del_mes",
}

EN_VUELO = ("pendiente", "en_curso")


class RepositorioDeMatch:
    """Las consultas de Match de **una** empresa, la del contexto."""

    def __init__(self, bd: Session, contexto: ContextoDeEmpresa) -> None:
        if not isinstance(contexto, ContextoDeEmpresa):
            raise SinContexto(
                "El repositorio de Match exige un ContextoDeEmpresa y recibió "
                f"{type(contexto).__name__}. Las tres operaciones sin empresa viven en "
                "RepositorioDeSistema, que no lee candidatos, scores ni razones."
            )
        self._bd = bd
        self._ctx = contexto

    @property
    def empresa_id(self) -> int:
        return self._ctx.empresa_id

    # --- D7 y CA3: la activación de la empresa del contexto ----------------

    def empresa_activada(self) -> bool:
        """«Match activado **y** anexo de subprocesador firmado» para la empresa
        del contexto (D7, CA3, PLAN.md PR-10).

        Vive **aquí y en ningún otro sitio** (`docs/arquitectura.md` §4 y §5.3:
        «la comprobación de D7 debe vivir en el mismo punto de acceso a datos, no
        en el router»). Quien decide es **una** función y la llaman los tres
        caminos que pueden violar CA3, cada uno con su contexto:

        - `encolar`, antes del `INSERT` —contexto «desde la vacante»—, porque CA3
          prohíbe «ningún registro de Match» y no solo «ninguna llamada» (R2·M2);
        - el bucle del ejecutor, al tomar la fila —contexto «desde el trabajo»—,
          que es el camino **sin cookie** de F5 y §5.3: la fila puede estar en la
          cola de antes, y ahí no hay sesión que revalidar;
        - la vista de vacante (`services/listado.py`), que es la mitad de CA3 que
          Meridian ve el 15-ene.

        El `slug` **no es un argumento**: sale de la fila de la empresa del
        contexto, por la misma razón que el `empresa_id` (PR-04, D4). Un `slug` de
        llamador es el que el siguiente confunde, y confundirlo aquí es emitir una
        llamada por una empresa sin anexo firmado (F5, severidad 5).

        Es un estado que hay que **encender a propósito**: con la configuración en
        su valor por omisión no hay ninguna empresa activada (R4·I1), así que esto
        devuelve `False` para las 40.
        """
        empresa = self._bd.get(Empresa, self.empresa_id)
        return empresa is not None and ajustes_match().match_activado(empresa.slug)

    # --- lectura -----------------------------------------------------------

    def scores(self) -> list[ScoreDeMatch]:
        """Los scores de **esta** empresa. Así «cero filas» se asercia por
        empresa y no en global, que pasaría con el `empresa_id` cambiado (R6·I3).
        """
        return list(
            self._bd.scalars(
                select(ScoreDeMatch)
                .where(ScoreDeMatch.empresa_id == self.empresa_id)
                .order_by(ScoreDeMatch.id)
            )
        )

    def score(self, candidato_id: int, vacante_id: int) -> ScoreDeMatch | None:
        return self._bd.scalars(
            select(ScoreDeMatch).where(
                ScoreDeMatch.empresa_id == self.empresa_id,
                ScoreDeMatch.candidato_id == candidato_id,
                ScoreDeMatch.vacante_id == vacante_id,
            )
        ).first()

    def scores_de_vacante(self, vacante_id: int) -> list[ScoreDeMatch]:
        """Los scores de una vacante en **una** consulta (PR-05).

        Es la única consulta que Match añade a la vista de vacante, y por eso el
        guardia de R6·M4 puede exigir que el número no crezca con las filas: la
        plantilla no provoca una consulta por candidato (F27).
        """
        return list(
            self._bd.scalars(
                select(ScoreDeMatch)
                .where(
                    ScoreDeMatch.empresa_id == self.empresa_id,
                    ScoreDeMatch.vacante_id == vacante_id,
                )
                .order_by(ScoreDeMatch.id)
            )
        )

    def trabajos(self) -> list[TrabajoDeMatch]:
        """«Trabajos de esta empresa», para que los tests de PR-06 y PR-10 no
        construyan SQL sobre `match_trabajos` (R6·I3)."""
        return list(
            self._bd.scalars(
                select(TrabajoDeMatch)
                .where(TrabajoDeMatch.empresa_id == self.empresa_id)
                .order_by(TrabajoDeMatch.id)
            )
        )

    def candidato(self, candidato_id: int) -> Candidato | None:
        """El candidato de **esta** empresa, o `None`.

        Lo necesita el camino de escritura de PR-06: el hash del CV para la clave
        de idempotencia y el texto que se le pasa al proveedor. Es una lectura de
        candidatos, así que exige `empresa_id` como cualquier otra (I1) y nunca
        corre sobre contexto de sistema.
        """
        return self._bd.scalars(
            select(Candidato).where(
                Candidato.id == candidato_id, Candidato.empresa_id == self.empresa_id
            )
        ).one_or_none()

    def descripcion_de_vacante(self, vacante_id: int) -> str:
        """La descripción de la vacante de **esta** empresa (PR-09, R?·hallazgo 1).

        El tercer dato del pedido al proveedor (`SPEC.md` alcance 2 y D13: «solo
        el texto del CV y la descripción de la vacante»), y la primera lectura de
        Match que saca de Criba un dato de la **empresa** y no del candidato
        —decisión de Víctor del 22-nov-2026,
        `docs/decisiones-propuestas/2026-11-22-proveedor-y-vacante.md` §2—. Por
        eso vive aquí y no en el servicio: el `empresa_id` sale del contexto,
        nunca de un argumento (D4, CA1, F4, regla (a) de PR-04). Un `select`
        suelto sobre `vacantes` sin ese filtro manda la descripción de Northstar
        en la llamada de otra empresa, y eso es el incidente de [03:03] y no un
        error de programación.

        **Y ese filtro lo ejerce un test**, dicho aquí porque este es el sitio
        donde se borra: el test 5 de `tests/match/test_descripcion_de_vacante.py`
        llama a este método con el `vacante_id` de **la otra empresa**, en los dos
        sentidos, y exige `SinContexto` sin que el mensaje cite el texto ajeno
        (R2·I1). La mutación 4f·6 del cuerpo del PR —leer sin el filtro— pasa de
        **0 rojos a 1**. Los tests de aislamiento del paso no lo veían: pasan el
        `vacante_id` de la empresa del trabajo, así que con filtro o sin él
        reciben la misma descripción. El camino con un `vacante_id` ajeno no
        existe todavía —el `empresa_id` del contexto sale de la fila de la cola,
        que trae las dos columnas juntas—, y para cuando exista (el recálculo de
        D23/CA9 en PR-21, un script de re-puntuación) el cerrojo ya está puesto.

        Una vacante que no es de la empresa del contexto es `SinContexto` y no una
        cadena vacía: confundir «no te toca» con «no tiene descripción» haría que
        un fallo de aislamiento se viera igual que el «sin score por vacante sin
        descripción» de `SPEC.md` alcance 6, que es de PR-11.
        """
        descripcion = self._bd.scalars(
            select(Vacante.descripcion).where(
                Vacante.id == vacante_id, Vacante.empresa_id == self.empresa_id
            )
        ).one_or_none()
        if descripcion is None:
            raise SinContexto(
                f"Vacante {vacante_id} no es de la empresa {self.empresa_id} del contexto."
            )
        return descripcion

    def trabajo_por_clave(self, clave_idempotencia: str) -> TrabajoDeMatch | None:
        """El trabajo de esta empresa con esa clave, si ya existe (ADR-001 §D3).

        `uq_match_trabajos_idempotencia` es `(empresa_id, clave_idempotencia)`, y
        por eso esta lectura va con contexto de empresa y no es global.
        """
        return self._bd.scalars(
            select(TrabajoDeMatch).where(
                TrabajoDeMatch.empresa_id == self.empresa_id,
                TrabajoDeMatch.clave_idempotencia == clave_idempotencia,
            )
        ).one_or_none()

    def candidatos_de_vacante(self, vacante_id: int) -> list[int]:
        """Los candidatos postulados a una vacante (R4·M3).

        Es una **lectura con empresa**, no una cuarta operación de sistema: vive
        aquí para que PR-16 —el comando y la cobertura— no lea `postulaciones`
        con un `select` suelto, que la regla (a) no detectaría porque no es una
        tabla `match_*`.
        """
        self._mio(Vacante, vacante_id)
        return list(
            self._bd.scalars(
                select(Postulacion.candidato_id)
                .where(
                    Postulacion.empresa_id == self.empresa_id,
                    Postulacion.vacante_id == vacante_id,
                )
                .order_by(Postulacion.candidato_id)
            )
        )

    # --- escritura ---------------------------------------------------------

    def guardar_score(
        self,
        candidato_id: int,
        vacante_id: int,
        score: int | None,
        razones: Sequence[str],
        *,
        idioma: str = IDIOMA_POR_OMISION,
        motivo_sin_score: str | None = None,
    ) -> ScoreDeMatch:
        """CA13 en el estado: o hay score, o hay «sin score» con su motivo.

        **Actualiza la fila si el par ya tiene score en ese idioma** (PR-06): la
        clave natural de `match_scores` es (empresa, candidato, vacante, idioma)
        desde PR-02, y CA9(a) dice que un CV nuevo vuelve a puntuar el par. Sin
        esto, el segundo trabajo del mismo par choca con
        `uq_match_scores_par_idioma` y termina en `error` con el score viejo en
        la vista. El historial de versiones no vive aquí: es la fila de auditoría
        por score de PR-12.
        """
        self._mio(Candidato, candidato_id)
        self._mio(Vacante, vacante_id)
        existente = self._bd.scalars(
            select(ScoreDeMatch).where(
                ScoreDeMatch.empresa_id == self.empresa_id,
                ScoreDeMatch.candidato_id == candidato_id,
                ScoreDeMatch.vacante_id == vacante_id,
                ScoreDeMatch.idioma == idioma,
            )
        ).one_or_none()
        if existente is not None:
            existente.score = score
            existente.razones = list(razones)
            existente.estado = "listo" if score is not None else "sin_score"
            existente.motivo_sin_score = motivo_sin_score
            existente.actualizado_en = datetime.now(UTC)
            self._bd.flush()
            return existente
        fila = ScoreDeMatch(
            empresa_id=self.empresa_id,
            candidato_id=candidato_id,
            vacante_id=vacante_id,
            idioma=idioma,
            score=score,
            razones=list(razones),
            estado="listo" if score is not None else "sin_score",
            motivo_sin_score=motivo_sin_score,
        )
        self._bd.add(fila)
        self._bd.flush()
        return fila

    def crear_trabajo(
        self,
        candidato_id: int,
        vacante_id: int,
        clave_idempotencia: str,
        *,
        idioma: str = IDIOMA_POR_OMISION,
    ) -> TrabajoDeMatch:
        """La fila de la cola, **mínima a propósito**: quién encola y la clave de
        idempotencia son de PR-06, el lease y los reintentos de PR-14. Sin ella
        el constructor «desde el trabajo» no sería comprobable.
        """
        self._mio(Candidato, candidato_id)
        self._mio(Vacante, vacante_id)
        trabajo = TrabajoDeMatch(
            empresa_id=self.empresa_id,
            candidato_id=candidato_id,
            vacante_id=vacante_id,
            idioma=idioma,
            estado="pendiente",
            clave_idempotencia=clave_idempotencia,
        )
        self._bd.add(trabajo)
        self._bd.flush()
        return trabajo

    def marcar_trabajo(
        self, trabajo_id: int, estado: str, *, motivo: str | None = None
    ) -> TrabajoDeMatch:
        """`pendiente → en_curso → listo | error` (ADR-001 §Decisión 1).

        El cambio de estado es una escritura sobre `match_trabajos`, así que vive
        aquí y no en el bucle: la regla (a) de PR-04 lo exige por ruta. El lease,
        el contador de intentos y la reconciliación son de PR-14 y PR-15.
        """
        trabajo = self._bd.scalars(
            select(TrabajoDeMatch).where(
                TrabajoDeMatch.id == trabajo_id,
                TrabajoDeMatch.empresa_id == self.empresa_id,
            )
        ).one_or_none()
        if trabajo is None:
            raise SinContexto(
                f"El trabajo {trabajo_id} no es de la empresa {self.empresa_id} del contexto."
            )
        trabajo.estado = estado
        trabajo.motivo = motivo
        trabajo.actualizado_en = datetime.now(UTC)
        self._bd.flush()
        return trabajo

    # --- el filtro, en un solo sitio ---------------------------------------

    def _mio(self, modelo: type[Candidato] | type[Vacante], fila_id: int) -> None:
        fila = self._bd.get(modelo, fila_id)
        if fila is None or fila.empresa_id != self.empresa_id:
            raise SinContexto(
                f"{modelo.__name__} {fila_id} no es de la empresa {self.empresa_id} del contexto."
            )


class RepositorioDeSistema:
    """Las tres operaciones sin empresa, y nada más."""

    def __init__(self, bd: Session, contexto: ContextoDeSistema) -> None:
        if not isinstance(contexto, ContextoDeSistema):
            raise SinContexto(
                "Las operaciones sin empresa exigen un ContextoDeSistema explícito, "
                "no `None` ni un contexto vacío."
            )
        self._bd = bd
        self._ctx = contexto

    def siguiente_trabajo_pendiente(self) -> TrabajoDeMatch | None:
        """(a) `SELECT … FOR UPDATE SKIP LOCKED` (ADR-001 §Decisión 1).

        Devuelve la **fila de la cola**: de ahí sale después el contexto de
        empresa (`ContextoDeEmpresa.desde_el_trabajo`, F5, §5.3). El lease y los
        reintentos son de PR-14.
        """
        return self._bd.scalars(
            select(TrabajoDeMatch)
            .where(TrabajoDeMatch.estado == "pendiente")
            .order_by(TrabajoDeMatch.creado_en, TrabajoDeMatch.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        ).first()

    def trabajos_a_reconciliar(self, minutos: int = 60) -> list[TrabajoDeMatch]:
        """(b) leases vencidos y pendientes de más de 60 min, de **toda** la
        plataforma (CA7). Filas de la cola, nunca scores ni razones."""
        limite = datetime.now(UTC) - timedelta(minutes=minutos)
        return list(
            self._bd.scalars(
                select(TrabajoDeMatch)
                .where(TrabajoDeMatch.estado.in_(EN_VUELO), TrabajoDeMatch.creado_en < limite)
                .order_by(TrabajoDeMatch.id)
            )
        )

    def gasto_del_mes(self, mes: str, etiqueta: str = "produccion") -> int:
        """(c) D12 es un techo de **toda** la plataforma: un contador por empresa
        no podría dispararlo (CA10, F23)."""
        return (
            self._bd.scalar(
                select(GastoDelMes.gasto_centavos).where(
                    GastoDelMes.mes == mes, GastoDelMes.etiqueta_uso == etiqueta
                )
            )
            or 0
        )
