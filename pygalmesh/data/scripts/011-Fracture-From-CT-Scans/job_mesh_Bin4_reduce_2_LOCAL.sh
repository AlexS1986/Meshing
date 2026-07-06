#!/usr/bin/env bash
if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_PATH="${CONFIG_PATH:-$SCRIPT_DIR/config-Bin4-reduce-2-local-coarse.json}"
VOLUME_FILENAME="volume.npy"
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

PREPROCESS_SCRIPTS=(
  "00_dicom_2_npy.py"
  "01_segment_slice_wise.py"
  "02_build3D_segmented_array.py"
  "02a_rotate_pic_to_align_with_axis.py"
  "02b_build_subvolume_arrays.py"
)

REQUIRED_COMMANDS=(python3 tetgen)
REQUIRED_PYTHON_MODULES=(
  numpy
  scipy
  skimage
  meshio
  pygalmesh
  pydicom
  matplotlib
  porespy
  mpi4py
  dolfinx
  ufl
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
    sys.exit(1)
PY
}

json_bool() {
  python3 - "$CONFIG_PATH" "$1" <<'PY'
import json, sys
with open(sys.argv[1]) as handle:
    value = json.load(handle)
for key in sys.argv[2].split('.'):
    value = value.get(key, {}) if isinstance(value, dict) else {}
print("1" if value is True else "0")
PY
}

json_value_default() {
  python3 - "$CONFIG_PATH" "$1" "$2" <<'PY'
import json, sys
with open(sys.argv[1]) as handle:
    value = json.load(handle)
for key in sys.argv[2].split('.'):
    if not isinstance(value, dict) or key not in value:
        print(sys.argv[3])
        raise SystemExit
    value = value[key]
print(sys.argv[3] if value is None else value)
PY
}

run_python() {
  echo "+ python3 $*"
  python3 "$@"
}

write_voxel_cross_section() {
  local npy_path="$1"
  local stage_name="$2"
  local output_dir="$3"

  if [[ -f "$npy_path" ]]; then
    run_python "$SCRIPT_DIR/02g_write_voxel_cross_sections.py" \
      --npy "$npy_path" \
      --output-dir "$output_dir" \
      --stage "$stage_name" \
      --axis z
  fi
}

subvolume_folders() {
  python3 - "$CONFIG_PATH" <<'PY'
import json
import os
import sys
with open(sys.argv[1]) as handle:
    config = json.load(handle)
metadata_path = config["metadata_output_path"]
with open(metadata_path) as handle:
    metadata = json.load(handle)
entry = metadata["02b_build_subvolume_arrays.py"]
base = entry["subvolume_output_folder"]
for subvol in entry.get("subvolumes", []):
    print(os.path.join(base, subvol["path"]))
PY
}

require_commands "${REQUIRED_COMMANDS[@]}"
require_python_modules "${REQUIRED_PYTHON_MODULES[@]}"

CONFIG_INFO=$(python3 - "$CONFIG_PATH" <<'PY'
import json, sys
with open(sys.argv[1]) as handle:
    config = json.load(handle)
print(config["binning"]["label"])
print(config["01_segment_slice_wise"]["specimen_name"])
print(config["binning"].get("script_reduce_factor"))
print(config["02b_build_subvolume_arrays"].get("crop_offsets_reference", {}))
PY
)

echo "Generating local mesh for:"
echo "$CONFIG_INFO"
echo "Using config: $CONFIG_PATH"
echo "LOCAL_NPROCS cap: $LOCAL_NPROCS"

for script in "${PREPROCESS_SCRIPTS[@]}"; do
  run_python "$SCRIPT_DIR/$script" --config "$CONFIG_PATH"
done

subvolume_list_file="$(mktemp "${TMPDIR:-/tmp}/subvolumes.XXXXXX")"
trap 'rm -f "$subvolume_list_file"' EXIT
subvolume_folders > "$subvolume_list_file"

while IFS= read -r subfolder; do
  [[ -n "$subfolder" && -d "$subfolder" ]] || continue

  npy_file="$subfolder/$VOLUME_FILENAME"
  mesh_output="$subfolder/mesh.xdmf"
  folder_name="$(basename "$subfolder")"

  if [[ "$folder_name" =~ subvolume_x([0-9]+)_y([0-9]+) ]]; then
    center_x="${BASH_REMATCH[1]}"
    center_y="${BASH_REMATCH[2]}"
  else
    echo "Could not extract center_x and center_y from $folder_name; skipping." >&2
    continue
  fi

  echo "Processing $subfolder"
  meshing_npy_file="$npy_file"
  cross_section_dir="$subfolder/voxel_cross_sections"
  write_voxel_cross_section "$meshing_npy_file" "00_original_subvolume" "$cross_section_dir"

  if [[ "$(json_bool 02c_voxel_topology_cleanup.enabled)" == "1" ]]; then
    cleaned_npy_file="$subfolder/$(json_value_default 02c_voxel_topology_cleanup.output_filename volume_topology_cleaned.npy)"
    voxel_report_file="$subfolder/$(json_value_default 02c_voxel_topology_cleanup.report_filename volume_topology.txt)"
    run_python "$SCRIPT_DIR/02c_voxel_topology_cleanup.py" --config "$CONFIG_PATH" --npy "$npy_file" --output "$cleaned_npy_file" --report "$voxel_report_file"
    write_voxel_cross_section "$cleaned_npy_file" "01_topology_cleanup" "$cross_section_dir"
    if [[ "$(json_bool 02c_voxel_topology_cleanup.use_cleaned_for_meshing)" == "1" ]]; then
      meshing_npy_file="$cleaned_npy_file"
    fi
  fi


  if [[ "$(json_bool 02e_mirror_extrude_voxel.enabled)" == "1" ]]; then
    mirrored_npy_file="$subfolder/$(json_value_default 02e_mirror_extrude_voxel.output_filename volume_mirrored_x.npy)"
    mirrored_report_file="$subfolder/$(json_value_default 02e_mirror_extrude_voxel.report_filename volume_mirrored_x.txt)"
    run_python "$SCRIPT_DIR/02e_mirror_extrude_voxel.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --output "$mirrored_npy_file" --report "$mirrored_report_file"
    write_voxel_cross_section "$mirrored_npy_file" "02_voxel_mirror" "$cross_section_dir"
    if [[ "$(json_bool 02e_mirror_extrude_voxel.use_mirrored_for_meshing)" == "1" ]]; then
      meshing_npy_file="$mirrored_npy_file"
    fi
  fi

  if [[ "$(json_bool 02d_axis_aligned_cuboid_crop.enabled)" == "1" ]]; then
    cuboid_npy_file="$subfolder/$(json_value_default 02d_axis_aligned_cuboid_crop.output_filename volume_cuboid.npy)"
    cuboid_report_file="$subfolder/$(json_value_default 02d_axis_aligned_cuboid_crop.report_filename volume_cuboid.txt)"
    run_python "$SCRIPT_DIR/02d_axis_aligned_cuboid_crop.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --output "$cuboid_npy_file" --report "$cuboid_report_file"
    write_voxel_cross_section "$cuboid_npy_file" "03_internal_aniso_shell" "$cross_section_dir"
    if [[ "$(json_bool 02d_axis_aligned_cuboid_crop.use_cuboid_for_meshing)" == "1" ]]; then
      meshing_npy_file="$cuboid_npy_file"
    fi
  fi

  if [[ "$(json_bool 02f_add_voxel_shell.enabled)" == "1" ]]; then
    shelled_npy_file="$subfolder/$(json_value_default 02f_add_voxel_shell.output_filename volume_additive_shell.npy)"
    shelled_report_file="$subfolder/$(json_value_default 02f_add_voxel_shell.report_filename volume_additive_shell.txt)"
    run_python "$SCRIPT_DIR/02f_add_voxel_shell.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --output "$shelled_npy_file" --report "$shelled_report_file"
    write_voxel_cross_section "$shelled_npy_file" "04_external_shell" "$cross_section_dir"
    if [[ "$(json_bool 02f_add_voxel_shell.use_shell_for_meshing)" == "1" ]]; then
      meshing_npy_file="$shelled_npy_file"
    fi
  fi

  run_python "$SCRIPT_DIR/03_mesh_3D_array_pygalmesh.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --mesh "$mesh_output"
  run_python "$SCRIPT_DIR/04_scale_and_translate_mesh_mod.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --center_x "$center_x" --center_y "$center_y" --npy "$meshing_npy_file"

  if [[ "$(json_bool 10_snap_mesh_to_crop_boundary.enabled)" == "1" ]]; then
    run_python "$SCRIPT_DIR/10_snap_mesh_to_crop_boundary.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --report "${mesh_output%.xdmf}.snap_boundary.txt"
  fi

  if [[ "$(json_bool 11_mirror_extrude_mesh.enabled)" == "1" ]]; then
    run_python "$SCRIPT_DIR/11_mirror_extrude_mesh.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --report "${mesh_output%.xdmf}.mirror_extrude.txt"
  fi

  if [[ "$(json_bool 05_tetgen_postprocess.enabled)" == "1" ]]; then
    run_python "$SCRIPT_DIR/05_tetgen_postprocess_mesh.py" --config "$CONFIG_PATH" --mesh "$mesh_output"
    if [[ "$(json_bool 08_mesh_quality_report.enabled)" == "1" ]]; then
      run_python "$SCRIPT_DIR/08_mesh_quality_report.py" --config "$CONFIG_PATH" --tetgen-log "${mesh_output%.xdmf}.tetgen.log" --output "${mesh_output%.xdmf}.quality.txt"
    fi
  fi

  if [[ "$(json_bool 09_mesh_topology_audit.enabled)" == "1" ]]; then
    run_python "$SCRIPT_DIR/09_mesh_topology_audit.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --output "${mesh_output%.xdmf}.topology.txt"
  fi

  run_python "$SCRIPT_DIR/make_mesh_dlfx_compatible_cluster.py" "$subfolder" -f mesh.xdmf

  echo "Mesh written: $mesh_output"
  echo "DolfinX mesh written: $subfolder/dlfx_mesh.xdmf"
done < "$subvolume_list_file"

echo "Local mesh generation complete."
