#!/bin/bash
#SBATCH -J {JOB_NAME}
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
NHOLES={NHOLES} # needs to be int
WSTEG={WSTEG}
DHOLE={DHOLE}
E0={E0}
E1={E1}
MESH_FILE="{MESH_FILE}"
LAM_MICRO_PARAM={LAM_MICRO_PARAM}
MUE_MICRO_PARAM={MUE_MICRO_PARAM}
GC_MICRO_PARAM={GC_MICRO_PARAM}

# Calculate EPS_PARAM as 6 times E0 using awk if not provided by user
EPS_PARAM={EPS_PARAM}
ELEMENT_ORDER={ELEMENT_ORDER}

LCRACK=$(awk "BEGIN {print $WSTEG + $DHOLE}")

# Navigate to $HPC_SCRATCH
cd $HPC_SCRATCH

# Run the mesh generation and other scripts with --hole_angle parameter
srun -n 1 apptainer exec --bind $HOME/pygalmesh/shared:/home,$working_directory:/work $HOME/pygalmesh/alex-dolfinx.sif python3 $working_directory/03_mesh_3D_array_pygalmesh.py --config "$CONFIG_PATH" --npy "$NPY_FILE" --mesh "$MESH_OUTPUT"

EXITCODE=$?

# Exit the job script with the status of the scientific program
exit $EXITCODE

