#!/bin/bash

#SBATCH -J ebody-bin
#SBATCH -A p0023647
#SBATCH -t 1440

#SBATCH -p mem
#SBATCH --nodes=1
#SBATCH -n 96
#SBATCH --mem-per-cpu=15000
#SBATCH -C "m01&mem1536g"

#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness/%x.out.%j

#SBATCH --mail-type=END

set -euo pipefail

working_directory="$HPC_SCRATCH/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness"
source "$working_directory/config.sh"

SELECTED_BINNING_ID="${1:-2}"
CONFIG_ARG="${2:-config-Bin${SELECTED_BINNING_ID}.json}"
if [[ "$CONFIG_ARG" = /* ]]; then
  CONFIG_PATH="$CONFIG_ARG"
else
  CONFIG_PATH="/data/scripts/009-Binning-Variation-CT-Stiffness/$CONFIG_ARG"
fi

CONTAINER_PATH="$HOME/meshing/Meshing/pygalmesh/pygalmesh.sif"
BIND_PATHS="$HOME/meshing/Meshing/pygalmesh/data:/home,$HPC_SCRATCH/pygalmesh/data:/data"
SIM_CONTAINER="$HOME/dolfinx_alex/alex-dolfinx.sif"
SIM_BIND="$HOME/dolfinx_alex/shared:/home"

SOURCE_DIR="$working_directory/00_template"
VOLUME_FILENAME="volume.npy"
MATERIALS=("std")
DIRECTIONS=("x")
output_directory_variable="ebody/1-part"

PREPROCESS_SCRIPTS=(
  "00_dicom_2_npy.py"
  "01_segment_slice_wise.py"
  "02_build3D_segmented_array.py"
  "02a_rotate_pic_to_align_with_axis.py"
  "02b_build_subvolume_arrays.py"
)

CONFIG_INFO=$(
  srun -n 1 apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" \
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
base_subvolume_container_path="$(echo "$CONFIG_INFO" | sed -n '3p')"
binning_id_config="$(echo "$CONFIG_INFO" | sed -n '4p')"
reduce_factor_config="$(echo "$CONFIG_INFO" | sed -n '5p')"
base_subvolume_folder="${base_subvolume_container_path/#\/data/$HPC_SCRATCH/pygalmesh/data}"
case_scratch="$working_directory/scratch/${run_name}_${SLURM_JOB_ID:-manual}"
sim_ntasks="${SLURM_NTASKS:-96}"

echo "Processing $binning_label"
echo "Using config: $CONFIG_PATH"
echo "Case scratch: $case_scratch"
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
    echo "TMPDIR: $TMPDIR"
    apptainer exec --bind "$bind_paths,$case_scratch:$case_scratch" "$container" "$@"
  ' bash "$case_scratch" "$bind_paths" "$container" "$@"
}

for script in "${PREPROCESS_SCRIPTS[@]}"; do
  run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
    python3 "$working_directory/$script" --config "$CONFIG_PATH"
done

if [[ "$binning_id_config" == "1" && "$reduce_factor_config" == "null" ]]; then
  echo "Skipping pore-size evaluation for $run_name (Bin1 reduce-null)."
else
  run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
    python3 "$working_directory/evaluate_pore_size_distribution.py" \
      --results-dir "$working_directory" \
      --output-dir "$working_directory/00_results/pore_size_distribution" \
      --only-case "${run_name}_segmented" \
      --porespy-cores 1
fi

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
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH"       python3 "$working_directory/02d_axis_aligned_cuboid_crop.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --output "$cuboid_npy_file" --report "$cuboid_report_file"
    use_cuboid_for_meshing=$(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
with open(sys.argv[1], "r") as handle:
    config = json.load(handle)
print("1" if config.get("02d_axis_aligned_cuboid_crop", {}).get("use_cuboid_for_meshing", False) else "0")
PY
)
    if [[ "$use_cuboid_for_meshing" == "1" ]]; then
      meshing_npy_file="$cuboid_npy_file"
    fi
  fi

  run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH"     python3 "$working_directory/03_mesh_3D_array_pygalmesh.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --mesh "$mesh_output"

  run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH"     python3 "$working_directory/04_scale_and_translate_mesh_mod.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --center_x "$center_x" --center_y "$center_y"

  tetgen_enabled=$(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
with open(sys.argv[1], "r") as handle:
    config = json.load(handle)
print("1" if config.get("05_tetgen_postprocess", {}).get("enabled", False) else "0")
PY
)
  if [[ "$tetgen_enabled" == "1" ]]; then
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH"       python3 "$working_directory/05_tetgen_postprocess_mesh.py" --config "$CONFIG_PATH" --mesh "$mesh_output"
    quality_report_enabled=$(python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
with open(sys.argv[1], "r") as handle:
    config = json.load(handle)
print("1" if config.get("08_mesh_quality_report", {}).get("enabled", False) else "0")
PY
)
    if [[ "$quality_report_enabled" == "1" ]]; then
      run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH"         python3 "$working_directory/08_mesh_quality_report.py" --config "$CONFIG_PATH" --tetgen-log "${mesh_output%.xdmf}.tetgen.log" --output "${mesh_output%.xdmf}.quality.txt"
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
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH"       python3 "$working_directory/09_mesh_topology_audit.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --output "${mesh_output%.xdmf}.topology.txt"
  fi
done

for subfolder in "$base_subvolume_folder"/*/; do
  [ -d "$subfolder" ] || continue
  if [ -f "$subfolder/mesh.xdmf" ]; then
    run_container 1 "" "$SIM_BIND" "$SIM_CONTAINER" \
      python3 "$working_directory/make_mesh_dlfx_compatible_cluster.py" "$subfolder" -f mesh.xdmf
  fi
done

for mat in "${MATERIALS[@]}"; do
  for dir in "${DIRECTIONS[@]}"; do
    output_tag="${mat}-${dir}"
    final_output_dir="$working_directory/00_results/${SPECIMEN_NAME}/${binning_label}/${output_directory_variable}/${run_name}-${output_tag}"

    for subfolder in "$base_subvolume_folder"/*/; do
      [ -d "$subfolder" ] || continue

      cp -v "$SOURCE_DIR"/* "$subfolder"
      cp -v "$CONFIG_PATH" "$subfolder/config.json"

      run_container "$sim_ntasks" "$subfolder" "$SIM_BIND" "$SIM_CONTAINER" \
        python3 "$subfolder/linearelastic.py" --material "$mat"

      run_container 1 "$subfolder" "$BIND_PATHS" "$CONTAINER_PATH" python3 update_trafo.py
      run_container 1 "$subfolder" "$BIND_PATHS" "$CONTAINER_PATH" make
      run_container 1 "$subfolder" "$BIND_PATHS" "$CONTAINER_PATH" ./trafo.x
      run_container 1 "$subfolder" "$BIND_PATHS" "$CONTAINER_PATH" \
        bash -c "Xvfb :99 -screen 0 1024x768x24 & sleep 2 && export DISPLAY=:99 && python3 print_e_body_2_paraview.py"
      run_container 1 "$subfolder" "$BIND_PATHS" "$CONTAINER_PATH" python3 find_e33.py
      run_container 1 "$subfolder" "$SIM_BIND" "$SIM_CONTAINER" python3 write_e33_to_mesh.py
    done

    mkdir -p "$final_output_dir"
    cp -rv "$base_subvolume_folder" "$final_output_dir/"
    cp -v "$working_directory/${run_name}_segmented/metadata.json" "$final_output_dir/" || true
    cp -v "$HPC_SCRATCH/pygalmesh$CONFIG_PATH" "$final_output_dir/" || true
  done
done

run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
  python3 "$working_directory/collect_binning_results.py" --project-dir "$working_directory" --specimen-name "$SPECIMEN_NAME" --config "$CONFIG_PATH"

rm -rf "$case_scratch"
