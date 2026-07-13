#!/bin/bash

#SBATCH -J mesh-b4-r2
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH -p mem
#SBATCH --nodes=1
#SBATCH -n 8
#SBATCH --mem-per-cpu=15000
#SBATCH -C "m01&mem1536g"
#SBATCH --array=0-2%1
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/011-Fracture-From-CT-Scans/%x.err.%A_%a
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/011-Fracture-From-CT-Scans/%x.out.%A_%a
#SBATCH --mail-type=END

set -euo pipefail

SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/011-Fracture-From-CT-Scans"
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
echo "Starting mesh-only resolution job for $config_name"

MESH_ONLY=1 DLFX_CONVERT_NTASKS=8 SRUN_TIME=1440 SRUN_MEM_PER_CPU=15000 \
  bash "$SCRIPT_DIR/job_fracture_from_scans_CLUSTER.sh" "$config_name"
