#!/bin/bash
#SBATCH -J meshing
#SBATCH -A p0023647
#SBATCH -t 1440  # "minutes", "minutes:seconds", "hours:minutes:seconds", "days-hours", "days-hours:minutes" and "days-hours:minutes:seconds"
#SBATCH --mem-per-cpu=6000
#SBATCH -n 32
#SBATCH -e /work/scratch/as12vapa/001-Special-Issue-2025/{FOLDER_NAME}/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/001-Special-Issue-2025/{FOLDER_NAME}/%x.out.%j
#SBATCH --mail-type=End
#SBATCH -C i01

# Set the working directory name
working_folder_name="{FOLDER_NAME}"  # Change this to your desired folder name
# Create the working directory under $HPC_SCRATCH
working_directory="$HPC_SCRATCH/001-Special-Issue-2025/$working_folder_name"

# Default values for parameters
CONFIG_PATH="{CONFIG_PATH}" #
NPY_PATH="{NPY_PATH}"
MESH_PATH="{MESH_PATH}"


# Navigate to $HPC_SCRATCH
cd $HPC_SCRATCH

# Run the mesh generation and other scripts with --hole_angle parameter
srun -n 1 apptainer exec --bind $HOME/meshing/Meshing/pygalmesh/data:/home,$working_directory:/work $HOME/meshing/Meshing/pygalmesh/pygalmesh.sif python3 $working_directory/03_mesh_3D_array_pygalmesh.py --config "$CONFIG_PATH" --npy "$NPY_FILE" --mesh "$MESH_OUTPUT"

EXITCODE=$?

# Exit the job script with the status of the scientific program
exit $EXITCODE

