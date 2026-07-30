#!/bin/bash

#SBATCH -J fracture-sim
#SBATCH -A p0023647
#SBATCH -t 10080
#SBATCH --mem-per-cpu=4000
#SBATCH -n 96
#SBATCH -N 1
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/012-Fracture-Mesh-Sim-Split/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/012-Fracture-Mesh-Sim-Split/%x.out.%j
#SBATCH --mail-type=END
#SBATCH -C i01

# Stage 2 of the split fracture-from-CT-scans pipeline: runs the phase-field
# fracture simulation against meshes already produced by
# job_generate_mesh_CLUSTER.sh, archived under
#   data/resources/generated_meshes/<specimen>/<binning>/<run_name>/
#
# Does NOT regenerate meshes. If the archive for this config is missing, run
# job_generate_mesh_CLUSTER.sh first with the same config file.
#
# Usage: sbatch job_run_simulation_CLUSTER.sh [config-file.json]
#   (defaults to config-Bin4-reduce-2-cluster-coarse.json; must match the
#   config used for mesh generation so specimen/binning/run_name line up)

set -euo pipefail

working_directory="$HPC_SCRATCH/pygalmesh/data/scripts/012-Fracture-Mesh-Sim-Split"
source "$working_directory/config.sh"

CONFIG_ARG="${1:-config-Bin4-reduce-2-cluster-coarse.json}"
if [[ "$CONFIG_ARG" = /* ]]; then
  CONFIG_PATH="$CONFIG_ARG"
else
  CONFIG_PATH="/data/scripts/012-Fracture-Mesh-Sim-Split/$CONFIG_ARG"
fi
CONFIG_HOST_PATH="${CONFIG_PATH/#\/data/$HPC_SCRATCH/pygalmesh/data}"

SIM_CONTAINER="$HOME/dolfinx_alex/alex-dolfinx.sif"
SIM_BIND="$HOME/dolfinx_alex/shared:/home,$HPC_SCRATCH/pygalmesh/data:/data"

SOURCE_DIR="$working_directory/00_template"
output_directory_variable="fracture"
sim_ntasks="${SLURM_NTASKS:-96}"
SRUN_MEM_PER_CPU="${SRUN_MEM_PER_CPU:-4000}"

CONFIG_INFO=$(python3 - "$CONFIG_HOST_PATH" <<'PYINFO'
import json
import sys
with open(sys.argv[1], "r") as handle:
    config = json.load(handle)
frac = config.get("fracture", {})
print(config["binning"]["label"])
# Must match job_generate_mesh_CLUSTER.sh's run_name derivation exactly, or
# this script will look for the mesh archive under the wrong path.
# 01_segment_slice_wise.specimen_name is shared across the coarse/medium/fine
# configs -- use 03_mesh_3D_array.specimen_name, which is resolution-specific.
print(config["03_mesh_3D_array"]["specimen_name"])
print(" ".join(frac.get("materials", ["std"])))
print(" ".join(frac.get("directions", ["y"])))
print(frac.get("mesh_file", "dlfx_mesh"))
print(frac.get("lam_param", 1.0))
print(frac.get("mue_param", 1.0))
print(frac.get("Gc_param", 1.0))
print(frac.get("eps_factor_param", 20.0))
print(frac.get("element_order", 1))
print(frac.get("fracture_toughness", "alsi10mg_as_built"))
PYINFO
)

binning_label="$(echo "$CONFIG_INFO" | sed -n '1p')"
run_name="$(echo "$CONFIG_INFO" | sed -n '2p')"
materials_line="$(echo "$CONFIG_INFO" | sed -n '3p')"
directions_line="$(echo "$CONFIG_INFO" | sed -n '4p')"
fracture_mesh_file="$(echo "$CONFIG_INFO" | sed -n '5p')"
fracture_lam="$(echo "$CONFIG_INFO" | sed -n '6p')"
fracture_mue="$(echo "$CONFIG_INFO" | sed -n '7p')"
fracture_gc="$(echo "$CONFIG_INFO" | sed -n '8p')"
fracture_eps_factor="$(echo "$CONFIG_INFO" | sed -n '9p')"
fracture_element_order="$(echo "$CONFIG_INFO" | sed -n '10p')"
fracture_toughness="$(echo "$CONFIG_INFO" | sed -n '11p')"
read -r -a MATERIALS <<< "$materials_line"
read -r -a DIRECTIONS <<< "$directions_line"

MESH_ARCHIVE_DIR="$HPC_SCRATCH/pygalmesh/data/resources/generated_meshes/${SPECIMEN_NAME}/${binning_label}/${run_name}"
if [[ ! -d "$MESH_ARCHIVE_DIR" ]]; then
  echo "No archived mesh found at: $MESH_ARCHIVE_DIR" >&2
  echo "Run job_generate_mesh_CLUSTER.sh with the same config file first." >&2
  exit 1
fi

base_subvolume_folder="$working_directory/${run_name}_from_resources"
case_scratch="$working_directory/scratch/${run_name}_${SLURM_JOB_ID:-manual}"

rm -rf "$base_subvolume_folder" "$case_scratch"
mkdir -p "$case_scratch/tmp"
cp -rv "$MESH_ARCHIVE_DIR" "$base_subvolume_folder"

echo "Running fracture simulation for $binning_label / $run_name"
echo "Using config: $CONFIG_PATH"
echo "Mesh source (archived): $MESH_ARCHIVE_DIR"
echo "Working mesh copy: $base_subvolume_folder"
echo "Fracture params: mesh=$fracture_mesh_file material_toughness=$fracture_toughness fallback_lam=$fracture_lam fallback_mue=$fracture_mue fallback_Gc=$fracture_gc eps_factor=$fracture_eps_factor order=$fracture_element_order"

run_container() {
  local ntasks="$1"
  local chdir="$2"
  local bind_paths="$3"
  local container="$4"
  shift 4
  local srun_args=(-n "$ntasks" --mem-per-cpu="$SRUN_MEM_PER_CPU")
  if [[ -n "$chdir" ]]; then
    srun_args+=(--chdir="$chdir")
  fi
  srun "${srun_args[@]}" bash -lc '
    case_scratch="$1"
    bind_paths="$2"
    container="$3"
    shift 3
    mkdir -p "$case_scratch/tmp"
    export TMPDIR="$case_scratch/tmp"
    echo "TMPDIR: $TMPDIR"
    apptainer exec --bind "$bind_paths,$case_scratch:$case_scratch" "$container" "$@"
  ' bash "$case_scratch" "$bind_paths" "$container" "$@"
}

for mat in "${MATERIALS[@]}"; do
  for dir in "${DIRECTIONS[@]}"; do
    final_output_dir="$working_directory/00_results/${SPECIMEN_NAME}/${binning_label}/${output_directory_variable}/${run_name}-${mat}-${dir}"
    for subfolder in "$base_subvolume_folder"/*/; do
      [ -d "$subfolder" ] || continue
      [ -f "$subfolder/dlfx_mesh.xdmf" ] || continue
      cp -v "$SOURCE_DIR"/* "$subfolder"
      cp -v "$CONFIG_HOST_PATH" "$subfolder/config.json"
      run_container "$sim_ntasks" "$subfolder" "$SIM_BIND" "$SIM_CONTAINER" \
        python3 "$subfolder/script.py" \
          --mesh_file "$fracture_mesh_file" \
          --material "$mat" \
          --fracture-toughness "$fracture_toughness" \
          --config "$subfolder/config.json" \
          --lam_param "$fracture_lam" \
          --mue_param "$fracture_mue" \
          --Gc_param "$fracture_gc" \
          --eps_factor_param "$fracture_eps_factor" \
          --element_order "$fracture_element_order"
    done
    mkdir -p "$final_output_dir"
    cp -rv "$base_subvolume_folder" "$final_output_dir/"
    cp -v "$CONFIG_HOST_PATH" "$final_output_dir/" || true
  done
done

rm -rf "$case_scratch"
echo "Fracture simulation run complete."
echo "Results: $working_directory/00_results/${SPECIMEN_NAME}/${binning_label}/${output_directory_variable}/"
