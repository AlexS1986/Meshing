#!/usr/bin/env bash
#
# Schritt 3: Configs + Punkt-Jobs erzeugen und das Projekt nach $HPC_SCRATCH
# synchronisieren. Das Gegenstueck zu 02_create_folders_CLUSTER.sh aus 014,
# nur fuer alle Kombinationen auf einmal. Laeuft auf dem Login-Node.
#
#   cd "$HOME/meshing/Meshing/pygalmesh"
#   data/scripts/015-Yield-Surface-Batch-leS/batch_create_folders_CLUSTER.sh
#
#   # nur einzelne Kombinationen neu erzeugen:
#   ONLY_DATASETS="JM-25-83" data/scripts/.../batch_create_folders_CLUSTER.sh
#
#   # nur synchronisieren, nichts neu erzeugen:
#   SKIP_GENERATE=1 data/scripts/.../batch_create_folders_CLUSTER.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SRC_DIR="${BATCH_SRC_DIR:-$HOME/meshing/Meshing/pygalmesh/}"
DEST_DIR="${BATCH_DEST_DIR:-$HPC_SCRATCH/pygalmesh/}"

if [[ "${SKIP_GENERATE:-0}" != "1" ]]; then
  bash "$SCRIPT_DIR/batch_create_configs.sh"
  bash "$SCRIPT_DIR/batch_setup_jobs.sh"
fi

if [[ -z "${HPC_SCRATCH:-}" ]]; then
  echo "HPC_SCRATCH ist nicht gesetzt - es wurde nur erzeugt, nicht synchronisiert." >&2
  exit 0
fi

mkdir -p "$DEST_DIR"
# -a archive, -v verbose, --update: neuere Dateien im Ziel nicht ueberschreiben
rsync -av --update "$SRC_DIR" "$DEST_DIR"

echo
echo "Synchronisiert: $SRC_DIR  ->  $DEST_DIR"
echo "Projektordner : $DEST_DIR/data/scripts/$(basename "$SCRIPT_DIR")"
echo "Weiter mit    : \"\$HPC_SCRATCH/pygalmesh/data/scripts/$(basename "$SCRIPT_DIR")/batch_submit_CLUSTER.sh\""
