#!/bin/bash

#SBATCH -J mesh-les-frac
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH -p mem
# Es arbeitet nur EIN Task (run_container 1 = srun -n 1); die Zuteilung dient
# dem Speicher. 32 x 45000 MB = 1,44 TB - dieselbe Groesse, mit der die
# Netzvorbereitung in 015 erfolgreich lief.
#SBATCH --nodes=1
#SBATCH -n 32
#SBATCH --mem-per-cpu=45000
#SBATCH -C "m01&mem1536g"
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/016-Fracture-From-leS/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/016-Fracture-From-leS/%x.out.%j
#SBATCH --mail-type=END

# Stufe 1 der zweistufigen Bruchpipeline (Aufteilung wie in 012):
# .leS -> Voxelvolumen -> Netz -> DolfinX-Netz. KEINE Simulation.
#
# Usage: sbatch job_generate_mesh_CLUSTER.sh [config-file.json]
#        (ohne Argument: die Default-Stufe aus config.sh)

set -euo pipefail

SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/016-Fracture-From-leS"
source "$SCRIPT_DIR/config.sh"
bash "$SCRIPT_DIR/run_generate_mesh_CLUSTER.sh" \
  "${1:-${FRACTURE_MESH_CONFIG:-config-fracture-${SPECIMEN_NAME}-${DEFAULT_TIER}.json}}"
