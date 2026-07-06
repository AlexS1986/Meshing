#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage


CASE_RE = re.compile(r"^(.+)_Bin(?P<bin>[0-9]+)_reduce-(?P<reduce>[^_]+)_segmented$")


def configure_matplotlib(output_dir):
    cache_dir = output_dir / ".matplotlib"
    xdg_cache_dir = output_dir / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    xdg_cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_dir))
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ.setdefault("XDG_CACHE_HOME", str(xdg_cache_dir))
    import matplotlib.pyplot as plt

    return plt


def reduce_to_number(value):
    return 1.0 if value == "null" else float(value)


def reduce_priority(value):
    if value == "null":
        return 0.0
    return float(value)


def voxel_volume_to_diameter(voxel_counts, voxel_size_um):
    voxel_volume_um3 = voxel_size_um ** 3
    return 2.0 * ((3.0 * voxel_counts * voxel_volume_um3) / (4.0 * np.pi)) ** (1.0 / 3.0)


def load_json(path):
    if not path.exists():
        return {}
    with path.open("r") as handle:
        return json.load(handle)


def case_config(case_dir, search_roots, bin_value, reduce_value):
    config_name = f"config-Bin{bin_value}-reduce-{reduce_value}.json"
    candidates = [case_dir / config_name]
    candidates.extend(root / config_name for root in search_roots)
    for config_path in candidates:
        if config_path.exists():
            return load_json(config_path), config_path
    return {}, candidates[0]


def discover_cases(results_dir):
    case_roots = []
    if (results_dir / "cases").is_dir():
        case_roots.append(results_dir / "cases")
    case_roots.append(results_dir)

    rows = []
    seen = set()
    for case_root in case_roots:
        if not case_root.is_dir():
            continue
        for case_dir in sorted(path for path in case_root.iterdir() if path.is_dir()):
            match = CASE_RE.match(case_dir.name)
            if not match or case_dir.name in seen:
                continue
            volume_files = sorted(case_dir.glob("*_3D/subvolume_*/volume.npy"))
            if not volume_files:
                continue
            bin_value = int(match.group("bin"))
            reduce_value = match.group("reduce")
            config, config_path = case_config(
                case_dir,
                search_roots=[case_root, case_root.parent, results_dir],
                bin_value=bin_value,
                reduce_value=reduce_value,
            )
            rows.append(
                {
                    "case_name": case_dir.name,
                    "case_dir": case_dir,
                    "bin": bin_value,
                    "reduce": reduce_value,
                    "reduce_numeric": reduce_to_number(reduce_value),
                    "volume_path": volume_files[0],
                    "config": config,
                    "config_path": config_path,
                }
            )
            seen.add(case_dir.name)
    return sorted(rows, key=lambda row: (row["bin"], reduce_priority(row["reduce"])), reverse=True)


def connectivity_structure(connectivity):
    if connectivity == 6:
        return ndimage.generate_binary_structure(3, 1)
    if connectivity == 18:
        structure = ndimage.generate_binary_structure(3, 2)
        structure[0, 0, 0] = False
        structure[0, 0, 2] = False
        structure[0, 2, 0] = False
        structure[0, 2, 2] = False
        structure[2, 0, 0] = False
        structure[2, 0, 2] = False
        structure[2, 2, 0] = False
        structure[2, 2, 2] = False
        return structure
    if connectivity == 26:
        return ndimage.generate_binary_structure(3, 3)
    raise ValueError("Connectivity must be one of 6, 18, or 26.")


def boundary_labels(labels):
    faces = [
        labels[0, :, :],
        labels[-1, :, :],
        labels[:, 0, :],
        labels[:, -1, :],
        labels[:, :, 0],
        labels[:, :, -1],
    ]
    ids = np.unique(np.concatenate([face.ravel() for face in faces]))
    return ids[ids != 0]


def parallel_snow_partitioning(pore_mask, max_volume=1_000_000, cores=None):
    try:
        import porespy
        from porespy.filters import snow_partitioning_parallel
    except ImportError as exc:
        raise RuntimeError(
            "The Porenanalyse pore-data method requires porespy. "
            "Install/use an environment with porespy, or run with --method connected-components."
        ) from exc

    import inspect
    import math

    porespy.settings.tqdm["disable"] = True
    if max_volume < 10_000:
        raise ValueError("max_volume must be at least 10000.")

    depth, height, width = pore_mask.shape
    total_volume = depth * height * width
    total_chunks = math.ceil(total_volume / max_volume)
    side = total_chunks ** (1.0 / 3.0)
    scale = np.array([depth, height, width]) / (total_volume ** (1.0 / 3.0))
    axis_splits = side * scale
    divs = np.ceil(axis_splits).astype(int).tolist()

    if "parallel_kw" in inspect.signature(snow_partitioning_parallel).parameters:
        parallel_kw = {"divs": divs, "overlap": 4}
        if cores is not None:
            parallel_kw["cores"] = cores
        result = snow_partitioning_parallel(pore_mask, parallel_kw=parallel_kw)
    else:
        result = snow_partitioning_parallel(pore_mask, divs=divs, overlap=4, cores=cores)
    return result.regions


def pore_data_from_porespy(volume_path, pore_value, max_volume, cores):
    from skimage.measure import regionprops

    volume = np.load(volume_path)
    pore_mask = volume == pore_value
    regions = parallel_snow_partitioning(pore_mask, max_volume=max_volume, cores=cores)
    properties = regionprops(regions)

    pore_rows = []
    for prop in properties:
        z_cent, y_cent, x_cent = prop.centroid
        pore_rows.append([prop.label, int(prop.area), 0, int(x_cent), int(y_cent), int(z_cent)])

    pore_rows = np.asarray(pore_rows, dtype=np.int64)
    return pore_rows, {
        "volume_shape": "x".join(map(str, volume.shape)),
        "all_pore_components": len(pore_rows),
        "excluded_boundary_components": 0,
        "kept_pore_components": len(pore_rows),
    }


def pore_data_from_connected_components(volume_path, pore_value, connectivity, exclude_boundary_connected):
    volume = np.load(volume_path)
    pore_mask = volume == pore_value
    labels, pore_count = ndimage.label(pore_mask, structure=connectivity_structure(connectivity))
    sizes = np.bincount(labels.ravel(), minlength=pore_count + 1)[1:].astype(np.int64)
    kept_labels = np.arange(1, pore_count + 1, dtype=np.int64)

    excluded_count = 0
    if exclude_boundary_connected and pore_count:
        boundary_ids = boundary_labels(labels)
        excluded_count = len(boundary_ids)
        if excluded_count:
            keep = np.ones(len(sizes), dtype=bool)
            keep[boundary_ids - 1] = False
            sizes = sizes[keep]
            kept_labels = kept_labels[keep]

    objects = ndimage.find_objects(labels)
    pore_rows = []
    for label, size in zip(kept_labels, sizes):
        slices = objects[label - 1]
        if slices is None:
            continue
        coords = np.argwhere(labels[slices] == label)
        centroid_local = coords.mean(axis=0)
        z_cent = centroid_local[0] + slices[0].start
        y_cent = centroid_local[1] + slices[1].start
        x_cent = centroid_local[2] + slices[2].start
        pore_rows.append([label, int(size), 0, int(x_cent), int(y_cent), int(z_cent)])

    return np.asarray(pore_rows, dtype=np.int64), {
        "volume_shape": "x".join(map(str, volume.shape)),
        "all_pore_components": pore_count,
        "excluded_boundary_components": excluded_count,
        "kept_pore_components": len(pore_rows),
    }


def write_pore_data(path, pore_rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    header = "Region_Label Pore_Size / X_Coord Y_Coord Z_Coord"
    if len(pore_rows) == 0:
        path.write_text(f"# {header}\n")
        return
    np.savetxt(path, pore_rows, fmt="%d %d %d %d %d %d", header=header)


def summary_stats(values):
    if len(values) == 0:
        return {
            "count": 0,
            "mean": "",
            "median": "",
            "std": "",
            "min": "",
            "max": "",
        }
    return {
        "count": len(values),
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "std": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }


def plot_histogram(values, output_path, title, xlabel, bins, log_x, plt):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 6), constrained_layout=True)

    values = np.asarray(values)
    values = values[values > 0]
    if len(values) == 0:
        ax.text(0.5, 0.5, "No pores", ha="center", va="center", transform=ax.transAxes)
    else:
        if log_x and values.min() > 0 and values.max() > values.min():
            bin_edges = np.logspace(np.log10(values.min()), np.log10(values.max()), bins)
            ax.set_xscale("log")
        else:
            bin_edges = bins
        ax.hist(values, bins=bin_edges, color="#8ecae6", edgecolor="#216f9b")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Number of pores")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.6)
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def fieldnames():
    return [
        "case_name",
        "bin",
        "reduce",
        "reduce_numeric",
        "effective_binning_factor",
        "voxel_size_um",
        "pore_value",
        "method",
        "connectivity",
        "boundary_connected_excluded",
        "status",
        "returncode",
        "volume_shape",
        "all_pore_components",
        "excluded_boundary_components",
        "kept_pore_components",
        "pore_size_voxels_mean",
        "pore_size_voxels_median",
        "pore_size_voxels_std",
        "pore_size_voxels_min",
        "pore_size_voxels_max",
        "pore_diameter_um_mean",
        "pore_diameter_um_median",
        "pore_diameter_um_std",
        "pore_diameter_um_min",
        "pore_diameter_um_max",
        "volume_path",
        "pore_data_path",
        "error",
    ]


def write_summary(rows, summary_path):
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames())
        writer.writeheader()
        writer.writerows(rows)


def process_case(case, args):
    plt = configure_matplotlib(args.output_dir / "plots")
    config = case["config"]
    binning_config = config.get("binning", {})
    effective_binning = binning_config.get("effective_binning_factor") or case["bin"] * case["reduce_numeric"]
    voxel_size_um = args.base_voxel_size_um * float(effective_binning)
    pore_value = config.get("02a_rotate_pic_to_align_with_axis", {}).get("pore_value", args.pore_value)

    print(f"Evaluating {case['case_name']} from {case['volume_path']}", flush=True)
    if args.method == "porespy":
        pore_rows, component_info = pore_data_from_porespy(
            case["volume_path"],
            pore_value=pore_value,
            max_volume=args.porespy_max_volume,
            cores=args.porespy_cores,
        )
    else:
        pore_rows, component_info = pore_data_from_connected_components(
            case["volume_path"],
            pore_value=pore_value,
            connectivity=args.connectivity,
            exclude_boundary_connected=args.exclude_boundary_connected,
        )
    pore_sizes_voxels = pore_rows[:, 1] if len(pore_rows) else np.asarray([], dtype=np.int64)
    pore_diameters_um = voxel_volume_to_diameter(pore_sizes_voxels, voxel_size_um)

    case_output_dir = args.output_dir / "cases" / case["case_name"]
    pore_data_path = case_output_dir / "Pore_Data.txt"
    write_pore_data(pore_data_path, pore_rows)

    voxel_stats = summary_stats(pore_sizes_voxels)
    diameter_stats = summary_stats(pore_diameters_um)
    row = {
        "case_name": case["case_name"],
        "bin": case["bin"],
        "reduce": case["reduce"],
        "reduce_numeric": case["reduce_numeric"],
        "effective_binning_factor": effective_binning,
        "voxel_size_um": voxel_size_um,
        "pore_value": pore_value,
        "method": args.method,
        "connectivity": args.connectivity,
        "boundary_connected_excluded": args.exclude_boundary_connected if args.method == "connected-components" else False,
        "status": "ok",
        "returncode": 0,
        "volume_path": str(case["volume_path"]),
        "pore_data_path": str(pore_data_path),
        "error": "",
        **component_info,
        "pore_size_voxels_mean": voxel_stats["mean"],
        "pore_size_voxels_median": voxel_stats["median"],
        "pore_size_voxels_std": voxel_stats["std"],
        "pore_size_voxels_min": voxel_stats["min"],
        "pore_size_voxels_max": voxel_stats["max"],
        "pore_diameter_um_mean": diameter_stats["mean"],
        "pore_diameter_um_median": diameter_stats["median"],
        "pore_diameter_um_std": diameter_stats["std"],
        "pore_diameter_um_min": diameter_stats["min"],
        "pore_diameter_um_max": diameter_stats["max"],
    }

    if case["reduce"] == "null":
        plot_histogram(
            pore_diameters_um,
            args.output_dir / "plots" / f"{case['case_name']}_pore_diameter_histogram.png",
            title=f"{case['case_name']} pore size distribution",
            xlabel="Effective pore diameter (um)",
            bins=args.bins,
            log_x=not args.linear_x,
            plt=plt,
        )
    return row


def single_case_output_path(output_dir, case_name):
    return output_dir / "case_rows" / f"{case_name}.json"


def run_case_subprocess(case, args):
    row_path = single_case_output_path(args.output_dir, case["case_name"])
    row_path.parent.mkdir(parents=True, exist_ok=True)
    if row_path.exists():
        row_path.unlink()

    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--single-case",
        case["case_name"],
        "--results-dir",
        str(args.results_dir),
        "--output-dir",
        str(args.output_dir),
        "--base-voxel-size-um",
        str(args.base_voxel_size_um),
        "--method",
        args.method,
        "--porespy-max-volume",
        str(args.porespy_max_volume),
        "--connectivity",
        str(args.connectivity),
        "--bins",
        str(args.bins),
    ]
    if args.porespy_cores is not None:
        cmd.extend(["--porespy-cores", str(args.porespy_cores)])
    if args.exclude_boundary_connected:
        cmd.append("--exclude-boundary-connected")
    if args.include_bin1_reduce_null:
        cmd.append("--include-bin1-reduce-null")
    if args.linear_x:
        cmd.append("--linear-x")

    result = subprocess.run(cmd)
    if result.returncode == 0 and row_path.exists():
        with row_path.open("r") as handle:
            return json.load(handle)

    return {
        "case_name": case["case_name"],
        "bin": case["bin"],
        "reduce": case["reduce"],
        "reduce_numeric": case["reduce_numeric"],
        "effective_binning_factor": "",
        "voxel_size_um": "",
        "pore_value": "",
        "method": args.method,
        "connectivity": args.connectivity,
        "boundary_connected_excluded": args.exclude_boundary_connected if args.method == "connected-components" else False,
        "status": "failed",
        "returncode": result.returncode,
        "volume_shape": "",
        "all_pore_components": "",
        "excluded_boundary_components": "",
        "kept_pore_components": "",
        "pore_size_voxels_mean": "",
        "pore_size_voxels_median": "",
        "pore_size_voxels_std": "",
        "pore_size_voxels_min": "",
        "pore_size_voxels_max": "",
        "pore_diameter_um_mean": "",
        "pore_diameter_um_median": "",
        "pore_diameter_um_std": "",
        "pore_diameter_um_min": "",
        "pore_diameter_um_max": "",
        "volume_path": str(case["volume_path"]),
        "pore_data_path": str(args.output_dir / "cases" / case["case_name"] / "Pore_Data.txt"),
        "error": f"case subprocess exited with return code {result.returncode}",
    }


def main():
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Compute pore-size distributions from downloaded volume.npy files.")
    parser.add_argument("--results-dir", type=Path, default=script_dir / "results")
    parser.add_argument("--output-dir", type=Path, default=script_dir / "results" / "pore_size_distribution")
    parser.add_argument("--base-voxel-size-um", type=float, default=60.4)
    parser.add_argument("--method", choices=["porespy", "connected-components"], default="porespy")
    parser.add_argument("--porespy-max-volume", type=int, default=1_000_000)
    parser.add_argument("--porespy-cores", type=int, default=None)
    parser.add_argument("--connectivity", type=int, default=26, choices=[6, 18, 26])
    parser.add_argument("--pore-value", type=int, default=0)
    parser.add_argument("--exclude-boundary-connected", action="store_true")
    parser.add_argument("--include-bin1-reduce-null", action="store_true")
    parser.add_argument("--bins", type=int, default=50)
    parser.add_argument("--linear-x", action="store_true")
    parser.add_argument("--only-case", help="Evaluate only this case name while preserving subprocess isolation.")
    parser.add_argument("--single-case", help=argparse.SUPPRESS)
    parser.add_argument("--no-subprocess", action="store_true", help="Process all cases in this interpreter.")
    args = parser.parse_args()

    cases = discover_cases(args.results_dir)
    if not cases:
        raise SystemExit(f"No volume.npy files found below {args.results_dir}")

    if args.only_case:
        cases = [case for case in cases if case["case_name"] == args.only_case]
        if not cases:
            raise SystemExit(f"Case not found: {args.only_case}")

    if args.single_case:
        matches = [case for case in cases if case["case_name"] == args.single_case]
        if not matches:
            raise SystemExit(f"Case not found: {args.single_case}")
        case = matches[0]
        if case["bin"] == 1 and case["reduce"] == "null" and not args.include_bin1_reduce_null:
            print(f"Skipping {case['case_name']} (Bin1 reduce-null)", flush=True)
            return
        row = process_case(case, args)
        row_path = single_case_output_path(args.output_dir, case["case_name"])
        row_path.parent.mkdir(parents=True, exist_ok=True)
        with row_path.open("w") as handle:
            json.dump(row, handle, indent=2)
        write_summary([row], args.output_dir / "case_summaries" / f"{case['case_name']}.csv")
        return

    rows = []
    for case in cases:
        if case["bin"] == 1 and case["reduce"] == "null" and not args.include_bin1_reduce_null:
            print(f"Skipping {case['case_name']} (Bin1 reduce-null)", flush=True)
            continue

        row = process_case(case, args) if args.no_subprocess else run_case_subprocess(case, args)
        rows.append(row)

    summary_path = args.output_dir / "pore_size_summary.csv"
    write_summary(rows, summary_path)

    print(f"Wrote {len(rows)} rows to {summary_path}")
    print(f"Wrote reduce-null histograms to {args.output_dir / 'plots'}")


if __name__ == "__main__":
    main()
