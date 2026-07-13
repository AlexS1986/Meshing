#!/bin/bash

#SBATCH -J mesh-b4-r2
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH -n 8
#SBATCH -N 1
#SBATCH --mem-per-cpu=9000
#SBATCH -C i01
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

if [[ -z "${MESH_SOURCE_SUBVOLUME_DIR:-}" ]]; then
  source_candidates=(
    "$SCRIPT_DIR/JM-25-74_Bin4_reduce-2_segmented/JM-25-74_Bin4_reduce-2_segmented_3D/subvolume_x52_y74"
    "$SCRIPT_DIR/00_results/JM-25-74_Bin4_reduce-2_segmented_cluster_fine/JM-25-74_Bin4_reduce-2_segmented_cluster_fine_3D/subvolume_x52_y74"
  )
  for candidate in "${source_candidates[@]}"; do
    if [[ -f "$candidate/volume.npy" ]]; then
      MESH_SOURCE_SUBVOLUME_DIR="$candidate"
      break
    fi
  done
fi

if [[ -z "${MESH_SOURCE_SUBVOLUME_DIR:-}" ]]; then
  echo "Could not find the existing volume.npy in HPC scratch." >&2
  echo "Set MESH_SOURCE_SUBVOLUME_DIR to the subvolume_x*_y* directory." >&2
  exit 1
fi

echo "Voxel input from HPC scratch: $MESH_SOURCE_SUBVOLUME_DIR/volume.npy"

MESH_ONLY=1 \
MESH_SOURCE_SUBVOLUME_DIR="$MESH_SOURCE_SUBVOLUME_DIR" \
DLFX_CONVERT_NTASKS=8 SRUN_TIME=1440 \
  bash "$SCRIPT_DIR/job_fracture_from_scans_CLUSTER.sh" "$config_name"
