#!/bin/bash

#SBATCH -J mesh-ct
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH -p mem
#SBATCH --nodes=1
#SBATCH -n 32
#SBATCH --mem-per-cpu=15000
#SBATCH -C "m01&mem1536g"
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/012-Fracture-Mesh-Sim-Split/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/012-Fracture-Mesh-Sim-Split/%x.out.%j
#SBATCH --mail-type=END

# Stage 1 of the split fracture-from-CT-scans pipeline: DICOM preprocessing,
# meshing, and DOLFINx mesh conversion only -- no fracture simulation.
#
# Finished per-subvolume meshes are archived under
#   data/resources/generated_meshes/<specimen>/<binning>/<run_name>/
# so job_run_simulation_CLUSTER.sh can reference them later without
# re-running any of the steps below.
#
# Usage: sbatch job_generate_mesh_CLUSTER.sh [config-file.json]
#   (defaults to config-Bin4-reduce-2-cluster-fine.json)

set -euo pipefail

working_directory="$HPC_SCRATCH/pygalmesh/data/scripts/012-Fracture-Mesh-Sim-Split"
source "$working_directory/config.sh"

CONFIG_ARG="${1:-config-Bin4-reduce-2-cluster-fine.json}"
if [[ "$CONFIG_ARG" = /* ]]; then
  CONFIG_PATH="$CONFIG_ARG"
else
  CONFIG_PATH="/data/scripts/012-Fracture-Mesh-Sim-Split/$CONFIG_ARG"
fi
CONFIG_HOST_PATH="${CONFIG_PATH/#\/data/$HPC_SCRATCH/pygalmesh/data}"

CONTAINER_PATH="$HOME/meshing/Meshing/pygalmesh/pygalmesh.sif"
RESOURCE_RELATIVE_PATH="B02_Mevert_AlSi10MgSchaum_JM-26-74_Binning_Variation/Binning 4/JM-25-74_6min15_750^C_erodiert_nach Trockenschrank_Bin4"
resource_candidates=()
if [[ -n "${HPC_RESOURCE_DIR:-}" ]]; then
  resource_candidates+=("$HPC_RESOURCE_DIR")
fi
resource_candidates+=(
  "$HPC_SCRATCH/pygalmesh/data/resources"
  "$HPC_SCRATCH/resources"
  "$HOME/meshing/Meshing/pygalmesh/data/resources"
)

RESOURCE_DIR=""
for candidate in "${resource_candidates[@]}"; do
  if [[ -f "$candidate/$RESOURCE_RELATIVE_PATH/DICOMDIR" ]]; then
    RESOURCE_DIR="$candidate"
    break
  fi
done

if [[ -z "$RESOURCE_DIR" ]]; then
  echo "Could not locate the original Bin4 DICOM data on the cluster." >&2
  echo "Expected DICOMDIR below one of these resource roots:" >&2
  printf '  %s\n' "${resource_candidates[@]}" >&2
  echo "Set HPC_RESOURCE_DIR to the host directory that contains $RESOURCE_RELATIVE_PATH." >&2
  exit 1
fi

echo "Cluster resource root: $RESOURCE_DIR"
echo "Container DICOM path: /data/resources/$RESOURCE_RELATIVE_PATH/DICOMDIR"
BIND_PATHS="$HOME/meshing/Meshing/pygalmesh/data:/home,$HPC_SCRATCH/pygalmesh/data:/data,$RESOURCE_DIR:/data/resources:ro"
SIM_CONTAINER="$HOME/dolfinx_alex/alex-dolfinx.sif"
SIM_BIND="$HOME/dolfinx_alex/shared:/home,$HPC_SCRATCH/pygalmesh/data:/data"

VOLUME_FILENAME="volume.npy"
SRUN_MEM_PER_CPU="${SRUN_MEM_PER_CPU:-15000}"

PREPROCESS_SCRIPTS=(
  "00_dicom_2_npy.py"
  "01_segment_slice_wise.py"
  "02_build3D_segmented_array.py"
  "02a_rotate_pic_to_align_with_axis.py"
  "02b_build_subvolume_arrays.py"
)

CONFIG_INFO=$(
  srun -n 1 --mem-per-cpu="$SRUN_MEM_PER_CPU" apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" \
    python3 - "$CONFIG_PATH" <<'PYINFO'
import json
import sys
with open(sys.argv[1], "r") as handle:
    config = json.load(handle)
print(config["binning"]["label"])
# NOTE: use 03_mesh_3D_array.specimen_name, not
# 01_segment_slice_wise.specimen_name -- the latter is shared across the
# coarse/medium/fine mesh-resolution configs (they only override
# 03_mesh_3D_array.specimen_name), so using it here would make every
# resolution tier archive to the same path and overwrite the previous one.
print(config["03_mesh_3D_array"]["specimen_name"])
print(config["02b_build_subvolume_arrays"]["subvolume_output_folder"])
print(config.get("metadata_output_path", ""))
PYINFO
)

binning_label="$(echo "$CONFIG_INFO" | sed -n '1p')"
run_name="$(echo "$CONFIG_INFO" | sed -n '2p')"
base_subvolume_container_path="$(echo "$CONFIG_INFO" | sed -n '3p')"
metadata_container_path="$(echo "$CONFIG_INFO" | sed -n '4p')"
base_subvolume_folder="${base_subvolume_container_path/#\/data/$HPC_SCRATCH/pygalmesh/data}"
metadata_host_path="${metadata_container_path/#\/data/$HPC_SCRATCH/pygalmesh/data}"
case_scratch="$working_directory/scratch/${run_name}_${SLURM_JOB_ID:-manual}"

rm -rf "$case_scratch"
mkdir -p "$case_scratch/tmp"

echo "Generating mesh for $binning_label / $run_name"
echo "Using config: $CONFIG_PATH"
echo "Case scratch: $case_scratch"

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

write_voxel_cross_section() {
  local npy_path="$1"
  local stage_name="$2"
  local output_dir="$3"

  if [[ -f "$npy_path" ]]; then
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/02g_write_voxel_cross_sections.py" \
        --npy "$npy_path" \
        --output-dir "$output_dir" \
        --stage "$stage_name" \
        --axis z
  fi
}

config_bool() {
  python3 - "$CONFIG_HOST_PATH" "$1" <<'PYBOOL'
import json, sys
with open(sys.argv[1]) as handle:
    config = json.load(handle)
value = config
for key in sys.argv[2].split('.'):
    value = value.get(key, {}) if isinstance(value, dict) else {}
print("1" if value is True else "0")
PYBOOL
}

config_value_default() {
  python3 - "$CONFIG_HOST_PATH" "$1" "$2" <<'PYVAL'
import json, sys
with open(sys.argv[1]) as handle:
    config = json.load(handle)
value = config
for key in sys.argv[2].split('.'):
    if not isinstance(value, dict) or key not in value:
        print(sys.argv[3]); raise SystemExit
    value = value[key]
print(sys.argv[3] if value is None else value)
PYVAL
}

for script in "${PREPROCESS_SCRIPTS[@]}"; do
  run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
    python3 "$working_directory/$script" --config "$CONFIG_PATH"
done

for subfolder in "$base_subvolume_folder"/subvolume_x*_y*/; do
  [ -d "$subfolder" ] || continue
  npy_file="$subfolder/$VOLUME_FILENAME"
  mesh_output="$subfolder/mesh.xdmf"
  folder_name="$(basename "$subfolder")"
  if [[ "$folder_name" =~ subvolume_x([0-9]+)_y([0-9]+) ]]; then
    center_x="${BASH_REMATCH[1]}"
    center_y="${BASH_REMATCH[2]}"
  else
    echo "Could not extract center_x and center_y from $folder_name"
    continue
  fi

  meshing_npy_file="$npy_file"
  cross_section_dir="$subfolder/voxel_cross_sections"
  write_voxel_cross_section "$meshing_npy_file" "00_original_subvolume" "$cross_section_dir"
  if [[ "$(config_bool 02c_voxel_topology_cleanup.enabled)" == "1" ]]; then
    cleaned_npy_file="$subfolder/$(config_value_default 02c_voxel_topology_cleanup.output_filename volume_topology_cleaned.npy)"
    voxel_report_file="$subfolder/$(config_value_default 02c_voxel_topology_cleanup.report_filename volume_topology.txt)"
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/02c_voxel_topology_cleanup.py" --config "$CONFIG_PATH" --npy "$npy_file" --output "$cleaned_npy_file" --report "$voxel_report_file"
    write_voxel_cross_section "$cleaned_npy_file" "01_topology_cleanup" "$cross_section_dir"
    if [[ "$(config_bool 02c_voxel_topology_cleanup.use_cleaned_for_meshing)" == "1" ]]; then
      meshing_npy_file="$cleaned_npy_file"
    fi
  fi

  if [[ "$(config_bool 02e_mirror_extrude_voxel.enabled)" == "1" ]]; then
    mirrored_npy_file="$subfolder/$(config_value_default 02e_mirror_extrude_voxel.output_filename volume_mirrored_x.npy)"
    mirrored_report_file="$subfolder/$(config_value_default 02e_mirror_extrude_voxel.report_filename volume_mirrored_x.txt)"
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/02e_mirror_extrude_voxel.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --output "$mirrored_npy_file" --report "$mirrored_report_file"
    write_voxel_cross_section "$mirrored_npy_file" "02_voxel_mirror" "$cross_section_dir"
    if [[ "$(config_bool 02e_mirror_extrude_voxel.use_mirrored_for_meshing)" == "1" ]]; then
      meshing_npy_file="$mirrored_npy_file"
    fi
  fi

  if [[ "$(config_bool 02d_axis_aligned_cuboid_crop.enabled)" == "1" ]]; then
    cuboid_npy_file="$subfolder/$(config_value_default 02d_axis_aligned_cuboid_crop.output_filename volume_cuboid.npy)"
    cuboid_report_file="$subfolder/$(config_value_default 02d_axis_aligned_cuboid_crop.report_filename volume_cuboid.txt)"
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/02d_axis_aligned_cuboid_crop.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --output "$cuboid_npy_file" --report "$cuboid_report_file"
    write_voxel_cross_section "$cuboid_npy_file" "03_internal_aniso_shell" "$cross_section_dir"
    if [[ "$(config_bool 02d_axis_aligned_cuboid_crop.use_cuboid_for_meshing)" == "1" ]]; then
      meshing_npy_file="$cuboid_npy_file"
    fi
  fi

  if [[ "$(config_bool 02f_add_voxel_shell.enabled)" == "1" ]]; then
    shelled_npy_file="$subfolder/$(config_value_default 02f_add_voxel_shell.output_filename volume_additive_shell.npy)"
    shelled_report_file="$subfolder/$(config_value_default 02f_add_voxel_shell.report_filename volume_additive_shell.txt)"
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/02f_add_voxel_shell.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --output "$shelled_npy_file" --report "$shelled_report_file"
    write_voxel_cross_section "$shelled_npy_file" "04_external_shell" "$cross_section_dir"
    if [[ "$(config_bool 02f_add_voxel_shell.use_shell_for_meshing)" == "1" ]]; then
      meshing_npy_file="$shelled_npy_file"
    fi
  fi

  run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
    python3 "$working_directory/03_mesh_3D_array_pygalmesh.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --mesh "$mesh_output"
  run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
    python3 "$working_directory/04_scale_and_translate_mesh_mod.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --center_x "$center_x" --center_y "$center_y" --npy "$meshing_npy_file"

  if [[ "$(config_bool 10_snap_mesh_to_crop_boundary.enabled)" == "1" ]]; then
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/10_snap_mesh_to_crop_boundary.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --report "${mesh_output%.xdmf}.snap_boundary.txt"
  fi

  if [[ "$(config_bool 11_mirror_extrude_mesh.enabled)" == "1" ]]; then
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/11_mirror_extrude_mesh.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --report "${mesh_output%.xdmf}.mirror_extrude.txt"
  fi

  if [[ "$(config_bool 05_tetgen_postprocess.enabled)" == "1" ]]; then
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/05_tetgen_postprocess_mesh.py" --config "$CONFIG_PATH" --mesh "$mesh_output"
    if [[ "$(config_bool 08_mesh_quality_report.enabled)" == "1" ]]; then
      run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
        python3 "$working_directory/08_mesh_quality_report.py" --config "$CONFIG_PATH" --tetgen-log "${mesh_output%.xdmf}.tetgen.log" --output "${mesh_output%.xdmf}.quality.txt"
    fi
  fi

  if [[ "$(config_bool 09_mesh_topology_audit.enabled)" == "1" ]]; then
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/09_mesh_topology_audit.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --output "${mesh_output%.xdmf}.topology.txt"
  fi
done

for subfolder in "$base_subvolume_folder"/*/; do
  [ -d "$subfolder" ] || continue
  if [ -f "$subfolder/mesh.xdmf" ]; then
    run_container 1 "" "$SIM_BIND" "$SIM_CONTAINER" \
      python3 "$working_directory/make_mesh_dlfx_compatible_cluster.py" "$subfolder" -f mesh.xdmf
  fi
done

rm -rf "$case_scratch"

# --- Archive the finished meshes into data/resources so they can be
# --- referenced by job_run_simulation_CLUSTER.sh without re-meshing.
MESH_ARCHIVE_ROOT="$HPC_SCRATCH/pygalmesh/data/resources/generated_meshes"
MESH_ARCHIVE_DIR="$MESH_ARCHIVE_ROOT/${SPECIMEN_NAME}/${binning_label}/${run_name}"

rm -rf "$MESH_ARCHIVE_DIR"
mkdir -p "$(dirname "$MESH_ARCHIVE_DIR")"
cp -rv "$base_subvolume_folder" "$MESH_ARCHIVE_DIR"
if [[ -f "$metadata_host_path" ]]; then
  cp -v "$metadata_host_path" "$MESH_ARCHIVE_DIR/metadata.json"
fi
cp -v "$CONFIG_HOST_PATH" "$MESH_ARCHIVE_DIR/config.json"

echo "Mesh generation complete."
echo "Meshes archived to: $MESH_ARCHIVE_DIR"
echo "Run job_run_simulation_CLUSTER.sh with the same config to simulate against them."
