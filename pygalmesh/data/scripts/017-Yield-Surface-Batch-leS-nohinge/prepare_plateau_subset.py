#!/usr/bin/env python3
"""Bereitet die Plateau-Fortsetzung einer Teilmenge der Studie 017 vor
(Entscheidung 10.09.2026, CLAUDE_PROJECT_NOTES).

Hintergrund: Die Hauptstudie endet bei alpha_avg_material = 2e-3 (~2-3 %
Boxdehnung). Die H0-Testlaeufe zeigen, dass die Tangente erst bei ~5 %
Dehnung unter 2-5 % der Anfangssteigung faellt und die Spannung dort 15-20 %
ueber der 2e-3-Fliessspannung liegt. Statt alle 768 Punkte weiterzurechnen
(~600k Kernstunden) wird eine Teilmenge aus den vorhandenen Snapshots bis
5 % Dehnung fortgesetzt, um zu pruefen, ob sig(5 %)/sig(2e-3) richtungs-
unabhaengig ist (dann ist die Plateauflaeche die skalierte 2e-3-Flaeche).

Was das Skript tut, je ausgewaehltem Punkt:
  1. sichert `yield_run_<mat>_<dir>.json` und `restart_meta_*.json` im
     Arbeitsordner als `*.alpha2e-3` (die 2e-3-Auswertung liegt zusaetzlich
     unveraendert in 00_results/) und ENTFERNT die yield_run-Datei, damit
     job_yield_surface_point_CLUSTER.sh den Solverlauf nicht ueberspringt;
  2. entfernt in `restart_meta_*.json` den Eintrag des blockierenden Kriteriums
     aus `yield_states` -- elastoplastic.py laedt diese Liste beim Restart
     (Z. 700) und bricht ab, sobald ALLE blockierenden Kriterien darin stehen
     (Z. 959), OHNE die Schwelle neu zu pruefen. Ohne diesen Schritt endet der
     Fortsetzungslauf nach einem Zeitschritt mit "[STOP] alle Abbruchkriterien
     erreicht" (so passiert am 10.09.2026, 96 Jobs a 4-10 min);
  3. patcht die Punkt-Config: `total_time = <ziel-dehnung>` (t == strain_scale,
     der Solver endet dort regulaer und schreibt die Zusammenfassung),
     alpha_avg_material-Schwelle unerreichbar (0.05), damit ALLE Punkte
     dieselbe Enddehnung erreichen; 1e-3/2e-3/5e-3/1e-2 bleiben Doku-Stufen
     mit Feld-Snapshot.
  4. schreibt die Liste der einzureichenden Jobskripte nach --job-list.

Der vorhandene Rechenstand (elastoplastic_*.xdmf + restart_meta) bleibt
liegen; elastoplastic.py setzt ihn fort (yield_restart.py). Bei JM-25-71/83
reicht ein 24-h-Job nicht bis 5 % -> Walltime-Stop und Fortsetzung per
resubmit_yield_surface_timeouts_CLUSTER.sh (Kette).

Aufruf (Login-Knoten, Studienordner):
  python3 prepare_plateau_subset.py --dry-run
  python3 prepare_plateau_subset.py --apply
"""
import argparse, glob, json, os, shutil, sys

ap = argparse.ArgumentParser()
ap.add_argument("--root", default=os.path.expandvars("$HPC_SCRATCH/pygalmesh/data/scripts/017-Yield-Surface-Batch-leS-nohinge"))
ap.add_argument("--datasets", default="JM-25-71,JM-25-77,JM-25-83,JM-25-88")
ap.add_argument("--sigy", default="075")
ap.add_argument("--n-directions", type=int, default=24, help="Anzahl Richtungen je Kombination (gleichmaessig aus 96 gezogen)")
ap.add_argument("--target-strain", type=float, default=0.05, help="Enddehnung (total_time); t == strain_scale")
ap.add_argument("--doc-levels", default="0.001,0.002,0.005,0.01")
ap.add_argument("--tag", default="alpha2e-3", help="Suffix der Sicherungskopien im Arbeitsordner")
ap.add_argument("--job-list", default="/tmp/plateau_jobs.txt")
ap.add_argument("--apply", action="store_true")
ap.add_argument("--dry-run", action="store_true")
a = ap.parse_args()
if not (a.apply or a.dry_run):
    sys.exit("Bitte --dry-run oder --apply angeben.")
doc_levels = [float(x) for x in a.doc_levels.split(",") if x.strip()]

os.chdir(a.root)
jobs, skipped = [], []
for ds in a.datasets.split(","):
    combo = f"{ds}_sigy{a.sigy}"
    run_root = f"yield_surface_runs/{ds}_les_r4/leS-r4-sigy{a.sigy}"
    all_jobs = sorted(glob.glob(f"yield_surface_jobs/{combo}/n*/ys_*/job_*_CLUSTER.sh"))
    if not all_jobs:
        skipped.append(f"{combo}: keine Jobskripte"); continue
    step = max(len(all_jobs) // a.n_directions, 1)
    chosen = all_jobs[::step][:a.n_directions]
    print(f"\n{combo}: {len(chosen)} von {len(all_jobs)} Richtungen (jede {step}.)")
    for job in chosen:
        point = os.path.basename(os.path.dirname(job))
        sub = f"{run_root}/{point}/subvolume_x0_y0"
        summ = glob.glob(f"{sub}/yield_run_*.json")
        metas = glob.glob(f"{sub}/restart_meta_*.json")
        state = glob.glob(f"{sub}/elastoplastic_*.xdmf")
        if not (summ and metas and state):
            skipped.append(f"{combo}/{point[:6]}: Rechenstand unvollstaendig (json {len(summ)}, meta {len(metas)}, xdmf {len(state)})")
            continue
        hist = json.load(open(metas[0])).get("averaged_history", [])
        reached = max((x["strain_scale"] for x in hist), default=0.0)
        alpha = max((x.get("alpha_avg_reduced_material_volume") or 0.0 for x in hist), default=0.0)
        if reached >= a.target_strain:
            skipped.append(f"{combo}/{point[:6]}: schon bei {reached:.2%} (>= Ziel)"); continue
        print(f"  {point[:6]}: Stand {reached:.2%}, alpha {alpha:.2e} -> Ziel {a.target_strain:.0%}")
        cfg_path = os.path.join(os.path.dirname(job), "config.json")
        if a.apply:
            for f in summ + metas:
                bak = f + "." + a.tag
                if not os.path.exists(bak): shutil.copy2(f, bak)
            for f in summ: os.remove(f)          # sonst ueberspringt der Job den Solverlauf
            # Erreichte Kriterien zuruecksetzen: sonst stoppt der Restart sofort
            for f in metas:
                meta = json.load(open(f)); ystates = meta.get("yield_states", {})
                removed = [k for k in list(ystates) if k == "alpha_avg_material"]
                for k in removed: ystates.pop(k)
                if removed:
                    meta["yield_states"] = ystates
                    meta.setdefault("plateau_note", []).append(
                        f"yield_states {removed} entfernt (Plateau-Fortsetzung bis {a.target_strain:g})")
                    json.dump(meta, open(f, "w"), indent=2)
            cfg = json.load(open(cfg_path)); ys = cfg["yield_surface"]
            bak = cfg_path + ".vor_plateau"
            if not os.path.exists(bak): shutil.copy2(cfg_path, bak)
            ys["total_time"] = a.target_strain
            ys["criteria"] = [c for c in ys.get("criteria", []) if not c["name"].startswith("alpha_avg_material_")]
            for c in ys["criteria"]:
                if c["name"] == "alpha_avg_material":
                    c["threshold"] = 0.05          # praktisch unerreichbar -> alle Punkte laufen bis target_strain
                    c["blocking"] = True
                    c["comment"] = (f"Plateau-Lauf: Abbruch ueber total_time = {a.target_strain:g} (= Boxdehnung), "
                                    "alpha-Schwelle absichtlich unerreichbar, damit alle Richtungen dieselbe "
                                    "Enddehnung erreichen (10.09.2026)")
                else:
                    c["blocking"] = False
            for lvl in doc_levels:
                ys["criteria"].append({"name": f"alpha_avg_material_{lvl:g}", "quantity": "alpha_avg_reduced_material_volume",
                                       "threshold": lvl, "blocking": False,
                                       "comment": "Doku-Stufe (Ereignis + Feld-Snapshot, kein Abbruch)"})
            ys.setdefault("history", []).append(
                {"date": "2026-09-10", "change": f"Plateau-Fortsetzung: total_time={a.target_strain}, "
                                                 f"alpha-Abbruch deaktiviert, Doku-Stufen {doc_levels} "
                                                 f"(prepare_plateau_subset.py, Fortsetzung ab {reached:.4f})"})
            json.dump(cfg, open(cfg_path, "w"), indent=2)
        jobs.append(job)

if a.apply:
    open(a.job_list, "w").write("\n".join(jobs) + ("\n" if jobs else ""))
print(f"\n{len(jobs)} Punkte vorbereitet{'' if a.apply else ' (DRY-RUN, nichts geaendert)'}"
      f"{', Jobliste: ' + a.job_list if a.apply else ''}")
if skipped:
    print(f"uebersprungen ({len(skipped)}):")
    for s in skipped[:20]: print("   ", s)
