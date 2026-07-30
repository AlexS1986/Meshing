#!/bin/bash
# Step 3: Mesh the tessellation for FEM (run inside the Docker container).
# RCL controls the relative element size (smaller = finer). RCL=0.75 gives
# a reasonable resolution per grain for crystal-plasticity-type FEM.
#
# Material selection:   MAT=316L (default) | 17-4PH
set -e
cd "$(dirname "$0")"

MAT=${MAT:-316L}
PJSON="params_${MAT}.json"
[ -f "$PJSON" ] || { echo "missing $PJSON - run step 1/2 for $MAT first"; exit 1; }

N=$(python3 -c "import json;print(json.load(open('$PJSON'))['n_grains'])")
RCL=${RCL:-0.75}
ORDER=${ORDER:-1}     # 1 = linear tets (fine for FEniCSx), 2 = quadratic
OUT="waam_${MAT}_n${N}"

echo ">> [$MAT] meshing $OUT.tess  (rcl=$RCL, order=$ORDER)"
neper -M "$OUT.tess" \
      -rcl "$RCL" \
      -order "$ORDER" \
      -format msh \
      -statelt vol \
      -o "$OUT"

echo ">> [$MAT] done: $OUT.msh"
