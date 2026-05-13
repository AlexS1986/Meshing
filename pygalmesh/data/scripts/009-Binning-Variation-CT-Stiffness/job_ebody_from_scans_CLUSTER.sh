#!/bin/bash
#SBATCH -J ebody-bin
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH --mem-per-cpu=9000
#SBATCH -n 16
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness/%x.out.%j
#SBATCH --mail-type=END
#SBATCH -C i01

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
PY
)

binning_label="$(echo "$CONFIG_INFO" | sed -n '1p')"
run_name="$(echo "$CONFIG_INFO" | sed -n '2p')"
base_subvolume_container_path="$(echo "$CONFIG_INFO" | sed -n '3p')"
base_subvolume_folder="${base_subvolume_container_path/#\/data/$HPC_SCRATCH/pygalmesh/data}"
case_scratch_container="/data/scripts/009-Binning-Variation-CT-Stiffness/scratch/${run_name}_${SLURM_JOB_ID:-manual}"
case_scratch="$HPC_SCRATCH/pygalmesh$case_scratch_container"
export TMPDIR="$case_scratch_container/tmp"

echo "Processing $binning_label"
echo "Using config: $CONFIG_PATH"
echo "Case scratch: $case_scratch"
echo "Container TMPDIR: $TMPDIR"
rm -rf "$case_scratch"
mkdir -p "$case_scratch/tmp"

for script in "${PREPROCESS_SCRIPTS[@]}"; do
  srun -n 1 apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" \
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

  srun -n 1 apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" \
    python3 "$working_directory/03_mesh_3D_array_pygalmesh.py" --config "$CONFIG_PATH" --npy "$npy_file" --mesh "$mesh_output"

  srun -n 1 apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" \
    python3 "$working_directory/04_scale_and_translate_mesh_mod.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --center_x "$center_x" --center_y "$center_y"
done

for subfolder in "$base_subvolume_folder"/*/; do
  [ -d "$subfolder" ] || continue
  if [ -f "$subfolder/mesh.xdmf" ]; then
    srun -n 1 apptainer exec --bind "$SIM_BIND" "$SIM_CONTAINER" \
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

      srun -n 16 --chdir="$subfolder" apptainer exec --bind "$SIM_BIND" "$SIM_CONTAINER" \
        python3 "$subfolder/linearelastic.py" --material "$mat"

      srun -n 1 --chdir="$subfolder" apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" python3 update_trafo.py
      srun -n 1 --chdir="$subfolder" apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" make
      srun -n 1 --chdir="$subfolder" apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" ./trafo.x
      srun -n 1 --chdir="$subfolder" apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" \
        bash -c "Xvfb :99 -screen 0 1024x768x24 & sleep 2 && export DISPLAY=:99 && python3 print_e_body_2_paraview.py"
      srun -n 1 --chdir="$subfolder" apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" python3 find_e33.py
      srun -n 1 --chdir="$subfolder" apptainer exec --bind "$SIM_BIND" "$SIM_CONTAINER" python3 write_e33_to_mesh.py
    done

    mkdir -p "$final_output_dir"
    cp -rv "$base_subvolume_folder" "$final_output_dir/"
    cp -v "$working_directory/${run_name}_segmented/metadata.json" "$final_output_dir/" || true
    cp -v "$HPC_SCRATCH/pygalmesh$CONFIG_PATH" "$final_output_dir/" || true
  done
done

rm -rf "$case_scratch"

srun -n 1 apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" \
  python3 "$working_directory/collect_binning_results.py" --project-dir "$working_directory" --specimen-name "$SPECIMEN_NAME" --config "$CONFIG_PATH"
