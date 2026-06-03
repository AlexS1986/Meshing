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
        row["total_reduce_factor"] = row["bin"] * row["reduce_numeric"]
        row.update(moduli)
        row.update(volume)
        rows.append(row)

    return sorted(rows, key=lambda row: (row["total_reduce_factor"], row["bin"], row["reduce_numeric"]))


def write_csv(rows, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "case_name",
        "bin",
        "reduce",
        "reduce_numeric",
        "total_reduce_factor",
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
    plt.rcParams.update(
        {
            "font.size": 18,
            "axes.labelsize": 22,
            "axes.titlesize": 22,
            "xtick.labelsize": 18,
            "ytick.labelsize": 18,
            "legend.fontsize": 18,
            "legend.title_fontsize": 19,
        }
    )
    return plt


def plot_quantity(rows, quantity, ylabel, output_path, plt, x_key="reduce_numeric", xlabel="FEM reduce"):
    plot_rows = [row for row in rows if isinstance(row.get(quantity), (int, float))]
    if not plot_rows:
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9.0, 6.0), constrained_layout=True)
    markers = {
        1: "o",
        2: "s",
        4: "^",
    }

    for bin_value in sorted({row["bin"] for row in plot_rows}):
        subset = [row for row in plot_rows if row["bin"] == bin_value]
        ax.scatter(
            [row[x_key] for row in subset],
            [row[quantity] for row in subset],
            marker=markers.get(bin_value, "D"),
            s=120,
            label=f"Bin {bin_value}",
        )

    tick_values = sorted({row[x_key] for row in plot_rows})
    tick_labels = []
    for value in tick_values:
        has_null = x_key == "reduce_numeric" and any(
            row["reduce"] == "null" and row[x_key] == value for row in plot_rows
        )
        tick_labels.append("null/1" if has_null else f"{value:g}")

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xticks(tick_values)
    ax.set_xticklabels(tick_labels)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(title="Binning", markerscale=1.2)

    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    return True


def plot_min_max_e(rows, output_path, plt, x_key="reduce_numeric", xlabel="FEM reduce"):
    plot_rows = [
        row
        for row in rows
        if isinstance(row.get("Emax"), (int, float)) and isinstance(row.get("Emin"), (int, float))
    ]
    if not plot_rows:
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9.0, 6.0), constrained_layout=True)
    colors = {
        1: "#1f77b4",
        2: "#ff7f0e",
        4: "#2ca02c",
    }
    marker_specs = [
        ("Emax", "E max", "^"),
        ("Emin", "E min", "v"),
    ]

    for bin_value in sorted({row["bin"] for row in plot_rows}):
        subset = [row for row in plot_rows if row["bin"] == bin_value]
        color = colors.get(bin_value)
        for quantity, label, marker in marker_specs:
            ax.scatter(
                [row[x_key] for row in subset],
                [row[quantity] for row in subset],
                marker=marker,
                s=120,
                color=color,
                label=f"Bin {bin_value} {label}",
            )

    tick_values = sorted({row[x_key] for row in plot_rows})
    tick_labels = []
    for value in tick_values:
        has_null = x_key == "reduce_numeric" and any(
            row["reduce"] == "null" and row[x_key] == value for row in plot_rows
        )
        tick_labels.append("null/1" if has_null else f"{value:g}")

    ax.set_xlabel(xlabel)
    ax.set_ylabel("E min / E max")
    ax.set_xticks(tick_values)
    ax.set_xticklabels(tick_labels)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(title="Binning and E range", markerscale=1.2)

    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    return True


def plot_e_range(rows, output_path, plt, x_key="reduce_numeric", xlabel="FEM reduce"):
    plot_rows = [
        row
        for row in rows
        if isinstance(row.get("Emax"), (int, float)) and isinstance(row.get("Emin"), (int, float))
    ]
    if not plot_rows:
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9.0, 6.0), constrained_layout=True)
    colors = {
        1: "#1f77b4",
        2: "#ff7f0e",
        4: "#2ca02c",
    }
    markers = {
        1: "o",
        2: "s",
        4: "^",
    }

    for bin_value in sorted({row["bin"] for row in plot_rows}):
        subset = [row for row in plot_rows if row["bin"] == bin_value]
        x_values = [row[x_key] for row in subset]
        y_mid = [(row["Emax"] + row["Emin"]) / 2.0 for row in subset]
        y_lower = [mid - row["Emin"] for mid, row in zip(y_mid, subset)]
        y_upper = [row["Emax"] - mid for mid, row in zip(y_mid, subset)]
        ax.errorbar(
            x_values,
            y_mid,
            yerr=[y_lower, y_upper],
            fmt=markers.get(bin_value, "D"),
            color=colors.get(bin_value),
            markersize=11,
            capsize=8,
            capthick=2.0,
            elinewidth=2.4,
            linestyle="none",
            label=f"Bin {bin_value}",
        )

    tick_values = sorted({row[x_key] for row in plot_rows})
    tick_labels = []
    for value in tick_values:
        has_null = x_key == "reduce_numeric" and any(
            row["reduce"] == "null" and row[x_key] == value for row in plot_rows
        )
        tick_labels.append("null/1" if has_null else f"{value:g}")

    ax.set_xlabel(xlabel)
    ax.set_ylabel("E range (E min to E max)")
    ax.set_xticks(tick_values)
    ax.set_xticklabels(tick_labels)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(title="Binning", markerscale=1.2)

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
        total_output_path = output_dir / f"{file_stem}_vs_total_reduce_factor.png"
        if plot_quantity(
            rows,
            quantity,
            ylabel,
            total_output_path,
            plt,
            x_key="total_reduce_factor",
            xlabel="Total FEM reduce (Binning x FEM reduce)",
        ):
            written.append(total_output_path)
    if plot_min_max_e(rows, output_dir / "E_min_max_vs_reduce.png", plt):
        written.append(output_dir / "E_min_max_vs_reduce.png")
    if plot_min_max_e(
        rows,
        output_dir / "E_min_max_vs_total_reduce_factor.png",
        plt,
        x_key="total_reduce_factor",
        xlabel="Total FEM reduce (Binning x FEM reduce)",
    ):
        written.append(output_dir / "E_min_max_vs_total_reduce_factor.png")
    if plot_e_range(rows, output_dir / "E_range_vs_reduce.png", plt):
        written.append(output_dir / "E_range_vs_reduce.png")
    if plot_e_range(
        rows,
        output_dir / "E_range_vs_total_reduce_factor.png",
        plt,
        x_key="total_reduce_factor",
        xlabel="Total FEM reduce (Binning x FEM reduce)",
    ):
        written.append(output_dir / "E_range_vs_total_reduce_factor.png")
    return written


def main():
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Plot elastic moduli and relative density versus FEM reduce factors.")
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
