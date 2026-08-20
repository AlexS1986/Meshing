#!/usr/bin/env bash
#
# Schritt 2 der Batch-Studie: erzeugt je Kombination die Punkt-Jobs
# (Belastungsrichtungen im eps_1/eps_2/eps_3-Raum).
#
#   ./batch_setup_jobs.sh            # Punktzahl aus config.sh (YIELD_SURFACE_POINTS)
#   ./batch_setup_jobs.sh 48         # Punktzahl explizit
#
# Ergebnis je Kombination:
#   yield_surface_jobs/<dataset>_sigy<XXX>/nNNN/
#     manifest.csv
#     submit_all_yield_surface_points.sh
#     ys_.../{config.json, parameters.txt, job_ys_..._CLUSTER.sh}
#
# Voraussetzung: batch_create_configs.sh lief vorher.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
YIELD_SURFACE_POINTS="${1:-${YIELD_SURFACE_POINTS:-96}}"
export YIELD_SURFACE_POINTS
# shellcheck source=/dev/null
source "$SCRIPT_DIR/batch_lib.sh"

echo "=== Punkt-Jobs erzeugen ==="
batch_print_plan
echo

total=0
while read -r ds sig combo cfg jobs; do
  [[ -n "$ds" ]] || continue
  if [[ ! -f "$SCRIPT_DIR/$cfg" ]]; then
    echo "[FEHLER] Config fehlt: $cfg  -> zuerst ./batch_create_configs.sh" >&2
    exit 2
  fi
  echo "--- $combo  ($cfg -> $jobs)"
  YIELD_SURFACE_BASE_CONFIG="$cfg" \
  YIELD_SURFACE_OUTPUT_DIR="$jobs" \
  YIELD_JOB_NAME_PREFIX="${ds}_s$(batch_sigy_tag "$sig")" \
  bash "$SCRIPT_DIR/setup_yield_surface_jobs.sh" "$YIELD_SURFACE_POINTS"
  total=$((total + YIELD_SURFACE_POINTS))
done < <(batch_combos)

echo
echo "Punkt-Jobs insgesamt: $total"
if [[ "$total" -gt "${BATCH_MAX_SUBMIT:-1000}" ]]; then
  echo "[WARNUNG] Das sind mehr als BATCH_MAX_SUBMIT=${BATCH_MAX_SUBMIT:-1000} Jobs."
  echo "          batch_submit_CLUSTER.sh wird sie nicht in einem Rutsch einreichen."
fi
