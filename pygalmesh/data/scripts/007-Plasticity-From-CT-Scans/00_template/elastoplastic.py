import alex.plasticity
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
import basix

# ---------- Arguments ----------
material_set = sys.argv[1] if len(sys.argv) > 1 else "default"
loading_direction = sys.argv[2] if len(sys.argv) > 2 else "x"

# ---------- Paths ----------
script_path = os.path.dirname(__file__)
script_name = os.path.splitext(os.path.basename(__file__))[0]

logfile_path = alex.os.logfile_full_path(script_path, script_name)
outputfile_graph_path = alex.os.outputfile_graph_full_path(script_path, script_name)
outputfile_xdmf_path = alex.os.outputfile_xdmf_full_path(script_path, script_name)

# ---------- MPI ----------
comm = MPI.COMM_WORLD
rank = comm.Get_rank()

# ---------- Mesh (3D unit cube for testing) ----------
# N = 10
# domain = dlfx.mesh.create_unit_cube(
#     comm,
#     N, N, N,
#     cell_type=dlfx.mesh.CellType.tetrahedron
# )

# ---------- Load Mesh ----------
with dlfx.io.XDMFFile(comm, os.path.join(script_path, 'dlfx_mesh.xdmf'), 'r') as mesh_inp:
    domain = mesh_inp.read_mesh()

# ---------- Time ----------
dt = dlfx.fem.Constant(domain, 0.02)
dt_max = dlfx.fem.Constant(domain, dt.value)
t = dlfx.fem.Constant(domain, 0.0)
Tend = 50.0 * dt.value

# ---------- Material ----------
material = material_set.lower()

if material == "am":
    E_mod, nu = 73000.0, 0.36
    sig_y_value = 140.0
    hard_value = 0.0

elif material == "std":
    E_mod, nu = 70000.0, 0.35
    sig_y_value = 140.0
    hard_value = 0.0

elif material == "conv":
    E_mod, nu = 82000.0, 0.35
    sig_y_value = 110.0
    hard_value = 0.0

elif material == "default":
    E_mod, nu = 2.5, 0.25
    sig_y_value = 1.0
    hard_value = 0.22

else:
    print(f"[WARNING] Unknown material '{material_set}', using DEFAULT test values.")
    E_mod, nu = 2.5, 0.25
    sig_y_value = 1.0
    hard_value = 0.22

# ---------- Convert to FEM Constants ----------
lam = dlfx.fem.Constant(domain, le.get_lambda(E_mod, nu))
mu  = dlfx.fem.Constant(domain, le.get_mu(E_mod, nu))

sig_y = dlfx.fem.Constant(domain, sig_y_value)
hard  = dlfx.fem.Constant(domain, hard_value)

# ---------- Function Space ----------
Ve = ufl.VectorElement("Lagrange", domain.ufl_cell(), 1)
V = dlfx.fem.FunctionSpace(domain, Ve)

u = dlfx.fem.Function(V)
um1 = dlfx.fem.Function(V)
urestart = dlfx.fem.Function(V)

du = ufl.TestFunction(V)
ddu = ufl.TrialFunction(V)

# ---------- Internal Variables ----------
deg_quad = 1

(
    alpha_n, alpha_tmp,
    e_p_11_n, e_p_22_n, e_p_33_n,
    e_p_12_n, e_p_13_n, e_p_23_n,
    e_p_11_tmp, e_p_22_tmp, e_p_33_tmp,
    e_p_12_tmp, e_p_13_tmp, e_p_23_tmp
) = alex.plasticity.define_internal_state_variables_basix_3D(domain, deg_quad)

dx = alex.plasticity.define_custom_integration_measure_that_matches_quadrature_degree_and_scheme(
    domain, deg_quad, "default"
)

quadrature_points, cells = alex.plasticity.get_quadraturepoints_and_cells_for_inter_polation_at_gauss_points(
    domain, deg_quad
)

# ---------- Plastic strain tensor ----------
e_p_n = ufl.as_tensor([
    [e_p_11_n, e_p_12_n, e_p_13_n],
    [e_p_12_n, e_p_22_n, e_p_23_n],
    [e_p_13_n, e_p_23_n, e_p_33_n],
])

# ---------- Plasticity Problem ----------
plasticityProblem = alex.plasticity.Plasticity_3D(
    sig_y=sig_y,
    hard=hard,
    alpha_n=alpha_n,
    e_p_n=e_p_n,
    dx=dx
)

# ---------- Boundary tagging for reaction force ----------
x_min, x_max, y_min, y_max, z_min, z_max = bc.get_dimensions(domain, comm)
atol = (x_max - x_min) * 0.025

n = ufl.FacetNormal(domain)
front_surface_tag = 9

if loading_direction.lower() == "y":
    top_surface_tags = pp.tag_part_of_boundary(
        domain,
        bc.get_top_boundary_of_box_as_function(domain, comm, atol),
        front_surface_tag
    )
else:
    top_surface_tags = pp.tag_part_of_boundary(
        domain,
        bc.get_right_boundary_of_box_as_function(domain, comm, atol),
        front_surface_tag
    )

ds_front_tagged = ufl.Measure('ds', domain=domain, subdomain_data=top_surface_tags)

dim = domain.topology.dim

TEN = dlfx.fem.functionspace(domain, ("DP", deg_quad-1, (dim, dim)))
sigma_interpolated = dlfx.fem.Function(TEN)

S0e = basix.ufl.element("DP", domain.basix_cell(), 0, shape=())
S0 = dlfx.fem.functionspace(domain, S0e)

sigma_vm_interpolated = dlfx.fem.Function(S0)


# ---------- Hooks ----------
def before_first_time_step():
    urestart.x.array[:] = um1.x.array[:]
    if rank == 0:
        sol.prepare_newton_logfile(logfile_path)
        pp.prepare_graphs_output_file(outputfile_graph_path)
    pp.write_meshoutputfile(domain, outputfile_xdmf_path, comm)

def before_each_time_step(t, dt):
    if rank == 0:
        sol.print_time_and_dt(t, dt)

# ---------- Newton ----------
def get_residuum_and_gateaux(delta_t):
    return plasticityProblem.prep_newton(
        u=u,
        um1=um1,
        du=du,
        ddu=ddu,
        lam=lam,
        mu=mu
    )

# ---------- Boundary Conditions ----------
def get_bcs(t):
    max_mean_strain = 0.25

    if loading_direction.lower() == "y":
        amplitude = - max_mean_strain *(y_max-y_min)
        # Y direction loading
        bc_front_x = bc.define_dirichlet_bc_from_value(domain, 0.0, 0, bc.get_top_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)
        bc_front_y = bc.define_dirichlet_bc_from_value(domain, amplitude * t, 1, bc.get_top_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)
        bc_front_z = bc.define_dirichlet_bc_from_value(domain, 0.0, 2, bc.get_top_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)

        bc_back_x = bc.define_dirichlet_bc_from_value(domain, 0.0, 0, bc.get_bottom_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)
        bc_back_y = bc.define_dirichlet_bc_from_value(domain, 0.0, 1, bc.get_bottom_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)
        bc_back_z = bc.define_dirichlet_bc_from_value(domain, 0.0, 2, bc.get_bottom_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)
    else:
        # X direction loading
        amplitude = - max_mean_strain *(x_max-x_min)
        bc_front_x = bc.define_dirichlet_bc_from_value(domain, amplitude * t, 0, bc.get_right_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)
        bc_front_y = bc.define_dirichlet_bc_from_value(domain, 0.0, 1, bc.get_right_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)
        bc_front_z = bc.define_dirichlet_bc_from_value(domain, 0.0, 2, bc.get_right_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)

        bc_back_x = bc.define_dirichlet_bc_from_value(domain, 0.0, 0, bc.get_left_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)
        bc_back_y = bc.define_dirichlet_bc_from_value(domain, 0.0, 1, bc.get_left_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)
        bc_back_z = bc.define_dirichlet_bc_from_value(domain, 0.0, 2, bc.get_left_boundary_of_box_as_function(domain, comm, atol=atol), V, -1)

    return [bc_front_x, bc_front_y, bc_front_z, bc_back_x, bc_back_y, bc_back_z]

# ---------- Postprocessing ----------
def after_timestep_success(t, dt, iters):

    # 🔴 Plastic update
    alex.plasticity.update_e_p_n_and_alpha_arrays_3D(
        u,
        e_p_11_tmp, e_p_22_tmp, e_p_33_tmp,
        e_p_12_tmp, e_p_13_tmp, e_p_23_tmp,
        e_p_11_n, e_p_22_n, e_p_33_n,
        e_p_12_n, e_p_13_n, e_p_23_n,
        alpha_tmp, alpha_n,
        domain, cells, quadrature_points,
        sig_y, hard, mu
    )

    # ---------- Stress (UFL) ----------
    sigma = plasticityProblem.sigma(u,lam,mu)
    sig_vm = le.sigvM(sigma)

    # ---------- Interpolate sigma ----------
    sigma_expr = dlfx.fem.Expression(
        sigma,
        TEN.element.interpolation_points()
    )
    sigma_interpolated.interpolate(sigma_expr)
    sigma_interpolated.name = "sigma"

    # ---------- Interpolate von Mises ----------
    vm_expr = dlfx.fem.Expression(
        sig_vm,
        S0.element.interpolation_points()
    )
    sigma_vm_interpolated.interpolate(vm_expr)
    sigma_vm_interpolated.name = "sig_vm"

    # ---------- Reaction force ----------
    Rx, Ry, Rz = pp.reaction_force(
        sigma_interpolated,
        n=n,
        ds=ds_front_tagged(front_surface_tag),
        comm=comm
    )

    if rank == 0:
        sol.write_to_newton_logfile(logfile_path, t, dt, iters)

        pp.write_to_graphs_output_file(
            outputfile_graph_path,
            t,
            Rx, Ry, Rz
        )

    # ---------- Write to XDMF ----------
    pp.write_tensor_fields(
        domain, comm,
        [sigma_interpolated],
        ["sigma"],
        outputfile_xdmf_path,
        t
    )

    pp.write_scalar_fields(
        domain, comm,
        [sigma_vm_interpolated],
        ["sig_vm"],
        outputfile_xdmf_path,
        t
    )

    # 🔴 alpha_n (internal variable)
    pp.write_field(
        domain,
        outputfile_xdmf_path,
        alpha_n,
        t,
        comm,
        S=S0
    )

    # displacement
    u.name = "u"
    pp.write_vector_field(domain, outputfile_xdmf_path, u, t, comm)

    # ---------- Update ----------
    um1.x.array[:] = u.x.array[:]
    urestart.x.array[:] = u.x.array[:]

def after_timestep_restart(t, dt, iters):
    u.x.array[:] = urestart.x.array[:]

def after_last_timestep():
    if rank == 0:
        pp.print_graphs_plot(
            outputfile_graph_path,
            script_path,
            legend_labels=["R_x", "R_y", "R_z"]
        )

# ---------- Solver ----------
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
    dt_max=dt_max
)