#!/bin/bash
# Step 2: Generate the 3D tessellation with Neper (run inside the Docker container).
#
# Strategy: generate an ~equiaxed tessellation with the fitted (relative)
# diameq distribution in a cube, then stretch it along z (build direction)
# by the fitted elongation factor -> columnar grains.
# Parameters come from params_<MAT>.json (written by 01_fit_ebsd.py).
#
# Material selection:   MAT=316L (default) | 17-4PH   e.g.
#   MAT=17-4PH bash 02_generate_tess.sh
set -e
cd "$(dirname "$0")"

MAT=${MAT:-316L}
PJSON="params_${MAT}.json"
[ -f "$PJSON" ] || { echo "missing $PJSON - run: python3 01_fit_ebsd.py --material $MAT"; exit 1; }

N=$(python3 -c "import json;print(json.load(open('$PJSON'))['n_grains'])")
L=$(python3 -c "import json;print(json.load(open('$PJSON'))['neper']['domain_cube_um'])")
MORPHO=$(python3 -c "import json;print(json.load(open('$PJSON'))['neper']['morpho'])")
SCALE=$(python3 -c "import json;print(json.load(open('$PJSON'))['neper']['transform'])")
ORI=$(python3 -c "import json;print(json.load(open('$PJSON'))['neper']['ori_file'])")
OUT="waam_${MAT}_n${N}"

echo ">> [$MAT] Neper tessellation: n=$N, cube($L um), $MORPHO, $SCALE"

# NOTE: the -morpho objective plateaus around f~0.006-0.008 for this config, so a
# strict target (e.g. val=5e-3) never terminates. Default stops at f<1e-2 (already
# reached quickly) OR after itermax. For a quick first test: FAST=1 (voronoi).
neper -T -n "$N" \
      -domain "cube($L,$L,$L)" \
      -morpho "$MORPHO" \
      -morphooptistop "${MORPHOSTOP:-val=1e-2||itermax=30000}" \
      -ori "file($ORI,des=euler-bunge)" \
      -oridescriptor euler-bunge \
      -transform "$SCALE" \
      -statcell "id,vol,diameq,sphericity,x,y,z" \
      -o "$OUT" \
      -format tess,ori

# per-grain orientation table for FEniCSx: "grain_id phi1 Phi phi2 crystal"
# (from $OUT.ori written by -format tess,ori; line i = cell i). The crystal
# system per grain is carried over from n<N>_<MAT>.meta (same sampling order).
MAT="$MAT" N="$N" OUT="$OUT" python3 - << 'EOF'
import json, os
mat = os.environ['MAT']; n = int(os.environ['N']); out = os.environ['OUT']
lines = [l.split() for l in open(f'{out}.ori')
         if l.strip() and not l.startswith(('#', '$'))]
assert len(lines) == n, f"expected {n} orientations, got {len(lines)}"
meta_path = f'n{n}_{mat}.meta'
crystals = ([l.strip() for l in open(meta_path) if l.strip() and not l.startswith('#')]
            if os.path.exists(meta_path) else ['unknown'] * n)
with open(f'grain_ori_{mat}.txt', 'w') as f:
    f.write(f"# material={mat}\n# grain_id phi1 Phi phi2 (Bunge, deg) crystal\n")
    for i, r in enumerate(lines):
        f.write(f"{i+1} {r[-3]} {r[-2]} {r[-1]} {crystals[i]}\n")
print(f"wrote grain_ori_{mat}.txt")
EOF

# optional: PNG visualization (needs povray, already in the image)
neper -V "$OUT.tess" -datacellcol ori -print "${OUT}_tess" || true

echo ">> [$MAT] done: $OUT.tess"
