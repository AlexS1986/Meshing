import dolfinx as dlfx
from mpi4py import MPI
import json
import numpy as np
import os
import ufl

import alex.os
import alex.postprocessing as pp
import basix

# Paths
script_path = os.path.dirname(__file__)
script_name_without_extension = os.path.splitext(os.path.basename(__file__))[0]
outputfile_xdmf_path = alex.os.outputfile_xdmf_full_path(script_path, script_name_without_extension)

# MPI setup
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
print(f"MPI-STATUS: Process {rank} of {size}")

# Read mesh
with dlfx.io.XDMFFile(comm, os.path.join(script_path, 'dlfx_mesh.xdmf'), 'r') as mesh_inp:
    domain = mesh_inp.read_mesh(name="Grid")

# Function spaces
Se = basix.ufl.element("P", domain.basix_cell(), 1, shape=())
S = dlfx.fem.FunctionSpace(domain, Se)

Ve = ufl.VectorElement("Lagrange", domain.ufl_cell(), 1)
V = dlfx.fem.FunctionSpace(domain, Ve)

# Load JSON utility
def load_json_data(filename):
    try:
        with open(os.path.join(script_path, filename), 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load {filename}: {e}")
        return {}

# Load homogenized moduli
E_data = load_json_data("E_moduli.json")
G_data = load_json_data("G_moduli.json")

# Combine scalar values
all_scalar_fields = {}
for source in [E_data, G_data]:
    for key, val in source.items():
        if isinstance(val, (float, int)):
            all_scalar_fields[key] = float(val)
        elif isinstance(val, dict) and "value" in val:
            all_scalar_fields[key] = float(val["value"])

# Write scalar fields
for name, value in all_scalar_fields.items():
    print(f"Writing scalar field: {name} = {value}")
    f = dlfx.fem.Function(S)
    f.name = name
    f.x.array[:] = np.full_like(f.x.array[:], value)
    pp.write_field(domain, outputfile_path=outputfile_xdmf_path, field=f, t=0.0, comm=comm)

# Combine vector fields for directions
all_vector_fields = {}
for prefix, source in [("E", E_data), ("G", G_data)]:
    for suffix in ["max", "min"]:
        key = f"{prefix}{suffix}"
        val = source.get(key)
        if isinstance(val, dict) and "direction" in val:
            direction = np.array(val["direction"], dtype=float)
            if direction.shape == (3,):
                all_vector_fields[f"{key}_dir"] = direction

# Write vector fields
for name, vec in all_vector_fields.items():
    print(f"Writing vector field: {name} = {vec}")
    f = dlfx.fem.Function(V)
    f.name = name
    f.x.array[:] = np.tile(vec, f.x.array.shape[0] // 3)
    pp.write_field(domain, outputfile_path=outputfile_xdmf_path, field=f, t=0.0, comm=comm)

# Final mesh write
pp.write_meshoutputfile(domain, outputfile_xdmf_path, comm)
print(f"All moduli fields written to {outputfile_xdmf_path}")






