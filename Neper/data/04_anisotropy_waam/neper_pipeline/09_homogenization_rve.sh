#!/bin/bash
# Step 9: Generate a per-material RVE cube for elastic homogenization.
#
# Higher grain count + finer mesh than the default RVE, so the effective
# stiffness tensor is well resolved. Runs the standard pipeline (01->02->03->04)
# with N grains and mesh size RCL, producing:
#     waam_<MAT>_n<N>.xdmf / .h5    (mesh + "grain" cell tag)
#     grain_ori_<MAT>.txt           (grain_id phi1 Phi phi2 crystal)
# which are the inputs of the dolfinx homogenization
# (dolfinx_alex/shared/scripts/069-waam-polycrystal-anisotropy).
#
# Run inside the Neper/Gmsh container:
#     MAT=316L   bash 09_homogenization_rve.sh
#     MAT=17-4PH bash 09_homogenization_rve.sh
#
# Env: MAT (default 316L), N (default 300), RCL (default 0.5), FAST=1 (quick test).
set -e
cd "$(dirname "$0")"

MAT=${MAT:-316L}
# N: grain count. Higher = better statistics + smaller KUBC boundary effect (the
# orthotropic 316L RVE is an elongated box). N=500 -> ~8 grains/direction. This
# is the main runtime knob; drop to 300 for faster, raise for smoother tensors.
N=${N:-500}
# RCL: relative element size. 0.6 (slightly coarser than 0.5) meshes the flat
# orthotropic grains robustly and keeps element counts / solve time reasonable.
RCL=${RCL:-0.6}

echo "############################################################"
echo "#  Homogenization RVE: $MAT   (n=$N grains, rcl=$RCL)"
echo "############################################################"

pip3 install --quiet meshio h5py numpy pandas matplotlib 2>/dev/null || true

python3 01_fit_ebsd.py --material "$MAT" --n "$N"     # params_<MAT>.json, n<N>_<MAT>.ori/.meta
MAT="$MAT" bash 02_generate_tess.sh                   # waam_<MAT>_n<N>.tess + grain_ori_<MAT>.txt
MAT="$MAT" RCL="$RCL" bash 03_mesh.sh                 # waam_<MAT>_n<N>.msh   (finer mesh)
python3 04_convert_to_xdmf.py "waam_${MAT}_n${N}.msh" # -> waam_<MAT>_n<N>.xdmf/.h5

echo ""
echo "=== done: homogenization RVE for $MAT ==="
echo "  mesh : waam_${MAT}_n${N}.xdmf / .h5"
echo "  ori  : grain_ori_${MAT}.txt"
echo ""
echo "Next (host): copy these into the dolfinx homogenization folder, e.g."
echo "  dolfinx_alex/shared/scripts/069-waam-polycrystal-anisotropy/inputs/"
echo "then run prepare_inputs.py + homogenize_rve.py inside the dolfinx container."
