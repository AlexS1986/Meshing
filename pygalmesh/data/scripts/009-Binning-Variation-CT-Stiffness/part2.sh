#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Define the one config used by this part here, or pass it as the first argument.
CONFIG_PATH="${1:-$SCRIPT_DIR/config-Bin2.json}"

if [ ! -f "$CONFIG_PATH" ]; then
  echo "Config not found: $CONFIG_PATH"
  echo "Create one with: ./create_config.sh <binning_id>"
  exit 1
fi

python3 "$SCRIPT_DIR/02_build3D_segmented_array.py" --config "$CONFIG_PATH"
python3 "$SCRIPT_DIR/02a_rotate_pic_to_align_with_axis.py" --config "$CONFIG_PATH"
python3 "$SCRIPT_DIR/02b_build_subvolume_arrays.py" --config "$CONFIG_PATH"
