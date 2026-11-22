"""La frontera de pseudonimización.

Nombre, correo, teléfono, dirección, links y fotos: los seis datos de §1a
(PR-08, CA2).

Es la **única fábrica** de `PayloadPseudonimizado` (`proveedor/payload.py`): el
cuerpo que sale de Criba se construye aquí y en ningún otro sitio.

**Dos pasadas, y las dos hacen falta** (R1·B3, el test 3 y el test 4 de
`tests/match/test_pseudonimizacion.py`):

1. **valores conocidos** — todo lo que está en los campos estructurados del
   candidato (`nombre` y sus partes, `correo`, `telefono`, `links`) se quita
   **también del texto libre**. No amplía CA2: CA2 dice «el cuerpo enviado no
   contiene ninguno de esos seis datos» y no distingue campo de narrativa. Y es
   el caso corriente: prácticamente todo CV repite el nombre en la primera línea;
2. **patrones** — correo, teléfono, URL y dirección caen aunque **no** estén en
   ningún campo. Hacen falta porque hay datos de §1a que el esquema no guarda en
   ninguna columna —la **dirección** y la **foto** no tienen campo en
   `candidatos` (`app/plataforma/modelos.py`)— y porque la sección de referencias
   trae el correo y el teléfono de otra persona.

El orden es **patrones primero y valores conocidos después**, y no es un detalle
de estilo: al revés, quitar «Valentina» del *slug* de su URL de LinkedIn rompería
la URL en trozos que ya ningún patrón reconoce, y el resto saldría de Criba.

**Se quita el dato, no la frase.** Cada dato se sustituye por una marca
(`[nombre]`, `[correo]`, …) en vez de borrarse: el texto que rodea al dato es el
que decide el score (F1, §4 de `llamadas/2026-11-21-cambios-decisiones.md`), y un
pseudonimizador que se lleve el párrafo pasa CA2 y rompe CA14. La marca dice al
modelo que ahí había algo, y no es un dato de nadie.

**Lo que esto cuesta, dicho en el sitio donde se paga.** Limpiar por patrón puede
**quitar de más** —un número de licencia escrito como un teléfono, un «1200 Main
Street» que fuera el nombre de un empleador—. No se arregla con una regla más
fina: se **mide**, y lo mide CA14 sobre el conjunto dorado (PR-17). Por eso el
payload lleva el contador de `sustituciones` y por eso el cuerpo del PR trae el
número por CV de fixture. Donde la regla fina no estaba decidida, este módulo
**no la inventa**: el código postal solo cae acompañado de su estado, porque un
número de cinco cifras suelto es indistinguible de un número de licencia.

**Lo que este módulo NO limpia, a propósito:** empleador anterior, universidad y
ciudad no declarada. Son las entidades que §1a **no** nombra, detectarlas es una
tarea con falsos negativos y no una regla, y **decide Priya** (pregunta abierta 2
de `SPEC.md`, antes del 12-dic-2026). El test 3b las espera en `xfail(strict)`.
"""

from __future__ import annotations

import re

from app.match.proveedor.payload import PayloadPseudonimizado, unica_fabrica
from app.plataforma.modelos import Candidato

# Las marcas. Son parte de lo que el proveedor ve, así que se leen: dicen qué
# clase de dato había sin decir cuál era.
MARCA_DE_NOMBRE = "[nombre]"
MARCA_DE_CORREO = "[correo]"
MARCA_DE_TELEFONO = "[telefono]"
MARCA_DE_DIRECCION = "[direccion]"
MARCA_DE_ENLACE = "[enlace]"

# Un valor de campo más corto que esto no se usa como patrón: «de», «la» o una
# inicial suelta se comerían media narrativa (F1).
LARGO_MINIMO = 3

# Los sufijos de calle. Lista corta y deliberada: `Dr`, `St.` como abreviatura de
# santo o `Way` dentro de una frase son los falsos positivos conocidos, así que
# solo entran los que vienen detrás de un número de portal.
_SUFIJOS_DE_CALLE = (
    "Street",
    "St",
    "Avenue",
    "Ave",
    "Road",
    "Rd",
    "Lane",
    "Ln",
    "Drive",
    "Boulevard",
    "Blvd",
    "Highway",
    "Hwy",
    "Parkway",
    "Pkwy",
    "Calle",
    "Avenida",
    "Carrera",
)

# Patrones, en el orden en que se aplican. El enlace va primero: una URL puede
# llevar dentro un correo, un teléfono o un nombre, y partirla dejaría trozos que
# ningún patrón posterior reconoce.
PATRONES: tuple[tuple[re.Pattern[str], str], ...] = (
    # Enlaces y fotos: toda URL, incluida la del `![Foto de perfil](…)`. El
    # lookbehind suelta la puntuación final de la frase, que no es parte del link.
    (
        re.compile(r"(?:https?://|www\.)[^\s<>()\[\]\"'«»]+(?<![.,;:!?])", re.IGNORECASE),
        MARCA_DE_ENLACE,
    ),
    # Correos, estén en un campo o en la narrativa (el de la referencia no lo está).
    (re.compile(r"[\w.+%-]+@[\w-]+(?:\.[\w-]+)+"), MARCA_DE_CORREO),
    # Teléfonos: diez dígitos con prefijo opcional, separados por espacio, punto,
    # guion o paréntesis. Diez dígitos es lo que lo distingue de un código postal
    # o de un número de licencia.
    (
        re.compile(r"(?<![\d(])(?:\+\d{1,3}[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}(?!\d)"),
        MARCA_DE_TELEFONO,
    ),
    # Dirección: número de portal, hasta cuatro palabras y un sufijo de calle.
    (
        re.compile(
            r"\b\d{1,6}\s+(?:[^\W\d_][\w'.\-]*\s+){0,4}(?:" + "|".join(_SUFIJOS_DE_CALLE) + r")\b",
            re.IGNORECASE,
        ),
        MARCA_DE_DIRECCION,
    ),
    # Código postal **con su estado**: `TX 77002`. Un número de cinco cifras
    # suelto no se toca, y eso está dicho en el docstring: es la regla fina que el
    # plan declinó escribir y que CA14 tendrá que medir.
    (re.compile(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b"), MARCA_DE_DIRECCION),
)


@unica_fabrica
def pseudonimizar(candidato: Candidato) -> PayloadPseudonimizado:
    """El cuerpo que sale de Criba, sin ninguno de los seis datos de §1a.

    Recibe el **candidato** y no solo su texto porque la mitad del trabajo sale de
    sus campos: lo que está en `nombre`, `correo`, `telefono` o `links` se quita
    también del texto libre (R1·B3).
    """
    texto = candidato.cv_texto or ""
    sustituciones = 0
    for patron, marca in PATRONES:
        texto, hechas = patron.subn(marca, texto)
        sustituciones += hechas
    for valor, marca in _valores_conocidos(candidato):
        texto, hechas = _quitar_valor(texto, valor, marca)
        sustituciones += hechas
    return PayloadPseudonimizado(cv=texto, sustituciones=sustituciones)


def _valores_conocidos(candidato: Candidato) -> list[tuple[str, str]]:
    """Los valores de los campos estructurados, **de más largo a más corto**.

    El orden importa para que «Valentina Arrieta Köhler» caiga como un nombre y no
    como tres. Las **partes** del nombre van aparte porque ningún campo las trae
    sueltas y el texto sí las usa así («Arrieta es mi apellido paterno»).
    """
    valores = [
        (candidato.nombre, MARCA_DE_NOMBRE),
        *((parte, MARCA_DE_NOMBRE) for parte in candidato.nombre.split()),
        (candidato.correo, MARCA_DE_CORREO),
        (candidato.telefono, MARCA_DE_TELEFONO),
        *((link, MARCA_DE_ENLACE) for link in candidato.links),
    ]
    con_valor = [(v.strip(), m) for v, m in valores if len(v.strip()) >= LARGO_MINIMO]
    return sorted(con_valor, key=lambda par: len(par[0]), reverse=True)


def _quitar_valor(texto: str, valor: str, marca: str) -> tuple[str, int]:
    """Sustituye un valor conocido, sin cortar palabras y sin importar mayúsculas.

    Los bordes se piden con `(?<!\\w)` y `(?!\\w)` y no con `\\b`, porque hay
    valores que empiezan por un carácter que no es de palabra —`+1 713 …`— y ahí
    `\\b` no casa nunca.
    """
    patron = re.compile(rf"(?<!\w){re.escape(valor)}(?!\w)", re.IGNORECASE)
    return patron.subn(marca, texto)
