"""Deja el entorno de QA en un estado conocido antes de cada pasada (sección 7).

    uv run python qa/preparar.py                          # semilla + scores con el MOCK
    uv run python qa/preparar.py --proveedor claude_cli   # scores reales (≈0,01 USD por CV)

Hace tres cosas, en este orden:

1. **Vuelve a sembrar `criba_dev`** con `app.plataforma.semilla` (TRUNCATE + datos
   sintéticos): lo que dejó la pasada anterior —candidatos de prueba, CVs subidos,
   trabajos— desaparece. Una QA que corre sobre la basura de otra reporta basura.
2. **Encola un trabajo por cada postulación abierta con CV** de las empresas
   activadas, por la fachada de Match (`encolar`), como lo haría la subida de CV.
3. **Corre el ejecutor** hasta vaciar la cola, con el proveedor elegido.

El entorno de Match lo decide el entorno del proceso, igual que en el servidor:
`CRIBA_MATCH_ACTIVO` y `CRIBA_MATCH_EMPRESAS_ACTIVADAS`. Si no están, este script
usa los de la QA: Match encendido y **solo Northstar** activada (SPEC, «Alcance de
activación»). Meridian queda apagada, como en producción.

Nunca toca `criba_test` ni nada fuera de la base de desarrollo.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("CRIBA_MATCH_ACTIVO", "1")
os.environ.setdefault("CRIBA_MATCH_EMPRESAS_ACTIVADAS", "northstar-health")

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.configuracion import ajustes
from app.db import motor
from app.match.cola.ejecutor import pasadas
from app.match.fachada import encolar
from app.migracion import aplicar_migraciones
from app.plataforma.modelos import ETAPAS_CERRADAS, Candidato, Postulacion
from app.plataforma.semilla import resumen, sembrar


def encolar_postulaciones_con_cv(sesion: Session) -> int:
    pares = sesion.execute(
        select(Postulacion.vacante_id, Postulacion.candidato_id)
        .join(Candidato, Candidato.id == Postulacion.candidato_id)
        .where(Candidato.cv_texto.is_not(None), Postulacion.etapa.not_in(ETAPAS_CERRADAS))
        .order_by(Postulacion.id)
    ).all()
    for vacante_id, candidato_id in pares:
        encolar(sesion, vacante_id, candidato_id)
    sesion.commit()
    return len(pares)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--proveedor", choices=("mock", "claude_cli"), default="mock")
    args = parser.parse_args()
    os.environ["CRIBA_MATCH_PROVEEDOR"] = args.proveedor

    aplicar_migraciones(ajustes().url_bd)
    with Session(motor()) as sesion:
        sembrar(sesion)
        print(resumen(sesion).splitlines()[0])
        pares = encolar_postulaciones_con_cv(sesion)
        hechos = asyncio.run(pasadas(sesion, maximo=1000))
        sesion.commit()
    print(
        f"Postulaciones abiertas con CV: {pares}. Trabajos procesados: {hechos} "
        f"(proveedor: {args.proveedor}; las empresas sin activar no encolan). "
        f"Empresas activadas: {os.environ['CRIBA_MATCH_EMPRESAS_ACTIVADAS']}."
    )


if __name__ == "__main__":
    main()
