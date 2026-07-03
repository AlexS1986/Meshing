#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/config.sh"
POINTS="${1:-${YIELD_SURFACE_POINTS:-6}}"
RADIUS="${YIELD_SURFACE_STRAIN_RADIUS:-0.25}"
python3 "$SCRIPT_DIR/setup_yield_surface_jobs.py" --points "$POINTS" --radius "$RADIUS"
