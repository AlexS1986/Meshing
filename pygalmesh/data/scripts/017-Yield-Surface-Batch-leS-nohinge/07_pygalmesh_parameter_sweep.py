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
        "name": "exude120_s5",
        "pygalmesh_parameters": {
            "max_element_size_factor": 5.0,
            "max_facet_distance_factor": 0.3,
            "lloyd": False,
            "odt": False,
            "perturb": True,
            "exude": True,
            "exude_time_limit": 120,
            "exude_sliver_bound": 5.0,
            "seed": 0,
            "verbose": False,
        },
    },
    {
        "name": "finer4_fd025_exude120_s5",
        "pygalmesh_parameters": {
            "max_element_size_factor": 4.0,
            "max_facet_distance_factor": 0.25,
            "lloyd": False,
            "odt": False,
            "perturb": True,
            "exude": True,
            "exude_time_limit": 120,
            "exude_sliver_bound": 5.0,
            "seed": 0,
            "verbose": False,
        },
    },
    {
        "name": "finer4_fd025_odt_exude120_s5",
        "pygalmesh_parameters": {
            "max_element_size_factor": 4.0,
            "max_facet_distance_factor": 0.25,
            "lloyd": False,
            "odt": True,
            "perturb": True,
            "exude": True,
            "exude_time_limit": 120,
            "exude_sliver_bound": 5.0,
            "seed": 0,
            "verbose": False,
        },
    },
]


METRIC_PATTERNS = {
    "input_points": r"Input points:\s+(\d+)",
    "input_tetrahedra": r"Input tetrahedra:\s+(\d+)",
    "mesh_points": r"Mesh points:\s+(\d+)",
    "mesh_tetrahedra": r"Mesh tetrahedra:\s+(\d+)",
    "smallest_volume": r"Smallest volume:\s+([0-9.eE+-]+)",
    "largest_volume": r"Largest volume:\s+([0-9.eE+-]+)",
    "shortest_edge": r"Shortest edge:\s+([0-9.eE+-]+)",
    "longest_edge": r"Longest edge:\s+([0-9.eE+-]+)",
    "smallest_aspect_ratio": r"Smallest asp\.ratio:\s+([0-9.eE+-]+)",
    "largest_aspect_ratio": r"Largest asp\.ratio:\s+([0-9.eE+-]+)",
    "smallest_facet_angle": r"Smallest facangle:\s+([0-9.eE+-]+)",
    "largest_facet_angle": r"Largest facangle:\s+([0-9.eE+-]+)",
    "smallest_dihedral": r"Smallest dihedral:\s+([0-9.eE+-]+)",
    "largest_dihedral": r"Largest dihedral:\s+([0-9.eE+-]+)",
}


def load_variants(path):
    if path is None:
        return DEFAULT_VARIANTS
    with open(path, "r") as handle:
        variants = json.load(handle)
    if isinstance(variants, dict):
        variants = variants.get("variants", [])
    return variants


def run_command(command, cwd=None, log_path=None):
    print("+ " + " ".join(str(part) for part in command), flush=True)
    with subprocess.Popen(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    ) as proc:
        output_lines = []
        with open(log_path, "w") if log_path else open("/dev/null", "w") as log_handle:
            for line in proc.stdout:
                print(line, end="")
                log_handle.write(line)
                output_lines.append(line)
        return_code = proc.wait()
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, command, "".join(output_lines))
    return "".join(output_lines)


def parse_tetgen_log(log_path):
    text = Path(log_path).read_text() if Path(log_path).exists() else ""
    metrics = {}
    for key, pattern in METRIC_PATTERNS.items():
        match = re.search(pattern, text)
        metrics[key] = match.group(1) if match else ""

    low_dihedral = re.search(r"0 -\s+5 degrees:\s+(\d+).*\n\s+5 - 10 degrees:\s+(\d+)", text)
    if low_dihedral:
        metrics["dihedral_0_5_count"] = low_dihedral.group(1)
        metrics["dihedral_5_10_count"] = low_dihedral.group(2)
    else:
        metrics["dihedral_0_5_count"] = ""
        metrics["dihedral_5_10_count"] = ""
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Sweep pygalmesh parameters and compare TetGen quality reports.")
    parser.add_argument("--config", required=True, help="Base config JSON")
    parser.add_argument("--npy", required=True, help="Input subvolume volume.npy")
    parser.add_argument("--output-dir", required=True, help="Directory for sweep outputs")
    parser.add_argument("--variants", default=None, help="Optional JSON list/object of variants")
    parser.add_argument("--only", nargs="*", default=None, help="Run only named variants")
    parser.add_argument("--max-runs", type=int, default=None, help="Limit number of variants to run")
    parser.add_argument("--skip-existing", action="store_true", help="Skip variants whose TetGen log already exists")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    base_config_path = Path(args.config)
    base_config = json.loads(base_config_path.read_text())
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata_source = Path(base_config["metadata_output_path"])
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
        variant_dir.mkdir(parents=True, exist_ok=True)
        mesh_path = variant_dir / "mesh.xdmf"
        config_path = variant_dir / "config.json"
        metadata_path = variant_dir / "metadata.json"
        mesh_log_path = variant_dir / "mesh_generation.log"
        tetgen_log_path = variant_dir / "mesh_tetgen_check.tetgen.log"

        if args.skip_existing and tetgen_log_path.exists():
            print(f"Skipping existing variant: {name}")
        else:
            config = copy.deepcopy(base_config)
            config["metadata_output_path"] = str(metadata_path)
            if metadata_source.exists():
                shutil.copy2(metadata_source, metadata_path)
            else:
                metadata_path.write_text("{}\n")

            mesh_cfg = config["03_mesh_3D_array"]
            mesh_cfg["meshing_method"] = "pygalmesh"
            mesh_cfg["mesh_output_path"] = str(mesh_path)
            pygalmesh_params = mesh_cfg.setdefault("pygalmesh_parameters", {})
            pygalmesh_params["verbose"] = False
            pygalmesh_params.update(variant.get("pygalmesh_parameters", {}))
            config_path.write_text(json.dumps(config, indent=2) + "\n")

            run_command(
                [
                    sys.executable,
                    str(script_dir / "03_mesh_3D_array_pygalmesh.py"),
                    "--config",
                    str(config_path),
                    "--npy",
                    str(args.npy),
                    "--mesh",
                    str(mesh_path),
                ],
                log_path=mesh_log_path,
            )
            run_command(
                [
                    sys.executable,
                    str(script_dir / "05_tetgen_postprocess_mesh.py"),
                    "--config",
                    str(config_path),
                    "--mesh",
                    str(mesh_path),
                    "--output",
                    str(variant_dir / "mesh_tetgen_check.xdmf"),
                    "--switches=-rCV",
                ],
                log_path=variant_dir / "tetgen_postprocess_stdout.log",
            )
            run_command(
                [
                    sys.executable,
                    str(script_dir / "08_mesh_quality_report.py"),
                    "--config",
                    str(config_path),
                    "--tetgen-log",
                    str(tetgen_log_path),
                    "--output",
                    str(variant_dir / "mesh_quality.txt"),
                ],
                log_path=variant_dir / "mesh_quality_stdout.log",
            )

        row = {"variant": name}
        quality_report_path = variant_dir / "mesh_quality.txt"
        row["quality_report_path"] = str(quality_report_path)
        if quality_report_path.exists():
            first_line = quality_report_path.read_text().splitlines()[0]
            row["quality_verdict"] = first_line.split(":", 1)[1].strip() if ":" in first_line else ""
        else:
            row["quality_verdict"] = ""
        row.update(variant.get("pygalmesh_parameters", {}))
        row.update(parse_tetgen_log(tetgen_log_path))
        row["mesh_path"] = str(mesh_path)
        row["tetgen_log_path"] = str(tetgen_log_path)
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
    print(f"Wrote sweep summary: {summary_path}")


if __name__ == "__main__":
    main()
