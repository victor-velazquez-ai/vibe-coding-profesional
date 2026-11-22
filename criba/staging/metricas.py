"""Consulta de métricas para tu agente durante un incidente, **con el rol `agente_metricas`**.

Es la puerta que le das a tu agente en producción: una consulta SQL, una transacción
de solo lectura y el rol que solo ve las vistas agregadas de `metricas`. No hay forma
de pedir otra cosa: si la consulta toca `candidatos` o `match_scores`, Postgres
responde «permission denied», y eso es lo que tiene que pasar.

  uv run --env-file staging/staging.env python staging/metricas.py \n      "SELECT * FROM metricas.scores_por_vacante"

Sin `docker exec` a propósito: en `.claude/settings.json` cualquier `docker` pide
permiso, y en una sesión sin persona delante (`claude -p`) pedir permiso es no poder.
"""

import os
import sys

from sqlalchemy import create_engine, text


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit('uso: python staging/metricas.py "SELECT ..."')
    url = os.environ.get("CRIBA_URL_METRICAS")
    if not url:
        sys.exit("falta CRIBA_URL_METRICAS (está en staging/staging.env)")
    motor = create_engine(url)
    with motor.connect() as con:
        con.execute(text("SET TRANSACTION READ ONLY"))
        filas = con.execute(text(sys.argv[1]))
        columnas = list(filas.keys())
        datos = [[("" if v is None else str(v)) for v in fila] for fila in filas]
    anchos = [max([len(c)] + [len(f[i]) for f in datos]) for i, c in enumerate(columnas)]
    print(" | ".join(c.ljust(a) for c, a in zip(columnas, anchos, strict=True)))
    print("-+-".join("-" * a for a in anchos))
    for f in datos:
        print(" | ".join(v.ljust(a) for v, a in zip(f, anchos, strict=True)))
    print(f"({len(datos)} filas)")


if __name__ == "__main__":
    main()
