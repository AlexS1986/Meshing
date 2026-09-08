#!/usr/bin/env python3
"""Build ParaView point clouds and convex-hull surfaces from yield-run JSON files."""

import argparse
import csv
import itertools
import json
from pathlib import Path

import numpy as np

try:
    from scipy.spatial import ConvexHull, QhullError
except ImportError:  # Point-cloud output remains available without SciPy.
    ConvexHull = None
    QhullError = Exception


def iter_json_files(root):
    yield from root.rglob("*.json")


def scalar(state, name):
    value = state.get(name)
    return float(value) if value is not None else np.nan


def read_yield_state(path):
    try:
        with path.open() as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        print(f"[skip] {path}: {error}")
        return None
    state = data.get("final_yield_state")
    if not isinstance(state, dict):
        return None
    eps = np.asarray(state.get("eps_mac_eigenvalues_current"), dtype=float)
    sigma = np.asarray(state.get("sigma_avg_reduced_volume"), dtype=float)
    if eps.shape != (3,) or sigma.shape != (3, 3) or not np.all(np.isfinite(eps)) or not np.all(np.isfinite(sigma)):
        print(f"[skip] {path}: incomplete final strain/stress state")
        return None
    sigma = 0.5 * (sigma + sigma.T)
    return {
        "source": str(path),
        "material": str(data.get("material", "unknown")),
        "loading_direction": str(data.get("loading_direction", "unknown")),
        "stop_reason": str(data.get("stop_reason", "unknown")),
        "strain": eps,
        "stress_normal": np.diag(sigma),
        "stress_principal": np.linalg.eigvalsh(sigma),
        "t": scalar(state, "t"),
        "strain_scale": scalar(state, "strain_scale"),
        "sig_vm": scalar(state, "sig_vm_avg_reduced_volume"),
        "yielded_fraction": scalar(state, "yielded_fraction_reduced_material_volume"),
    }


def point_key(point, tolerance):
    scale = max(tolerance, np.finfo(float).eps)
    return tuple(np.rint(np.asarray(point) / scale).astype(np.int64))


def unique_records(records, coordinate, tolerance, expand_permutations=False):
    unique = {}
    for record in records:
        points = [record[coordinate]]
        if expand_permutations:
            points = sorted(set(itertools.permutations(record[coordinate].tolist())))
        for point in points:
            key = point_key(point, tolerance)
            unique.setdefault(key, (np.asarray(point, dtype=float), record))
    return list(unique.values())


def hull_faces(points):
    if len(points) < 4 or ConvexHull is None:
        return np.empty((0, 3), dtype=int), "fewer than four points or SciPy unavailable"
    try:
        hull = ConvexHull(points)
        return np.asarray(hull.simplices, dtype=int), None
    except QhullError as error:
        return np.empty((0, 3), dtype=int), f"convex hull failed: {error.__class__.__name__}"


def write_legacy_vtk(path, items, title, norm_label):
    points = np.asarray([item[0] for item in items], dtype=float)
    faces, warning = hull_faces(points)
    with path.open("w") as out:
        out.write("# vtk DataFile Version 3.0\n")
        out.write(f"{title}\nASCII\nDATASET POLYDATA\n")
        out.write(f"POINTS {len(points)} double\n")
        for point in points:
            out.write("{:.17g} {:.17g} {:.17g}\n".format(*point))
        out.write(f"VERTICES {len(points)} {2 * len(points)}\n")
        for index in range(len(points)):
            out.write(f"1 {index}\n")
        out.write(f"POLYGONS {len(faces)} {4 * len(faces)}\n")
        for face in faces:
            out.write(f"3 {face[0]} {face[1]} {face[2]}\n")
        out.write(f"POINT_DATA {len(points)}\n")
        fields = {
            norm_label: np.linalg.norm(points, axis=1),
            "t": [item[1]["t"] for item in items],
            "strain_scale": [item[1]["strain_scale"] for item in items],
            "sig_vm_avg": [item[1]["sig_vm"] for item in items],
            "yielded_fraction": [item[1]["yielded_fraction"] for item in items],
        }
        for name, values in fields.items():
            out.write(f"SCALARS {name} double 1\nLOOKUP_TABLE default\n")
            for value in values:
                out.write(f"{float(value):.17g}\n")
    if warning:
        print(f"[point cloud only] {path.name}: {warning}")
    else:
        print(f"[surface] {path.name}: {len(points)} points, {len(faces)} triangles")


def write_csv(path, records):
    fields = [
        "source", "material", "loading_direction", "stop_reason", "t", "strain_scale",
        "eps_1", "eps_2", "eps_3", "sigma_xx", "sigma_yy", "sigma_zz",
        "sigma_principal_min", "sigma_principal_mid", "sigma_principal_max",
        "sig_vm_avg_reduced_volume", "yielded_fraction_reduced_material_volume",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow(dict(
                source=record["source"], material=record["material"],
                loading_direction=record["loading_direction"], stop_reason=record["stop_reason"],
                t=record["t"], strain_scale=record["strain_scale"],
                eps_1=record["strain"][0], eps_2=record["strain"][1], eps_3=record["strain"][2],
                sigma_xx=record["stress_normal"][0], sigma_yy=record["stress_normal"][1], sigma_zz=record["stress_normal"][2],
                sigma_principal_min=record["stress_principal"][0],
                sigma_principal_mid=record["stress_principal"][1],
                sigma_principal_max=record["stress_principal"][2],
                sig_vm_avg_reduced_volume=record["sig_vm"],
                yielded_fraction_reduced_material_volume=record["yielded_fraction"],
            ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=Path(__file__).resolve().parent / "00_results")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--material", default=None)
    parser.add_argument("--loading-direction", default=None)
    parser.add_argument("--dedup-tolerance", type=float, default=1e-10)
    parser.add_argument("--expand-principal-permutations", action="store_true",
                        help="Create all six principal-stress permutations; use only for an isotropic response.")
    parser.add_argument("--exclude-substring", default=None,
                        help="Skip any JSON file whose name contains this substring "
                             "(useful to filter out leftover/duplicate result files).")
    args = parser.parse_args()

    input_root = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else input_root / "yield_surface_paraview"
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for path in sorted(iter_json_files(input_root)):
        if args.exclude_substring and args.exclude_substring in path.name:
            continue
        record = read_yield_state(path)
        if record is None:
            continue
        if args.material and record["material"] != args.material:
            continue
        if args.loading_direction and record["loading_direction"] != args.loading_direction:
            continue
        records.append(record)
    if not records:
        raise SystemExit(f"No JSON containing a complete final_yield_state found below {input_root}")

    write_csv(output_dir / "yield_surface_points.csv", records)
    datasets = [
        ("strain", "yield_surface_strain.vtk", "Yield surface in strain eigenvalue space", "norm_of_the_strain_tensor", False),
        ("stress_normal", "yield_surface_stress_normal.vtk", "Yield surface in fixed-axis normal-stress space", "norm_of_the_normal_stress_vector", False),
        ("stress_principal", "yield_surface_stress_principal.vtk", "Yield surface in sorted principal-stress space", "norm_of_the_stress_tensor", args.expand_principal_permutations),
    ]
    for coordinate, filename, title, norm_label, expand in datasets:
        items = unique_records(records, coordinate, args.dedup_tolerance, expand)
        write_legacy_vtk(output_dir / filename, items, title, norm_label)
    print(f"Accepted {len(records)} yield-state JSON files. Output: {output_dir}")


if __name__ == "__main__":
    main()
