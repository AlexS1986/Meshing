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
      "max_facet_distance_factor": $MAX_FACET_DISTANCE_FACTOR,
      "exude_time_limit": $PYGALMESH_EXUDE_TIME_LIMIT,
      "exude_sliver_bound": $PYGALMESH_EXUDE_SLIVER_BOUND
    },
    "nanomesh_parameters": {
      "meshing_options": "-pAqD",
      "output_format": "gmsh22",
      "output_binary": false
    },
    "sdf_pygalmesh_parameters": {
      "material_value": $SDF_PYGALMESH_MATERIAL_VALUE,
      "sdf_sigma_voxels": $SDF_SIGMA_VOXELS,
      "level": 0.0,
      "pad_width": $SDF_SURFACE_PAD_WIDTH,
      "keep_largest_component": false,
      "component_connectivity": 6,
      "fill_holes": true,
      "require_watertight_surface": true,
      "reorient": false,
      "marching_cubes_step_size": 1,
      "surface_decimation_reduction": 0.0,
      "surface_decimation_preserve_topology": true,
      "surface_decimation_splitting": false,
      "surface_decimation_boundary_vertex_deletion": false,
      "min_surface_component_faces": 0,
      "pygalmesh_parameters": {
        "max_element_size_factor": $MAX_ELEMENT_SIZE_FACTOR,
        "max_facet_distance_factor": $MAX_FACET_DISTANCE_FACTOR,
        "exude_time_limit": $PYGALMESH_EXUDE_TIME_LIMIT,
        "exude_sliver_bound": $PYGALMESH_EXUDE_SLIVER_BOUND,
        "lloyd": false,
        "odt": false,
        "perturb": true,
        "exude": true,
        "max_edge_size_at_feature_edges_factor": 0.0,
        "min_facet_angle": 0.0,
        "max_radius_surface_delaunay_ball_factor": 0.0,
        "max_circumradius_edge_ratio": 0.0,
        "seed": 0,
        "verbose": true
      }
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
    "subvolume_output_folder": "$segmented_3d_output",
    "crop_offsets_reference": {
      "enabled": $SUBVOLUME_CROP_OFFSETS_ENABLED,
      "reference_binning_id": $REFERENCE_BINNING_ID,
      "reference_reduce_factor": $REFERENCE_REDUCE_FACTOR,
      "x_min": $SUBVOLUME_CROP_OFFSET_X_MIN,
      "x_max": $SUBVOLUME_CROP_OFFSET_X_MAX,
      "y_min": $SUBVOLUME_CROP_OFFSET_Y_MIN,
      "y_max": $SUBVOLUME_CROP_OFFSET_Y_MAX,
      "z_min": $SUBVOLUME_CROP_OFFSET_Z_MIN,
      "z_max": $SUBVOLUME_CROP_OFFSET_Z_MAX
    },
    "crop_bounds_reference": {
      "enabled": $SUBVOLUME_CROP_BOUNDS_ENABLED,
      "reference_binning_id": $REFERENCE_BINNING_ID,
      "reference_reduce_factor": $REFERENCE_REDUCE_FACTOR,
      "x_min": $(json_value_or_null "$SUBVOLUME_CROP_BOUND_X_MIN"),
      "x_max": $(json_value_or_null "$SUBVOLUME_CROP_BOUND_X_MAX"),
      "y_min": $(json_value_or_null "$SUBVOLUME_CROP_BOUND_Y_MIN"),
      "y_max": $(json_value_or_null "$SUBVOLUME_CROP_BOUND_Y_MAX"),
      "z_min": $(json_value_or_null "$SUBVOLUME_CROP_BOUND_Z_MIN"),
      "z_max": $(json_value_or_null "$SUBVOLUME_CROP_BOUND_Z_MAX")
    }
  },
  "02e_mirror_extrude_voxel": {
    "enabled": $VOXEL_MIRROR_EXTRUDE_ENABLED,
    "axis": "$VOXEL_MIRROR_EXTRUDE_AXIS",
    "plane": "$VOXEL_MIRROR_EXTRUDE_PLANE",
    "material_value": $MATERIAL_VALUE,
    "output_filename": "volume_mirrored_x2.npy",
    "report_filename": "volume_mirrored_x2.txt",
    "use_mirrored_for_meshing": $VOXEL_MIRROR_EXTRUDE_USE_FOR_MESHING,
    "drop_duplicate_plane": $VOXEL_MIRROR_EXTRUDE_DROP_DUPLICATE_PLANE,
    "repetitions": $VOXEL_MIRROR_EXTRUDE_REPETITIONS
  },
  "02f_add_voxel_shell": {
    "enabled": $ADDITIVE_VOXEL_SHELL_ENABLED,
    "value": $ADDITIVE_VOXEL_SHELL_VALUE,
    "output_filename": "volume_boundary_shell_aniso_external_shell.npy",
    "report_filename": "volume_boundary_shell_aniso_external_shell.txt",
    "use_shell_for_meshing": $ADDITIVE_VOXEL_SHELL_USE_FOR_MESHING,
    "thickness": $ADDITIVE_VOXEL_SHELL_THICKNESS,
    "thicknesses": {
      "x_min": $ADDITIVE_VOXEL_SHELL_X_MIN,
      "x_max": $ADDITIVE_VOXEL_SHELL_X_MAX,
      "y_min": $ADDITIVE_VOXEL_SHELL_Y_MIN,
      "y_max": $ADDITIVE_VOXEL_SHELL_Y_MAX,
      "z_min": $ADDITIVE_VOXEL_SHELL_Z_MIN,
      "z_max": $ADDITIVE_VOXEL_SHELL_Z_MAX
    }
  },
  "02d_axis_aligned_cuboid_crop": {
    "enabled": $BOUNDARY_SHELL_ENABLED,
    "output_filename": "volume_boundary_shell_aniso.npy",
    "report_filename": "volume_boundary_shell_aniso.txt",
    "use_cuboid_for_meshing": $BOUNDARY_SHELL_ENABLED,
    "crop": {
      "enabled": false,
      "value": $BOUNDARY_SHELL_VALUE,
      "margin": 0
    },
    "boundary_seal": {
      "enabled": $BOUNDARY_SHELL_ENABLED,
      "value": $BOUNDARY_SHELL_VALUE,
      "thickness": $BOUNDARY_SHELL_THICKNESS,
      "thicknesses": {
        "x_min": $BOUNDARY_SHELL_X_MIN,
        "x_max": $BOUNDARY_SHELL_X_MAX,
        "y_min": $BOUNDARY_SHELL_Y_MIN,
        "y_max": $BOUNDARY_SHELL_Y_MAX,
        "z_min": $BOUNDARY_SHELL_Z_MIN,
        "z_max": $BOUNDARY_SHELL_Z_MAX
      }
    }
  },
  "10_snap_mesh_to_crop_boundary": {
    "enabled": $SNAP_MESH_TO_CROP_BOUNDARY_ENABLED,
    "tolerance_fraction": $SNAP_MESH_TO_CROP_BOUNDARY_TOLERANCE_FRACTION,
    "tolerance_absolute": $(json_value_or_null "$SNAP_MESH_TO_CROP_BOUNDARY_TOLERANCE_ABSOLUTE"),
    "volume_tolerance": $SNAP_MESH_TO_CROP_BOUNDARY_VOLUME_TOLERANCE,
    "orient_tets_positive": $SNAP_MESH_TO_CROP_BOUNDARY_ORIENT_TETS_POSITIVE
  },
  "11_mirror_extrude_mesh": {
    "enabled": $MIRROR_EXTRUDE_MESH_ENABLED,
    "axis": "$MIRROR_EXTRUDE_AXIS",
    "plane": "$MIRROR_EXTRUDE_PLANE",
    "merge_tolerance_fraction": $MIRROR_EXTRUDE_MERGE_TOLERANCE_FRACTION,
    "merge_tolerance_absolute": $(json_value_or_null "$MIRROR_EXTRUDE_MERGE_TOLERANCE_ABSOLUTE"),
    "volume_tolerance": $MIRROR_EXTRUDE_VOLUME_TOLERANCE,
    "orient_tets_positive": $MIRROR_EXTRUDE_ORIENT_TETS_POSITIVE
  },
  "fracture": {
    "materials": ["std"],
    "directions": ["y"],
    "mesh_file": "$FRACTURE_MESH_FILE",
    "lam_param": $FRACTURE_LAM_PARAM,
    "mue_param": $FRACTURE_MUE_PARAM,
    "Gc_param": $FRACTURE_GC_PARAM,
    "eps_factor_param": $FRACTURE_EPS_FACTOR_PARAM,
    "element_order": $FRACTURE_ELEMENT_ORDER
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
