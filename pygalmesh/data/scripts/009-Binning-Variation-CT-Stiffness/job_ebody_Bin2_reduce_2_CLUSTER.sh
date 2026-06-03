#!/bin/bash

#SBATCH -J eb-b2-r2
#SBATCH -A p0023647
#SBATCH -t 1440

#SBATCH -p mem
#SBATCH --nodes=1
#SBATCH -n 96
#SBATCH --mem-per-cpu=15000
#SBATCH -C "m01&mem1536g"

#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness/%x.out.%j

#SBATCH --mail-type=END

SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness"
bash "$SCRIPT_DIR/job_ebody_from_scans_CLUSTER.sh" 2 config-Bin2-reduce-2.json
