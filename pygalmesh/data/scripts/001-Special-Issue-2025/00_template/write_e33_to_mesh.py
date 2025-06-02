import alex.homogenization
import alex.linearelastic
import alex.phasefield
import alex.util
import dolfinx as dlfx
from mpi4py import MPI
import json

import ufl
import numpy as np
import os
import sys

import alex.os
import alex.boundaryconditions as bc
import alex.postprocessing as pp
import alex.solution as sol
import alex.linearelastic as le

import basix

# Paths
script_path = os.path.dirname(__file__)
script_name_without_extension = os.path.splitext(os.path.basename(__file__))[0]
logfile_path = alex.os.logfile_full_path(script_path, script_name_without_extension)
outputfile_graph_path = alex.os.outputfile_graph_full_path(script_path, script_name_without_extension)
outputfile_xdmf_path = alex.os.outputfile_xdmf_full_path(script_path, script_name_without_extension)

# Timer
timer = dlfx.common.Timer()
timer.start()

# MPI
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
print('MPI-STATUS: Process:', rank, 'of', size, 'processes.')
sys.stdout.flush()

# Mesh
with dlfx.io.XDMFFile(comm, os.path.join(script_path, 'dlfx_mesh.xdmf'), 'r') as mesh_inp:
    domain = mesh_inp.read_mesh()

Se = basix.ufl.element("P", domain.basix_cell(), 1, shape=())
S = dlfx.fem.FunctionSpace(domain, Se)
e33 = dlfx.fem.Function(S)

# Read e33_val from E33.json (fall back to -1.0 if unavailable)
e33_json_path = os.path.join(script_path, 'E33.json')
e33_val = -1.0
try:
    with open(e33_json_path, 'r') as f:
        data = json.load(f)
        e33_val = data.get("value", e33_val)
        print(f"Loaded e33_val from E33.json: {e33_val}")
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"Warning: Could not read E33.json ({e}), using default e33_val = {e33_val}")

# Assign the value to the function vector
e33.x.array[:] = np.full_like(e33.x.array[:], e33_val)

# Write field to output file
pp.write_meshoutputfile(domain, outputfile_xdmf_path, comm)
pp.write_field(domain, outputfile_path=outputfile_xdmf_path, field=e33, t=0.0, comm=comm)





