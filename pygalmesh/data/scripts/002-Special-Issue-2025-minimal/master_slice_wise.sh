#!/bin/bash

# Shared config file path
CONFIG_PATH="/data/scripts/001-Special-Issue-2025/config.json"

# List of Python scripts to execute
SCRIPTS=(
    #  "00_dicom_2_npy.py"
    #  "01_segment_slice_wise.py"
    #  "02_build3D_segmented_array.py"
    #  "02a_rotate_pic_to_align_with_axis.py"
    "02b_build_subvolume_arrays.py"
    #  "03_mesh_3D_array_pygalmesh.py"
)

# Run each script with the shared config
for SCRIPT in "${SCRIPTS[@]}"; do
    echo "🚀 Running $SCRIPT with config: $CONFIG_PATH"
    python3 "$SCRIPT" --config "$CONFIG_PATH"

    # Exit if a script fails
    if [ $? -ne 0 ]; then
        echo "❌ Error while running $SCRIPT. Exiting..."
        exit 1
    fi

    echo "✅ Finished $SCRIPT"
    echo "----------------------------"
done

echo "🎉 All scripts completed successfully."


