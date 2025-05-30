#!/bin/bash

# --------- User-defined Parameters ---------

# Set specimen name only once
SPECIMEN_NAME="JM-25-24"

# Base folder for scripts and data
BASE_PATH="."

# Full output path for the config.json
CONFIG_PATH="$BASE_PATH/config.json"

# Output path base used across JSON
OUTPUT_BASE="$BASE_PATH/${SPECIMEN_NAME}_segmented"

# Path to the raw DICOM folder
DICOM_FOLDER="/data/resources/special_issue_hannover/raw_dicom/${SPECIMEN_NAME}/${SPECIMEN_NAME}-245min_750^C_erodiert"

# Optional: different dataset path
# DICOM_FOLDER="/data/resources/special_issue_hannover/raw_dicom/JM-25-26-245min_750^C"

# 3D subvolume parameters — set to number or leave empty to make it null in JSON
# DESIRED_WIDTH_X=100
# DESIRED_HEIGHT_Y=100
# CENTER_X=512
# CENTER_Y=512
MIN_Z=80
MAX_Z=185

# MIN_Z=90
# MAX_Z=220

# ❌ Subvolume block size is no longer used — replaced with xy_divisions
# BLOCK_EDGE_VOXELS=320

# ✅ Instead, define how many equal subdivisions you want in x and y
XY_DIVISIONS=1

# --------- Derived Paths ---------
NPY_OUTPUT_FOLDER="$BASE_PATH/${SPECIMEN_NAME}/npy"
SEGMENTED_3D_OUTPUT="$OUTPUT_BASE/${SPECIMEN_NAME}_segmented_3D"
MESH_OUTPUT_PATH="$OUTPUT_BASE/mesh.xdmf"

# --------- Function to handle null or value ---------
json_value_or_null() {
  local var="$1"
  if [[ -z "$var" ]]; then
    echo "null"
  else
    echo "$var"
  fi
}

# --------- Write JSON to File ---------
cat <<EOF > "$CONFIG_PATH"
{
  "metadata_output_path": "$OUTPUT_BASE/metadata.json",
  "dicom2npy": {
    "foldername": "$DICOM_FOLDER",
    "option": "reduce",
    "crop": {
      "x_start": 1000,
      "x_end": 1150,
      "y_start": 1000,
      "y_end": 1150
    },
    "reduce": {
      "factor": 4
    },
    "slice_start": 0,
    "slice_end": null,
    "output_folder": "$NPY_OUTPUT_FOLDER"
  },
  "01_segment_slice_wise": {
    "specimen_name": "$SPECIMEN_NAME",
    "input_folder": "$NPY_OUTPUT_FOLDER",
    "output_folder": "$OUTPUT_BASE",
    "preview_slice_index": 100,
    "seg_algorithm": "otsu",
    "gaussian_filter_sigma_factor": 5
  },
  "02_segmented_3D_array": {
    "input_folder": "$OUTPUT_BASE",
    "output_folder": "$SEGMENTED_3D_OUTPUT",
    "desired_width_x": $(json_value_or_null "$DESIRED_WIDTH_X"),
    "desired_height_y": $(json_value_or_null "$DESIRED_HEIGHT_Y"),
    "center_x": $(json_value_or_null "$CENTER_X"),
    "center_y": $(json_value_or_null "$CENTER_Y"),
    "min_z": $(json_value_or_null "$MIN_Z"),
    "max_z": $(json_value_or_null "$MAX_Z")
  },
  "03_mesh_3D_array": {
    "specimen_name": "${SPECIMEN_NAME}_segmented",
    "input_folder": "$SEGMENTED_3D_OUTPUT",
    "smoothing_sigma_factor": 5,
    "segmentation_algorithm": "otsu",
    "z_slice": 0,
    "scale_factor": 1.0,
    "meshing_method": "pygalmesh",
    "mesh_output_path": "$MESH_OUTPUT_PATH",
    "pygalmesh_parameters": {
      "max_element_size_factor": 5.0,
      "max_facet_distance_factor": 0.3
    },
    "nanomesh_parameters": {
      "meshing_options": "-pAqD",
      "output_format": "gmsh22",
      "output_binary": false
    }
  },
  "02a_rotate_pic_to_align_with_axis": {
    "material_value": 1,
    "pore_value": 0,
    "buffer_width": 15,
    "buffer_width_min_x": 75,
    "buffer_width_max_x": 15,
    "buffer_width_min_y": 15,
    "buffer_width_max_y": 15,
    "buffer_width_min_z": 15,
    "buffer_width_max_z": 15,
    "angles": [-12.9, 4, 2.5]
  },
  "02b_build_subvolume_arrays": {
    "xy_divisions": $(json_value_or_null "$XY_DIVISIONS"),
    "subvolume_output_folder": "$SEGMENTED_3D_OUTPUT"
  }
}
EOF

echo "✅ Config file successfully written to: $CONFIG_PATH"








