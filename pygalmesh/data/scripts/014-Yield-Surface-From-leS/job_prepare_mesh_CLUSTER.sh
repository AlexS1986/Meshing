#!/bin/bash

#SBATCH -J prep-ys-mesh
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH -p mem
#SBATCH --nodes=1
#SBATCH -n 96
#SBATCH --mem-per-cpu=15000
#SBATCH -C "m01&mem1536g"
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/014-Yield-Surface-From-leS/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/014-Yield-Surface-From-leS/%x.out.%j
#SBATCH --mail-type=END

set -euo pipefail

SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/014-Yield-Surface-From-leS"
bash "$SCRIPT_DIR/run_prepare_mesh_CLUSTER.sh" \
  "${1:-${PREPARE_MESH_CONFIG:-config-A01-les.json}}"
