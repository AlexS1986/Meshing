#!/usr/bin/env bash
#
# Schritt 4: die komplette Studie einreichen.
#
#   1. je Datensatz EINE Netzvorbereitung (job_prepare_mesh_CLUSTER.sh).
#      Das Netz haengt nicht von sig_y ab, beide sig_y-Varianten benutzen es.
#   2. je Kombination alle Punkt-Jobs mit --dependency=afterok:<prep-id>.
#      Scheitert die Vorbereitung, verwirft SLURM die Punkt-Jobs
#      (--kill-on-invalid-dep=yes).
#
# Aufruf auf dem Login-Node (Ordner egal):
#
#   "$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS/batch_submit_CLUSTER.sh"
#
# Umgebungsvariablen:
#
#   DRY_RUN=1              nur anzeigen, was eingereicht wuerde
#   SKIP_PREPARE=1         keine Netzvorbereitung, Punkt-Jobs ohne Abhaengigkeit
#   AUTO_SKIP_PREPARE=0    Netzvorbereitung auch dann einreichen, wenn das
#                          fertige dlfx_mesh.xdmf schon existiert (Default 1)
#   ONLY_DATASETS="JM-25-77 JM-25-83"
#   ONLY_SIG_Y="100"
#   PREP_JOB_TIME=240      Zeitlimit der Netzvorbereitung (Minuten, Default 120)
#   FORCE=1                Queue-Limit-Pruefung uebergehen
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/batch_lib.sh"
batch_require_scratch

EXPECTED_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/$PROJECT_NAME"
if [[ "$SCRIPT_DIR" != "$EXPECTED_DIR" ]]; then
  echo "[WARNUNG] Dieses Skript laeuft aus $SCRIPT_DIR," >&2
  echo "          gerechnet wird aber in $EXPECTED_DIR." >&2
  echo "          Erst batch_create_folders_CLUSTER.sh laufen lassen." >&2
fi

echo "=== Einreichen ==="
batch_print_plan
echo

# sbatch schreibt auf manchen Clustern Plugin-Meldungen auf stdout
# ("sbatch: slurm_job_submit: [I] LUA ..."). Job-ID = letzte rein numerische Zeile.
extract_job_id() {
  printf '%s\n' "$1" | tr -d '\r' | sed 's/;.*//' | grep -E '^[0-9]+$' | tail -n 1
}

config_value() {  # config_value <config-datei> <dotted.key>
  python3 - "$SCRIPT_DIR/$1" "$2" <<'PY'
import json, sys
with open(sys.argv[1]) as h:
    cfg = json.load(h)
value = cfg
for key in sys.argv[2].split('.'):
    value = value[key]
print(value)
PY
}

# --- planen ------------------------------------------------------------------
declare -a COMBO_DS COMBO_SIG COMBO_ID COMBO_CFG COMBO_JOBS
n_points_total=0
while read -r ds sig combo cfg jobs; do
  [[ -n "$ds" ]] || continue
  if [[ ! -f "$SCRIPT_DIR/$cfg" ]]; then
    echo "[FEHLER] Config fehlt auf dem Scratch: $cfg" >&2
    echo "         batch_create_folders_CLUSTER.sh ausfuehren." >&2
    exit 2
  fi
  mapfile -t found < <(find "$SCRIPT_DIR/$jobs" -mindepth 2 -maxdepth 2 -name 'job_*_CLUSTER.sh' 2>/dev/null | sort)
  if [[ "${#found[@]}" -eq 0 ]]; then
    echo "[FEHLER] Keine Punkt-Jobs in $jobs" >&2
    echo "         batch_create_folders_CLUSTER.sh ausfuehren." >&2
    exit 2
  fi
  COMBO_DS+=("$ds"); COMBO_SIG+=("$sig"); COMBO_ID+=("$combo")
  COMBO_CFG+=("$cfg"); COMBO_JOBS+=("$jobs")
  n_points_total=$((n_points_total + ${#found[@]}))
done < <(batch_combos)

mapfile -t DATASETS < <(batch_active_datasets)
n_prep=0
[[ "${SKIP_PREPARE:-0}" == "1" ]] || n_prep="${#DATASETS[@]}"

in_queue=0
if command -v squeue >/dev/null 2>&1; then
  in_queue="$(squeue -h -u "$USER" 2>/dev/null | wc -l | tr -d ' ')"
fi
planned=$((n_points_total + n_prep))
echo "In der Queue      : $in_queue"
echo "Neu einzureichen  : $planned  ($n_prep Netzvorbereitungen + $n_points_total Punkt-Jobs)"
echo "Limit             : ${BATCH_MAX_SUBMIT:-1000}"
if [[ $((in_queue + planned)) -gt "${BATCH_MAX_SUBMIT:-1000}" && "${FORCE:-0}" != "1" && "${DRY_RUN:-0}" != "1" ]]; then
  echo >&2
  echo "[ABBRUCH] $in_queue + $planned ueberschreitet BATCH_MAX_SUBMIT=${BATCH_MAX_SUBMIT:-1000}." >&2
  echo "          Teilweise einreichen, z.B.:" >&2
  echo "            ONLY_SIG_Y=100 $0" >&2
  echo "            ONLY_DATASETS=\"JM-25-77 JM-25-71\" $0" >&2
  echo "          oder FORCE=1 setzen, wenn das Limit inzwischen hoeher ist." >&2
  exit 3
fi
echo

# --- 1. Netzvorbereitung je Datensatz ----------------------------------------
declare -A PREP_ID
for ds in "${DATASETS[@]}"; do
  # Config des ersten sig_y dieses Datensatzes; das Netz ist fuer beide gleich.
  cfg=""
  for i in "${!COMBO_DS[@]}"; do
    if [[ "${COMBO_DS[$i]}" == "$ds" ]]; then cfg="${COMBO_CFG[$i]}"; break; fi
  done

  if [[ "${SKIP_PREPARE:-0}" == "1" ]]; then
    echo "[$ds] Netzvorbereitung uebersprungen (SKIP_PREPARE=1)."
    continue
  fi

  subvol_container="$(config_value "$cfg" 02b_build_subvolume_arrays.subvolume_output_folder)"
  subvol_host="$(batch_container_to_host "$subvol_container")"
  if [[ "${AUTO_SKIP_PREPARE:-1}" == "1" ]] \
     && compgen -G "$subvol_host/subvolume_x*_y*/dlfx_mesh.xdmf" > /dev/null; then
    echo "[$ds] Netz existiert bereits ($subvol_host) - Vorbereitung uebersprungen."
    continue
  fi

  prep_args=(--parsable --time="${PREP_JOB_TIME:-120}")
  [[ -n "${PREP_JOB_PARTITION:-}" ]] && prep_args+=(-p "$PREP_JOB_PARTITION")
  [[ -n "${JOB_ACCOUNT:-}" ]] && prep_args+=(-A "$JOB_ACCOUNT")
  prep_args+=(-J "prep-$ds")
  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    echo "[dry-run] sbatch ${prep_args[*]} $SCRIPT_DIR/job_prepare_mesh_CLUSTER.sh $cfg"
    PREP_ID["$ds"]="000000"
  else
    out="$(sbatch "${prep_args[@]}" "$SCRIPT_DIR/job_prepare_mesh_CLUSTER.sh" "$cfg")"
    id="$(extract_job_id "$out")"
    if [[ -z "$id" ]]; then
      echo "[FEHLER] Job-ID der Netzvorbereitung nicht lesbar:" >&2
      printf '%s\n' "$out" >&2
      exit 2
    fi
    PREP_ID["$ds"]="$id"
    echo "[$ds] Netzvorbereitung eingereicht: Job $id  (config $cfg)"
  fi
done
echo

# --- 2. Punkt-Jobs je Kombination --------------------------------------------
submitted=0
for i in "${!COMBO_ID[@]}"; do
  ds="${COMBO_DS[$i]}"; combo="${COMBO_ID[$i]}"; jobs="${COMBO_JOBS[$i]}"
  dep_args=()
  if [[ -n "${PREP_ID[$ds]:-}" ]]; then
    dep_args=(--dependency="afterok:${PREP_ID[$ds]}" --kill-on-invalid-dep=yes)
  fi
  mapfile -t point_jobs < <(find "$SCRIPT_DIR/$jobs" -mindepth 2 -maxdepth 2 -name 'job_*_CLUSTER.sh' | sort)
  echo "[$combo] ${#point_jobs[@]} Punkt-Jobs${PREP_ID[$ds]:+ (afterok:${PREP_ID[$ds]})}"
  for job in "${point_jobs[@]}"; do
    job_dir="$(dirname "$job")"
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
      echo "  [dry-run] sbatch ${dep_args[*]-} --error=$job_dir/%x.err.%j --output=$job_dir/%x.out.%j $job"
    else
      sbatch ${dep_args[@]+"${dep_args[@]}"} \
        --error="$job_dir/%x.err.%j" \
        --output="$job_dir/%x.out.%j" \
        "$job" > /dev/null
    fi
    submitted=$((submitted + 1))
  done
done

echo
echo "Punkt-Jobs eingereicht: $submitted"
echo "Status  : squeue -u \"\$USER\"    bzw.  $SCRIPT_DIR/batch_status_CLUSTER.sh"
echo "Prep-Log: $SCRIPT_DIR/prep-*.out.<jobid>   (dort muss 'Prepared mesh' stehen)"
