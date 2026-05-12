#!/bin/bash
#SBATCH -J eb-b4-r4
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH --mem-per-cpu=9000
#SBATCH -n 16
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness/%x.out.%j
#SBATCH --mail-type=END
#SBATCH -C i01

SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness"
bash "$SCRIPT_DIR/job_ebody_from_scans_CLUSTER.sh" 4 config-Bin4-reduce-4.json
