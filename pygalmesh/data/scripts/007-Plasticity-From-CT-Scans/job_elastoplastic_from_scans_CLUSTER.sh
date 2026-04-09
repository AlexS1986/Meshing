#!/bin/bash
#SBATCH -J elastoplastic
#SBATCH -A p0023647
#SBATCH -t 10080
#SBATCH --mem-per-cpu=9000
#SBATCH -n 32
#SBATCH -N 1
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/007-Plasticity-From-CT-Scans/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/007-Plasticity-From-CT-Scans/%x.out.%j
#SBATCH --mail-type=END
#SBATCH -C i01

set -e

# -------------------------------
# Setup
# -------------------------------

specimen_name="JM-25-19"
output_directory_variable="pressure_experiment"
working_directory="$HPC_SCRATCH/pygalmesh/data/scripts/007-Plasticity-From-CT-Scans"

CONTAINER_PATH="$HOME/meshing/Meshing/pygalmesh/pygalmesh.sif"
BIND_PATHS="$HOME/meshing/Meshing/pygalmesh/data:/home,$HPC_SCRATCH/pygalmesh/data:/data"
CONFIG_PATH="/data/scripts/007-Plasticity-From-CT-Scans/config-${specimen_name}.json"

BASE_SUBVOLUME_FOLDER="$HPC_SCRATCH/pygalmesh/data/scripts/007-Plasticity-From-CT-Scans/${specimen_name}_segmented/${specimen_name}_segmented_3D"
VOLUME_FILENAME="volume.npy"

SIM_CONTAINER="$HOME/dolfinx_alex/alex-dolfinx.sif"
SIM_BIND="$HOME/dolfinx_alex/shared:/home"

SOURCE_DIR="$working_directory/00_template"
TARGET_DIR="$BASE_SUBVOLUME_FOLDER"
MESH_INPUT_DIR="$BASE_SUBVOLUME_FOLDER"
SIM_SCRIPT="elastoplastic.py"

EXTEND_SCRIPT="$working_directory/02c_extend_image_pressure_experiment.py"
EXTEND_THICKNESS=10  # Adjust if needed

# -------------------------------
# Run initial preprocessing scripts (up to 02a)
# -------------------------------

PRE_SCRIPTS=(
    "00_dicom_2_npy.py"
    "01_segment_slice_wise.py"
    "02_build3D_segmented_array.py"
    "02a_rotate_pic_to_align_with_axis.py"
)

for SCRIPT in "${PRE_SCRIPTS[@]}"; do
    echo "🚀 Running preprocessing: $SCRIPT"
    srun -n 1 apptainer exec --bind $BIND_PATHS $CONTAINER_PATH \
        python3 "$working_directory/$SCRIPT" --config "$CONFIG_PATH"
    echo "✅ Finished: $SCRIPT"
    echo "----------------------------"
done

# -------------------------------
# Begin material-direction loop
# -------------------------------

MATERIALS=("default")
DIRECTIONS=("y")

for MAT in "${MATERIALS[@]}"; do
    for DIR in "${DIRECTIONS[@]}"; do

        echo "🚀 Running 02b for Material=$MAT Direction=$DIR"
        srun -n 1 apptainer exec --bind $BIND_PATHS $CONTAINER_PATH \
            python3 "$working_directory/02b_build_subvolume_arrays.py" --config "$CONFIG_PATH"

        echo "🧱 Starting image extension using $EXTEND_SCRIPT"
        echo "📐 Direction: $DIR | Thickness: $EXTEND_THICKNESS"

        find "$BASE_SUBVOLUME_FOLDER" -type f -name "$VOLUME_FILENAME" | while read -r NPY_FILE; do
            echo "➕ Extending $NPY_FILE"
            srun -n 1 apptainer exec --bind $BIND_PATHS $CONTAINER_PATH \
                python3 "$EXTEND_SCRIPT" "$NPY_FILE" "$DIR" --thickness "$EXTEND_THICKNESS"
            if [ $? -ne 0 ]; then
                echo "❌ Error while extending $NPY_FILE. Exiting..."
                exit 1
            fi
            echo "✅ Extended: $NPY_FILE"
            echo "----------------------------"
        done

        echo "🌐 Starting mesh generation and transformation"

        MESH_SCRIPT="$working_directory/03_mesh_3D_array_pygalmesh.py"
        SCALE_SCRIPT="$working_directory/04_scale_and_translate_mesh_mod.py"

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

        echo "🔁 Converting mesh files to DolfinX format"
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

        echo "🔬 Starting simulation: Material=$MAT Direction=$DIR"
        for subfolder in "$TARGET_DIR"/*/; do
            [ -d "$subfolder" ] || continue
            echo "⚙️  Processing: $subfolder"

            if [ -d "$working_directory/scratch" ]; then
                echo "🧹 Removing existing scratch directory: $working_directory/scratch"
                rm -rf "$working_directory/scratch"
            fi

            cp -v "$SOURCE_DIR"/* "$subfolder"
            rm -rf "$working_directory/scratch"
            sleep 2s

            echo "🔬 Running $SIM_SCRIPT with params $MAT $DIR"
            srun -n 32 --chdir="$subfolder" apptainer exec --bind $SIM_BIND $SIM_CONTAINER \
                python3 "$subfolder/$SIM_SCRIPT" "$MAT" "$DIR"
        done

        FINAL_OUTPUT_DIR="$working_directory/00_results/${specimen_name}/${output_directory_variable}/${specimen_name}-${MAT}-${DIR}"
        echo "📦 Copying results to: $FINAL_OUTPUT_DIR"
        mkdir -p "$FINAL_OUTPUT_DIR"

        cp -rv "$BASE_SUBVOLUME_FOLDER" "$FINAL_OUTPUT_DIR/"

        PARENT_DIR="$(dirname "$BASE_SUBVOLUME_FOLDER")"
        if [ -f "$PARENT_DIR/metadata.json" ]; then
            cp -v "$PARENT_DIR/metadata.json" "$FINAL_OUTPUT_DIR/"
        else
            echo "⚠️  metadata.json not found in $PARENT_DIR"
        fi

        CONFIG_ACTUAL_PATH="$HPC_SCRATCH/pygalmesh$CONFIG_PATH"
        if [ -f "$CONFIG_ACTUAL_PATH" ]; then
            cp -v "$CONFIG_ACTUAL_PATH" "$FINAL_OUTPUT_DIR/"
        else
            echo "⚠️  config.json not found at $CONFIG_ACTUAL_PATH"
        fi

        echo "✅ Finished simulation Material=$MAT Direction=$DIR"
        echo "----------------------------"

    done
done

echo "🎉 All preprocessing, extension, meshing, simulation, and archiving completed successfully."


















