#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup_H0_tests_CLUSTER.sh - Testlaeufe mit H = 0 (ideal plastisch) bis zu einer
# festen Makrodehnung, alle Fliesskriterien nur als Doku-Ereignisse.
#
# Zweck (08.09.2026, CLAUDE.md §22 ff.): (1) konvergiert H = 0 ohne Scharnier-
# teile am Fliessbeginn? (2) Verlauf der Makrokurve Richtung Plateau (Traglast),
# (3) Kosten je Punkt bis 5/10 % Dehnung. Ergebnisse landen getrennt von der
# Hauptstudie (binning label "<label>-H0", Jobordner yield_surface_jobs_H0/),
# batch_status/health_check/resubmit sehen sie nicht.
#
# Aufruf (Login-Knoten, im Studienordner auf Scratch):
#   DRY_RUN=1 ./setup_H0_tests_CLUSTER.sh              # nur anlegen + anzeigen
#   DRY_RUN=0 ./setup_H0_tests_CLUSTER.sh              # anlegen + einreichen
# Optionen (Umgebung):
#   DATASETS="JM-25-77 JM-25-71 JM-25-83 JM-25-88"   SIGY=075
#   SAMPLES="ys_095"        (ys_095 ~ Druck in z; ys_000 ~ Zug in z)
#   TOTAL_TIME=0.10         (Endwert der Dehnungsskala = Makrodehnung)
#   ALPHA_LEVELS="0.001 0.002 0.005 0.01"   (Doku-Ereignisse, jeweils Snapshot)
#   HARDENING=0             JOB_TIME=1440
# ---------------------------------------------------------------------------
set -euo pipefail
WORK="${YS_WORKDIR:-$HPC_SCRATCH/pygalmesh/data/scripts/$(basename "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")}"
DRY_RUN="${DRY_RUN:-1}"
DATASETS="${DATASETS:-JM-25-77 JM-25-71 JM-25-83 JM-25-88}"
SIGY="${SIGY:-075}"
SAMPLES="${SAMPLES:-ys_095}"
TOTAL_TIME="${TOTAL_TIME:-0.10}"
ALPHA_LEVELS="${ALPHA_LEVELS:-0.001 0.002 0.005 0.01}"
HARDENING="${HARDENING:-0}"
JOB_TIME="${JOB_TIME:-1440}"
cd "$WORK"
PROJECT="$(basename "$WORK")"
OUT="$WORK/yield_surface_jobs_H0"
mkdir -p "$OUT"
n_sub=0
for DS in $DATASETS; do
  combo="${DS}_sigy${SIGY}"
  for SMP in $SAMPLES; do
    src=$(ls -d "$WORK/yield_surface_jobs/$combo"/n*/"${SMP}"_* 2>/dev/null | head -1)
    [[ -n "$src" ]] || { echo "[FEHLER] kein Punkt-Job fuer $combo/$SMP" >&2; continue; }
    sid="$(basename "$src")"
    dst="$OUT/$combo/$sid"
    mkdir -p "$dst"
    WORK="$WORK" SRC="$src/config.json" DST="$dst/config.json" TOTAL_TIME="$TOTAL_TIME" \
    ALPHA_LEVELS="$ALPHA_LEVELS" HARDENING="$HARDENING" python3 - <<'PY'
import json, os
c = json.load(open(os.environ["SRC"])); ys = c["yield_surface"]
c["binning"]["label"] = c["binning"]["label"] + "-H0"
ys["total_time"] = float(os.environ["TOTAL_TIME"])
for m in ys.get("material_sets", {}).values():
    m["hard"] = float(os.environ["HARDENING"])
levels = [float(x) for x in os.environ["ALPHA_LEVELS"].split()]
crit = [k for k in ys["criteria"] if k["quantity"] != "alpha_avg_reduced_material_volume"]
for k in crit: k["blocking"] = False
for a in levels:
    crit.append({"name": f"alpha_avg_material_{a:g}", "quantity": "alpha_avg_reduced_material_volume",
                 "threshold": a, "blocking": False,
                 "comment": "H0-Testlauf 08.09.2026: Doku-Ereignis (Snapshot), kein Abbruch; Abbruch nur ueber total_time"})
ys["criteria"] = crit
ys["primary_criterion"] = f"alpha_avg_material_{levels[0]:g}"
ys.setdefault("history", []).append({"date": "2026-09-08", "change": f"H0-Test: hard={os.environ['HARDENING']}, total_time={os.environ['TOTAL_TIME']}, alle Kriterien blocking=false, alpha-Stufen {levels} (setup_H0_tests_CLUSTER.sh)"})
json.dump(c, open(os.environ["DST"], "w"), indent=2); open(os.environ["DST"], "a").write("\n")
print(f"  config: {os.environ['DST']}  label={c['binning']['label']} hard={os.environ['HARDENING']} total_time={ys['total_time']} kriterien={[k['name'] for k in crit]}")
PY
    jobsrc=$(ls "$src"/job_*_CLUSTER.sh | head -1)
    jobdst="$dst/job_${sid}_H0_CLUSTER.sh"
    jn="${DS}_s${SIGY}-H0-${SMP/ys_/ys}"
    sed -e "s|^#SBATCH -J .*|#SBATCH -J ${jn:0:48}|" \
        -e "s|^#SBATCH -t .*|#SBATCH -t ${JOB_TIME}|" \
        -e "s|^#SBATCH -e .*|#SBATCH -e ${dst}/%x.err.%j|" \
        -e "s|^#SBATCH -o .*|#SBATCH -o ${dst}/%x.out.%j|" \
        -e "s|/data/scripts/${PROJECT}/yield_surface_jobs/${combo}/n[0-9]*/${sid}/config.json|/data/scripts/${PROJECT}/yield_surface_jobs_H0/${combo}/${sid}/config.json|" \
        "$jobsrc" > "$jobdst"
    chmod 755 "$jobdst"
    grep -q "yield_surface_jobs_H0" "$jobdst" || { echo "[FEHLER] Config-Pfad im Jobskript nicht ersetzt: $jobdst" >&2; exit 1; }
    if [[ "$DRY_RUN" == "1" ]]; then
      echo "  [dry-run] sbatch $jobdst   (-J $jn)"
    else
      out=$(sbatch "$jobdst" 2>&1); jid=$(echo "$out" | grep -o "Submitted batch job [0-9]*" | grep -o "[0-9]*$")
      echo "  eingereicht: $jn -> Job ${jid:-?}"; n_sub=$((n_sub+1))
    fi
  done
done
echo "Jobordner: $OUT   eingereicht: $n_sub   (DRY_RUN=$DRY_RUN)"
