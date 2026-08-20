#!/usr/bin/env python3
"""Sammelt die Ergebnisse aller Kombinationen in EIN Paket und zippt es.

Wird normalerweise ueber `batch_collect_results.sh` aufgerufen; das
Shell-Skript liest die Kombinationen aus config.sh und reicht sie hier als
--combo-Argumente herein. Nur Standardbibliothek, laeuft also direkt auf dem
Login-Node ohne Container.

Paketstruktur:

    <name>/
      README.md                 Kurzbeschreibung + Inhaltsverzeichnis
      summary.csv               je Kombination: erwartet / gefunden / gueltig
      yield_points_all.csv      alle Punkte aller Kombinationen, alle Kriterien
      <combo_id>/
        config.json             Config der Kombination
        manifest.csv            Richtungen des Samplings
        parameters.txt          aufgeloeste Solver-Parameter
        yield_points.csv        nur diese Kombination
        points/<sample>__yield_run_*.json
        mesh/                   Qualitaets- und Topologiereports des Netzes
        averages/               optional (--with-averages), Zeitreihen je Punkt
        logs/                   optional (--with-logs), SLURM .out/.err
"""

import argparse
import csv
import json
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

SAMPLE_RE = re.compile(r"^ys_\d{3}_")

# Reihenfolge der Kriterien in der CSV; "final" ist der Zustand, den
# primary_criterion gefuellt hat (das, was collect_yield_surface_points.py sieht).
CRITERION_ORDER = ["final", "eps_p_eq_macroscopic", "alpha_avg_material",
                   "yielded_fraction_material", "yielded_fraction_rve"]

CSV_FIELDS = [
    "combo_id", "dataset", "sig_y", "run_id", "binning_label",
    "sample_id", "sample_index", "criterion", "quantity", "threshold", "value",
    "stop_reason", "criteria_reached", "criteria_missed",
    "target_eps_1", "target_eps_2", "target_eps_3",
    "eps_1", "eps_2", "eps_3", "strain_scale", "t",
    "sigma_xx", "sigma_yy", "sigma_zz", "sigma_yz", "sigma_xz", "sigma_xy",
    "sig_vm_avg_reduced_volume",
    "eps_p_eq_macroscopic", "alpha_avg_reduced_material_volume",
    "yielded_fraction_reduced_material_volume", "yielded_fraction_reduced_volume",
    "reaction_force_x", "reaction_force_y", "reaction_force_z",
    "reduced_volume_box", "reduced_volume_material", "relative_density",
    "source_file",
]


def sample_id_from(path, root):
    """Letztes ys_NNN_*-Verzeichnis im Pfad.

    Unter 00_results steht der Sample-Name zweimal im Pfad:
    <sample>-<material>-<richtung>/<sample>/<subvolume>/. Der zweite, also der
    letzte Treffer, ist der reine sample_id ohne den Material-Suffix.
    """
    hit = None
    for part in path.relative_to(root).parts:
        if SAMPLE_RE.match(part):
            hit = part
    return hit or path.parent.name


def tensor_components(value):
    """3x3-Liste -> (xx, yy, zz, yz, xz, xy); alles andere -> Nones."""
    try:
        m = [[float(value[i][j]) for j in range(3)] for i in range(3)]
    except Exception:
        return (None,) * 6
    return (m[0][0], m[1][1], m[2][2], m[1][2], m[0][2], m[0][1])


def rows_from_summary(data, meta, sample_id, sample_index, source):
    """Eine Zeile je Fliesskriterium plus eine Zeile 'final'."""
    states = dict(data.get("yield_states") or {})
    if data.get("final_yield_state"):
        states["final"] = data["final_yield_state"]

    vol_box = data.get("reduced_volume_box")
    vol_mat = data.get("reduced_volume_material")
    rel_dens = (vol_mat / vol_box) if (vol_box and vol_mat) else None
    target = data.get("eps_mac_eigenvalues_target") or [None, None, None]

    ordered = [n for n in CRITERION_ORDER if n in states]
    ordered += [n for n in states if n not in ordered]

    rows = []
    for name in ordered:
        state = states[name] or {}
        eps = state.get("eps_mac_eigenvalues_current") or [None, None, None]
        sxx, syy, szz, syz, sxz, sxy = tensor_components(state.get("sigma_avg_reduced_volume"))
        rf = state.get("reaction_force") or [None, None, None]
        rows.append({
            "combo_id": meta["combo_id"], "dataset": meta["dataset"],
            "sig_y": data.get("sig_y", meta["sig_y"]),
            "run_id": meta["run_id"], "binning_label": meta["binning_label"],
            "sample_id": sample_id, "sample_index": sample_index,
            "criterion": name,
            "quantity": state.get("quantity"),
            "threshold": state.get("threshold"),
            "value": state.get("value"),
            "stop_reason": data.get("stop_reason"),
            "criteria_reached": ";".join(data.get("criteria_reached") or []),
            "criteria_missed": ";".join(data.get("criteria_missed") or []),
            "target_eps_1": target[0], "target_eps_2": target[1], "target_eps_3": target[2],
            "eps_1": eps[0], "eps_2": eps[1], "eps_3": eps[2],
            "strain_scale": state.get("strain_scale"), "t": state.get("t"),
            "sigma_xx": sxx, "sigma_yy": syy, "sigma_zz": szz,
            "sigma_yz": syz, "sigma_xz": sxz, "sigma_xy": sxy,
            "sig_vm_avg_reduced_volume": state.get("sig_vm_avg_reduced_volume"),
            "eps_p_eq_macroscopic": state.get("eps_p_eq_macroscopic"),
            "alpha_avg_reduced_material_volume": state.get("alpha_avg_reduced_material_volume"),
            "yielded_fraction_reduced_material_volume": state.get("yielded_fraction_reduced_material_volume"),
            "yielded_fraction_reduced_volume": state.get("yielded_fraction_reduced_volume"),
            "reaction_force_x": rf[0], "reaction_force_y": rf[1], "reaction_force_z": rf[2],
            "reduced_volume_box": vol_box, "reduced_volume_material": vol_mat,
            "relative_density": rel_dens,
            "source_file": source,
        })
    return rows


def read_manifest(jobs_dir):
    path = jobs_dir / "manifest.csv"
    index = {}
    if path.is_file():
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                index[row["sample_id"]] = row
    return index


def collect_combo(project, pkg, meta, args):
    combo_dir = pkg / meta["combo_id"]
    points_dir = combo_dir / "points"
    points_dir.mkdir(parents=True, exist_ok=True)

    results_root = project / "00_results" / meta["run_id"] / meta["binning_label"]
    runs_root = project / "yield_surface_runs" / meta["run_id"] / meta["binning_label"]
    jobs_dir = project / meta["jobs_dir"]
    manifest = read_manifest(jobs_dir)

    # Ergebnisdateien einsammeln; 00_results hat Vorrang vor dem Arbeitsordner.
    found = {}
    for root in (results_root, runs_root):
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("yield_run_*.json")):
            sample = sample_id_from(path, root)
            found.setdefault((sample, path.name), path)

    rows, n_final, n_broken = [], 0, 0
    for (sample, filename), path in sorted(found.items()):
        try:
            with path.open() as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            print(f"  [WARNUNG] unlesbar: {path} ({exc})")
            n_broken += 1
            continue
        target = points_dir / f"{sample}__{filename}"
        shutil.copy2(path, target)
        if data.get("final_yield_state"):
            n_final += 1
        entry = manifest.get(sample, {})
        rows.extend(rows_from_summary(
            data, meta, sample, entry.get("sample_index"),
            str(path.relative_to(project))))

        if args.with_averages:
            averages = path.with_name(path.name.replace("yield_run_", "yield_averages_"))
            if averages.is_file():
                (combo_dir / "averages").mkdir(exist_ok=True)
                shutil.copy2(averages, combo_dir / "averages" / f"{sample}__{averages.name}")

    # Config, Manifest, ein Parameterreport
    config_src = project / meta["config"]
    if config_src.is_file():
        shutil.copy2(config_src, combo_dir / "config.json")
    if (jobs_dir / "manifest.csv").is_file():
        shutil.copy2(jobs_dir / "manifest.csv", combo_dir / "manifest.csv")
    for candidate in sorted(jobs_dir.glob("ys_*/parameters.txt")):
        shutil.copy2(candidate, combo_dir / "parameters.txt")
        break

    # Netzreports des Datensatzes (klein, aber fuer die Bewertung wichtig)
    mesh_dir = combo_dir / "mesh"
    segmented = project / f"{meta['run_id']}_segmented"
    if segmented.is_dir():
        for pattern in ("metadata.json", "**/*.quality.txt", "**/*.topology.txt",
                        "**/volume_topology.txt", "**/volume_cuboid.txt",
                        "**/*.sidecar.json"):
            for path in sorted(segmented.glob(pattern)):
                if path.is_file() and path.stat().st_size < 5_000_000:
                    mesh_dir.mkdir(exist_ok=True)
                    rel = path.relative_to(segmented).as_posix().replace("/", "__")
                    shutil.copy2(path, mesh_dir / rel)

    if args.with_logs:
        logs_dir = combo_dir / "logs"
        for path in sorted(jobs_dir.glob("ys_*/*.out.*")) + sorted(jobs_dir.glob("ys_*/*.err.*")):
            if path.stat().st_size > args.max_log_bytes:
                continue
            logs_dir.mkdir(exist_ok=True)
            shutil.copy2(path, logs_dir / f"{path.parent.name}__{path.name}")

    with (combo_dir / "yield_points.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    expected = len(manifest) or args.expected_points
    print(f"  {meta['combo_id']:<24} JSONs {len(found):>4} / erwartet {expected:>4}"
          f"   mit final_yield_state {n_final:>4}")
    return rows, {
        "combo_id": meta["combo_id"], "dataset": meta["dataset"], "sig_y": meta["sig_y"],
        "run_id": meta["run_id"], "binning_label": meta["binning_label"],
        "expected_points": expected, "result_files": len(found),
        "with_final_yield_state": n_final,
        "missing": max(0, expected - len(found)), "unreadable": n_broken,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--combo", action="append", default=[],
                        metavar="ds|sig|run_id|label|combo_id|config|jobs_dir",
                        help="Wird von batch_collect_results.sh gesetzt.")
    parser.add_argument("--output-dir", default=None,
                        help="Default: <projekt>/00_results/_packages")
    parser.add_argument("--name", default=None,
                        help="Name des Pakets (Default: results_<datum>)")
    parser.add_argument("--expected-points", type=int, default=0)
    parser.add_argument("--with-averages", action="store_true",
                        help="yield_averages_*.json (Zeitreihen) mitnehmen - deutlich groesser")
    parser.add_argument("--with-logs", action="store_true", help="SLURM .out/.err mitnehmen")
    parser.add_argument("--max-log-bytes", type=int, default=2_000_000)
    parser.add_argument("--per-combo-zip", action="store_true",
                        help="ein Zip je Kombination statt eines grossen")
    parser.add_argument("--no-zip", action="store_true", help="nur den Ordner erzeugen")
    args = parser.parse_args()

    project = Path(args.project_dir).resolve() if args.project_dir else Path(__file__).resolve().parent
    out_root = Path(args.output_dir) if args.output_dir else project / "00_results" / "_packages"
    name = args.name or f"results_{datetime.now():%Y%m%d-%H%M}"
    pkg = out_root / name
    pkg.mkdir(parents=True, exist_ok=True)

    metas = []
    for spec in args.combo:
        parts = spec.split("|")
        if len(parts) != 7:
            raise SystemExit(f"--combo braucht 7 Felder, bekam: {spec!r}")
        ds, sig, run_id, label, combo_id, config, jobs_dir = parts
        metas.append({"dataset": ds, "sig_y": sig, "run_id": run_id,
                      "binning_label": label, "combo_id": combo_id,
                      "config": config, "jobs_dir": jobs_dir})
    if not metas:
        raise SystemExit("Keine Kombinationen uebergeben (--combo).")

    print(f"Projekt: {project}")
    print(f"Paket  : {pkg}")
    all_rows, summary = [], []
    for meta in metas:
        rows, stats = collect_combo(project, pkg, meta, args)
        all_rows.extend(rows)
        summary.append(stats)

    with (pkg / "yield_points_all.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)

    summary_fields = list(summary[0].keys())
    with (pkg / "summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(summary)

    readme = [
        f"# Fliessflaechen-Ergebnisse {name}",
        "",
        f"Erzeugt am {datetime.now():%d.%m.%Y %H:%M} aus `{project}`.",
        "",
        "## Inhalt",
        "",
        "| Datei | Inhalt |",
        "|---|---|",
        "| `summary.csv` | je Kombination: erwartete Punkte, gefundene Ergebnis-JSONs, davon mit `final_yield_state` |",
        "| `yield_points_all.csv` | alle Fliessflaechenpunkte aller Kombinationen; **eine Zeile je Kriterium** (`criterion`-Spalte) |",
        "| `<combo>/yield_points.csv` | dasselbe, nur diese Kombination |",
        "| `<combo>/points/` | die unveraenderten `yield_run_*.json` |",
        "| `<combo>/config.json` | Config der Kombination (enthaelt sig_y, Kriterien, Netzparameter) |",
        "| `<combo>/manifest.csv` | die gesampelten Belastungsrichtungen |",
        "| `<combo>/mesh/` | Qualitaets- und Topologiereports des vorbereiteten Netzes |",
        "",
        "`criterion = final` ist der Zustand, den `primary_criterion` gefuellt hat -",
        "das ist die Zeile, die der bisherigen Auswertung (`collect_yield_surface_points.py`)",
        "entspricht. Die anderen Zeilen sind die uebrigen Fliesskriterien aus demselben Lauf.",
        "",
        "## Uebersicht",
        "",
        "| Kombination | Datensatz | sig_y | erwartet | gefunden | gueltig |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for stats in summary:
        readme.append(f"| {stats['combo_id']} | {stats['dataset']} | {stats['sig_y']} | "
                      f"{stats['expected_points']} | {stats['result_files']} | "
                      f"{stats['with_final_yield_state']} |")
    (pkg / "README.md").write_text("\n".join(readme) + "\n")

    print()
    print(f"Punkte gesamt (Zeilen in yield_points_all.csv): {len(all_rows)}")

    if args.no_zip:
        print(f"Paketordner: {pkg}")
        return

    def zip_dir(source, archive):
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for path in sorted(source.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(source.parent).as_posix())
        return archive.stat().st_size

    if args.per_combo_zip:
        for meta in metas:
            combo_dir = pkg / meta["combo_id"]
            if not combo_dir.is_dir():
                continue
            archive = out_root / f"{name}__{meta['combo_id']}.zip"
            size = zip_dir(combo_dir, archive)
            print(f"{archive}  ({size / 1e6:.1f} MB)")
        for extra in ("summary.csv", "yield_points_all.csv", "README.md"):
            shutil.copy2(pkg / extra, out_root / f"{name}__{extra}")
    else:
        archive = out_root / f"{name}.zip"
        size = zip_dir(pkg, archive)
        print(f"{archive}  ({size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
