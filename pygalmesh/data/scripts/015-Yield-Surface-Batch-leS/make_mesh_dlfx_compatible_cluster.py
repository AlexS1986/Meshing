import dolfinx as dlfx
import dolfinx.io
from mpi4py import MPI
import meshio
import numpy as np
import os
import ufl
import copy
import argparse

# --- MPI communicator ---
comm = MPI.COMM_WORLD
rank = comm.Get_rank()

# --- Parse CLI arguments ---
parser = argparse.ArgumentParser(description="Convert mesh files to DolfinX format in-place.")
parser.add_argument("input_path", type=str, help="Path to the directory containing mesh files")
parser.add_argument(
    "--mesh-filenames", "-f", nargs="+", default=["mesh_output.xdmf"],
    help="Name(s) of the mesh file(s) to process (default: mesh_output.xdmf)"
)
# 05.09.2026: Freischwebende Netzfragmente (Zusammenhangskomponenten ohne
# Kontakt zur Randschale) erzeugen Starrkoerpermoden -> MUMPS INFO(1)=-10
# (r4 JM-25-77: 22 Fragmente, 2918 Knoten, 132 Nullmoden). Sie werden hier
# entfernt; behalten wird die groesste Komponente sowie jede Komponente, die
# innerhalb von --boundary-tol an eine Aussenflaeche der Bounding-Box reicht
# (dort greifen die Dirichlet-Randbedingungen der Randschale).
parser.add_argument("--keep-floating", action="store_true",
                    help="Fragmente NICHT entfernen (altes Verhalten)")
parser.add_argument("--boundary-tol", type=float, default=0.4,
                    help="Abstand zur Bounding-Box (Netzeinheit, mm), innerhalb dessen eine Komponente als angebunden gilt (default 0.4 = 6 Voxel x 66,8 um)")
args = parser.parse_args()


def drop_floating_components(points, cells, tol, report_path):
    """Entfernt Zusammenhangskomponenten ohne Kontakt zur Bounding-Box-Oberflaeche."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    cells = np.asarray(cells, dtype=np.int64)
    nv = points.shape[0]
    e = np.vstack([cells[:, [0, 1]], cells[:, [0, 2]], cells[:, [0, 3]],
                   cells[:, [1, 2]], cells[:, [1, 3]], cells[:, [2, 3]]])
    adj = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(nv, nv))
    ncomp, label = connected_components(adj, directed=False)
    used = np.zeros(nv, bool); used[cells.ravel()] = True
    lo, hi = points[used].min(0), points[used].max(0)
    near = np.zeros(nv, bool)
    for d in range(3):
        near |= (points[:, d] < lo[d] + tol) | (points[:, d] > hi[d] - tol)
    sizes = np.bincount(label[used], minlength=ncomp)      # nur referenzierte Knoten
    real = sizes > 0                                        # Komponenten mit Zellen
    anchored = np.bincount(label[near & used], minlength=ncomp) > 0
    keep = anchored.copy(); keep[np.argmax(sizes)] = True
    cell_keep = keep[label[cells[:, 0]]]
    new_cells = cells[cell_keep]
    dropped = int((real & ~keep).sum())
    lines = [
        f"components_total: {int(real.sum())}",
        f"components_dropped_floating: {dropped}",
        f"cells_before: {cells.shape[0]}",
        f"cells_after: {new_cells.shape[0]}",
        f"nodes_dropped: {int(sizes[~keep].sum())}",
        f"boundary_tol: {tol}",
        f"largest_component_nodes: {int(sizes.max())}",
    ]
    if dropped:
        fs = np.sort(sizes[real & ~keep])[::-1]
        lines.append("dropped_component_nodes: " + " ".join(str(int(v)) for v in fs[:50]))
    with open(report_path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join("  " + l for l in lines))
    # Knoten neu nummerieren (nur referenzierte Punkte behalten)
    ref = np.zeros(nv, bool); ref[new_cells.ravel()] = True
    newid = -np.ones(nv, np.int64); newid[ref] = np.arange(int(ref.sum()))
    return points[ref], newid[new_cells]

input_folder = args.input_path
target_mesh_filenames = set(args.mesh_filenames)

# --- Find mesh files in input folder ---
mesh_files = []
for file in os.listdir(input_folder):
    if file in target_mesh_filenames:
        input_file = os.path.join(input_folder, file)
        output_file = os.path.join(input_folder, "dlfx_mesh.xdmf")
        mesh_files.append((input_file, output_file))

# --- Process mesh files ---
for input_file, output_file in mesh_files:
    if rank == 0:
        print(f"Processing mesh: {input_file}")
        meshio_data = meshio.read(input_file)

        # Adjust point orientation
        points_tmp = meshio_data.points[:, :3]
        points = copy.deepcopy(points_tmp)
        points[:, 0] = points_tmp[:, 0]
        points[:, 1] = points_tmp[:, 1]

        # Filter active tetrahedral cells. Pygalmesh writes medit:ref; nanomesh writes tetgen:ref.
        tetra_cells = meshio_data.cells_dict.get("tetra")
        cell_data = meshio_data.cell_data_dict
        if "medit:ref" in cell_data and "tetra" in cell_data["medit:ref"]:
            cells_id = cell_data["medit:ref"]["tetra"]
        elif "tetgen:ref" in cell_data and "tetra" in cell_data["tetgen:ref"]:
            cells_id = cell_data["tetgen:ref"]["tetra"]
        elif "gmsh:physical" in cell_data and "tetra" in cell_data["gmsh:physical"]:
            cells_id = cell_data["gmsh:physical"]["tetra"]
        else:
            cells_id = None

        if tetra_cells is None:
            raise ValueError(f"No tetra cells found in {input_file}")
        if cells_id is None:
            active_cells = np.asarray(tetra_cells, dtype=np.int64)
        else:
            active_cells = np.asarray(tetra_cells, dtype=np.int64)[np.asarray(cells_id) != 0]
        if not args.keep_floating:
            print("Removing floating mesh components (no contact to the bounding-box surface):")
            points, active_cells = drop_floating_components(
                points, active_cells, args.boundary_tol,
                os.path.join(input_folder, "dlfx_mesh.components.txt"))
    else:
        points = None
        active_cells = None

    # Create mesh
    cell = ufl.Cell('tetrahedron', geometric_dimension=3)
    element = ufl.VectorElement('Lagrange', cell, 1, dim=3)
    mesh = ufl.Mesh(element)
    domain = dlfx.mesh.create_mesh(comm, active_cells, points, mesh)

    # Write mesh
    if rank == 0:
        print(f"Writing converted mesh to: {output_file}")
    with dlfx.io.XDMFFile(comm, output_file, "w") as xdmf:
        xdmf.write_mesh(domain)



