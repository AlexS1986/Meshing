import dolfinx as dlfx
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
args = parser.parse_args()

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
        points[:, 0] = points_tmp[:, 1]
        points[:, 1] = points_tmp[:, 0]

        # Filter active tetrahedral cells
        tetra_cells = meshio_data.cells_dict.get("tetra")
        cells_id = meshio_data.cell_data_dict['medit:ref']['tetra']
        active_cells = [cell for idx, cell in enumerate(tetra_cells) if cells_id[idx] == 1]
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



