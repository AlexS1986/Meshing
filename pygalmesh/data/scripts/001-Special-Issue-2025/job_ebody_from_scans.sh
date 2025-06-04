#!/bin/bash
#SBATCH -J ebody
#SBATCH -A p0023647
#SBATCH -t 1440                   # max time in minutes
#SBATCH --mem-per-cpu=6000
#SBATCH -n 32
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/001-Special-Issue-2025/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/001-Special-Issue-2025/%x.out.%j
#SBATCH --mail-type=END
#SBATCH -C i01

set -e

# -------------------------------
# Setup
# -------------------------------

working_directory="$HPC_SCRATCH/pygalmesh/data/scripts/001-Special-Issue-2025"
CONTAINER_PATH="$HOME/meshing/Meshing/pygalmesh/pygalmesh.sif"
BIND_PATHS="$HOME/meshing/Meshing/pygalmesh/data:/home,$HPC_SCRATCH/pygalmesh/data:/data"
CONFIG_PATH="/data/scripts/001-Special-Issue-2025/config.json"
BASE_SUBVOLUME_FOLDER="$HPC_SCRATCH/pygalmesh/data/scripts/001-Special-Issue-2025/JM-25-24_segmented/JM-25-24_segmented_3D"
VOLUME_FILENAME="volume.npy"

SIM_CONTAINER="$HOME/dolfinx_alex/alex-dolfinx.sif"
SIM_BIND="$HOME/dolfinx_alex/shared:/home,$working_directory:/work"

SOURCE_DIR="$working_directory/00_template"
TARGET_DIR="$BASE_SUBVOLUME_FOLDER"
MESH_INPUT_DIR="$BASE_SUBVOLUME_FOLDER"
SIM_SCRIPT="linearelastic.py"

# Scripts to run in order
SCRIPTS=(
    "00_dicom_2_npy.py"
    "01_segment_slice_wise.py"
    "02_build3D_segmented_array.py"
    "02a_rotate_pic_to_align_with_axis.py"
    "02b_build_subvolume_arrays.py"
)

# -------------------------------
# Run preprocessing scripts
# -------------------------------

for SCRIPT in "${SCRIPTS[@]}"; do
    echo "🚀 Running preprocessing: $SCRIPT"
    srun -n 1 apptainer exec --bind $BIND_PATHS $CONTAINER_PATH \
        python3 "$working_directory/$SCRIPT" --config "$CONFIG_PATH"
    echo "✅ Finished: $SCRIPT"
    echo "----------------------------"
done

# -------------------------------
# Meshing and Transformation
# -------------------------------

MESH_SCRIPT="$working_directory/03_mesh_3D_array_pygalmesh.py"
SCALE_SCRIPT="$working_directory/04_scale_and_translate_mesh_mod.py"

echo "🌐 Starting mesh generation"

find "$BASE_SUBVOLUME_FOLDER" -type f -name "$VOLUME_FILENAME" | while read -r NPY_FILE; do
    SUBFOLDER=$(dirname "$NPY_FILE")
    FOLDER_NAME=$(basename "$SUBFOLDER")
    MESH_OUTPUT="$SUBFOLDER/mesh.xdmf"

    if [[ "$FOLDER_NAME" =~ subvolume_x([0-9]+)_y([0-9]+) ]]; then
        CENTER_X="${BASH_REMATCH[1]}"
        CENTER_Y="${BASH_REMATCH[2]}"
    else
        echo "❌ Could not extract center_x and center_y from: $FOLDER_NAME"
        exit 1
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

# -------------------------------
# Mesh Conversion to DolfinX
# -------------------------------

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
# Simulation & Postprocessing
# -------------------------------

if [ ! -d "$SOURCE_DIR" ] || [ ! -d "$TARGET_DIR" ]; then
    echo "❌ SOURCE or TARGET directory missing"
    exit 1
fi

for subfolder in "$TARGET_DIR"/*/; do
    [ -d "$subfolder" ] || continue
    echo "⚙️  Starting simulation pipeline for: $subfolder"
    cp -v "$SOURCE_DIR"/* "$subfolder"

    echo "🔬 Running $SIM_SCRIPT with 32 CPUs in: $subfolder"
    srun -n 32 --chdir="$subfolder" apptainer exec --bind $SIM_BIND $SIM_CONTAINER \
       python3 "$subfolder/$SIM_SCRIPT"

    echo "🛠️  Running update_trafo.py"
    srun -n 1 --chdir="$subfolder" apptainer exec --bind $BIND_PATHS $CONTAINER_PATH \
        python3 update_trafo.py

    echo "🔧 Running make"
    srun -n 1 --chdir="$subfolder" apptainer exec --bind $BIND_PATHS $CONTAINER_PATH \
        make

    echo "🚀 Running compiled binary: trafo.x"
    srun -n 1 --chdir="$subfolder" apptainer exec --bind $BIND_PATHS $CONTAINER_PATH \
        ./trafo.x

    echo "📤 Exporting to ParaView with DISPLAY"
    srun -n 1 --chdir="$subfolder" apptainer exec --bind $BIND_PATHS $CONTAINER_PATH \
        bash -c "Xvfb :99 -screen 0 1024x768x24 & sleep 2 && export DISPLAY=:99 && python3 print_e_body_2_paraview.py"

    echo "📈 Computing scalar e33 using find_e33.py"
    srun -n 1 --chdir="$subfolder" apptainer exec --bind $BIND_PATHS $CONTAINER_PATH \
        python3 find_e33.py

    echo "💾 Writing e33 to mesh using write_e33_to_mesh.py"
    srun -n 1 --chdir="$subfolder" apptainer exec --bind $SIM_BIND $SIM_CONTAINER \
        python3 write_e33_to_mesh.py

    echo "✅ Finished simulation and postprocessing for: $subfolder"
    echo ""
done

echo "🎉 All meshing, simulation, and postprocessing steps completed successfully."







