#!/bin/bash

# Source folder (where results are stored)
SOURCE_FOLDER="/Users/alexanderschluter/Work/Hypo/Hypo/Simulation/Meshing/pygalmesh/data/resources/2D_structure_Hannover/310125_var_bcpos_rho_10_120_004/"

# Destination folder (where you want to copy them)
DEST_FOLDER="/Users/alexanderschluter/Work/Hypo/Hypo/Simulation/dolfinx_alex/shared/scripts/052-Special-Issue-IJF-Hannover/resources/310125_var_bcpos_rho_10_120_004"

# Only create the destination folder if it does NOT exist
if [ ! -d "$DEST_FOLDER" ]; then
    echo "Destination folder does not exist. Creating it..."
    mkdir -p "$DEST_FOLDER"
else
    echo "Destination folder already exists. Skipping creation."
fi

# Sync contents — only update changed or new files
rsync -av --update "$SOURCE_FOLDER" "$DEST_FOLDER"

echo "Synchronized contents from $SOURCE_FOLDER to $DEST_FOLDER"
