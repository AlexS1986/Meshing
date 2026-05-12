#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path


def load_json(path):
    if not path.exists():
        return {}
    with path.open("r") as handle:
        return json.load(handle)


def find_modulus(subvolume_path):
    e_moduli = load_json(subvolume_path / "E_moduli.json")
    for key in ("E33", "E22", "E11"):
        if key in e_moduli:
            return e_moduli.get(key)
    return None


def rows_from_metadata(project_dir, specimen_name, binning_id):
    label = f"Bin{binning_id}"
    run_name = f"{specimen_name}_{label}"
    metadata_path = project_dir / f"{run_name}_segmented" / "metadata.json"
    metadata = load_json(metadata_path)
    subvolume_block = metadata.get("02b_build_subvolume_arrays.py", {})
    subvolume_base = Path(subvolume_block.get("subvolume_output_folder", ""))

    for subvolume in subvolume_block.get("subvolumes", []):
        rel_path = subvolume.get("path")
        local_subvolume_path = project_dir / f"{run_name}_segmented" / f"{run_name}_segmented_3D" / rel_path
        configured_subvolume_path = subvolume_base / rel_path if rel_path else Path()
        modulus = find_modulus(local_subvolume_path)
        if modulus is None:
            modulus = find_modulus(configured_subvolume_path)

        yield {
            "binning": label,
            "subvolume": rel_path,
            "x_start": subvolume.get("x_start"),
            "x_end": subvolume.get("x_end"),
            "y_start": subvolume.get("y_start"),
            "y_end": subvolume.get("y_end"),
            "z_start": subvolume.get("z_start"),
            "z_end": subvolume.get("z_end"),
            "relative_density": subvolume.get("relative_density"),
            "porosity": subvolume.get("porosity"),
            "effective_stiffness": modulus,
        }


def rows_from_config(config_path, project_dir):
    config = load_json(config_path)
    metadata_path = Path(config["metadata_output_path"])
    if str(metadata_path).startswith("/data/"):
        metadata_path = project_dir / metadata_path.relative_to("/data/scripts/009-Binning-Variation-CT-Stiffness")

    metadata = load_json(metadata_path)
    subvolume_block = metadata.get("02b_build_subvolume_arrays.py", {})
    subvolume_base = Path(subvolume_block.get("subvolume_output_folder", ""))
    if str(subvolume_base).startswith("/data/"):
        subvolume_base = project_dir / subvolume_base.relative_to("/data/scripts/009-Binning-Variation-CT-Stiffness")

    label = config.get("binning", {}).get("label", "")
    reduce_factor = config.get("binning", {}).get("script_reduce_factor")

    for subvolume in subvolume_block.get("subvolumes", []):
        rel_path = subvolume.get("path")
        subvolume_path = subvolume_base / rel_path if rel_path else Path()
        modulus = find_modulus(subvolume_path)

        yield {
            "binning": label,
            "reduce_factor": reduce_factor,
            "subvolume": rel_path,
            "x_start": subvolume.get("x_start"),
            "x_end": subvolume.get("x_end"),
            "y_start": subvolume.get("y_start"),
            "y_end": subvolume.get("y_end"),
            "z_start": subvolume.get("z_start"),
            "z_end": subvolume.get("z_end"),
            "relative_density": subvolume.get("relative_density"),
            "porosity": subvolume.get("porosity"),
            "effective_stiffness": modulus,
        }


def main():
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Collect binning, porosity, density, and stiffness results into CSV.")
    parser.add_argument("--project-dir", type=Path, default=script_dir)
    parser.add_argument("--specimen-name", default="JM-25-74")
    parser.add_argument("--binnings", nargs="+", default=["1", "2", "4"])
    parser.add_argument("--config", type=Path, help="Collect rows for one config file, including reduce variants.")
    parser.add_argument("--output", type=Path, default=script_dir / "00_results" / "binning_summary.csv")
    args = parser.parse_args()

    rows = []
    if args.config:
        rows.extend(rows_from_config(args.config, args.project_dir))
    else:
        for binning_id in args.binnings:
            rows.extend(rows_from_metadata(args.project_dir, args.specimen_name, binning_id))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "binning",
        "reduce_factor",
        "subvolume",
        "x_start",
        "x_end",
        "y_start",
        "y_end",
        "z_start",
        "z_end",
        "relative_density",
        "porosity",
        "effective_stiffness",
    ]
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
