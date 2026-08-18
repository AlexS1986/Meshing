#!/usr/bin/env bash
# Erzeugt die Config der .leS-Pipeline (Default: config-A01-les.json) aus den
# LES_*-Variablen in config.sh. Zusaetzliche Argumente werden durchgereicht,
# z.B.:  ./create_les_config.sh --reduce 4 --output config-A01-les-r4.json
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/config.sh"

ARGS=(
  --base-config "${LES_BASE_CONFIG:-config-Bin4-reduce-2.json}"
  --output "${LES_CONFIG_FILENAME:-config-A01-les.json}"
  --dataset-id "${LES_DATASET_ID:-JM-25-77_A01_les}"
  --les-input "${LES_INPUT:-/data/resources/A01_segmented}"
  --reduce "${LES_REDUCE_FACTOR:-2}"
  --reduce-mode "${LES_REDUCE_MODE:-majority}"
  --reduce-threshold "${LES_REDUCE_THRESHOLD:-0.5}"
  --smooth-sigma "${LES_SMOOTH_SIGMA:-0.0}"
  --line-order "${LES_LINE_ORDER:-C}"
  --les-material-value "${LES_MATERIAL_VALUE:-1}"
  --bounds-mode "${LES_BOUNDS_MODE:-full}"
  --voxel-size-unit "${LES_VOXEL_SIZE_UNIT:-mm}"
  --xy-divisions "${LES_XY_DIVISIONS:-1}"
  --sdf-pad-width "${LES_SDF_PAD_WIDTH:-3}"
  --mesh-size-scale "${LES_MESH_SIZE_SCALE:-1.0}"
  --boundary-shell-xz "${LES_BOUNDARY_SHELL_XZ:-8}"
  --boundary-shell-y "${LES_BOUNDARY_SHELL_Y:-12}"
)

if [[ -n "${LES_MAX_ELEMENT_SIZE_UM:-}" ]]; then
  ARGS+=(--max-element-size-um "$LES_MAX_ELEMENT_SIZE_UM")
fi

if [[ -n "${LES_CURRENT_TETS:-}" && -n "${LES_TARGET_TETS:-}" ]]; then
  ARGS+=(--current-tets "$LES_CURRENT_TETS" --target-tets "$LES_TARGET_TETS")
fi

if [[ "${LES_KEEP_LARGEST_COMPONENT:-false}" == "true" ]]; then ARGS+=(--keep-largest-component); fi

if [[ -n "${LES_X_RANGE:-}" ]]; then ARGS+=(--x-range ${LES_X_RANGE}); fi
if [[ -n "${LES_Y_RANGE:-}" ]]; then ARGS+=(--y-range ${LES_Y_RANGE}); fi
if [[ -n "${LES_Z_RANGE:-}" ]]; then ARGS+=(--z-range ${LES_Z_RANGE}); fi

python3 "$SCRIPT_DIR/create_les_dataset_config.py" "${ARGS[@]}" "$@"
