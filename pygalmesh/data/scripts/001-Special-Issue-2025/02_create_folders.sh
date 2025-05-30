#!/bin/bash

# Exit on error
set -e

# Define source and destination directories
SRC_DIR="$HOME/meshing/Meshing/pygalmesh"
DEST_DIR="$HPC_SCRATCH/pygalmesh"

# Create destination directory if it doesn't exist
mkdir -p "$DEST_DIR"

# Copy directory and contents
cp -r "$SRC_DIR"/* "$DEST_DIR"

echo "Contents copied from $SRC_DIR to $DEST_DIR"













