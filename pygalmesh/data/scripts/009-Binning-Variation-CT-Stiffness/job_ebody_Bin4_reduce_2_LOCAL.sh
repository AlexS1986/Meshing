#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_PATH="${CONFIG_PATH:-$SCRIPT_DIR/config-Bin4-reduce-2-sdf-pygalmesh-boundary-shell-aniso-sigma1p0.json}"
SOURCE_DIR="$SCRIPT_DIR/00_template"
VOLUME_FILENAME="volume.npy"
MATERIALS=("std")
DIRECTIONS=("x")
OUTPUT_DIRECTORY_VARIABLE="ebody/1-part"

REQUIRED_COMMANDS=(python3 make tetgen)
OPTIONAL_COMMANDS=(mpirun mpiexec Xvfb)
REQUIRED_PYTHON_MODULES=(
  numpy
  pygalmesh
  nanomesh
  skimage
  meshio
  h5py
  pydicom
  matplotlib
  scipy
  porespy
  mpi4py
  dolfinx
  ufl
  alex.homogenization
  alex.linearelastic
  alex.phasefield
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
  python3 - "$@" <<'PY'
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
    print("", file=sys.stderr)
    print("Required Python modules for this local ebody run:", file=sys.stderr)
    print("  " + " ".join(sys.argv[1:]), file=sys.stderr)
    print("", file=sys.stderr)
    print("The DolfinX solve/conversion steps need mpi4py, dolfinx, ufl, and the", file=sys.stderr)
    print("project alex package. This script adds /data/utils to PYTHONPATH for alex,", file=sys.stderr)
    print("but the active container/environment still has to provide the DolfinX stack.", file=sys.stderr)
    sys.exit(1)
PY
}

echo "Checking dependencies for the local ebody pipeline..."
echo "Required commands: ${REQUIRED_COMMANDS[*]}"
echo "Required Python modules: ${REQUIRED_PYTHON_MODULES[*]}"
echo "Optional commands: ${OPTIONAL_COMMANDS[*]} (MPI/Xvfb support when available)"
require_commands "${REQUIRED_COMMANDS[@]}"
require_python_modules "${REQUIRED_PYTHON_MODULES[@]}"

CONFIG_INFO=$(
  python3 - "$CONFIG_PATH" <<'PY'
import json
import sys

with open(sys.argv[1], "r") as handle:
    config = json.load(handle)

print(config["binning"]["label"])
print(config["01_segment_slice_wise"]["specimen_name"])
print(config["02b_build_subvolume_arrays"]["subvolume_output_folder"])
print(config["binning"]["id"])
reduce_factor = config["binning"].get("script_reduce_factor")
print("null" if reduce_factor is None else reduce_factor)
PY
)

binning_label="$(echo "$CONFIG_INFO" | sed -n '1p')"
run_name="$(echo "$CONFIG_INFO" | sed -n '2p')"
base_subvolume_folder="$(echo "$CONFIG_INFO" | sed -n '3p')"
binning_id_config="$(echo "$CONFIG_INFO" | sed -n '4p')"
reduce_factor_config="$(echo "$CONFIG_INFO" | sed -n '5p')"

case_scratch="$SCRIPT_DIR/scratch/${run_name}_local_$$"
mkdir -p "$case_scratch/tmp"
export TMPDIR="$case_scratch/tmp"
trap 'rm -rf "$case_scratch"' EXIT

run_python() {
  echo "+ python3 $*"
  python3 "$@"
}

run_python_in_dir() {
  local chdir="$1"
  shift
  echo "+ (cd $chdir && python3 $*)"
  (cd "$chdir" && python3 "$@")
}

run_solver() {
  local chdir="$1"
  local material="$2"

  if command -v mpirun >/dev/null 2>&1; then
    echo "+ (cd $chdir && mpirun -n $LOCAL_NPROCS python3 linearelastic.py --material $material)"
    (cd "$chdir" && mpirun -n "$LOCAL_NPROCS" python3 linearelastic.py --material "$material")
  elif command -v mpiexec >/dev/null 2>&1; then
    echo "+ (cd $chdir && mpiexec -n $LOCAL_NPROCS python3 linearelastic.py --material $material)"
    (cd "$chdir" && mpiexec -n "$LOCAL_NPROCS" python3 linearelastic.py --material "$material")
  else
    echo "No mpirun/mpiexec found; running solver with a single Python process."
    run_python_in_dir "$chdir" linearelastic.py --material "$material"
  fi
}

echo "Processing $binning_label reduce-$reduce_factor_config locally"
echo "Using config: $CONFIG_PATH"
echo "Using TMPDIR: $TMPDIR"
echo "Solver processes: up to $LOCAL_NPROCS"

for script in "${PREPROCESS_SCRIPTS[@]}"; do
  run_python "$SCRIPT_DIR/$script" --config "$CONFIG_PATH"
done

if [[ "$binning_id_config" == "1" && "$reduce_factor_config" == "null" ]]; then
  echo "Skipping pore-size evaluation for $run_name (Bin1 reduce-null)."
else
  run_python "$SCRIPT_DIR/evaluate_pore_size_distribution.py" \
    --results-dir "$SCRIPT_DIR" \
    --output-dir "$SCRIPT_DIR/00_results/pore_size_distribution" \
    --only-case "${run_name}_segmented" \
    --porespy-cores 1
fi

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
  voxel_cleanup_enabled=$(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
with open(sys.argv[1], "r") as handle:
    config = json.load(handle)
print("1" if config.get("02c_voxel_topology_cleanup", {}).get("enabled", False) else "0")
PY
)
  if [[ "$voxel_cleanup_enabled" == "1" ]]; then
    cleaned_npy_file="$subfolder/$(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
with open(sys.argv[1], "r") as handle:
    config = json.load(handle)
print(config.get("02c_voxel_topology_cleanup", {}).get("output_filename", "volume_topology_cleaned.npy"))
PY
)"
    voxel_report_file="$subfolder/$(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
with open(sys.argv[1], "r") as handle:
    config = json.load(handle)
print(config.get("02c_voxel_topology_cleanup", {}).get("report_filename", "volume_topology.txt"))
PY
)"
    run_python "$SCRIPT_DIR/02c_voxel_topology_cleanup.py" --config "$CONFIG_PATH" --npy "$npy_file" --output "$cleaned_npy_file" --report "$voxel_report_file"
    use_cleaned_for_meshing=$(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
with open(sys.argv[1], "r") as handle:
    config = json.load(handle)
print("1" if config.get("02c_voxel_topology_cleanup", {}).get("use_cleaned_for_meshing", False) else "0")
PY
)
    if [[ "$use_cleaned_for_meshing" == "1" ]]; then
      if [[ ! -f "$cleaned_npy_file" ]]; then
        echo "Voxel cleanup is configured for meshing, but no cleaned file was written: $cleaned_npy_file" >&2
        exit 1
      fi
      meshing_npy_file="$cleaned_npy_file"
    fi
  fi

  cuboid_crop_enabled=$(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
with open(sys.argv[1], "r") as handle:
    config = json.load(handle)
print("1" if config.get("02d_axis_aligned_cuboid_crop", {}).get("enabled", False) else "0")
PY
)
  if [[ "$cuboid_crop_enabled" == "1" ]]; then
    cuboid_npy_file="$subfolder/$(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
with open(sys.argv[1], "r") as handle:
    config = json.load(handle)
print(config.get("02d_axis_aligned_cuboid_crop", {}).get("output_filename", "volume_cuboid.npy"))
PY
)"
    cuboid_report_file="$subfolder/$(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
with open(sys.argv[1], "r") as handle:
    config = json.load(handle)
print(config.get("02d_axis_aligned_cuboid_crop", {}).get("report_filename", "volume_cuboid.txt"))
PY
)"
    run_python "$SCRIPT_DIR/02d_axis_aligned_cuboid_crop.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --output "$cuboid_npy_file" --report "$cuboid_report_file"
    use_cuboid_for_meshing=$(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
with open(sys.argv[1], "r") as handle:
    config = json.load(handle)
print("1" if config.get("02d_axis_aligned_cuboid_crop", {}).get("use_cuboid_for_meshing", False) else "0")
PY
)
    if [[ "$use_cuboid_for_meshing" == "1" ]]; then
      if [[ ! -f "$cuboid_npy_file" ]]; then
        echo "Cuboid voxel preprocessing is configured for meshing, but no cuboid file was written: $cuboid_npy_file" >&2
        exit 1
      fi
      meshing_npy_file="$cuboid_npy_file"
    fi
  fi

  run_python "$SCRIPT_DIR/03_mesh_3D_array_pygalmesh.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --mesh "$mesh_output"
  run_python "$SCRIPT_DIR/04_scale_and_translate_mesh_mod.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --center_x "$center_x" --center_y "$center_y"

  tetgen_enabled=$(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
with open(sys.argv[1], "r") as handle:
    config = json.load(handle)
print("1" if config.get("05_tetgen_postprocess", {}).get("enabled", False) else "0")
PY
)
  if [[ "$tetgen_enabled" == "1" ]]; then
    run_python "$SCRIPT_DIR/05_tetgen_postprocess_mesh.py" --config "$CONFIG_PATH" --mesh "$mesh_output"
    quality_report_enabled=$(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
with open(sys.argv[1], "r") as handle:
    config = json.load(handle)
print("1" if config.get("08_mesh_quality_report", {}).get("enabled", False) else "0")
PY
)
    if [[ "$quality_report_enabled" == "1" ]]; then
      run_python "$SCRIPT_DIR/08_mesh_quality_report.py" --config "$CONFIG_PATH" --tetgen-log "${mesh_output%.xdmf}.tetgen.log" --output "${mesh_output%.xdmf}.quality.txt"
    fi
  fi

  topology_audit_enabled=$(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
with open(sys.argv[1], "r") as handle:
    config = json.load(handle)
print("1" if config.get("09_mesh_topology_audit", {}).get("enabled", False) else "0")
PY
)
  if [[ "$topology_audit_enabled" == "1" ]]; then
    run_python "$SCRIPT_DIR/09_mesh_topology_audit.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --output "${mesh_output%.xdmf}.topology.txt"
  fi

  gmsh_enabled=$(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
with open(sys.argv[1], "r") as handle:
    config = json.load(handle)
print("1" if config.get("06_gmsh_postprocess", {}).get("enabled", False) else "0")
PY
)
  if [[ "$gmsh_enabled" == "1" ]]; then
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
    output_tag="${mat}-${direction}"
    final_output_dir="$SCRIPT_DIR/00_results/${SPECIMEN_NAME}/${binning_label}/${OUTPUT_DIRECTORY_VARIABLE}/${run_name}-${output_tag}"

    for subfolder in "$base_subvolume_folder"/*/; do
      [[ -d "$subfolder" ]] || continue

      find "$SOURCE_DIR" -maxdepth 1 -type f -exec cp -v {} "$subfolder" \;
      cp -v "$CONFIG_PATH" "$subfolder/config.json"

      run_solver "$subfolder" "$mat"
      run_python_in_dir "$subfolder" update_trafo.py
      (cd "$subfolder" && make)
      (cd "$subfolder" && ./trafo.x)

      if command -v Xvfb >/dev/null 2>&1; then
        (cd "$subfolder" && Xvfb :99 -screen 0 1024x768x24 >/tmp/xvfb-bin4-r2.log 2>&1 &)
        sleep 2
        (cd "$subfolder" && DISPLAY=:99 python3 print_e_body_2_paraview.py)
      else
        run_python_in_dir "$subfolder" print_e_body_2_paraview.py
      fi

      run_python_in_dir "$subfolder" find_e33.py
      run_python_in_dir "$subfolder" write_e33_to_mesh.py
    done

    mkdir -p "$final_output_dir"
    cp -rv "$base_subvolume_folder" "$final_output_dir/"
    cp -v "$SCRIPT_DIR/${run_name}_segmented/metadata.json" "$final_output_dir/" || true
    cp -v "$CONFIG_PATH" "$final_output_dir/" || true
  done
done

run_python "$SCRIPT_DIR/collect_binning_results.py" --project-dir "$SCRIPT_DIR" --specimen-name "$SPECIMEN_NAME" --config "$CONFIG_PATH"

echo "Done. Results were written under:"
echo "$SCRIPT_DIR/00_results/${SPECIMEN_NAME}/${binning_label}/${OUTPUT_DIRECTORY_VARIABLE}"
