#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_PATH="${CONFIG_PATH:-$SCRIPT_DIR/config-Bin4-reduce-2.json}"
SOURCE_DIR="$SCRIPT_DIR/00_template"
VOLUME_FILENAME="volume.npy"
OUTPUT_DIRECTORY_VARIABLE="yield_surface"

REQUIRED_COMMANDS=(python3 tetgen)
OPTIONAL_COMMANDS=(mpirun mpiexec)
REQUIRED_PYTHON_MODULES=(
  numpy
  pygalmesh
  skimage
  meshio
  h5py
  pydicom
  matplotlib
  scipy
  mpi4py
  dolfinx
  ufl
  alex.plasticity
  alex.linearelastic
  alex.util
  alex.os
  alex.boundaryconditions
  alex.postprocessing
  alex.solution
  gmsh
)

LOCAL_NPROCS="${LOCAL_NPROCS:-6}"
if ! [[ "$LOCAL_NPROCS" =~ ^[0-9]+$ ]] || [[ "$LOCAL_NPROCS" -lt 1 ]]; then
  echo "LOCAL_NPROCS must be a positive integer; got '$LOCAL_NPROCS'." >&2
  exit 2
fi
if [[ "$LOCAL_NPROCS" -gt 6 ]]; then
  echo "LOCAL_NPROCS=$LOCAL_NPROCS requested; capping at 6 for this local run."
  LOCAL_NPROCS=6
fi

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"
export PYTHONPATH="/data/utils${PYTHONPATH:+:$PYTHONPATH}"
export OMPI_ALLOW_RUN_AS_ROOT=1
export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1

# shellcheck source=/dev/null
source "$SCRIPT_DIR/config.sh"

PREPROCESS_SCRIPTS=(
  "00_dicom_2_npy.py"
  "01_segment_slice_wise.py"
  "02_build3D_segmented_array.py"
  "02a_rotate_pic_to_align_with_axis.py"
  "02b_build_subvolume_arrays.py"
)

require_commands() {
  local missing=()
  local command_name
  for command_name in "$@"; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
      missing+=("$command_name")
    fi
  done
  if [[ "${#missing[@]}" -gt 0 ]]; then
    echo "Missing required command(s): ${missing[*]}" >&2
    exit 1
  fi
}

require_python_modules() {
  python3 - "$@" <<'PYMODS'
import importlib
import sys
missing = []
for module in sys.argv[1:]:
    try:
        importlib.import_module(module)
    except Exception as exc:
        missing.append(f"{module} ({exc})")
if missing:
    print("Missing or broken required Python module(s): " + "; ".join(missing), file=sys.stderr)
    sys.exit(1)
PYMODS
}

json_bool() {
  python3 - "$CONFIG_PATH" "$1" <<'PYBOOL'
import json
import sys
with open(sys.argv[1]) as handle:
    config = json.load(handle)
value = config
for key in sys.argv[2].split('.'):
    value = value.get(key, {}) if isinstance(value, dict) else {}
print("1" if value is True else "0")
PYBOOL
}

json_value_default() {
  python3 - "$CONFIG_PATH" "$1" "$2" <<'PYVAL'
import json
import sys
with open(sys.argv[1]) as handle:
    config = json.load(handle)
value = config
for key in sys.argv[2].split('.'):
    if not isinstance(value, dict) or key not in value:
        print(sys.argv[3])
        raise SystemExit
    value = value[key]
print(sys.argv[3] if value is None else value)
PYVAL
}

run_python() {
  echo "+ python3 $*"
  python3 "$@"
}

run_solver() {
  local chdir="$1"
  local material="$2"
  local direction="$3"
  local cmd=(python3 elastoplastic.py --material "$material" --loading-direction "$direction" --config config.json)
  if command -v mpirun >/dev/null 2>&1; then
    echo "+ (cd $chdir && mpirun -n $LOCAL_NPROCS ${cmd[*]})"
    (cd "$chdir" && mpirun -n "$LOCAL_NPROCS" "${cmd[@]}")
  elif command -v mpiexec >/dev/null 2>&1; then
    echo "+ (cd $chdir && mpiexec -n $LOCAL_NPROCS ${cmd[*]})"
    (cd "$chdir" && mpiexec -n "$LOCAL_NPROCS" "${cmd[@]}")
  else
    echo "No mpirun/mpiexec found; running solver with a single Python process."
    (cd "$chdir" && "${cmd[@]}")
  fi
}

echo "Checking dependencies for the local yield-surface pipeline..."
require_commands "${REQUIRED_COMMANDS[@]}"
require_python_modules "${REQUIRED_PYTHON_MODULES[@]}"

CONFIG_INFO=$(python3 - "$CONFIG_PATH" <<'PYINFO'
import json
import sys
with open(sys.argv[1]) as handle:
    config = json.load(handle)
print(config["binning"]["label"])
print(config["01_segment_slice_wise"]["specimen_name"])
print(config["02b_build_subvolume_arrays"]["subvolume_output_folder"])
print(" ".join(config.get("yield_surface", {}).get("materials", ["std"])))
print(" ".join(config.get("yield_surface", {}).get("loading_directions", ["x"])))
PYINFO
)

binning_label="$(echo "$CONFIG_INFO" | sed -n '1p')"
run_name="$(echo "$CONFIG_INFO" | sed -n '2p')"
base_subvolume_folder="$(echo "$CONFIG_INFO" | sed -n '3p')"
materials_line="$(echo "$CONFIG_INFO" | sed -n '4p')"
directions_line="$(echo "$CONFIG_INFO" | sed -n '5p')"
read -r -a MATERIALS <<< "$materials_line"
read -r -a DIRECTIONS <<< "$directions_line"

case_scratch="$SCRIPT_DIR/scratch/${run_name}_yield_local_$$"
mkdir -p "$case_scratch/tmp"
export TMPDIR="$case_scratch/tmp"
trap 'rm -rf "$case_scratch"' EXIT

echo "Processing $binning_label locally for yield-surface generation"
echo "Using config: $CONFIG_PATH"
echo "Materials: ${MATERIALS[*]}"
echo "Directions: ${DIRECTIONS[*]}"
echo "Solver processes: up to $LOCAL_NPROCS"

for script in "${PREPROCESS_SCRIPTS[@]}"; do
  run_python "$SCRIPT_DIR/$script" --config "$CONFIG_PATH"
done

for subfolder in "$base_subvolume_folder"/subvolume_x*_y*/; do
  [[ -d "$subfolder" ]] || continue
  npy_file="$subfolder/$VOLUME_FILENAME"
  mesh_output="$subfolder/mesh.xdmf"
  folder_name="$(basename "$subfolder")"
  if [[ "$folder_name" =~ subvolume_x([0-9]+)_y([0-9]+) ]]; then
    center_x="${BASH_REMATCH[1]}"
    center_y="${BASH_REMATCH[2]}"
  else
    echo "Could not extract center_x and center_y from $folder_name; skipping."
    continue
  fi

  meshing_npy_file="$npy_file"
  if [[ "$(json_bool 02c_voxel_topology_cleanup.enabled)" == "1" ]]; then
    cleaned_npy_file="$subfolder/$(json_value_default 02c_voxel_topology_cleanup.output_filename volume_topology_cleaned.npy)"
    voxel_report_file="$subfolder/$(json_value_default 02c_voxel_topology_cleanup.report_filename volume_topology.txt)"
    run_python "$SCRIPT_DIR/02c_voxel_topology_cleanup.py" --config "$CONFIG_PATH" --npy "$npy_file" --output "$cleaned_npy_file" --report "$voxel_report_file"
    if [[ "$(json_bool 02c_voxel_topology_cleanup.use_cleaned_for_meshing)" == "1" ]]; then
      meshing_npy_file="$cleaned_npy_file"
    fi
  fi

  if [[ "$(json_bool 02d_axis_aligned_cuboid_crop.enabled)" == "1" ]]; then
    cuboid_npy_file="$subfolder/$(json_value_default 02d_axis_aligned_cuboid_crop.output_filename volume_cuboid.npy)"
    cuboid_report_file="$subfolder/$(json_value_default 02d_axis_aligned_cuboid_crop.report_filename volume_cuboid.txt)"
    run_python "$SCRIPT_DIR/02d_axis_aligned_cuboid_crop.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --output "$cuboid_npy_file" --report "$cuboid_report_file"
    if [[ "$(json_bool 02d_axis_aligned_cuboid_crop.use_cuboid_for_meshing)" == "1" ]]; then
      meshing_npy_file="$cuboid_npy_file"
    fi
  fi

  run_python "$SCRIPT_DIR/03_mesh_3D_array_pygalmesh.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --mesh "$mesh_output"
  run_python "$SCRIPT_DIR/04_scale_and_translate_mesh_mod.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --center_x "$center_x" --center_y "$center_y"

  if [[ "$(json_bool 05_tetgen_postprocess.enabled)" == "1" ]]; then
    run_python "$SCRIPT_DIR/05_tetgen_postprocess_mesh.py" --config "$CONFIG_PATH" --mesh "$mesh_output"
    if [[ "$(json_bool 08_mesh_quality_report.enabled)" == "1" ]]; then
      run_python "$SCRIPT_DIR/08_mesh_quality_report.py" --config "$CONFIG_PATH" --tetgen-log "${mesh_output%.xdmf}.tetgen.log" --output "${mesh_output%.xdmf}.quality.txt"
    fi
  fi

  if [[ "$(json_bool 09_mesh_topology_audit.enabled)" == "1" ]]; then
    run_python "$SCRIPT_DIR/09_mesh_topology_audit.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --output "${mesh_output%.xdmf}.topology.txt"
  fi

  if [[ "$(json_bool 06_gmsh_postprocess.enabled)" == "1" ]]; then
    run_python "$SCRIPT_DIR/06_gmsh_postprocess_mesh.py" --config "$CONFIG_PATH" --mesh "$mesh_output"
  fi
done

for subfolder in "$base_subvolume_folder"/*/; do
  [[ -d "$subfolder" ]] || continue
  if [[ -f "$subfolder/mesh.xdmf" ]]; then
    run_python "$SCRIPT_DIR/make_mesh_dlfx_compatible_cluster.py" "$subfolder" -f mesh.xdmf
  fi
done

for mat in "${MATERIALS[@]}"; do
  for direction in "${DIRECTIONS[@]}"; do
    final_output_dir="$SCRIPT_DIR/00_results/${SPECIMEN_NAME}/${binning_label}/${OUTPUT_DIRECTORY_VARIABLE}/${run_name}-${mat}-${direction}"
    for subfolder in "$base_subvolume_folder"/*/; do
      [[ -d "$subfolder" ]] || continue
      find "$SOURCE_DIR" -maxdepth 1 -type f -exec cp -v {} "$subfolder" \;
      cp -v "$CONFIG_PATH" "$subfolder/config.json"
      run_solver "$subfolder" "$mat" "$direction"
    done
    mkdir -p "$final_output_dir"
    cp -rv "$base_subvolume_folder" "$final_output_dir/"
    cp -v "$SCRIPT_DIR/${run_name}_segmented/metadata.json" "$final_output_dir/" || true
    cp -v "$CONFIG_PATH" "$final_output_dir/" || true
  done
done

echo "Done. Results were written under:"
echo "$SCRIPT_DIR/00_results/${SPECIMEN_NAME}/${binning_label}/${OUTPUT_DIRECTORY_VARIABLE}"
