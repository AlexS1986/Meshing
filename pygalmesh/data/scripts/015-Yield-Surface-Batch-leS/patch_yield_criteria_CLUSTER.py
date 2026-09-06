#!/usr/bin/env python3
"""Patcht bestehende Studien-Configs auf die Entscheidungen vom 06.09.2026
(CLAUDE.md Publikationsordner §19):

  * primary_criterion = alpha_avg_material, Schwelle 1e-3
  * nur das Primaerkriterium bricht ab (blocking), die anderen werden aufgezeichnet
  * lineare Verfestigung hard = H [MPa] fuer alle material_sets

Betrifft die Datensatz-Configs (config-<ds>-r4-sigy<XXX>.json) und die
Punkt-Configs (yield_surface_jobs/<combo>/nNNN/ys_*/config.json). Laufende Jobs
haben ihre config.json bereits in den Arbeitsordner kopiert und bleiben
unberuehrt; wartende Jobs lesen die gepatchte Punkt-Config beim Start.

Aufruf (Login-Knoten):
  python3 patch_yield_criteria_CLUSTER.py [--root $S] [--alpha-threshold 1e-3] [--hardening 70] [--dry-run]
Ein Backup jeder Datei wird als <datei>.vor_kriterien_20260906 abgelegt (nur beim ersten Patch).
"""
import argparse, glob, json, os, shutil, sys

ap = argparse.ArgumentParser()
ap.add_argument("--root", default=os.path.expandvars("$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS"))
ap.add_argument("--primary", default="alpha_avg_material")
ap.add_argument("--alpha-threshold", type=float, default=1e-3)
ap.add_argument("--hardening", type=float, default=70.0)
ap.add_argument("--dry-run", action="store_true")
a = ap.parse_args()

files = sorted(glob.glob(os.path.join(a.root, "config-*-r4-sigy*.json"))) + \
        sorted(glob.glob(os.path.join(a.root, "yield_surface_jobs", "*", "n*", "ys_*", "config.json")))
print(f"{len(files)} Configs unter {a.root}")
n_changed = n_same = 0
summary = {}
for f in files:
    c = json.load(open(f))
    ys = c.get("yield_surface")
    if not ys:
        print("  ohne yield_surface:", f); continue
    before = json.dumps(ys, sort_keys=True)
    ys["primary_criterion"] = a.primary
    for crit in ys.get("criteria", []):
        crit["blocking"] = (crit["name"] == a.primary)
        if crit["name"] == "alpha_avg_material":
            crit["threshold"] = a.alpha_threshold
            crit["comment"] = ("<alpha> (akkumulierte aequivalente plastische Dehnung) ueber die Materialphase; "
                               "1e-3 ~ 2 % Boxdehnung, Tangente ~10 % der Anfangssteigung (r4, 06.09.2026)")
        elif crit["name"] == "eps_p_eq_macroscopic":
            crit["comment"] = ("sqrt(2/3 E_p:E_p), Volumenmittel des plastischen Dehnungstensors; in Schaeumen "
                               "durch Aufhebung der Biegeplastizitaet sehr klein -> nur Dokumentation (06.09.2026)")
    for name, m in ys.get("material_sets", {}).items():
        m["hard"] = a.hardening
    ys.setdefault("history", []).append(
        {"date": "2026-09-06", "change": f"primary={a.primary}, alpha_avg threshold={a.alpha_threshold}, "
                                          f"blocking=primary only, hard={a.hardening} MPa (patch_yield_criteria_CLUSTER.py)"})
    after = json.dumps(ys, sort_keys=True)
    if before == after:
        n_same += 1; continue
    n_changed += 1
    if not a.dry_run:
        bak = f + ".vor_kriterien_20260906"
        if not os.path.exists(bak):
            shutil.copy2(f, bak)
        json.dump(c, open(f, "w"), indent=2)
    key = (ys["primary_criterion"], tuple((k["name"], k["threshold"], k["blocking"]) for k in ys["criteria"]),
           tuple(sorted((n, m["hard"]) for n, m in ys["material_sets"].items())))
    summary[key] = summary.get(key, 0) + 1
print(f"geaendert: {n_changed}   unveraendert: {n_same}   {'(DRY-RUN, nichts geschrieben)' if a.dry_run else ''}")
for key, n in summary.items():
    prim, crits, hard = key
    print(f"  {n:4d} x primary={prim}")
    for name, thr, blk in crits:
        print(f"         {name:28s} >= {thr:g}  {'ABBRUCH' if blk else 'nur Doku'}")
    print(f"         hard: {dict(hard)}")
