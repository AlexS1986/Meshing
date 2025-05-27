#!/bin/bash

# --------- User-defined Parameters ---------

SPECIMEN_NAME="JM-25-26"
BASE_PATH="/data/scripts/001-Special-Issue-2025"
DICOM_FOLDER="/data/resources/special_issue_hannover/raw_dicom/JM-25-26-245min_750^C"

# Original image dimensions (before downsampling)
IMAGE_X=2784
IMAGE_Y=2964

# Size of the rectangular area to tile (in original resolution)
AREA_X=1600
AREA_Y=1600

# Size of each square subregion (in original resolution)
SQUARE_EDGE=400

# Reduce factor (must be integer)
REDUCE_FACTOR=4

# Z-range (in voxels, unchanged by reduce factor)
MIN_Z=100
MAX_Z=190

# --------- Derived Paths ---------
OUTPUT_BASE="$BASE_PATH/${SPECIMEN_NAME}_segmented"
NPY_OUTPUT_FOLDER="$BASE_PATH/${SPECIMEN_NAME}/npy"

# --------- Reduced Dimensions ---------
IMAGE_X_REDUCED=$(( IMAGE_X / REDUCE_FACTOR ))
IMAGE_Y_REDUCED=$(( IMAGE_Y / REDUCE_FACTOR ))
AREA_X_REDUCED=$(( AREA_X / REDUCE_FACTOR ))
AREA_Y_REDUCED=$(( AREA_Y / REDUCE_FACTOR ))
SQUARE_EDGE_REDUCED=$(( SQUARE_EDGE / REDUCE_FACTOR ))

# Compute top-left origin of the reduced AREA centered in the reduced image
X_ORIGIN=$(( (IMAGE_X_REDUCED - AREA_X_REDUCED) / 2 ))
Y_ORIGIN=$(( (IMAGE_Y_REDUCED - AREA_Y_REDUCED) / 2 ))

# Number of tiles in x and y direction
NUM_X=$(( AREA_X_REDUCED / SQUARE_EDGE_REDUCED ))
NUM_Y=$(( AREA_Y_REDUCED / SQUARE_EDGE_REDUCED ))

echo "Generating $((NUM_X * NUM_Y)) config files"
echo "Grid origin in reduced image: ($X_ORIGIN, $Y_ORIGIN), tiling $NUM_X x $NUM_Y squares"

# --------- Loop Over Grid ---------
for ((ix=0; ix<NUM_X; ix++)); do
  for ((iy=0; iy<NUM_Y; iy++)); do

    # Compute center of current square
    CENTER_X=$(( X_ORIGIN + ix * SQUARE_EDGE_REDUCED + SQUARE_EDGE_REDUCED / 2 ))
    CENTER_Y=$(( Y_ORIGIN + iy * SQUARE_EDGE_REDUCED + SQUARE_EDGE_REDUCED / 2 ))

    # Set unique folder and file paths
    SUBFOLDER="center_x_${CENTER_X}_center_y_${CENTER_Y}"
    SUBFOLDER_PATH="$OUTPUT_BASE/$SUBFOLDER"
    SEGMENTED_3D_OUTPUT="$SUBFOLDER_PATH/${SPECIMEN_NAME}_segmented_3D"
    MESH_OUTPUT_PATH="$SUBFOLDER_PATH/mesh_output.xdmf"
    CONFIG_PATH="$SUBFOLDER_PATH/config.json"
    METADATA_PATH="$SUBFOLDER_PATH/metadata.json"

    mkdir -p "$SUBFOLDER_PATH"

    # --------- Write JSON ---------
    cat <<EOF > "$CONFIG_PATH"
{
  "metadata_output_path": "$METADATA_PATH",
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
      "factor": $REDUCE_FACTOR
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
    "desired_width_x": $SQUARE_EDGE_REDUCED,
    "desired_width_y": $SQUARE_EDGE_REDUCED,
    "center_x": $CENTER_X,
    "center_y": $CENTER_Y,
    "min_z": $MIN_Z,
    "max_z": $MAX_Z
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
  }
}
EOF

    echo "Wrote config: $CONFIG_PATH"
  done
done

echo "✅ All config files written to: $OUTPUT_BASE"












