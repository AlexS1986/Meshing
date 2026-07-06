#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="${SCRIPT_DIR:-$HPC_SCRATCH/pygalmesh/data/scripts/010-Yield-Surface-Generation}"
PROJECT_DIR="${PROJECT_DIR:-$SCRIPT_DIR}"
OUTPUT_DIR="${OUTPUT_DIR:-$PROJECT_DIR/00_results/downloads}"

mkdir -p "$OUTPUT_DIR"

python3 "$SCRIPT_DIR/package_yield_run_jsons.py" \
  --project-dir "$PROJECT_DIR" \
  --material std \
  --direction tensor \
  --output "$OUTPUT_DIR/yield_run_std_tensor_jsons.zip"

echo
echo "Zip ready:"
echo "$OUTPUT_DIR/yield_run_std_tensor_jsons.zip"
