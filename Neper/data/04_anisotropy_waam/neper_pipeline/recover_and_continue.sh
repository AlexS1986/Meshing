#!/bin/bash
# Recovery: reuse a FINISHED waam_<MAT>_n<N>.tess (do NOT re-run the morpho
# optimization), re-emit .ori + grain_ori_<MAT>.txt, then continue 03 -> 04 -> 05.
#
# Usage:   MAT=316L bash recover_and_continue.sh      (default MAT=316L)
set -e
cd "$(dirname "$0")"

MAT=${MAT:-316L}
PJSON="params_${MAT}.json"
[ -f "$PJSON" ] || { echo "missing $PJSON - run step 1 for $MAT first"; exit 1; }
N=$(python3 -c "import json;print(json.load(open('$PJSON'))['n_grains'])")
OUT="waam_${MAT}_n${N}"
[ -f "$OUT.tess" ] || { echo "missing $OUT.tess - nothing to recover"; exit 1; }

echo ">> [$MAT] recovering from $OUT.tess (no re-optimization)"
neper -T -loadtess "$OUT.tess" \
      -statcell "id,vol,diameq,sphericity,x,y,z" \
      -o "$OUT" -format ori

MAT="$MAT" N="$N" OUT="$OUT" python3 - << 'EOF'
import os
mat = os.environ['MAT']; n = int(os.environ['N']); out = os.environ['OUT']
lines = [l.split() for l in open(f"{out}.ori")
         if l.strip() and not l.startswith(("#", "$"))]
assert len(lines) == n, f"expected {n} orientations, got {len(lines)}"
meta = f"n{n}_{mat}.meta"
crystals = ([l.strip() for l in open(meta) if l.strip() and not l.startswith('#')]
            if os.path.exists(meta) else ['unknown'] * n)
with open(f"grain_ori_{mat}.txt", "w") as f:
    f.write(f"# material={mat}\n# grain_id phi1 Phi phi2 (Bunge, deg) crystal\n")
    for i, r in enumerate(lines):
        f.write(f"{i+1} {r[-3]} {r[-2]} {r[-1]} {crystals[i]}\n")
print(f"grain_ori_{mat}.txt ok")
EOF

pip3 install --quiet meshio h5py 2>/dev/null || true
MAT="$MAT" bash 03_mesh.sh
python3 04_convert_to_xdmf.py "$OUT.msh"
python3 05_verify_stats.py "$MAT"
echo "=== done: $OUT.xdmf/.h5 + grain_ori_${MAT}.txt ==="
