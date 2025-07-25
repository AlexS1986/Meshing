#!/bin/bash

# Exit on error
set -e

# Define source and destination directories
SRC_DIR="$HOME/meshing/Meshing/pygalmesh/"
DEST_DIR="$HPC_SCRATCH/pygalmesh/"

# Create destination directory if it doesn't exist
mkdir -p "$DEST_DIR"

# Sync files:
# -a : archive (preserve structure, permissions, etc.)
# -v : verbose (show what's happening)
# --update : skip files that are newer in DEST_DIR
rsync -av --update "$SRC_DIR" "$DEST_DIR"

echo "Folder structure and updated files copied from $SRC_DIR to $DEST_DIR"















