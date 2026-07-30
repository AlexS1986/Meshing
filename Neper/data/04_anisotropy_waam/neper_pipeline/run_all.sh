#!/bin/bash
# Run the whole pipeline INSIDE the Docker container (Neper + Gmsh image)
# for BOTH steels (316L, 17-4PH) and build the combined V specimen.
#
# From the Neper folder on the host:
#   docker compose up -d --build
#   docker compose exec ubuntu_custom bash /data/04_anisotropy_waam/neper_pipeline/run_all.sh
#
# Options (env):
#   MATERIALS="316L 17-4PH"   which RVEs to build (default both)
#   COMBINED=1                also build spec_combined_V (default 1)
#   SPECIMENS=0               also build the V/H/45deg tensile bars per steel
#                             (step 7, optional, default 0)
#   FAST=1                    quick Voronoi tessellations (seconds, for testing)
#
# Note: step 4 needs meshio+h5py (installed below via pip, needs internet in the
# container; alternatively add them to the Dockerfile).
set -e
cd "$(dirname "$0")"

pip3 install --quiet meshio h5py numpy pandas matplotlib 2>/dev/null || true

MATERIALS="${MATERIALS:-316L 17-4PH}"
COMBINED="${COMBINED:-1}"
SPECIMENS="${SPECIMENS:-0}"

for MAT in $MATERIALS; do
  echo ""
  echo "############################################################"
  echo "#  RVE pipeline: $MAT"
  echo "############################################################"
  python3 01_fit_ebsd.py --material "$MAT"     # fit EBSD -> params_$MAT.json, n200_$MAT.ori
  MAT="$MAT" bash 02_generate_tess.sh          # Neper tessellation (-> .tess, .stcell, grain_ori_$MAT.txt)
  MAT="$MAT" bash 03_mesh.sh                    # Neper meshing      (-> waam_${MAT}_n200.msh)
  N=$(python3 -c "import json;print(json.load(open('params_'+'$MAT'+'.json'))['n_grains'])")
  python3 04_convert_to_xdmf.py "waam_${MAT}_n${N}.msh"   # msh -> XDMF for FEniCSx
  python3 05_verify_stats.py "$MAT"             # statistics check vs. EBSD targets

  if [ "$SPECIMENS" = "1" ]; then
    echo "--- optional: V/H/45deg tensile bars ($MAT) ---"
    MAT="$MAT" python3 07_tensile_specimens.py  # -> spec_${MAT}_V/H/45deg.xdmf + grain_ori_${MAT}_*.txt
  fi
done

if [ "$COMBINED" = "1" ]; then
  echo ""
  echo "############################################################"
  echo "#  Combined V specimen (316L / transition / 17-4PH)"
  echo "############################################################"
  # needs the fitted params of all three regions:
  python3 01_fit_ebsd.py --material trans
  # (316L and 17-4PH params were written above; if MATERIALS was narrowed,
  #  make sure both exist)
  [ -f params_316L.json ]   || python3 01_fit_ebsd.py --material 316L
  [ -f params_17-4PH.json ] || python3 01_fit_ebsd.py --material 17-4PH
  python3 08_combined_specimen.py
fi

echo ""
echo "=== done ==="
for MAT in $MATERIALS; do
  N=$(python3 -c "import json;print(json.load(open('params_'+'$MAT'+'.json'))['n_grains'])")
  echo "  $MAT  RVE:      waam_${MAT}_n${N}.xdmf/.h5  +  grain_ori_${MAT}.txt"
done
[ "$COMBINED" = "1" ] && echo "  combined V:        spec_combined_V.xdmf/.h5  +  spec_combined_V_grain_ori.txt"
echo "  FEniCSx loader:    06_fenicsx_example.py"
