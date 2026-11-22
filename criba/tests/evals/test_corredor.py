"""El arnés de evals · el corredor: el camino de producción y el gemelo del invariante.

Lo que fija este archivo es lo que la revisión del paso echó en falta (**hallazgo
I1**): `evals/corredor.py` es el módulo del que depende por completo la dimensión
**invariante** —la que da sentido al arnés en fs-26, fs-28 y fs-29— y hoy no hay
ningún test que falle si se rompe. `poe evals` con el MOCK no sirve de red: todos
los scores son 70, así que el invariante sale verde siempre y un emparejamiento
equivocado del gemelo no se ve.

Los ocho criterios que se fijan aquí, uno por test:

1. el arnés **sale por la única puerta** del proveedor, con el CV que la frontera de
   CA2 dejó salir y con la descripción de la vacante (`pseudonimizar` →
   `proveedor_configurado` → `correr_cli`);
2. el gemelo del invariante se empareja **por número de intento**;
3. pedir un caso con invariante **trae también a su gemelo**;
4. si el gemelo falló en ese intento, el caso **no pasa** y el motivo lo nombra;
5. un `ErrorDelProveedor` se recoge **por intento** y no tumba la pasada;
6. el **costo** es el que el proveedor reporta en cada llamada, y con el MOCK es cero;
7. el observador del costo **no altera la única puerta** ni se queda con cuerpos;
8. la **traza** dice el score y nunca las razones ni el CV (F12, D15).

Todos con el CLI doblado en su costura (`tests/evals/doble_del_camino.py`): ningún
test de aquí lanza un proceso, abre red ni toca la base de datos.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator

import pytest

from app.match.proveedor import cliente
from app.match.proveedor.cliente import MODELO
from app.match.proveedor.mock import SCORE_DEL_MOCK, VERSION_DEL_MOCK
from evals.calificacion import BANDA_DE_ERROR
from evals.casos import casos
from evals.corredor import casos_a_correr, correr, costo_observado
from tests.dobles.cli import NOMBRE_DE_LA_COSTURA, frases_de, normalizar
from tests.evals.conftest import CASOS_ESPERADOS, caso
from tests.evals.doble_del_camino import (
    COSTO_POR_LLAMADA,
    RAZONES_DE_FS01,
    RAZONES_DE_QA,
    PonerGuion,
    camino_doblado,
    respuesta_del_cli,
)

# El correo que el CV de fs-04 lleva en texto libre. No es de nadie
# (`example.com`), y es justo lo que la frontera de CA2 tiene que haber quitado
# antes de que el pedido salga de Criba.
CORREO_DE_FS04 = "tomas.aranda@example.com"


@pytest.fixture
def camino(monkeypatch: pytest.MonkeyPatch) -> Iterator[PonerGuion]:
    """El arnés con la única puerta del proveedor doblada (`camino_doblado`)."""
    with camino_doblado(monkeypatch) as poner:
        yield poner


async def test_el_arnes_puntua_por_la_unica_puerta_y_con_el_cv_pseudonimizado(
    camino: PonerGuion,
) -> None:
    """Criterio 1 · el arnés no tiene una segunda forma de puntuar.

    La llamada sale por `correr_cli` —la única puerta por la que puede salir un CV
    (F12, PR-09)—, el cuerpo que viaja es el que `pseudonimizar` dejó salir (el
    correo de fs-04 no está, y el contador de sustituciones lo dice) y la
    descripción de la vacante va dentro, que es el tercer dato del pedido. Si
    mañana el corredor construyera su propio payload o su propio cliente, el
    informe mediría un camino que nadie recorre."""
    doble = camino({"fs-04": [respuesta_del_cli(55, "Considera: python", "Considera: sql")]})

    pasada = await correr(modo="claude", k=1, ids=["fs-04"], traza=False)

    assert doble.llamadas == 1, "el arnés no pasó por la única puerta del proveedor"
    entrada = doble.entradas[0]
    assert CORREO_DE_FS04 not in entrada, "el correo del CV salió de Criba (CA2, §1a)"
    assert caso("fs-04")["vacante"] in entrada, "la descripción de la vacante no viajó"
    assert pasada.intentos[0].sustituciones >= 1, (
        "el payload no trae ninguna sustitución: el arnés no pasó por la frontera de CA2"
    )
    assert pasada.total.modelos == (MODELO,), "la versión de modelo es la que el CLI reporta"


async def test_el_gemelo_del_invariante_se_empareja_por_numero_de_intento(
    camino: PonerGuion,
) -> None:
    """Criterio 2 · las dos respuestas que se comparan son de la **misma** pasada.

    fs-26 es el CV de fs-25 con la edad, el estado civil, los hijos, la
    nacionalidad y la foto añadidos, y el invariante pregunta «¿ese dato movió el
    score?». Para que la diferencia sea atribuible al dato y no a la varianza entre
    llamadas, el gemelo tiene que ser el del **mismo intento**.

    El guion lo separa a propósito: en el intento 1 los dos dan 85 (diferencia 0,
    pasa) y en el intento 2 fs-26 da 85 y fs-25 da 70 (diferencia 15, se rompe).
    Un emparejamiento contra el intento 1 —o contra un promedio— daría los dos
    intentos verdes y el informe diría que fs-26 cumple el invariante cuando no lo
    cumple. Las dos bandas son «alto» en los cuatro casos, así que lo único que
    puede mover el resultado es el invariante."""
    doble = camino(
        {
            "fs-26": [respuesta_del_cli(85, *RAZONES_DE_QA), respuesta_del_cli(85, *RAZONES_DE_QA)],
            "fs-25": [respuesta_del_cli(85, *RAZONES_DE_QA), respuesta_del_cli(70, *RAZONES_DE_QA)],
        }
    )

    pasada = await correr(modo="claude", k=2, ids=["fs-26"], traza=False)

    assert doble.llamadas == 4, "dos casos por dos intentos son cuatro llamadas"
    por_id = {uno.caso_id: uno for uno in pasada.resultados}
    primero, segundo = por_id["fs-26"].calificaciones
    assert primero.invariante_ok is True, "85 contra 85 en el intento 1"
    assert segundo.invariante_ok is False, (
        "85 contra 70 en el intento 2: el gemelo se emparejó con otro intento"
    )
    assert por_id["fs-26"].aciertos == 1
    assert por_id["fs-25"].aciertos == 2, "el gemelo se califica solo, y 70 y 85 son «alto»"
    motivos = " ".join(por_id["fs-26"].motivos)
    assert "fs-25" in motivos and "15" in motivos, motivos


def test_pedir_un_caso_con_invariante_trae_tambien_a_su_gemelo() -> None:
    """Criterio 3 · `--casos fs-26` no se puede calificar sin fs-25.

    Sin el gemelo en la pasada, la dimensión del invariante no tiene contra qué
    comparar: el corredor levanta un `ValueError` o —peor— la daría por buena. Y el
    gemelo no se duplica si ya se pidió, porque entonces se puntuaría dos veces una
    llamada que se paga."""
    assert {uno["id"] for uno in casos_a_correr(["fs-26"])} == {"fs-26", "fs-25"}
    assert {uno["id"] for uno in casos_a_correr(["fs-29"])} == {"fs-29", "fs-03"}

    los_dos = casos_a_correr(["fs-26", "fs-25"])
    assert len(los_dos) == 2, "el gemelo ya pedido no se corre dos veces"

    assert len(casos_a_correr([])) == CASOS_ESPERADOS == len(casos())


async def test_un_caso_cuyo_gemelo_fallo_en_ese_intento_no_pasa_y_el_motivo_lo_nombra(
    camino: PonerGuion,
) -> None:
    """Criterio 4 · un invariante que no se pudo comprobar no es un verde.

    fs-26 responde perfectamente y su gemelo no llega a responder: el caso **no
    pasa**, su banda es `error_del_camino` y el motivo nombra a fs-25. Darlo por
    bueno sería reportar como cumplido el control que no se ejecutó, que es la
    peor de las dos salidas: fs-26 es uno de los casos que el archivo marca
    críticos."""
    camino(
        {
            "fs-26": [respuesta_del_cli(85, *RAZONES_DE_QA)],
            "fs-25": [subprocess.TimeoutExpired(cmd="claude", timeout=120)],
        }
    )

    pasada = await correr(modo="claude", k=1, ids=["fs-26"], traza=False)

    por_id = {uno.caso_id: uno for uno in pasada.resultados}
    calificacion = por_id["fs-26"].calificaciones[0]
    assert calificacion.paso is False
    assert calificacion.banda == BANDA_DE_ERROR
    assert "fs-25" in " ".join(calificacion.motivos), calificacion.motivos
    assert por_id["fs-26"].pass_k is False


async def test_un_error_del_proveedor_en_un_intento_no_tumba_el_resto_de_la_pasada(
    camino: PonerGuion,
) -> None:
    """Criterio 5 · el fallo se recoge por intento, como el ejecutor por trabajo.

    Con el proveedor real son llamadas que se pagan: un timeout en el intento 1 no
    puede tirar a la basura lo que ya se compró. El intento sin respuesta queda
    contado como fallo del **camino** —`errores`, que es lo que mira el código de
    salida— y el otro se califica igual."""
    doble = camino(
        {
            "fs-01": [
                subprocess.TimeoutExpired(cmd="claude", timeout=120),
                respuesta_del_cli(85, *RAZONES_DE_FS01),
            ]
        }
    )

    pasada = await correr(modo="claude", k=2, ids=["fs-01"], traza=False)

    assert doble.llamadas == 2
    assert len(pasada.intentos) == 2
    assert len(pasada.errores) == 1
    assert "TiempoDeEsperaDelProveedor" in str(pasada.errores[0].error)
    resultado = pasada.resultados[0]
    assert (resultado.k, resultado.aciertos) == (2, 1)
    assert resultado.pass_k is False
    assert resultado.calificaciones[0].banda == BANDA_DE_ERROR
    assert resultado.calificaciones[1].paso is True


async def test_el_costo_de_la_pasada_es_el_que_el_proveedor_reporta_y_con_el_mock_es_cero(
    camino: PonerGuion,
) -> None:
    """Criterio 6 · el costo sale del sobre del CLI, una vez por llamada.

    El encargo pide el costo de la pasada y el adaptador de producción descarta el
    `total_cost_usd` del sobre, porque contar el gasto es de PR-13. El arnés lo lee
    de paso en la única puerta: dos llamadas son dos veces el costo de una, no una
    ni tres. Con el MOCK no se envuelve nada —no sale del proceso— y el costo es
    exactamente cero."""
    camino({"fs-01": [respuesta_del_cli(85, *RAZONES_DE_FS01)] * 2})

    pagada = await correr(modo="claude", k=2, ids=["fs-01"], traza=False)
    assert pagada.total.costo_usd == pytest.approx(2 * COSTO_POR_LLAMADA)

    gratis = await correr(modo="mock", k=2, ids=["fs-01"], traza=False)
    assert gratis.total.costo_usd == 0.0
    assert gratis.total.modelos == (VERSION_DEL_MOCK,)
    assert gratis.intentos[0].respuesta is not None
    assert gratis.intentos[0].respuesta.score == SCORE_DEL_MOCK


def test_el_observador_del_costo_no_altera_la_unica_puerta_ni_se_queda_con_cuerpos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Criterio 7 · es un observador, no un doble.

    Envolver la costura del proveedor desde fuera de `app/` es la única licencia
    que el arnés se toma, y tiene tres condiciones que nada comprobaba (hallazgo
    M2): la salida del CLI se devuelve **tal cual** —si el envoltorio la recortara,
    `interpretar` vería otra respuesta que la de producción—, lo único que se
    guarda es el **número** del costo (nunca el sobre, que lleva el `result` con
    las razones dentro: F12, D15) y la puerta se restaura al salir **aunque la
    llamada falle**. Cuando PR-13 exponga el costo por llamada, esta función se
    borra entera y este test con ella."""
    salida = respuesta_del_cli(85, *RAZONES_DE_FS01)
    recibidas: list[str] = []

    def correr_falso(argumentos: tuple[str, ...], entrada: str, timeout: float) -> str:
        recibidas.append(entrada)
        return salida

    monkeypatch.setattr(cliente, NOMBRE_DE_LA_COSTURA, correr_falso)

    with costo_observado(True) as gastos:
        assert cliente.correr_cli is not correr_falso, "el observador no envolvió la puerta"
        assert cliente.correr_cli(("claude",), "<cv>\nsintetico\n</cv>", 1.0) == salida
    assert cliente.correr_cli is correr_falso, "el observador no restauró la puerta"
    assert recibidas == ["<cv>\nsintetico\n</cv>"], "la llamada de verdad no llegó al original"
    assert gastos == [pytest.approx(COSTO_POR_LLAMADA)]
    assert all(isinstance(gasto, float) for gasto in gastos), "solo se guarda el número"

    monkeypatch.setattr(cliente, NOMBRE_DE_LA_COSTURA, _puerta_que_falla)
    with pytest.raises(RuntimeError), costo_observado(True):
        cliente.correr_cli(("claude",), "<cv>\nsintetico\n</cv>", 1.0)
    assert cliente.correr_cli is _puerta_que_falla, "la puerta no se restauró tras un fallo"


def _puerta_que_falla(argumentos: tuple[str, ...], entrada: str, timeout: float) -> str:
    """El proceso del proveedor que se cae: lo que el observador tiene que dejar pasar."""
    raise RuntimeError("el proceso del proveedor se cayó")


async def test_la_traza_del_arnes_dice_el_score_y_nunca_las_razones_ni_el_cv(
    camino: PonerGuion,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Criterio 8 · la regla de log de F12 y D15, también en una herramienta.

    La traza existe para que una pasada de once minutos con el proveedor real no
    parezca colgada, y por eso imprime una línea por llamada. Lo que no puede
    llevar es el texto: hoy los casos son sintéticos, pero el día que esto corra
    con el conjunto dorado de CA14 (PR-17) serán CVs de candidatos reales de
    Northstar, y la traza acaba en la consola de quien la lanzó."""
    razon = "Punto considerado: fastapi"
    camino({"fs-01": [respuesta_del_cli(85, razon, "Punto considerado: postgres")]})

    await correr(modo="claude", k=1, ids=["fs-01"], traza=True)

    traza = normalizar(capsys.readouterr().err)
    assert "fs-01" in traza and "score=85" in traza
    assert razon not in traza, "la traza lleva una razón del modelo dentro"
    filtradas = [frase for frase in frases_de(caso("fs-01")["cv"]) if frase in traza]
    assert filtradas == [], f"la traza lleva texto del CV: {filtradas}"
