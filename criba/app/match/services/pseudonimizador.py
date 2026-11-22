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
la **auditoría de CVs sintéticos del 22-nov-2026**
(`docs/auditorias/2026-11-22-cvs-sinteticos.md`), que encontró ese nombre saliendo
entero al proveedor con los siete tests del paso en verde: sus fixtures escribían
la PII del texto libre idéntica, carácter por carácter, a la de los campos, así
que probaban la igualdad exacta y no el parecido.

**Y una foto puede llegar como nombre de archivo y no como URL** —«Foto adjunta:
sofia_ramirez_2026.png»—, que es la segunda fuga de esa auditoría y la forma
corriente en que una foto llega a un CV subido. Son dos datos de §1a en la misma
línea: la foto y, dentro del nombre de archivo, el de la candidata.

**La regla que sale de las dos y vale para todo el módulo: el dato es el dato, no
su forma de escribirlo.** §1a dice «teléfono», no «teléfono en el formato de
Texas»; dice «links a perfiles», no «links con `https://`». Así que cada clase de
dato reconoce **las formas en que un CV la escribe**, y cada una está donde se
decide:

- el **enlace**, con esquema o como dominio pelado —`linkedin.com/in/…`,
  `github.com/usuario`— (`_FORMAS_DE_ENLACE`);
- la **dirección**, en las dos sintaxis: el número delante («1200 Walnut
  Street») y el nombre de la vía delante con el número al final («Calle Hidalgo
  123»), que es la forma corriente en español (`_VIAS_EN_ESPANOL`);
- el **teléfono**, en sus dos agrupaciones de diez dígitos, 3-3-4 y 2-4-4
  (`_AGRUPACIONES_DE_TELEFONO`);
- el **nombre**, escrito con otra letra latina: sin tilde, y también con una letra
  que no se descompone —«Soren Lukasz» por «Søren Łukasz»— (`_letra_base`); y con
  un **apellido de dos letras**, `Li` o `Wu`, que no es una inicial
  (`_partes_del_nombre`).

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

Las formas nuevas traen su propio falso positivo, y se dice aquí: «en la calle 3
de abril» cae como dirección, y un dominio con ruta escrito en la narrativa
—`ejemplo.com/curso`— cae como enlace aunque no sea un perfil. Las dos erran del
lado que CA2 manda (antes de más que de menos) y se miden por el mismo sitio que
el resto, CA14.

**Lo que este módulo NO limpia, a propósito:** empleador anterior, universidad y
ciudad no declarada. Son las entidades que §1a **no** nombra, detectarlas es una
tarea con falsos negativos y no una regla, y **decide Priya** (pregunta abierta 2
de `SPEC.md`, antes del 12-dic-2026). El test 3b las espera en `xfail(strict)`.

Y tampoco un ***handle*** sin dominio —«Twitter: @sofiaramirez»—: §1a dice «links
a perfiles», y si un handle cuenta como uno es de la misma familia que esa
pregunta abierta. Se deja escrito en el cuerpo del PR como no cubierto, no como
una regla inventada aquí.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

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
)

# Los nombres de vía en español, que son los mismos en las dos sintaxis y por eso
# van aparte: en «1200 Avenida Juárez» van **detrás** del número de portal, como
# los de arriba, y en «Calle Hidalgo 123» van **delante**, con el número al final.
# Esa segunda forma es la corriente en español y era la que salía entera: la lista
# ya nombraba `Calle`, `Avenida` y `Carrera`, pero solo el patrón con el número
# delante las usaba, así que para la sintaxis que las justifica eran código muerto.
_VIAS_EN_ESPANOL = (
    "Calle",
    "Avenida",
    "Carrera",
)

# Las palabras que pueden ir entre el número de portal y el sufijo de calle (o
# entre el nombre de la vía y su número): hasta cuatro, sin cifras.
_PALABRAS_DE_LA_VIA = r"(?:[^\W\d_][\w'.\-]*\s+){0,4}"

# Las **agrupaciones** de diez dígitos que se leen como teléfono. Diez dígitos es
# lo que distingue un teléfono de un código postal o de un número de licencia, y
# por eso las dos los piden todos: lo que cambia entre países es dónde van los
# separadores, no cuántas cifras hay (§1a dice «teléfono», no «teléfono en el
# formato de Texas»).
#
# Son dos agrupaciones enumeradas y no una regla elástica —«grupos de dos a cuatro
# cifras»— a propósito: esa regla bajaría el mínimo a **ocho** dígitos y se
# llevaría cualquier número largo del CV, que es el «quitar de más» de F1. Y la de
# 2-4-4 pide los separadores **obligatorios** porque sin ellos son diez dígitos
# seguidos, que es lo que la primera ya reconoce.
_AGRUPACIONES_DE_TELEFONO = (
    r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}",  # 3-3-4, el de Estados Unidos
    r"\d{2}[\s.\-]\d{4}[\s.\-]\d{4}",  # 2-4-4, el de México
)

# Un enlace, en las dos formas en que un CV escribe un perfil: con esquema o
# `www.` —`https://www.linkedin.com/in/…`— y como **dominio pelado**,
# `linkedin.com/in/…` o `github.com/usuario`, que es la forma más corriente de
# escribirlo a mano y la que salía entera. El dominio pelado exige la ruta (`/…`)
# y que la última etiqueta antes de la ruta sean solo letras: así no se lleva
# «12.5/10» ni la parte de dominio de un correo, que no tiene ruta. El
# `(?<![\w@.])` del dominio pelado es lo que impide empezar a casar en la mitad de
# un correo o de una URL que ya cayó por la primera forma.
_FORMAS_DE_ENLACE = (
    r"(?:https?://|www\.)[^\s<>()\[\]\"'«»]+",
    r"(?<![\w@.])[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}/[^\s<>()\[\]\"'«»]*",
)

# Patrones, en el orden en que se aplican. El enlace va primero: una URL puede
# llevar dentro un correo, un teléfono o un nombre, y partirla dejaría trozos que
# ningún patrón posterior reconoce.
PATRONES: tuple[tuple[re.Pattern[str], str], ...] = (
    # Enlaces y fotos: toda URL, incluida la del `![Foto de perfil](…)`, y el
    # perfil escrito como dominio pelado (`_FORMAS_DE_ENLACE`). El lookbehind
    # final suelta la puntuación de la frase, que no es parte del link.
    (
        re.compile(r"(?:" + "|".join(_FORMAS_DE_ENLACE) + r")(?<![.,;:!?])", re.IGNORECASE),
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
    # Teléfonos: diez dígitos con prefijo de país opcional, en una de las
    # agrupaciones de `_AGRUPACIONES_DE_TELEFONO`.
    (
        re.compile(
            r"(?<![\d(])(?:\+\d{1,3}[\s.\-]?)?(?:"
            + "|".join(_AGRUPACIONES_DE_TELEFONO)
            + r")(?!\d)"
        ),
        MARCA_DE_TELEFONO,
    ),
    # Dirección en sintaxis inglesa: número de portal, hasta cuatro palabras y un
    # sufijo de calle (`1200 Walnut Street`, `1200 Avenida Juárez`).
    (
        re.compile(
            r"\b\d{1,6}\s+"
            + _PALABRAS_DE_LA_VIA
            + r"(?:"
            + "|".join((*_SUFIJOS_DE_CALLE, *_VIAS_EN_ESPANOL))
            + r")\b",
            re.IGNORECASE,
        ),
        MARCA_DE_DIRECCION,
    ),
    # Dirección en sintaxis española: el nombre de la vía delante y el número al
    # final (`Calle Hidalgo 123`, `Avenida Insurgentes Sur 1457`). La dirección es
    # dato de §1a y **no tiene segunda red**: `candidatos` no tiene columna de
    # dirección (`app/plataforma/modelos.py`), así que la pasada de valores
    # conocidos no la puede conocer y si el patrón no la reconoce, el dato sale.
    (
        re.compile(
            r"\b(?:" + "|".join(_VIAS_EN_ESPANOL) + r")\s+" + _PALABRAS_DE_LA_VIA + r"\d{1,6}\b",
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
    for valor in _valores_conocidos(candidato):
        texto, cuantas = _quitar_valor(texto, valor)
        hechas += cuantas
    return texto, hechas


@dataclass(frozen=True, slots=True)
class _ValorConocido:
    """Un valor de campo, su marca y **cómo** se reconoce en el texto libre.

    `respetar_mayusculas` existe por las partes cortas del nombre: ver
    `_partes_del_nombre`.
    """

    valor: str
    marca: str
    respetar_mayusculas: bool = False


def _valores_conocidos(candidato: Candidato) -> list[_ValorConocido]:
    """Los valores de los campos estructurados, **de más largo a más corto**.

    El orden importa para que «Valentina Arrieta Köhler» caiga como un nombre y no
    como tres. Las **partes** del nombre van aparte porque ningún campo las trae
    sueltas y el texto sí las usa así («Arrieta es mi apellido paterno»).
    """
    de_un_campo = [
        _ValorConocido(candidato.nombre, MARCA_DE_NOMBRE),
        _ValorConocido(candidato.correo, MARCA_DE_CORREO),
        _ValorConocido(candidato.telefono, MARCA_DE_TELEFONO),
        *(_ValorConocido(link, MARCA_DE_ENLACE) for link in candidato.links),
    ]
    valores = [
        _ValorConocido(valor.valor.strip(), valor.marca)
        for valor in de_un_campo
        if len(valor.valor.strip()) >= LARGO_MINIMO
    ]
    valores += _partes_del_nombre(candidato.nombre)
    return sorted(valores, key=lambda valor: len(valor.valor), reverse=True)


def _partes_del_nombre(nombre: str) -> list[_ValorConocido]:
    """Las partes del nombre completo: ningún campo las trae sueltas y el texto sí.

    Una parte **más corta que `LARGO_MINIMO`** cuenta solo si lleva mayúscula
    inicial, y entonces se reconoce **distinguiendo mayúsculas**. Es la salida a la
    tensión que `LARGO_MINIMO` tenía mal resuelta: `Li`, `Wu`, `Ng`, `Vo`, `Xu` y
    `Ho` son apellidos completos y frecuentes —y el nombre es el primero de los
    seis datos de §1a—, mientras que `de`, `la` o `do` son partículas que en
    español están por toda la narrativa («jefa **de** piso», «**la** unidad»).
    Bajarle el mínimo a todas pasaría el criterio del nombre y rompería el del
    texto puntuable (F1, CA14): distinguir mayúsculas es lo que separa el apellido
    de la partícula sin inventar una lista de partículas por idioma (F34).

    Lo que esto **no** reconoce, dicho donde se decide: un apellido corto escrito
    en minúscula o en versales en el texto libre («li atiende», «LI»).
    """
    partes: list[_ValorConocido] = []
    for parte in nombre.split():
        if len(parte) >= LARGO_MINIMO:
            partes.append(_ValorConocido(parte, MARCA_DE_NOMBRE))
        elif parte[:1].isupper():
            partes.append(_ValorConocido(parte, MARCA_DE_NOMBRE, respetar_mayusculas=True))
    return partes


def _quitar_valor(texto: str, valor: _ValorConocido) -> tuple[str, int]:
    """Sustituye un valor conocido por su marca, y dice cuántas veces."""
    return _patron_de_valor(valor).subn(valor.marca, texto)


def _patron_de_valor(valor: _ValorConocido) -> re.Pattern[str]:
    """**Cómo se reconoce** un valor de campo dentro del texto libre.

    Está en una función sola porque es la decisión que la pasada de valores
    conocidos toma, y toda ella: el resto de `_quitar_valor` es un `subn`.

    Los bordes se piden con `(?<!\\w)` y `(?!\\w)` y no con `\\b`, porque hay
    valores que empiezan por un carácter que no es de palabra —`+1 713 …`— y ahí
    `\\b` no casa nunca.

    Y **los acentos no cuentan**, igual que las mayúsculas: «Jose Angel Trevino»
    es el mismo nombre que «José Ángel Treviño», y quien lea el cuerpo al otro
    lado identifica a la misma persona (primera fuga de la auditoría del
    22-nov-2026, `docs/auditorias/2026-11-22-cvs-sinteticos.md`). No es una regla
    nueva: §1a dice «nombre», no «el nombre tal como está escrito en la base de
    datos».

    Las mayúsculas sí cuentan cuando el valor lo pide (`respetar_mayusculas`), que
    es el caso de las partes cortas del nombre.
    """
    patron = _tolerante_a_acentos(valor.valor, respetar_mayusculas=valor.respetar_mayusculas)
    banderas = re.NOFLAG if valor.respetar_mayusculas else re.IGNORECASE
    return re.compile(rf"(?<!\w){patron}(?!\w)", banderas)


def _tolerante_a_acentos(valor: str, *, respetar_mayusculas: bool = False) -> str:
    """El valor como patrón, con cada letra abierta a sus variantes acentuadas.

    `José` sale como `[jĵ][eèéê…][sśş…][eèéê…]`: así casa escrito con tildes y sin
    ellas, en los dos sentidos —el campo acentuado contra el texto sin acentos, y
    al revés—, que es el caso corriente (teclado sin configurar, PDF mal extraído,
    una nómina que no admite tildes).

    Con `respetar_mayusculas`, cada familia se escribe en la caja de la letra del
    valor —`Li` sale como `[LĹĻĽ…][iìíî…]`—, porque el patrón se compila sin
    `IGNORECASE` y una familia en minúscula no casaría con la mayúscula del
    apellido.

    Lo que **no** hace es normalizar el texto que sale: el cuerpo enviado conserva
    sus acentos. Aquí solo se abre lo que se **reconoce**.
    """
    piezas: list[str] = []
    for caracter in unicodedata.normalize("NFC", valor):
        base = _letra_base(caracter)
        familia = _FAMILIAS_DE_LETRA.get(base) if base else None
        if familia and respetar_mayusculas and caracter.isupper():
            familia = familia.upper()
        piezas.append(f"[{re.escape(familia)}]" if familia else re.escape(caracter))
    return "".join(piezas)


def _sin_diacriticos(texto: str) -> str:
    """El texto sin marcas de acento, por descomposición canónica (NFD)."""
    return "".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c))


# El nombre Unicode de una letra latina **adornada**: «LATIN SMALL LETTER O WITH
# STROKE», «LATIN CAPITAL LETTER L WITH STROKE». Es el segundo camino de
# `_letra_base`, para las letras que NFD no descompone.
_LETRA_CON_ADORNO = re.compile(r"LATIN (?:SMALL|CAPITAL) LETTER ([A-Z]) WITH ")


def _letra_base(caracter: str) -> str | None:
    """**Qué letra ASCII hay debajo** de este carácter, o `None` si no hay una sola.

    Dos caminos, y el segundo es el que la descomposición no cubre:

    1. **la marca de acento se quita** (NFD): `é` → `e`, `ğ` → `g`, `ů` → `u`;
    2. la letra **no se descompone** porque su adorno no es una marca aparte sino
       parte del glifo —`ø`, `ł`, `đ`, `ħ`—, y ahí lo dice su **nombre Unicode**:
       «LATIN SMALL LETTER O WITH STROKE». Se lee de ahí y no de una lista escrita
       a mano, por la misma razón que la tabla de familias (F34): el día del primer
       apellido con `ŧ` ya está cubierto.

    `None` es la respuesta honesta para la eszett (`ß`), la ligadura `æ` y la i sin
    punto del turco (U+0131): ninguna es «una letra con algo encima» —su nombre
    Unicode no dice `… WITH …`—, así que ahí no hay «la misma letra» y este módulo
    no la inventa.
    """
    sin_diacriticos = _sin_diacriticos(caracter)
    if len(sin_diacriticos) == 1 and sin_diacriticos.isascii() and sin_diacriticos.isalpha():
        return sin_diacriticos.lower()
    con_adorno = _LETRA_CON_ADORNO.match(unicodedata.name(caracter, ""))
    return con_adorno.group(1).lower() if con_adorno else None


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
