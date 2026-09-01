#!/bin/bash
#
# Reicht Netzerzeugung und Bruchsimulation als abhaengige Jobkette ein.
# Scheitert die Netzerzeugung, verwirft SLURM die Simulation
# (--kill-on-invalid-dep), statt sie ins Leere laufen zu lassen.
#
#   "$HPC_SCRATCH/pygalmesh/data/scripts/016-Fracture-From-leS/submit_fracture_pipeline_CLUSTER.sh"
#   submit_fracture_pipeline_CLUSTER.sh config-fracture-JM-25-88-medium.json
#
# Optionen:
#   SKIP_MESH=1 ...   Netz existiert schon, nur die Simulation einreihen
#   ONLY_MESH=1 ...   nur die Netzerzeugung
#   DRY_RUN=1  ...     nur anzeigen, was eingereicht wuerde

set -euo pipefail

SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/016-Fracture-From-leS"
source "$SCRIPT_DIR/config.sh"

CONFIG_ARG="${1:-config-fracture-${SPECIMEN_NAME}-${DEFAULT_TIER}.json}"
CONFIG_HOST_PATH="$SCRIPT_DIR/$CONFIG_ARG"
if [[ ! -f "$CONFIG_HOST_PATH" ]]; then
  echo "Config nicht gefunden: $CONFIG_HOST_PATH" >&2
  echo "Vorher ./create_fracture_config.sh und 02_create_folders_CLUSTER.sh laufen lassen." >&2
  exit 2
fi

submit() {
  if [[ -n "${DRY_RUN:-}" ]]; then
    echo "[dry-run] sbatch $*"
    echo "000000"
    return
  fi
  sbatch --parsable "$@"
}

mesh_job_id=""
if [[ -z "${SKIP_MESH:-}" ]]; then
  mesh_job_id="$(submit \
    -t "$MESH_JOB_TIME" -p "$MESH_JOB_PARTITION" \
    "$SCRIPT_DIR/job_generate_mesh_CLUSTER.sh" "$CONFIG_ARG")"
  echo "Netzerzeugung eingereicht: $mesh_job_id  ($CONFIG_ARG)"
fi

if [[ -n "${ONLY_MESH:-}" ]]; then
  echo "ONLY_MESH gesetzt - Simulation nicht eingereicht."
  exit 0
fi

dep_args=()
if [[ -n "$mesh_job_id" ]]; then
  dep_args=(--dependency="afterok:$mesh_job_id" --kill-on-invalid-dep=yes)
fi

sim_job_id="$(submit "${dep_args[@]}" \
  -t "$SIM_JOB_TIME" -n "$SIM_JOB_NTASKS" \
  --mem-per-cpu="$SIM_JOB_MEM_PER_CPU" -C "$SIM_JOB_CONSTRAINT" \
  "$SCRIPT_DIR/job_run_simulation_CLUSTER.sh" "$CONFIG_ARG")"
echo "Bruchsimulation eingereicht: $sim_job_id${mesh_job_id:+  (nach $mesh_job_id)}"
