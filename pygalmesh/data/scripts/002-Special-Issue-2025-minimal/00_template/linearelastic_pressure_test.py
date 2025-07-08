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

import alex.os
import alex.boundaryconditions as bc
import alex.postprocessing as pp
import alex.solution as sol
import alex.linearelastic as le

import json

# ---------- Command-Line Argument Parsing ----------
if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
    print("Usage: python3 script.py [Material: Conv|AM] [Direction: x|y]")
    sys.exit(0)

material_set = sys.argv[1] if len(sys.argv) > 1 else "Conv"
loading_direction = sys.argv[2] if len(sys.argv) > 2 else "x"

# ---------- Script Path Handling ----------
script_path = os.path.dirname(__file__)
script_name_without_extension = os.path.splitext(os.path.basename(__file__))[0]
logfile_path = alex.os.logfile_full_path(script_path, script_name_without_extension)
outputfile_graph_path = alex.os.outputfile_graph_full_path(script_path, script_name_without_extension)
outputfile_xdmf_path = alex.os.outputfile_xdmf_full_path(script_path, script_name_without_extension)

# ---------- MPI and Timer Setup ----------
timer = dlfx.common.Timer()
timer.start()

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
print('MPI-STATUS: Process:', rank, 'of', size, 'processes.')
sys.stdout.flush()

# ---------- Load Mesh ----------
with dlfx.io.XDMFFile(comm, os.path.join(script_path, 'dlfx_mesh.xdmf'), 'r') as mesh_inp:
    domain = mesh_inp.read_mesh()

# ---------- Time Setup ----------
dt = dlfx.fem.Constant(domain, 0.02)
dt_max = dlfx.fem.Constant(domain, dt.value)
t = dlfx.fem.Constant(domain, 0.00)
Tend = 50.0 * dt.value

# ---------- Material Parameters ----------
if material_set.lower() == "am":
    E_mod = 73000.0
    nu = 0.36
    sigvm_threshhold = 140.0
else:
    E_mod = 82000.0
    nu = 0.35
    sigvm_threshhold = 110.0

lam = dlfx.fem.Constant(domain, alex.linearelastic.get_lambda(E_mod, nu))
mu = dlfx.fem.Constant(domain, alex.linearelastic.get_mu(E_mod, nu))

# ---------- Function Spaces ----------
Ve = ufl.VectorElement("Lagrange", domain.ufl_cell(), 1)
V = dlfx.fem.FunctionSpace(domain, Ve)

u = dlfx.fem.Function(V)
urestart = dlfx.fem.Function(V)
du = ufl.TestFunction(V)
ddu = ufl.TrialFunction(V)

# ---------- Initialization ----------
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
pp.print_bounding_box(rank, x_min_all, x_max_all, y_min_all, y_max_all, z_min_all, z_max_all)
atol = (x_max_all - x_min_all) * 0.02

# ---------- Boundary Conditions ----------
def get_bcs(t):
    amplitude = -1.0

    if loading_direction.lower() == "y":
        # Y direction loading
        bc_front_x = bc.define_dirichlet_bc_from_value(domain, 0.0, 0, bc.get_top_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)
        bc_front_y = bc.define_dirichlet_bc_from_value(domain, amplitude * t, 1, bc.get_top_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)
        bc_front_z = bc.define_dirichlet_bc_from_value(domain, 0.0, 2, bc.get_top_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)

        bc_back_x = bc.define_dirichlet_bc_from_value(domain, 0.0, 0, bc.get_bottom_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)
        bc_back_y = bc.define_dirichlet_bc_from_value(domain, 0.0, 1, bc.get_bottom_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)
        bc_back_z = bc.define_dirichlet_bc_from_value(domain, 0.0, 2, bc.get_bottom_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)
    else:
        # X direction loading
        bc_front_x = bc.define_dirichlet_bc_from_value(domain, amplitude * t, 0, bc.get_right_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)
        bc_front_y = bc.define_dirichlet_bc_from_value(domain, 0.0, 1, bc.get_right_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)
        bc_front_z = bc.define_dirichlet_bc_from_value(domain, 0.0, 2, bc.get_right_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)

        bc_back_x = bc.define_dirichlet_bc_from_value(domain, 0.0, 0, bc.get_left_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)
        bc_back_y = bc.define_dirichlet_bc_from_value(domain, 0.0, 1, bc.get_left_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)
        bc_back_z = bc.define_dirichlet_bc_from_value(domain, 0.0, 2, bc.get_left_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)

    return [bc_front_x, bc_front_y, bc_front_z, bc_back_x, bc_back_y, bc_back_z]

n = ufl.FacetNormal(domain)
simulation_result = np.array([0.0])
front_surface_tag = 9

if loading_direction.lower() == "y":
    top_surface_tags = pp.tag_part_of_boundary(domain, bc.get_top_boundary_of_box_as_function(domain, comm, atol=atol), front_surface_tag)
else:
    top_surface_tags = pp.tag_part_of_boundary(domain, bc.get_right_boundary_of_box_as_function(domain, comm, atol=atol), front_surface_tag)

ds_front_tagged = ufl.Measure('ds', domain=domain, subdomain_data=top_surface_tags)

success_timestep_counter = dlfx.fem.Constant(domain, 0.0)
postprocessing_interval = dlfx.fem.Constant(domain, 25.0)

def after_timestep_success(t, dt, iters):
    u.name = "u"
    sigma = le.sigma_as_tensor(u, lam, mu)
    Rx_front, Ry_front, Rz_front = pp.reaction_force(sigma, n=n, ds=ds_front_tagged(front_surface_tag), comm=comm)
    sig_vm = le.sigvM(sigma)

    vol = comm.allreduce(dlfx.fem.assemble_scalar(dlfx.fem.form(dlfx.fem.Constant(domain, 1.0) * ufl.dx)), MPI.SUM)
    vol_above = comm.allreduce(dlfx.fem.assemble_scalar(dlfx.fem.form(dlfx.fem.Constant(domain, 1.0) * ufl.conditional(ufl.ge(sig_vm, sigvm_threshhold), 1.0, 0.0) * ufl.dx)), MPI.SUM)
    simulation_result[0] = vol_above / vol * 100.0

    if rank == 0:
        pp.write_to_graphs_output_file(outputfile_graph_path, t, simulation_result[0], Rx_front)

    success_timestep_counter.value += 1.0
    urestart.x.array[:] = u.x.array[:]

    if not int(success_timestep_counter.value) % int(postprocessing_interval.value) == 0:
        return

    eps_strain = ufl.sym(ufl.grad(u))
    pp.write_tensor_fields(domain, comm, [sigma, eps_strain], ["sigma", "eps"], outputfile_xdmf_path, t)
    pp.write_scalar_fields(domain, comm, [sig_vm], ["sig_vm"], outputfile_xdmf_path, t)
    pp.write_vector_field(domain, outputfile_xdmf_path, u, t, comm)

def after_timestep_restart(t, dt, iters):
    u.x.array[:] = urestart.x.array[:]
    # raise RuntimeError("Linear computation - NO RESTART NECESSARY")

def after_last_timestep():
    timer.stop()
    if rank == 0:
        pp.print_graphs_plot(outputfile_graph_path, script_path, legend_labels=[
            f"volume percent above sigvm = {sigvm_threshhold}",
            "R_x [ N ]"
        ])
        runtime = timer.elapsed()
        sol.print_runtime(runtime)
        sol.write_runtime_to_newton_logfile(logfile_path, runtime)

# ---------- Solver Call ----------
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
    dt_never_scale_up=False,
    dt_max=dt_max
)
