#!/bin/bash

# Source folder (where results are stored)
SOURCE_FOLDER="/Users/alexanderschluter/Work/Hypo/Hypo/Simulation/Meshing/pygalmesh/data/resources/2D_structure_Hannover/260504_dcb_beta_phi_a_rho_var_min_max"

# Destination folder (where you want to copy them)
DEST_FOLDER="/Users/alexanderschluter/Work/Hypo/Hypo/Simulation/dolfinx_alex/shared/scripts/063-Special-Issue-IJF-Hannover/resources/"

# Only create the destination folder if it does NOT exist
if [ ! -d "$DEST_FOLDER" ]; then
    echo "Destination folder does not exist. Creating it..."
    mkdir -p "$DEST_FOLDER"
else
    echo "Destination folder already exists. Skipping creation."
fi

# Sync contents and overwrite existing files
rsync -av "$SOURCE_FOLDER" "$DEST_FOLDER"

echo "Synchronized contents from $SOURCE_FOLDER to $DEST_FOLDER"
