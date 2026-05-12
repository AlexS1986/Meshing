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

python3 "$SCRIPT_DIR/00_dicom_2_npy.py" --config "$CONFIG_PATH"
python3 "$SCRIPT_DIR/01_segment_slice_wise.py" --config "$CONFIG_PATH"
