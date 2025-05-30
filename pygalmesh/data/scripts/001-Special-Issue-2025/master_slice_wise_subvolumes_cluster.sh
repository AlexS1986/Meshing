#!/bin/bash
#SBATCH -J meshing
#SBATCH -A p0023647
#SBATCH -t 1440           # max time (minutes)
#SBATCH --mem-per-cpu=6000
#SBATCH -n 32
#SBATCH -e $HPC_SCRATCH/pygalmesh/data/scripts/001-Special-Issue-2025/%x.err.%j
#SBATCH -o $HPC_SCRATCH/pygalmesh/data/scripts/001-Special-Issue-2025/%x.out.%j
#SBATCH --mail-type=END
#SBATCH -C i01

# -------------------------------
# Setup
# -------------------------------

set -e  # exit on error

# Working directory inside scratch (adjust if needed)
working_directory="$HPC_SCRATCH/pygalmesh/data/scripts/001-Special-Issue-2025"

# Apptainer container & bind paths
CONTAINER_PATH="$HOME/meshing/Meshing/pygalmesh/pygalmesh.sif"
BIND_PATHS="$HOME/meshing/Meshing/pygalmesh/data:/home,$HPC_SCRATCH/pygalmesh/data:/data"

# Config & base folders inside container (inside /data)
CONFIG_PATH="/data/scripts/001-Special-Issue-2025/config.json"
BASE_SUBVOLUME_FOLDER="/data/scripts/001-Special-Issue-2025/JM-25-24_segmented/JM-25-24_segmented_3D"
VOLUME_FILENAME="volume.npy"

# Python scripts to run
SCRIPTS=(
    "00_dicom_2_npy.py"
    "01_segment_slice_wise.py"
    "02_build3D_segmented_array.py"
    "02a_rotate_pic_to_align_with_axis.py"
    "02b_build_subvolume_arrays.py"
)

# -------------------------------
# Run standard scripts
# -------------------------------

for SCRIPT in "${SCRIPTS[@]}"; do
    echo "🚀 Running $SCRIPT with config: $CONFIG_PATH"
    srun -n 1 apptainer exec --bind $BIND_PATHS $CONTAINER_PATH \
        python3 "$working_directory/$SCRIPT" --config "$CONFIG_PATH"
    echo "✅ Finished $SCRIPT"
    echo "----------------------------"
done

# -------------------------------
# Mesh generation + scaling/translation
# -------------------------------

MESH_SCRIPT="$working_directory/03_mesh_3D_array_pygalmesh.py"
SCALE_SCRIPT="$working_directory/04_scale_and_translate_mesh_mod.py"

echo "🌐 Starting mesh generation using $MESH_SCRIPT"

# Find all volume.npy files
find "$BASE_SUBVOLUME_FOLDER" -type f -name "$VOLUME_FILENAME" | while read -r NPY_FILE; do
    SUBFOLDER=$(dirname "$NPY_FILE")
    FOLDER_NAME=$(basename "$SUBFOLDER")
    MESH_OUTPUT="$SUBFOLDER/mesh.xdmf"

    # Extract center_x and center_y from folder name (e.g. subvolume_x75_y19)
    if [[ "$FOLDER_NAME" =~ subvolume_x([0-9]+)_y([0-9]+) ]]; then
        CENTER_X="${BASH_REMATCH[1]}"
        CENTER_Y="${BASH_REMATCH[2]}"
    else
        echo "❌ Could not extract center_x and center_y from folder name: $FOLDER_NAME"
        exit 1
    fi

    echo "🧩 Meshing: $NPY_FILE -> $MESH_OUTPUT"
    srun -n 1 apptainer exec --bind $BIND_PATHS $CONTAINER_PATH \
        python3 "$MESH_SCRIPT" --config "$CONFIG_PATH" --npy "$NPY_FILE" --mesh "$MESH_OUTPUT"

    echo "✅ Meshed: $MESH_OUTPUT"

    echo "🎯 Scaling and translating mesh with center_x=$CENTER_X, center_y=$CENTER_Y"
    srun -n 1 apptainer exec --bind $BIND_PATHS $CONTAINER_PATH \
        python3 "$SCALE_SCRIPT" --config "$CONFIG_PATH" --mesh "$MESH_OUTPUT" --center_x "$CENTER_X" --center_y "$CENTER_Y"

    echo "✅ Scaled & Translated: $MESH_OUTPUT"
    echo "----------------------------"
done

echo "🎉 All scripts, meshing, and mesh transformations completed successfully."







