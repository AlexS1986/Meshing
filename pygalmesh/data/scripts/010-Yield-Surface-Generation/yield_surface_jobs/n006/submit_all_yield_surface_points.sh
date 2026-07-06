#!/usr/bin/env bash
#SBATCH -J ys-submit-n006
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH --mem-per-cpu=9000
#SBATCH -n 1
#SBATCH -N 1
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/010-Yield-Surface-Generation/yield_surface_jobs/n006/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/010-Yield-Surface-Generation/yield_surface_jobs/n006/%x.out.%j
#SBATCH --mail-type=END
#SBATCH -C i01

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

sbatch "$SCRIPT_DIR/ys_000_e1_p0p2500_e2_p0p0000_e3_p0p0000/job_ys_000_e1_p0p2500_e2_p0p0000_e3_p0p0000_CLUSTER.sh"
sbatch "$SCRIPT_DIR/ys_001_e1_m0p2500_e2_p0p0000_e3_p0p0000/job_ys_001_e1_m0p2500_e2_p0p0000_e3_p0p0000_CLUSTER.sh"
sbatch "$SCRIPT_DIR/ys_002_e1_p0p0000_e2_p0p2500_e3_p0p0000/job_ys_002_e1_p0p0000_e2_p0p2500_e3_p0p0000_CLUSTER.sh"
sbatch "$SCRIPT_DIR/ys_003_e1_p0p0000_e2_m0p2500_e3_p0p0000/job_ys_003_e1_p0p0000_e2_m0p2500_e3_p0p0000_CLUSTER.sh"
sbatch "$SCRIPT_DIR/ys_004_e1_p0p0000_e2_p0p0000_e3_p0p2500/job_ys_004_e1_p0p0000_e2_p0p0000_e3_p0p2500_CLUSTER.sh"
sbatch "$SCRIPT_DIR/ys_005_e1_p0p0000_e2_p0p0000_e3_m0p2500/job_ys_005_e1_p0p0000_e2_p0p0000_e3_m0p2500_CLUSTER.sh"
