#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# health_check_nodes_CLUSTER.sh - Gesundheits-Check der Studie 016 je Knotentyp
#
# Nach dem Vorbild von 015/health_check_nodes_CLUSTER.sh, zugeschnitten auf die
# Frage aus dem OpenBLAS-Vorfall (015, 05.09.2026): rechnet alex-dolfinx.sif auf
# i02 (Sapphire Rapids, mpsd*) genauso sauber wie auf i01 (mpsc*)?
#   A  SLURM-Bilanz der 016-Jobs seit START (sacct) je Knotentyp
#   B  Logfile-Scan je Job und je Knotentyp: DMUMPS INFO(1)= -10 (numerisch
#      singulaer = BLAS-Fehlbild), NO CONVERGENCE, nan, dt too small, sowie ob
#      OPENBLAS_CORETYPE im Log auftaucht
#   C  Fazit
#
# Prueft die sbatch-Logs %x.out.%j / %x.err.%j im Projektordner (Jobnamen
# frac-les-sim, mesh-les-frac, blas-*). Kriterien sind als >= 1 formuliert,
# weil grep -c auch Kommentar-/Echo-Zeilen mitzaehlt.
#
# Aufruf (Login-Knoten):
#   bash health_check_nodes_CLUSTER.sh
#   START=2026-09-06 bash health_check_nodes_CLUSTER.sh
#
# Exit-Code: 0 = ok, 1 = Warnungen, 2 = Alarm
# ---------------------------------------------------------------------------
set -uo pipefail

WORK="${FRAC_WORKDIR:-$HPC_SCRATCH/pygalmesh/data/scripts/016-Fracture-From-leS}"
START="${START:-2026-09-06}"      # Datum des OpenBLAS-Fixes in 016
JOBNAMES="${JOBNAMES:-frac-les-sim,mesh-les-frac,blas-ohne,blas-mit}"

cd "$WORK" 2>/dev/null || { echo "Arbeitsordner nicht gefunden: $WORK" >&2; exit 2; }

echo "==========================================================================="
echo " Studie 016 - Health Check je Knotentyp   $(date '+%Y-%m-%d %H:%M')"
echo " Ordner: $WORK   sacct seit: $START   Jobnamen: $JOBNAMES"
echo "==========================================================================="

SACCT_FILE=$(mktemp); trap 'rm -f "$SACCT_FILE"' EXIT
sacct -u "$USER" -S "$START" -P -n --name="$JOBNAMES" \
  -o JobID,JobName%30,State,ExitCode,Elapsed,NodeList,Start \
  > "$SACCT_FILE" 2>/dev/null || echo "  (sacct nicht verfuegbar)"

SACCT_FILE="$SACCT_FILE" python3 - <<'PY_EOF'
import collections, glob, os, re, sys

alarms, warns = [], []

def node_type(nodelist):
    if not nodelist or nodelist in ("None assigned", "(null)"): return "-"
    if nodelist.startswith("mpsc"): return "i01"
    if nodelist.startswith("mpsd"): return "i02"
    if nodelist.startswith("mem") or nodelist.startswith("m0"): return "mem"
    return "andere"

# ------------------------------------------------------------------ A: sacct
jobs = {}
for line in open(os.environ["SACCT_FILE"]):
    p = line.rstrip("\n").split("|")
    if len(p) < 7 or "." in p[0]: continue
    jid, name, state, exitcode, elapsed, nodes, start = p[:7]
    jobs[jid] = dict(id=jid, name=name, state=state.split()[0], exit=exitcode,
                     elapsed=elapsed, nodes=nodes, ntype=node_type(nodes))

print()
print("--- A. SLURM-Bilanz der 016-Jobs seit START (sacct) ---------------------------")
if not jobs:
    print("  keine 016-Jobs in sacct seit dem Startdatum")
tab = collections.defaultdict(collections.Counter)
for j in jobs.values(): tab[j["ntype"]][j["state"]] += 1
states = sorted({s for c in tab.values() for s in c})
if states:
    print("  " + f"{'KNOTEN':8s}" + "".join(f"{s:>16s}" for s in states))
    for nt in sorted(tab):
        print("  " + f"{nt:8s}" + "".join(f"{tab[nt][s]:16d}" for s in states))
for j in sorted(jobs.values(), key=lambda x: x["id"]):
    if j["state"] in {"FAILED", "OUT_OF_MEMORY", "NODE_FAIL", "TIMEOUT"}:
        alarms.append(f"A: {j['name']} ({j['id']}, {j['ntype']}) {j['state']} exit {j['exit']} nach {j['elapsed']}")

# ------------------------------------------------------------------ B: Logs
def read(path):
    try: return open(path, "rb").read().decode("utf-8", "replace")
    except Exception: return ""

pat = {
    "mumps-10":   re.compile(r"INFO\(1\)\s*=\s*-10|INFOG\(1\)\s*=\s*-10"),
    "noconv":     re.compile(r"NO CONVERGENCE"),
    "nan":        re.compile(r"\bnan\b", re.I),
    "dt<min":     re.compile(r"dt too small"),
    "mumps-9":    re.compile(r"INFO\(1\)\s*=\s*-9\b|INFOG\(1\)\s*=\s*-9\b|error code is: 76"),
}
print()
print("--- B. Logfile-Scan (%x.out.%j + %x.err.%j) --------------------------------")
print(f"  {'JOB':>9s} {'NAME':14s} {'KN':4s} {'STATE':10s} " + "".join(f"{k:>9s}" for k in pat) + "  CORETYPE")
agg = collections.defaultdict(lambda: collections.Counter())
for j in sorted(jobs.values(), key=lambda x: x["id"]):
    logs = glob.glob(f"*.out.{j['id']}") + glob.glob(f"*.err.{j['id']}") + \
           glob.glob(f"scratch/blas_check/*.{j['id']}.out")
    if not logs:
        print(f"  {j['id']:>9s} {j['name'][:14]:14s} {j['ntype']:4s} {j['state']:10s}   (kein Log gefunden)")
        continue
    txt = "\n".join(read(l) for l in logs)
    counts = {k: len(r.findall(txt)) for k, r in pat.items()}
    core = "SkylakeX" if "core: SkylakeX" in txt else ("Cooperlake" if "core: Cooperlake" in txt else
           ("gesetzt" if "OPENBLAS_CORETYPE" in txt else "-"))
    agg[j["ntype"]]["jobs"] += 1
    for k, v in counts.items():
        if v >= 1: agg[j["ntype"]][k] += 1
    flags = []
    if counts["mumps-10"] >= 1:
        flags.append("MUMPS-10"); alarms.append(f"B: {j['name']} ({j['id']}, {j['ntype']}) DMUMPS INFO(1)=-10 -> BLAS-Fehlbild, OPENBLAS_CORETYPE pruefen")
    if counts["nan"] >= 1:
        flags.append("NaN"); alarms.append(f"B: {j['name']} ({j['id']}, {j['ntype']}) 'nan' im Log")
    if counts["dt<min"] >= 1:
        flags.append("dt<min"); alarms.append(f"B: {j['name']} ({j['id']}, {j['ntype']}) Abbruch 'dt too small'")
    if counts["mumps-9"] >= 1:
        flags.append("MUMPS-9/76"); warns.append(f"B: {j['name']} ({j['id']}, {j['ntype']}) MUMPS Speicherfehler (-9/76)")
    if counts["noconv"] >= 1 and j["name"].startswith("frac"):
        warns.append(f"B: {j['name']} ({j['id']}, {j['ntype']}) {counts['noconv']}x NO CONVERGENCE")
    if core == "Cooperlake" and j["name"] != "blas-ohne":
        alarms.append(f"B: {j['name']} ({j['id']}) OpenBLAS-Kern Cooperlake trotz Fix")
    print(f"  {j['id']:>9s} {j['name'][:14]:14s} {j['ntype']:4s} {j['state']:10s} "
          + "".join(f"{counts[k]:9d}" for k in pat) + f"  {core}  {' '.join(flags)}")

print()
print("  Treffer je Knotentyp (Anzahl Jobs mit >= 1 Treffer):")
print(f"  {'KNOTEN':8s} {'JOBS':>5s}" + "".join(f"{k:>10s}" for k in pat))
for nt in sorted(agg):
    a = agg[nt]
    print(f"  {nt:8s} {a['jobs']:5d}" + "".join(f"{a[k]:10d}" for k in pat))

# ------------------------------------------------------------------ C: Fazit
print()
print("--- C. Fazit ---------------------------------------------------------------")
if alarms:
    print("  !! ALARM:"); [print("     " + a) for a in alarms[:30]]
if warns:
    print("  ! Warnungen:"); [print("     " + w) for w in warns[:20]]
if "i02" in agg:
    a = agg["i02"]
    if a["mumps-10"] == 0 and a["nan"] == 0 and a["dt<min"] == 0:
        print(f"  i02: {a['jobs']} Jobs ohne MUMPS -10, NaN oder dt-Abbruch -> kein Hinweis auf das OpenBLAS-Problem.")
    else:
        print("  i02: Auffaelligkeiten -> Zeilen oben; Vergleich mit i01 in Abschnitt B.")
else:
    print("  noch kein 016-Job auf i02 gelaufen.")
if not alarms and not warns: print("  Alles in Ordnung.")
sys.exit(2 if alarms else (1 if warns else 0))
PY_EOF
rc=$?
echo
echo "==========================================================================="
case $rc in 0) echo " ERGEBNIS: OK";; 1) echo " ERGEBNIS: Warnungen";; *) echo " ERGEBNIS: ALARM";; esac
echo "==========================================================================="
exit $rc
