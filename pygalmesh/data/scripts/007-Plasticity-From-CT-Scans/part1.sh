#!/bin/bash

CONFIGS_BASE_DIR="/data/scripts/001-Special-Issue-2025/JM-25-26_segmented"
SCRIPT_DIR="$(dirname "$(realpath "$0")")"

DICOM_SCRIPT="00_dicom_2_npy.py"
SEGMENT_SCRIPT="01_segment_slice_wise.py"

CREATE_CONFIG_SCRIPT="$SCRIPT_DIR/create_config_multiple.sh"

echo "Running: $CREATE_CONFIG_SCRIPT"
bash "$CREATE_CONFIG_SCRIPT"
if [ $? -ne 0 ]; then
    echo "Error: create_config_multiple.sh failed"
    exit 1
fi
echo "Finished: $CREATE_CONFIG_SCRIPT"

CONFIG_FILES=$(find "$CONFIGS_BASE_DIR" -type f -name "config.json" | sort)

if [[ -z "$CONFIG_FILES" ]]; then
    echo "No config.json files found after running $CREATE_CONFIG_SCRIPT"
    exit 1
fi

CONFIG_ARRAY=($CONFIG_FILES)
FIRST_CONFIG="${CONFIG_ARRAY[0]}"
FIRST_CONFIG_DIR="$(dirname "$FIRST_CONFIG")"
FIRST_METADATA="$FIRST_CONFIG_DIR/metadata.json"

echo "Running $DICOM_SCRIPT on first config: $FIRST_CONFIG"
python3 "$DICOM_SCRIPT" --config "$FIRST_CONFIG"
if [ $? -ne 0 ]; then
    echo "Error: $DICOM_SCRIPT failed"
    exit 1
fi
echo "Finished $DICOM_SCRIPT"

echo "Running $SEGMENT_SCRIPT on first config: $FIRST_CONFIG"
python3 "$SEGMENT_SCRIPT" --config "$FIRST_CONFIG"
if [ $? -ne 0 ]; then
    echo "Error: $SEGMENT_SCRIPT failed"
    exit 1
fi
echo "Finished $SEGMENT_SCRIPT"

if [ ! -f "$FIRST_METADATA" ]; then
    echo "Error: metadata.json not found in first config directory: $FIRST_METADATA"
    exit 1
fi

echo "Copying metadata.json from $FIRST_METADATA to all config folders..."
for CONFIG_PATH in "${CONFIG_ARRAY[@]}"; do
    CONFIG_DIR="$(dirname "$CONFIG_PATH")"
    METADATA_DEST="$CONFIG_DIR/metadata.json"
    cp "$FIRST_METADATA" "$METADATA_DEST"
    echo "Copied metadata.json to $CONFIG_DIR"
done












