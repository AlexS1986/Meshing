#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Reicht Fliessflaechen-Punktjobs, die am SLURM-Zeitlimit abgebrochen sind,
# als Restart-Kette neu ein. Jeder Kettenjob laeuft wieder mit dem Zeitlimit
# des urspruenglichen Punkt-Jobskripts (z.B. -t 1440) und setzt die Rechnung
# ueber den Restart-Mechanismus in elastoplastic.py/yield_restart.py fort.
#
# Kette: Job 1 wird sofort eingereicht; Jobs 2..MAX_CHAIN haengen jeweils mit
#   --dependency=afternotok:<Vorgaenger> --kill-on-invalid-dep=yes
# am Vorgaenger. Bricht ein Glied am Zeitlimit (oder anderweitig) ab, startet
# das naechste und setzt fort; laeuft ein Glied erfolgreich durch, werden die
# restlichen Glieder von SLURM automatisch entfernt (DependencyNeverSatisfied
# + kill-on-invalid-dep). Manuelles Nachreichen ist nicht noetig; reicht die
# Kette nicht aus, dieses Skript einfach erneut aufrufen.
#
# Aufruf (auf dem Cluster, nach dem Sync des 014-Ordners):
#   resubmit_yield_surface_timeouts_CLUSTER.sh [JOBS_ROOT]
#
#   JOBS_ROOT   Ordner mit den Punkt-Jobs (Default:
#               $HPC_SCRATCH/.../014-Yield-Surface-From-leS/yield_surface_jobs,
#               es werden alle nNNN-Unterordner durchsucht)
#
# Umgebungsvariablen:
#   MAX_CHAIN=5        Gesamtzahl Jobs je Kette (1 Start + 4 Fortsetzungen)
#   DRY_RUN=1          nur anzeigen, nichts einreichen
#   INCLUDE_FAILED=1   auch Jobs neu einreichen, deren letzter Abbruch KEIN
#                      Timeout war (Default: nur Timeout-Jobs)
# ---------------------------------------------------------------------------

working_directory="$HPC_SCRATCH/pygalmesh/data/scripts/014-Yield-Surface-From-leS"
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

# Alle Sample-Ordner einsammeln (JOBS_ROOT selbst oder nNNN-Unterordner)
sample_dirs=()
for d in "$JOBS_ROOT"/ys_*/ "$JOBS_ROOT"/*/ys_*/; do
  [[ -d "$d" ]] && sample_dirs+=("${d%/}")
done
if [[ ${#sample_dirs[@]} -eq 0 ]]; then
  echo "Keine ys_*-Sample-Ordner unter $JOBS_ROOT gefunden." >&2
  exit 2
fi

# Laufende/wartende Jobs des Nutzers einmalig abfragen (Name = sample_id)
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

  # dataset/binning/Materialien/Richtungen aus der Config
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

  # 2) Laeuft/wartet schon ein Job (auch Kettenglieder) mit diesem Namen?
  job_name="${sample_id:0:48}"
  if grep -qxF "$job_name" <<< "$queued_names"; then
    echo "[LAEUFT ] $sample_id - Job ist bereits eingereiht/aktiv, nichts zu tun."
    n_running=$((n_running + 1)); continue
  fi

  # 3) Letzte Fehlerdatei klassifizieren
  latest_err="$(ls -t "$sample_dir"/*.err.* 2>/dev/null | head -n 1 || true)"
  if [[ -z "$latest_err" ]]; then
    echo "[NIE GESTARTET] $sample_id - keine .err-Datei; bitte regulaer einreichen."
    n_neverrun=$((n_neverrun + 1)); continue
  fi
  if grep -q "DUE TO TIME LIMIT" "$latest_err"; then
    reason="TIMEOUT"
    n_timeout=$((n_timeout + 1))
  else
    reason="ANDERER FEHLER"
    n_failed=$((n_failed + 1))
    if [[ "$INCLUDE_FAILED" != "1" ]]; then
      echo "[FEHLER ] $sample_id - letzter Abbruch war kein Timeout ($(basename "$latest_err")); uebersprungen (INCLUDE_FAILED=1 erzwingt)."
      continue
    fi
  fi

  # 4) Restart-Kette einreichen
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[DRY-RUN] $sample_id ($reason) - wuerde Kette mit $MAX_CHAIN Jobs einreichen."
    continue
  fi
  prev="$(sbatch --parsable "$job_script")"
  chain_ids=("$prev")
  for ((i = 2; i <= MAX_CHAIN; i++)); do
    prev="$(sbatch --parsable --dependency="afternotok:$prev" --kill-on-invalid-dep=yes "$job_script")"
    chain_ids+=("$prev")
  done
  echo "[RESUBMIT] $sample_id ($reason): Kette ${chain_ids[*]}"
  n_submitted=$((n_submitted + 1))
done

echo ""
echo "Zusammenfassung: fertig=$n_done, laeuft=$n_running, Timeout=$n_timeout, andere Fehler=$n_failed, nie gestartet=$n_neverrun, neu eingereicht=$n_submitted (Kettenlaenge $MAX_CHAIN)"
if [[ "$n_submitted" -gt 0 ]]; then
  echo "Hinweis: Ketten ueberwachen mit squeue -u \$USER; ein erfolgreich beendetes"
  echo "Glied raeumt seine restlichen Kettenglieder automatisch ab."
fi
