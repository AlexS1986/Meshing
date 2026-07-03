#!/bin/bash
set -euo pipefail

working_directory="$HPC_SCRATCH/pygalmesh/data/scripts/010-Yield-Surface-Generation"
CONFIG_ARG="${1:?Usage: job_yield_surface_point_CLUSTER.sh /data/path/to/sample/config.json}"
if [[ "$CONFIG_ARG" = /* ]]; then
  CONFIG_PATH="$CONFIG_ARG"
else
  CONFIG_PATH="/data/scripts/010-Yield-Surface-Generation/$CONFIG_ARG"
fi
CONFIG_HOST_PATH="${CONFIG_PATH/#\/data/$HPC_SCRATCH/pygalmesh/data}"

CONTAINER_PATH="$HOME/meshing/Meshing/pygalmesh/pygalmesh.sif"
BIND_PATHS="$HOME/meshing/Meshing/pygalmesh/data:/home,$HPC_SCRATCH/pygalmesh/data:/data"
SIM_CONTAINER="$HOME/dolfinx_alex/alex-dolfinx.sif"
SIM_BIND="$HOME/dolfinx_alex/shared:/home,$HPC_SCRATCH/pygalmesh/data:/data"
SOURCE_DIR="$working_directory/00_template"
sim_ntasks="${SLURM_NTASKS:-96}"
case_scratch="$working_directory/scratch/yield_point_${SLURM_JOB_ID:-manual}"
rm -rf "$case_scratch"
mkdir -p "$case_scratch/tmp"

run_container() {
  local ntasks="$1"
  local chdir="$2"
  local bind_paths="$3"
  local container="$4"
  shift 4
  local srun_args=(-n "$ntasks")
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
    apptainer exec --bind "$bind_paths,$case_scratch:$case_scratch" "$container" "$@"
  ' bash "$case_scratch" "$bind_paths" "$container" "$@"
}

CONFIG_INFO=$(srun -n 1 apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" python3 - "$CONFIG_PATH" <<'PYINFO'
import json, sys
with open(sys.argv[1]) as handle:
    config = json.load(handle)
ys = config.get("yield_surface", {})
print(config["binning"]["label"])
print(config["01_segment_slice_wise"]["specimen_name"])
print(config["02b_build_subvolume_arrays"]["subvolume_output_folder"])
print(" ".join(ys.get("materials", ["std"])))
print(" ".join(ys.get("loading_directions", ["tensor"])))
print(ys.get("sample_id", "yield_sample"))
print(config.get("02d_axis_aligned_cuboid_crop", {}).get("output_filename", "volume_boundary_shell_aniso.npy"))
PYINFO
)

binning_label="$(echo "$CONFIG_INFO" | sed -n '1p')"
run_name="$(echo "$CONFIG_INFO" | sed -n '2p')"
base_subvolume_container_path="$(echo "$CONFIG_INFO" | sed -n '3p')"
materials_line="$(echo "$CONFIG_INFO" | sed -n '4p')"
directions_line="$(echo "$CONFIG_INFO" | sed -n '5p')"
sample_id="$(echo "$CONFIG_INFO" | sed -n '6p')"
shell_volume_filename="$(echo "$CONFIG_INFO" | sed -n '7p')"
read -r -a MATERIALS <<< "$materials_line"
read -r -a DIRECTIONS <<< "$directions_line"
base_subvolume_folder="${base_subvolume_container_path/#\/data/$HPC_SCRATCH/pygalmesh/data}"
run_root="$working_directory/yield_surface_runs/$sample_id"
mkdir -p "$run_root"

echo "Running yield-surface point: $sample_id"
echo "Using config: $CONFIG_PATH"
echo "Using prepared mesh folder: $base_subvolume_folder"
echo "Run root: $run_root"

for mat in "${MATERIALS[@]}"; do
  for direction in "${DIRECTIONS[@]}"; do
    final_output_dir="$working_directory/00_results/${SPECIMEN_NAME:-JM-25-74}/${binning_label}/yield_surface/${sample_id}-${mat}-${direction}"
    for subfolder in "$base_subvolume_folder"/*/; do
      [ -d "$subfolder" ] || continue
      if [ ! -f "$subfolder/dlfx_mesh.xdmf" ]; then
        echo "Missing $subfolder/dlfx_mesh.xdmf. Run job_prepare_mesh_Bin4_reduce_2_CLUSTER.sh first." >&2
        exit 1
      fi
      target="$run_root/$(basename "$subfolder")"
      rm -rf "$target"
      mkdir -p "$target"
      cp -v "$subfolder"/dlfx_mesh.* "$target"/
      cp -v "$subfolder"/mesh.xdmf "$target"/ 2>/dev/null || true
      cp -v "$subfolder"/mesh.h5 "$target"/ 2>/dev/null || true
      cp -v "$subfolder/$shell_volume_filename" "$target"/ 2>/dev/null || true
      cp -v "$subfolder"/volume*.npy "$target"/ 2>/dev/null || true
      cp -v "$SOURCE_DIR"/* "$target"/
      cp -v "$CONFIG_HOST_PATH" "$target/config.json"
      run_container "$sim_ntasks" "$target" "$SIM_BIND" "$SIM_CONTAINER" \
        python3 "$target/elastoplastic.py" --material "$mat" --loading-direction "$direction" --config "$target/config.json"
    done
    mkdir -p "$final_output_dir"
    cp -rv "$run_root" "$final_output_dir/"
    cp -v "$CONFIG_HOST_PATH" "$final_output_dir/config.json" || true
  done
done

rm -rf "$case_scratch"
echo "Yield-surface point complete: $sample_id"
