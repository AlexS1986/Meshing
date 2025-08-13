import argparse
import os
import shutil
from datetime import datetime
from mpi4py import MPI
import pfmfrac_function as sim

# Initialize MPI
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

# Define argument parser
parser = argparse.ArgumentParser(description="Run a simulation with specified parameters and organize output files.")
parser.add_argument("--mesh_file", type=str, required=True, help="Name of the mesh file")
parser.add_argument("--lam_param", type=float, required=True, help="Lambda parameter")
parser.add_argument("--mue_param", type=float, required=True, help="Mu parameter")
parser.add_argument("--Gc_param", type=float, required=True, help="Gc parameter")
parser.add_argument("--eps_factor_param", type=float, required=True, help="Epsilon factor parameter")
parser.add_argument("--element_order", type=int, required=True, help="Element order")

# Parse arguments
args = parser.parse_args()

# Extract script path and name
script_path = os.path.dirname(__file__)
script_name_without_extension = os.path.splitext(os.path.basename(__file__))[0]

# Run the simulation
sim.run_simulation(args.mesh_file,
                   args.lam_param,
                   args.mue_param,
                   args.Gc_param,
                   args.eps_factor_param,
                   args.element_order,
                   comm)

# Put files in folders
current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
# Create a folder name based on the parameters, current time, and mesh file name
folder_name = (f"simulation_{current_time}_"
               f"{args.mesh_file}_"
               f"lam{args.lam_param}_mue{args.mue_param}_Gc{args.Gc_param}_eps{args.eps_factor_param}_order{args.element_order}")
comm.barrier()
if comm.Get_rank() == 0:
    # Create the directory if it doesn't exist
    if not os.path.exists(os.path.join(script_path, folder_name)):
        os.makedirs(os.path.join(script_path, folder_name))

    files_to_move = ["pfmfrac_function.xdmf", "pfmfrac_function.h5", "pfmfrac_function_graphs.txt", "pfmfrac_function_log.txt"]  # Replace with actual files

    for file in files_to_move:
        file_path = os.path.join(script_path, file)
        if os.path.exists(file_path):
            shutil.move(file_path, os.path.join(script_path, folder_name, os.path.basename(file)))
        else:
            print(f"File {file_path} does not exist and cannot be moved.")
