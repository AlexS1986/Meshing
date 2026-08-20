#!/bin/bash

#SBATCH -J prep-ys-mesh
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH -p mem
# Es arbeitet nur ein Task (run_container 1 = srun -n 1); die Zuteilung
# dient dem Speicher. 32 x 45000 MB = 1,44 TB, wie beim erfolgreichen Lauf
# mit 96 x 15000 MB.
#SBATCH --nodes=1
#SBATCH -n 32
#SBATCH --mem-per-cpu=15000
#SBATCH -C "m01&mem1536g"
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS/%x.out.%j
#SBATCH --mail-type=END

set -euo pipefail

SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS"
bash "$SCRIPT_DIR/run_prepare_mesh_CLUSTER.sh" \
  "${1:-${PREPARE_MESH_CONFIG:-config-A01-les.json}}"
