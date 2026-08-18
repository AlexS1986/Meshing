#!/usr/bin/env python3
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def safe_float_label(value):
    if value is None:
        return "na"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "na"
    if abs(value) < 5e-13:
        value = 0.0
    return f"{value:+.6g}".replace("+", "p").replace("-", "m").replace(".", "p")


def safe_name(text):
    keep = []
    for char in str(text):
        if char.isalnum() or char in ("-", "_", "."):
            keep.append(char)
        else:
            keep.append("_")
    return "".join(keep).strip("_") or "unknown"


def infer_sample_id(path, data):
    config_path = data.get("config_path")
    if config_path:
        try:
            with open(config_path) as handle:
                config = json.load(handle)
            sample_id = config.get("yield_surface", {}).get("sample_id")
            if sample_id:
                return sample_id
        except OSError:
            pass

    for part in path.parts:
        if part.startswith("ys_"):
            return part
    return path.parent.name


def iter_summary_files(search_root, filename):
    yield from search_root.glob(f"00_results/**/{filename}")
    yield from search_root.glob(f"yield_surface_runs/**/{filename}")


def row_and_archive_name(path):
    with path.open() as handle:
        data = json.load(handle)

    final_state = data.get("final_yield_state") or {}
    current_eps = final_state.get("eps_mac_eigenvalues_current") or [None, None, None]
    target_eps = data.get("eps_mac_eigenvalues_target") or [None, None, None]
    sample_id = infer_sample_id(path, data)
    material = data.get("material") or "material"
    direction = data.get("loading_direction") or "direction"

    archive_name = (
        f"{safe_name(sample_id)}"
        f"__target_e1_{safe_float_label(target_eps[0])}"
        f"_e2_{safe_float_label(target_eps[1])}"
        f"_e3_{safe_float_label(target_eps[2])}"
        f"__yield_e1_{safe_float_label(current_eps[0])}"
        f"_e2_{safe_float_label(current_eps[1])}"
        f"_e3_{safe_float_label(current_eps[2])}"
        f"__{safe_name(material)}_{safe_name(direction)}.json"
    )

    row = {
        "archive_name": archive_name,
        "source_file": str(path),
        "sample_id": sample_id,
        "material": material,
        "loading_direction": direction,
        "stop_reason": data.get("stop_reason"),
        "target_eps_1": target_eps[0],
        "target_eps_2": target_eps[1],
        "target_eps_3": target_eps[2],
        "yield_eps_1": current_eps[0],
        "yield_eps_2": current_eps[1],
        "yield_eps_3": current_eps[2],
        "strain_scale": final_state.get("strain_scale"),
        "alpha_avg_reduced_material_volume": final_state.get("alpha_avg_reduced_material_volume"),
        "yielded_fraction_reduced_material_volume": final_state.get("yielded_fraction_reduced_material_volume"),
    }
    return row, archive_name


def main():
    parser = argparse.ArgumentParser(
        description="Package yield_run_<material>_<direction>.json summaries into a downloadable zip."
    )
    parser.add_argument("--project-dir", default=Path(__file__).resolve().parent)
    parser.add_argument("--material", default="std")
    parser.add_argument("--direction", default="tensor")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    filename = f"yield_run_{args.material}_{args.direction}.json"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = (
        Path(args.output).resolve()
        if args.output
        else project_dir / "00_results" / "downloads" / f"{filename[:-5]}_{timestamp}.zip"
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    seen = set()
    rows = []
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as zf:
        for path in sorted(iter_summary_files(project_dir, filename)):
            path = path.resolve()
            if path in seen:
                continue
            seen.add(path)
            row, archive_name = row_and_archive_name(path)
            rows.append(row)
            zf.write(path, archive_name)

        manifest_name = "manifest.csv"
        fieldnames = [
            "archive_name",
            "source_file",
            "sample_id",
            "material",
            "loading_direction",
            "stop_reason",
            "target_eps_1",
            "target_eps_2",
            "target_eps_3",
            "yield_eps_1",
            "yield_eps_2",
            "yield_eps_3",
            "strain_scale",
            "alpha_avg_reduced_material_volume",
            "yielded_fraction_reduced_material_volume",
        ]
        manifest_path = output.with_suffix(".manifest.csv")
        with manifest_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        zf.write(manifest_path, manifest_name)

    print(f"Packaged {len(rows)} files into: {output}")
    print(f"Manifest also written to: {manifest_path}")
    if rows:
        print("Download this zip from the cluster, for example with scp/rsync.")
    else:
        print(f"No {filename} files found below: {project_dir}")


if __name__ == "__main__":
    main()
