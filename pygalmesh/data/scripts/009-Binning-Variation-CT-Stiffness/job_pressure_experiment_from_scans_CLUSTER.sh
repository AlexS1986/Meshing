#!/bin/bash

#SBATCH -J pressure-bin

#SBATCH -A p0023647

#SBATCH -t 1440

#SBATCH -n 96
#SBATCH -N 1
#SBATCH --mem-per-cpu=9000

#SBATCH -C "mem"

#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness/%x.err.%j

#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness/%x.out.%j

#SBATCH --mail-type=END
set -euo pipefail

working_directory="$HPC_SCRATCH/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness"
source "$working_directory/config.sh"

CONTAINER_PATH="$HOME/meshing/Meshing/pygalmesh/pygalmesh.sif"
BIND_PATHS="$HOME/meshing/Meshing/pygalmesh/data:/home,$HPC_SCRATCH/pygalmesh/data:/data"
SIM_CONTAINER="$HOME/dolfinx_alex/alex-dolfinx.sif"
SIM_BIND="$HOME/dolfinx_alex/shared:/home"

SOURCE_DIR="$working_directory/00_template"
sim_ntasks="${SLURM_NTASKS:-96}"
VOLUME_FILENAME="volume.npy"
EXTEND_SCRIPT="$working_directory/02c_extend_image_pressure_experiment.py"
EXTEND_THICKNESS=10
MATERIALS=("std" "Conv" "AM")
DIRECTIONS=("x" "y")

PRE_SCRIPTS=(
  "00_dicom_2_npy.py"
  "01_segment_slice_wise.py"
  "02_build3D_segmented_array.py"
  "02a_rotate_pic_to_align_with_axis.py"
)

for binning_id in "${BINNING_IDS[@]}"; do
  binning_label="Bin${binning_id}"
  run_name="${SPECIMEN_NAME}_${binning_label}"
  config_path="/data/scripts/009-Binning-Variation-CT-Stiffness/config-${binning_label}.json"
  base_subvolume_folder="$working_directory/${run_name}_segmented/${run_name}_segmented_3D"

  for script in "${PRE_SCRIPTS[@]}"; do
    srun -n 1 apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/$script" --config "$config_path"
  done

  for mat in "${MATERIALS[@]}"; do
    for dir in "${DIRECTIONS[@]}"; do
      srun -n 1 apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" \
        python3 "$working_directory/02b_build_subvolume_arrays.py" --config "$config_path"

      find "$base_subvolume_folder" -type f -name "$VOLUME_FILENAME" | while read -r npy_file; do
        srun -n 1 apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" \
          python3 "$EXTEND_SCRIPT" "$npy_file" "$dir" --thickness "$EXTEND_THICKNESS"
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
          python3 "$working_directory/03_mesh_3D_array_pygalmesh.py" --config "$config_path" --npy "$npy_file" --mesh "$mesh_output"
        srun -n 1 apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" \
          python3 "$working_directory/04_scale_and_translate_mesh_mod.py" --config "$config_path" --mesh "$mesh_output" --center_x "$center_x" --center_y "$center_y"
      done

      for subfolder in "$base_subvolume_folder"/*/; do
        [ -d "$subfolder" ] || continue
        [ -f "$subfolder/mesh.xdmf" ] || continue

        srun -n 1 apptainer exec --bind "$SIM_BIND" "$SIM_CONTAINER" \
          python3 "$working_directory/make_mesh_dlfx_compatible_cluster.py" "$subfolder" -f mesh.xdmf
        cp -v "$SOURCE_DIR"/* "$subfolder"
        srun -n "$sim_ntasks" --chdir="$subfolder" apptainer exec --bind "$SIM_BIND" "$SIM_CONTAINER" \
          python3 "$subfolder/linearelastic_pressure_test.py" "$mat" "$dir"
      done

      final_output_dir="$working_directory/00_results/${SPECIMEN_NAME}/${binning_label}/pressure_experiment/${run_name}-${mat}-${dir}"
      mkdir -p "$final_output_dir"
      cp -rv "$base_subvolume_folder" "$final_output_dir/"
      cp -v "$working_directory/${run_name}_segmented/metadata.json" "$final_output_dir/" || true
      cp -v "$HPC_SCRATCH/pygalmesh$config_path" "$final_output_dir/" || true
    done
  done
done
