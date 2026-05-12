#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

if [[ "${1:-}" == "--all" ]]; then
  SELECTED_BINNINGS=("${BINNING_IDS[@]}")
elif [[ -n "${1:-}" ]]; then
  SELECTED_BINNINGS=("$1")
else
  SELECTED_BINNINGS=("$DEFAULT_BINNING_ID")
fi

bash "$SCRIPT_DIR/create_config.sh" --all

SCRIPTS=(
  "00_dicom_2_npy.py"
  "01_segment_slice_wise.py"
  "02_build3D_segmented_array.py"
  "02a_rotate_pic_to_align_with_axis.py"
  "02b_build_subvolume_arrays.py"
)

for binning_id in "${SELECTED_BINNINGS[@]}"; do
  binning_label="Bin${binning_id}"
  config_path="$SCRIPT_DIR/config-${binning_label}.json"

  echo "=========================================="
  echo "Processing $binning_label with $config_path"
  echo "=========================================="

  for script in "${SCRIPTS[@]}"; do
    echo "Running $script"
    python3 "$SCRIPT_DIR/$script" --config "$config_path"
    echo "Finished $script"
    echo "----------------------------"
  done
done

echo "All selected binnings completed."
