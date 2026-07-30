#!/bin/bash
# Full WAAM microstructure mesh pipeline, start to end (Neper/Gmsh container).
# Produces every mesh the dolfinx computations need:
#   * homogenization RVE cube per steel   (waam_<MAT>_n<N>.xdmf/.h5 + grain_ori_<MAT>.txt)
#   * directional tensile bars V/H/45deg   (spec_<MAT>_<orient>.xdmf/.h5 + grain_ori_<MAT>_<orient>.txt)
#   * combined V bar 316L/transition/17-4PH (spec_combined_V.xdmf/.h5 + spec_combined_V_grain_ori.txt)
#
# From the Neper folder on the host:
#   docker compose up -d --build
#   docker compose exec ubuntu_custom bash /data/04_anisotropy_waam/neper_pipeline/run_pipeline.sh
# (or run directly inside the container in this folder: bash run_pipeline.sh)
#
# Env:
#   MATERIALS="316L 17-4PH"   steels to process (default both)
#   N=300  RCL=0.5            homogenization RVE grain count / mesh size
#   CLEAN=1                   remove all generated files first (clean start)
#   SPECIMENS=0              skip the V/H/45deg bars (default 1 = build them)
#   COMBINED=0               skip the combined bar (default 1 = build it)
#   FAST=1                   quick Voronoi tessellations (seconds; for testing)
set -e
cd "$(dirname "$0")"

MATERIALS="${MATERIALS:-316L 17-4PH}"
N="${N:-300}"
RCL="${RCL:-0.5}"
SPECIMENS="${SPECIMENS:-1}"
COMBINED="${COMBINED:-1}"

pip3 install --quiet meshio h5py numpy pandas matplotlib 2>/dev/null || true

if [ "${CLEAN:-0}" = "1" ]; then
    echo "### cleaning generated files ###"
    bash clean_generated.sh
fi

# ---- 1) homogenization RVE cubes (finer + more grains) ---------------------
for MAT in $MATERIALS; do
    MAT="$MAT" N="$N" RCL="$RCL" bash 09_homogenization_rve.sh
done

# ---- 2) directional tensile bars (V / H / 45deg) ---------------------------
if [ "$SPECIMENS" = "1" ]; then
    for MAT in $MATERIALS; do
        echo "### directional bars: $MAT ###"
        MAT="$MAT" python3 07_tensile_specimens.py
    done
fi

# ---- 3) combined V bar (316L / transition / 17-4PH) ------------------------
if [ "$COMBINED" = "1" ]; then
    echo "### combined V bar ###"
    python3 01_fit_ebsd.py --material trans
    [ -f params_316L.json ]   || python3 01_fit_ebsd.py --material 316L
    [ -f params_17-4PH.json ] || python3 01_fit_ebsd.py --material 17-4PH
    python3 08_combined_specimen.py
fi

echo ""
echo "==================== pipeline done ===================="
for MAT in $MATERIALS; do
    echo "  RVE       : waam_${MAT}_n${N}.xdmf/.h5   + grain_ori_${MAT}.txt"
    [ "$SPECIMENS" = "1" ] && echo "  bars      : spec_${MAT}_V/H/45deg.xdmf/.h5 + grain_ori_${MAT}_<orient>.txt"
done
[ "$COMBINED" = "1" ] && echo "  combined  : spec_combined_V.xdmf/.h5 + spec_combined_V_grain_ori.txt"
echo ""
echo "Next (host): stage into the dolfinx homogenization project"
echo "  cd .../dolfinx_alex/shared/scripts/069-waam-polycrystal-anisotropy"
echo "  python3 prepare_inputs.py --rve $MATERIALS --n $N"
echo "  python3 prepare_inputs.py --specimens $MATERIALS"
echo "then run homogenize_rve.py / uniaxial_tension.py in the dolfinx container."
