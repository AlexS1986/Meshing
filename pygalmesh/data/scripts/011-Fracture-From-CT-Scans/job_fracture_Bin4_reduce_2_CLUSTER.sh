#!/bin/bash

#SBATCH -J frac-b4-r2-fine
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH -n 96
#SBATCH -N 1
#SBATCH --mem-per-cpu=9000
#SBATCH -C i01
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/011-Fracture-From-CT-Scans/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/011-Fracture-From-CT-Scans/%x.out.%j
#SBATCH --mail-type=END

SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/011-Fracture-From-CT-Scans"
bash "$SCRIPT_DIR/job_fracture_from_scans_CLUSTER.sh" config-Bin4-reduce-2-cluster-fine.json
