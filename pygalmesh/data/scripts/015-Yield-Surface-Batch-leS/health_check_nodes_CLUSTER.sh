#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# health_check_nodes_CLUSTER.sh - Gesundheits-Check der Studie 015 je Knotentyp
#
# Ergaenzt health_check_CLUSTER.sh um die Frage "laeuft es auf i02 genauso
# sauber wie auf i01?" und um die Fehlerbilder aus r2 (01./02.09.2026):
#   A  SLURM-Bilanz seit START (sacct): RUNNING/COMPLETED/FAILED/TIMEOUT/OOM,
#      ExitCode 3 = kontrollierter Walltime-Stop, je Knotentyp
#      (mpsc* = i01, mpsd* = i02)
#   B  Laufende Jobs: Fortschritt (Zeitschritte), Alter des letzten Log-Eintrags
#      -> Haenger (MUMPS-Kollektive nach getoetetem Rang), 'Killed' in .err (OOM),
#      MaxRSS gegen die Zuteilung (32 x 5600 MB = 179 GB)
#   C  Logfile-Scan je Knotentyp: NO CONVERGENCE, MUMPS error 76 / INFOG(1)=-9,
#      'dt too small', dofs (erwartet 1-2,5 Mio bei r4), Sekunden je Schritt
#   D  Ergebnis-JSONs ohne Fliessflaechenpunkt (dt_below_minimum), je Knotentyp
#   E  Fazit + Vergleichstabelle i01 vs i02
#
# Aufruf (Login-Knoten):
#   bash health_check_nodes_CLUSTER.sh
#   START=2026-09-03 STALE_MIN=90 bash health_check_nodes_CLUSTER.sh
#   DATASET=JM-25-77 bash health_check_nodes_CLUSTER.sh
#
# Exit-Code: 0 = ok, 1 = Warnungen, 2 = Alarm
# ---------------------------------------------------------------------------
set -uo pipefail

WORK="${YS_WORKDIR:-$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS}"
START="${START:-2026-09-03}"         # sacct-Startdatum (Umstellung auf i01|i02)
STALE_MIN="${STALE_MIN:-90}"         # Minuten ohne neuen Log-Eintrag -> Haenger-Verdacht
DATASET="${DATASET:-}"
MEM_PER_TASK_MB="${MEM_PER_TASK_MB:-5600}"   # --mem-per-cpu der Punkt-Jobs
DOFS_MIN="${DOFS_MIN:-800000}"
DOFS_MAX="${DOFS_MAX:-3000000}"

cd "$WORK" 2>/dev/null || { echo "Arbeitsordner nicht gefunden: $WORK" >&2; exit 2; }

echo "==========================================================================="
echo " Studie 015 - Health Check je Knotentyp   $(date '+%Y-%m-%d %H:%M')"
echo " Ordner: $WORK   sacct seit: $START   Haenger ab: ${STALE_MIN} min"
echo "==========================================================================="

SACCT_FILE=$(mktemp)
SSTAT_FILE=$(mktemp)
trap 'rm -f "$SACCT_FILE" "$SSTAT_FILE"' EXIT

# Haupt- und Step-Zeilen; -P = pipe-getrennt, -n = ohne Header
sacct -u "$USER" -S "$START" -P -n \
  -o JobID,JobName%60,State,ExitCode,Elapsed,NodeList,MaxRSS,NTasks,Start,End \
  > "$SACCT_FILE" 2>/dev/null || echo "  (sacct nicht verfuegbar)"

# MaxRSS laufender Jobs (Step .0 = srun im Job)
for J in $(squeue --me -h -t R -o "%i"); do
  sstat -P -n -o JobID,MaxRSS -j "${J}.0" 2>/dev/null
done > "$SSTAT_FILE"

SACCT_FILE="$SACCT_FILE" SSTAT_FILE="$SSTAT_FILE" STALE_MIN="$STALE_MIN" DATASET="$DATASET" \
MEM_PER_TASK_MB="$MEM_PER_TASK_MB" START="$START" DOFS_MIN="$DOFS_MIN" DOFS_MAX="$DOFS_MAX" python3 - <<'PY_EOF'
import collections, glob, json, os, re, sys, time

stale_min  = float(os.environ["STALE_MIN"])
only_ds    = os.environ.get("DATASET", "")
mem_per_task = float(os.environ["MEM_PER_TASK_MB"])
dofs_min   = float(os.environ["DOFS_MIN"]); dofs_max = float(os.environ["DOFS_MAX"])
alarm = warn = 0
alarms, warns = [], []

def node_type(nodelist):
    if not nodelist or nodelist in ("None assigned", "(null)"):
        return "-"
    if nodelist.startswith("mpsc"): return "i01"
    if nodelist.startswith("mpsd"): return "i02"
    return "andere"

def to_mb(s):
    s = (s or "").strip()
    if not s: return None
    m = re.match(r"([\d.]+)([KMGT]?)", s)
    if not m: return None
    v = float(m.group(1)); u = m.group(2)
    return v * {"": 1/1024/1024, "K": 1/1024, "M": 1, "G": 1024, "T": 1024*1024}[u]

# ---------------------------------------------------------------- A: sacct
jobs = {}          # jobid -> dict
for line in open(os.environ["SACCT_FILE"]):
    p = line.rstrip("\n").split("|")
    if len(p) < 10: continue
    jid, name, state, exitcode, elapsed, nodes, maxrss, ntasks, start, end = p[:10]
    base = jid.split(".")[0]
    if "." not in jid:
        if not re.search(r"-ys\d+$", name): continue
        if only_ds and only_ds not in name: continue
        jobs[base] = dict(id=base, name=name, state=state.split()[0], exit=exitcode,
                          elapsed=elapsed, nodes=nodes, ntype=node_type(nodes),
                          maxrss=None, start=start, end=end)
    else:
        if base in jobs:
            mb = to_mb(maxrss)
            if mb: jobs[base]["maxrss"] = max(jobs[base]["maxrss"] or 0, mb)
for line in open(os.environ["SSTAT_FILE"]):
    p = line.rstrip("\n").split("|")
    if len(p) < 2: continue
    base = p[0].split(".")[0]; mb = to_mb(p[1])
    if base in jobs and mb: jobs[base]["maxrss"] = max(jobs[base]["maxrss"] or 0, mb)

print()
print("--- A. SLURM-Bilanz der Punkt-Jobs seit Umstellung (sacct) -----------------")
if not jobs:
    print("  keine Punkt-Jobs in sacct seit dem Startdatum")
tab = collections.defaultdict(collections.Counter)
for j in jobs.values():
    st = j["state"]
    if st == "FAILED" and j["exit"].startswith("3:"):
        st = "WALLTIME_STOP(3)"
    tab[j["ntype"]][st] += 1
states = sorted({s for c in tab.values() for s in c})
if states:
    print("  " + f"{'KNOTEN':8s}" + "".join(f"{s:>18s}" for s in states))
    for nt in sorted(tab):
        print("  " + f"{nt:8s}" + "".join(f"{tab[nt][s]:18d}" for s in states))
bad_states = {"FAILED", "OUT_OF_MEMORY", "NODE_FAIL", "TIMEOUT", "CANCELLED"}
for j in sorted(jobs.values(), key=lambda x: x["id"]):
    if j["state"] in bad_states and not j["exit"].startswith("3:"):
        alarm = 1
        alarms.append(f"A: {j['name']} ({j['id']}, {j['ntype']}) {j['state']} exit {j['exit']} nach {j['elapsed']}")
    if j["state"] == "TIMEOUT":
        warns.append(f"A: {j['name']} ({j['id']}) TIMEOUT ohne kontrollierten Stop -> Snapshot pruefen")
if any(j["state"] == "FAILED" and j["exit"].startswith("3:") for j in jobs.values()):
    n = sum(1 for j in jobs.values() if j["state"] == "FAILED" and j["exit"].startswith("3:"))
    warns.append(f"A: {n} kontrollierte Walltime-Stops -> resubmit_yield_surface_timeouts_CLUSTER.sh")

# --------------------------------------------------- Logs den Jobs zuordnen
def find_logs(jid):
    outs = glob.glob(f"yield_surface_jobs/*/n*/ys_*/*.out.{jid}")
    errs = glob.glob(f"yield_surface_jobs/*/n*/ys_*/*.err.{jid}")
    return (outs[0] if outs else None), (errs[0] if errs else None)

def read(path):
    try: return open(path, "rb").read().decode("utf-8", "replace")
    except Exception: return ""

step_re = re.compile(r"Computing solution at time")
dofs_re = re.compile(r"solving fem problem with\s+([\d.,]+)\s+dofs", re.I)

scan = {}
now = time.time()
for j in jobs.values():
    out, err = find_logs(j["id"])
    j["out"], j["err"] = out, err
    if not out: continue
    txt = read(out)
    s = dict(
        steps=len(step_re.findall(txt)),
        noconv=txt.count("NO CONVERGENCE"),
        mumps76=("error code is: 76" in txt),
        mumps9=("INFOG(1)=-9" in txt or "INFO(1)=-9" in txt),
        dtsmall=("dt too small" in txt),
        wstop=("YIELD_WALLTIME_STOP" in txt or "walltime_deadline_reached" in txt),
        reached=len(re.findall(r"\[YIELD\] '.*?' erstmals erreicht", txt)),
        stop_all=("[STOP] alle Abbruchkriterien" in txt),
        age_min=(now - os.path.getmtime(out)) / 60.0,
        killed=("Killed" in read(err)) if err else False,
    )
    m = dofs_re.search(txt)
    s["dofs"] = float(m.group(1).replace(",", "")) if m else None
    # Sekunden je Schritt: aus Elapsed (h:m:s / d-h:m:s)
    el = j["elapsed"]; secs = 0
    try:
        d, rest = (el.split("-") + [None])[:2] if "-" in el else (0, el)
        hms = [int(x) for x in rest.split(":")]
        while len(hms) < 3: hms.insert(0, 0)
        secs = int(d) * 86400 + hms[0] * 3600 + hms[1] * 60 + hms[2]
    except Exception:
        pass
    s["sec_per_step"] = (secs / s["steps"]) if s["steps"] else None
    scan[j["id"]] = s

# ---------------------------------------------------------------- B: laufend
print()
print("--- B. Laufende Jobs: Fortschritt, Log-Alter, Speicher -----------------------")
running = [j for j in jobs.values() if j["state"] == "RUNNING"]
if not running:
    print("  keine laufenden Punkt-Jobs")
else:
    print(f"  {'JOB':>9s} {'KOMBINATION/PUNKT':34s} {'KN':4s} {'ELAPSED':>10s} {'STEPS':>6s} "
          f"{'VERW':>5s} {'s/STEP':>7s} {'LOG-ALTER':>10s} {'MaxRSS':>8s}")
    for j in sorted(running, key=lambda x: x["id"]):
        s = scan.get(j["id"])
        if not s:
            print(f"  {j['id']:>9s} {j['name'][:34]:34s} {j['ntype']:4s} {j['elapsed']:>10s}   (noch kein .out)")
            continue
        flags = []
        if s["age_min"] > stale_min and not s["stop_all"]:
            flags.append("HAENGER?"); alarm = 1
            alarms.append(f"B: {j['name']} ({j['id']}, {j['ntype']}) seit {s['age_min']:.0f} min kein Log-Eintrag")
        if s["killed"]:
            flags.append("KILLED/OOM"); alarm = 1
            alarms.append(f"B: {j['name']} ({j['id']}, {j['ntype']}) 'Killed' im .err (OOM-Killer)")
        if j["maxrss"] and j["maxrss"] > 0.9 * mem_per_task:
            flags.append("MEM>90%"); warn = 1
            warns.append(f"B: {j['name']} ({j['id']}) MaxRSS je Rang {j['maxrss']/1024:.1f} GB nahe Zuteilung {mem_per_task/1024:.1f} GB")
        if s["noconv"] >= 5:
            flags.append("KRIECHER"); warn = 1
        rss = f"{j['maxrss']/1024:.0f}G" if j["maxrss"] else "-"
        sps = f"{s['sec_per_step']:.0f}" if s["sec_per_step"] else "-"
        print(f"  {j['id']:>9s} {j['name'][:34]:34s} {j['ntype']:4s} {j['elapsed']:>10s} {s['steps']:6d} "
              f"{s['noconv']:5d} {sps:>7s} {s['age_min']:6.0f} min {rss:>8s}  {' '.join(flags)}")
    print("  (VERW = verworfene Schritte 'NO CONVERGENCE'; MaxRSS = groesster Rang, Zuteilung 5,6 GB je Rang)")

# ---------------------------------------------------------------- C: Logs je Knotentyp
print()
print("--- C. Logfile-Scan je Knotentyp (alle Jobs seit Umstellung) -----------------")
agg = collections.defaultdict(lambda: collections.defaultdict(list))
for j in jobs.values():
    s = scan.get(j["id"])
    if not s: continue
    a = agg[j["ntype"]]
    a["n"].append(1); a["steps"].append(s["steps"]); a["noconv"].append(s["noconv"])
    a["mumps"].append(int(s["mumps76"] or s["mumps9"])); a["dtsmall"].append(int(s["dtsmall"]))
    a["killed"].append(int(s["killed"])); a["reached"].append(int(s["reached"] > 0))
    if s["dofs"]: a["dofs"].append(s["dofs"])
    if s["sec_per_step"]: a["sps"].append(s["sec_per_step"])
    if s["mumps76"] or s["mumps9"]:
        alarm = 1; alarms.append(f"C: {j['name']} ({j['id']}, {j['ntype']}) MUMPS-Fehler im Log")
    if s["dtsmall"]:
        alarm = 1; alarms.append(f"C: {j['name']} ({j['id']}, {j['ntype']}) Abbruch 'dt too small'")
    if s["dofs"] and not (dofs_min <= s["dofs"] <= dofs_max):
        warn = 1; warns.append(f"C: {j['name']} ({j['id']}) dofs {s['dofs']:.3g} ausserhalb {dofs_min:.0f}-{dofs_max:.0f}")
def mean(x): return sum(x) / len(x) if x else 0.0
if not agg:
    print("  noch keine Logs")
else:
    print(f"  {'KNOTEN':8s} {'JOBS':>5s} {'STEPS/JOB':>10s} {'VERW/JOB':>9s} {'KRIECHER':>9s} {'MUMPS':>6s} "
          f"{'dt<min':>7s} {'KILLED':>7s} {'KRIT.ERR':>9s} {'dofs (Mio)':>11s} {'s/STEP':>7s}")
    for nt in sorted(agg):
        a = agg[nt]
        print(f"  {nt:8s} {len(a['n']):5d} {mean(a['steps']):10.1f} {mean(a['noconv']):9.2f} "
              f"{sum(1 for v in a['noconv'] if v >= 5):9d} {sum(a['mumps']):6d} {sum(a['dtsmall']):7d} "
              f"{sum(a['killed']):7d} {sum(a['reached']):9d} "
              f"{(mean(a['dofs'])/1e6 if a['dofs'] else 0):11.2f} {mean(a['sps']):7.0f}")
    print("  (KRIECHER = >= 5 verworfene Schritte; KRIT.ERR = Jobs mit mind. einem erreichten Fliesskriterium)")

# ---------------------------------------------------------------- D: JSONs
print()
print("--- D. Ergebnis-JSONs ohne Fliessflaechenpunkt (seit Umstellung) -------------")
pattern = "00_results/*/*/yield_surface/*/*/*/yield_run_*.json"
start_epoch = time.mktime(time.strptime(os.environ["START"], "%Y-%m-%d"))
n_json = n_bad = 0; bad = []
for f in sorted(glob.glob(pattern)):
    if "_failed" in f or "_packages" in f: continue
    if only_ds and only_ds not in f: continue
    if os.path.getmtime(f) < start_epoch: continue
    n_json += 1
    try: d = json.load(open(f))
    except Exception as e:
        n_bad += 1; bad.append((f, f"unlesbar: {e}")); continue
    if not d.get("final_yield_state"):
        n_bad += 1; bad.append((f, f"stop_reason={d.get('stop_reason')}"))
print(f"  JSONs: {n_json}   ohne Fliessflaechenpunkt: {n_bad}")
for f, why in bad[:15]:
    alarm = 1
    p = f.split("/"); alarms.append(f"D: {p[1]}/{p[2]} {p[4][:6]} {why}")
    print(f"     {p[1]}/{p[2]} {p[4][:6]} {why}")

# ---------------------------------------------------------------- E: Fazit
print()
print("--- E. Fazit ---------------------------------------------------------------")
if alarms:
    print("  !! ALARM:")
    for a in alarms[:30]: print("     " + a)
    if len(alarms) > 30: print(f"     ... und {len(alarms)-30} weitere")
if warns:
    print("  ! Warnungen:")
    for w in warns[:20]: print("     " + w)
if "i02" in agg:
    a = agg["i02"]
    kriecher = sum(1 for v in a["noconv"] if v >= 5)
    if sum(a["mumps"]) == 0 and sum(a["dtsmall"]) == 0 and sum(a["killed"]) == 0 and kriecher == 0:
        print(f"  i02: {len(a['n'])} Jobs ohne MUMPS-Fehler, dt-Abbruch, OOM oder Kriecher "
              f"-> bisher kein Hinweis auf das alte Konvergenzproblem.")
    else:
        print("  i02: Auffaelligkeiten vorhanden -> Zeilen oben; Vergleich mit i01 in Abschnitt C.")
else:
    print("  noch kein Job auf i02 gelaufen.")
if not alarms and not warns:
    print("  Alles in Ordnung.")
sys.exit(2 if alarms else (1 if warns else 0))
PY_EOF
rc=$?
echo
echo "==========================================================================="
case $rc in 0) echo " ERGEBNIS: OK";; 1) echo " ERGEBNIS: Warnungen";; *) echo " ERGEBNIS: ALARM";; esac
echo "==========================================================================="
exit $rc
