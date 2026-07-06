import alex.linearelastic
import alex.phasefield
import dolfinx as dlfx
from mpi4py import MPI
from petsc4py import PETSc as petsc

import ufl 
import numpy as np
import os 
import sys
import math
import basix

import alex.os
import alex.boundaryconditions as bc
import alex.postprocessing as pp
import alex.solution as sol
import alex.linearelastic as le
import alex.phasefield as pf


def run_simulation(mesh_file, lam_param, mue_param, Gc_param, eps_factor_param, element_order, comm):

    script_path = os.path.dirname(__file__)
    script_name_without_extension = os.path.splitext(os.path.basename(__file__))[0]
    working_folder = script_path
    logfile_path = alex.os.logfile_full_path(working_folder, script_name_without_extension)
    outputfile_graph_path = alex.os.outputfile_graph_full_path(working_folder, script_name_without_extension)
    outputfile_xdmf_path = alex.os.outputfile_xdmf_full_path(working_folder, script_name_without_extension)

    timer = dlfx.common.Timer()
    timer.start()

    rank = comm.Get_rank()
    size = comm.Get_size()
    print('MPI-STATUS: Process:', rank, 'of', size, 'processes.')
    sys.stdout.flush()

    with dlfx.io.XDMFFile(comm, os.path.join(script_path, mesh_file+".xdmf"), 'r') as mesh_inp: 
        domain = mesh_inp.read_mesh()

    dt = dlfx.fem.Constant(domain, 0.0001)
    t_global = dlfx.fem.Constant(domain, 0.0)
    Tend = 1000.0 * dt.value

    Ve = basix.ufl.element("P", domain.basix_cell(), element_order, shape=(domain.geometry.dim,))
    Se = basix.ufl.element("P", domain.basix_cell(), element_order, shape=())
    W = dlfx.fem.functionspace(domain, basix.ufl.mixed_element([Ve, Se]))

    dim = domain.topology.dim
    alex.os.mpi_print('spatial dimensions: '+str(dim), rank)

    x_min_all, x_max_all, y_min_all, y_max_all, z_min_all, z_max_all = pp.compute_bounding_box(comm, domain)
    pp.print_bounding_box(rank, x_min_all, x_max_all, y_min_all, y_max_all, z_min_all, z_max_all)

    lam = dlfx.fem.Constant(domain, lam_param)
    mu = dlfx.fem.Constant(domain, mue_param)

    eta = dlfx.fem.Constant(domain, 0.001)
    Gc = dlfx.fem.Constant(domain, Gc_param)
    epsilon = dlfx.fem.Constant(domain, (y_max_all - y_min_all) / eps_factor_param)

    Mob = dlfx.fem.Constant(domain, 1000.0)
    iMob = dlfx.fem.Constant(domain, 1.0 / Mob.value)
   
    sig_c = pf.sig_c_quadr_deg(Gc.value, mu.value, epsilon.value)
    L = (y_max_all - y_min_all)
    K1 = dlfx.fem.Constant(domain, 1.0 * sig_c * math.sqrt(L))

    crack_tip_start_location_x = 0.1*(x_max_all - x_min_all) + x_min_all
    crack_tip_start_location_y = (y_max_all + y_min_all) / 2.0

    def crack(x):
        x_log = x[0] < crack_tip_start_location_x
        y_log = np.isclose(x[1], crack_tip_start_location_y, atol=(0.02*(y_max_all - y_min_all)))
        return np.logical_and(y_log, x_log)

    tdim = domain.topology.dim
    fdim = tdim - 1
    domain.topology.create_connectivity(fdim, tdim)

    crackfacets = dlfx.mesh.locate_entities(domain, fdim, crack)
    crackdofs = dlfx.fem.locate_dofs_topological(W.sub(1), fdim, crackfacets)
    bccrack = dlfx.fem.dirichletbc(0.0, crackdofs, W.sub(1))

    w = dlfx.fem.Function(W)
    u, s = w.split()
    wrestart = dlfx.fem.Function(W)
    wm1 = dlfx.fem.Function(W)
    dw = ufl.TestFunction(W)
    ddw = ufl.TrialFunction(W)

    def before_first_time_step():
        wm1.sub(1).x.array[:] = np.ones_like(wm1.sub(1).x.array[:])
        wrestart.x.array[:] = wm1.x.array[:]
        if rank == 0:
            sol.prepare_newton_logfile(logfile_path)
            pp.prepare_graphs_output_file(outputfile_graph_path)
        pp.write_meshoutputfile(domain, outputfile_xdmf_path, comm)

    def before_each_time_step(t, dt):
        if rank == 0:
            sol.print_time_and_dt(t, dt)
        
    phaseFieldProblem = pf.StaticPhaseFieldProblem3D(degradationFunction=pf.quadratic_degradation(),
                                                     psisurf=pf.psisurf)

    def get_residuum_and_gateaux(delta_t: dlfx.fem.Constant):
        [Res, dResdw] = phaseFieldProblem.prep_newton(
            w=w, wm1=wm1, dw=dw, ddw=ddw, lam=lam, mu=mu,
            Gc=Gc, epsilon=epsilon, eta=eta,
            iMob=iMob, delta_t=delta_t)
        return [Res, dResdw]

    # =========================
    # SURFING BCS IMPLEMENTATION
    # =========================

    atol = (x_max_all - x_min_all) * 0.02
    xxK1 = dlfx.fem.Constant(domain, np.array([0.0, 0.0, 0.0], dtype=dlfx.default_scalar_type))
    w_D = dlfx.fem.Function(W)

    def compute_surf_displacement():
        x = ufl.SpatialCoordinate(domain)
        dx = x[0] - xxK1[0]
        dy = x[1] - xxK1[1]

        nu = le.get_nu(lam=lam, mu=mu)

        r = ufl.sqrt(dx*dx + dy*dy)
        theta = ufl.atan2(dy, dx)

        factor = K1 / (2.0 * mu * math.sqrt(2.0 * math.pi))

        u_x = factor * ufl.sqrt(r) * (3 - 4*nu - ufl.cos(theta)) * ufl.cos(theta/2)
        u_y = factor * ufl.sqrt(r) * (3 - 4*nu - ufl.cos(theta)) * ufl.sin(theta/2)

        return ufl.as_vector([u_x, u_y, 0.0])

    boundary_surfing_bc = bc.get_boundary_of_box_as_function(domain, comm,atol=atol,epsilon=epsilon.value)
    facets_at_boundary = dlfx.mesh.locate_entities_boundary(domain, fdim, boundary_surfing_bc)
    dofs_at_boundary = dlfx.fem.locate_dofs_topological(W.sub(0), fdim, facets_at_boundary)
    bc_expression = dlfx.fem.Expression(compute_surf_displacement(), W.sub(0).element.interpolation_points())

    # =========================
    # CRACK TIP AND TIME-DEPENDENT BCS
    # =========================
    
        # setupt tracking
    Se = ufl.FiniteElement("Lagrange", domain.ufl_cell(),1) 
    S = dlfx.fem.FunctionSpace(domain,Se)
    s_zero_for_tracking_at_nodes = dlfx.fem.Function(S)
    c = dlfx.fem.Constant(domain, petsc.ScalarType(1))
    sub_expr = dlfx.fem.Expression(c,S.element.interpolation_points())
    s_zero_for_tracking_at_nodes.interpolate(sub_expr)

    xtip = np.array([0.0, 0.0, 0.0], dtype=dlfx.default_scalar_type)
    xK1 = dlfx.fem.Constant(domain, xtip)
    v_crack = 2.0*(x_max_all - x_min_all)/Tend
    vcrack_const = dlfx.fem.Constant(domain, np.array([v_crack, 0.0, 0.0], dtype=dlfx.default_scalar_type))
    crack_start = dlfx.fem.Constant(domain, np.array([crack_tip_start_location_x, crack_tip_start_location_y, 0.0], dtype=dlfx.default_scalar_type))
    
    def get_bcs(t):
        x_min_all, x_max_all, y_min_all, y_max_all, z_min_all, z_max_all = bc.get_dimensions(domain, comm)
        v_crack = 2.0*(x_max_all - crack_tip_start_location_x)/Tend
        xtip[0] = x_min_all + v_crack * t
        xtip[1] = crack_tip_start_location_y

        xxK1.value = np.array([xtip[0], xtip[1], 0.0], dtype=dlfx.default_scalar_type)

        w_D.sub(0).interpolate(bc_expression)
        bc_surf = dlfx.fem.dirichletbc(w_D, dofs_at_boundary)

        bcs = [bc_surf]

        if abs(t) > sys.float_info.epsilon * 5:
            bcs.append(pf.irreversibility_bc(domain, W, wm1))
        bcs.append(bccrack)
        
        return bcs

    # =========================
    # REST OF THE SIMULATION
    # =========================

    n = ufl.FacetNormal(domain)
    external_surface_tags = pp.tag_part_of_boundary(domain, bc.get_boundary_of_box_as_function(domain, comm, atol=atol), 5)
    ds = ufl.Measure('ds', domain=domain, subdomain_data=external_surface_tags)
    top_surface_tags = pp.tag_part_of_boundary(domain, bc.get_top_boundary_of_box_as_function(domain, comm, atol=atol), 1)
    ds_top_tagged = ufl.Measure('ds', domain=domain, subdomain_data=top_surface_tags)

    success_timestep_counter = dlfx.fem.Constant(domain, 0.0)
    postprocessing_interval = dlfx.fem.Constant(domain, 1.0)
    Work = dlfx.fem.Constant(domain, 0.0)
    
    S = dlfx.fem.functionspace(domain, Se)

    def after_timestep_success(t, dt, iters):
        sigma = phaseFieldProblem.sigma_degraded(u, s, lam.value, mu.value, eta)
        Rx_top, Ry_top, Rz_top = pp.reaction_force(sigma, n=n, ds=ds_top_tagged(1), comm=comm)
        
        um1, _ = ufl.split(wm1)
        dW = pp.work_increment_external_forces(sigma, u, um1, n, ds(5), comm=comm)
        Work.value = Work.value + dW
        
        A = pf.get_surf_area(s, epsilon=epsilon, dx=ufl.dx, comm=comm)
        
        if rank == 0:
            sol.write_to_newton_logfile(logfile_path, t, dt, iters)
        
        eshelby = phaseFieldProblem.getEshelby(w, eta, lam, mu)
        J3D_glob_x, J3D_glob_y, J3D_glob_z = alex.linearelastic.get_J_3D(eshelby, ds=ds(5), n=n, comm=comm)

        if rank == 0:
            print(pp.getJString(J3D_glob_x, J3D_glob_y, J3D_glob_z))
        
        # s_zero_for_tracking_at_nodes = dlfx.fem.Function(S)
        # c = dlfx.fem.Constant(domain, petsc.ScalarType(1))
        # sub_expr = dlfx.fem.Expression(c,S.element.interpolation_points())
       
        # s_zero_for_tracking_at_nodes = dlfx.fem.Function(S)
        # sub_expr = dlfx.fem.Constant(S.mesh, petsc.ScalarType(1))
        # #sub_expr = dlfx.fem.Constant(S.function_space.mesh, petsc.ScalarType(1))
        # #sub_expr = dlfx.fem.Expression(petsc.ScalarType(1), S.element.interpolation_points())
        # s_zero_for_tracking_at_nodes.interpolate(sub_expr)
        # #s_zero_for_tracking_at_nodes.interpolate(sub_expr)
        
        #s_zero_for_tracking_at_nodes = dlfx.fem.Function(S)
        # c = dlfx.fem.Constant(domain, petsc.ScalarType(1))
        # sub_expr = dlfx.fem.Expression(c,S.element.interpolation_points())
        s_zero_for_tracking_at_nodes.interpolate(s)

        #s_zero_for_tracking_at_nodes.interpolate(s)
        x_tip, max_y, max_z, min_x, min_y, min_z = pp.crack_bounding_box_3D(domain, pf.get_dynamic_crack_locator_function(wm1, s_zero_for_tracking_at_nodes), comm)
        
        if rank == 0:
            print("Crack tip position x: " + str(x_tip))
            pp.write_to_graphs_output_file(outputfile_graph_path, t, J3D_glob_x, J3D_glob_y, J3D_glob_z, x_tip, xtip[0], Rx_top, Ry_top, Rz_top, dW, Work.value, A)
        
        wm1.x.array[:] = w.x.array[:]
        wrestart.x.array[:] = w.x.array[:]
        success_timestep_counter.value += 1.0
        if not int(success_timestep_counter.value) % int(postprocessing_interval.value) == 0:
            return 
        
        pp.write_phasefield_mixed_solution(domain, outputfile_xdmf_path, w, t, comm)

    def after_timestep_restart(t, dt, iters):
        w.x.array[:] = wrestart.x.array[:]
        
    def after_last_timestep():
        timer.stop()
        pp.write_phasefield_mixed_solution(domain, outputfile_xdmf_path, w, 0.0, comm)
        if rank == 0:
            runtime = timer.elapsed()
            sol.print_runtime(runtime)
            sol.write_runtime_to_newton_logfile(logfile_path, runtime)
            pp.print_graphs_plot(outputfile_graph_path, script_path, legend_labels=["Jx", "Jy", "Jz", "x_tip", "xtip", "Rx", "Ry", "Rz", "dW", "W", "A"])

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
        t=t_global
    )