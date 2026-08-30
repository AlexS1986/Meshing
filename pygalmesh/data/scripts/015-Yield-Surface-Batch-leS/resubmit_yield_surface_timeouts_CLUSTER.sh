#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Studie 015 (Batch): reicht Fliessflaechen-Punktjobs, die am SLURM-Zeitlimit
# abgebrochen sind, als Restart-Kette neu ein. Jeder Kettenjob laeuft mit den
# unveraenderten SBATCH-Einstellungen des Punkt-Jobskripts und setzt die
# Rechnung ueber den Restart-Mechanismus in elastoplastic.py/yield_restart.py
# fort (Doku: RESTART_NACH_TIMEOUT.md in 014, uebernommen fuer 015).
#
# Kette: Job 1 sofort; Jobs 2..MAX_CHAIN jeweils mit
#   --dependency=afternotok:<Vorgaenger> --kill-on-invalid-dep=yes
# Bricht ein Glied am Zeitlimit ab, setzt das naechste fort; laeuft ein Glied
# erfolgreich durch, raeumt SLURM die restlichen Glieder automatisch ab.
# Reicht die Kette nicht, dieses Skript einfach erneut aufrufen - fertige und
# laufende Punkte werden erkannt und uebersprungen.
#
# Aufruf (auf dem Cluster, nach Sync des 015-Ordners):
#   resubmit_yield_surface_timeouts_CLUSTER.sh [JOBS_ROOT]
#
#   JOBS_ROOT   Default: .../015-Yield-Surface-Batch-leS/yield_surface_jobs
#               (durchsucht alle Kombinationen <combo>/nNNN/ys_*). Auch ein
#               einzelner Kombinations- oder nNNN-Ordner ist erlaubt, z.B.
#               yield_surface_jobs/JM-25-77_sigy075/n096
#
# Umgebungsvariablen:
#   MAX_CHAIN=5        Gesamtzahl Jobs je Kette (1 Start + 4 Fortsetzungen)
#   DRY_RUN=1          nur anzeigen, nichts einreichen
#   INCLUDE_FAILED=1   auch Jobs neu einreichen, deren letzter Abbruch KEIN
#                      Timeout war (Default: nur Timeout-Jobs)
# ---------------------------------------------------------------------------

working_directory="$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS"
JOBS_ROOT="${1:-$working_directory/yield_surface_jobs}"
MAX_CHAIN="${MAX_CHAIN:-5}"
DRY_RUN="${DRY_RUN:-0}"
INCLUDE_FAILED="${INCLUDE_FAILED:-0}"

if [[ ! -d "$JOBS_ROOT" ]]; then
  echo "Jobs-Ordner nicht gefunden: $JOBS_ROOT" >&2
  exit 2
fi
if ! command -v sbatch > /dev/null; then
  echo "sbatch nicht gefunden - dieses Skript laeuft auf dem Cluster." >&2
  exit 2
fi

# Sample-Ordner einsammeln: JOBS_ROOT kann yield_surface_jobs (Tiefe 2),
# ein Kombinationsordner (Tiefe 1) oder ein nNNN-Ordner (Tiefe 0) sein.
sample_dirs=()
for d in "$JOBS_ROOT"/ys_*/ "$JOBS_ROOT"/*/ys_*/ "$JOBS_ROOT"/*/*/ys_*/; do
  [[ -d "$d" ]] && sample_dirs+=("${d%/}")
done
if [[ ${#sample_dirs[@]} -eq 0 ]]; then
  echo "Keine ys_*-Sample-Ordner unter $JOBS_ROOT gefunden." >&2
  exit 2
fi

# Laufende/wartende Jobs des Nutzers einmalig abfragen
queued_names="$(squeue -h -u "$USER" -o '%j' 2>/dev/null || true)"

n_done=0 n_running=0 n_timeout=0 n_failed=0 n_neverrun=0 n_submitted=0

for sample_dir in "${sample_dirs[@]}"; do
  sample_id="$(basename "$sample_dir")"
  job_script="$sample_dir/job_${sample_id}_CLUSTER.sh"
  config_json="$sample_dir/config.json"
  if [[ ! -f "$job_script" || ! -f "$config_json" ]]; then
    echo "[WARNUNG] $sample_id: job-Skript oder config.json fehlt - uebersprungen."
    continue
  fi

  # dataset/binning/Materialien/Richtungen aus der Config (binning_label
  # enthaelt in 015 das sig_y-Tag und trennt die beiden Varianten)
  mapfile -t cfg < <(python3 - "$config_json" <<'PYCFG'
import json, sys
with open(sys.argv[1]) as handle:
    config = json.load(handle)
ys = config.get("yield_surface", {})
dataset_id = config.get("dataset", {}).get("id")
if not dataset_id:
    dataset_id = config["01_segment_slice_wise"]["specimen_name"].split("_Bin", 1)[0]
print(dataset_id)
print(config["binning"]["label"])
print(" ".join(m.lower() for m in ys.get("materials", ["std"])))
print(" ".join(ys.get("loading_directions", ["tensor"])))
PYCFG
)
  if [[ ${#cfg[@]} -lt 4 ]]; then
    echo "[WARNUNG] $sample_id: config.json nicht lesbar - uebersprungen."
    continue
  fi
  dataset_id="${cfg[0]}"; binning_label="${cfg[1]}"
  read -r -a mats <<< "${cfg[2]}"
  read -r -a dirs <<< "${cfg[3]}"
  combo_tag="$(basename "$(dirname "$(dirname "$sample_dir")")")"

  # 1) Fertig? Zusammenfassungen aller mat/richtung-Kombinationen in 00_results
  all_done=1
  for mat in "${mats[@]}"; do
    for direction in "${dirs[@]}"; do
      final_dir="$working_directory/00_results/${dataset_id}/${binning_label}/yield_surface/${sample_id}-${mat}-${direction}"
      if [[ -z "$(find "$final_dir" -name "yield_run_${mat}_${direction}.json" -print -quit 2>/dev/null)" ]]; then
        all_done=0; break 2
      fi
    done
  done
  if [[ "$all_done" == "1" ]]; then
    n_done=$((n_done + 1)); continue
  fi

  # 2) Laeuft/wartet schon ein Job (auch Kettenglieder)? Jobname steht im
  #    Skript (#SBATCH -J <combo>-ysNNN, in 015 NICHT gleich der sample_id).
  job_name="$(awk '/^#SBATCH -J /{print $3; exit}' "$job_script")"
  if [[ -n "$job_name" ]] && grep -qxF "$job_name" <<< "$queued_names"; then
    echo "[LAEUFT ] $combo_tag/$sample_id - Job '$job_name' ist bereits eingereiht/aktiv."
    n_running=$((n_running + 1)); continue
  fi

  # 3) Letzte Fehlerdatei klassifizieren
  latest_err="$(ls -t "$sample_dir"/*.err.* 2>/dev/null | head -n 1 || true)"
  if [[ -z "$latest_err" ]]; then
    echo "[NIE GESTARTET] $combo_tag/$sample_id - keine .err-Datei; regulaer einreichen (batch_submit_CLUSTER.sh)."
    n_neverrun=$((n_neverrun + 1)); continue
  fi
  # "DUE TO TIME LIMIT" = harter SLURM-Kill.
  # "YIELD_WALLTIME_STOP" = elastoplastic.py hat sich kontrolliert kurz vor dem
  # Zeitlimit beendet (Snapshot + restart_meta geschrieben, Exit-Code 3). Beides
  # ist derselbe Fall: der Punkt ist nicht fertig und wird fortgesetzt.
  if grep -q -e "DUE TO TIME LIMIT" -e "YIELD_WALLTIME_STOP" "$latest_err"; then
    reason="TIMEOUT"
    n_timeout=$((n_timeout + 1))
  else
    reason="ANDERER FEHLER"
    n_failed=$((n_failed + 1))
    if [[ "$INCLUDE_FAILED" != "1" ]]; then
      echo "[FEHLER ] $combo_tag/$sample_id - letzter Abbruch war kein Timeout ($(basename "$latest_err")); uebersprungen (INCLUDE_FAILED=1 erzwingt)."
      continue
    fi
  fi

  # 4) Restart-Kette einreichen (Logs wie beim batch_submit in den Sample-Ordner)
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[DRY-RUN] $combo_tag/$sample_id ($reason) - wuerde Kette mit $MAX_CHAIN Jobs einreichen."
    continue
  fi
  log_args=(--error="$sample_dir/%x.err.%j" --output="$sample_dir/%x.out.%j")
  prev="$(sbatch --parsable "${log_args[@]}" "$job_script")"
  chain_ids=("$prev")
  for ((i = 2; i <= MAX_CHAIN; i++)); do
    prev="$(sbatch --parsable --dependency="afternotok:$prev" --kill-on-invalid-dep=yes "${log_args[@]}" "$job_script")"
    chain_ids+=("$prev")
  done
  echo "[RESUBMIT] $combo_tag/$sample_id ($reason): Kette ${chain_ids[*]}"
  n_submitted=$((n_submitted + 1))
done

echo ""
echo "Zusammenfassung: fertig=$n_done, laeuft=$n_running, Timeout=$n_timeout, andere Fehler=$n_failed, nie gestartet=$n_neverrun, neu eingereicht=$n_submitted (Kettenlaenge $MAX_CHAIN)"
if [[ "$n_submitted" -gt 0 ]]; then
  echo "Hinweis: Ueberwachen mit batch_status_CLUSTER.sh bzw. squeue -u \$USER;"
  echo "ein erfolgreich beendetes Glied raeumt seine restlichen Kettenglieder"
  echo "automatisch ab."
fi
