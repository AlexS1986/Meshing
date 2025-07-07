import alex.homogenization
import alex.linearelastic
import alex.phasefield
import alex.util
import dolfinx as dlfx
from mpi4py import MPI

import ufl 
import numpy as np
import os 
import sys
import argparse
import json

import alex.os
import alex.boundaryconditions as bc
import alex.postprocessing as pp
import alex.solution as sol
import alex.linearelastic as le

# Argument parser
parser = argparse.ArgumentParser(description="Linear Elastic Homogenization")
parser.add_argument(
    "--material", type=str, choices=["conv", "am"], default="conv",
    help="Material model: 'conv' (default) or 'am'"
)
args = parser.parse_args()

# Setup paths
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

# Read mesh
with dlfx.io.XDMFFile(comm, os.path.join(script_path, 'dlfx_mesh.xdmf'), 'r') as mesh_inp:
    domain = mesh_inp.read_mesh()

# Time setup
dt = dlfx.fem.Constant(domain, 1.0)
t = dlfx.fem.Constant(domain, 0.00)
column = dlfx.fem.Constant(domain, 0.0)
Tend = 6.0 * dt.value

# Material constants
if args.material == "am":
    lam = dlfx.fem.Constant(domain, 88550.0)
    mu = dlfx.fem.Constant(domain, 13200.0)
else:  # conv
    lam = dlfx.fem.Constant(domain, 51100.0)
    mu = dlfx.fem.Constant(domain, 26300.0)

E_mod = alex.linearelastic.get_emod(lam.value, mu.value)

# Function space
Ve = ufl.VectorElement("Lagrange", domain.ufl_cell(), 1)
V = dlfx.fem.FunctionSpace(domain, Ve)

# Boundary conditions
fdim = domain.topology.dim - 1
bcs = []

# Solution functions
u = dlfx.fem.Function(V)
urestart = dlfx.fem.Function(V)
du = ufl.TestFunction(V)
ddu = ufl.TrialFunction(V)

def before_first_time_step():
    urestart.x.array[:] = np.ones_like(urestart.x.array[:])
    
    if rank == 0:
        sol.prepare_newton_logfile(logfile_path)
        pp.prepare_graphs_output_file(outputfile_graph_path)
    pp.write_meshoutputfile(domain, outputfile_xdmf_path, comm)

def before_each_time_step(t, dt):
    if rank == 0:
        sol.print_time_and_dt(t, dt)

linearElasticProblem = alex.linearelastic.StaticLinearElasticProblem()

def get_residuum_and_gateaux(delta_t: dlfx.fem.Constant):
    [Res, dResdw] = linearElasticProblem.prep_newton(u, du, ddu, lam, mu)
    return [Res, dResdw]

x_min_all, x_max_all, y_min_all, y_max_all, z_min_all, z_max_all = bc.get_dimensions(domain, comm)
atol = (x_max_all - x_min_all) * 0.05

u_D = dlfx.fem.Function(V)
boundary = bc.get_boundary_of_box_as_function(domain, comm, atol=atol)
facets_at_boundary = dlfx.mesh.locate_entities_boundary(domain, fdim, boundary)
dofs_at_boundary = dlfx.fem.locate_dofs_topological(V, fdim, facets_at_boundary)

eps_mac = dlfx.fem.Constant(domain, np.zeros((3, 3)))

def get_bcs(t):
    Eps_Voigt = np.zeros((6,))
    Eps_Voigt[int(t)] = 1.0

    eps_mac.value = np.array([
        [Eps_Voigt[0], Eps_Voigt[5] / 2.0, Eps_Voigt[4] / 2.0],
        [Eps_Voigt[5] / 2.0, Eps_Voigt[1], Eps_Voigt[3] / 2.0],
        [Eps_Voigt[4] / 2.0, Eps_Voigt[3] / 2.0, Eps_Voigt[2]]
    ])

    if t > 5:
        eps_mac.value = np.zeros((3, 3))

    comm.barrier()

    def compute_linear_displacement():
        x = ufl.SpatialCoordinate(domain)
        u_x = eps_mac.value[0, 0] * x[0] + eps_mac.value[0, 1] * x[1] + eps_mac.value[0, 2] * x[2]
        u_y = eps_mac.value[1, 0] * x[0] + eps_mac.value[1, 1] * x[1] + eps_mac.value[1, 2] * x[2]
        u_z = eps_mac.value[2, 0] * x[0] + eps_mac.value[2, 1] * x[1] + eps_mac.value[2, 2] * x[2]
        return ufl.as_vector([u_x, u_y, u_z])

    bc_expression = dlfx.fem.Expression(compute_linear_displacement(), V.element.interpolation_points())
    u_D.interpolate(bc_expression)
    bc_linear_displacement = dlfx.fem.dirichletbc(u_D, dofs_at_boundary)

    return [bc_linear_displacement]

simulation_result = np.array([0.0])
vol = (x_max_all - x_min_all) * (y_max_all - y_min_all) * (z_max_all - z_min_all)
Chom = np.zeros((6, 6))

def after_timestep_success(t, dt, iters):
    u.name = "u"
    pp.write_vector_field(domain, outputfile_xdmf_path, u, t, comm)

    sigma_for_unit_strain = alex.homogenization.compute_averaged_sigma(u, lam, mu, vol, comm=comm)

    comm.barrier()
    if rank == 0:
        if column.value < 6:
            Chom[int(column.value)] = sigma_for_unit_strain
        else:
            t = 2.0 * Tend  # exit
            return
        column.value = column.value + 1
        sol.write_to_newton_logfile(logfile_path, t, dt, iters)

    urestart.x.array[:] = u.x.array[:]

def after_timestep_restart(t, dt, iters):
    raise RuntimeError("Linear computation - NO RESTART NECESSARY")
    u.x.array[:] = urestart.x.array[:]

def after_last_timestep():
    timer.stop()
    if rank == 0:
        print(np.array_str(Chom, precision=2))
        print(alex.homogenization.print_results(Chom))

        chom_path = os.path.join(script_path, "Chom.json")
        with open(chom_path, "w") as f:
            json.dump(Chom.tolist(), f, indent=4)
        print(f"Saved Chom matrix to: {chom_path}")

        runtime = timer.elapsed()
        sol.print_runtime(runtime)
        sol.write_runtime_to_newton_logfile(logfile_path, runtime)

sol.solve_with_newton_adaptive_time_stepping(
    domain,
    u,
    Tend,
    dt,
    before_first_timestep_hook=before_first_time_step,
    after_last_timestep_hook=after_last_timestep,
    before_each_timestep_hook=before_each_time_step,
    get_residuum_and_gateaux=get_residuum_and_gateaux,
    get_bcs=get_bcs,
    after_timestep_restart_hook=after_timestep_restart,
    after_timestep_success_hook=after_timestep_success,
    comm=comm,
    print_bool=True,
    t=t,
    dt_never_scale_up=True
)

