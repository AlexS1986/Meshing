#!/usr/bin/env bash
#
# Schritt 1 der Batch-Studie: erzeugt je Kombination (Datensatz x sig_y) eine
# Config aus config-A01-les.json.
#
#   ./batch_create_configs.sh
#   ONLY_DATASETS="JM-25-77" ONLY_SIG_Y=100 ./batch_create_configs.sh
#   LES_REDUCE_FACTOR=8 ./batch_create_configs.sh
#
# Ergebnis: config-<dataset>-r<N>-sigy<XXX>.json im Projektordner.
# Beide sig_y-Varianten eines Datensatzes bekommen dieselbe dataset.id und
# damit denselben Netzordner; unterschieden werden sie ueber binning.label.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/batch_lib.sh"

echo "=== Configs erzeugen ==="
batch_print_plan
echo

count=0
while read -r ds sig combo cfg jobs; do
  [[ -n "$ds" ]] || continue
  les_path="$(batch_dataset_les_path "$ds")"
  run_id="$(batch_run_id "$ds")"
  label="$(batch_binning_label "$ds" "$sig")"

  echo "--- $combo"
  LES_DATASET_ID="$run_id" \
  LES_INPUT="$les_path" \
  LES_CONFIG_FILENAME="$cfg" \
  LES_BASE_CONFIG="${LES_BASE_CONFIG:-config-A01-les.json}" \
  YIELD_SIG_Y="$sig" \
  bash "$SCRIPT_DIR/create_les_config.sh" --binning-label "$label" "$@"
  count=$((count + 1))
  echo
done < <(batch_combos)

echo "$count Configs geschrieben in $SCRIPT_DIR"
