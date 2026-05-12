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

PREPROCESS_SCRIPTS=(
  "00_dicom_2_npy.py"
  "01_segment_slice_wise.py"
  "02_build3D_segmented_array.py"
  "02a_rotate_pic_to_align_with_axis.py"
  "02b_build_subvolume_arrays.py"
)

VOLUME_FILENAME="volume.npy"
MESH_SCRIPT="$SCRIPT_DIR/03_mesh_3D_array_pygalmesh.py"
SCALE_SCRIPT="$SCRIPT_DIR/04_scale_and_translate_mesh_mod.py"

for binning_id in "${SELECTED_BINNINGS[@]}"; do
  binning_label="Bin${binning_id}"
  run_name="${SPECIMEN_NAME}_${binning_label}"
  config_path="$SCRIPT_DIR/config-${binning_label}.json"
  base_subvolume_folder="$SCRIPT_DIR/${run_name}_segmented/${run_name}_segmented_3D"

  echo "=========================================="
  echo "Processing $binning_label with $config_path"
  echo "=========================================="

  for script in "${PREPROCESS_SCRIPTS[@]}"; do
    echo "Running $script"
    python3 "$SCRIPT_DIR/$script" --config "$config_path"
    echo "Finished $script"
    echo "----------------------------"
  done

  echo "Starting mesh generation for $binning_label"
  find "$base_subvolume_folder" -type f -name "$VOLUME_FILENAME" | while read -r npy_file; do
    subfolder="$(dirname "$npy_file")"
    folder_name="$(basename "$subfolder")"
    mesh_output="$subfolder/mesh.xdmf"

    if [[ "$folder_name" =~ subvolume_x([0-9]+)_y([0-9]+) ]]; then
      center_x="${BASH_REMATCH[1]}"
      center_y="${BASH_REMATCH[2]}"
    else
      echo "Could not extract center_x and center_y from folder name: $folder_name"
      exit 1
    fi

    python3 "$MESH_SCRIPT" --config "$config_path" --npy "$npy_file" --mesh "$mesh_output"
    python3 "$SCALE_SCRIPT" --config "$config_path" --mesh "$mesh_output" --center_x "$center_x" --center_y "$center_y"
  done
done

echo "All selected binnings processed and meshed."
