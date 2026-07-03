#!/bin/bash

#SBATCH -J prep-ys-b4-r2
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH -p mem
#SBATCH --nodes=1
#SBATCH -n 96
#SBATCH --mem-per-cpu=15000
#SBATCH -C "m01&mem1536g"
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/010-Yield-Surface-Generation/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/010-Yield-Surface-Generation/%x.out.%j
#SBATCH --mail-type=END

set -euo pipefail

working_directory="$HPC_SCRATCH/pygalmesh/data/scripts/010-Yield-Surface-Generation"
CONFIG_PATH="/data/scripts/010-Yield-Surface-Generation/config-Bin4-reduce-2.json"
CONTAINER_PATH="$HOME/meshing/Meshing/pygalmesh/pygalmesh.sif"
BIND_PATHS="$HOME/meshing/Meshing/pygalmesh/data:/home,$HPC_SCRATCH/pygalmesh/data:/data"
SIM_CONTAINER="$HOME/dolfinx_alex/alex-dolfinx.sif"
SIM_BIND="$HOME/dolfinx_alex/shared:/home,$HPC_SCRATCH/pygalmesh/data:/data"
VOLUME_FILENAME="volume.npy"
case_scratch="$working_directory/scratch/prepare_mesh_${SLURM_JOB_ID:-manual}"
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

config_bool() {
  srun -n 1 apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" python3 - "$CONFIG_PATH" "$1" <<'PYBOOL'
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
  srun -n 1 apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" python3 - "$CONFIG_PATH" "$1" "$2" <<'PYVAL'
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

CONFIG_INFO=$(srun -n 1 apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" python3 - "$CONFIG_PATH" <<'PYINFO'
import json, sys
with open(sys.argv[1]) as handle:
    config = json.load(handle)
print(config["02b_build_subvolume_arrays"]["subvolume_output_folder"])
PYINFO
)
base_subvolume_folder="${CONFIG_INFO/#\/data/$HPC_SCRATCH/pygalmesh/data}"

for script in 00_dicom_2_npy.py 01_segment_slice_wise.py 02_build3D_segmented_array.py 02a_rotate_pic_to_align_with_axis.py 02b_build_subvolume_arrays.py; do
  run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" python3 "$working_directory/$script" --config "$CONFIG_PATH"
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
  if [[ "$(config_bool 02c_voxel_topology_cleanup.enabled)" == "1" ]]; then
    cleaned_npy_file="$subfolder/$(config_value_default 02c_voxel_topology_cleanup.output_filename volume_topology_cleaned.npy)"
    voxel_report_file="$subfolder/$(config_value_default 02c_voxel_topology_cleanup.report_filename volume_topology.txt)"
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" python3 "$working_directory/02c_voxel_topology_cleanup.py" --config "$CONFIG_PATH" --npy "$npy_file" --output "$cleaned_npy_file" --report "$voxel_report_file"
    if [[ "$(config_bool 02c_voxel_topology_cleanup.use_cleaned_for_meshing)" == "1" ]]; then
      meshing_npy_file="$cleaned_npy_file"
    fi
  fi
  if [[ "$(config_bool 02d_axis_aligned_cuboid_crop.enabled)" == "1" ]]; then
    cuboid_npy_file="$subfolder/$(config_value_default 02d_axis_aligned_cuboid_crop.output_filename volume_cuboid.npy)"
    cuboid_report_file="$subfolder/$(config_value_default 02d_axis_aligned_cuboid_crop.report_filename volume_cuboid.txt)"
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" python3 "$working_directory/02d_axis_aligned_cuboid_crop.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --output "$cuboid_npy_file" --report "$cuboid_report_file"
    if [[ "$(config_bool 02d_axis_aligned_cuboid_crop.use_cuboid_for_meshing)" == "1" ]]; then
      meshing_npy_file="$cuboid_npy_file"
    fi
  fi
  run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" python3 "$working_directory/03_mesh_3D_array_pygalmesh.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --mesh "$mesh_output"
  run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" python3 "$working_directory/04_scale_and_translate_mesh_mod.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --center_x "$center_x" --center_y "$center_y"
  if [[ "$(config_bool 05_tetgen_postprocess.enabled)" == "1" ]]; then
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" python3 "$working_directory/05_tetgen_postprocess_mesh.py" --config "$CONFIG_PATH" --mesh "$mesh_output"
    if [[ "$(config_bool 08_mesh_quality_report.enabled)" == "1" ]]; then
      run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" python3 "$working_directory/08_mesh_quality_report.py" --config "$CONFIG_PATH" --tetgen-log "${mesh_output%.xdmf}.tetgen.log" --output "${mesh_output%.xdmf}.quality.txt"
    fi
  fi
  if [[ "$(config_bool 09_mesh_topology_audit.enabled)" == "1" ]]; then
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" python3 "$working_directory/09_mesh_topology_audit.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --output "${mesh_output%.xdmf}.topology.txt"
  fi
done

for subfolder in "$base_subvolume_folder"/*/; do
  [ -d "$subfolder" ] || continue
  if [ -f "$subfolder/mesh.xdmf" ]; then
    run_container 1 "" "$SIM_BIND" "$SIM_CONTAINER" python3 "$working_directory/make_mesh_dlfx_compatible_cluster.py" "$subfolder" -f mesh.xdmf
  fi
done

rm -rf "$case_scratch"
echo "Prepared Bin4 reduce-2 mesh and DolfinX files."
