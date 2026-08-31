import sys
import glob
import os
import dolfinx as dlfx
from typing import Callable
from mpi4py import MPI

from dolfinx.fem.petsc import NonlinearProblem
from dolfinx.nls.petsc import NewtonSolver

import dolfinx.fem as fem

from dolfinx.fem.petsc import LinearProblem

from petsc4py import PETSc

import numpy as np

def print_time_and_dt(t: float, dt: float):
    print(' ')
    print('==================================================')
    print('Computing solution at time = {0:.4e}'.format(t))
    print('==================================================')
    print('Current time step dt = {0:.4e}'.format(dt))
    print('==================================================')
    print(' ')
    sys.stdout.flush()
    return True
    

def print_no_convergence(dt: float):
    print('-----------------------------')
    print('!!! NO CONVERGENCE => dt: ', dt)
    print('-----------------------------')
    sys.stdout.flush()
    return True
    
def print_increasing_dt(dt: float):
    print('-----------------------------')
    print('!!! Increasing dt to: ', dt)
    print('-----------------------------')
    sys.stdout.flush()
    return True
    
def print_decreasing_dt(dt: float):
    print('-----------------------------')
    print('!!! Decreasing dt to: ', dt)
    print('-----------------------------')
    sys.stdout.flush()
    return True
    
def print_timestep_overview(iters: int, converged: bool, restart_solution: bool):
    print('-----------------------------')
    print(' No. of iterations: ', iters)
    print(' Converged:         ', converged)
    print(' Restarting:        ', restart_solution)
    print('-----------------------------')
    sys.stdout.flush()
    return True

def print_timestep_overview_staggered(iters_u: int, iters_s: int, converged: bool, restart_solution: bool):
    print('-----------------------------')
    print(' No. of iterations u: ', iters_u)
    print(' No. of iterations s: ', iters_s)
    print(' Converged:         ', converged)
    print(' Restarting:        ', restart_solution)
    print('-----------------------------')
    sys.stdout.flush()
    return True

def print_runtime(runtime: float):
    print('') 
    print('-----------------------------')
    print('elapsed time:', runtime)
    print('-----------------------------')
    print('') 
    sys.stdout.flush()
    return True
        
def prepare_newton_logfile(logfile_path: str):
    for file in glob.glob(logfile_path):
        os.remove(logfile_path)
    logfile = open(logfile_path, 'w')  
    logfile.write('# time, dt, no. iterations (for convergence) \n')
    logfile.close()
    return True
    
def write_to_newton_logfile(logfile_path: str, t: float, dt: float, iters: int):
    logfile = open(logfile_path, 'a')
    logfile.write(str(t)+'  '+str(dt)+'  '+str(iters)+'\n')
    logfile.close()
    return True

def write_runtime_to_newton_logfile(logfile_path: str, runtime: float):
    logfile = open(logfile_path, 'a')
    logfile.write('# \n')
    logfile.write('# elapsed time:  '+str(runtime)+'\n')
    logfile.write('# \n')
    logfile.close()
    return True

def default_hook():
    return

def default_hook_tdt(t,dt):
    return

def default_hook_dt(dt):
    return

def default_hook_t(t):
    return

def default_hook_all(t,dt,iters):
    return

def solve_with_newton_adaptive_time_stepping_old(domain: dlfx.mesh.Mesh,
                                             w: dlfx.fem.Function, 
                                             Tend: float,
                                             dt: float,
                                             before_first_timestep_hook: Callable = default_hook,
                                             after_last_timestep_hook: Callable = default_hook,
                                             before_each_timestep_hook: Callable = default_hook_tdt, 
                                             get_residuum_and_gateaux: Callable = default_hook_dt,
                                             get_bcs: Callable = default_hook_t,
                                             after_timestep_success_hook: Callable = default_hook_all,
                                             after_timestep_restart_hook: Callable = default_hook_all,
                                             comm: MPI.Intercomm = MPI.COMM_WORLD,
                                             print = False):
    rank = comm.Get_rank()
    
    # time stepping
    max_iters = 8
    min_iters = 4
    dt_scale_down = 0.5
    dt_scale_up = 2.0
    
    t = 0
    trestart = 0
    delta_t = dlfx.fem.Constant(domain, dt)

    before_first_timestep_hook()

    while t < Tend:
        delta_t.value = dt

        before_each_timestep_hook(t,dt)
            
        [Res, dResdw] = get_residuum_and_gateaux(delta_t)
        
        bcs = get_bcs(t)
        
        # define nonlinear problem and solver
        problem = NonlinearProblem(Res, w, bcs, dResdw)
        solver = NewtonSolver(comm, problem)
        solver.report = True
        solver.max_it = max_iters
        
        ksp = solver.krylov_solver
        opts = PETSc.Options()
        option_prefix = ksp.getOptionsPrefix()
        opts[f"{option_prefix}ksp_type"] = "preonly"
        opts[f"{option_prefix}pc_type"] = "lu"
        opts[f"{option_prefix}pc_factor_mat_solver_type"] = "mumps"
        ksp.setFromOptions()
        
        # control adaptive time adjustment
        restart_solution = False
        converged = False
        iters = max_iters + 1 # iters always needs to be defined
        try:
            (iters, converged) = solver.solve(w)
        except RuntimeError:
            dt = dt_scale_down*dt
            restart_solution = True
            if rank == 0 and print:
                print_no_convergence(dt)
        
        if converged and iters < min_iters and t > np.finfo(float).eps:
            dt = dt_scale_up*dt
            if rank == 0 and print:
                print_increasing_dt(dt)
        if iters >= max_iters:
            dt = dt_scale_down*dt
            restart_solution = True
            if rank == 0 and print:
                print_decreasing_dt(dt)
                
        if not converged:
            restart_solution = True

        if rank == 0 and print:    
            print_timestep_overview(iters, converged, restart_solution)
            
      

        if not(restart_solution): # TODO and converged? 
            after_timestep_success_hook(t,dt,iters)
            trestart = t
            t = t+dt
        else:
            t = trestart+dt
            after_timestep_restart_hook(t,dt,iters)
    after_last_timestep_hook()

def solve_with_newton_adaptive_time_stepping(domain: dlfx.mesh.Mesh,
                                             w: dlfx.fem.Function, 
                                             Tend: float,
                                             dt: dlfx.fem.Constant,
                                             before_first_timestep_hook: Callable = default_hook,
                                             after_last_timestep_hook: Callable = default_hook,
                                             before_each_timestep_hook: Callable = default_hook_tdt, 
                                             get_residuum_and_gateaux: Callable = default_hook_dt,
                                             get_bcs: Callable = default_hook_t,
                                             after_timestep_success_hook: Callable = default_hook_all,
                                             after_timestep_restart_hook: Callable = default_hook_all,
                                             comm: MPI.Intercomm = MPI.COMM_WORLD,
                                             print_bool = False,
                                             solver : NewtonSolver = None,
                                             t: dlfx.fem.Constant = None,
                                             dt_max: dlfx.fem.Constant = None,
                                             dt_never_scale_up: bool = False,
                                             trestart: dlfx.fem.Constant = None,
                                             max_iters = 8,
                                             min_iters = 4, 
                                             arc_length=False,
                                             λ_arc_length=None,
                                             arc_length_ds=0.01):
    rank = comm.Get_rank()
    
    if print_bool:
        print_total_dofs(w, comm, rank)
    
    # time stepping
    # max_iters = 8
    # min_iters = 4
    dt_scale_down = 0.5
    dt_scale_up = 2.0
    
    if not dt_max is None:
        if dt.value >= dt_max.value:
            dt.value = dt_max.value
    
    # t = 0
    if t is None:
        t = dlfx.fem.Constant(domain, 0.0)
    if trestart is None:
        trestart = dlfx.fem.Constant(domain, 0.0)
    # delta_t = dlfx.fem.Constant(domain, dt)
    # dtt = dt.value 

    before_first_timestep_hook()

    # nn = 0
    choose_default_solver_each_time_step = False
    if solver is None:
            choose_default_solver_each_time_step = True
    
    if arc_length:
        arc = Crisfield(λ=λ_arc_length,u=w,ds=arc_length_ds)
        arc.initialise(ds=arc_length_ds)
    # gc.set_debug(gc.DEBUG_LEAK)
    while t.value < Tend:
        # if comm.Get_rank() == 0:
        #     print(f"time: {t.value} Tend: {Tend}")
        # if choose_default_solver_each_time_step and solver is not None:
        #     comm.Barrier()
        #     del solver
        #     gc.collect()
        #     comm.Barrier()
        # dt.value = dtt

        before_each_timestep_hook(t.value,dt.value)
            
        [Res, dResdw] = get_residuum_and_gateaux(dt)
        
        bcs = get_bcs(t.value)
        
        if choose_default_solver_each_time_step:
            if comm.Get_rank() == 0:
                print(f"NO SOLVER PROVIDED. Default solver created each time step")
            solver, problem = get_solver(w, comm, max_iters, Res, dResdw, bcs)
            
        
        # control adaptive time adjustment
        # restart_solution = False
        converged = False
        iters = 0 # iters always needs to be defined
        try:
            if arc_length:  
                arc.update_problem(problem)
                iters, converged = arc.solve_step()
                if rank == 0:
                    print(f"ARCLENGTH SOLVE: iters={iters}, converged={converged}, λ={arc.λ.value:.3e}, ds={arc.ds:.3e}")
            else:
                (iters, converged) = solver.solve(w)
        except RuntimeError as e:
            if comm.Get_rank() == 0:
                print(e)
            if not arc_length:
                dt.value = dt_scale_down*dt.value
                # restart_solution = True
                if rank == 0 and print_bool:
                    print_no_convergence(dt.value)
                
        
        if converged:
            after_timestep_success_hook(t.value,dt.value,iters)
        
        if not arc_length:
            if converged and iters < min_iters and t.value > np.finfo(float).eps and iters > 0:
                
                if not dt_never_scale_up:
                    if dt_max is None:
                        dt.value = dt_scale_up*dt.value
                        if rank == 0 and print_bool:
                            print_increasing_dt(dt.value)
                    else:
                        if not (dt_scale_up*dt.value > dt_max.value): 
                            dt.value = dt_scale_up*dt.value
                            if rank == 0 and print_bool:
                                print_increasing_dt(dt.value)
                        else:
                            dt.value = dt_max.value
                    
        restart_solution = False
        if arc_length:
            if converged:
                # do nothing arc length handles time update?
                a=1
            else:
                trestart.value = t.value
        else:
            if converged:
                #after_timestep_success_hook(t.value,dt.value,iters)
                trestart.value = t.value
                t.value = t.value+dt.value
            else:
                restart_solution = True
                after_timestep_restart_hook(t.value,dt.value,iters)
                t.value = trestart.value+dt.value
        
        if rank == 0 and print_bool:    
            print_timestep_overview(iters,converged,restart_solution) 
    after_last_timestep_hook()
    
    
    
def solve_staggered(domain: dlfx.mesh.Mesh,
                                             u: dlfx.fem.Function,
                                             s: dlfx.fem.Function, 
                                             Tend: float,
                                             dt: dlfx.fem.Constant,
                                             before_first_timestep_hook: Callable = default_hook,
                                             after_last_timestep_hook: Callable = default_hook,
                                             before_each_timestep_hook: Callable = default_hook_tdt, 
                                             get_residuum_and_gateaux_u: Callable = default_hook_dt,
                                             get_residuum_and_gateaux_s: Callable = default_hook_dt,
                                             get_bcs: Callable = default_hook_t,
                                             after_timestep_success_hook: Callable = default_hook_all,
                                             after_timestep_restart_hook: Callable = default_hook_all,
                                             comm: MPI.Intercomm = MPI.COMM_WORLD,
                                             print_bool = False,
                                             solver : NewtonSolver = None,
                                             t: dlfx.fem.Constant = None,
                                             trestart: dlfx.fem.Constant = None,
                                             dt_max: dlfx.fem.Constant = None,
                                             dt_never_scale_up: bool = False,
                                             max_iters = 20,
                                             min_iters = 1):
    rank = comm.Get_rank()
    
    dt_scale_down = 0.5
    dt_scale_up = 2.0
        
    # t = 0
    if t is None:
        t = dlfx.fem.Constant(domain, 0.0)
    if trestart is None:
        trestart = dlfx.fem.Constant(domain, 0.0)
    # delta_t = dlfx.fem.Constant(domain, dt)
    # dtt = dt.value 

    before_first_timestep_hook()

    # nn = 0
    choose_default_solver_each_time_step = False
    if solver is None:
            choose_default_solver_each_time_step = True

    while t.value < Tend:

        before_each_timestep_hook(t.value,dt.value)
            
        
        
        bcs_u, bcs_s = get_bcs(t.value)
            
        
        # control adaptive time adjustment
        # restart_solution = False
        converged = False
        converged_u  = False
        converged_s = False
        iters_u = 0 # iters always needs to be defined
        iters_s = 0
        try:
            [Res_u,  dRes_uDu] = get_residuum_and_gateaux_u(dt)
            solver_u, problem_u = get_solver(u, comm, max_iters, Res_u, dRes_uDu, bcs_u)
            (iters_u, converged_u) = solver_u.solve(u)
            
            [Res_s,  dRes_sDs] = get_residuum_and_gateaux_s(dt)
            solver_s, problem_s = get_solver(s, comm, max_iters, Res_s, dRes_sDs, bcs_s)
            (iters_s, converged_s) = solver_s.solve(s)
            a=1
        except RuntimeError as e:
                if comm.Get_rank() == 0:
                    print(e)
                    print_no_convergence(dt.value)
                dt.value = dt_scale_down*dt.value
                
        converged = converged_u and converged_s
        if rank == 0 and print_bool:
            print(f"converged iters_u : {iters_u} iters_s : {iters_s}")
        
        if converged:
            after_timestep_success_hook(t.value,dt.value,iters_u)
            
             
        if converged and iters_u + iters_s < min_iters and t.value > np.finfo(float).eps and iters_u + iters_s > 0:
                
                    if dt_max is None:
                        dt.value = dt_scale_up*dt.value
                        if rank == 0 and print_bool:
                            print_increasing_dt(dt.value)
                    else:
                        if not (dt_scale_up*dt.value > dt_max.value): 
                            dt.value = dt_scale_up*dt.value
                            if rank == 0 and print_bool:
                                print_increasing_dt(dt.value)
                        else:
                            dt.value = dt_max.value
        
                    
        restart_solution = False
        if converged:
                #after_timestep_success_hook(t.value,dt.value,iters)
                trestart.value = t.value
                t.value = t.value+dt.value
        else:   
                
                restart_solution = True
                after_timestep_restart_hook(t.value,dt.value,iters_u+iters_s)
                t.value = trestart.value+dt.value
        
        if rank == 0 and print_bool:    
            print_timestep_overview_staggered(iters_u,iters_s,converged,restart_solution)
    after_last_timestep_hook()

def print_total_dofs(w, comm, rank):
    num_dofs = np.shape(w.x.array[:])[0]
    comm.Barrier()
    num_dofs_all = comm.allreduce(num_dofs, op=MPI.SUM)
    comm.Barrier()
    if rank == 0:
        print('solving fem problem with', num_dofs_all,'dofs ...')
        sys.stdout.flush()

# def solve_with_newton_adaptive_time_stepping(domain: dlfx.mesh.Mesh,
#                                              w: dlfx.fem.Function, 
#                                              Tend: float,
#                                              dt: dlfx.fem.Constant,
#                                              before_first_timestep_hook: Callable = default_hook,
#                                              after_last_timestep_hook: Callable = default_hook,
#                                              before_each_timestep_hook: Callable = default_hook_tdt, 
#                                              get_residuum_and_gateaux: Callable = default_hook_dt,
#                                              get_bcs: Callable = default_hook_t,
#                                              after_timestep_success_hook: Callable = default_hook_all,
#                                              after_timestep_restart_hook: Callable = default_hook_all,
#                                              comm: MPI.Intercomm = MPI.COMM_WORLD,
#                                              print_bool = False,
#                                              solver : NewtonSolver = None,
#                                              t: dlfx.fem.Constant = None):
#     rank = comm.Get_rank()
    
#     # time stepping
#     max_iters = 8
#     min_iters = 4
#     dt_scale_down = 0.5
#     dt_scale_up = 2.0
    
#     # t = 0
#     if t is None:
#         t = dlfx.fem.Constant(domain, 0.0)
#     trestart = dlfx.fem.Constant(domain, 0.0)
#     # delta_t = dlfx.fem.Constant(domain, dt)
#     dtt = dt.value 

#     before_first_timestep_hook()

#     # nn = 0
    
#     while t.value < Tend:
#         dt.value = dtt

#         before_each_timestep_hook(t.value,dtt)
            
#         [Res, dResdw] = get_residuum_and_gateaux(dt)
        
#         bcs = get_bcs(t.value)
        
#         if solver is None:
#             if comm.Get_rank() == 0:
#                 print_bool(f"No solver provided. Default solver chosen")
#             solver = get_solver(w, comm, max_iters, Res, dResdw, bcs)
        
#         # control adaptive time adjustment
#         restart_solution = False
#         converged = False
#         iters = max_iters + 1 # iters always needs to be defined
#         try:
#             (iters, converged) = solver.solve(w)
#             # if nn < 3:
#             #     iters = 9
#             #     converged = False
#             #     nn = nn +1
#             #     raise RuntimeError()
#             # else:
#             #     a = 1
#         except RuntimeError:
#             dtt = dt_scale_down*dtt
#             restart_solution = True
#             if rank == 0 and print_bool:
#                 print_no_convergence(dtt)
        
#         if converged and iters < min_iters and t.value > np.finfo(float).eps:
#             dtt = dt_scale_up*dtt
#             if rank == 0 and print_bool:
#                 print_increasing_dt(dtt)
                
#         if iters > max_iters:
#             dtt = dt_scale_down*dtt
#             restart_solution = True
#             if rank == 0 and print_bool:
#                 print_decreasing_dt(dtt)
                
#         if not converged:
#             restart_solution = True

#         if rank == 0 and print_bool:    
#             print_timestep_overview(iters, converged, restart_solution)
            
#         if not(restart_solution): 
#             after_timestep_success_hook(t.value,dtt,iters)
#             trestart.value = t.value
#             t.value = t.value+dtt
#         else:
#             after_timestep_restart_hook(t.value,dtt,iters)
#             t.value = trestart.value+dtt    
#     after_last_timestep_hook()

def get_solver(w, comm, max_iters, Res, dResdw, bcs):
    if dResdw is not None:
        problem = NonlinearProblem(Res, w, bcs, dResdw)
    else:
        #problem = NonlinearProblem(Res, w, bcs)
        problem = NonlinearProblem(Res, w, bcs)
        
    solver = NewtonSolver(comm, problem)
    solver.report = True
    solver.max_it = max_iters

    # ksp = solver.krylov_solver
    # opts = PETSc.Options()
    # option_prefix = ksp.getOptionsPrefix()
    # opts[f"{option_prefix}ksp_type"] = "fcg"
    # # opts[f"{option_prefix}pc_type"] = "lu"
    # opts[f"{option_prefix}pc_factor_mat_solver_type"] = "mumps"
    # ksp.setFromOptions()
    
    if comm.Get_rank() == 0:
        ksp = solver.krylov_solver
        print("Default KSP Type:", ksp.getType())
        print("Default PC Type:", ksp.getPC().getType())
    
    return solver, problem

    
    
class CustomLinearProblem(fem.petsc.LinearProblem):
        def assemble_rhs(self, u=None):
            """Assemble right-hand side and lift Dirichlet bcs.

            Parameters
            ----------
            u : dlfx.fem.Function, optional
                For non-zero Dirichlet bcs u_D, use this function to assemble rhs with the value u_D - u_{bc}
                where u_{bc} is the value of the given u at the corresponding. Typically used for custom Newton methods
                with non-zero Dirichlet bcs.
            """

            # Assemble rhs
            with self._b.localForm() as b_loc:
                b_loc.set(0)
            fem.petsc.assemble_vector(self._b, self._L)

            # Apply boundary conditions to the rhs
            x0 = [] if u is None else [u.vector]
            fem.petsc.apply_lifting(self._b, [self._a], bcs=[self.bcs], x0=x0, scale=1.0)
            self._b.ghostUpdate(addv=PETSc.InsertMode.ADD, mode=PETSc.ScatterMode.REVERSE)
            x0 = None if u is None else u.vector
            fem.petsc.set_bc(self._b, self.bcs, x0, scale=1.0)

        def assemble_lhs(self):
            self._A.zeroEntries()
            fem.petsc.assemble_matrix_mat(self._A, self._a, bcs=self.bcs)
            self._A.assemble()

        def solve_system(self):
            # Solve linear system and update ghost values in the solution
            self._solver.solve(self._b, self._x)
            self.u.x.scatter_forward()
            
            
def solve_with_custom_newton_adaptive_time_stepping(domain: dlfx.mesh.Mesh,
                                             sol: dlfx.fem.Function,
                                             dsol: dlfx.fem.Function,  
                                             Tend: float,
                                             dt: float,
                                             before_first_timestep_hook: Callable = default_hook,
                                             after_last_timestep_hook: Callable = default_hook,
                                             before_each_timestep_hook: Callable = default_hook_tdt, 
                                             get_residuum_and_gateaux: Callable = default_hook_dt,
                                             get_bcs: Callable = default_hook_t,
                                             after_iteration_hook: Callable = default_hook, 
                                             after_timestep_success_hook: Callable = default_hook_all,
                                             after_timestep_restart_hook: Callable = default_hook_all,
                                             comm: MPI.Intercomm = MPI.COMM_WORLD,
                                             print_bool = False):
    rank = comm.Get_rank()
    
    # time stepping
    max_iters = 8
    min_iters = 4
    dt_scale_down = 0.5
    dt_scale_up = 2.0
    
    t = 0.00000000001
    trestart = 0
    delta_t = dlfx.fem.Constant(domain, dt)

    before_first_timestep_hook()

    while t < Tend:
        delta_t.value = dt

        before_each_timestep_hook(t,dt)
            
       
        
        
        # define nonlinear problem and solver
        # problem = NonlinearProblem(Res, sol, bcs, dResdw)
        # solver = NewtonSolver(comm, problem)
        # solver.report = True
        # solver.max_it = max_iters
        
        # # control adaptive time adjustment
        restart_solution = False
        converged = False
        iters = max_iters + 1 # iters always needs to be defined
        try:
            [Res, dResdw] = get_residuum_and_gateaux(delta_t)
            bcs = get_bcs(t)
            Jacobi = dlfx.fem.form(dResdw)
            Residual_form = dlfx.fem.form(Res)
            parameter_handover_after_last_iteration, iters, converged = solve_with_custom_newton(Jacobi,Residual_form,sol,dsol,comm,bcs,after_iteration_hook=after_iteration_hook, print_bool=print_bool)
        except RuntimeError:
            dt = dt_scale_down*dt
            restart_solution = True
            if rank == 0 and print_bool:
                print_no_convergence(dt)
        
        if converged and iters < min_iters and t > np.finfo(float).eps:
            dt = dt_scale_up*dt
            if rank == 0 and print_bool:
                print_increasing_dt(dt)
        if iters >= max_iters:
            dt = dt_scale_down*dt
            restart_solution = True
            if rank == 0 and print_bool:
                print_decreasing_dt(dt)
                
        if not converged:
            restart_solution = True

        if rank == 0 and print_bool:    
            print_timestep_overview(iters, converged, restart_solution)

       

        if not(restart_solution):
            # after_timestep_success_hook(t,dt,iters)
            after_timestep_success_hook(t,dt,iters,parameter_handover_after_last_iteration)
            trestart = t
            t = t+dt
        else:
            t = trestart+dt
            after_timestep_restart_hook(t,dt,iters)
    after_last_timestep_hook() 
    
    
def solve_with_newton(domain, sol, dsol, Nitermax, tol,
                      load_steps,  
                      before_first_timestep_hook: Callable, 
                      before_each_timestep_hook: Callable, 
                      after_last_timestep_hook: Callable, 
                      get_residuum_and_tangent: Callable, 
                      get_bcs: Callable, 
                      after_iteration_hook: Callable, 
                      after_timestep_success_hook: Callable, 
                      comm, print_bool=False):
    
        before_first_timestep_hook()            
        for i, t in enumerate(load_steps):
            
            
            before_each_timestep_hook(t,-1.0)
            
            Residual, tangent_form = get_residuum_and_tangent(-1.0)
            
            bcs = get_bcs(t)
            # tangent_problem = LinearProblem(tangent_form,-Residual,bcs,du,petsc_options={
            # "ksp_type": "preonly",
            # "pc_type": "lu",
            # "pc_factor_mat_solver_type": "mumps",
            # })
            
            Jacobi = dlfx.fem.form(tangent_form)
            Residual_form = dlfx.fem.form(Residual)
            parameter_handover_after_last_iteration, niter, converged = solve_with_custom_newton(Jacobi,Residual_form,sol,dsol,comm,bcs,after_iteration_hook=after_iteration_hook, print_bool=print_bool)
            
            if print_bool and comm.Get_rank() == 0:
                print_timestep_overview(niter,converged=converged,restart_solution=False)
                
            after_timestep_success_hook(t,-1.0,niter,parameter_handover_after_last_iteration)
            
        #     tangent_problem = CustomLinearProblem(
        #     tangent_form,
        #     -Residual,
        #     u=du,
        #     bcs=bcs,
        #     petsc_options={
        #     "ksp_type": "preonly",
        #     "pc_type": "lu",
        #     "pc_factor_mat_solver_type": "mumps",
        #     }
        #     )
        
        
        # # compute the residual norm at the beginning of the load step
        #     tangent_problem.assemble_rhs()
        #     nRes0 = tangent_problem._b.norm()
        #     nRes = nRes0
            

        #     niter = 0
        #     while nRes / nRes0 > tol and niter < Nitermax:
        #     # update residual and tangent
        #         Residual, tangent_form = get_residuum_and_tangent()
        #         # Residual, tangent_form = alex.plasticity.get_residual_and_tangent(n, loading, as_3D_tensor(sig_np1), u_, v, eps, ds(3), dx, lmbda,mu,as_3D_tensor(N_np1),beta,H)
        #     # tangent_form = ufl.inner(eps(v), sigma_tang(eps(u_))) * dx
            
        #     # solve for the displacement correction
        #         tangent_problem.assemble_lhs()
        #         tangent_problem.solve_system()
                
        #         du = tangent_problem.solve()

        #     # update the displacement increment with the current correction
        #         parameter_handover_after_last_iteration = after_iteration_hook()

        #     # compute the new residual
        #         tangent_problem.assemble_rhs()
        #         nRes = tangent_problem._b.norm()

        #         niter += 1
                
        
        #     if niter < Nitermax:
        #         after_timestep_success_hook(t,i,niter,parameter_handover_after_last_iteration)
        #     else:
        #         raise Exception("No convergence")
        
        after_last_timestep_hook()
        
        

# def solve_with_custom_newton(jacobian, residual, sol, dsol, comm, bcs, after_iteration_hook, print_bool=False):
#     # def assemble_rhs_and_apply_bcs(jacobian, residual, uh, bcs, L):
#     #     dlfx.fem.petsc.assemble_vector(L, residual)
#     #     L.ghostUpdate(addv=PETSc.InsertMode.ADD, mode=PETSc.ScatterMode.REVERSE)
#     #     L.scale(-1)

#     #         # Compute b - J(u_D-u_(i-1))
#     #     dlfx.fem.petsc.apply_lifting(L, [jacobian], [bcs], x0=[uh.vector], scale=1)
#     #         # Set du|_bc = u_{i-1}-u_D
#     #     dlfx.fem.petsc.set_bc(L, bcs, uh.vector, 1.0)
#     #     L.ghostUpdate(addv=PETSc.InsertMode.INSERT_VALUES, mode=PETSc.ScatterMode.FORWARD)
    
    
    
#     A = dlfx.fem.petsc.create_matrix(jacobian)
#     L = dlfx.fem.petsc.create_vector(residual)
    
#     solver = PETSc.KSP().create(comm)
#     solver.setOperators(A)
    
    
#     i = 0
#     max_iterations = 25
#     du_norm = []
    
#     # assemble_rhs_and_apply_bcs(jacobian, residual, uh, bcs, L)
#     # nRes0 = 100000000
    
#     converged = False
#     while i < max_iterations:

        
#     # Assemble Jacobian and residual
#         with L.localForm() as loc_L:
#             loc_L.set(0)
#         A.zeroEntries()
#         dlfx.fem.petsc.assemble_matrix(A, jacobian, bcs=bcs)
#         A.assemble()
        
#         dlfx.fem.petsc.assemble_vector(L, residual)
#         L.ghostUpdate(addv=PETSc.InsertMode.ADD, mode=PETSc.ScatterMode.REVERSE)
#         L.scale(-1)
        
#         # check for convergence
#         if i != 0:
#             if (np.isclose(np.sum(dsol.x.array),0.0) and np.isclose(np.sum(L.array),0.0) ) or correction_norm/u0 < 1e-10:
#                 converged = True
#                 break

#             # Compute b - J(u_D-u_(i-1))
#         dlfx.fem.petsc.apply_lifting(L, [jacobian], [bcs], x0=[sol.vector], scale=1)
#             # Set du|_bc = u_{i-1}-u_D
#         dlfx.fem.petsc.set_bc(L, bcs, sol.vector, 1.0)
#         L.ghostUpdate(addv=PETSc.InsertMode.INSERT_VALUES, mode=PETSc.ScatterMode.FORWARD)
#         # assemble_rhs_and_apply_bcs(jacobian, residual, uh, bcs, L)
        
#         # Solve linear problem
#         solver.solve(L, dsol.vector)
#         dsol.x.scatter_forward()

#         # Update u_{i+1} = u_i + delta u_i
#         sol.x.array[:] += dsol.x.array
#         sol.x.scatter_forward()
        
#         if i == 0:
#             u0 = sol.vector.norm(0)
#         i += 1
        
#         parameters = after_iteration_hook()

#         # Compute norm of update
#         correction_norm = dsol.vector.norm(0)
        

#         # Compute L2 error comparing to the analytical solution
#         du_norm.append(correction_norm)

#         if print_bool and comm.Get_rank() == 0:
#             print(f"Converged: {converged}")
#             # print(f"Iteration {i}: Correction norm {correction_norm}")
#             print(f"Iteration {i}: Relative correction norm {correction_norm/u0 }")
#             sys.stdout.flush()
#         # if correction_norm < 1e-10:
#         #     converged = True
#         #     break
#         #     # return parameters, i
#     if converged:
#         if print_bool and comm.Get_rank() == 0:
#             print(f"Converged: { converged }")
#             # print(f"Iteration {i}: Correction norm {correction_norm}")
#             print(f"Iteration {i}: Relative correction norm {correction_norm/u0 }")
#             sys.stdout.flush()
#         return parameters, i, converged
#     # if comm.Get_rank() == 0:
#     #     raise Exception("Newton not converged")
#     return parameters, i, converged


def solve_with_custom_newton(jacobian, residual, sol, dsol, comm, bcs, after_iteration_hook, print_bool=False, max_iterations = 8):
    A = dlfx.fem.petsc.create_matrix(jacobian)
    L = dlfx.fem.petsc.create_vector(residual)
    
    solver = PETSc.KSP().create(comm)
    solver.setOperators(A)
    
    i = 0
    # max_iterations = 8
    du_norm = []
    
    converged = False
    epsilon = 1e-16  # Small value to prevent division by zero

    while i < max_iterations:
        with L.localForm() as loc_L:
            loc_L.set(0)
        A.zeroEntries()
        dlfx.fem.petsc.assemble_matrix(A, jacobian, bcs=bcs)
        A.assemble()
        
        dlfx.fem.petsc.assemble_vector(L, residual)
        L.ghostUpdate(addv=PETSc.InsertMode.ADD, mode=PETSc.ScatterMode.REVERSE)
        L.scale(-1)

        # Apply lifting and set boundary conditions
        dlfx.fem.petsc.apply_lifting(L, [jacobian], [bcs], x0=[sol.vector], scale=1)
        dlfx.fem.petsc.set_bc(L, bcs, sol.vector, 1.0)
        L.ghostUpdate(addv=PETSc.InsertMode.INSERT_VALUES, mode=PETSc.ScatterMode.FORWARD)

        # Solve linear problem
        solver.solve(L, dsol.vector)
        dsol.x.scatter_forward()

        # Update solution
        sol.x.array[:] += dsol.x.array
        sol.x.scatter_forward()

        # Compute norms for convergence check
        correction_norm = dsol.vector.norm()
        residual_norm = np.linalg.norm(np.array(L.array))
        
        if i == 0:
            initial_residual_norm = max(residual_norm, epsilon)
            initial_solution_norm = max(sol.vector.norm(), epsilon)

        # Convergence criteria
        relative_correction_norm = correction_norm / initial_solution_norm
        relative_residual_norm = residual_norm / initial_residual_norm

        if print_bool and comm.Get_rank() == 0:
            print(f"Iteration {i}: Correction norm = {correction_norm}, Residual norm = {residual_norm}",flush=True)
            print(f"Iteration {i}: Relative correction norm = {relative_correction_norm}, Relative residual norm = {relative_residual_norm}",flush=True)
            sys.stdout.flush()


        
        i += 1
        parameters = after_iteration_hook()
        
        # Check convergence
        if relative_residual_norm < 1e-10 or relative_correction_norm < 1e-10:
            converged = True
            break

    if converged:
        if print_bool and comm.Get_rank() == 0:
            print(f"Converged after {i} iterations.")
        return parameters, i, converged

    if comm.Get_rank() == 0:
        print("Newton method did not converge within the maximum number of iterations.")
    return parameters, i, converged



def update_newmark(beta, gamma, dt, u, um1, vm1, am1, is_ufl=True):
    if is_ufl:
        acc = 1.0/(beta*dt*dt)*(u-um1) - 1.0/(beta*dt)*vm1-(0.5-beta)/beta*am1
        vel = gamma/(beta*dt)*(u-um1)+(1.0-gamma/beta)*vm1+dt*(beta-0.5*gamma)/beta*am1
    else: 
        acc = 1.0/(beta*dt*dt)*(u.x.array[:]-um1.x.array[:])-1.0/(beta*dt)*vm1.x.array[:]-(0.5-beta)/beta*am1.x.array[:]
        vel = gamma/(beta*dt)*(u.x.array[:]-um1.x.array[:])+(1.0-gamma/beta)*vm1.x.array[:]+dt*(beta-0.5*gamma)/beta*am1.x.array[:]
    return acc, vel 

from petsc4py import PETSc
import numpy as np
import dolfinx


def explain_snes_reason(reason: int) -> str:
    """Return a human-readable explanation for PETSc SNES convergence reason."""
    reasons = {
        # --- Converged ---
        PETSc.SNES.ConvergedReason.CONVERGED_FNORM_ABS: "Converged: residual norm below absolute tolerance",
        PETSc.SNES.ConvergedReason.CONVERGED_FNORM_RELATIVE: "Converged: residual norm reduced by relative tolerance",
        PETSc.SNES.ConvergedReason.CONVERGED_SNORM_RELATIVE: "Converged: step norm below tolerance (stationary point)",
        PETSc.SNES.ConvergedReason.CONVERGED_ITS: "Converged: reached requested iteration count",

        # --- Diverged ---
        PETSc.SNES.ConvergedReason.DIVERGED_FUNCTION_DOMAIN: "Diverged: function not defined at current iterate (NaN or domain error)",
        PETSc.SNES.ConvergedReason.DIVERGED_FUNCTION_COUNT: "Diverged: too many function evaluations",
        PETSc.SNES.ConvergedReason.DIVERGED_LINEAR_SOLVE: "Diverged: linear solve failed (KSP did not converge)",
        PETSc.SNES.ConvergedReason.DIVERGED_LOCAL_MIN: "Diverged: found a local minimum (not a root)",
        PETSc.SNES.ConvergedReason.DIVERGED_MAX_IT: "Diverged: reached maximum iterations",
    }

    # Unknown reason (0 = not yet converged)
    if reason == 0:
        return "Not yet converged: solver still running"

    # If PETSc reason is known
    if reason in reasons:
        return reasons[reason]

    # Fallback for unknown codes
    return f"Unknown SNES reason code: {reason}"


import numpy as np
from petsc4py import PETSc
import dolfinx
from dolfinx.fem.petsc import create_vector, create_matrix

def explain_snes_reason(reason: int) -> str:
    reasons = {
        PETSc.SNES.ConvergedReason.CONVERGED_FNORM_ABS: "Converged: residual norm below absolute tolerance",
        PETSc.SNES.ConvergedReason.CONVERGED_FNORM_RELATIVE: "Converged: residual norm reduced by relative tolerance",
        PETSc.SNES.ConvergedReason.CONVERGED_SNORM_RELATIVE: "Converged: step norm below tolerance (stationary point)",
        PETSc.SNES.ConvergedReason.CONVERGED_ITS: "Converged: reached requested iteration count",
        PETSc.SNES.ConvergedReason.CONVERGED_TR_DELTA: "Converged: trust region too small",
        PETSc.SNES.ConvergedReason.DIVERGED_FUNCTION_DOMAIN: "Diverged: function not defined at current iterate (NaN or domain error)",
        PETSc.SNES.ConvergedReason.DIVERGED_FUNCTION_COUNT: "Diverged: too many function evaluations",
        PETSc.SNES.ConvergedReason.DIVERGED_LINEAR_SOLVE: "Diverged: linear solve failed (KSP did not converge)",
        PETSc.SNES.ConvergedReason.DIVERGED_FNORM_INFINITY: "Diverged: residual norm is infinite or NaN",
        PETSc.SNES.ConvergedReason.DIVERGED_LS_FAILURE: "Diverged: line search failed",
        PETSc.SNES.ConvergedReason.DIVERGED_LOCAL_MIN: "Diverged: found a local minimum (not a root)",
        PETSc.SNES.ConvergedReason.DIVERGED_MAX_IT: "Diverged: reached maximum iterations",
        PETSc.SNES.ConvergedReason.DIVERGED_BREAKDOWN: "Diverged: numerical breakdown (unknown failure)",
    }
    if reason == 0:
        return "Not yet converged: solver still running"
    return reasons.get(reason, f"Unknown SNES reason code: {reason}")

import numpy as np
from petsc4py import PETSc
import dolfinx
from dolfinx.fem.petsc import create_vector, create_matrix

# -----------------------------
def explain_snes_reason(reason: int) -> str:
    reasons = {
        PETSc.SNES.ConvergedReason.CONVERGED_FNORM_ABS: "Converged: residual norm below absolute tolerance",
        PETSc.SNES.ConvergedReason.CONVERGED_FNORM_RELATIVE: "Converged: residual norm reduced by relative tolerance",
        PETSc.SNES.ConvergedReason.CONVERGED_SNORM_RELATIVE: "Converged: step norm below tolerance (stationary point)",
        PETSc.SNES.ConvergedReason.CONVERGED_ITS: "Converged: reached requested iteration count",
        PETSc.SNES.ConvergedReason.DIVERGED_FUNCTION_DOMAIN: "Diverged: function not defined at current iterate (NaN or domain error)",
        PETSc.SNES.ConvergedReason.DIVERGED_FUNCTION_COUNT: "Diverged: too many function evaluations",
        PETSc.SNES.ConvergedReason.DIVERGED_LINEAR_SOLVE: "Diverged: linear solve failed (KSP did not converge)",
        PETSc.SNES.ConvergedReason.DIVERGED_LOCAL_MIN: "Diverged: found a local minimum (not a root)",
        PETSc.SNES.ConvergedReason.DIVERGED_MAX_IT: "Diverged: reached maximum iterations",
    }
    if reason == 0:
        return "Not yet converged"
    return reasons.get(reason, f"Unknown SNES reason code: {reason}")

# -----------------------------
class Crisfield:
    def __init__(self, λ: dolfinx.fem.Constant, u: dolfinx.fem.Function,
                 psi=1.0, ds=0.1, monitor=None, inner=None):
        """
        Crisfield arc-length continuation.
        Problem can be attached later.
        """
        self.λ = λ
        self.u = u
        self.psi = psi
        self.ds = ds
        self.monitor = monitor
        self.inner = inner if inner is not None else lambda v1, v2: v1.dot(v2)

        self.problem = None

        # SNES created at initialization
        self.comm = u.function_space.mesh.comm
        self.snes = PETSc.SNES().create(self.comm)
        self.snes.setType("newtontr")

        # Work vectors, initialized when problem is attached
        self.b = None
        self.A = None
        self.dFdλ = None
        self.dx = None
        self.Δx = None
        self.δx_dFdλ = None

        self.dλ = dolfinx.fem.Constant(λ._ufl_domain, λ.value)
        self.Δλ = dolfinx.fem.Constant(λ._ufl_domain, λ.value)

    # -----------------------------
    def update_problem(self, problem):
        """Attach or update nonlinear problem."""
        self.problem = problem
        PETSc.Sys.Print("[Crisfield] Problem attached/updated.")

        # Create work vectors if first time
        if self.b is None:
            self.b = create_vector(self.problem.L)
            self.A = create_matrix(self.problem.a)
            self.dFdλ = self.b.copy()
            self.dx = self.b.copy()
            self.Δx = self.b.copy()
            self.δx_dFdλ = self.b.copy()

        # Attach callbacks
        self.snes.setFunction(lambda snes, x, b: self.problem.F(x, b), self.b)
        self.snes.setJacobian(lambda snes, x, A, B: self.problem.J(x, A), self.A)

        # Attach Crisfield update
        self.snes.setUpdate(Crisfield.update, kargs=dict(continuation=self))

    # -----------------------------
    def initialise(self, ds=None, λ=None, psi=None):
        if ds is not None:
            self.ds = ds
        if psi is not None:
            self.psi = psi
        if λ is not None:
            self.λ.value = λ
        if self.dx:
            with self.dx.localForm() as dx_local:
                dx_local.set(0.0)
        self.dλ.value = self.ds

    # -----------------------------
    def solve_step(self, ds=None, zero_x_predictor=False,
               ds_min=1e-4, ds_max=0.5, ds_increase_factor=1.2, ds_decrease_factor=0.5,
               iter_increase=4, iter_decrease=8):
        """Solve one Crisfield step, adaptively updating ds."""
        if self.problem is None:
            raise RuntimeError("No problem attached. Use update_problem() first.")
        if ds is not None:
            self.ds = ds

        # Predictor step: update u only, no change to λ
        if zero_x_predictor:
            with self.Δx.localForm() as Δx_local:
                Δx_local.set(0.0)
        else:
            with self.dx.localForm() as dx_local, self.Δx.localForm() as Δx_local:
                dx_local.copy(Δx_local)

        self.u.vector.axpy(1.0, self.Δx)  # predictor update

        PETSc.Sys.Print(f"[Crisfield] Trying step with ds={self.ds:.3e}")
        self.snes.solve(None, self.u.vector)

        reason = self.snes.getConvergedReason()
        iters = self.snes.getIterationNumber()
        reason_str = explain_snes_reason(reason)
        PETSc.Sys.Print(f"[Crisfield] step: iters={iters}, reason={reason_str} ({reason})")
        converged = reason > 0

        if converged:
            # Update λ and Δλ only after successful convergence
            self.Δλ.value = self.dλ.value
            self.λ.value += self.Δλ.value

            Crisfield.update(self.snes, iters, self)
            with self.dx.localForm() as dx_local, self.Δx.localForm() as Δx_local:
                Δx_local.copy(dx_local)
            self.dλ.value = self.Δλ.value

            # Adaptive ds
            if iters <= iter_increase:
                self.ds = min(self.ds * ds_increase_factor, ds_max)
            elif iters >= iter_decrease:
                self.ds = max(self.ds * ds_decrease_factor, ds_min)

            return iters, True
        else:
            # Reduce ds and reset predictor, λ unchanged
            self.ds = max(self.ds * ds_decrease_factor, ds_min)
            with self.Δx.localForm() as Δx_local:
                Δx_local.set(0.0)
            return iters, False

    # -----------------------------
    @staticmethod
    def update(snes, snes_iteration, continuation):
        """Crisfield arc-length update."""
        Δx, dx = continuation.Δx, continuation.dx
        Δλ, dλ = continuation.Δλ.value.item(), continuation.dλ.value.item()
        dFdλ, δx_dFdλ = continuation.dFdλ, continuation.δx_dFdλ
        psi, ds = continuation.psi, continuation.ds

        δx = snes.getSolutionUpdate()
        if snes_iteration == 0:
            with δx.localForm() as δx_local:
                δx_local.set(0.0)
        Δx.axpy(-1.0, δx)

        if snes.getKSP().getConvergedReason() != 0 and snes_iteration > 0:
            snes.getKSP().solve(-dFdλ, δx_dFdλ)
        else:
            with δx_dFdλ.localForm() as dx_local:
                dx_local.set(0.0)

        dFdλ_inner = psi**2 * continuation.inner(dFdλ, dFdλ)
        a1 = continuation.inner(δx_dFdλ, δx_dFdλ) + dFdλ_inner
        a2 = continuation.inner(Δx, δx_dFdλ) + Δλ * dFdλ_inner
        a3 = continuation.inner(Δx, Δx) + Δλ**2 * dFdλ_inner - ds**2

        if a1 > 0.0:
            arg = a2**2 - a1 * a3
            if arg < 0:
                raise RuntimeError("Arc-length quadratic has no real roots.")
            sqr = np.sqrt(arg)
            δλ1 = (-a2 - sqr) / a1
            δλ2 = (-a2 + sqr) / a1
            sign = np.sign(continuation.inner(δx_dFdλ, dx) + dλ * dFdλ_inner)
            δλ = δλ1 if δλ1 * sign > δλ2 * sign else δλ2
        else:
            δλ = -a3 / (2 * a2) if abs(a2) > 1e-14 else 0.0

        continuation.Δλ.value += δλ
        continuation.Δx.axpy(δλ, δx_dFdλ)
        continuation.λ.value += δλ
        snes.getSolution().axpy(δλ, δx_dFdλ)



