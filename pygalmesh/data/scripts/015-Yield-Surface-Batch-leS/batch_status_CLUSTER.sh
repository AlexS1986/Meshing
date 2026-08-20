#!/usr/bin/env bash
#
# Uebersicht ueber den Stand der Studie: Netz vorhanden, wie viele Punkt-Jobs
# erzeugt, wie viele Ergebnisse da, wie viele Jobs noch laufen oder warten.
#
#   "$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS/batch_status_CLUSTER.sh"
#
# Laeuft auch ohne SLURM (dann ohne die Queue-Spalten).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/batch_lib.sh"

QUEUE_FILE="$(mktemp)"
trap 'rm -f "$QUEUE_FILE"' EXIT
if command -v squeue >/dev/null 2>&1; then
  squeue -h -u "$USER" -o '%j %T' > "$QUEUE_FILE" 2>/dev/null || true
fi

count_state() {  # count_state <jobname-praefix> <STATE>
  awk -v p="$1" -v s="$2" '$1 ~ "^"p && $2 == s {n++} END {print n+0}' "$QUEUE_FILE"
}

printf '%-24s %-6s %6s %8s %8s %8s %8s %8s\n' \
  KOMBINATION NETZ JOBS ERGEBNIS GUELTIG RUNNING PENDING SONST
printf '%.0s-' {1..90}; echo

total_jobs=0; total_res=0; total_ok=0
while read -r ds sig combo cfg jobs; do
  [[ -n "$ds" ]] || continue
  run_id="$(batch_run_id "$ds")"
  label="$(batch_binning_label "$ds" "$sig")"

  mesh="nein"
  if compgen -G "$SCRIPT_DIR/${run_id}_segmented/${run_id}_segmented_3D/subvolume_x*_y*/dlfx_mesh.xdmf" >/dev/null; then
    mesh="ja"
  fi

  n_jobs="$(find "$SCRIPT_DIR/$jobs" -mindepth 2 -maxdepth 2 -name 'job_*_CLUSTER.sh' 2>/dev/null | wc -l | tr -d ' ')"

  results=0; valid=0
  for root in "$SCRIPT_DIR/00_results/$run_id/$label" "$SCRIPT_DIR/yield_surface_runs/$run_id/$label"; do
    [[ -d "$root" ]] || continue
    while IFS= read -r f; do
      results=$((results + 1))
      grep -q '"final_yield_state": {' "$f" && valid=$((valid + 1)) || true
    done < <(find "$root" -name 'yield_run_*.json' 2>/dev/null | sort -u)
    [[ "$results" -gt 0 ]] && break   # 00_results hat Vorrang
  done

  prefix="${ds}_s$(batch_sigy_tag "$sig")-ys"
  run_n="$(count_state "$prefix" RUNNING)"
  pend_n="$(count_state "$prefix" PENDING)"
  other_n="$(awk -v p="$prefix" '$1 ~ "^"p && $2 != "RUNNING" && $2 != "PENDING" {n++} END {print n+0}' "$QUEUE_FILE")"

  printf '%-24s %-6s %6s %8s %8s %8s %8s %8s\n' \
    "$combo" "$mesh" "$n_jobs" "$results" "$valid" "$run_n" "$pend_n" "$other_n"
  total_jobs=$((total_jobs + n_jobs)); total_res=$((total_res + results)); total_ok=$((total_ok + valid))
done < <(batch_combos)

printf '%.0s-' {1..90}; echo
printf '%-24s %-6s %6s %8s %8s\n' SUMME "" "$total_jobs" "$total_res" "$total_ok"
echo
echo "Netzvorbereitungen in der Queue:"
awk '$1 ~ /^prep-/ {printf "  %-24s %s\n", $1, $2}' "$QUEUE_FILE" || true
echo
echo "Ergebnisse einsammeln und zippen: $SCRIPT_DIR/batch_collect_results.sh"
