#!/usr/bin/env python3
import argparse
import csv
import copy
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_VARIANTS = [
    {
        "name": "baseline_sigma_current",
        "01_segment_slice_wise": {
            "gaussian_sigma_pixels": None,
            "median_filter_size": 0,
            "threshold_multiplier": 1.0,
            "threshold_offset": 0.0,
            "remove_small_objects_min_size": 0,
            "remove_small_holes_area_threshold": 0,
            "binary_opening_radius": 0,
            "binary_closing_radius": 0,
        },
    },
    {
        "name": "gauss_px_0p5",
        "01_segment_slice_wise": {"gaussian_sigma_pixels": 0.5},
    },
    {
        "name": "gauss_px_1p0",
        "01_segment_slice_wise": {"gaussian_sigma_pixels": 1.0},
    },
    {
        "name": "gauss_px_1p5",
        "01_segment_slice_wise": {"gaussian_sigma_pixels": 1.5},
    },
    {
        "name": "gauss_px_1p0_holes16_objects8",
        "01_segment_slice_wise": {
            "gaussian_sigma_pixels": 1.0,
            "remove_small_objects_min_size": 8,
            "remove_small_holes_area_threshold": 16,
        },
    },
    {
        "name": "gauss_px_1p0_threshold_low_0p98",
        "01_segment_slice_wise": {
            "gaussian_sigma_pixels": 1.0,
            "threshold_multiplier": 0.98,
        },
    },
    {
        "name": "gauss_px_1p0_threshold_high_1p02",
        "01_segment_slice_wise": {
            "gaussian_sigma_pixels": 1.0,
            "threshold_multiplier": 1.02,
        },
    },
]


REPORT_PATTERNS = {
    "relative_density": r"relative_density: ([0-9.eE+-]+)",
    "material_components_6": r"material_components_6: (\d+)",
    "material_components_26": r"material_components_26: (\d+)",
    "material_components_joined_only_by_edge_or_corner": r"material_components_joined_only_by_edge_or_corner: (\d+)",
    "pore_components_6": r"pore_components_6: (\d+)",
    "pore_components_26": r"pore_components_26: (\d+)",
    "pore_components_joined_only_by_edge_or_corner": r"pore_components_joined_only_by_edge_or_corner: (\d+)",
    "enclosed_pore_components_6": r"enclosed_pore_components_6: (\d+)",
    "enclosed_pore_voxels_6": r"enclosed_pore_voxels_6: (\d+)",
    "mixed_2x2x2_blocks": r"mixed_2x2x2_blocks: (\d+)",
    "material_ambiguous_2x2x2_blocks": r"material_ambiguous_2x2x2_blocks: (\d+)",
    "pore_ambiguous_2x2x2_blocks": r"pore_ambiguous_2x2x2_blocks: (\d+)",
}


def load_variants(path):
    if path is None:
        return DEFAULT_VARIANTS
    with open(path, "r") as handle:
        variants = json.load(handle)
    if isinstance(variants, dict):
        variants = variants.get("variants", [])
    return variants


def run_command(command, log_path):
    print("+ " + " ".join(str(part) for part in command), flush=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with subprocess.Popen(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    ) as proc:
        with open(log_path, "w") as log_handle:
            output = []
            for line in proc.stdout:
                print(line, end="")
                log_handle.write(line)
                output.append(line)
        code = proc.wait()
    if code != 0:
        raise subprocess.CalledProcessError(code, command, "".join(output))


def parse_topology_report(path):
    text = path.read_text() if path.exists() else ""
    row = {}
    verdict = re.search(r"Voxel topology verdict: (\w+)", text)
    row["voxel_topology_verdict"] = verdict.group(1) if verdict else ""
    for key, pattern in REPORT_PATTERNS.items():
        matches = re.findall(pattern, text)
        row[key] = matches[-1] if matches else ""
    return row


def update_nested(base, updates):
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            update_nested(base[key], value)
        else:
            base[key] = value


def main():
    parser = argparse.ArgumentParser(description="Sweep 01 segmentation parameters and score voxel topology before meshing.")
    parser.add_argument("--config", required=True, help="Base config JSON")
    parser.add_argument("--output-dir", required=True, help="Sweep output directory")
    parser.add_argument("--variants", default=None, help="Optional JSON variant list/object")
    parser.add_argument("--only", nargs="*", default=None, help="Run only named variants")
    parser.add_argument("--max-runs", type=int, default=None, help="Limit number of variants")
    parser.add_argument("--skip-existing", action="store_true", help="Skip variants with existing topology report")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    base_config_path = Path(args.config).resolve()
    base_config = json.loads(base_config_path.read_text())
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    variants = load_variants(args.variants)
    if args.only:
        wanted = set(args.only)
        variants = [variant for variant in variants if variant["name"] in wanted]
    if args.max_runs is not None:
        variants = variants[: args.max_runs]

    rows = []
    for variant in variants:
        name = variant["name"]
        variant_dir = output_dir / name
        segmented_dir = variant_dir / "segmented_slices"
        volume_dir = variant_dir / "segmented_3D"
        subvolume_dir = volume_dir / "subvolume_x40_y42"
        topology_report = subvolume_dir / "volume_topology.txt"
        config_path = variant_dir / "config.json"
        metadata_path = variant_dir / "metadata.json"

        if args.skip_existing and topology_report.exists():
            print(f"Skipping existing variant: {name}")
        else:
            variant_dir.mkdir(parents=True, exist_ok=True)
            config = copy.deepcopy(base_config)
            shutil.copy2(base_config["metadata_output_path"], metadata_path)
            config["metadata_output_path"] = str(metadata_path)
            config["01_segment_slice_wise"]["output_folder"] = str(segmented_dir)
            config["02_segmented_3D_array"]["input_folder"] = str(segmented_dir)
            config["02_segmented_3D_array"]["output_folder"] = str(volume_dir)
            config["03_mesh_3D_array"]["input_folder"] = str(volume_dir)
            config["02b_build_subvolume_arrays"]["subvolume_output_folder"] = str(volume_dir)
            update_nested(config, variant.get("config", {}))
            update_nested(config["01_segment_slice_wise"], variant.get("01_segment_slice_wise", {}))
            config_path.write_text(json.dumps(config, indent=2) + "\n")

            run_command([sys.executable, str(script_dir / "01_segment_slice_wise.py"), "--config", str(config_path)], variant_dir / "01_segment.log")
            run_command([sys.executable, str(script_dir / "02_build3D_segmented_array.py"), "--config", str(config_path)], variant_dir / "02_build3D.log")
            run_command([sys.executable, str(script_dir / "02a_rotate_pic_to_align_with_axis.py"), "--config", str(config_path)], variant_dir / "02a_rotate.log")
            run_command([sys.executable, str(script_dir / "02b_build_subvolume_arrays.py"), "--config", str(config_path)], variant_dir / "02b_subvolume.log")

            subvolumes = sorted(volume_dir.glob("subvolume_x*_y*/volume.npy"))
            if not subvolumes:
                raise RuntimeError(f"No subvolume volume.npy created for variant {name}")
            subvolume_path = subvolumes[0]
            topology_report = subvolume_path.with_name("volume_topology.txt")
            run_command(
                [
                    sys.executable,
                    str(script_dir / "02c_voxel_topology_cleanup.py"),
                    "--config",
                    str(config_path),
                    "--npy",
                    str(subvolume_path),
                    "--report",
                    str(topology_report),
                    "--output",
                    str(subvolume_path.with_name("volume_topology_cleaned.npy")),
                ],
                variant_dir / "02c_topology.log",
            )

        row = {"variant": name, "config_path": str(config_path), "topology_report": str(topology_report)}
        row.update(variant.get("01_segment_slice_wise", {}))
        row.update(parse_topology_report(topology_report))
        rows.append(row)

    summary_path = output_dir / "summary.csv"
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with open(summary_path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote segmentation topology sweep summary: {summary_path}")


if __name__ == "__main__":
    main()
