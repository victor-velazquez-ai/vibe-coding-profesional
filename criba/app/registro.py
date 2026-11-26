"""Los logs del proceso: consola legible y, en el staging, **una línea JSON por archivo**.

`docs/arquitectura.md` §2 describe los logs como un componente del sistema —«poder
reconstruir qué pasó con un score sin exponer datos»— y §5.5 recuerda lo que son:
«una superficie de salida de datos». Hasta ahora las líneas existían
(`services/listado.py`, `proveedor/cliente.py`) pero nadie las escribía a ningún
sitio: en la suite las recoge `caplog` y en desarrollo se las queda uvicorn. El
staging es el primer entorno donde hay que poder **leerlas después de un
incidente**, y de eso va este módulo.

Dos decisiones, y las dos son de privacidad (F12, D15, CA1 «ni log suyo»):

1. **al archivo solo van los loggers de `app.`**. El motivo no es estética: con el
   nivel del raíz en INFO, cualquier librería que registre a INFO acaba en el
   archivo, y `sqlalchemy.engine` registra **el SQL con sus parámetros** —o sea el
   texto del CV— en cuanto alguien arranca el motor con `echo=True`. Un filtro por
   nombre de logger cierra esa puerta antes de que se abra. La consola no lleva
   filtro: ahí sí interesa ver a uvicorn;
2. **la traza de la excepción no entra**, nunca. Es el camino literal de F12: un
   `subprocess.TimeoutExpired` del CLI del proveedor lleva dentro la línea de
   órdenes, la salida parcial y el error estándar, o sea el prompt con el CV; y la
   forma más natural del mundo de escribirlo en un archivo es dejar que el
   formateador añada el `exc_info`. Qué falló se sabe por el `motivo` del trabajo,
   que es un nombre de tipo acotado a 120 caracteres y vive en la fila de la cola
   (`cola/ejecutor.py`), no en el log.

El directorio sale de `CRIBA_LOG_DIR` y **sin esa variable no se escribe ningún
archivo**: en desarrollo y en la suite esto es un no-op. Cada proceso escribe el
suyo (`app.jsonl`, `ejecutor.jsonl`) porque dos procesos sobre el mismo archivo se
pisan las líneas.

Qué **no** hace, y llega cuando haga falta: ni rotación, ni retención —la
retención de los logs es pregunta abierta de F12 y la decide Priya—, ni
`request_id` propagado por middleware (lo crea por llamada quien registra).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

VARIABLE_DE_DIRECTORIO = "CRIBA_LOG_DIR"
PREFIJO_DE_NUESTROS_LOGGERS = "app"
# Marca de los manejadores que pone este módulo, para que una segunda llamada no
# duplique cada línea. `logging` no sabe decir «ya estabas configurado».
MARCA = "criba"
FORMATO_DE_CONSOLA = "%(levelname)-5.5s [%(name)s] %(message)s"


class FormateadorJSON(logging.Formatter):
    """Un objeto JSON por línea. Si el mensaje ya es un objeto JSON, se mezcla.

    Mezclar y no anidar está pensado para quien lee el archivo con `grep`: las
    líneas que ya nacen en JSON —`match.listar_vacante` y `match.trabajo_cerrado`—
    quedan con sus campos arriba, y las que no —las del adaptador del proveedor,
    `proveedor=claude_cli decision=… latencia_ms=… modelo=…`— quedan bajo
    `mensaje`. Así el archivo es una sola cosa y no dos formatos mezclados.
    """

    def format(self, record: logging.LogRecord) -> str:
        linea: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "logger": record.name,
        }
        mensaje = record.getMessage()
        campos = _objeto_json(mensaje)
        if campos is None:
            linea["mensaje"] = mensaje
        else:
            linea.update(campos)
        # `default=str` y no un `try/except`: un campo que no sea serializable
        # sale como su texto, y la línea se escribe igual. Un log que se cae por
        # un `TypeError` se lleva por delante la petición que lo emitió.
        return json.dumps(linea, ensure_ascii=False, default=str)


def _objeto_json(mensaje: str) -> dict[str, object] | None:
    """El mensaje interpretado como objeto JSON, o `None` si no lo es."""
    if not mensaje.startswith("{"):
        return None
    try:
        valor = json.loads(mensaje)
    except ValueError:
        return None
    return valor if isinstance(valor, dict) else None


class SoloNuestrosLoggers(logging.Filter):
    """Al archivo, solo lo que registra la aplicación (ver decisión 1 de arriba)."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name == PREFIJO_DE_NUESTROS_LOGGERS or record.name.startswith(
            f"{PREFIJO_DE_NUESTROS_LOGGERS}."
        )


def archivo_de(proceso: str) -> Path | None:
    """Dónde escribe este proceso, o `None` si no hay `CRIBA_LOG_DIR`."""
    directorio = os.environ.get(VARIABLE_DE_DIRECTORIO, "").strip()
    return Path(directorio) / f"{proceso}.jsonl" if directorio else None


def configurar_logs(proceso: str) -> Path | None:
    """Deja el proceso registrando a consola y, con `CRIBA_LOG_DIR`, al archivo.

    Devuelve el archivo para que el comando pueda decir en voz alta dónde está
    escribiendo: un log que nadie encuentra durante un incidente no sirve de nada
    (`RUNBOOK.md`).
    """
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    if any(manejador.get_name() == MARCA for manejador in raiz.handlers):
        return archivo_de(proceso)

    consola = logging.StreamHandler()
    consola.set_name(MARCA)
    consola.setFormatter(logging.Formatter(FORMATO_DE_CONSOLA))
    raiz.addHandler(consola)

    destino = archivo_de(proceso)
    if destino is None:
        return None
    destino.parent.mkdir(parents=True, exist_ok=True)
    archivo = logging.FileHandler(destino, encoding="utf-8")
    archivo.set_name(MARCA)
    archivo.setFormatter(FormateadorJSON())
    archivo.addFilter(SoloNuestrosLoggers())
    raiz.addHandler(archivo)
    return destino
