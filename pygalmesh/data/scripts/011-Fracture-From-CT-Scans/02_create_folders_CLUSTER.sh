#!/bin/bash
set -euo pipefail

SRC_DIR="$HOME/meshing/Meshing/pygalmesh/"
DEST_DIR="$HPC_SCRATCH/pygalmesh/"
mkdir -p "$DEST_DIR"
rsync -av --update "$SRC_DIR" "$DEST_DIR"

echo "Folder structure and updated files copied from $SRC_DIR to $DEST_DIR"
echo "Project folder: data/scripts/011-Fracture-From-CT-Scans"
