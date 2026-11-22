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
2. **patrones** — correo, teléfono, URL, dirección y nombre de archivo de foto
   caen aunque **no** estén en ningún campo. Hacen falta porque hay datos de §1a
   que el esquema no guarda en ninguna columna —la **dirección** y la **foto** no
   tienen campo en `candidatos` (`app/plataforma/modelos.py`)— y porque la
   sección de referencias trae el correo y el teléfono de otra persona.

**Un valor conocido se reconoce sin acentos y sin mayúsculas**, en
`_tolerante_a_acentos`: «Jose Angel Trevino» es el mismo nombre que «José Ángel
Treviño». §1a dice «nombre», no «el nombre tal como está escrito en la base de
datos», y el candidato que firma su CV sin tildes es el caso corriente. Lo dice
la **auditoría de CVs sintéticos del 22-nov-2026**, que encontró ese nombre
saliendo entero al proveedor con los siete tests del paso en verde: sus fixtures
escribían la PII del texto libre idéntica, carácter por carácter, a la de los
campos, así que probaban la igualdad exacta y no el parecido.

**Y una foto puede llegar como nombre de archivo y no como URL** —«Foto adjunta:
sofia_ramirez_2026.png»—, que es la segunda fuga de esa auditoría y la forma
corriente en que una foto llega a un CV subido. Son dos datos de §1a en la misma
línea: la foto y, dentro del nombre de archivo, el de la candidata.

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
import unicodedata

from app.match.proveedor.payload import PayloadPseudonimizado, unica_fabrica
from app.plataforma.modelos import Candidato

# Las marcas. Son parte de lo que el proveedor ve, así que se leen: dicen qué
# clase de dato había sin decir cuál era.
MARCA_DE_NOMBRE = "[nombre]"
MARCA_DE_CORREO = "[correo]"
MARCA_DE_TELEFONO = "[telefono]"
MARCA_DE_DIRECCION = "[direccion]"
MARCA_DE_ENLACE = "[enlace]"
MARCA_DE_FOTO = "[foto]"

# Un valor de campo más corto que esto no se usa como patrón: «de», «la» o una
# inicial suelta se comerían media narrativa (F1).
LARGO_MINIMO = 3

# Las extensiones que hacen de un nombre de archivo una **foto**, que es uno de
# los seis datos de §1a. Lista corta y deliberada, por la misma razón que la de
# los sufijos de calle: solo formatos de imagen, nunca el `.pdf` del título ni el
# `.docx` de la carta, que no son datos de nadie.
_EXTENSIONES_DE_FOTO = (
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "heic",
    "heif",
    "bmp",
    "tif",
    "tiff",
)

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
    # La foto **adjunta**, que no es una URL: `[Foto adjunta: sofia_ramirez_2026.png]`.
    # Es la segunda fuga de la auditoría del 22-nov-2026 y es la forma corriente en
    # que una foto llega a un CV subido. Cae el nombre de archivo **entero** y no
    # solo la parte que es un nombre: el nombre de archivo de una foto de carné
    # identifica a quien la subió aunque lleve dentro un apodo o un número de
    # expediente, y partirlo dejaría trozos que ya ningún patrón reconoce.
    # Va **después** del enlace a propósito: una URL que acaba en `.jpg` tiene que
    # caer entera como enlace, no por su último segmento.
    (
        re.compile(
            r"[\w.\-]+\.(?:" + "|".join(_EXTENSIONES_DE_FOTO) + r")(?!\w)",
            re.IGNORECASE,
        ),
        MARCA_DE_FOTO,
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

    El texto entra **normalizado a NFC**, que es la otra mitad de «los acentos no
    cuentan» (`_tolerante_a_acentos`): un CV extraído de un PDF puede traer la
    tilde en un punto de código aparte —la letra `e` y la tilde suelta, U+0301— y
    entonces el «José» del campo no casaría con el «José» del texto. NFC es una
    equivalencia canónica: no cambia el texto que el proveedor lee, solo cómo está
    escrito por dentro.
    """
    texto = unicodedata.normalize("NFC", candidato.cv_texto or "")
    texto, por_patron = _pasada_de_patrones(texto)
    texto, por_valor_conocido = _pasada_de_valores_conocidos(texto, candidato)
    return PayloadPseudonimizado(cv=texto, sustituciones=por_patron + por_valor_conocido)


def _pasada_de_patrones(texto: str) -> tuple[str, int]:
    """La pasada 1: lo que cae **aunque no esté en ningún campo** del candidato.

    Es una función y no un bucle dentro de `pseudonimizar` porque las dos pasadas
    son las dos mitades de R1·B3 y cada una tiene su propia razón de existir: esta
    es la que cubre los datos de §1a que el esquema no guarda en ninguna columna.
    """
    hechas = 0
    for patron, marca in PATRONES:
        texto, cuantas = patron.subn(marca, texto)
        hechas += cuantas
    return texto, hechas


def _pasada_de_valores_conocidos(texto: str, candidato: Candidato) -> tuple[str, int]:
    """La pasada 2: lo que está en los campos del candidato, fuera del texto libre."""
    hechas = 0
    for valor, marca in _valores_conocidos(candidato):
        texto, cuantas = _quitar_valor(texto, valor, marca)
        hechas += cuantas
    return texto, hechas


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
    """Sustituye un valor conocido por su marca, y dice cuántas veces."""
    return _patron_de_valor(valor).subn(marca, texto)


def _patron_de_valor(valor: str) -> re.Pattern[str]:
    """**Cómo se reconoce** un valor de campo dentro del texto libre.

    Está en una función sola porque es la decisión que la pasada de valores
    conocidos toma, y toda ella: el resto de `_quitar_valor` es un `subn`.

    Los bordes se piden con `(?<!\\w)` y `(?!\\w)` y no con `\\b`, porque hay
    valores que empiezan por un carácter que no es de palabra —`+1 713 …`— y ahí
    `\\b` no casa nunca.

    Y **los acentos no cuentan**, igual que las mayúsculas: «Jose Angel Trevino»
    es el mismo nombre que «José Ángel Treviño», y quien lea el cuerpo al otro
    lado identifica a la misma persona (primera fuga de la auditoría del
    22-nov-2026). No es una regla nueva: §1a dice «nombre», no «el nombre tal
    como está escrito en la base de datos».
    """
    return re.compile(rf"(?<!\w){_tolerante_a_acentos(valor)}(?!\w)", re.IGNORECASE)


def _tolerante_a_acentos(valor: str) -> str:
    """El valor como patrón, con cada letra abierta a sus variantes acentuadas.

    `José` sale como `[jĵ][eèéê…][sśş…][eèéê…]`: así casa escrito con tildes y sin
    ellas, en los dos sentidos —el campo acentuado contra el texto sin acentos, y
    al revés—, que es el caso corriente (teclado sin configurar, PDF mal extraído,
    una nómina que no admite tildes).

    Lo que **no** hace es normalizar el texto que sale: el cuerpo enviado conserva
    sus acentos. Aquí solo se abre lo que se **reconoce**.
    """
    piezas: list[str] = []
    for caracter in unicodedata.normalize("NFC", valor):
        base = _letra_base(caracter)
        familia = _FAMILIAS_DE_LETRA.get(base) if base else None
        piezas.append(f"[{re.escape(familia)}]" if familia else re.escape(caracter))
    return "".join(piezas)


def _sin_diacriticos(texto: str) -> str:
    """El texto sin marcas de acento, por descomposición canónica (NFD)."""
    return "".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c))


def _letra_base(caracter: str) -> str | None:
    """**Qué letra ASCII hay debajo** de este carácter, o `None` si no hay una sola.

    Está en una función sola porque es la pregunta que tanto la tabla de familias
    como `_tolerante_a_acentos` tienen que contestar, y la contestaban por
    separado: así hay un único sitio donde ensancharla el día que aparezca una
    letra que esta no reconozca.

    `None` es la respuesta honesta para la eszett, la ligadura `æ` o la i sin
    punto del turco: ahí no hay «la misma letra sin tilde» y este módulo no la
    inventa.
    """
    sin_diacriticos = _sin_diacriticos(caracter)
    if len(sin_diacriticos) == 1 and sin_diacriticos.isascii() and sin_diacriticos.isalpha():
        return sin_diacriticos.lower()
    return None


def _familias_de_letra() -> dict[str, str]:
    """Por cada letra ASCII, **todas** las letras latinas que son esa misma letra.

    Se calcula una vez, al importar, recorriendo el bloque latino de Unicode y
    preguntándole a `_letra_base` cuál es la letra de debajo: una tabla escrita a
    mano se quedaría corta el día del primer apellido con `ğ` o con `ů` (F34).
    Fuera quedan las letras para las que `_letra_base` no sabe contestar.
    """
    familias: dict[str, set[str]] = {}
    for punto in range(0x00C0, 0x0250):  # Latin-1 Supplement, Latin Extended-A y B
        caracter = chr(punto)
        base = _letra_base(caracter)
        minuscula = caracter.lower()
        if base and len(minuscula) == 1:
            familias.setdefault(base, set()).add(minuscula)
    return {base: "".join(sorted(variantes | {base})) for base, variantes in familias.items()}


# Al importar y no por llamada: son ~380 puntos de código y el bucle de PR-14
# pseudonimiza un CV por trabajo.
_FAMILIAS_DE_LETRA = _familias_de_letra()
