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

**Tres más, de la auditoría de CVs sintéticos del 22-nov-2026** (tests 8, 9 y
10). Los siete de arriba quedaron en verde y la auditoría encontró dos fugas que
ninguno imaginaba, las dos **dentro de CA2** y las dos sobre uno de los seis
datos de §1a: el candidato que escribe su propio nombre **sin acentos** en el
texto (test 8) y la foto que llega como **nombre de archivo adjunto** y no como
URL (test 9). La razón por la que los siete anteriores no las ven es la misma en
los dos casos: las fixtures de arriba escriben la PII del texto libre **igual,
carácter por carácter**, que los campos estructurados, así que prueban la
igualdad exacta y no el parecido. El test 10 las vuelve a mirar por el camino de
escritura real y con las dos empresas, que es donde el hallazgo dice que ocurrió
(«sale entero al proveedor»).

**Y nueve más, de la tercera ronda de revisión** (tests 11 a 19). Seis hallazgos
suyos caen dentro de CA2 y ninguno sobre una entidad que §1a no nombre: cuatro
son el **mismo hueco de fixture** que la auditoría del 22-nov —el dato escrito de
otra forma: el link como dominio pelado (I1), la dirección en sintaxis española
(I2), el teléfono en formato mexicano (M5) y el nombre con una letra que no se
descompone (M3b)— y dos son **controles que ya funcionan y que ningún test
ejercitaba**: la normalización NFC (M3a) y la fábrica única de payloads (M1).
Esos dos nacen en verde y está dicho al lado de cada uno. El mapa de hallazgo a
test está en la cabecera de la sección, junto con lo que esta ronda **no**
convierte en test y por qué.

**Cómo fallan estos tests mientras la frontera no existe:** con un `assert` que
dice qué símbolo falta, no con un `ImportError` en la recolección. De eso se
encarga `frontera()`, abajo: los dos módulos del mapa de §2 ya existen (PR-01) y
están vacíos, así que los nombres se resuelven con `getattr` y se asercian.
"""

from __future__ import annotations

import importlib
import inspect
import re
import unicodedata
from collections.abc import Callable, Mapping
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

# Los símbolos que PR-08 tiene que crear, con su módulo del mapa de §2.
SIMBOLOS = {
    "app.match.proveedor.payload": ("PayloadPseudonimizado", "FronteraViolada", "unica_fabrica"),
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
    """Los símbolos de PR-08, ya resueltos."""

    tipo: type
    violacion: type[BaseException]
    pseudonimizar: Callable[[Candidato], Any]
    # La tercera pata de la frontera (test 17, M1): el decorador que registra la
    # **única** fábrica de payloads. Se resuelve aquí y no con un `import` para
    # que el día que no exista el rojo sea el `assert` de `frontera()`.
    unica_fabrica: Callable[..., Any]


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
        resueltos["unica_fabrica"],
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


# --- 8, 9 y 10 · la auditoría de CVs sintéticos del 22-nov-2026 -------------
#
# Dos fugas, las dos de CA2 y las dos sobre uno de los seis datos de §1a. No
# amplían el criterio: lo leen donde los tests 1 a 7 no miraban, porque sus
# fixtures escriben el dato del texto libre **idéntico** al del campo
# estructurado y así solo prueban la igualdad exacta.


@dataclass(frozen=True, slots=True)
class Fuga:
    """Un CV de la auditoría: sus campos, su marca y lo que no puede salir.

    `fugas` son los valores que **hoy** salen enteros al proveedor, declarados
    aquí al lado del test y con la etiqueta del dato de §1a al que pertenecen. El
    test asercia primero que la fixture los trae (si no, pasaría sin probar nada,
    que es el punto ciego que F2 y F15 nombran) y después que ninguno sobrevive.
    """

    archivo: str
    nombre: str
    correo: str
    telefono: str
    marca: str
    fugas: dict[str, str]
    # Los links del campo `links` del candidato. Vacío en las dos fugas de la
    # auditoría; la fixture de la tercera ronda sí lo usa, porque su hallazgo (I1)
    # es justo que el link del **campo** es la URL completa con `https://` y el
    # del texto es el dominio pelado: dos formas de escribir el mismo perfil.
    links: tuple[str, ...] = ()

    def crudo(self) -> str:
        return cv(self.archivo)


# Fuga 1 · «José Ángel Treviño» firma el CV como «Jose Angel Trevino».
# El campo `nombre` lleva los acentos y el texto no, así que la pasada de valores
# conocidos —que compara el valor tal cual, sin mayúsculas pero **con** acentos—
# no reconoce ni el nombre completo ni sus partes. Es nombre, el primero de §1a.
FUGA_SIN_ACENTOS = Fuga(
    archivo="pii_sin_acentos_es",
    nombre="José Ángel Treviño",
    correo="jose.trevino@ejemplo.test",
    telefono="+1 956 555 0143",
    marca="admisiones hospitalarias",
    fugas={
        "nombre completo sin acentos (§1a · nombre)": "Jose Angel Trevino",
        "nombre de pila sin acento (§1a · nombre)": "Jose",
        "segundo nombre sin acento (§1a · nombre)": "Angel",
        "apellido sin acento (§1a · nombre)": "Trevino",
    },
)

# Fuga 2 · la foto de «Sofía Ramírez» llega como `[Foto adjunta: …png]`.
# No es una URL, así que el patrón de enlaces no la toca; y el nombre que lleva
# dentro va sin acentos y pegado con guion bajo, así que la pasada de valores
# conocidos tampoco: `_` es carácter de palabra y el borde `(?!\w)` no casa. Son
# dos datos de §1a a la vez, la foto y el nombre.
FUGA_FOTO_ADJUNTA = Fuga(
    archivo="pii_foto_adjunta_es",
    nombre="Sofía Ramírez",
    correo="sofia.ramirez@ejemplo.test",
    telefono="+1 210 555 0188",
    marca="instrumentista de guardia",
    fugas={
        "archivo de la foto (§1a · fotos)": "sofia_ramirez_2026.png",
        "nombre dentro del archivo de la foto (§1a · nombre)": "sofia_ramirez",
        "apellido sin acento (§1a · nombre)": "ramirez",
    },
)


def candidato_de(sesion: Session, empresa: EmpresaDePrueba, fuga: Fuga) -> Candidato:
    """El candidato de una fuga, con sus campos **acentuados** y su CV sin acentos.

    Es la diferencia con `candidato_con`: ahí los campos y el texto llevan el
    mismo valor carácter por carácter, y aquí no, que es justo el caso que la
    auditoría encontró.
    """
    candidato = Candidato(
        empresa_id=empresa.empresa.id,
        nombre=fuga.nombre,
        correo=fuga.correo,
        telefono=fuga.telefono,
        links=list(fuga.links),
        cv_texto=fuga.crudo(),
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


def siguen_en(cuerpo: str, datos: Mapping[str, str]) -> list[str]:
    """Las etiquetas de los datos de `datos` que siguen en el cuerpo enviado.

    La comparación **ignora mayúsculas** porque CA2 habla del dato y no de su
    forma de escribirlo: un nombre de archivo en minúsculas es el mismo nombre.
    Lo que no ignora son los acentos — no se normaliza nada aquí a propósito:
    cómo se reconoce «Jose» como «José» es decisión del constructor, y un test
    que la tomara estaría escribiendo el arreglo en vez del criterio.
    """
    plano = cuerpo.lower()
    return [etiqueta for etiqueta, valor in datos.items() if valor.lower() in plano]


def fugas_en(cuerpo: str, fuga: Fuga) -> list[str]:
    """Lo mismo, para los datos declarados en una `Fuga`."""
    return siguen_en(cuerpo, fuga.fugas)


@pytest.mark.parametrize(
    "fuga", (FUGA_SIN_ACENTOS, FUGA_FOTO_ADJUNTA), ids=("sin-acentos", "foto-adjunta")
)
def test_la_fixture_de_cada_fuga_trae_de_verdad_el_dato_que_se_escapa(fuga: Fuga) -> None:
    """La guardia de las dos fixtures nuevas, antes de mirar el pseudonimizador.

    Si un día alguien «limpia» la fixture y le quita el nombre sin acentos o el
    archivo de la foto, los tests 8 y 9 se pondrían verdes sin que nadie hubiera
    arreglado nada. Esto es lo que impide ese verde (F2, F15).
    """
    crudo = fuga.crudo()
    for etiqueta, valor in fuga.fugas.items():
        assert valor in crudo, f"la fixture {fuga.archivo} ya no trae «{etiqueta}»"
    assert fuga.marca in crudo, "la fixture no trae su marca: el test 10 no podría distinguirla"
    assert fuga.nombre in crudo, (
        "la fixture no trae el nombre acentuado: sin él no se distingue la fuga "
        "de un pseudonimizador que no funcione en absoluto"
    )


# --- 8 · el nombre escrito sin acentos ------------------------------------


def test_el_nombre_escrito_sin_acentos_en_el_cv_tampoco_sale_en_el_cuerpo_enviado(
    sesion: Session, northstar: EmpresaDePrueba
) -> None:
    """CA2 · primera fuga de la auditoría · «Jose Angel Trevino» es su nombre.

    §1a dice «nombre», no «el nombre tal como está escrito en la base de datos».
    Un candidato que firma su CV sin tildes —porque el teclado, porque el PDF,
    porque la nómina no las admite— sigue siendo identificable por quien lea el
    cuerpo al otro lado: «Jose Angel Trevino» nombra a una sola persona. Esto no
    es la pregunta abierta 2 (empleador, universidad, ciudad): es el primero de
    los seis datos que §1a sí nombra, así que la regla 1.5 de `PLAN.md` no admite
    `xfail` aquí.

    La aserción que importa es la del **nombre acentuado también fuera**: prueba
    que el pseudonimizador no está roto del todo, y que lo que falla es solo el
    parecido. Si las dos mitades fallaran juntas, el rojo no diría nada nuevo.
    """
    f = frontera()
    fuga = FUGA_SIN_ACENTOS

    payload = f.pseudonimizar(candidato_de(sesion, northstar, fuga))

    assert fuga.nombre not in payload.cv, "ni el nombre acentuado sale: la frontera no funciona"
    assert fugas_en(payload.cv, fuga) == [], (
        "el cuerpo enviado lleva el nombre del candidato escrito sin acentos (CA2, §1a · nombre): "
        f"{fugas_en(payload.cv, fuga)}"
    )
    # Y se quitó el dato, no la frase: el texto que decide el score sigue ahí (F1).
    assert fuga.marca in payload.cv, "el pseudonimizador se llevó el texto que decide el score"


# --- 9 · la foto que llega como nombre de archivo adjunto -----------------


def test_el_nombre_del_archivo_de_la_foto_adjunta_no_sale_en_el_cuerpo_enviado(
    sesion: Session, northstar: EmpresaDePrueba
) -> None:
    """CA2 · segunda fuga de la auditoría · `[Foto adjunta: sofia_ramirez_2026.png]`.

    El test 4 cubre la foto **cuando es una URL** (`![Foto de perfil](https://…)`)
    y ahí el patrón de enlaces la barre. Una foto adjunta no tiene URL: tiene el
    nombre del archivo, que es la forma en que una foto llega a un CV subido. Y
    ese nombre lleva dentro el de la candidata, con las palabras pegadas por
    guion bajo y sin acentos.

    Son **dos** de los seis datos de §1a en la misma línea, y el rojo se sostiene
    con cualquiera de las dos lecturas de «fotos»: si la referencia a la foto
    contara como foto, falla por foto; y si no contara, falla igual por el
    nombre, que no admite lectura estrecha. Lo que **no** se asercia aquí es cómo
    se arregla —si cae todo el nombre de archivo de imagen o solo la parte que es
    un nombre—: eso es del constructor.
    """
    f = frontera()
    fuga = FUGA_FOTO_ADJUNTA

    payload = f.pseudonimizar(candidato_de(sesion, northstar, fuga))

    assert fuga.nombre not in payload.cv, "ni el nombre acentuado sale: la frontera no funciona"
    assert fugas_en(payload.cv, fuga) == [], (
        "el cuerpo enviado lleva la foto adjunta de la candidata y su nombre dentro "
        f"(CA2, §1a · fotos y nombre): {fugas_en(payload.cv, fuga)}"
    )
    assert fuga.marca in payload.cv, "se fue la sección entera, no el dato (F1)"


# --- 10 · las dos fugas por el camino real, y sin cruzar de empresa -------


async def test_las_dos_fugas_tampoco_salen_por_el_camino_real_ni_cruzan_de_empresa(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    activar_match: Callable[[str], None],
    proveedor_contado: ProveedorContado,
) -> None:
    """CA2 y CA1 · las dos fugas donde la auditoría dice que ocurrieron.

    El hallazgo es «sale entero **al proveedor**», y los tests 8 y 9 llaman al
    pseudonimizador a mano: eso deja sin comprobar lo que §5.4 teme, que el
    cuerpo que de verdad sale sea otro. Aquí los dos pares se encolan, el bucle
    los toma, y lo que se asercia es lo que el proveedor recibió.

    Y se asercia con las **dos empresas**, que es el requisito número uno del
    cliente (D4, CA1, [03:03]): un pseudonimizador que arreglara las dos fugas
    leyendo los campos del candidato equivocado las cerraría en el test 8 y 9 y
    seguiría mandando el nombre de la candidata de Meridian dentro del payload de
    Northstar. **Meridian se activa a propósito**, igual que en el test 7: lo que
    se mide aquí es el cruce de datos, no la activación por empresa (CA3, PR-10).
    """
    f = frontera()
    activar_match(meridian.slug)
    de_northstar = candidato_de(sesion, northstar, FUGA_SIN_ACENTOS)
    de_meridian = candidato_de(sesion, meridian, FUGA_FOTO_ADJUNTA)
    encolar(sesion, northstar.vacante.id, de_northstar.id)
    encolar(sesion, meridian.vacante.id, de_meridian.id)

    assert await pasadas(sesion, proveedor_contado) == 2
    enviados = proveedor_contado.payloads
    assert len(enviados) == 2
    assert all(isinstance(cuerpo, f.tipo) for cuerpo in enviados)

    textos = [cuerpo.cv for cuerpo in enviados]
    for fuga in (FUGA_SIN_ACENTOS, FUGA_FOTO_ADJUNTA):
        for texto in textos:
            assert fugas_en(texto, fuga) == [], (
                f"salió al proveedor el dato de {fuga.archivo} (CA2): {fugas_en(texto, fuga)}"
            )

    # Cada payload lleva **su** CV: ni mezclados, ni el de la otra empresa.
    norte = [t for t in textos if FUGA_SIN_ACENTOS.marca in t]
    sur = [t for t in textos if FUGA_FOTO_ADJUNTA.marca in t]
    assert len(norte) == len(sur) == 1, "un payload no lleva el CV de su empresa"
    assert FUGA_FOTO_ADJUNTA.marca not in norte[0] and FUGA_SIN_ACENTOS.marca not in sur[0]

    for empresa, candidato in ((northstar, de_northstar), (meridian, de_meridian)):
        scores = repo_de(sesion, empresa).scores()
        assert [(s.candidato_id, s.empresa_id) for s in scores] == [
            (candidato.id, empresa.empresa.id)
        ], f"{empresa.slug} no guardó exactamente su score"


# --- 11 a 19 · la tercera ronda de revisión de PR-08 -----------------------
#
# Cuatro hallazgos de conducta y dos de cobertura, **todos dentro de CA2** y
# ninguno sobre una entidad que §1a no nombre (las de 3b siguen en el test 6):
#
#   I1 · el link a perfil escrito como dominio pelado        → test 11 (en rojo)
#   I2 · la dirección en sintaxis española                   → test 12 (en rojo)
#   M5 · el teléfono en formato mexicano                      → test 13 (en rojo)
#   M2 · el apellido de dos letras                            → tests 14 (rojo) y 15
#   M3 · la letra que no se descompone, y la NFC              → tests 16 (rojo) y 17
#   M1 · la tercera pata de la frontera, sin test             → test 18
#   y los cuatro datos nuevos por el camino real, con las dos empresas → test 19
#
# Los cinco primeros son el **mismo tipo de hueco** que la auditoría del
# 22-nov-2026 encontró con el nombre sin acentos, y por eso se leen con ella:
# las fixtures escriben cada dato en **una sola sintaxis** —el link con
# `https://`, la dirección con el número delante, el teléfono en grupos de
# 3-3-4— así que prueban que el patrón reconoce esa forma de escribirlo, no que
# el dato no sale. §1a dice «teléfono», no «teléfono en el formato de Texas».
#
# Dos nacen en **verde** a propósito y se declara aquí para que nadie los lea
# como defectos: el test 17 (la normalización NFC) y el test 18 (la segunda
# fábrica) cubren controles que **ya funcionan y que ningún test ejercitaba** —
# quitar la línea de NFC, o cambiar la guardia de `unica_fabrica` por un
# `if False:`, deja hoy la suite entera verde. Son regresión, no criterio nuevo.
#
# Y lo que esta ronda **no** convierte en test, dicho en voz alta:
#   · el *handle* de Twitter (`@sofiaramirez`, segunda mitad de M5): §1a dice
#     «links a perfiles» y un handle sin dominio no es un link. Decidir que
#     cuenta sería inventar un requisito (CLAUDE.md), así que va a preguntas
#     abiertas con la pregunta 2 de `SPEC.md` y no a un `xfail`;
#   · M4 (la auditoría del 22-nov citada por código, tests y fixtures y sin
#     archivo en `docs/`) es un defecto de **cita**, no de conducta: lo arregla
#     quien registre la fuente, y un test no lo puede sostener. Lo único de M4
#     que vive en `tests/` —el comentario duplicado y contradictorio de
#     `ARCHIVOS_DE_CV`— va arreglado en `conftest.py` en este mismo commit.


# Los dominios pelados (I1). El valor que se asercia es **el trozo que sigue
# llevando al perfil**: con el slug limpio de nombres, `linkedin.com/in/` basta
# para identificarlo, y `github.com/rvega88` no lo toca nada.
ENLACES_SIN_ESQUEMA = {
    "link de perfil sin esquema (§1a · links a perfiles)": "linkedin.com/in/",
    "link de perfil con alias (§1a · links a perfiles)": "github.com/rvega88",
}

# La dirección en formato español (I2): la vía delante, el número al final.
DIRECCION_EN_SINTAXIS_ESPANOLA = {
    "dirección en sintaxis española (§1a · dirección)": "Calle Hidalgo 123",
}

# El teléfono de la referencia en formato mexicano (M5): grupos de 2-4-4.
TELEFONOS_EN_FORMATO_MEXICANO = {
    "teléfono de referencia, formato local (§1a · teléfono)": "81-1234-5678",
    "teléfono de referencia, formato internacional (§1a · teléfono)": "+52 81 1234 5678",
}

FORMAS_DE_ESCRIBIR = Fuga(
    archivo="pii_otras_formas_de_escribir_es",
    nombre="Renata Solís Vega",
    correo="renata.solis@ejemplo.test",
    telefono="+1 713 555 0122",
    marca="urgencias pediátricas",
    fugas={
        **ENLACES_SIN_ESQUEMA,
        **DIRECCION_EN_SINTAXIS_ESPANOLA,
        **TELEFONOS_EN_FORMATO_MEXICANO,
    },
    # El campo lleva la URL **completa**, que es la otra mitad de I1: la pasada
    # de valores conocidos compara el valor entero del campo, así que el dominio
    # pelado del texto no es «el mismo valor» y solo puede caer por patrón.
    links=("https://www.linkedin.com/in/renata-solis-sintetica",),
)


# Los tres CV de abajo van escritos aquí y no en un archivo de fixture, por la
# misma razón que `CV_SIN_PII` del test 5: lo que prueban es **cómo se reconoce
# el valor de un campo dentro del texto**, así que son dos frases y leerlas al
# lado de su aserción es lo que las hace comprobables. Siguen siendo sintéticos
# (D3 modificado, D15, F12).

# M2 · un apellido de dos letras. `Li`, `Wu`, `Ng`, `Vo`, `Xu`, `Ho` son
# apellidos completos y frecuentes, y el nombre es el primero de los seis de §1a.
NOMBRE_DE_DOS_LETRAS = "Mei Li"
CV_DEL_APELLIDO_DE_DOS_LETRAS = (
    "Soy Mei Li, enfermera registrada con licencia vigente en Texas. "
    "La enfermera Li atiende el banco de sangre en el turno de noche y "
    "firma como Li las notas de transfusión."
)
FUGAS_DE_DOS_LETRAS = {
    "apellido de dos letras en la narrativa (§1a · nombre)": "enfermera Li",
    "apellido de dos letras al final de la frase (§1a · nombre)": "firma como Li",
}

# M2, la contracara · una partícula de dos letras del propio nombre. Es el
# límite barato de F1, como el test 5: el arreglo de `Li` no puede llevarse los
# «de» y los «la» de la narrativa, que es lo que el `LARGO_MINIMO` del módulo
# dice que está evitando.
NOMBRE_CON_PARTICULAS = "Ana de la Rosa"
CV_CON_PARTICULAS = (
    "Ana de la Rosa, jefa de piso. Trabajo de noche en la unidad de quemados "
    "y de día en consulta externa."
)
NARRATIVA_QUE_NO_SE_TOCA = ("de piso", "de noche", "la unidad", "de día")

# M3(b) · letras latinas que **no** se descomponen por NFD: `ø`, `ł`, `đ`, `ħ`.
# El docstring del módulo enumera la eszett, la ligadura y la i sin punto del
# turco como excluidas a propósito; estas no están enumeradas y son el caso
# realista en un apellido.
NOMBRE_CON_OTRA_LETRA = "Søren Łukasz"
CV_DEL_NOMBRE_CON_OTRA_LETRA = (
    "Soy Soren Lukasz, auxiliar de farmacia hospitalaria con seis años en "
    "oncología. En la plataforma figuro como Søren Łukasz, con sus barras; "
    "en el CV escribo Lukasz, que es como lo pronuncian aquí."
)
FUGAS_DE_OTRA_LETRA = {
    "nombre completo escrito con otra letra (§1a · nombre)": "Soren Lukasz",
    "apellido escrito con otra letra (§1a · nombre)": "Lukasz",
}

# M3(a) · la tilde **descompuesta**: la `e` y el acento en dos puntos de código
# (U+0301), que es lo que puede traer un CV extraído de un PDF.
NOMBRE_CON_TILDE = "José Ángel Treviño"
CV_CON_LA_TILDE_DESCOMPUESTA = unicodedata.normalize(
    "NFD",
    "Soy José Ángel Treviño, auxiliar administrativo en admisiones "
    "hospitalarias. Treviño es mi apellido paterno.",
)


def candidato_declarado(
    sesion: Session,
    empresa: EmpresaDePrueba,
    *,
    nombre: str,
    texto: str,
    telefono: str = "+1 713 555 0133",
) -> Candidato:
    """Un candidato de esa empresa con su nombre en el campo y su CV a mano.

    El correo sale del nombre para que dos candidatos del mismo test no choquen
    con `uq_candidatos_empresa_correo`, y se pasa siempre: `candidatos.correo` no
    admite nulo.
    """
    identificador = re.sub(r"[^a-z]+", "-", _sin_tildes(nombre).lower()).strip("-")
    candidato = Candidato(
        empresa_id=empresa.empresa.id,
        nombre=nombre,
        correo=f"{identificador}@ejemplo.test",
        telefono=telefono,
        links=[],
        cv_texto=texto,
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


def _sin_tildes(texto: str) -> str:
    """Solo para construir el correo de un candidato declarado, nunca para asertar."""
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def campos_de(candidato: Candidato) -> tuple[str, ...]:
    """Los campos estructurados del candidato, para la guardia de «esto prueba el patrón»."""
    return (candidato.nombre, candidato.correo, candidato.telefono, *candidato.links)


def test_la_fixture_de_la_tercera_ronda_trae_de_verdad_los_datos_que_se_escapan() -> None:
    """La guardia de la fixture nueva, antes de mirar el pseudonimizador.

    Igual que la de las dos fugas de la auditoría: si alguien «limpia» la fixture
    y le quita el dominio pelado, la dirección en español o el teléfono mexicano,
    los tests 11, 12 y 13 se pondrían verdes sin que nadie hubiera arreglado nada
    (F2, F15).
    """
    fuga = FORMAS_DE_ESCRIBIR
    crudo = fuga.crudo()
    for etiqueta, valor in fuga.fugas.items():
        assert valor in crudo, f"la fixture {fuga.archivo} ya no trae «{etiqueta}»"
    assert fuga.marca in crudo, "la fixture no trae su marca: el test 19 no podría distinguirla"
    assert fuga.nombre in crudo, (
        "la fixture no trae el nombre: sin él no se distingue la fuga de un "
        "pseudonimizador que no funcione en absoluto"
    )
    assert fuga.links[0] in crudo, "el campo `links` y el texto no hablan del mismo perfil (I1)"


# --- 11 · el link a perfil escrito como dominio pelado --------------------


def test_un_link_a_perfil_escrito_como_dominio_pelado_tampoco_sale_en_el_cuerpo_enviado(
    sesion: Session, northstar: EmpresaDePrueba
) -> None:
    """CA2 · I1 · «links a perfiles» es uno de los seis datos de §1a.

    El patrón de enlace solo reconoce lo que lleva `https?://` o `www.`, y un
    perfil escrito como dominio pelado —`linkedin.com/in/…`, `github.com/…`— es
    la forma más corriente de escribirlo en un CV. Los tests 1, 3, 4, 7 y 10 no
    lo ven porque las cuatro fixtures anteriores escriben **todos** sus links con
    `https://`: prueban que el patrón reconoce esa sintaxis, no que el dato no
    sale.

    Y la pasada de valores conocidos no es la segunda red aquí, por eso la
    guardia de abajo compara por **igualdad** y no por contención: esa pasada
    busca el valor **entero** del campo —la URL con esquema—, así que del dominio
    pelado solo se lleva las partes del nombre que el slug repita. Lo que queda
    (`linkedin.com/in/[nombre]-[nombre]-sintetica`) sigue llevando al perfil, y
    `github.com/rvega88` no lo toca nada.
    """
    f = frontera()
    fuga = FORMAS_DE_ESCRIBIR
    candidato = candidato_de(sesion, northstar, fuga)
    for etiqueta, valor in ENLACES_SIN_ESQUEMA.items():
        assert valor not in campos_de(candidato), (
            f"«{etiqueta}» es, tal cual, un campo del candidato: esto no probaría el patrón"
        )

    payload = f.pseudonimizar(candidato)

    assert siguen_en(payload.cv, ENLACES_SIN_ESQUEMA) == [], (
        "el cuerpo enviado lleva un link al perfil del candidato (CA2, §1a · links a perfiles): "
        f"{siguen_en(payload.cv, ENLACES_SIN_ESQUEMA)}"
    )
    # El link del campo sí cae hoy: es la mitad que prueba que la frontera no
    # está roma del todo y que lo que falla es solo la forma de escribirlo.
    assert fuga.links[0] not in payload.cv, "ni el link con esquema sale: la frontera no funciona"
    assert fuga.marca in payload.cv, "se fue el párrafo, no el dato (F1)"


# --- 12 · la dirección escrita en sintaxis española -----------------------


def test_una_direccion_escrita_en_sintaxis_espanola_tampoco_sale_en_el_cuerpo_enviado(
    sesion: Session, northstar: EmpresaDePrueba
) -> None:
    """CA2 · I2 · la dirección es dato de §1a y **no tiene segunda red**.

    El patrón de dirección pide el número de portal **antes** del sufijo de
    calle (`1200 Walnut Street`). En español el nombre de la vía va primero y el
    número al final (`Calle Hidalgo 123`), así que una dirección escrita así sale
    entera: solo cae el código postal, que es otro patrón.

    Y aquí no hay segunda red: `candidatos` no tiene columna de dirección
    (`app/plataforma/modelos.py`), así que la pasada de valores conocidos no la
    puede conocer. Si el patrón no la reconoce, el dato sale.

    Esta es, además, la mitad «en español» que CA2 pide y que la fixture ES
    anterior probaba sobre sintaxis inglesa: el test 1 dice en su docstring que
    los dos idiomas están «porque un pseudonimizador que solo reconozca la
    puntuación de uno de los dos pasaría la mitad del criterio», y es exactamente
    lo que pasaba.
    """
    f = frontera()
    fuga = FORMAS_DE_ESCRIBIR
    candidato = candidato_de(sesion, northstar, fuga)
    for etiqueta, valor in DIRECCION_EN_SINTAXIS_ESPANOLA.items():
        assert valor not in campos_de(candidato), f"«{etiqueta}» está en un campo del candidato"

    payload = f.pseudonimizar(candidato)

    assert siguen_en(payload.cv, DIRECCION_EN_SINTAXIS_ESPANOLA) == [], (
        "el cuerpo enviado lleva la dirección del candidato (CA2, §1a · dirección): "
        f"{siguen_en(payload.cv, DIRECCION_EN_SINTAXIS_ESPANOLA)}"
    )
    # El código postal con su estado sí cae hoy, y es la mitad que prueba que lo
    # que falla es la sintaxis de la calle y no el patrón de dirección entero.
    assert "NL 64000" not in payload.cv, "ni el código postal sale: la frontera no funciona"
    assert fuga.marca in payload.cv, "se fue el párrafo, no el dato (F1)"


# --- 13 · el teléfono en formato mexicano ---------------------------------


def test_un_telefono_escrito_en_formato_mexicano_tampoco_sale_en_el_cuerpo_enviado(
    sesion: Session, northstar: EmpresaDePrueba
) -> None:
    """CA2 · M5 · el teléfono es dato de §1a, y §1a no habla de formatos.

    El patrón pide grupos de 3-3-4, que es el formato de Estados Unidos. El de
    la referencia va en 2-4-4 (`81-1234-5678`, `+52 81 1234 5678`), que es lo que
    trae un CV de la frontera —la fixture ES anterior ya nombra Monterrey y
    Laredo— y no cae por ningún patrón. Como el teléfono de la referencia no está
    en ningún campo del candidato, el patrón es la única red: es el mismo caso
    que el test 4 ya asercia **en formato estadounidense**.

    **Lo que este test no decide:** cuánto se puede ensanchar el patrón sin
    comerse un número de licencia. Ese es el riesgo de «quitar de más» que el
    plan manda **medir** (PR-08 §«Lo que 3a cuesta», F1) y que mide CA14 sobre el
    conjunto dorado (PR-17). Aquí solo se asercia el criterio: el teléfono no
    sale. El test 5 sigue acotando el otro lado.

    **Y la otra mitad de M5 no se asercia:** un *handle* (`@sofiaramirez`) no es
    un «link a perfil» tal como §1a lo nombra, y decidir que cuenta sería
    inventar un requisito. Va a preguntas abiertas, no a un `xfail` (la regla 1.5
    de `PLAN.md` solo admite `xfail` sobre lo que §1a no nombra, y esto es
    justamente lo que no se sabe si §1a nombra).
    """
    f = frontera()
    fuga = FORMAS_DE_ESCRIBIR
    candidato = candidato_de(sesion, northstar, fuga)
    for etiqueta, valor in TELEFONOS_EN_FORMATO_MEXICANO.items():
        assert valor not in campos_de(candidato), (
            f"«{etiqueta}» está en un campo: esto no probaría el patrón"
        )

    payload = f.pseudonimizar(candidato)

    assert siguen_en(payload.cv, TELEFONOS_EN_FORMATO_MEXICANO) == [], (
        "el cuerpo enviado lleva un teléfono (CA2, §1a · teléfono): "
        f"{siguen_en(payload.cv, TELEFONOS_EN_FORMATO_MEXICANO)}"
    )
    assert fuga.telefono not in payload.cv, "ni el teléfono del campo sale: la frontera no funciona"
    assert "Referencias" in payload.cv, "se fue la sección entera, no el dato (F1)"


# --- 14 · el apellido de dos letras ---------------------------------------


def test_un_apellido_de_dos_letras_tampoco_sale_del_texto_libre(
    sesion: Session, northstar: EmpresaDePrueba
) -> None:
    """CA2 · M2 · el nombre es el primero de los seis datos de §1a.

    `LARGO_MINIMO` deja fuera de la pasada de valores conocidos cualquier parte
    del nombre de menos de tres letras, y `Li`, `Wu`, `Ng`, `Vo`, `Xu` o `Ho` son
    apellidos completos y frecuentes, no iniciales. Con el campo `nombre` en
    «Mei Li», el nombre completo sí cae —tiene cinco letras— y el apellido suelto
    de la narrativa sale: «La enfermera Li atiende el banco de sangre» identifica
    a la candidata para quien lea el cuerpo al otro lado.

    No es la pregunta abierta 2 (empleador, universidad, ciudad): es nombre, así
    que la regla 1.5 de `PLAN.md` no admite `xfail` aquí. Cómo se arregla es del
    constructor; lo que este test fija es que el dato no sale y —en el test 15—
    que el arreglo no se lleva la narrativa.
    """
    f = frontera()
    candidato = candidato_declarado(
        sesion, northstar, nombre=NOMBRE_DE_DOS_LETRAS, texto=CV_DEL_APELLIDO_DE_DOS_LETRAS
    )

    payload = f.pseudonimizar(candidato)

    assert NOMBRE_DE_DOS_LETRAS not in payload.cv, (
        "ni el nombre completo sale: la frontera no funciona"
    )
    assert siguen_en(payload.cv, FUGAS_DE_DOS_LETRAS) == [], (
        "el cuerpo enviado lleva el apellido del candidato (CA2, §1a · nombre): "
        f"{siguen_en(payload.cv, FUGAS_DE_DOS_LETRAS)}"
    )
    assert "banco de sangre" in payload.cv, "se fue la frase, no el dato (F1)"


# --- 15 · la contracara de 14: la partícula no se come la narrativa -------


def test_una_particula_de_dos_letras_del_nombre_no_se_come_la_narrativa(
    sesion: Session, northstar: EmpresaDePrueba
) -> None:
    """El límite barato del arreglo de M2 (F1), como el test 5 lo es de 3a.

    `LARGO_MINIMO` existe por una razón escrita en el módulo: «de», «la» o una
    inicial suelta se comerían media narrativa. En «Ana de la Rosa» —un nombre
    español corriente— las partes cortas son partículas, y el texto sobre el que
    se calcula el score está lleno de ellas: «jefa **de** piso», «**de** noche»,
    «**la** unidad». Un arreglo de M2 que simplemente baje el mínimo pasa el test
    14 y rompe CA14.

    **Nace en verde** y es a propósito: hoy nada se lleva esas partículas. Lo que
    hace es impedir que el arreglo del test 14 las empiece a llevar, que es la
    única forma de que ese arreglo salga mal sin que nadie lo vea.
    """
    f = frontera()
    candidato = candidato_declarado(
        sesion, northstar, nombre=NOMBRE_CON_PARTICULAS, texto=CV_CON_PARTICULAS
    )

    payload = f.pseudonimizar(candidato)

    assert NOMBRE_CON_PARTICULAS not in payload.cv, "el nombre completo sigue en el cuerpo (CA2)"
    for trozo in NARRATIVA_QUE_NO_SE_TOCA:
        assert trozo in payload.cv, (
            f"el pseudonimizador se llevó «{trozo}», que es narrativa y no el nombre de nadie "
            "(F1, §4 de llamadas/2026-11-21-cambios-decisiones.md)"
        )


# --- 16 · el nombre escrito con una letra que no se descompone ------------


def test_el_nombre_escrito_con_otra_letra_latina_tampoco_sale_en_el_cuerpo_enviado(
    sesion: Session, northstar: EmpresaDePrueba
) -> None:
    """CA2 · M3(b) · «Soren Lukasz» es el nombre de «Søren Łukasz».

    La tabla de familias de letra se construye por descomposición canónica, y hay
    letras latinas que **no se descomponen**: `ø`, `ł`, `đ`, `ħ`. Para ellas no
    hay familia, así que el campo `Søren Łukasz` no reconoce el `Soren Lukasz`
    que el candidato escribe en su CV — que es exactamente la fuga que la segunda
    ronda cerró para los acentos («el nombre escrito con otra letra»).

    El docstring del módulo enumera la eszett, la ligadura y la i sin punto del
    turco como excluidas **a propósito**, porque ahí no hay «la misma letra sin
    tilde»; estas sí la tienen y no están enumeradas. Y el PR declara haber
    cerrado esta clase de fuga con una
    tabla automática «para que no se quede corta el día del primer apellido con
    ğ» (F34): `ğ` sí entra, `ł` no.

    La aserción de que el nombre **tal como está en el campo** sí cae es la que
    prueba que lo que falla es solo el parecido.
    """
    f = frontera()
    candidato = candidato_declarado(
        sesion, northstar, nombre=NOMBRE_CON_OTRA_LETRA, texto=CV_DEL_NOMBRE_CON_OTRA_LETRA
    )

    payload = f.pseudonimizar(candidato)

    assert NOMBRE_CON_OTRA_LETRA not in payload.cv, (
        "ni el nombre tal como está en el campo sale: la frontera no funciona"
    )
    assert siguen_en(payload.cv, FUGAS_DE_OTRA_LETRA) == [], (
        "el cuerpo enviado lleva el nombre del candidato escrito con otra letra "
        f"(CA2, §1a · nombre): {siguen_en(payload.cv, FUGAS_DE_OTRA_LETRA)}"
    )
    assert "farmacia hospitalaria" in payload.cv, "se fue la frase, no el dato (F1)"


# --- 17 · la tilde descompuesta (regresión: nace en verde) ----------------


def test_el_nombre_con_la_tilde_descompuesta_tampoco_sale_en_el_cuerpo_enviado(
    sesion: Session, northstar: EmpresaDePrueba
) -> None:
    """CA2 · M3(a) · el CV extraído de un PDF puede traer la tilde aparte.

    El módulo normaliza el texto a NFC antes de limpiarlo, y esa línea es la otra
    mitad de «los acentos no cuentan»: sin ella, el `José` del campo —un punto de
    código— no casa con el `José` del texto cuando ese viene en dos puntos de
    código (la `e` y el acento suelto, U+0301), y el nombre sale entero. Ninguna
    fixture trae una tilde descompuesta, así que **quitar la línea deja hoy la
    suite entera verde**.

    **Nace en verde** y es a propósito: no es un defecto, es un control sin test
    (rúbrica 4). La aserción que lo sostiene es la de la forma **descompuesta**:
    sin normalización el cuerpo conservaría esa forma, y buscar solo la compuesta
    pasaría sin probar nada.
    """
    f = frontera()
    candidato = candidato_declarado(
        sesion, northstar, nombre=NOMBRE_CON_TILDE, texto=CV_CON_LA_TILDE_DESCOMPUESTA
    )
    descompuesto = unicodedata.normalize("NFD", NOMBRE_CON_TILDE)
    assert descompuesto != NOMBRE_CON_TILDE, (
        "el nombre de prueba no tiene ninguna tilde que separar"
    )
    assert descompuesto in (candidato.cv_texto or ""), (
        "el CV declarado no trae la tilde descompuesta: el test pasaría sin probar nada"
    )

    payload = f.pseudonimizar(candidato)

    assert descompuesto not in payload.cv, (
        "el cuerpo enviado lleva el nombre del candidato con la tilde descompuesta "
        "(CA2, §1a · nombre): el texto no se normalizó antes de limpiarlo"
    )
    assert NOMBRE_CON_TILDE not in payload.cv, "el cuerpo enviado lleva el nombre del candidato"
    assert "admisiones hospitalarias" in payload.cv, "se fue la frase, no el dato (F1)"


# --- 18 · la tercera pata de la frontera (regresión: nace en verde) -------


def test_una_segunda_fabrica_de_payloads_es_una_frontera_violada_al_importar() -> None:
    """La tercera pata de la frontera, que ningún test ejercitaba (M1).

    `payload.py` dice que contra el escenario de §5.4 hacen falta tres cosas y
    que ninguna sirve sola: el tipo, el rechazo en ejecución y el **constructor
    privado**, que se cierra con «una sola fábrica registrada». Las dos primeras
    las prueba el test 2 (el `ContextVar` y el `__post_init__`); la tercera era
    hasta hoy una afirmación del docstring: cambiar la guardia por un `if False:`
    deja la suite entera verde, y entonces el segundo prompt de enero se escribe
    con su propia fábrica y «pseudonimizado» vuelve a ser una declaración.

    Las dos mitades, porque el control tiene que cortar **y** dejar trabajar:
    registrar una fábrica distinta es `FronteraViolada`, y volver a decorar la
    misma función —el mismo `módulo.qualname`, que es lo que pasa al reimportar
    el módulo— no lo es.

    **Nace en verde** a propósito, como el test 17: es un control sin test, no un
    defecto.
    """
    f = frontera()

    with pytest.raises(f.violacion):
        f.unica_fabrica(lambda candidato: candidato)

    # Volver a decorar la misma función —el mismo `módulo.qualname`, que es lo que
    # ocurre al reimportar el módulo— no es una segunda puerta.
    assert callable(f.unica_fabrica(f.pseudonimizar))

    # Y el intento fallido no deja la frontera rota: la fábrica de siempre sigue
    # construyendo payloads. El candidato va sin sesión a propósito: esto no toca
    # la base de datos.
    payload = f.pseudonimizar(
        Candidato(
            nombre="Renata Solís Vega",
            correo="renata.solis@ejemplo.test",
            telefono="+1 713 555 0122",
            links=[],
            cv_texto="Soy Renata Solís Vega, enfermera de urgencias pediátricas.",
        )
    )
    assert isinstance(payload, f.tipo) and "Renata" not in payload.cv


# --- 19 · las formas nuevas por el camino real, y sin cruzar de empresa ----


async def test_las_formas_nuevas_tampoco_salen_por_el_camino_real_ni_cruzan_de_empresa(
    sesion: Session,
    northstar: EmpresaDePrueba,
    meridian: EmpresaDePrueba,
    activar_match: Callable[[str], None],
    proveedor_contado: ProveedorContado,
) -> None:
    """CA2 y CA1 · lo mismo que los tests 11 a 16, donde de verdad sale el cuerpo.

    Los tests 11 a 16 llaman al pseudonimizador a mano, y eso deja sin comprobar
    lo que §5.4 teme: que el cuerpo que **de verdad** sale sea otro. Aquí los tres
    pares se encolan, el bucle los toma y se asercia lo que el proveedor recibió.

    Y con las **dos empresas**, que es el requisito número uno del cliente (D4,
    CA1, [03:03]): un arreglo de estas fugas que reconociera los campos del
    candidato equivocado cerraría los tests 11 a 16 y seguiría mandando el nombre
    del candidato de Meridian dentro del payload de Northstar. **Meridian se
    activa a propósito**, igual que en los tests 7 y 10: lo que se mide aquí es el
    cruce de datos, no la activación por empresa (CA3, PR-10).
    """
    f = frontera()
    activar_match(meridian.slug)
    de_northstar = candidato_de(sesion, northstar, FORMAS_DE_ESCRIBIR)
    dos_letras = candidato_declarado(
        sesion, northstar, nombre=NOMBRE_DE_DOS_LETRAS, texto=CV_DEL_APELLIDO_DE_DOS_LETRAS
    )
    de_meridian = candidato_declarado(
        sesion, meridian, nombre=NOMBRE_CON_OTRA_LETRA, texto=CV_DEL_NOMBRE_CON_OTRA_LETRA
    )
    for empresa, candidato in (
        (northstar, de_northstar),
        (northstar, dos_letras),
        (meridian, de_meridian),
    ):
        encolar(sesion, empresa.vacante.id, candidato.id)

    assert await pasadas(sesion, proveedor_contado) == 3
    enviados = proveedor_contado.payloads
    assert len(enviados) == 3
    assert all(isinstance(cuerpo, f.tipo) for cuerpo in enviados)

    textos = [cuerpo.cv for cuerpo in enviados]
    nuevas = {
        **FORMAS_DE_ESCRIBIR.fugas,
        **FUGAS_DE_DOS_LETRAS,
        **FUGAS_DE_OTRA_LETRA,
    }
    for texto in textos:
        assert siguen_en(texto, nuevas) == [], (
            "salió al proveedor un dato de §1a por el camino real (CA2): "
            f"{siguen_en(texto, nuevas)}"
        )

    # Cada payload lleva **su** CV: ni mezclados, ni el de la otra empresa.
    marcas = ("urgencias pediátricas", "banco de sangre", "farmacia hospitalaria")
    for marca in marcas:
        assert sum(marca in texto for texto in textos) == 1, (
            f"la marca «{marca}» no está en exactamente un payload"
        )
    de_meridian_texto = next(t for t in textos if "farmacia hospitalaria" in t)
    assert "urgencias pediátricas" not in de_meridian_texto
    assert "banco de sangre" not in de_meridian_texto

    assert sorted(s.candidato_id for s in repo_de(sesion, northstar).scores()) == sorted(
        (de_northstar.id, dos_letras.id)
    ), "Northstar no guardó exactamente sus dos scores"
    assert [s.candidato_id for s in repo_de(sesion, meridian).scores()] == [de_meridian.id], (
        "Meridian no guardó exactamente su score"
    )
