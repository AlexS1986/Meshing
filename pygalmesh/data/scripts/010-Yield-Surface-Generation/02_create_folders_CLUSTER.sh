#!/bin/bash

# Exit on error
set -e

# Define source and destination directories
SRC_DIR="$HOME/meshing/Meshing/pygalmesh/"
DEST_DIR="$HPC_SCRATCH/pygalmesh/"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Generate/update the per-direction yield-surface jobs before syncing.
# Override with: YIELD_SURFACE_POINTS=20 ./02_create_folders_CLUSTER.sh
if [ -f "$SCRIPT_DIR/setup_yield_surface_jobs.sh" ]; then
  "$SCRIPT_DIR/setup_yield_surface_jobs.sh" "${YIELD_SURFACE_POINTS:-6}"
fi

# Create destination directory if it doesn't exist
mkdir -p "$DEST_DIR"

# Sync files:
# -a : archive (preserve structure, permissions, etc.)
# -v : verbose (show what's happening)
# --update : skip files that are newer in DEST_DIR
rsync -av --update "$SRC_DIR" "$DEST_DIR"

echo "Folder structure and updated files copied from $SRC_DIR to $DEST_DIR"
echo "Project folder: data/scripts/010-Yield-Surface-Generation"














