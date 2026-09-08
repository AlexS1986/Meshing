#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/create_yield_surface_paraview.py" \
  --input "${1:-$SCRIPT_DIR/00_results}" \
  --output-dir "${2:-$SCRIPT_DIR/00_results/yield_surface_paraview}"
