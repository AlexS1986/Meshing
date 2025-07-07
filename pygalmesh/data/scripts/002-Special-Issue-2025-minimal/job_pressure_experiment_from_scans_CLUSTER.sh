#!/bin/bash
#SBATCH -J ebody
#SBATCH -A p0023647
#SBATCH -t 1440                   # max time in minutes
#SBATCH --mem-per-cpu=6000
#SBATCH -n 32
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/002-Special-Issue-2025-minimal/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/002-Special-Issue-2025-minimal/%x.out.%j
#SBATCH --mail-type=END
#SBATCH -C i01

set -e

# -------------------------------
# Setup
# -------------------------------

working_directory="$HPC_SCRATCH/pygalmesh/data/scripts/002-Special-Issue-2025-minimal"
CONTAINER_PATH="$HOME/meshing/Meshing/pygalmesh/pygalmesh.sif"
BIND_PATHS="$HOME/meshing/Meshing/pygalmesh/data:/home,$HPC_SCRATCH/pygalmesh/data:/data"
CONFIG_PATH="/data/scripts/002-Special-Issue-2025-minimal/config-JM-25-24.json"
BASE_SUBVOLUME_FOLDER="$HPC_SCRATCH/pygalmesh/data/scripts/002-Special-Issue-2025-minimal/JM-25-24_segmented/JM-25-24_segmented_3D"
VOLUME_FILENAME="volume.npy"

SIM_CONTAINER="$HOME/dolfinx_alex/alex-dolfinx.sif"
SIM_BIND="$HOME/dolfinx_alex/shared:/home"

SOURCE_DIR="$working_directory/00_template"
TARGET_DIR="$BASE_SUBVOLUME_FOLDER"
MESH_INPUT_DIR="$BASE_SUBVOLUME_FOLDER"
SIM_SCRIPT="linearelastic_pressure_test.py"

# -------------------------------
# Preprocessing, meshing, etc.
# -------------------------------
# You can comment out this section if already run once.

SCRIPTS=(
    "00_dicom_2_npy.py"
    "01_segment_slice_wise.py"
    "02_build3D_segmented_array.py"
    "02a_rotate_pic_to_align_with_axis.py"
    "02b_build_subvolume_arrays.py"
)

for SCRIPT in "${SCRIPTS[@]}"; do
    echo "🚀 Running preprocessing: $SCRIPT"
    srun -n 1 apptainer exec --bind $BIND_PATHS $CONTAINER_PATH \
        python3 "$working_directory/$SCRIPT" --config "$CONFIG_PATH"
    echo "✅ Finished: $SCRIPT"
    echo "----------------------------"
done

MESH_SCRIPT="$working_directory/03_mesh_3D_array_pygalmesh.py"
SCALE_SCRIPT="$working_directory/04_scale_and_translate_mesh_mod.py"

echo "🌐 Starting mesh generation and transformation"

for SUBFOLDER in "$BASE_SUBVOLUME_FOLDER"/subvolume_x*_y*/; do
    [ -d "$SUBFOLDER" ] || continue
    NPY_FILE="$SUBFOLDER/$VOLUME_FILENAME"
    MESH_OUTPUT="$SUBFOLDER/mesh.xdmf"
    FOLDER_NAME=$(basename "$SUBFOLDER")

    if [ ! -f "$NPY_FILE" ]; then
        echo "⚠️  Skipping $SUBFOLDER — $VOLUME_FILENAME not found."
        continue
    fi

    if [[ "$FOLDER_NAME" =~ subvolume_x([0-9]+)_y([0-9]+) ]]; then
        CENTER_X="${BASH_REMATCH[1]}"
        CENTER_Y="${BASH_REMATCH[2]}"
    else
        echo "❌ Could not extract center_x and center_y from: $FOLDER_NAME"
        continue
    fi

    echo "🧩 Meshing $NPY_FILE using $MESH_SCRIPT"
    srun -n 1 apptainer exec --bind $BIND_PATHS $CONTAINER_PATH \
        python3 "$MESH_SCRIPT" --config "$CONFIG_PATH" --npy "$NPY_FILE" --mesh "$MESH_OUTPUT"

    echo "🎯 Scaling and translating mesh using $SCALE_SCRIPT"
    srun -n 1 apptainer exec --bind $BIND_PATHS $CONTAINER_PATH \
        python3 "$SCALE_SCRIPT" --config "$CONFIG_PATH" --mesh "$MESH_OUTPUT" --center_x "$CENTER_X" --center_y "$CENTER_Y"

    echo "✅ Completed mesh transformation for: $SUBFOLDER"
    echo "----------------------------"
done

echo "🔁 Converting mesh files in subfolders of: $MESH_INPUT_DIR using make_mesh_dlfx_compatible_cluster.py"

for subfolder in "$MESH_INPUT_DIR"/*/; do
    [ -d "$subfolder" ] || continue

    if [ -f "$subfolder/mesh.xdmf" ]; then
        echo "🔄 Converting: $subfolder/mesh.xdmf"
        srun -n 1 apptainer exec --bind $SIM_BIND $SIM_CONTAINER \
            python3 "$working_directory/make_mesh_dlfx_compatible_cluster.py" "$subfolder" -f mesh.xdmf
        echo "✅ Done converting: $subfolder"
    else
        echo "⚠️  Skipping $subfolder — mesh.xdmf not found."
    fi
done

# -------------------------------
# Simulation & Postprocessing for all parameter combinations
# -------------------------------

materials=("Conv" "AM")
directions=("x" "y")

for material in "${materials[@]}"; do
    for direction in "${directions[@]}"; do

        OUTPUT_TAG="${material}_${direction}"
        FINAL_OUTPUT_DIR="$working_directory/16-parts-JM-25-24-$OUTPUT_TAG"
        echo "🚀 Starting simulations for $OUTPUT_TAG"

        for subfolder in "$TARGET_DIR"/*/; do
            [ -d "$subfolder" ] || continue
            echo "⚙️  Running simulation in: $subfolder [$OUTPUT_TAG]"

            if [ -d "$working_directory/scratch" ]; then
                echo "🧹 Removing scratch directory"
                rm -rf "$working_directory/scratch"
            fi

            cp -v "$SOURCE_DIR"/* "$subfolder"
            rm -rf "$working_directory/scratch"
            sleep 2s

            echo "🔬 Running $SIM_SCRIPT with material=$material, direction=$direction"
            srun -n 32 --chdir="$subfolder" apptainer exec --bind $SIM_BIND $SIM_CONTAINER \
                python3 "$subfolder/$SIM_SCRIPT" "$material" "$direction"

            echo "📈 Plotting results"
            srun -n 1 --chdir="$subfolder" apptainer exec --bind $BIND_PATHS $CONTAINER_PATH \
                python3 plot_pressure_experiment_results.py
        done

        echo "📦 Archiving results for $OUTPUT_TAG"
        mkdir -p "$FINAL_OUTPUT_DIR"
        cp -rv "$BASE_SUBVOLUME_FOLDER" "$FINAL_OUTPUT_DIR/"
        PARENT_DIR="$(dirname "$BASE_SUBVOLUME_FOLDER")"
        if [ -f "$PARENT_DIR/metadata.json" ]; then
            cp -v "$PARENT_DIR/metadata.json" "$FINAL_OUTPUT_DIR/"
        else
            echo "⚠️  metadata.json not found in $PARENT_DIR"
        fi

        if [ -f "$CONFIG_PATH" ]; then
            cp -v "$CONFIG_PATH" "$FINAL_OUTPUT_DIR/config.json"
        else
            echo "⚠️  config.json not found at $CONFIG_PATH"
        fi

        echo "✅ Finished simulations and export for: $OUTPUT_TAG"
        echo "----------------------------"

    done
done

echo "🎉 All meshing, simulations, postprocessing, and archiving completed for all parameter sets."



















