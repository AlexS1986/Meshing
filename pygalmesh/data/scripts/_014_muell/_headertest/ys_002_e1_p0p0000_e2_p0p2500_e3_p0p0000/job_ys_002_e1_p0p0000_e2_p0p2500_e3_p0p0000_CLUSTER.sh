#!/bin/bash

#SBATCH -J ys_002_e1_p0p0000_e2_p0p2500_e3_p0p0000
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH -n 96
#SBATCH --mem-per-cpu=9000
#SBATCH -C i01
#SBATCH --mail-type=END

SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/014-Yield-Surface-From-leS"
bash "$SCRIPT_DIR/job_yield_surface_point_CLUSTER.sh" "/data/scripts/014-Yield-Surface-From-leS/yield_surface_jobs/_headertest/ys_002_e1_p0p0000_e2_p0p2500_e3_p0p0000/config.json"
