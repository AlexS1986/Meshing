#!/usr/bin/env bash
# Build the yield surface (point cloud + convex-hull VTKs) for the n192
# sampling study only.
#
# 00_results/n192/yield_run_std_tensor_jsons/ contains 240 JSON files:
# 192 in the current n192 naming scheme, plus 48 leftover files from the
# older 48-point study that were copied in with colliding ys_000-ys_047
# indices (recognizable by "-std-tensor__target" right after the last eps
# value). This wrapper excludes those 48 old-scheme files so only the
# genuine 192-point sampling is used.
#
# Usage:
#   ./create_yield_surface_n192.sh
#
# Output:
#   00_results/n192/yield_surface_paraview/
#     yield_surface_points.csv
#     yield_surface_strain.vtk
#     yield_surface_stress_normal.vtk
#     yield_surface_stress_principal.vtk

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 "$SCRIPT_DIR/create_yield_surface_paraview.py" \
  --input "$SCRIPT_DIR/00_results/n192/yield_run_std_tensor_jsons" \
  --output-dir "$SCRIPT_DIR/00_results/n192/yield_surface_paraview" \
  --exclude-substring="-std-tensor__target"
