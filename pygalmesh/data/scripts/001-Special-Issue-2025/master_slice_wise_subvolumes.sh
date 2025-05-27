#!/bin/bash

# -------------------------------
# Resolve script directory
# -------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# -------------------------------
# Configuration (relative paths)
# -------------------------------

CONFIG_PATH="$SCRIPT_DIR/config.json"
BASE_SUBVOLUME_FOLDER="$SCRIPT_DIR/JM-25-24_segmented/JM-25-24_segmented_3D"
VOLUME_FILENAME="volume.npy"

# -------------------------------
# Python scripts to run with config.json
# -------------------------------

SCRIPTS=(
    "00_dicom_2_npy.py"
    "01_segment_slice_wise.py"
    "02_build3D_segmented_array.py"
    "02a_rotate_pic_to_align_with_axis.py"
    "02b_build_subvolume_arrays.py"
)

# -------------------------------
# Run standard scripts with config.json
# -------------------------------

for SCRIPT in "${SCRIPTS[@]}"; do
    echo "🚀 Running $SCRIPT with config: $CONFIG_PATH"
    python3 "$SCRIPT" --config "$CONFIG_PATH"
    if [ $? -ne 0 ]; then
        echo "❌ Error while running $SCRIPT. Exiting..."
        exit 1
    fi
    echo "✅ Finished $SCRIPT"
    echo "----------------------------"
done

# -------------------------------
# Mesh generation + scaling/translation
# -------------------------------

MESH_SCRIPT="$SCRIPT_DIR/03_mesh_3D_array_pygalmesh.py"
SCALE_SCRIPT="$SCRIPT_DIR/04_scale_and_translate_mesh_mod.py"
echo "🌐 Starting mesh generation using $MESH_SCRIPT"

find "$BASE_SUBVOLUME_FOLDER" -type f -name "$VOLUME_FILENAME" | while read -r NPY_FILE; do
    SUBFOLDER=$(dirname "$NPY_FILE")
    FOLDER_NAME=$(basename "$SUBFOLDER")
    MESH_OUTPUT="$SUBFOLDER/mesh.xdmf"

    # Extract center_x and center_y from folder name
    if [[ "$FOLDER_NAME" =~ subvolume_x([0-9]+)_y([0-9]+) ]]; then
        CENTER_X="${BASH_REMATCH[1]}"
        CENTER_Y="${BASH_REMATCH[2]}"
    else
        echo "❌ Could not extract center_x and center_y from folder name: $FOLDER_NAME"
        exit 1
    fi

    echo "🧩 Meshing: $NPY_FILE -> $MESH_OUTPUT"
    python3 "$MESH_SCRIPT" --config "$CONFIG_PATH" --npy "$NPY_FILE" --mesh "$MESH_OUTPUT"
    if [ $? -ne 0 ]; then
        echo "❌ Error during meshing $NPY_FILE. Exiting..."
        exit 1
    fi
    echo "✅ Meshed: $MESH_OUTPUT"

    echo "🎯 Scaling and translating mesh with center_x=$CENTER_X, center_y=$CENTER_Y"
    python3 "$SCALE_SCRIPT" \
        --config "$CONFIG_PATH" \
        --mesh "$MESH_OUTPUT" \
        --center_x "$CENTER_X" \
        --center_y "$CENTER_Y"
    if [ $? -ne 0 ]; then
        echo "❌ Error during scale/translate for $MESH_OUTPUT. Exiting..."
        exit 1
    fi
    echo "✅ Scaled & Translated: $MESH_OUTPUT"
    echo "----------------------------"
done

echo "🎉 All scripts, meshing, and mesh transformations completed successfully."






