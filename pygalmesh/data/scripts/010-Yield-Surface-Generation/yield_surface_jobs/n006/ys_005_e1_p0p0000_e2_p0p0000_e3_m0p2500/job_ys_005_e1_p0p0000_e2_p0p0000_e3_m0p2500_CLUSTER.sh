#!/bin/bash

#SBATCH -J ys_005_e1_p0p0000_e2_p0p0000_e3_m0p2500
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH -p mem
#SBATCH --nodes=1
#SBATCH -n 96
#SBATCH --mem-per-cpu=15000
#SBATCH -C "m01&mem1536g"
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/010-Yield-Surface-Generation/yield_surface_jobs/n006/ys_005_e1_p0p0000_e2_p0p0000_e3_m0p2500/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/010-Yield-Surface-Generation/yield_surface_jobs/n006/ys_005_e1_p0p0000_e2_p0p0000_e3_m0p2500/%x.out.%j
#SBATCH --mail-type=END

SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/010-Yield-Surface-Generation"
bash "$SCRIPT_DIR/job_yield_surface_point_CLUSTER.sh" "/data/scripts/010-Yield-Surface-Generation/yield_surface_jobs/n006/ys_005_e1_p0p0000_e2_p0p0000_e3_m0p2500/config.json"
