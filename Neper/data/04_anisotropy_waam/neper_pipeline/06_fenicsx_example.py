#!/usr/bin/env python3
"""
Step 6 (example): Load the mesh + grain tags + orientations in FEniCSx and
build a per-cell anisotropic elastic stiffness tensor.

Works for a single-material RVE or the combined V specimen:

    python3 06_fenicsx_example.py 316L        # waam_316L_n<N>.xdmf
    python3 06_fenicsx_example.py 17-4PH      # waam_17-4PH_n<N>.xdmf
    python3 06_fenicsx_example.py combined    # spec_combined_V.xdmf

Shows how to
  - read the XDMF mesh + grain-id cell tags into dolfinx,
  - read grain_ori_<MAT>.txt (id phi1 Phi phi2 crystal ...) incl. the crystal
    system per grain (fcc / bcc),
  - build, per cell, the single-crystal cubic stiffness of that grain's phase
    rotated into the sample frame:  C_sample = T(g) . C_crystal . T(g)^T
    (6x6 Voigt / Bond rotation), ready for an anisotropic elasticity solve.

The single-crystal constants below are LITERATURE PLACEHOLDERS - replace with
your own values.  Units: GPa (mesh coordinates are in um; choose a consistent
unit system in the actual solve).

Tested against dolfinx >= 0.7 API.
"""
import json
import os
import sys

import numpy as np
from mpi4py import MPI
from dolfinx import fem, io

HERE = os.path.dirname(os.path.abspath(__file__))
sel = sys.argv[1] if len(sys.argv) > 1 else "316L"

if sel == "combined":
    xdmf = os.path.join(HERE, "spec_combined_V.xdmf")
    ori_file = os.path.join(HERE, "spec_combined_V_grain_ori.txt")
else:
    n = json.load(open(os.path.join(HERE, f"params_{sel}.json")))["n_grains"]
    xdmf = os.path.join(HERE, f"waam_{sel}_n{n}.xdmf")
    ori_file = os.path.join(HERE, f"grain_ori_{sel}.txt")

# ---- single-crystal cubic stiffness (Voigt 6x6), PLACEHOLDERS [GPa] --------
#   austenitic FCC (316L-like)     : C11, C12, C44
#   martensitic/ferritic BCC (Fe)  : C11, C12, C44
CUBIC = {
    "fcc": dict(C11=204.6, C12=137.7, C44=126.2),   # ~316L austenite
    "bcc": dict(C11=231.4, C12=134.7, C44=116.4),   # ~alpha-Fe / martensite
}
CUBIC["hcp"] = CUBIC["bcc"]      # epsilon is negligible; fall back to bcc
CUBIC["unknown"] = CUBIC["fcc"]


def cubic_C(sys_name):
    c = CUBIC[sys_name]
    C11, C12, C44 = c["C11"], c["C12"], c["C44"]
    C = np.zeros((6, 6))
    C[:3, :3] = C12
    C[0, 0] = C[1, 1] = C[2, 2] = C11
    C[3, 3] = C[4, 4] = C[5, 5] = C44
    return C


def bunge_to_g(phi1, Phi, phi2):
    """v_crystal = g @ v_sample (Bunge convention), angles in rad."""
    c1, s1, c, s, c2, s2 = (np.cos(phi1), np.sin(phi1), np.cos(Phi),
                            np.sin(Phi), np.cos(phi2), np.sin(phi2))
    return np.array([
        [c1 * c2 - s1 * s2 * c,  s1 * c2 + c1 * s2 * c, s2 * s],
        [-c1 * s2 - s1 * c2 * c, -s1 * s2 + c1 * c2 * c, c2 * s],
        [s1 * s,                 -c1 * s,                c]])


def bond_matrix(a):
    """6x6 Voigt (Bond) rotation M so that C_sample = M @ C_crystal @ M.T,
    with a = rotation matrix mapping crystal->sample (a = g^T)."""
    M = np.zeros((6, 6))
    M[:3, :3] = a ** 2
    M[:3, 3:] = 2 * np.array([
        [a[0, 1] * a[0, 2], a[0, 2] * a[0, 0], a[0, 0] * a[0, 1]],
        [a[1, 1] * a[1, 2], a[1, 2] * a[1, 0], a[1, 0] * a[1, 1]],
        [a[2, 1] * a[2, 2], a[2, 2] * a[2, 0], a[2, 0] * a[2, 1]]])
    M[3:, :3] = np.array([
        [a[1, 0] * a[2, 0], a[1, 1] * a[2, 1], a[1, 2] * a[2, 2]],
        [a[2, 0] * a[0, 0], a[2, 1] * a[0, 1], a[2, 2] * a[0, 2]],
        [a[0, 0] * a[1, 0], a[0, 1] * a[1, 1], a[0, 2] * a[1, 2]]])
    M[3:, 3:] = np.array([
        [a[1, 1] * a[2, 2] + a[1, 2] * a[2, 1], a[1, 2] * a[2, 0] + a[1, 0] * a[2, 2], a[1, 0] * a[2, 1] + a[1, 1] * a[2, 0]],
        [a[2, 1] * a[0, 2] + a[2, 2] * a[0, 1], a[2, 2] * a[0, 0] + a[2, 0] * a[0, 2], a[2, 0] * a[0, 1] + a[2, 1] * a[0, 0]],
        [a[0, 1] * a[1, 2] + a[0, 2] * a[1, 1], a[0, 2] * a[1, 0] + a[0, 0] * a[1, 2], a[0, 0] * a[1, 1] + a[0, 1] * a[1, 0]]])
    return M


# ---- mesh + grain tags -----------------------------------------------------
with io.XDMFFile(MPI.COMM_WORLD, xdmf, "r") as xf:
    mesh = xf.read_mesh(name="Grid")
    mesh.topology.create_connectivity(mesh.topology.dim, mesh.topology.dim)
    grain_tags = xf.read_meshtags(mesh, name="Grid")   # values = grain id

print(f"[{sel}] mesh: {mesh.topology.index_map(3).size_global} cells, "
      f"{len(np.unique(grain_tags.values))} grains")

# ---- per-grain orientation + crystal system --------------------------------
g_by_grain, sys_by_grain = {}, {}
with open(ori_file) as fh:
    for line in fh:
        if line.startswith("#") or not line.strip():
            continue
        p = line.split()
        gid = int(p[0])
        g_by_grain[gid] = bunge_to_g(*np.deg2rad([float(p[1]), float(p[2]), float(p[3])]))
        sys_by_grain[gid] = p[4] if len(p) > 4 else "unknown"

# per-cell rotated stiffness (DG-0, 36 components) + rotation matrix
Vc = fem.functionspace(mesh, ("DG", 0, (6, 6)))
Cf = fem.Function(Vc, name="stiffness_sample")
cvals = Cf.x.array.reshape(-1, 36)

ncell = mesh.topology.index_map(3).size_local
cell_grain = np.zeros(ncell, dtype=np.int64)
cell_grain[grain_tags.indices] = grain_tags.values
for c, gid in enumerate(cell_grain):
    g = g_by_grain[int(gid)]                  # crystal<-sample
    a = g.T                                   # sample<-crystal (= crystal->sample)
    M = bond_matrix(a)
    C = M @ cubic_C(sys_by_grain[int(gid)]) @ M.T
    cvals[c, :] = C.flatten()

print("per-cell anisotropic stiffness C_sample(x) ready (DG-0 6x6, GPa).")

# quick sanity output for ParaView (grain ids)
with io.XDMFFile(MPI.COMM_WORLD, os.path.join(HERE, f"check_grains_{sel}.xdmf"), "w") as xf:
    xf.write_mesh(mesh)
    xf.write_meshtags(grain_tags, mesh.geometry)
print(f"wrote check_grains_{sel}.xdmf (view grain ids in ParaView)")
