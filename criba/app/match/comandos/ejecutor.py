"""El ejecutor como **proceso aparte**, que es lo que el staging necesita.

    uv run --env-file staging/staging.env python -m app.match.comandos.ejecutor

Corre `una_pasada` en bucle —hasta vaciar la cola y a esperar unos segundos—
hasta que alguien lo pare con Ctrl+C. Nada más: los reintentos, el lease y la
concurrencia siguen viviendo en `app/match/cola/ejecutor.py` (PR-06, PR-14,
PR-15). Este módulo es **quién lo invoca**, y solo eso.

**Esto no cambia lo que ADR-001 decide para producción.** La Decisión 2 de
ADR-001 dice «el ejecutor corre en el proceso web», y sigue siendo así: el gancho
de subida de CV encola y el proceso web puntúa. Extraerlo a un proceso aparte está
registrado allí como **cambio preparado, no hecho** —«el código del bucle es el
mismo y solo cambia quién lo invoca»—, con cinco disparadores de revisión (T1-T5)
y un hito en diciembre.

Por qué en el staging va **aparte**, entonces:

1. el staging existe para medir T1 —«p95 al abrir la vacante, con la cola
   trabajando»— y con el ejecutor dentro del mismo proceso que sirve las vistas no
   se puede separar la contención del scoring de la de la web. Con dos procesos,
   la medición dice de dónde viene el p95;
2. con el proveedor real encendido (`claude_cli`), una pasada tarda lo que tarde
   el CLI. En el staging eso tiene que poder pararse con Ctrl+C sin tirar la app,
   que es justo la mitad de ADR-001 que su propio argumento en contra señala («el
   ejecutor no puede morir independientemente de la app»);
3. y es la forma de ejercer el cambio preparado antes de necesitarlo: si T1 se
   dispara en diciembre, el proceso ya existe y ya se sabe arrancar.

Lo que este proceso **no** es: el comando de la carga inicial de CA20, que puntúa
una lista explícita de vacantes y es PR-16 (`comandos/carga_inicial.py`). Aquí no
se elige qué puntuar: se atiende la cola en el orden en que está.

Qué **no** trae, y a propósito: ni reconciliación de leases ni la alerta de
pendientes >60 min de CA7 (son PR-15), ni apagado ordenado por SIGTERM, ni tope
de concurrencia (PR-14). Una pasada a la vez, como el bucle de hoy.
"""

from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session

from app.db import motor
from app.match.cola.ejecutor import una_pasada
from app.match.configuracion import ajustes_match
from app.registro import configurar_logs

NOMBRE_DEL_PROCESO = "ejecutor"
# Pocos segundos: el presupuesto de D16 es de 10 minutos de CV recibido a score
# guardado, así que no hace falta sondear más rápido, y a 12 CVs/hora de toda la
# plataforma (`docs/contexto.md`, [04:06]) tampoco serviría de nada.
SEGUNDOS_ENTRE_VUELTAS = 5.0


async def bucle(intervalo: float = SEGUNDOS_ENTRE_VUELTAS) -> None:
    """`una_pasada` hasta vaciar la cola y a esperar. Lo para Ctrl+C.

    **Una sesión por trabajo, con su `commit()` antes de tomar el siguiente.**
    No es un detalle: con el proveedor real una pasada tarda lo que tarde el
    CLI, y encadenar varias dentro de una sola transacción (lo que hacía
    `pasadas(bd)` con su `maximo=100` por omisión) la deja abierta durante toda
    la tanda. Eso es exactamente lo que F16 cuenta —la migración que se queda
    esperando—, mantiene tomadas con `FOR UPDATE SKIP LOCKED` las filas de toda
    la tanda, hace que `metricas.trabajos_por_estado` y la alerta de pendientes
    >60 min de CA7 vean como `pendiente` un trabajo que ya se puntuó, y si el
    proceso muere a mitad se pierde el trabajo de toda la tanda aunque el gasto
    contra el techo de D12 ya se haya hecho. Por eso aquí no se usa `pasadas`:
    cada trabajo abre su propia sesión y hace su propio `commit()`, que es la
    misma forma que usa `crear_sesion` en la app, una sesión por unidad de
    trabajo.
    """
    while True:
        hubo_trabajo = True
        while hubo_trabajo:
            with Session(motor(), expire_on_commit=False) as bd:
                hubo_trabajo = bool(await una_pasada(bd))
                bd.commit()
        await asyncio.sleep(intervalo)


def main() -> None:
    """Punto de entrada del proceso: configura los logs, dice dónde y gira."""
    archivo = configurar_logs(NOMBRE_DEL_PROCESO)
    ajustes = ajustes_match()
    # **Qué empresas están activadas no se dice aquí**, y eso lo exige un test:
    # el estado por empresa se lee en `configuracion.py` y en el repositorio, en
    # ningún otro sitio (`docs/arquitectura.md` §4 y §5.3,
    # `tests/match/test_activacion_por_empresa.py`). Un banner informativo es un
    # segundo lector, y dos lectores son dos reglas que se separan en enero. Qué
    # empresas están encendidas se mira en `staging/staging.env`, que es de donde
    # sale. El interruptor **global** sí se dice: es otra cosa y este bucle lo
    # consulta en cada pasada (R6·I5).
    print(f"Ejecutor de Match · activo={ajustes.activo} proveedor={ajustes.modo_proveedor}")
    print(f"Logs: {archivo if archivo is not None else 'solo a la consola (sin CRIBA_LOG_DIR)'}")
    if not ajustes.activo:
        # No se calla: con el interruptor global apagado `una_pasada` no hace
        # nada, y un proceso que gira sin hacer nada y sin decirlo es media hora
        # buscando por qué no hay scores (R6·I5, y la caché de una lectura por
        # proceso de `ajustes_match`).
        print("CRIBA_MATCH_ACTIVO está apagado: este proceso no va a puntuar nada.")
    print(f"Una pasada cada {SEGUNDOS_ENTRE_VUELTAS:g} s. Ctrl+C para parar.")
    try:
        asyncio.run(bucle())
    except KeyboardInterrupt:
        print("\nEjecutor detenido.")


if __name__ == "__main__":
    main()
