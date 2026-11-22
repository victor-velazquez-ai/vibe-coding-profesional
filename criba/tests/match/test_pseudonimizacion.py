"""PR-08 · la frontera de pseudonimización (CA2, D3 modificado §1a).

Lo que este archivo sostiene es **lo que no se puede recuperar**: lo enviado ya
salió (F2, severidad 4 por probabilidad 4; F6, 5 por 3; `PLAN.md` PR-08
«Riesgo»: «recuperación: ninguna hacia atrás»). Por eso va **antes** de que
exista cualquier cliente real (regla 1.5) y por eso la frontera es un **tipo**, no
un método dentro de un servicio grande (`docs/arquitectura.md` §5.4, escenario:
«enero, presión de demo, alguien añade un segundo prompt para re-puntuar y llama
al cliente directo porque es más corto»).

Los cinco controles del paso, en el orden de `PLAN.md` PR-08:

1. **CA2** · los seis datos de §1a no salen en el cuerpo construido, en español y
   en inglés (test 1);
2. **CA2, segunda mitad** · al cliente del proveedor no se le puede pasar otra
   cosa: a nivel de tipos **y** con un test que lo intenta (test 2);
3. **3a · valores conocidos** · lo que está en los campos estructurados sale
   **también del texto libre** (test 3);
4. **3a · patrones** · correo, teléfono y URL de perfil salen aunque no estén en
   ningún campo (test 4), con su contracara: un CV sin PII sale **intacto**
   (test 5), que es el límite barato del riesgo de «quitar de más» (F1);
5. **3b** · las entidades que §1a **no** nombra, en `xfail(strict=True)` con el
   motivo escrito (test 6). Es el único marcador aceptable aquí: la regla 1.5 de
   `PLAN.md` prohíbe habilitar el cliente real con un `xfail` sobre **uno de los
   seis** datos de §1a.

Y uno más, que el plan no enumera pero que es el requisito número uno del cliente
(D4, CA1): **ningún CV cruza de empresa en el payload** (test 7), comprobado por
el camino de escritura real y no llamando al pseudonimizador a mano.

**Cómo fallan estos tests mientras la frontera no existe:** con un `assert` que
dice qué símbolo falta, no con un `ImportError` en la recolección. De eso se
encarga `frontera()`, abajo: los dos módulos del mapa de §2 ya existen (PR-01) y
están vacíos, así que los nombres se resuelven con `getattr` y se asercian.
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, get_type_hints

import pytest
from sqlalchemy.orm import Session

from app.match.cola.ejecutor import pasadas
from app.match.cola.trabajos import encolar
from app.match.configuracion import IDIOMA_POR_OMISION, Proveedor
from app.match.proveedor.mock import SCORE_DEL_MOCK, ProveedorMock
from app.plataforma.modelos import Candidato, Postulacion
from tests.dobles.proveedor import ProveedorContado
from tests.match.conftest import EmpresaDePrueba, cv, repo_de

RAIZ = Path(__file__).resolve().parents[2]
PAQUETE_DEL_PROVEEDOR = RAIZ / "app" / "match" / "proveedor"

# Los tres símbolos que PR-08 tiene que crear, con su módulo del mapa de §2.
SIMBOLOS = {
    "app.match.proveedor.payload": ("PayloadPseudonimizado", "FronteraViolada"),
    "app.match.services.pseudonimizador": ("pseudonimizar",),
}

# Un CV sin ningún dato de §1a **y sin ninguna cifra larga**: el número de
# licencia que un patrón de teléfono podría comerse no se mete aquí a propósito
# (ver el docstring del test 5).
CV_SIN_PII = (
    "Enfermera registrada con licencia vigente en Texas. Ocho años en piso de "
    "medicina interna, cinco de ellos en turno nocturno de doce horas. "
    "Telemetría, manejo de vía central y valoración al ingreso."
)


# --- el material: los datos de §1a de cada fixture --------------------------


@dataclass(frozen=True, slots=True)
class Pii:
    """Los datos de un CV de fixture, declarados **al lado del test**.

    No se leen del archivo: se declaran aquí y el test asercia que el archivo los
    trae (`assert valor in crudo`). Una fixture que se queda sin su PII es el
    punto ciego de CA2 que F2 y F15 nombran, y así el test se queja de la fixture
    en vez de pasar sin probar nada.
    """

    archivo: str
    nombre: str
    partes: tuple[str, ...]
    correo: str
    telefono: str
    link: str
    direccion: str
    codigo_postal: str
    foto: str
    correo_de_referencia: str
    telefono_de_referencia: str
    url_de_referencia: str
    marca: str
    empleador: str
    universidad: str
    ciudad: str

    def crudo(self) -> str:
        return cv(self.archivo)

    def seis_datos_de_1a(self) -> dict[str, str]:
        """Los seis de D3 modificado §1a: nombre, correo, teléfono, dirección,
        links a perfiles y fotos.

        La **dirección** y la **foto** entran aquí aunque `candidatos` no tenga
        columna para ellas (hecho del esquema, `app/plataforma/modelos.py`): CA2
        no distingue si el dato viene de un campo o de la narrativa. De la
        dirección se asercian la calle y el código postal, no la ciudad: la
        ciudad es lo que la pregunta abierta 2 deja sin decidir (test 6).
        """
        return {
            "nombre": self.nombre,
            "correo": self.correo,
            "teléfono": self.telefono,
            "dirección (calle)": self.direccion,
            "dirección (código postal)": self.codigo_postal,
            "link a perfil": self.link,
            "foto": self.foto,
        }

    def datos_sin_campo(self) -> dict[str, str]:
        """Los que **no** están en ningún campo estructurado del candidato.

        Son los que solo caen por patrón: la foto, y el correo, el teléfono y la
        URL de perfil de la sección de referencias.
        """
        return {
            "foto": self.foto,
            "correo de la referencia": self.correo_de_referencia,
            "teléfono de la referencia": self.telefono_de_referencia,
            "URL de perfil de la referencia": self.url_de_referencia,
        }

    def entidades_que_1a_no_nombra(self) -> dict[str, str]:
        """Empleador anterior, universidad y ciudad no declarada: 3b, decide Priya."""
        return {
            "empleador anterior": self.empleador,
            "universidad": self.universidad,
            "ciudad no declarada": self.ciudad,
        }


PII_ES = Pii(
    archivo="pii_en_texto_libre_es",
    nombre="Valentina Arrieta Köhler",
    partes=("Valentina", "Arrieta", "Köhler"),
    correo="valentina.arrieta@ejemplo.test",
    telefono="+1 713 555 0101",
    link="https://www.linkedin.com/in/valentina-arrieta-sintetica",
    direccion="1200 Walnut Street",
    codigo_postal="77002",
    foto="https://cdn.ejemplo.test/fotos/valentina-arrieta.jpg",
    correo_de_referencia="marta.quiroga@ejemplo.test",
    telefono_de_referencia="+1 713 555 0199",
    url_de_referencia="https://perfiles.ejemplo.test/valentina-arrieta",
    marca="medicina interna",
    empleador="Hospital General Ridgeview",
    universidad="Universidad de Monterrey",
    ciudad="Laredo",
)

PII_EN = Pii(
    archivo="pii_en_texto_libre_en",
    nombre="Hannah Beaumont Oduya",
    partes=("Hannah", "Beaumont", "Oduya"),
    correo="hannah.beaumont@ejemplo.test",
    telefono="+1 512 555 0144",
    link="https://www.linkedin.com/in/hannah-beaumont-sintetica",
    direccion="4500 Cypress Lane",
    codigo_postal="78745",
    foto="https://cdn.ejemplo.test/fotos/hannah-beaumont.jpg",
    correo_de_referencia="owen.tilley@ejemplo.test",
    telefono_de_referencia="+1 512 555 0177",
    url_de_referencia="https://perfiles.ejemplo.test/hannah-beaumont",
    marca="medical surgical",
    empleador="Ridgeview General Hospital",
    universidad="Cardinal State University",
    ciudad="Odessa",
)


# --- la frontera, resuelta con un `assert` y no con un `ImportError` --------


@dataclass(frozen=True, slots=True)
class Frontera:
    """Los tres símbolos de PR-08, ya resueltos."""

    tipo: type
    violacion: type[BaseException]
    pseudonimizar: Callable[[Candidato], Any]


def frontera() -> Frontera:
    """Resuelve la frontera, o falla diciendo **qué** falta.

    `app/match/proveedor/payload.py` y `app/match/services/pseudonimizador.py`
    existen desde PR-01 (mapa de §2) con solo su docstring, así que un
    `from … import PayloadPseudonimizado` dejaría este archivo sin recolectar y
    el rojo sería un error de importación en vez de la aserción del criterio.
    """
    resueltos: dict[str, Any] = {}
    faltan: list[str] = []
    for modulo, nombres in SIMBOLOS.items():
        importado = importlib.import_module(modulo)
        for nombre in nombres:
            resueltos[nombre] = getattr(importado, nombre, None)
            if resueltos[nombre] is None:
                faltan.append(f"{modulo}.{nombre}")
    assert faltan == [], "la frontera de pseudonimización todavía no existe: falta " + ", ".join(
        faltan
    )
    return Frontera(
        resueltos["PayloadPseudonimizado"],
        resueltos["FronteraViolada"],
        resueltos["pseudonimizar"],
    )


def implementaciones_del_proveedor() -> list[type]:
    """Las clases con `puntuar` del paquete `app/match/proveedor/`, **enumeradas**.

    Enumeradas y no escritas a mano (F34): hoy solo está el MOCK, y el cliente
    real que PR-09 añada entra en el recorrido de la frontera sin que nadie toque
    este test — que es justo el PR en el que la frontera empieza a importar. Se
    instancian **sin argumentos** a propósito: el cliente de PR-09 se configura
    por variable de entorno, no por constructor.
    """
    clases: list[type] = []
    for archivo in sorted(PAQUETE_DEL_PROVEEDOR.glob("*.py")):
        if archivo.stem == "__init__":
            continue
        nombre_modulo = f"app.match.proveedor.{archivo.stem}"
        modulo = importlib.import_module(nombre_modulo)
        clases += [
            valor
            for valor in vars(modulo).values()
            if inspect.isclass(valor)
            and getattr(valor, "__module__", "") == nombre_modulo
            and callable(getattr(valor, "puntuar", None))
        ]
    return clases


def candidato_con(
    sesion: Session, empresa: EmpresaDePrueba, pii: Pii, *, texto: str | None = None
) -> Candidato:
    """Un candidato de esa empresa con su PII en los campos **y** en el CV.

    Los campos estructurados llevan los mismos valores que el texto libre: eso es
    lo que hace comprobable la mitad «valores conocidos» de 3a.
    """
    candidato = Candidato(
        empresa_id=empresa.empresa.id,
        nombre=pii.nombre,
        correo=pii.correo,
        telefono=pii.telefono,
        links=[pii.link],
        cv_texto=pii.crudo() if texto is None else texto,
    )
    sesion.add(candidato)
    sesion.flush()
    sesion.add(
        Postulacion(
            empresa_id=empresa.empresa.id,
            candidato_id=candidato.id,
            vacante_id=empresa.vacante.id,
        )
    )
    sesion.flush()
    return candidato


# --- 1 · CA2: los seis datos de §1a no salen -------------------------------


@pytest.mark.parametrize("pii", (PII_ES, PII_EN), ids=("es", "en"))
def test_ninguno_de_los_seis_datos_de_1a_sale_en_el_cuerpo_enviado(
    sesion: Session, northstar: EmpresaDePrueba, pii: Pii
) -> None:
    """CA2 · «el cuerpo enviado no contiene ninguno de esos seis datos».

    En los dos idiomas, porque CA2 pide fixtures en español y en inglés y porque
    un pseudonimizador que solo reconozca la puntuación de uno de los dos pasaría
    la mitad del criterio. El cuerpo lo construye el pseudonimizador; que sea el
    cuerpo que **de verdad** sale por el camino de escritura es el test 7.
    """
    f = frontera()
    crudo = pii.crudo()
    for etiqueta, valor in pii.seis_datos_de_1a().items():
        assert valor in crudo, f"la fixture {pii.archivo} no trae el dato «{etiqueta}» (F2, F15)"

    payload = f.pseudonimizar(candidato_con(sesion, northstar, pii))

    for etiqueta, valor in pii.seis_datos_de_1a().items():
        assert valor not in payload.cv, f"el cuerpo enviado lleva el dato «{etiqueta}» (CA2)"
    # Y no por haber vaciado el CV: el texto sobre el que se calcula el score
    # sigue ahí (F1, §4 de `llamadas/2026-11-21-cambios-decisiones.md`).
    assert pii.marca in payload.cv, "el pseudonimizador se llevó el texto que decide el score"
    assert payload.sustituciones > 0, "ninguna sustitución sobre un CV lleno de PII"


# --- 2 · CA2, segunda mitad: al cliente no se le puede pasar otra cosa -----


async def test_al_cliente_del_proveedor_no_se_le_puede_pasar_un_cuerpo_sin_pseudonimizar(
    sesion: Session, northstar: EmpresaDePrueba
) -> None:
    """CA2, segunda mitad · a nivel de tipos **y** con un test que lo intenta.

    Las tres mitades van juntas porque por separado ninguna cierra el camino: la
    anotación sola no es un control (no hay comprobador de tipos en `poe check`),
    el rechazo en ejecución sin anotación no se ve al escribir el segundo prompt
    de enero, y las dos juntas no sirven de nada si el tipo se puede construir
    desde fuera del pseudonimizador — sería «pseudonimizado» por declaración
    (`docs/arquitectura.md` §5.4, F6).
    """
    f = frontera()
    crudo = PII_ES.crudo()
    implementaciones = implementaciones_del_proveedor()
    assert implementaciones, "no hay ninguna implementación de proveedor que recorrer"

    # (a) tipos: el `Protocol` y **toda** implementación anotan el tipo de la frontera.
    for destino in (Proveedor, *implementaciones):
        anotacion = get_type_hints(destino.puntuar).get("payload")
        assert anotacion is f.tipo, f"{destino.__name__}.puntuar acepta {anotacion}, no la frontera"

    # (b) el intento: el `dict` que PR-06 pasaba y el texto crudo del CV.
    for cuerpo in ({"cv": crudo}, crudo):
        for clase in implementaciones:
            with pytest.raises(f.violacion):
                await clase().puntuar(cuerpo, IDIOMA_POR_OMISION)

    # (c) y el tipo no se construye fuera del pseudonimizador.
    with pytest.raises(f.violacion):
        f.tipo(cv=crudo, sustituciones=0)

    # (d) el camino largo, que es el único: pseudonimizar y entonces sí llamar.
    payload = f.pseudonimizar(candidato_con(sesion, northstar, PII_ES))
    assert isinstance(payload, f.tipo)
    expuesto = {nombre for nombre in dir(payload) if not nombre.startswith("_")}
    assert {"cv", "sustituciones"} <= expuesto, (
        f"el payload no expone cv ni sustituciones: {expuesto}"
    )
    with pytest.raises(AttributeError):  # inmutable: nadie le vuelve a meter el CV crudo
        payload.cv = crudo
    respuesta = await ProveedorMock().puntuar(payload, IDIOMA_POR_OMISION)
    assert respuesta.score == SCORE_DEL_MOCK


# --- 3 · 3a, valores conocidos: también del texto libre --------------------


def test_los_valores_de_los_campos_estructurados_salen_tambien_del_texto_libre(
    sesion: Session, northstar: EmpresaDePrueba
) -> None:
    """3a · R1·B3 · esto no amplía CA2: es CA2 tal cual.

    CA2 no distingue si el dato viene de un campo o de la narrativa, y el caso
    corriente es el de la narrativa: el nombre en la primera línea del texto, el
    apellido suelto en una frase, la dirección repetida en un párrafo. El
    **apellido por separado** es la aserción que importa: ningún campo lo trae
    solo, así que sale de partir el nombre completo.
    """
    f = frontera()
    pii = PII_ES
    crudo = pii.crudo()
    assert crudo.count(pii.nombre) >= 2, "la fixture no repite el nombre en el texto libre"
    for parte in pii.partes:
        assert parte in crudo, f"la fixture no trae la parte «{parte}» del nombre"

    payload = f.pseudonimizar(candidato_con(sesion, northstar, pii))

    assert pii.nombre not in payload.cv
    for parte in pii.partes:
        assert parte not in payload.cv, f"la parte «{parte}» del nombre sigue en el cuerpo (CA2)"
    assert pii.correo not in payload.cv and pii.telefono not in payload.cv
    assert pii.link not in payload.cv
    assert pii.direccion not in payload.cv, "la dirección sigue en el párrafo del traslado"
    # Se quitó el dato, no el párrafo: lo que rodea al nombre sigue siendo texto
    # puntuable (F1). Un pseudonimizador que borre la frase entera pasa CA2 y
    # rompe CA14.
    assert "apellido paterno" in payload.cv
    assert "turno nocturno" in payload.cv


# --- 4 · 3a, patrones: aunque no estén en ningún campo ---------------------


def test_correo_telefono_y_url_salen_por_patron_aunque_no_esten_en_ningun_campo(
    sesion: Session, northstar: EmpresaDePrueba
) -> None:
    """3a, segunda mitad · correo, teléfono y URL de perfil **por patrón**.

    Son los datos de la sección de referencias y la foto: ninguno está en un
    campo del candidato, así que la limpieza por valores conocidos no los toca.
    El test comprueba primero que de verdad no están en ningún campo — si lo
    estuvieran, pasaría por la razón equivocada.
    """
    f = frontera()
    pii = PII_ES
    candidato = candidato_con(sesion, northstar, pii)
    campos = (candidato.nombre, candidato.correo, candidato.telefono, *candidato.links)
    for etiqueta, valor in pii.datos_sin_campo().items():
        assert valor in pii.crudo(), f"la fixture no trae el dato «{etiqueta}»"
        assert valor not in campos, f"«{etiqueta}» está en un campo: esto no probaría el patrón"

    payload = f.pseudonimizar(candidato)

    for etiqueta, valor in pii.datos_sin_campo().items():
        assert valor not in payload.cv, f"«{etiqueta}» salió de Criba sin pasar por el patrón (CA2)"
    assert "Referencias" in payload.cv, "se fue la sección entera, no el dato"


# --- 5 · la contracara de 3a: lo que no hay que quitar --------------------


def test_un_cv_sin_pii_sale_intacto_y_sin_ninguna_sustitucion(
    sesion: Session, northstar: EmpresaDePrueba
) -> None:
    """El riesgo que 3a introduce, acotado a lo que sí se puede asertar (F1).

    Limpiar por patrón puede **quitar de más** y degradar el texto sobre el que
    se calcula el score (§4 de `llamadas/2026-11-21-cambios-decisiones.md`, F1).
    Cuánto se quita de más **no se decide aquí**: el plan dice que se mide, y lo
    mide CA14 sobre el conjunto dorado (PR-17). Por eso este CV no lleva ningún
    número de licencia que un patrón de teléfono pudiera comerse: asertar que un
    número de licencia sobrevive sería inventar la regla fina que el plan declinó
    escribir. Lo que sí se fija es el límite barato: **sin PII, no se toca nada**,
    y el contador de sustituciones —el número que el cuerpo del PR tiene que
    traer por CV de fixture— vale cero.
    """
    f = frontera()
    candidato = candidato_con(sesion, northstar, PII_ES, texto=CV_SIN_PII)

    payload = f.pseudonimizar(candidato)

    assert payload.cv == CV_SIN_PII, "se tocó un CV que no tenía ni uno de los seis datos de §1a"
    assert payload.sustituciones == 0


# --- 6 · 3b: las entidades que §1a no nombra ------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "pregunta abierta 2 de SPEC.md: §1a no nombra el empleador anterior, la universidad "
        "ni la ciudad no declarada, y detectarlos es una tarea con falsos negativos, no una "
        "regla. Decide Priya (PLAN.md §9, dependencia bloqueante antes del 12-dic-2026). "
        "strict=True: el día que se implemente, este test falla por pasar y alguien quita la "
        "marca. La regla 1.5 de PLAN.md solo admite xfail sobre entidades que §1a no nombra, "
        "nunca sobre uno de los seis datos: esos son los tests 1, 3 y 4."
    ),
)
def test_el_empleador_la_universidad_y_la_ciudad_no_declarada_tambien_salen(
    sesion: Session, northstar: EmpresaDePrueba
) -> None:
    """3b · la fixture ya está escrita: el día que Priya decida, solo se quita la marca."""
    f = frontera()
    pii = PII_ES
    for etiqueta, valor in pii.entidades_que_1a_no_nombra().items():
        assert valor in pii.crudo(), f"la fixture no trae la entidad «{etiqueta}»"

    payload = f.pseudonimizar(candidato_con(sesion, northstar, pii))

    for etiqueta, valor in pii.entidades_que_1a_no_nombra().items():
        assert valor not in payload.cv, f"la entidad «{etiqueta}» sigue en el cuerpo enviado"


# --- 7 · multiempresa en la frontera: ningún CV cruza de empresa ----------


async def test_el_payload_de_cada_empresa_lleva_solo_su_cv_y_nada_de_la_otra(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    activar_match: Callable[[str], None],
    proveedor_contado: ProveedorContado,
) -> None:
    """CA1 y CA2 por el camino **real** de escritura, con dos empresas.

    Los tests 1 a 6 llaman al pseudonimizador a mano, y eso deja sin comprobar lo
    que §5.4 teme: que el cuerpo que **de verdad** sale sea otro. Aquí el par se
    encola, el bucle lo toma y lo que se asercia es lo que el proveedor recibió:
    que es del tipo de la frontera, que no lleva PII, y que el payload de una
    empresa no trae una sola palabra del CV de la otra (D4, el requisito número
    uno, `llamadas/2026-11-20-tomas.md` [03:03]).

    **Meridian se activa a propósito**, aunque la fixture la cree sin anexo (D7):
    lo que este test mide es el cruce de datos, no la activación por empresa, que
    es CA3 y es de PR-10. Sin activarla, el día que PR-10 inserte la comprobación
    dentro de `encolar` este test pasaría con **un** payload y por la razón
    equivocada.
    """
    f = frontera()
    activar_match(meridian.slug)
    de_northstar = candidato_con(sesion, northstar, PII_ES)
    de_meridian = candidato_con(sesion, meridian, PII_EN)
    encolar(sesion, northstar.vacante.id, de_northstar.id)
    encolar(sesion, meridian.vacante.id, de_meridian.id)

    assert await pasadas(sesion, proveedor_contado) == 2
    enviados = proveedor_contado.payloads
    assert len(enviados) == 2
    assert all(isinstance(cuerpo, f.tipo) for cuerpo in enviados), (
        "el cuerpo que sale por el camino de escritura no es el de la frontera: "
        f"{[type(cuerpo).__name__ for cuerpo in enviados]}"
    )

    textos = [cuerpo.cv for cuerpo in enviados]
    for pii in (PII_ES, PII_EN):
        datos = {**pii.seis_datos_de_1a(), **pii.datos_sin_campo()}
        for etiqueta, valor in datos.items():
            for texto in textos:
                assert valor not in texto, f"salió el dato «{etiqueta}» de {pii.archivo} (CA2)"

    # Y cada payload lleva **su** CV: ni mezclados, ni el de la otra empresa.
    norte = [t for t in textos if PII_ES.marca in t]
    sur = [t for t in textos if PII_EN.marca in t]
    assert len(norte) == len(sur) == 1, "un payload no lleva el CV de su empresa"
    assert PII_EN.marca not in norte[0] and PII_ES.marca not in sur[0]

    for empresa, candidato in ((northstar, de_northstar), (meridian, de_meridian)):
        scores = repo_de(sesion, empresa).scores()
        assert [(s.candidato_id, s.empresa_id) for s in scores] == [
            (candidato.id, empresa.empresa.id)
        ], f"{empresa.slug} no guardó exactamente su score"
