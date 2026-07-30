#!/bin/bash

#SBATCH -J mesh-b4-r2
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH -p mem
#SBATCH --nodes=1
#SBATCH -n 32
#SBATCH --mem-per-cpu=15000
#SBATCH -C "m01&mem1536g"
#SBATCH --array=0-2%1
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/012-Fracture-Mesh-Sim-Split/%x.err.%A_%a
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/012-Fracture-Mesh-Sim-Split/%x.out.%A_%a
#SBATCH --mail-type=END

# Convenience wrapper: generates the Bin4 reduce-2 mesh at coarse, medium,
# and fine resolution (as a 3-task SLURM array, one at a time) and archives
# each into data/resources/generated_meshes/. Run job_run_simulation_*
# afterwards to simulate against a given resolution.

set -euo pipefail

SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/012-Fracture-Mesh-Sim-Split"
CONFIGS=(
  "config-Bin4-reduce-2-mesh-coarse.json"
  "config-Bin4-reduce-2-mesh-medium.json"
  "config-Bin4-reduce-2-mesh-fine.json"
)

array_index="${SLURM_ARRAY_TASK_ID:-${1:-}}"
if ! [[ "$array_index" =~ ^[0-2]$ ]]; then
  echo "Expected SLURM_ARRAY_TASK_ID 0, 1, or 2; got '$array_index'." >&2
  exit 2
fi

config_name="${CONFIGS[$array_index]}"
echo "Starting mesh generation for $config_name"

SRUN_MEM_PER_CPU=15000 \
  bash "$SCRIPT_DIR/job_generate_mesh_CLUSTER.sh" "$config_name"
