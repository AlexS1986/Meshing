#!/bin/bash

#SBATCH -J ys_002_e1_p0p0000_e2_p0p2500_e3_p0p0000
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH -n 32
#SBATCH -N 1
#SBATCH --mem-per-cpu=9000
#SBATCH -C i01
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/010-Yield-Surface-Generation/yield_surface_jobs/n006/ys_002_e1_p0p0000_e2_p0p2500_e3_p0p0000/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/010-Yield-Surface-Generation/yield_surface_jobs/n006/ys_002_e1_p0p0000_e2_p0p2500_e3_p0p0000/%x.out.%j
#SBATCH --mail-type=END

SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/010-Yield-Surface-Generation"
bash "$SCRIPT_DIR/job_yield_surface_point_CLUSTER.sh" "/data/scripts/010-Yield-Surface-Generation/yield_surface_jobs/n006/ys_002_e1_p0p0000_e2_p0p2500_e3_p0p0000/config.json"
