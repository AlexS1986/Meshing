import argparse
import json
import os
import sys

import alex.plasticity
import alex.util
import dolfinx as dlfx
from mpi4py import MPI

import ufl
import numpy as np

import alex.os
import alex.boundaryconditions as bc
import alex.postprocessing as pp
import alex.solution as sol
import alex.linearelastic as le
import basix


class StopSimulation(Exception):
    pass


parser = argparse.ArgumentParser(description="Elasto-plastic CT yield-surface loading run")
parser.add_argument("legacy_material", nargs="?", default=None)
parser.add_argument("legacy_loading_direction", nargs="?", default=None)
parser.add_argument("--material", default=None)
parser.add_argument("--loading-direction", "--direction", dest="loading_direction", default=None, choices=["x", "y", "z", "tensor"])
parser.add_argument("--config", default=None, help="Defaults to config.json in the solver folder if present.")
parser.add_argument("--eps1", type=float, default=None, help="First eigenvalue of the target diagonal macroscopic strain tensor.")
parser.add_argument("--eps2", type=float, default=None, help="Second eigenvalue of the target diagonal macroscopic strain tensor.")
parser.add_argument("--eps3", type=float, default=None, help="Third eigenvalue of the target diagonal macroscopic strain tensor.")
parser.add_argument("--yielded-volume-fraction", type=float, default=None, help="Stop once this fraction of the reduced material volume has alpha above tolerance.")
parser.add_argument("--alpha-yield-tolerance", type=float, default=None, help="Alpha threshold used to classify a cell as yielded.")
args = parser.parse_args()

material_set = args.material or args.legacy_material or "std"
loading_direction = (args.loading_direction or args.legacy_loading_direction or "tensor").lower()
if loading_direction not in {"x", "y", "z", "tensor"}:
    raise ValueError(f"Unsupported loading direction '{loading_direction}'. Use x, y, z, or tensor.")

script_path = os.path.dirname(__file__)
script_name = os.path.splitext(os.path.basename(__file__))[0]
logfile_path = alex.os.logfile_full_path(script_path, f"{script_name}_{material_set}_{loading_direction}")
outputfile_graph_path = alex.os.outputfile_graph_full_path(script_path, f"{script_name}_{material_set}_{loading_direction}")
outputfile_xdmf_path = alex.os.outputfile_xdmf_full_path(script_path, f"{script_name}_{material_set}_{loading_direction}")


def load_optional_config():
    config_path = args.config or os.path.join(script_path, "config.json")
    if config_path and os.path.isfile(config_path):
        with open(config_path, "r") as handle:
            return json.load(handle), config_path
    return {}, None


def boundary_shell_voxel_thicknesses(config):
    seal = config.get("02d_axis_aligned_cuboid_crop", {}).get("boundary_seal", {})
    if not seal.get("enabled", False):
        return None
    base_thickness = int(seal.get("thickness", 0) or 0)
    thicknesses = {
        "x_min": base_thickness, "x_max": base_thickness,
        "y_min": base_thickness, "y_max": base_thickness,
        "z_min": base_thickness, "z_max": base_thickness,
    }
    for key, value in (seal.get("thicknesses") or {}).items():
        if key in {"x", "y", "z"}:
            thicknesses[f"{key}_min"] = int(value)
            thicknesses[f"{key}_max"] = int(value)
        elif key in thicknesses:
            thicknesses[key] = int(value)
        else:
            raise ValueError(f"Unsupported boundary shell thickness key: {key}")
    return thicknesses


def load_solver_volume_shape(config):
    prep = config.get("02d_axis_aligned_cuboid_crop", {})
    names = []
    if prep.get("output_filename"):
        names.append(prep["output_filename"])
    names.extend(["volume_boundary_shell_aniso.npy", "volume_boundary_shell.npy", "volume_cuboid.npy", "volume.npy"])
    for name in names:
        volume_path = os.path.join(script_path, name)
        if os.path.isfile(volume_path):
            return np.load(volume_path, mmap_mode="r").shape, volume_path
    return None, None


def shell_widths_from_config(config, bounds):
    thicknesses = boundary_shell_voxel_thicknesses(config)
    if thicknesses is None:
        return None, None, None
    shape, volume_path = load_solver_volume_shape(config)
    if shape is None:
        return None, thicknesses, volume_path
    x_min, x_max, y_min, y_max, z_min, z_max = bounds
    return {
        "x_min": thicknesses["x_min"] / shape[0] * (x_max - x_min),
        "x_max": thicknesses["x_max"] / shape[0] * (x_max - x_min),
        "y_min": thicknesses["y_min"] / shape[1] * (y_max - y_min),
        "y_max": thicknesses["y_max"] / shape[1] * (y_max - y_min),
        "z_min": thicknesses["z_min"] / shape[2] * (z_max - z_min),
        "z_max": thicknesses["z_max"] / shape[2] * (z_max - z_min),
    }, thicknesses, volume_path


def shell_band_marker(widths, bounds):
    x_min, x_max, y_min, y_max, z_min, z_max = bounds
    return lambda x: (
        (x[0] <= x_min + widths["x_min"]) |
        (x[0] >= x_max - widths["x_max"]) |
        (x[1] <= y_min + widths["y_min"]) |
        (x[1] >= y_max - widths["y_max"]) |
        (x[2] <= z_min + widths["z_min"]) |
        (x[2] >= z_max - widths["z_max"])
    )


def interior_marker_from_shell(widths, bounds):
    x_min, x_max, y_min, y_max, z_min, z_max = bounds
    return lambda x: (
        (x[0] > x_min + widths["x_min"]) &
        (x[0] < x_max - widths["x_max"]) &
        (x[1] > y_min + widths["y_min"]) &
        (x[1] < y_max - widths["y_max"]) &
        (x[2] > z_min + widths["z_min"]) &
        (x[2] < z_max - widths["z_max"])
    )


def assemble_global_scalar(expr, comm):
    local_value = dlfx.fem.assemble_scalar(dlfx.fem.form(expr))
    return comm.allreduce(local_value, op=MPI.SUM)


def averaged_tensor_over_reduced_volume(tensor_expr, dx_reduced, tag, volume, comm):
    values = np.zeros((3, 3))
    if volume <= 0.0:
        return values
    for i in range(3):
        for j in range(3):
            values[i, j] = assemble_global_scalar(tensor_expr[i, j] * dx_reduced(tag), comm) / volume
    return values


def averaged_scalar_over_reduced_volume(scalar_expr, dx_reduced, tag, volume, comm):
    if volume <= 0.0:
        return 0.0
    return assemble_global_scalar(scalar_expr * dx_reduced(tag), comm) / volume


def positive_alpha_volume(alpha_expr, tolerance, dx_reduced, tag, comm):
    indicator = ufl.conditional(ufl.gt(alpha_expr, tolerance), 1.0, 0.0)
    return assemble_global_scalar(indicator * dx_reduced(tag), comm)


config, config_path = load_optional_config()
yield_config = config.get("yield_surface", {})

comm = MPI.COMM_WORLD
rank = comm.Get_rank()

with dlfx.io.XDMFFile(comm, os.path.join(script_path, "dlfx_mesh.xdmf"), "r") as mesh_inp:
    domain = mesh_inp.read_mesh()

dt_value = float(yield_config.get("time_step", 0.0001))
Tend_value = float(yield_config.get("total_time", 1.0e9))
dt_global = dlfx.fem.Constant(domain, dt_value)
dt_max = dlfx.fem.Constant(domain, 10*dt_global.value)
t = dlfx.fem.Constant(domain, 0.0)
Tend = Tend_value
dt_min = float(yield_config.get("dt_min", 1e-11))
max_mean_strain = float(yield_config.get("max_mean_strain", 0.25))

config_eps = yield_config.get("eps_mac_eigenvalues")
if args.eps1 is not None or args.eps2 is not None or args.eps3 is not None:
    if args.eps1 is None or args.eps2 is None or args.eps3 is None:
        raise ValueError("Provide all of --eps1, --eps2, and --eps3, or none of them.")
    eps_mac_eigenvalues = np.array([args.eps1, args.eps2, args.eps3], dtype=float)
elif config_eps is not None:
    if len(config_eps) != 3:
        raise ValueError("yield_surface.eps_mac_eigenvalues must contain exactly three values.")
    eps_mac_eigenvalues = np.array(config_eps, dtype=float)
else:
    eps_mac_eigenvalues = np.zeros(3, dtype=float)
    eps_mac_eigenvalues[{"x": 0, "y": 1, "z": 2}.get(loading_direction, 0)] = -max_mean_strain

strain_scale_start = float(yield_config.get("strain_scale_start", 1e-6))
strain_scale_rate = float(yield_config.get("strain_scale_rate", 1.0))
yielded_volume_fraction_target = float(
    args.yielded_volume_fraction
    if args.yielded_volume_fraction is not None
    else yield_config.get("yielded_volume_fraction", 0.02)
)
alpha_yield_tolerance = float(
    args.alpha_yield_tolerance
    if args.alpha_yield_tolerance is not None
    else yield_config.get("alpha_yield_tolerance", 1e-5)
)
if yielded_volume_fraction_target <= 0.0 or yielded_volume_fraction_target > 1.0:
    raise ValueError("yielded_volume_fraction must be in (0, 1].")

material = material_set.lower()
material_sets = yield_config.get("material_sets", {})
mat = material_sets.get(material)
if mat is None:
    mat = yield_config.get("default_material", {"E": 2.5, "nu": 0.25, "sig_y": 1.0, "hard": 0.01})
    if rank == 0:
        print(f"[WARNING] Unknown material '{material_set}', using default material from config.")

E_mod = float(mat.get("E", 2.5))
nu = float(mat.get("nu", 0.25))
sig_y_value = float(mat.get("sig_y", 1.0))
hard_value = float(mat.get("hard", 0.01))

lam = dlfx.fem.Constant(domain, le.get_lambda(E_mod, nu))
mu = dlfx.fem.Constant(domain, le.get_mu(E_mod, nu))
sig_y = dlfx.fem.Constant(domain, sig_y_value)
hard = dlfx.fem.Constant(domain, hard_value)

deg_quad = int(yield_config.get("quadrature_degree", 1))
Ve = ufl.VectorElement("Lagrange", domain.ufl_cell(), deg_quad)
V = dlfx.fem.FunctionSpace(domain, Ve)

u_fun = dlfx.fem.Function(V)
um1 = dlfx.fem.Function(V)
urestart = dlfx.fem.Function(V)

du = ufl.TestFunction(V)
ddu = ufl.TrialFunction(V)

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

e_p_n = ufl.as_tensor([
    [e_p_11_n, e_p_12_n, e_p_13_n],
    [e_p_12_n, e_p_22_n, e_p_23_n],
    [e_p_13_n, e_p_23_n, e_p_33_n],
])

plasticityProblem = alex.plasticity.Plasticity_3D(
    sig_y=sig_y,
    hard=hard,
    alpha_n=alpha_n,
    e_p_n=e_p_n,
    dx=dx
)

x_min_all, x_max_all, y_min_all, y_max_all, z_min_all, z_max_all = bc.get_dimensions(domain, comm)
domain_bounds = (x_min_all, x_max_all, y_min_all, y_max_all, z_min_all, z_max_all)
lengths = [x_max_all - x_min_all, y_max_all - y_min_all, z_max_all - z_min_all]
atol_scal = 0.04
atol_x = lengths[0] * atol_scal
atol_y = lengths[1] * atol_scal
atol_z = lengths[2] * atol_scal
shell_widths, shell_voxel_thicknesses, shell_volume_path = shell_widths_from_config(config, domain_bounds)

if loading_direction == "tensor":
    axis = int(np.argmax(np.abs(eps_mac_eigenvalues)))
else:
    axis = {"x": 0, "y": 1, "z": 2}[loading_direction]

fdim = domain.topology.dim - 1
u_D = dlfx.fem.Function(V)
if shell_widths is not None:
    boundary = shell_band_marker(shell_widths, domain_bounds)
    dofs_at_boundary = dlfx.fem.locate_dofs_geometrical(V, boundary)
else:
    boundary = bc.get_boundary_of_box_as_function(domain, comm, atol_x=atol_x, atol_y=atol_y, atol_z=atol_z)
    facets_at_boundary = dlfx.mesh.locate_entities_boundary(domain, fdim, boundary)
    dofs_at_boundary = dlfx.fem.locate_dofs_topological(V, fdim, facets_at_boundary)

eps_mac = dlfx.fem.Constant(domain, np.zeros((3, 3)))

n = ufl.FacetNormal(domain)
front_surface_tag = 9
if loading_direction == "x":
    reaction_boundary = bc.get_right_boundary_of_box_as_function(domain, comm, atol=atol_x)
elif loading_direction == "y":
    reaction_boundary = bc.get_top_boundary_of_box_as_function(domain, comm, atol=atol_y)
else:
    reaction_boundary = lambda x: np.isclose(x[2], z_max_all, atol=atol_z)
top_surface_tags = pp.tag_part_of_boundary(domain, reaction_boundary, front_surface_tag)
ds_front_tagged = ufl.Measure("ds", domain=domain, subdomain_data=top_surface_tags)

# Reduced integration domain: same idea as 009 linearelastic.py. This excludes
# the shell/boundary region where Dirichlet boundary conditions are applied.
tag_value_hom_cells = 1
if shell_widths is not None:
    marker1 = interior_marker_from_shell(shell_widths, domain_bounds)
else:
    marker1 = bc.dont_get_boundary_of_box_as_function(domain, comm, atol_x=atol_x, atol_y=atol_y, atol_z=atol_z)
marked_cells = dlfx.mesh.locate_entities(domain, dim=3, marker=marker1)
marked_values = np.full(len(marked_cells), tag_value_hom_cells, dtype=np.int32)
cell_tags = dlfx.mesh.meshtags(domain, 3, marked_cells, marked_values)

dx_hom_cells = ufl.Measure("dx", domain=domain, subdomain_data=cell_tags)
x_min_hom_all, x_max_hom_all, y_min_hom_all, y_max_hom_all, z_min_hom_all, z_max_hom_all = bc.get_tagged_subdomain_bounds(domain, cell_tags, tag_value_hom_cells, comm)
vol = (x_max_hom_all - x_min_hom_all) * (y_max_hom_all - y_min_hom_all) * (z_max_hom_all - z_min_hom_all)
vol_material = assemble_global_scalar(dlfx.fem.Constant(domain, 1.0) * dx_hom_cells(tag_value_hom_cells), comm)
vol_overall = lengths[0] * lengths[1] * lengths[2]

dim = domain.topology.dim
TEN = dlfx.fem.functionspace(domain, ("DP", max(deg_quad - 1, 0), (dim, dim)))
sigma_interpolated = dlfx.fem.Function(TEN)
S0e = basix.ufl.element("DP", domain.basix_cell(), 0, shape=())
S0 = dlfx.fem.functionspace(domain, S0e)
sigma_vm_interpolated = dlfx.fem.Function(S0)

averaged_history = []
final_yield_state = None
stop_reason = None


def before_first_time_step():
    urestart.x.array[:] = um1.x.array[:]
    if rank == 0:
        sol.prepare_newton_logfile(logfile_path)
        pp.prepare_graphs_output_file(outputfile_graph_path)
        print("=== Yield Surface Elasto-Plastic Run ===")
        print(f"material: {material}")
        print(f"loading_direction: {loading_direction}")
        print(f"E: {E_mod}, nu: {nu}, sig_y: {sig_y_value}, hard: {hard_value}")
        print(f"eps_mac_eigenvalues: {eps_mac_eigenvalues.tolist()}")
        print(f"strain_scale_start: {strain_scale_start}")
        print(f"strain_scale_rate: {strain_scale_rate}")
        print(f"total_time_solver_horizon: {Tend_value}")
        print(f"yielded_volume_fraction_target: {yielded_volume_fraction_target}")
        print(f"alpha_yield_tolerance: {alpha_yield_tolerance}")
        print(f"boundary_shell_voxel_thicknesses: {shell_voxel_thicknesses}")
        print(f"boundary_shell_physical_widths: {shell_widths}")
        print("=== Reduced Averaging Domain ===")
        print(f"x: [{x_min_hom_all}, {x_max_hom_all}]")
        print(f"y: [{y_min_hom_all}, {y_max_hom_all}]")
        print(f"z: [{z_min_hom_all}, {z_max_hom_all}]")
        print(f"reduced_volume_box: {vol}")
        print(f"reduced_volume_material: {vol_material}")
        print(f"total_volume_box: {vol_overall}")
    pp.write_meshoutputfile(domain, outputfile_xdmf_path, comm)


def before_each_time_step(t, dt):
    if dt_global.value < dt_min:
        if rank == 0:
            print(f"[STOP] dt too small: {dt_global.value:.3e} < {dt_min}")
        raise StopSimulation
    if rank == 0:
        sol.print_time_and_dt(t, dt)


def get_residuum_and_gateaux(delta_t):
    return plasticityProblem.prep_newton(
        u=u_fun,
        um1=um1,
        du=du,
        ddu=ddu,
        lam=lam,
        mu=mu
    )


def current_strain_scale(t):
    current_t = float(t.value if hasattr(t, "value") else t)
    return strain_scale_start + strain_scale_rate * max(current_t, 0.0)


def current_eps_mac_diagonal(t):
    return eps_mac_eigenvalues * current_strain_scale(t)


def get_bcs(t):
    eps_diag = current_eps_mac_diagonal(t)
    eps = np.diag(eps_diag)
    eps_mac.value = eps

    def compute_linear_displacement():
        x = ufl.SpatialCoordinate(domain)
        u_x = eps_mac.value[0, 0] * x[0] + eps_mac.value[0, 1] * x[1] + eps_mac.value[0, 2] * x[2]
        u_y = eps_mac.value[1, 0] * x[0] + eps_mac.value[1, 1] * x[1] + eps_mac.value[1, 2] * x[2]
        u_z = eps_mac.value[2, 0] * x[0] + eps_mac.value[2, 1] * x[1] + eps_mac.value[2, 2] * x[2]
        return ufl.as_vector([u_x, u_y, u_z])

    bc_expression = dlfx.fem.Expression(compute_linear_displacement(), V.element.interpolation_points())
    u_D.interpolate(bc_expression)
    return [dlfx.fem.dirichletbc(u_D, dofs_at_boundary)]


def after_timestep_success(t, dt, iters):
    alex.plasticity.update_e_p_n_and_alpha_arrays_3D(
        u_fun,
        e_p_11_tmp, e_p_22_tmp, e_p_33_tmp,
        e_p_12_tmp, e_p_13_tmp, e_p_23_tmp,
        e_p_11_n, e_p_22_n, e_p_33_n,
        e_p_12_n, e_p_13_n, e_p_23_n,
        alpha_tmp, alpha_n,
        domain, cells, quadrature_points,
        sig_y, hard, mu
    )

    sigma = plasticityProblem.sigma(u_fun, lam, mu)
    sig_vm = le.sigvM(sigma)

    sigma_expr = dlfx.fem.Expression(sigma, TEN.element.interpolation_points())
    sigma_interpolated.interpolate(sigma_expr)
    sigma_interpolated.name = "sigma"

    vm_expr = dlfx.fem.Expression(sig_vm, S0.element.interpolation_points())
    sigma_vm_interpolated.interpolate(vm_expr)
    sigma_vm_interpolated.name = "sig_vm"

    Rx, Ry, Rz = pp.reaction_force(
        sigma_interpolated,
        n=n,
        ds=ds_front_tagged(front_surface_tag),
        comm=comm
    )
    sigma_avg = averaged_tensor_over_reduced_volume(sigma, dx_hom_cells, tag_value_hom_cells, vol, comm)
    sig_vm_avg = averaged_scalar_over_reduced_volume(sig_vm, dx_hom_cells, tag_value_hom_cells, vol, comm)
    alpha_avg = averaged_scalar_over_reduced_volume(alpha_n, dx_hom_cells, tag_value_hom_cells, vol_material, comm)
    alpha_avg_box = averaged_scalar_over_reduced_volume(alpha_n, dx_hom_cells, tag_value_hom_cells, vol, comm)
    yielded_volume = positive_alpha_volume(alpha_n, alpha_yield_tolerance, dx_hom_cells, tag_value_hom_cells, comm)
    yielded_fraction_material = yielded_volume / vol_material if vol_material > 0.0 else 0.0
    yielded_fraction_box = yielded_volume / vol if vol > 0.0 else 0.0
    eps_diag = current_eps_mac_diagonal(t)
    scale = current_strain_scale(t)

    if rank == 0:
        sol.write_to_newton_logfile(logfile_path, t, dt, iters)
        pp.write_to_graphs_output_file(outputfile_graph_path, t, Rx, Ry, Rz)
        averaged_history.append({
            "t": float(t.value if hasattr(t, "value") else t),
            "dt": float(dt.value if hasattr(dt, "value") else dt),
            "iterations": int(iters),
            "reaction_force": [float(Rx), float(Ry), float(Rz)],
            "strain_scale": float(scale),
            "eps_mac_eigenvalues_current": eps_diag.tolist(),
            "sigma_avg_reduced_volume": sigma_avg.tolist(),
            "sig_vm_avg_reduced_volume": float(sig_vm_avg),
            "alpha_avg_reduced_material_volume": float(alpha_avg),
            "alpha_avg_reduced_volume": float(alpha_avg_box),
            "yielded_volume_alpha_gt_tol": float(yielded_volume),
            "yielded_fraction_reduced_material_volume": float(yielded_fraction_material),
            "yielded_fraction_reduced_volume": float(yielded_fraction_box),
        })

    pp.write_tensor_fields(domain, comm, [sigma_interpolated], ["sigma"], outputfile_xdmf_path, t)
    pp.write_scalar_fields(domain, comm, [sigma_vm_interpolated], ["sig_vm"], outputfile_xdmf_path, t)
    pp.write_field(domain, outputfile_xdmf_path, alpha_n, t, comm, S=S0)

    u_fun.name = "u"
    pp.write_vector_field(domain, outputfile_xdmf_path, u_fun, t, comm)

    um1.x.array[:] = u_fun.x.array[:]
    urestart.x.array[:] = u_fun.x.array[:]

    global final_yield_state, stop_reason
    if yielded_fraction_material >= yielded_volume_fraction_target:
        final_yield_state = averaged_history[-1] if rank == 0 and averaged_history else {
            "strain_scale": float(scale),
            "eps_mac_eigenvalues_current": eps_diag.tolist(),
            "alpha_avg_reduced_material_volume": float(alpha_avg),
            "yielded_fraction_reduced_material_volume": float(yielded_fraction_material),
        }
        stop_reason = "yielded_volume_fraction_reached"
        if rank == 0:
            print(
                f"[STOP] yielded fraction {yielded_fraction_material:.6g} "
                f">= target {yielded_volume_fraction_target:.6g}"
            )
        raise StopSimulation


def after_timestep_restart(t, dt, iters):
    u_fun.x.array[:] = urestart.x.array[:]


def after_last_timestep():
    if rank == 0:
        pp.print_graphs_plot(
            outputfile_graph_path,
            script_path,
            legend_labels=["R_x", "R_y", "R_z"]
        )
        summary_path = os.path.join(script_path, f"yield_run_{material}_{loading_direction}.json")
        with open(summary_path, "w") as handle:
            json.dump({
                "material": material,
                "loading_direction": loading_direction,
                "E": E_mod,
                "nu": nu,
                "sig_y": sig_y_value,
                "hard": hard_value,
                "eps_mac_eigenvalues_target": eps_mac_eigenvalues.tolist(),
                "strain_scale_start": strain_scale_start,
                "strain_scale_rate": strain_scale_rate,
                "yielded_volume_fraction_target": yielded_volume_fraction_target,
                "alpha_yield_tolerance": alpha_yield_tolerance,
                "final_yield_state": final_yield_state,
                "stop_reason": stop_reason,
                "time_step": dt_value,
                "total_time": Tend_value,
                "boundary_shell_voxel_thicknesses": shell_voxel_thicknesses,
                "boundary_shell_physical_widths": shell_widths,
                "boundary_shell_volume_path": shell_volume_path,
                "reduced_volume_box": vol,
                "reduced_volume_material": vol_material,
                "total_volume_box": vol_overall,
                "homogenization_excludes_boundary_shell": shell_widths is not None,
                "config_path": config_path,
            }, handle, indent=2)
        print(f"Saved yield run summary to: {summary_path}")
        averages_path = os.path.join(script_path, f"yield_averages_{material}_{loading_direction}.json")
        with open(averages_path, "w") as handle:
            json.dump(averaged_history, handle, indent=2)
        print(f"Saved reduced-volume averages to: {averages_path}")


try:
    sol.solve_with_newton_adaptive_time_stepping(
        domain,
        u_fun,
        Tend,
        dt_global,
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
except StopSimulation:
    if rank == 0 and stop_reason is None:
        print("[INFO] Simulation stopped because dt became too small.")
    after_last_timestep()
