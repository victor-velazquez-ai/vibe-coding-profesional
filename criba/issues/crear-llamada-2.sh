#!/usr/bin/env bash
#
# Crea en GitHub los issues de la SEGUNDA llamada con Tomás Reyes (22-nov-2026).
#
# NO EJECUTAR TODAVÍA: el repo de GitHub de Criba Match aún no existe.
# Antes de correrlo:
#   1. crear el repo y configurar `gh auth login`;
#   2. ajustar REPO abajo (el mismo valor que `crear.sh`);
#   3. crear las etiquetas que se usan aquí (o quitar los --label).
#
# Cada issue toma su cuerpo del borrador en este mismo directorio.
# Fuente de todo: llamadas/2026-11-22-tomas-2.md y llamadas/2026-11-22-tomas-2-delta.md
#
# El incidente del cero ([00:18], [01:12]) NO lleva issue: va por el camino del
# RUNBOOK.md y su informe vive en postmortems/.

set -euo pipefail

REPO="criba/criba-match"   # <-- ajustar cuando exista
cd "$(dirname "$0")"

gh issue create --repo "$REPO" \
  --title "Los hiring managers de Northstar quieren ver el score y el porqué" \
  --body-file "12-hiring-managers-ven-score-y-porque.md" \
  --label "decision" --label "pregunta-cliente" --label "permisos" --label "legal"

gh issue create --repo "$REPO" \
  --title "Recalcular los scores al editar la vacante, sin recalcular 500 por una coma" \
  --body-file "13-recalculo-al-editar-la-vacante.md" \
  --label "decision" --label "pregunta-cliente" --label "costos" --label "producto"

echo "Listo: 2 issues creados en $REPO"
