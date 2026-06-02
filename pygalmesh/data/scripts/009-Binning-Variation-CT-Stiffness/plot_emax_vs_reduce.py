#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
from pathlib import Path


CASE_RE = re.compile(r"^(.+)_Bin(?P<bin>[0-9]+)_reduce-(?P<reduce>[^_]+)_segmented$")


def reduce_to_number(value):
    if value == "null":
        return 1.0
    return float(value)


PLOT_SPECS = [
    ("E11", "E11", "E11"),
    ("E22", "E22", "E22"),
    ("E33", "E33", "E33"),
    ("Emax", "E_max", "Emax"),
    ("Emin", "E_min", "Emin"),
    ("vol_material_over_vol", "relative_density", "Relative density"),
]


def nested_value(data, key):
    value = data.get(key)
    if isinstance(value, dict) and "value" in value:
        return float(value["value"])
    if isinstance(value, (int, float)):
        return float(value)
    return None


def load_moduli(path):
    with path.open("r") as handle:
        data = json.load(handle)

    values = {
        "E11": nested_value(data, "E11"),
        "E22": nested_value(data, "E22"),
        "E33": nested_value(data, "E33"),
        "Emax": nested_value(data, "Emax"),
        "Emin": nested_value(data, "Emin"),
    }

    e_candidates = [values[key] for key in ("E11", "E22", "E33") if values[key] is not None]
    if values["Emax"] is None and e_candidates:
        values["Emax"] = max(e_candidates)
    if values["Emin"] is None and e_candidates:
        values["Emin"] = min(e_candidates)
    return values


def load_volume(path):
    if not path.exists():
        return {}
    with path.open("r") as handle:
        data = json.load(handle)

    values = {}
    for key in ("vol", "vol_material", "vol_overall", "vol_material_over_vol"):
        if isinstance(data.get(key), (int, float)):
            values[key] = float(data[key])
    return values


def collect_rows(results_dir):
    case_root = results_dir / "cases"
    rows = []

    for case_dir in sorted(path for path in case_root.iterdir() if path.is_dir()):
        match = CASE_RE.match(case_dir.name)
        if not match:
            continue

        e_files = sorted(case_dir.glob("*_3D/subvolume_*/E_moduli.json"))
        if not e_files:
            continue

        e_path = e_files[0]
        vol_path = e_path.with_name("vol.json")
        reduce_label = match.group("reduce")
        moduli = load_moduli(e_path)
        volume = load_volume(vol_path)
        row = {
            "case_name": case_dir.name,
            "bin": int(match.group("bin")),
            "reduce": reduce_label,
            "reduce_numeric": reduce_to_number(reduce_label),
            "E_moduli_json": str(e_path),
            "vol_json": str(vol_path) if vol_path.exists() else "",
        }
        row.update(moduli)
        row.update(volume)
        rows.append(row)

    return sorted(rows, key=lambda row: (row["bin"], row["reduce_numeric"]))


def write_csv(rows, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "case_name",
        "bin",
        "reduce",
        "reduce_numeric",
        "E11",
        "E22",
        "E33",
        "Emax",
        "Emin",
        "vol",
        "vol_material",
        "vol_overall",
        "vol_material_over_vol",
        "E_moduli_json",
        "vol_json",
    ]
    with output_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def configure_matplotlib(output_dir):
    cache_dir = output_dir / ".matplotlib"
    cache_dir.mkdir(parents=True, exist_ok=True)
    xdg_cache_dir = output_dir / ".cache"
    xdg_cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_dir))
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ.setdefault("XDG_CACHE_HOME", str(xdg_cache_dir))

    import matplotlib.pyplot as plt
    return plt


def plot_quantity(rows, quantity, ylabel, output_path, plt):
    plot_rows = [row for row in rows if isinstance(row.get(quantity), (int, float))]
    if not plot_rows:
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.0, 4.5), constrained_layout=True)
    markers = {
        1: "o",
        2: "s",
        4: "^",
    }

    for bin_value in sorted({row["bin"] for row in plot_rows}):
        subset = [row for row in plot_rows if row["bin"] == bin_value]
        ax.scatter(
            [row["reduce_numeric"] for row in subset],
            [row[quantity] for row in subset],
            marker=markers.get(bin_value, "D"),
            s=72,
            label=f"Bin {bin_value}",
        )

    tick_values = sorted({row["reduce_numeric"] for row in plot_rows})
    tick_labels = []
    for value in tick_values:
        has_null = any(row["reduce"] == "null" and row["reduce_numeric"] == value for row in plot_rows)
        tick_labels.append("null/1" if has_null else f"{value:g}")

    ax.set_xlabel("Reduce factor")
    ax.set_ylabel(ylabel)
    ax.set_xticks(tick_values)
    ax.set_xticklabels(tick_labels)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(title="Binning")

    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    return True


def plot_rows(rows, output_dir):
    plt = configure_matplotlib(output_dir)
    written = []
    for quantity, file_stem, ylabel in PLOT_SPECS:
        output_path = output_dir / f"{file_stem}_vs_reduce.png"
        if plot_quantity(rows, quantity, ylabel, output_path, plt):
            written.append(output_path)
    return written


def main():
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Plot elastic moduli and relative density versus reduce factor.")
    parser.add_argument("--results-dir", type=Path, default=script_dir / "results")
    parser.add_argument("--output-dir", type=Path, default=script_dir / "results" / "plots")
    parser.add_argument("--csv", type=Path, default=script_dir / "results" / "plots" / "moduli_and_density_vs_reduce.csv")
    args = parser.parse_args()

    rows = collect_rows(args.results_dir)
    if not rows:
        raise SystemExit(f"No E_moduli.json files found below {args.results_dir / 'cases'}")

    write_csv(rows, args.csv)
    plot_paths = plot_rows(rows, args.output_dir)

    print(f"Wrote {len(rows)} rows to {args.csv}")
    for path in plot_paths:
        print(f"Wrote plot to {path}")


if __name__ == "__main__":
    main()
