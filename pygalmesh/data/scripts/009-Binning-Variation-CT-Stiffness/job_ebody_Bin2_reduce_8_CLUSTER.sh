#!/bin/bash

#SBATCH -J eb-b2-r8

#SBATCH -A p0023647

#SBATCH -t 1440

#SBATCH -n 96
#SBATCH -N 1
#SBATCH --mem-per-cpu=9000

#SBATCH -C "mem"

#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness/%x.err.%j

#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness/%x.out.%j

#SBATCH --mail-type=END
SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness"
bash "$SCRIPT_DIR/job_ebody_from_scans_CLUSTER.sh" 2 config-Bin2-reduce-8.json
