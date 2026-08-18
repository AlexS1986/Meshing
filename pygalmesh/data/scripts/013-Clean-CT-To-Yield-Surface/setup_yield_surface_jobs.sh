#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/config.sh"
POINTS="${1:-${YIELD_SURFACE_POINTS:-6}}"
RADIUS="${YIELD_SURFACE_STRAIN_RADIUS:-0.25}"
BASE_CONFIG="${YIELD_SURFACE_BASE_CONFIG:-config.json}"
SETUP_ARGS=(
  --points "$POINTS"
  --radius "$RADIUS"
  --base-config "$BASE_CONFIG"
)
if [[ -n "${YIELD_SURFACE_OUTPUT_DIR:-}" ]]; then
  SETUP_ARGS+=(--output-dir "$YIELD_SURFACE_OUTPUT_DIR")
fi
python3 "$SCRIPT_DIR/setup_yield_surface_jobs.py" "${SETUP_ARGS[@]}"
