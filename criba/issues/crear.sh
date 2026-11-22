#!/usr/bin/env bash
#
# Crea en GitHub los issues de la llamada del 20-nov-2026 con Tomás Reyes.
#
# NO EJECUTAR TODAVÍA: el repo de GitHub de Criba Match aún no existe.
# Antes de correrlo:
#   1. crear el repo y configurar `gh auth login`;
#   2. ajustar REPO abajo;
#   3. crear las etiquetas que se usan aquí (o quitar los --label).
#
# Cada issue toma su cuerpo del borrador en este mismo directorio.
# Fuente de todo: llamadas/2026-11-20-tomas.md y llamadas/2026-11-20-tomas-delta.md

set -euo pipefail

REPO="criba/criba-match"   # <-- ajustar cuando exista
cd "$(dirname "$0")"

gh issue create --repo "$REPO" \
  --title "Resolver: mandar el CV completo a un proveedor externo contradice D3" \
  --body-file "01-cv-completo-proveedor-externo-vs-d3.md" \
  --label "bloqueante" --label "decision" --label "seguridad"

gh issue create --repo "$REPO" \
  --title "Aislamiento multiempresa en un solo lugar del código, con tests" \
  --body-file "02-aislamiento-multiempresa-un-solo-lugar.md" \
  --label "seguridad" --label "prioridad-alta"

gh issue create --repo "$REPO" \
  --title "Scoring asíncrono: la página nunca espera al modelo" \
  --body-file "03-scoring-asincrono-la-pagina-no-espera.md" \
  --label "arquitectura" --label "demo-15-ene"

gh issue create --repo "$REPO" \
  --title "Decidir el formato del score: porcentaje, semáforo o ambos" \
  --body-file "04-formato-del-score-porcentaje-o-semaforo.md" \
  --label "decision" --label "pregunta-cliente" --label "demo-15-ene"

gh issue create --repo "$REPO" \
  --title "Techo de costo mensual y protección contra ráfagas" \
  --body-file "05-techo-de-costo-y-proteccion-de-rafagas.md" \
  --label "decision" --label "pregunta-cliente" --label "costos"

gh issue create --repo "$REPO" \
  --title "Alcance de la ley 144 de Nueva York para Criba Match" \
  --body-file "06-ley-144-nueva-york-alcance-legal.md" \
  --label "legal" --label "pregunta-cliente" --label "riesgo"

gh issue create --repo "$REPO" \
  --title "¿Los hiring managers ven el score?" \
  --body-file "07-hiring-managers-ven-el-score.md" \
  --label "decision" --label "pregunta-cliente" --label "permisos"

gh issue create --repo "$REPO" \
  --title "Bilingüe: idioma del CV y idioma de la explicación" \
  --body-file "08-bilingue-idioma-del-cv-y-de-la-explicacion.md" \
  --label "decision" --label "pregunta-cliente" --label "producto"

gh issue create --repo "$REPO" \
  --title "Una vacante con 500+ candidatos tiene que abrir rápido" \
  --body-file "09-rendimiento-vacante-500-candidatos.md" \
  --label "rendimiento" --label "demo-15-ene"

gh issue create --repo "$REPO" \
  --title "Inventariar dónde guarda Match datos del candidato y cómo se borran" \
  --body-file "10-inventario-y-borrado-de-datos-de-match.md" \
  --label "privacidad" --label "soc2"

gh issue create --repo "$REPO" \
  --title "Acordar por escrito el alcance mínimo de la demo con Northstar (15-ene-2027)" \
  --body-file "11-alcance-minimo-demo-northstar-15-enero.md" \
  --label "planificacion" --label "demo-15-ene" --label "pregunta-cliente"

echo "Listo: 11 issues creados en $REPO"
