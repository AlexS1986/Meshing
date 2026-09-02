#!/bin/bash

#SBATCH -J prep-ys-mesh
#SBATCH -A l0003507
# Account: batch_submit_CLUSTER.sh ueberschreibt ihn mit JOB_ACCOUNT aus config.sh
# (CLI schlaegt Header). p0023647 ist seit 12/2025 ohne Kontingent.
#SBATCH -t 120
#SBATCH -p deflt
# Es arbeitet nur ein Task (run_container 1 = srun -n 1); die Zuteilung
# dient dem Speicher. 8 x 15000 MB = 120 GB auf einem i01-Knoten (365 GB).
# Gemessen (r2, 02.09.2026): MaxRSS 24-34 GB, Laufzeit r4 13-18 min.
# Kleiner Fussabdruck + kurzes Limit => Backfill-Kandidat auf deflt; die
# mem-Partition (m01, 1,5 TB) wartete tagelang (Reason=Priority).
#SBATCH --nodes=1
#SBATCH -n 8
#SBATCH --mem-per-cpu=15000
#SBATCH -C i01
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS/%x.out.%j
#SBATCH --mail-type=END

set -euo pipefail

SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS"
bash "$SCRIPT_DIR/run_prepare_mesh_CLUSTER.sh" \
  "${1:-${PREPARE_MESH_CONFIG:-config-A01-les.json}}"
