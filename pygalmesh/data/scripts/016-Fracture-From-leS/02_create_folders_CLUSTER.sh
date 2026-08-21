#!/bin/bash
#
# Projekt nach $HPC_SCRATCH synchronisieren. Vorher werden die Configs der
# Aufloesungsfamilie neu erzeugt, damit Aenderungen an config.sh wirksam werden.
#
#   cd "$HOME/meshing/Meshing/pygalmesh"
#   data/scripts/016-Fracture-From-leS/02_create_folders_CLUSTER.sh
#
# Configs nicht neu erzeugen (z.B. wenn sie von Hand angepasst wurden):
#   SKIP_CONFIGS=1 data/scripts/016-Fracture-From-leS/02_create_folders_CLUSTER.sh

set -e

SRC_DIR="$HOME/meshing/Meshing/pygalmesh/"
DEST_DIR="$HPC_SCRATCH/pygalmesh/"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "${SKIP_CONFIGS:-}" ] && [ -f "$SCRIPT_DIR/create_fracture_config.sh" ]; then
  "$SCRIPT_DIR/create_fracture_config.sh"
fi

mkdir -p "$DEST_DIR"
rsync -av --update "$SRC_DIR" "$DEST_DIR"

echo "Synchronisiert: $SRC_DIR -> $DEST_DIR"
echo "Projektordner : data/scripts/016-Fracture-From-leS"
