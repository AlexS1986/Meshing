#!/usr/bin/env python3
import argparse
import csv
import json
import math
from pathlib import Path


def axes_directions():
    return [
        (1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, -1.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.0, 0.0, -1.0),
    ]


def fibonacci_sphere(n):
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    points = []
    for i in range(n):
        z = 1.0 - (2.0 * i + 1.0) / n
        r = math.sqrt(max(0.0, 1.0 - z * z))
        theta = i * golden_angle
        points.append((math.cos(theta) * r, math.sin(theta) * r, z))
    return points


def sample_directions(n):
    if n < 6:
        raise ValueError("At least 6 yield-surface sample points are required.")
    if n == 6:
        return axes_directions()
    return fibonacci_sphere(n)


def sanitize_component(value):
    if abs(value) < 5e-13:
        value = 0.0
    return f"{value:+.4f}".replace("+", "p").replace("-", "m").replace(".", "p")


def main():
    parser = argparse.ArgumentParser(description="Create per-direction yield-surface configs and SLURM jobs.")
    parser.add_argument("--points", type=int, default=6, help="Number of directions to sample; minimum/default is 6.")
    parser.add_argument("--base-config", default="config-Bin4-reduce-2.json")
    parser.add_argument("--radius", type=float, default=0.25, help="Magnitude of the target eps eigenvalue vector before strain scaling.")
    parser.add_argument("--output-dir", default=None, help="Defaults to yield_surface_jobs/nNNN below the project directory.")
    parser.add_argument("--project-dir", default=None, help="Defaults to the directory containing this script.")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve() if args.project_dir else Path(__file__).resolve().parent
    base_config_path = Path(args.base_config)
    if not base_config_path.is_absolute():
        base_config_path = project_dir / base_config_path
    with base_config_path.open() as handle:
        base_config = json.load(handle)

    output_dir = Path(args.output_dir).resolve() if args.output_dir else project_dir / "yield_surface_jobs" / f"n{args.points:03d}"
    output_dir.mkdir(parents=True, exist_ok=True)

    directions = sample_directions(args.points)
    manifest_rows = []
    submit_lines = [
        "#!/usr/bin/env bash",
        f"#SBATCH -J ys-submit-n{args.points:03d}",
        "#SBATCH -A p0023647",
        "#SBATCH -t 1440",
        "#SBATCH --mem-per-cpu=9000",
        "#SBATCH -n 1",
        "#SBATCH -N 1",
        f"#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/010-Yield-Surface-Generation/yield_surface_jobs/n{args.points:03d}/%x.err.%j",
        f"#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/010-Yield-Surface-Generation/yield_surface_jobs/n{args.points:03d}/%x.out.%j",
        "#SBATCH --mail-type=END",
        "#SBATCH -C i01",
        "",
        "set -euo pipefail",
        "SCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"",
        "",
    ]

    for index, direction in enumerate(directions):
        dx, dy, dz = direction
        eps = [args.radius * dx, args.radius * dy, args.radius * dz]
        sample_id = f"ys_{index:03d}_e1_{sanitize_component(eps[0])}_e2_{sanitize_component(eps[1])}_e3_{sanitize_component(eps[2])}"
        sample_dir = output_dir / sample_id
        sample_dir.mkdir(parents=True, exist_ok=True)

        cfg = json.loads(json.dumps(base_config))
        ys = cfg.setdefault("yield_surface", {})
        ys["loading_directions"] = ["tensor"]
        ys["eps_mac_eigenvalues"] = eps
        ys["sample_id"] = sample_id
        ys["sample_index"] = index
        ys["sample_count"] = args.points
        ys["sample_direction_unit"] = [dx, dy, dz]
        ys["sample_radius"] = args.radius
        ys["sample_method"] = "cartesian_axes" if args.points == 6 else "fibonacci_sphere"

        config_path = sample_dir / "config.json"
        with config_path.open("w") as handle:
            json.dump(cfg, handle, indent=2)
            handle.write("\n")

        job_path = sample_dir / f"job_{sample_id}_CLUSTER.sh"
        job_text = f"""#!/bin/bash

#SBATCH -J {sample_id[:48]}
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH --mem-per-cpu=9000
#SBATCH -n 32
#SBATCH -N 1
#SBATCH -C i01
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/010-Yield-Surface-Generation/yield_surface_jobs/n{args.points:03d}/{sample_id}/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/010-Yield-Surface-Generation/yield_surface_jobs/n{args.points:03d}/{sample_id}/%x.out.%j
#SBATCH --mail-type=END

SCRIPT_DIR=\"$HPC_SCRATCH/pygalmesh/data/scripts/010-Yield-Surface-Generation\"
bash \"$SCRIPT_DIR/job_yield_surface_point_CLUSTER.sh\" \"/data/scripts/010-Yield-Surface-Generation/yield_surface_jobs/n{args.points:03d}/{sample_id}/config.json\"
"""
        job_path.write_text(job_text)
        job_path.chmod(0o755)
        submit_lines.append(f"sbatch \"$SCRIPT_DIR/{sample_id}/job_{sample_id}_CLUSTER.sh\"")
        manifest_rows.append({
            "sample_id": sample_id,
            "sample_index": index,
            "direction_x": dx,
            "direction_y": dy,
            "direction_z": dz,
            "eps_1": eps[0],
            "eps_2": eps[1],
            "eps_3": eps[2],
            "config": str(config_path.relative_to(project_dir)),
            "job": str(job_path.relative_to(project_dir)),
        })

    manifest_path = output_dir / "manifest.csv"
    with manifest_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0].keys()))
        writer.writeheader()
        writer.writerows(manifest_rows)

    submit_path = output_dir / "submit_all_yield_surface_points.sh"
    submit_path.write_text("\n".join(submit_lines) + "\n")
    submit_path.chmod(0o755)

    print(f"Wrote {len(manifest_rows)} yield-surface point jobs to {output_dir}")
    print(f"Manifest: {manifest_path}")
    print(f"Submit all after sync on the cluster with: {submit_path}")


if __name__ == "__main__":
    main()
