#!/usr/bin/env bash
#
# Reicht die komplette Kette als SLURM-Jobs ein: erst die Netzvorbereitung,
# dann alle Fließflächen-Punkte mit Abhängigkeit davon. Nach dem Aufruf ist
# nichts mehr interaktiv zu tun — die Punkt-Jobs starten automatisch, sobald
# die Netzvorbereitung *erfolgreich* beendet ist (afterok).
#
# Aufruf (Login-Node, Ordner egal):
#
#     "$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS/submit_les_pipeline_CLUSTER.sh"
#
# Argumente / Umgebungsvariablen:
#
#     $1 / PREPARE_MESH_CONFIG    Config (Default: config-A01-les.json = .leS-Pipeline)
#                                 DICOM-Pfad: config-Bin4-reduce-2.json
#     $2 / YIELD_SURFACE_POINTS   Anzahl Richtungen (Default: 192)
#     YIELD_SURFACE_JOBS_DIR      Job-Ordner explizit setzen
#                                 (Default: yield_surface_jobs/nNNN)
#     DEPEND_ON_JOB=<jobid>       Netzvorbereitung laeuft bereits: nur die
#                                 Punkt-Jobs einreihen, abhaengig von dieser ID
#     SKIP_PREPARE=1              Netzvorbereitung überspringen (Netz existiert
#                                 bereits) und die Punkt-Jobs sofort einreihen
#     DRY_RUN=1                   nur anzeigen, was eingereicht würde
#
set -euo pipefail

if [[ -z "${HPC_SCRATCH:-}" ]]; then
  echo "HPC_SCRATCH ist nicht gesetzt." >&2
  exit 2
fi

SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS"
CONFIG="${1:-${PREPARE_MESH_CONFIG:-config-A01-les.json}}"
POINTS="${2:-${YIELD_SURFACE_POINTS:-192}}"
YS_DIR="${YIELD_SURFACE_JOBS_DIR:-$SCRIPT_DIR/yield_surface_jobs/n$(printf '%03d' "$POINTS")}"

if [[ "$CONFIG" != /* ]]; then
  CONFIG_HOST_PATH="$SCRIPT_DIR/$CONFIG"
else
  CONFIG_HOST_PATH="${CONFIG/#\/data/$HPC_SCRATCH/pygalmesh/data}"
fi
if [[ ! -f "$CONFIG_HOST_PATH" ]]; then
  echo "Config nicht gefunden: $CONFIG_HOST_PATH" >&2
  echo "Wurde 02_create_folders_CLUSTER.sh nach dem Erzeugen der Config ausgeführt?" >&2
  exit 2
fi

mapfile -t POINT_JOBS < <(find "$YS_DIR" -mindepth 2 -maxdepth 2 -name 'job_*_CLUSTER.sh' | sort)
if [[ "${#POINT_JOBS[@]}" -eq 0 ]]; then
  echo "Keine Punkt-Jobs in: $YS_DIR" >&2
  echo "Zuerst erzeugen und synchronisieren:" >&2
  echo "  cd \"\$HOME/meshing/Meshing/pygalmesh\"" >&2
  echo "  YIELD_SURFACE_POINTS=$POINTS data/scripts/015-Yield-Surface-Batch-leS/02_create_folders_CLUSTER.sh" >&2
  exit 2
fi

echo "Projekt   : $SCRIPT_DIR"
echo "Config    : $CONFIG_HOST_PATH"
echo "Punkt-Jobs: ${#POINT_JOBS[@]} in $YS_DIR"

# sbatch schreibt auf manchen Clustern zusaetzliche Plugin-Meldungen auf stdout
# ("sbatch: slurm_job_submit: [I] LUA ..."). Deshalb wird aus der Ausgabe die
# letzte rein numerische Zeile als Job-ID herausgefiltert.
extract_job_id() {
  printf '%s\n' "$1" | tr -d '\r' | sed 's/;.*//' | grep -E '^[0-9]+$' | tail -n 1
}

DEPENDENCY_ARGS=()
PREP_JOB_ID=""
if [[ -n "${DEPEND_ON_JOB:-}" ]]; then
  PREP_JOB_ID="$DEPEND_ON_JOB"
  if ! [[ "$PREP_JOB_ID" =~ ^[0-9]+$ ]]; then
    echo "DEPEND_ON_JOB ist keine Job-ID: $PREP_JOB_ID" >&2
    exit 2
  fi
  echo "Nutze bereits laufende Netzvorbereitung: Job $PREP_JOB_ID"
  DEPENDENCY_ARGS=(--dependency="afterok:$PREP_JOB_ID" --kill-on-invalid-dep=yes)
elif [[ "${SKIP_PREPARE:-0}" == "1" ]]; then
  echo "Netzvorbereitung wird übersprungen (SKIP_PREPARE=1), keine Abhängigkeit."
else
  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    echo "[dry-run] sbatch --parsable $SCRIPT_DIR/job_prepare_mesh_CLUSTER.sh $CONFIG"
    PREP_JOB_ID="000000"
  else
    prep_output="$(sbatch --parsable "$SCRIPT_DIR/job_prepare_mesh_CLUSTER.sh" "$CONFIG")"
    PREP_JOB_ID="$(extract_job_id "$prep_output")"
    if [[ -z "$PREP_JOB_ID" ]]; then
      echo "Konnte die Job-ID der Netzvorbereitung nicht aus der sbatch-Ausgabe lesen:" >&2
      printf '%s\n' "$prep_output" >&2
      exit 2
    fi
  fi
  echo "Netzvorbereitung eingereicht: Job $PREP_JOB_ID"
  DEPENDENCY_ARGS=(--dependency="afterok:$PREP_JOB_ID" --kill-on-invalid-dep=yes)
fi

submitted=0
for job in "${POINT_JOBS[@]}"; do
  job_dir="$(dirname "$job")"
  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    echo "[dry-run] sbatch ${DEPENDENCY_ARGS[*]-} --error=$job_dir/%x.err.%j --output=$job_dir/%x.out.%j $job"
  else
    sbatch "${DEPENDENCY_ARGS[@]}" \
      --error="$job_dir/%x.err.%j" \
      --output="$job_dir/%x.out.%j" \
      "$job" > /dev/null
  fi
  submitted=$((submitted + 1))
done

echo "Punkt-Jobs eingereicht: $submitted"
if [[ -n "$PREP_JOB_ID" ]]; then
  echo "Sie starten automatisch nach erfolgreicher Netzvorbereitung (afterok:$PREP_JOB_ID)."
  echo "Scheitert die Vorbereitung, werden sie von SLURM verworfen (--kill-on-invalid-dep)."
fi
echo
echo "Status  : squeue -u \"\$USER\""
echo "Prep-Log: $SCRIPT_DIR/prep-ys-mesh.out.<jobid>   (dort muss 'Pipeline source: les' stehen)"
