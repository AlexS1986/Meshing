#!/bin/bash

#SBATCH -J frac-b4-r2-fine
#SBATCH -A p0023647
#SBATCH -t 10080
#SBATCH -p mem
#SBATCH --nodes=1
#SBATCH -n 96
#SBATCH --mem-per-cpu=15000
#SBATCH -C "m01&mem1536g"
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/011-Fracture-From-CT-Scans/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/011-Fracture-From-CT-Scans/%x.out.%j
#SBATCH --mail-type=END

SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/011-Fracture-From-CT-Scans"
SRUN_TIME=10080 SRUN_MEM_PER_CPU=15000 \
  bash "$SCRIPT_DIR/job_fracture_from_scans_CLUSTER.sh" config-Bin4-reduce-2-cluster-fine.json
