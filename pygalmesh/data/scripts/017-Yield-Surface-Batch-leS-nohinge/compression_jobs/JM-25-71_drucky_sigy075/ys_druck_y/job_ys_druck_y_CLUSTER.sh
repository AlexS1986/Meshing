#!/bin/bash

#SBATCH -J JM-25-71_s075-drucky
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH -n 32
#SBATCH -N 1
#SBATCH --mem-per-cpu=5600
#SBATCH --mail-type=END

SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/017-Yield-Surface-Batch-leS-nohinge"
bash "$SCRIPT_DIR/job_yield_surface_point_CLUSTER.sh" "/data/scripts/017-Yield-Surface-Batch-leS-nohinge/compression_jobs/JM-25-71_drucky_sigy075/ys_druck_y/config.json"
