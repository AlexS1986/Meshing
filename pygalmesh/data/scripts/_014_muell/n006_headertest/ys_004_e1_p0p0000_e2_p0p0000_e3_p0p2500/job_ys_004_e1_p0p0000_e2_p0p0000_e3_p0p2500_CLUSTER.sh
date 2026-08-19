#!/bin/bash

#SBATCH -J ys_004_e1_p0p0000_e2_p0p0000_e3_p0p2500
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH -n 64
#SBATCH -N 1
#SBATCH --mem-per-cpu=4000
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/014-Yield-Surface-From-leS/yield_surface_jobs/n006/ys_004_e1_p0p0000_e2_p0p0000_e3_p0p2500/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/014-Yield-Surface-From-leS/yield_surface_jobs/n006/ys_004_e1_p0p0000_e2_p0p0000_e3_p0p2500/%x.out.%j
#SBATCH -C i01
#SBATCH --mail-type=END

SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/014-Yield-Surface-From-leS"
bash "$SCRIPT_DIR/job_yield_surface_point_CLUSTER.sh" "/data/scripts/014-Yield-Surface-From-leS/yield_surface_jobs/n006/ys_004_e1_p0p0000_e2_p0p0000_e3_p0p2500/config.json"
