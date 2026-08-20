#!/usr/bin/env bash
#
# Schritt 5: Ergebnisse aller Kombinationen einsammeln, zu CSVs zusammenfassen
# und in EIN Zip packen, das sich mit einem scp herunterladen laesst.
#
# Auf dem Cluster (Login-Node):
#
#   "$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS/batch_collect_results.sh"
#
# Optionen (Umgebungsvariablen):
#
#   NAME=zwischenstand-1     Name des Pakets (Default: results_<datum>-<uhrzeit>)
#   WITH_AVERAGES=1          die Zeitreihen yield_averages_*.json mitnehmen
#                            (vollstaendige Last-Verformungs-Historie, gross)
#   WITH_LOGS=1              SLURM .out/.err der Punkt-Jobs mitnehmen
#   PER_COMBO_ZIP=1          ein Zip je Kombination statt eines grossen
#   NO_ZIP=1                 nur den Paketordner erzeugen, nicht zippen
#   ONLY_DATASETS=... ONLY_SIG_Y=...   nur Teile einsammeln
#
# Das Paket landet unter 00_results/_packages/ im Projektordner.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/batch_lib.sh"

ARGS=(--project-dir "$SCRIPT_DIR" --expected-points "$YIELD_SURFACE_POINTS")
[[ -n "${NAME:-}" ]]            && ARGS+=(--name "$NAME")
[[ "${WITH_AVERAGES:-0}" == "1" ]] && ARGS+=(--with-averages)
[[ "${WITH_LOGS:-0}" == "1" ]]     && ARGS+=(--with-logs)
[[ "${PER_COMBO_ZIP:-0}" == "1" ]] && ARGS+=(--per-combo-zip)
[[ "${NO_ZIP:-0}" == "1" ]]        && ARGS+=(--no-zip)

n=0
while read -r ds sig combo cfg jobs; do
  [[ -n "$ds" ]] || continue
  ARGS+=(--combo "$ds|$sig|$(batch_run_id "$ds")|$(batch_binning_label "$ds" "$sig")|$combo|$cfg|$jobs")
  n=$((n + 1))
done < <(batch_combos)

if [[ "$n" -eq 0 ]]; then
  echo "Keine Kombinationen ausgewaehlt (ONLY_DATASETS / ONLY_SIG_Y pruefen)." >&2
  exit 2
fi

echo "=== Ergebnisse einsammeln ($n Kombinationen) ==="
python3 "$SCRIPT_DIR/batch_collect_results.py" "${ARGS[@]}"

echo
echo "Herunterladen (vom eigenen Rechner aus):"
echo "  scp '${USER:-<user>}@<login-node>:$SCRIPT_DIR/00_results/_packages/*.zip' ."
echo
echo "Oder erst anschauen:"
echo "  ls -lh \"$SCRIPT_DIR/00_results/_packages\""
