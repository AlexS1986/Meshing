#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# restart_dead_points_CLUSTER.sh - Sammel-Restart der Punkte, die mit
# Ergebnis-JSON, aber OHNE erreichtes Primaerkriterium geendet sind
# (typisch `stop_reason = dt_below_minimum`, Stand vor der Umstellung auf
# H = 70 / alpha_avg / Newton-Defaults; CLAUDE.md Publikationsordner §17-§19).
#
# Diese Punkte sind fuer `resubmit_yield_surface_timeouts_CLUSTER.sh` "fertig"
# (JSON vorhanden) und werden dort NICHT neu eingereicht. Hier passiert:
#   1. Kandidaten finden: Snapshot (restart_meta_*.json) vorhanden,
#      alpha_avg < Schwelle in der gesamten Historie, kein Job in der Queue
#   2. Ergebnis-JSONs beiseite legen (Run-Ordner und 00_results) -> sonst
#      ueberspringt job_yield_surface_point_CLUSTER.sh den Solverlauf
#   3. Job einreichen (OHNE YS_FORCE_FRESH -> Fortsetzung aus dem Snapshot),
#      optional mit YIELD_RESUME_DT und Kettenlaenge
#
# Aufruf (Login-Knoten):
#   DRY_RUN=1 ./restart_dead_points_CLUSTER.sh          # Vorschau (Default!)
#   DRY_RUN=0 LIMIT=200 ./restart_dead_points_CLUSTER.sh
# Optionen (Umgebung):
#   DRY_RUN=1|0 (Default 1)   LIMIT=<n> Punkte (Default 200)
#   MAX_CHAIN=<n> (Default 2) RESUME_DT=<float> (Default 1e-4, leer = Snapshot-dt)
#   ALPHA_THRESHOLD=<float> (Default 0.001)   TAG=r4
# ---------------------------------------------------------------------------
set -uo pipefail

WORK="${YS_WORKDIR:-$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS}"
DRY_RUN="${DRY_RUN:-1}"
LIMIT="${LIMIT:-200}"
MAX_CHAIN="${MAX_CHAIN:-2}"
RESUME_DT="${RESUME_DT:-1e-4}"
ALPHA_THRESHOLD="${ALPHA_THRESHOLD:-0.001}"
TAG="${TAG:-r4}"
STAMP="$(date +%Y%m%d)"

cd "$WORK" 2>/dev/null || { echo "Arbeitsordner nicht gefunden: $WORK" >&2; exit 2; }
WORK="$PWD"   # ab hier absolut (die Globs unten sind absolut)
USER="${USER:-$(id -un)}"
command -v sbatch > /dev/null || { echo "sbatch nicht gefunden - auf dem Cluster ausfuehren." >&2; exit 2; }

QUEUED="$(squeue -h -u "$USER" -o '%j' 2>/dev/null || true)"

# --- Kandidatenliste (Python: Historien lesen) ------------------------------
CAND="$(mktemp)"; trap 'rm -f "$CAND"' EXIT
WORK="$WORK" TAG="$TAG" ALPHA_THRESHOLD="$ALPHA_THRESHOLD" python3 - > "$CAND" <<'PY'
import glob, json, os
W = os.environ["WORK"]; TAG = os.environ["TAG"]; THR = float(os.environ["ALPHA_THRESHOLD"])
for meta in sorted(glob.glob(f"{W}/yield_surface_runs/*_les_{TAG}/*/ys_*/subvolume_x0_y0/restart_meta_*.json")):
    run_dir = os.path.dirname(meta)                       # .../<sample>/subvolume_x0_y0
    sample  = os.path.basename(os.path.dirname(run_dir))  # ys_xxx_e1_...
    binning = os.path.basename(os.path.dirname(os.path.dirname(run_dir)))   # leS-r4-sigyXXX
    ds_id   = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(run_dir))))  # <ds>_les_r4
    ds      = ds_id.replace(f"_les_{TAG}", "")
    sigy    = binning.split("sigy")[-1]
    # Ergebnis-JSONs: im Arbeitsordner und in 00_results
    jsons = sorted(glob.glob(f"{run_dir}/yield_run_*.json"))
    res_dirs = sorted(glob.glob(f"{W}/00_results/{ds_id}/{binning}/yield_surface/{sample}-*"))
    if not jsons and not res_dirs:
        continue                                          # nicht beendet -> resubmit-Skript zustaendig
    try:
        h = json.load(open(meta)).get("averaged_history") or []
    except Exception:
        continue
    if not h:
        continue
    amax = max(s.get("alpha_avg_reduced_material_volume", 0.0) for s in h)
    if amax >= THR:
        continue                                          # Fliesspunkt vorhanden -> fertig
    combo = f"{ds}_sigy{sigy}"
    job = sorted(glob.glob(f"{W}/yield_surface_jobs/{combo}/n*/{sample}/job_*_CLUSTER.sh"))
    if not job:
        continue
    print("\t".join([combo, sample, job[0], run_dir,
                     ";".join(jsons), ";".join(res_dirs),
                     f"{amax:.3e}", f"{h[-1]['strain_scale']:.4e}", str(len(h))]))
PY

total=$(wc -l < "$CAND")
echo "Kandidaten (JSON vorhanden, alpha_avg < $ALPHA_THRESHOLD, Snapshot da): $total"
[[ "$total" -eq 0 ]] && exit 0

n_sub=0 n_skip_q=0 n_fail=0
FAILED_DIR="$WORK/00_results/_failed_alpha_$STAMP"
while IFS=$'\t' read -r combo sample job_script run_dir jsons res_dirs amax strain steps; do
  [[ "$n_sub" -ge "$LIMIT" ]] && break
  job_name="$(awk '/^#SBATCH -J /{print $3; exit}' "$job_script")"
  if [[ -n "$job_name" ]] && grep -qxF "$job_name" <<< "$QUEUED"; then
    n_skip_q=$((n_skip_q + 1)); continue
  fi
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[DRY-RUN] $combo/${sample:0:6}  alpha_max=$amax  strain=$strain  steps=$steps -> Kette $MAX_CHAIN"
    n_sub=$((n_sub + 1)); continue
  fi
  mkdir -p "$FAILED_DIR/$combo"
  IFS=';' read -r -a jarr <<< "$jsons";   for f in "${jarr[@]}"; do [[ -n "$f" && -e "$f" ]] && mv "$f" "$FAILED_DIR/$combo/${sample:0:6}_$(basename "$f")"; done
  IFS=';' read -r -a rarr <<< "$res_dirs"; for d in "${rarr[@]}"; do [[ -n "$d" && -e "$d" ]] && mv "$d" "$FAILED_DIR/$combo/"; done
  sample_dir="$(dirname "$job_script")"
  log_args=(--error="$sample_dir/%x.err.%j" --output="$sample_dir/%x.out.%j")
  exp="ALL"; [[ -n "$RESUME_DT" ]] && exp="ALL,YIELD_RESUME_DT=$RESUME_DT"
  # Das LUA-job_submit-Plugin schreibt "[I] ..." auf stdout -> nur die ID nehmen
  prev="$(sbatch --parsable --export="$exp" "${log_args[@]}" "$job_script" | grep -o '^[0-9]\+' | tail -n 1)"
  if [[ -z "$prev" ]]; then
    echo "[FEHLER ] $combo/${sample:0:6} - sbatch lieferte keine Job-ID" >&2; n_fail=$((n_fail + 1)); continue
  fi
  chain=("$prev")
  for ((i = 2; i <= MAX_CHAIN; i++)); do
    prev="$(sbatch --parsable --dependency="afternotok:$prev" --kill-on-invalid-dep=yes --export="$exp" "${log_args[@]}" "$job_script" | grep -o '^[0-9]\+' | tail -n 1)"
    [[ -n "$prev" ]] || break
    chain+=("$prev")
  done
  echo "[RESTART] $combo/${sample:0:6} (alpha_max=$amax, strain=$strain): ${chain[*]}"
  n_sub=$((n_sub + 1))
done < "$CAND"

echo "----------------------------------------------------------------------"
echo "Kandidaten: $total   eingereicht: $n_sub   uebersprungen (in Queue): $n_skip_q   Fehler: $n_fail"
[[ "$DRY_RUN" == "1" ]] && echo "(DRY-RUN: nichts eingereicht, keine JSON verschoben; DRY_RUN=0 zum Ausfuehren)"
[[ "$DRY_RUN" != "1" ]] && echo "Alte Ergebnis-JSONs/Slim-Ordner: $FAILED_DIR"
echo "Rest fuer den naechsten Aufruf: $((total - n_sub - n_skip_q))"
