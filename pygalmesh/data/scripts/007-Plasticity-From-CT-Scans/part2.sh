#!/bin/bash

CONFIGS_BASE_DIR="/data/scripts/001-Special-Issue-2025/JM-25-26_segmented"

REMAINING_SCRIPTS=(
    "02_build3D_segmented_array.py"
    "03_mesh_3D_array_pygalmesh.py"
    "04_scale_and_translate_mesh.py"  # Added as the final step
)

CONFIG_FILES=$(find "$CONFIGS_BASE_DIR" -type f -name "config.json" | sort)

if [[ -z "$CONFIG_FILES" ]]; then
    echo "❌ No config.json files found."
    exit 1
fi

CONFIG_ARRAY=($CONFIG_FILES)

for CONFIG_PATH in "${CONFIG_ARRAY[@]}"; do
    echo "=========================================="
    echo "📄 Processing config: $CONFIG_PATH"
    echo "=========================================="

    for SCRIPT in "${REMAINING_SCRIPTS[@]}"; do
        echo "🚀 Running $SCRIPT ..."
        python3 "$SCRIPT" --config "$CONFIG_PATH"
        if [ $? -ne 0 ]; then
            echo "❌ Error: $SCRIPT failed for config: $CONFIG_PATH"
            exit 1
        fi
        echo "✅ Finished $SCRIPT"
        echo "----------------------------"
    done

    echo "✔️ Completed all steps for: $CONFIG_PATH"
    echo ""
done

echo "🎉 All config files processed successfully."













