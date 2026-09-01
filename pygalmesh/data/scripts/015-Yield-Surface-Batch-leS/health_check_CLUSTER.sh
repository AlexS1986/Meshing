#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# health_check_CLUSTER.sh - schneller Gesundheits-Check der Studie 015
#
# Beantwortet auf einen Blick:
#   1. Was laeuft/wartet in der Queue (je Kombination)?
#   2. Gibt es Punkte, die "fertig" sind, aber KEINEN Fliessflaechenpunkt
#      geschrieben haben (final_yield_state = null)?  -> das darf nicht sein
#   3. Tauchen die bekannten Fehlerbilder neu auf (MUMPS error 76,
#      dt_below_minimum, viele verworfene Zeitschritte)?
#   4. Ist der MUMPS-Patch in den laufenden Jobs aktiv?
#   5. Wie weit sind die Laeufe bei den drei Fliesskriterien?
#
# Aufruf (auf dem Cluster):
#   bash health_check_CLUSTER.sh              # voller Check
#   QUICK=1 bash health_check_CLUSTER.sh      # ohne .out-Scan (nur Queue + JSON)
#   DATASET=JM-25-77 bash health_check_CLUSTER.sh   # nur ein Datensatz
#
# Exit-Code: 0 = alles in Ordnung, 1 = Warnungen, 2 = Fehler/Alarm
# ---------------------------------------------------------------------------
set -uo pipefail

WORK="${YS_WORKDIR:-$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS}"
QUICK="${QUICK:-0}"
DATASET="${DATASET:-}"
CRAWL_LIMIT="${CRAWL_LIMIT:-5}"     # ab so vielen verworfenen Schritten "Kriecher"

if [[ ! -d "$WORK" ]]; then
  echo "Arbeitsordner nicht gefunden: $WORK" >&2
  exit 2
fi
cd "$WORK" || exit 2

echo "==========================================================================="
echo " Studie 015 - Health Check   $(date '+%Y-%m-%d %H:%M')"
echo " Ordner: $WORK"
echo "==========================================================================="

# --- 1. Queue -------------------------------------------------------------
echo
echo "--- 1. Queue (squeue, ungekuerzte Jobnamen) -------------------------------"
if command -v squeue > /dev/null; then
  squeue --me -h -o "%T %j" \
    | awk '$2 ~ /-ys[0-9]+$/ { split($2, a, "-ys"); print a[1], $1 }' \
    | sort | uniq -c \
    | awk '{ printf "  %-22s %-9s %4s\n", $2, $3, $1 }'
  total_q=$(squeue --me -h -o "%j" | grep -c -- "-ys[0-9]*$")
  echo "  ---------------------------------------------"
  echo "  Punkt-Jobs in der Queue gesamt: $total_q"
else
  echo "  squeue nicht gefunden (laeuft dieses Skript auf dem Cluster?)"
fi

# --- 2.-5. Dateien --------------------------------------------------------
QUICK="$QUICK" DATASET="$DATASET" CRAWL_LIMIT="$CRAWL_LIMIT" python3 - <<'PY_EOF'
import glob, json, os, re, sys, collections

quick   = os.environ.get("QUICK", "0") == "1"
only_ds = os.environ.get("DATASET", "")
crawl_limit = int(os.environ.get("CRAWL_LIMIT", "5"))

# ---------------------------------------------------------------- Ergebnisse
# 00_results/<dataset>_les_r2/leS-r2-sigy<XXX>/yield_surface/<sample>-<mat>-<dir>/
#           <sample>/subvolume_x0_y0/yield_run_<mat>_<dir>.json
pattern = "00_results/*/*/yield_surface/*/*/*/yield_run_*.json"
jsons = [f for f in sorted(glob.glob(pattern)) if "_failed" not in f and "_packages" not in f]
if only_ds:
    jsons = [f for f in jsons if only_ds in f]

valid, invalid, crit_counts = [], [], collections.Counter()
per_combo = collections.defaultdict(lambda: {"json": 0, "valid": 0})

for f in jsons:
    parts = f.split("/")
    combo = f"{parts[1]}/{parts[2]}"
    sample = parts[4].split("-std")[0]
    try:
        d = json.load(open(f))
    except Exception as e:
        invalid.append((combo, sample, f"JSON nicht lesbar: {e}"))
        continue
    per_combo[combo]["json"] += 1
    if d.get("final_yield_state"):
        per_combo[combo]["valid"] += 1
        valid.append((combo, sample, d))
    else:
        invalid.append((combo, sample[:6],
                        f"stop_reason={d.get('stop_reason')} "
                        f"erreicht={','.join(d.get('criteria_reached') or []) or '-'}"))
    for name in (d.get("yield_states") or {}):
        crit_counts[name] += 1

print()
print("--- 2. Ergebnis-JSONs (Fertig-Markierung) ---------------------------------")
if not jsons:
    print("  noch keine yield_run_*.json vorhanden")
else:
    print(f"  {'KOMBINATION':38s} {'JSON':>5s} {'GUELTIG':>8s} {'OHNE PUNKT':>11s}")
    for combo in sorted(per_combo):
        s = per_combo[combo]
        bad = s["json"] - s["valid"]
        mark = "  <-- PRUEFEN" if bad else ""
        print(f"  {combo:38s} {s['json']:5d} {s['valid']:8d} {bad:11d}{mark}")

alarm = 0
if invalid:
    alarm = 1
    print()
    print(f"  !! ALARM: {len(invalid)} Lauf/Laeufe beendet OHNE final_yield_state:")
    for combo, sample, why in invalid[:20]:
        print(f"     {combo:38s} {sample:8s} {why}")
    if len(invalid) > 20:
        print(f"     ... und {len(invalid) - 20} weitere")
    print("     -> Ursache im .out pruefen (Abschnitt 3). Bei 'error code is: 76' /")
    print("        'dt too small': MUMPS-Problem, Rezept in RESTART_NACH_TIMEOUT.md.")
else:
    print()
    print("  OK: jede vorhandene Ergebnis-JSON enthaelt einen Fliessflaechenpunkt.")

# ------------------------------------------------- Teil-Fliesszustaende (live)
metas = glob.glob("yield_surface_runs/*/*/ys_*/subvolume_x0_y0/restart_meta_*.json")
if only_ds:
    metas = [m for m in metas if only_ds in m]

live = collections.Counter()
per_combo_live = collections.defaultdict(collections.Counter)
closest = []   # (abstand_faktor, combo, sample, werte)
THRESH = 0.002
for m in sorted(metas):
    parts = m.split("/")
    combo = f"{parts[1]}/{parts[2]}"
    sample = parts[3][:6]
    try:
        d = json.load(open(m))
    except Exception:
        continue
    for name in (d.get("yield_states") or {}):
        live[name] += 1
        per_combo_live[combo][name] += 1
    hist = d.get("averaged_history") or []
    if hist:
        s = hist[-1]
        epsp = s.get("eps_p_eq_macroscopic", 0.0) or 0.0
        closest.append((epsp, combo, sample, s))

print()
print("--- 3. Erreichte Fliesskriterien (Schwelle 0,002) --------------------------")
print("      Quelle: restart_meta_*.json der Arbeitsordner (auch laufende Jobs)")
if not metas:
    print("  noch keine Arbeitsordner mit restart_meta_*.json")
else:
    for name in ("yielded_fraction_material", "alpha_avg_material", "eps_p_eq_macroscopic"):
        n = live.get(name, 0)
        tag = "  <-- Primaerkriterium" if name == "eps_p_eq_macroscopic" else ""
        print(f"  {name:28s} {n:4d} von {len(metas)} Laeufen{tag}")
    if closest:
        closest.sort(reverse=True)
        print()
        print("  Am weitesten fortgeschritten (letzter Snapshot je Lauf):")
        print(f"  {'KOMBINATION':38s} {'SAMPLE':8s} {'scale':>8s} {'sig_vm':>7s} "
              f"{'eps_p_mac':>10s} {'x bis Ziel':>10s}")
        for epsp, combo, sample, s in closest[:5]:
            factor = THRESH / epsp if epsp > 0 else float("inf")
            fs = f"{factor:.0f}x" if factor != float("inf") else "-"
            print(f"  {combo:38s} {sample:8s} {s['strain_scale']:8.1e} "
                  f"{s['sig_vm_avg_reduced_volume']:7.2f} {epsp:10.1e} {fs:>10s}")

# --------------------------------------------------------------- .out-Scan
warn = 0
if quick:
    print()
    print("--- 4. Logfile-Scan uebersprungen (QUICK=1) -------------------------------")
else:
    print()
    print("--- 4. Logfile-Scan (jeweils neueste .out je Punkt) -----------------------")
    samples = sorted(glob.glob("yield_surface_jobs/*/n*/ys_*"))
    if only_ds:
        samples = [s for s in samples if only_ds in s]
    n_scanned = 0
    mumps, dtstop, crawl, walltime, patched, unpatched = [], [], [], [], 0, []
    for d in samples:
        outs = sorted(glob.glob(d + "/*.out.*"), key=os.path.getmtime)
        if not outs:
            continue
        n_scanned += 1
        newest = outs[-1]
        combo = d.split("/")[1]
        sample = os.path.basename(d)[:6]
        try:
            txt = open(newest, "rb").read().decode("utf-8", "replace")
        except Exception:
            continue
        fails = txt.count("NO CONVERGENCE")
        has_steps = "Computing solution at time" in txt
        if "error code is: 76" in txt:
            mumps.append((combo, sample, fails))
        if "dt too small" in txt:
            dtstop.append((combo, sample, fails))
        elif fails >= crawl_limit:
            crawl.append((combo, sample, fails))
        if "YIELD_WALLTIME_STOP" in txt or "walltime_deadline_reached" in txt:
            walltime.append((combo, sample))
        if has_steps:
            if "PETSc options (prefix nls_solve_)" in txt or "defaults applied" in txt:
                patched += 1
            else:
                unpatched.append((combo, sample))

    print(f"  {n_scanned} Punkte mit Logfile gescannt")
    print(f"  MUMPS-Fehler (error code 76)     : {len(mumps)}")
    print(f"  Abbruch 'dt too small'           : {len(dtstop)}")
    print(f"  Kriecher (>= {crawl_limit} verworfene Schritte): {len(crawl)}")
    print(f"  Walltime-Stop (Fortsetzung noetig): {len(walltime)}")
    print(f"  MUMPS-Patch aktiv / ohne Patch   : {patched} / {len(unpatched)}")

    if mumps or dtstop:
        alarm = 1
        print()
        print("  !! Betroffene Punkte (MUMPS-Fehler / Abbruch 'dt too small'):")
        seen = set()
        for combo, sample, f in mumps + dtstop:
            if (combo, sample) in seen:
                continue
            seen.add((combo, sample))
            if len(seen) > 20:
                print(f"     ... insgesamt {len(set((c, sm) for c, sm, _ in mumps + dtstop))} Punkte")
                break
            print(f"     {combo:24s} {sample:8s} verworfene Schritte: {f}")
    if crawl:
        warn = 1
        names = ["%s/%s (%d)" % (c.split("_sigy")[-1], sm, f) for c, sm, f in crawl[:12]]
        print()
        print("  ! Kriecher (laufen, aber mit Verwerfungen): " + ", ".join(names)
              + (" ..." if len(crawl) > 12 else ""))
    if unpatched:
        warn = 1
        names = ["%s/%s" % (c, sm) for c, sm in unpatched[:8]]
        print()
        print("  ! %d laufende Punkte OHNE MUMPS-Patch im Log "
              "(vor dem Patch gestartet - normal fuer Altlaeufe):" % len(unpatched))
        print("    " + ", ".join(names) + (" ..." if len(unpatched) > 8 else ""))

# ------------------------------------------------------------------ Fazit
print()
print("--- 5. Fazit --------------------------------------------------------------")
if alarm:
    print("  ALARM: siehe '!!'-Zeilen oben. Punkte ohne Fliessflaechenpunkt bzw.")
    print("         neue MUMPS-Abbrueche -> Bericht_MUMPS_Fehlerquelle_20260831.md")
    sys.exit(2)
if warn:
    print("  Warnungen (siehe '!'-Zeilen), aber keine verlorenen Punkte.")
    sys.exit(1)
print("  Alles in Ordnung: keine beendeten Laeufe ohne Fliessflaechenpunkt,")
print("  keine neuen MUMPS-Abbrueche.")
sys.exit(0)
PY_EOF
rc=$?

echo
echo "==========================================================================="
case $rc in
  0) echo " ERGEBNIS: OK" ;;
  1) echo " ERGEBNIS: Warnungen - siehe oben" ;;
  *) echo " ERGEBNIS: ALARM - siehe oben" ;;
esac
echo "==========================================================================="
exit $rc
