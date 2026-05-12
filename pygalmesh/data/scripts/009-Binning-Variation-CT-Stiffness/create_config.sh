#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"
HOST_BASE_PATH="${HOST_BASE_PATH:-$SCRIPT_DIR}"

json_value_or_null() {
  local var="${1:-}"
  if [[ -z "$var" ]]; then
    echo "null"
  else
    echo "$var"
  fi
}

reduce_factor_value() {
  local reduce_factor="${1:-null}"
  if [[ "$reduce_factor" == "null" || -z "$reduce_factor" ]]; then
    echo 1
  else
    echo "$reduce_factor"
  fi
}

reduce_label() {
  local reduce_factor="${1:-null}"
  if [[ "$reduce_factor" == "null" || -z "$reduce_factor" ]]; then
    echo "reduce-null"
  else
    echo "reduce-${reduce_factor}"
  fi
}

dicom_option_for_reduce() {
  local reduce_factor="${1:-null}"
  if [[ "$reduce_factor" == "null" || -z "$reduce_factor" ]]; then
    echo "full"
  else
    echo "reduce"
  fi
}

floor_scaled_index() {
  local value="$1"
  local binning_id="$2"
  local reduce_factor="$3"
  awk -v value="$value" \
      -v ref_bin="$REFERENCE_BINNING_ID" \
      -v ref_reduce="$REFERENCE_REDUCE_FACTOR" \
      -v bin="$binning_id" \
      -v reduce="$reduce_factor" \
      'BEGIN { print int(value * ref_bin * ref_reduce / (bin * reduce)) }'
}

ceil_scaled_index() {
  local value="$1"
  local binning_id="$2"
  local reduce_factor="$3"
  awk -v value="$value" \
      -v ref_bin="$REFERENCE_BINNING_ID" \
      -v ref_reduce="$REFERENCE_REDUCE_FACTOR" \
      -v bin="$binning_id" \
      -v reduce="$reduce_factor" \
      'BEGIN { x = value * ref_bin * ref_reduce / (bin * reduce); if (int(x) == x) print int(x); else print int(x) + 1 }'
}

round_scaled_index() {
  local value="$1"
  local binning_id="$2"
  local reduce_factor="$3"
  awk -v value="$value" \
      -v ref_bin="$REFERENCE_BINNING_ID" \
      -v ref_reduce="$REFERENCE_REDUCE_FACTOR" \
      -v bin="$binning_id" \
      -v reduce="$reduce_factor" \
      'BEGIN { print int(value * ref_bin * ref_reduce / (bin * reduce) + 0.5) }'
}

write_config_for_binning() {
  local binning_id="$1"
  local config_filename="${2:-config-Bin${binning_id}.json}"
  local reduce_factor="${3:-$REDUCE_FACTOR}"
  local reduce_value
  reduce_value="$(reduce_factor_value "$reduce_factor")"
  local dicom_option
  dicom_option="$(dicom_option_for_reduce "$reduce_factor")"
  local binning_label="Bin${binning_id}"
  local run_name="${SPECIMEN_NAME}_${binning_label}"
  if [[ "$config_filename" == *"reduce-"* ]]; then
    run_name="${run_name}_$(reduce_label "$reduce_factor")"
  fi
  local dicom_folder="${RESOURCE_BASE}/Binning ${binning_id}/${DICOM_FOLDER_PREFIX}_${binning_label}"

  local config_path="$HOST_BASE_PATH/$config_filename"
  local output_base="$BASE_PATH/${run_name}_segmented"
  local npy_output_folder="$BASE_PATH/${run_name}/npy"
  local segmented_3d_output="$output_base/${run_name}_segmented_3D"
  local mesh_output_path="$output_base/mesh.xdmf"
  local min_z max_z buffer_width_min_x buffer_width_max_x buffer_width_min_y buffer_width_max_y buffer_width_min_z buffer_width_max_z

  min_z="$(floor_scaled_index "$REFERENCE_MIN_Z" "$binning_id" "$reduce_value")"
  max_z="$(ceil_scaled_index "$REFERENCE_MAX_Z" "$binning_id" "$reduce_value")"
  buffer_width_min_x="$(round_scaled_index "$REFERENCE_BUFFER_WIDTH_MIN_X" "$binning_id" "$reduce_value")"
  buffer_width_max_x="$(round_scaled_index "$REFERENCE_BUFFER_WIDTH_MAX_X" "$binning_id" "$reduce_value")"
  buffer_width_min_y="$(round_scaled_index "$REFERENCE_BUFFER_WIDTH_MIN_Y" "$binning_id" "$reduce_value")"
  buffer_width_max_y="$(round_scaled_index "$REFERENCE_BUFFER_WIDTH_MAX_Y" "$binning_id" "$reduce_value")"
  buffer_width_min_z="$(round_scaled_index "$REFERENCE_BUFFER_WIDTH_MIN_Z" "$binning_id" "$reduce_value")"
  buffer_width_max_z="$(round_scaled_index "$REFERENCE_BUFFER_WIDTH_MAX_Z" "$binning_id" "$reduce_value")"

  cat > "$config_path" <<EOF
{
  "metadata_output_path": "$output_base/metadata.json",
  "binning": {
    "id": $binning_id,
    "label": "$binning_label",
    "resource_folder": "$dicom_folder",
    "script_reduce_factor": $(json_value_or_null "$reduce_factor"),
    "effective_binning_factor": $((binning_id * reduce_value)),
    "region_reference": {
      "binning_id": $REFERENCE_BINNING_ID,
      "reduce_factor": $REFERENCE_REDUCE_FACTOR,
      "min_z": $REFERENCE_MIN_Z,
      "max_z": $REFERENCE_MAX_Z
    }
  },
  "dicom2npy": {
    "foldername": "$dicom_folder",
    "option": "$dicom_option",
    "crop": {
      "x_start": $(json_value_or_null "$CROP_X_START"),
      "x_end": $(json_value_or_null "$CROP_X_END"),
      "y_start": $(json_value_or_null "$CROP_Y_START"),
      "y_end": $(json_value_or_null "$CROP_Y_END")
    },
    "reduce": {
      "factor": $(json_value_or_null "$reduce_factor")
    },
    "slice_start": $(json_value_or_null "$SLICE_START"),
    "slice_end": $(json_value_or_null "$SLICE_END"),
    "output_folder": "$npy_output_folder"
  },
  "01_segment_slice_wise": {
    "specimen_name": "$run_name",
    "input_folder": "$npy_output_folder",
    "output_folder": "$output_base",
    "preview_slice_index": $(json_value_or_null "$PREVIEW_SLICE_INDEX"),
    "seg_algorithm": "$SEGMENTATION_ALGORITHM",
    "gaussian_filter_sigma_factor": $GAUSSIAN_FILTER_SIGMA_FACTOR
  },
  "02_segmented_3D_array": {
    "input_folder": "$output_base",
    "output_folder": "$segmented_3d_output",
    "desired_width_x": $(json_value_or_null "$DESIRED_WIDTH_X"),
    "desired_height_y": $(json_value_or_null "$DESIRED_HEIGHT_Y"),
    "center_x": $(json_value_or_null "$CENTER_X"),
    "center_y": $(json_value_or_null "$CENTER_Y"),
    "min_z": $min_z,
    "max_z": $max_z
  },
  "03_mesh_3D_array": {
    "specimen_name": "${run_name}_segmented",
    "input_folder": "$segmented_3d_output",
    "smoothing_sigma_factor": $SMOOTHING_SIGMA_FACTOR,
    "segmentation_algorithm": "$SEGMENTATION_ALGORITHM",
    "z_slice": 0,
    "scale_factor": $MESH_SCALE_FACTOR,
    "meshing_method": "$MESHING_METHOD",
    "mesh_output_path": "$mesh_output_path",
    "pygalmesh_parameters": {
      "max_element_size_factor": $MAX_ELEMENT_SIZE_FACTOR,
      "max_facet_distance_factor": $MAX_FACET_DISTANCE_FACTOR
    },
    "nanomesh_parameters": {
      "meshing_options": "-pAqD",
      "output_format": "gmsh22",
      "output_binary": false
    }
  },
  "02a_rotate_pic_to_align_with_axis": {
    "material_value": $MATERIAL_VALUE,
    "pore_value": $PORE_VALUE,
    "buffer_width": $BUFFER_WIDTH,
    "buffer_width_min_x": $buffer_width_min_x,
    "buffer_width_max_x": $buffer_width_max_x,
    "buffer_width_min_y": $buffer_width_min_y,
    "buffer_width_max_y": $buffer_width_max_y,
    "buffer_width_min_z": $buffer_width_min_z,
    "buffer_width_max_z": $buffer_width_max_z,
    "angles": [$ROTATE_ANGLE_X, $ROTATE_ANGLE_Y, $ROTATE_ANGLE_Z]
  },
  "02b_build_subvolume_arrays": {
    "xy_divisions": $(json_value_or_null "$XY_DIVISIONS"),
    "subvolume_output_folder": "$segmented_3d_output"
  }
}
EOF

  echo "Wrote $config_path"
}

if [[ "${1:-}" == "--all" ]]; then
  for binning_id in "${BINNING_IDS[@]}"; do
    write_config_for_binning "$binning_id" "config-Bin${binning_id}.json" "null"
  done
  write_config_for_binning "$ACTIVE_BINNING_ID" "config.json"
elif [[ "${1:-}" == "--variants" ]]; then
  for binning_id in "${BINNING_IDS[@]}"; do
    for reduce_factor in "${REDUCE_FACTORS[@]}"; do
      write_config_for_binning "$binning_id" "config-Bin${binning_id}-$(reduce_label "$reduce_factor").json" "$reduce_factor"
    done
  done
elif [[ -n "${1:-}" ]]; then
  write_config_for_binning "$1" "config.json" "${2:-$REDUCE_FACTOR}"
else
  write_config_for_binning "$ACTIVE_BINNING_ID" "config.json"
fi
