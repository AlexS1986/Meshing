import argparse
import json
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
parser.add_argument("--material", type=str, default="std", help="Material set selected from fracture.material_sets")
parser.add_argument("--fracture-toughness", type=str, default=None, help="Gc set selected from fracture.fracture_toughness_sets")
parser.add_argument("--config", type=str, default=None, help="Config JSON; defaults to config.json beside this script")
parser.add_argument("--lam_param", type=float, default=1.0, help="Fallback Lambda parameter")
parser.add_argument("--mue_param", type=float, default=1.0, help="Fallback Mu parameter")
parser.add_argument("--Gc_param", type=float, required=True, help="Gc parameter")
parser.add_argument("--eps_factor_param", type=float, required=True, help="Epsilon factor parameter")
parser.add_argument("--element_order", type=int, required=True, help="Element order")

# Parse arguments
args = parser.parse_args()

# Extract script path and name
script_path = os.path.dirname(__file__)
script_name_without_extension = os.path.splitext(os.path.basename(__file__))[0]


def material_parameters():
    config_path = args.config or os.path.join(script_path, "config.json")
    config = {}
    if os.path.isfile(config_path):
        with open(config_path, "r") as handle:
            config = json.load(handle)

    fracture = config.get("fracture", {})
    material_sets = fracture.get("material_sets", {})
    material = material_sets.get(args.material)
    if material is None:
        material = fracture.get("default_material")
    toughness_name = args.fracture_toughness or fracture.get("fracture_toughness", "alsi10mg_as_built")
    toughness_sets = fracture.get("fracture_toughness_sets", {})
    toughness = toughness_sets.get(toughness_name)
    if toughness_sets and toughness is None:
        choices = ", ".join(sorted(toughness_sets))
        raise ValueError(f"Unknown fracture toughness '{toughness_name}'. Choose from: {choices}")
    if toughness is None:
        Gc = args.Gc_param
        toughness_source_doi = None
    else:
        Gc = float(toughness["Gc"])
        toughness_source_doi = toughness.get("source_doi")

    if material is None:
        return args.lam_param, args.mue_param, Gc, toughness_name

    E_mod = float(material["E"])
    nu = float(material["nu"])
    if not (-1.0 < nu < 0.5):
        raise ValueError(f"Poisson ratio must be between -1 and 0.5, got {nu}")
    lam = E_mod * nu / ((1.0 + nu) * (1.0 - 2.0 * nu))
    mu = E_mod / (2.0 * (1.0 + nu))
    if comm.Get_rank() == 0:
        print(f"Material '{args.material}': E={E_mod}, nu={nu}, lambda={lam}, mu={mu}")
        print(f"Fracture toughness '{toughness_name}': Gc={Gc}")
        if toughness_source_doi:
            print(f"Fracture toughness source DOI: {toughness_source_doi}")
    return lam, mu, Gc, toughness_name


lam_param, mue_param, Gc_param, toughness_name = material_parameters()

# Run the simulation
sim.run_simulation(args.mesh_file,
                   lam_param,
                   mue_param,
                   Gc_param,
                   args.eps_factor_param,
                   args.element_order,
                   comm)

# Put files in folders
current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
# Create a folder name based on the parameters, current time, and mesh file name
folder_name = (f"simulation_{current_time}_"
               f"{args.mesh_file}_"
               f"{args.material}_{toughness_name}_lam{lam_param}_mue{mue_param}_Gc{Gc_param}_eps{args.eps_factor_param}_order{args.element_order}")
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
