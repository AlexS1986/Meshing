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
# 08.09.2026: Zusaetzlich "Scharnierteile" entfernen - Zellgruppen, die mit dem
# Rest nur Kanten oder Knoten teilen, aber keine Dreiecksflaeche. Knotenbasiert
# zaehlen sie als verbunden, mechanisch sind sie fast frei (Rotation um Kante/
# Knoten = Starrkoerpermode, Pivot rundungsklein statt exakt null -> MUMPS
# meldet nichts, aber |u| bis 1e11 mm in diesen Knoten, Residuum konvergiert
# nicht mehr). r4-Netze: 87-253 solche Teile je Datensatz, 0,01-0,04 % des
# Volumens (CLAUDE.md §22). Behalten wird die groesste flaechenzusammenhaengende
# Komponente sowie Teile mit >= --hinge-min-anchor Knoten in der Randschale.
parser.add_argument("--keep-hinges", action="store_true",
                    help="Scharnierteile NICHT entfernen (Verhalten bis 08.09.2026)")
parser.add_argument("--hinge-min-anchor", type=int, default=4,
                    help="Nebenteil behalten, wenn mindestens so viele Knoten in der Randschale liegen (default 4)")
# 20.10.2026 (1D-Druckversuch): Verankerung nur an den Flaechen, die wirklich
# eine Randschale mit Dirichlet-Randbedingung tragen. Beim Druckversuch sind
# nur die x-Platten (x_min, x_max) geschlossen, die Seitenflaechen sind frei;
# dort "verankerte" Fragmente waeren Starrkoerper. Default "all" = altes
# Verhalten. Mit --config werden die Flaechen aus
# 02d_axis_aligned_cuboid_crop.boundary_seal.thicknesses abgeleitet (Dicke > 0).
parser.add_argument("--anchor-faces", default="all",
                    help="Kommaliste aus x_min,x_max,y_min,y_max,z_min,z_max oder Achsen x,y,z; 'all' = alle (default)")
parser.add_argument("--config", default=None,
                    help="Config-JSON; falls angegeben, Verankerungsflaechen = Schalenflaechen mit Dicke > 0 (schlaegt --anchor-faces)")
args = parser.parse_args()

ALL_FACES = ["x_min", "x_max", "y_min", "y_max", "z_min", "z_max"]


def anchor_faces_from_args(a):
    faces = None
    if a.config:
        import json
        with open(a.config) as handle:
            cfg = json.load(handle)
        seal = cfg.get("02d_axis_aligned_cuboid_crop", {}).get("boundary_seal", {})
        if seal.get("enabled", False):
            base = int(seal.get("thickness", 0) or 0)
            th = {f: base for f in ALL_FACES}
            for key, value in (seal.get("thicknesses") or {}).items():
                if key in ("x", "y", "z"):
                    th[key + "_min"] = int(value); th[key + "_max"] = int(value)
                elif key in th:
                    th[key] = int(value)
            faces = [f for f in ALL_FACES if th[f] > 0]
    if faces is None:
        if a.anchor_faces.strip().lower() == "all":
            faces = list(ALL_FACES)
        else:
            faces = []
            for tok in a.anchor_faces.split(","):
                tok = tok.strip().lower()
                if tok in ("x", "y", "z"):
                    faces += [tok + "_min", tok + "_max"]
                elif tok in ALL_FACES:
                    faces.append(tok)
                elif tok:
                    raise ValueError(f"Unbekannte Verankerungsflaeche: {tok}")
    if not faces:
        raise ValueError("Keine Verankerungsflaeche - Fragmentfilter braucht mindestens eine Schalenflaeche.")
    return faces


ANCHOR_FACES = anchor_faces_from_args(args)


def near_anchor_faces(points, lo, hi, tol):
    """Knoten innerhalb tol an einer der Verankerungsflaechen der Bounding-Box."""
    near = np.zeros(points.shape[0], bool)
    for d, ax in enumerate("xyz"):
        if f"{ax}_min" in ANCHOR_FACES:
            near |= points[:, d] < lo[d] + tol
        if f"{ax}_max" in ANCHOR_FACES:
            near |= points[:, d] > hi[d] - tol
    return near


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
    near = near_anchor_faces(points, lo, hi, tol)
    sizes = np.bincount(label[used], minlength=ncomp)      # nur referenzierte Knoten
    real = sizes > 0                                        # Komponenten mit Zellen
    anchored = np.bincount(label[near & used], minlength=ncomp) > 0
    keep = anchored.copy(); keep[np.argmax(sizes)] = True
    cell_keep = keep[label[cells[:, 0]]]
    new_cells = cells[cell_keep]
    dropped = int((real & ~keep).sum())
    lines = [
        f"anchor_faces: {','.join(ANCHOR_FACES)}",
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

def face_components(cells):
    """Zusammenhangskomponenten der Zellen ueber gemeinsame Dreiecksflaechen.

    Rueckgabe: label je Zelle (int64). Zwei Tets sind benachbart, wenn sie
    dieselbe (sortierte) Knotentripel-Flaeche besitzen; Kontakt nur ueber
    Kanten oder Knoten zaehlt nicht.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    cells = np.asarray(cells, dtype=np.int64)
    nc = cells.shape[0]
    faces = np.sort(np.stack([cells[:, [1, 2, 3]], cells[:, [0, 2, 3]],
                              cells[:, [0, 1, 3]], cells[:, [0, 1, 2]]], axis=1)
                    .reshape(-1, 3), axis=1)
    cell_of = np.repeat(np.arange(nc), 4)
    order = np.lexsort((faces[:, 2], faces[:, 1], faces[:, 0]))
    fs, cs = faces[order], cell_of[order]
    same = np.all(fs[1:] == fs[:-1], axis=1)
    a, b = cs[:-1][same], cs[1:][same]
    adj = coo_matrix((np.ones(len(a), dtype=np.int8), (a, b)), shape=(nc, nc))
    return connected_components(adj, directed=False)[1]


def drop_hinge_components(points, cells, tol, min_anchor, report_path):
    """Entfernt Zellgruppen ohne Flaechenkontakt zur Hauptkomponente ("Scharniere").

    Behalten: die groesste flaechenzusammenhaengende Komponente und jede
    Komponente mit mindestens min_anchor Knoten in der Randschale (dort fixieren
    die Dirichlet-Randbedingungen alle Freiheitsgrade). Nicht referenzierte
    Knoten werden entfernt und neu nummeriert.
    """
    cells = np.asarray(cells, dtype=np.int64)
    nv = points.shape[0]
    label = face_components(cells)
    ncomp = int(label.max()) + 1
    sizes = np.bincount(label, minlength=ncomp)
    used = np.zeros(nv, bool); used[cells.ravel()] = True
    lo, hi = points[used].min(0), points[used].max(0)
    near = near_anchor_faces(points, lo, hi, tol)
    # Randschalenknoten je Komponente (Knoten koennen mehreren Komponenten
    # angehoeren - genau das ist das Scharnier - deshalb ueber Zellen zaehlen)
    node_comp = np.repeat(label, 4)
    node_ids = cells.ravel()
    pairs = np.unique(np.stack([node_comp[near[node_ids]], node_ids[near[node_ids]]], axis=1), axis=0)
    anchor = np.bincount(pairs[:, 0], minlength=ncomp)
    keep = anchor >= max(int(min_anchor), 1)
    keep[np.argmax(sizes)] = True
    cell_keep = keep[label]
    new_cells = cells[cell_keep]
    dropped = int((~keep).sum())
    lines = [
        f"hinge_components_total: {ncomp}",
        f"hinge_components_dropped: {dropped}",
        f"hinge_components_kept_anchored: {int(keep.sum()) - 1}",
        f"hinge_cells_dropped: {int(cells.shape[0] - new_cells.shape[0])}",
        f"hinge_min_anchor: {int(min_anchor)}",
        f"cells_after_hinge_filter: {new_cells.shape[0]}",
    ]
    if dropped:
        fs = np.sort(sizes[~keep])[::-1]
        lines.append("dropped_hinge_component_cells: " + " ".join(str(int(v)) for v in fs[:50]))
    with open(report_path, "a") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join("  " + l for l in lines))
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
        if not args.keep_hinges:
            print("Removing hinge components (cell groups sharing no face with the main body):")
            points, active_cells = drop_hinge_components(
                points, active_cells, args.boundary_tol, args.hinge_min_anchor,
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



