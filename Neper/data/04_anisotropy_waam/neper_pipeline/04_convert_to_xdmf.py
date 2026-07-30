#!/usr/bin/env python3
"""
Step 4: Convert the Neper .msh to XDMF for FEniCSx.

Writes <name>.xdmf (+ .h5) containing the tetrahedra and a cell tag
"grain" = Neper cell id (1..N), matching grain_ori_<MAT>.txt.

Usage:  python3 04_convert_to_xdmf.py <mesh.msh> [MAT]
  If MAT (default 316L) is given and no explicit path, converts
  waam_<MAT>_n<N>.msh using params_<MAT>.json for N.

Requires: pip3 install meshio h5py   (inside the container)
"""
import json
import os
import sys

import meshio
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if len(sys.argv) > 1:
    msh = sys.argv[1]
else:
    mat = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("MAT", "316L")
    n = json.load(open(os.path.join(HERE, f"params_{mat}.json")))["n_grains"]
    msh = os.path.join(HERE, f"waam_{mat}_n{n}.msh")

m = meshio.read(msh)

# collect volume elements (tetra / tetra10) + their grain tags
etype = "tetra10" if "tetra10" in {cb.type for cb in m.cells} else "tetra"
cells = np.vstack([cb.data for cb in m.cells if cb.type == etype])

tag_key = None
for k in ("gmsh:physical", "gmsh:geometrical"):
    if k in m.cell_data_dict and etype in m.cell_data_dict[k]:
        tag_key = k
        break
if tag_key is None:
    sys.exit("no element tags found in msh - check Neper msh output")
tags = np.concatenate(
    [d for t, d in zip([cb.type for cb in m.cells], m.cell_data[tag_key]) if t == etype]
).astype(np.int32)

assert len(tags) == len(cells)
print(f"{len(cells)} {etype} elements, {len(np.unique(tags))} grains, "
      f"ids {tags.min()}..{tags.max()}")

out = os.path.splitext(msh)[0] + ".xdmf"
meshio.write(out, meshio.Mesh(
    points=m.points,
    cells=[(etype, cells)],
    cell_data={"grain": [tags]},
))
print("wrote", out, "(+ .h5)  - units: um")
