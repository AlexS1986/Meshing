#!/usr/bin/env python3
"""Patcht bestehende Studien-Configs auf die aktuellen Entscheidungen
(CLAUDE.md Publikationsordner §19, §23; Variante A vom 09.09.2026):

  * primary_criterion = alpha_avg_material, Schwelle --alpha-threshold (09.09.: 2e-3)
  * nur das Primaerkriterium bricht ab (blocking), die anderen werden aufgezeichnet
  * zusaetzliche alpha-Stufen als reine Doku-Ereignisse (--doc-levels, Default
    0.001,0.005,0.01; jede Stufe loest [YIELD]-Ereignis + Feld-Snapshot aus)
  * lineare Verfestigung hard = H [MPa] fuer alle material_sets (09.09.: 0)

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
ap.add_argument("--root", default=os.path.expandvars("$HPC_SCRATCH/pygalmesh/data/scripts/017-Yield-Surface-Batch-leS-nohinge"))
ap.add_argument("--primary", default="alpha_avg_material")
ap.add_argument("--alpha-threshold", type=float, default=2e-3)
ap.add_argument("--hardening", type=float, default=0.0)
ap.add_argument("--doc-levels", default="0.001,0.005,0.01",
                help="alpha_avg-Stufen, die nur aufgezeichnet werden (kommagetrennt, '' = keine)")
ap.add_argument("--tag", default="20260909", help="Backup-Suffix .vor_kriterien_<tag>")
ap.add_argument("--dry-run", action="store_true")
a = ap.parse_args()
doc_levels = [float(x) for x in a.doc_levels.split(",") if x.strip()]

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
    # Doku-Stufen (Name alpha_avg_material_<x>) entfernen und neu aufbauen -> idempotent
    ys["criteria"] = [k for k in ys.get("criteria", []) if not k["name"].startswith("alpha_avg_material_")]
    for crit in ys["criteria"]:
        crit["blocking"] = (crit["name"] == a.primary)
        if crit["name"] == "alpha_avg_material":
            crit["threshold"] = a.alpha_threshold
            crit["comment"] = ("<alpha> (akkumulierte aequivalente plastische Dehnung) ueber die Materialphase; "
                               "Abbruchkriterium der Studie; 1e-3 ~ 1,5-2,5 % Boxdehnung, 2e-3 ~ 2,3-4,2 % "
                               "(H0-Tests 08./09.09.2026)")
        elif crit["name"] == "eps_p_eq_macroscopic":
            crit["comment"] = ("sqrt(2/3 E_p:E_p), Volumenmittel des plastischen Dehnungstensors; in Schaeumen "
                               "durch Aufhebung der Biegeplastizitaet sehr klein -> nur Dokumentation (06.09.2026)")
    for lvl in doc_levels:
        if abs(lvl - a.alpha_threshold) < 1e-12:
            continue
        ys["criteria"].append({"name": f"alpha_avg_material_{lvl:g}", "quantity": "alpha_avg_reduced_material_volume",
                               "threshold": lvl, "blocking": False,
                               "comment": "Doku-Stufe (Ereignis + Feld-Snapshot, kein Abbruch); Fliessflaechen-Familie"})
    for name, m in ys.get("material_sets", {}).items():
        m["hard"] = a.hardening
    ys.setdefault("history", []).append(
        {"date": "2026-09-09", "change": f"Variante A: primary={a.primary}, alpha_avg threshold={a.alpha_threshold}, "
                                          f"blocking=primary only, doc levels={doc_levels}, hard={a.hardening} MPa "
                                          f"(patch_yield_criteria_CLUSTER.py)"})
    after = json.dumps(ys, sort_keys=True)
    if before == after:
        n_same += 1; continue
    n_changed += 1
    if not a.dry_run:
        bak = f + ".vor_kriterien_" + a.tag
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
