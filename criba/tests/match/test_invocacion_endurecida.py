"""PR-09 · las tres cosas que la invocación **apaga**, y el tope que el plan pide.

Este archivo cubre el hueco que la ronda de revisión de PR-09 llama **I2**: el
test de la invocación asercia la **ausencia** de los argumentos prohibidos
(`test_cliente_proveedor.py`, `ARGUMENTOS_PROHIBIDOS`), y eso es media regla. La
otra media —que las banderas de endurecimiento **estén**— no la comprobaba nadie,
así que borrarlas dejaba la suite verde:

- sin la bandera que apaga la **persistencia de sesión**, el CLI escribe un
  archivo de sesión con el CV pseudonimizado dentro, en el directorio del
  usuario. Eso es texto de CV **fuera de Criba**: donde D15 no llega, donde el
  inventario de borrado de CA16 no lo ve y donde la retención la decide el disco
  de la máquina (F12);
- sin la bandera que deja al modelo **sin herramientas**, el CLI puede escribir
  fuera de Criba, y ninguna de las tres garantías del paso —frontera, timeout y
  regla de log— cubre lo que escriba una herramienta;
- sin **tope por llamada**, desaparece el «tope» que el objetivo de PR-09 nombra
  (`PLAN.md` PR-09: «con tope de tokens»), que es lo que acota la llamada suelta
  que se desmadra por debajo del techo mensual de D12.

**Lo que el plan dice y el paso implementó no es lo mismo, y aquí no se adivina:**
`PLAN.md` PR-09 dice «tope de **tokens**» y D12 es un techo **en dólares** de toda
la plataforma. El criterio que estos tests exigen es el que las dos lecturas
comparten: que la invocación lleve **un tope por llamada, con un número positivo
dentro y muy por debajo del techo mensual**. Cuál de las dos unidades es la que
Víctor quiere queda anotado como pregunta, no resuelta por un test.

**Por qué estos tests nombran banderas del CLI.** Las banderas son de la
herramienta, no nuestras, y una lista de nombres envejece (F34). Pero el control
de verdad —«el CV va por la entrada estándar y nada de él en `argv`»— ya está en
`test_cliente_proveedor.py` y no cubre nada de esto: que el CV no esté en `argv`
no impide que el CLI lo escriba en un archivo de sesión. Así que cada test acepta
**las formas conocidas de decir lo mismo** y falla nombrando la propiedad, no la
bandera.

Ningún test de este archivo lanza el CLI de verdad.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from app.match.configuracion import IDIOMA_POR_OMISION
from tests.dobles.cli import CLIDoblado, adaptador, payload_sintetico

# El techo **mensual** de toda la plataforma (D12, 1.500 USD). Un tope «por
# llamada» igual o mayor que esto no acota ninguna llamada: es el presupuesto
# entero del mes puesto en una.
TECHO_MENSUAL_USD = 1500

# Las formas conocidas de apagar la sesión. Solo negativas: `--session-persistence
# true` no apaga nada.
SIN_SESION = ("--no-session-persistence", "--no-session", "--no-save-session")
CON_VALOR_DE_SESION = "--session-persistence"
APAGADO = frozenset({"false", "0", "off", "no", "none", ""})

# Sin herramientas, y por las tres puertas por las que una herramienta entra: la
# bandera, los archivos de ajustes (de usuario, de proyecto, locales) y los
# servidores MCP que esos archivos declaren.
SIN_HERRAMIENTAS = ("--tools", "--no-tools")
SIN_AJUSTES = ("--setting-sources", "--no-settings")
SIN_MCP = ("--strict-mcp-config", "--no-mcp")

# Topes por llamada, en cualquiera de las dos unidades que el plan y D12 nombran.
TOPES_POR_LLAMADA = ("--max-budget-usd", "--max-cost-usd", "--max-tokens", "--max-output-tokens")


def _valor_de(argumentos: Sequence[str], bandera: str) -> str | None:
    """El valor de esa bandera, en las dos formas: `--x=v` y `--x v`."""
    for indice, argumento in enumerate(argumentos):
        if argumento == bandera:
            siguiente = argumentos[indice + 1] if indice + 1 < len(argumentos) else None
            return "" if siguiente is None or siguiente.startswith("--") else siguiente
        if argumento.startswith(f"{bandera}="):
            return argumento.split("=", 1)[1]
    return None


def _apagado(argumentos: Sequence[str], banderas: Sequence[str], con_valor: str = "") -> bool:
    """Verdadero si alguna de esas banderas apaga la propiedad.

    Se admiten las dos formas de apagar: la bandera negativa suelta
    (`--no-algo`) y la bandera con un valor vacío o falso (`--algo ""`), que es
    como el CLI de la decisión N4 deja sin herramientas y sin ajustes.
    """
    if any(bandera in argumentos for bandera in banderas):
        bandera = next(bandera for bandera in banderas if bandera in argumentos)
        if bandera.startswith("--no-"):
            return True
        return (_valor_de(argumentos, bandera) or "").strip().lower() in APAGADO
    if con_valor:
        valor = _valor_de(argumentos, con_valor)
        return valor is not None and valor.strip().lower() in APAGADO
    return any(
        argumento.startswith(f"{bandera}=")
        and argumento.split("=", 1)[1].strip().lower() in APAGADO
        for bandera in banderas
        for argumento in argumentos
    )


async def _invocacion(cli: Callable[..., CLIDoblado]) -> CLIDoblado:
    """Una llamada del adaptador real, con el doble de la costura puesto."""
    doble = cli()
    await adaptador().real().puntuar(payload_sintetico(), IDIOMA_POR_OMISION)
    assert doble.llamadas == 1, "el adaptador no lanzó exactamente una invocación"
    return doble


# --- 1 · sin sesión: el CV no se queda en un archivo del disco --------------


async def test_la_invocacion_no_deja_sesion_del_cli_en_disco_con_el_cv_dentro(
    cli: Callable[..., CLIDoblado],
) -> None:
    """N4 («sin herramientas y **sin sesión**»), F12, D15, CA16.

    La mitad de F12 que no es un log. El CV sale de Criba hacia el proveedor con
    las tres condiciones de D3 modificado cumplidas; un archivo de sesión en el
    directorio del usuario de la máquina que corre el proceso web **no cumple
    ninguna de las tres**, y además:

    - **D15** dice que el texto del CV no se guarda, y ese archivo lo guarda;
    - **CA16** exige el inventario en el repo de cada lugar donde Match guarda
      datos derivados del candidato, y `~/.claude/projects/…` no está en
      `docs/inventario-borrado.md` ni puede estarlo: no es una tabla nuestra;
    - el borrado en 7 días pasa por encima de él sin verlo.

    Es la bandera más fácil de borrar «porque no hacía falta» y la más caras de
    las tres: cuando se note, los ~680 CVs de la demo ya están en el disco.
    """
    doble = await _invocacion(cli)

    assert _apagado(doble.ultima.argumentos, SIN_SESION, CON_VALOR_DE_SESION), (
        "la invocación no apaga la persistencia de sesión del CLI "
        f"({doble.ultima.linea}): el proceso escribe un archivo de sesión con el CV "
        "pseudonimizado dentro, fuera de Criba, fuera de D15 y fuera del inventario de "
        "borrado de CA16"
    )


# --- 2 · sin herramientas, por ninguna de las tres puertas ------------------


async def test_la_invocacion_no_le_da_herramientas_al_modelo_ni_por_ajustes_ni_por_mcp(
    cli: Callable[..., CLIDoblado],
) -> None:
    """N4 · «sin herramientas», y las herramientas entran por tres puertas.

    La decisión del proveedor dice «CLI `claude -p` por subproceso, **sin
    herramientas y sin sesión**». Sin herramientas no es una bandera: es tres,
    porque el CLI las toma de tres sitios y cerrar uno deja los otros dos
    abiertos:

    1. la **bandera** de herramientas, vacía;
    2. los **archivos de ajustes** —de usuario, de proyecto y locales—, que
       declaran herramientas y permisos; en la máquina de un desarrollador existen
       y son suyos, no de Criba;
    3. los **servidores MCP** que esos archivos declaren, que son procesos de
       terceros con acceso a lo que el modelo les mande.

    Lo que está al otro lado es un CV. Una herramienta que escriba un archivo, o
    un servidor MCP que reciba el texto, saca el CV del único camino que D3
    modificado autorizó — y ninguna de las tres garantías de este paso (frontera,
    timeout, regla de log) cubre lo que haga una herramienta.

    `ARGUMENTOS_PROHIBIDOS` de `test_cliente_proveedor.py` es la otra mitad: ahí
    se comprueba que **no** se pasen `--allowedTools`, `--mcp-config` ni
    `--dangerously-skip-permissions`. No pasar los que dan permiso no es lo mismo
    que decir explícitamente que no hay ninguno.
    """
    argumentos = (await _invocacion(cli)).ultima.argumentos

    assert _apagado(argumentos, SIN_HERRAMIENTAS), (
        f"la invocación no deja al modelo sin herramientas ({' '.join(argumentos)}): lo que una "
        "herramienta escriba sale de Criba sin pasar por la frontera de CA2"
    )
    assert _apagado(argumentos, SIN_AJUSTES), (
        "la invocación no excluye los archivos de ajustes (de usuario, de proyecto y locales): "
        "los ajustes de la máquina deciden qué herramientas tiene el proceso que recibe el CV"
    )
    assert any(bandera in argumentos for bandera in SIN_MCP), (
        "la invocación no excluye los servidores MCP declarados fuera de Criba: son procesos de "
        "terceros, y lo que el modelo les mande es el CV"
    )


# --- 3 · el tope por llamada que el objetivo del paso nombra ----------------


async def test_la_invocacion_lleva_un_tope_por_llamada_con_un_numero_dentro(
    cli: Callable[..., CLIDoblado],
) -> None:
    """`PLAN.md` PR-09 («con tope de tokens») y D12 · el tope de la llamada suelta.

    El techo de D12 son 1.500 USD/mes de **toda la plataforma** y lo cuenta
    PR-13: es una barrera que se mira entre llamada y llamada. Lo que ninguna
    suma mensual para es **una** llamada que se desmadra —un CV de 200 páginas,
    un modelo que entra en bucle—, y para eso el objetivo de este paso pide un
    tope. Sin él, el «tope» del enunciado no existe en el código y nadie se
    entera hasta la factura.

    El test no elige la unidad: `PLAN.md` dice tokens, D12 habla en dólares y las
    dos lecturas comparten lo mismo —un tope **por llamada**, con un número
    positivo y muy por debajo del techo del mes—. Que un tope de 1.500 USD por
    llamada no acota nada es la mitad que hace al test valer algo: un número
    presente no es un número que limite.
    """
    argumentos = (await _invocacion(cli)).ultima.argumentos

    topes = {
        bandera: valor
        for bandera in TOPES_POR_LLAMADA
        if (valor := _valor_de(argumentos, bandera)) is not None
    }
    assert topes, (
        f"la invocación no lleva ningún tope por llamada ({' '.join(argumentos)}): el objetivo "
        "de PR-09 pide «tope de tokens» y el techo de D12 es mensual y de toda la plataforma, "
        "así que no acota la llamada suelta que se desmadra"
    )
    for bandera, crudo in topes.items():
        try:
            valor = float(crudo)
        except ValueError:
            raise AssertionError(
                f"el tope {bandera} no lleva un número dentro: {crudo!r}"
            ) from None
        assert valor > 0, f"el tope {bandera} vale {crudo!r}: un tope de cero no deja pasar nada"
        if "usd" in bandera:
            assert valor < TECHO_MENSUAL_USD, (
                f"el tope por llamada ({valor} USD) es el techo mensual entero de D12 "
                f"({TECHO_MENSUAL_USD} USD) o más: no acota ninguna llamada"
            )
