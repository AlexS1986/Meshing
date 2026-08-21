#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

import meshio
import numpy as np


def load_config(path):
    with open(path, "r") as handle:
        return json.load(handle)


def tetra_block_index(mesh):
    for index, block in enumerate(mesh.cells):
        if block.type == "tetra":
            return index
    raise ValueError("No tetra cell block found in mesh")


def tetra_volumes(points, cells):
    p0 = points[cells[:, 0]]
    p1 = points[cells[:, 1]]
    p2 = points[cells[:, 2]]
    p3 = points[cells[:, 3]]
    return np.einsum("ij,ij->i", np.cross(p1 - p0, p2 - p0), p3 - p0) / 6.0


def compact_mesh(points, cells):
    used = np.unique(cells.ravel())
    old_to_new = np.full(len(points), -1, dtype=np.int64)
    old_to_new[used] = np.arange(len(used), dtype=np.int64)
    return points[used], old_to_new[cells], used


def snap_points_to_bounds(points, bounds_min, bounds_max, tolerance):
    snapped = points.copy()
    counts = {}
    for axis, name in enumerate(("x", "y", "z")):
        lo_mask = np.abs(snapped[:, axis] - bounds_min[axis]) <= tolerance
        hi_mask = np.abs(snapped[:, axis] - bounds_max[axis]) <= tolerance
        counts[f"{name}_min"] = int(np.count_nonzero(lo_mask))
        counts[f"{name}_max"] = int(np.count_nonzero(hi_mask))
        snapped[lo_mask, axis] = bounds_min[axis]
        snapped[hi_mask, axis] = bounds_max[axis]
    return snapped, counts


def filter_cell_data(mesh, tetra_index, keep_mask):
    filtered = []
    for name, data_list in mesh.cell_data.items():
        new_list = []
        for index, data in enumerate(data_list):
            if index == tetra_index and len(data) == len(keep_mask):
                new_list.append(np.asarray(data)[keep_mask])
            else:
                new_list.append(data)
        filtered.append((name, new_list))
    return dict(filtered)


def write_report(path, info):
    lines = ["Mesh crop-boundary snap report", "==============================", ""]
    for key, value in info.items():
        lines.append(f"{key}: {value}")
    Path(path).write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Snap mesh nodes near the crop cuboid boundary and remove collapsed tetrahedra.")
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--mesh", required=True, help="Input/output mesh path")
    parser.add_argument("--output", default=None, help="Optional output mesh path. Defaults to overwrite --mesh")
    parser.add_argument("--report", default=None, help="Optional text report path")
    args = parser.parse_args()

    config = load_config(args.config)
    cfg = config.get("10_snap_mesh_to_crop_boundary", {})
    if not cfg.get("enabled", False):
        print("Boundary snapping disabled in config; leaving mesh unchanged.")
        return

    mesh_path = args.mesh
    output_path = args.output or args.mesh
    report_path = args.report or str(Path(output_path).with_suffix(".snap_boundary.txt"))

    mesh = meshio.read(mesh_path)
    tetra_index = tetra_block_index(mesh)
    points = np.asarray(mesh.points[:, :3], dtype=float)
    cells = np.asarray(mesh.cells[tetra_index].data, dtype=np.int64)

    bounds_min = points.min(axis=0)
    bounds_max = points.max(axis=0)
    lengths = bounds_max - bounds_min
    if np.any(lengths <= 0.0):
        raise ValueError(f"Invalid mesh bounds for snapping: min={bounds_min}, max={bounds_max}")

    tolerance_fraction = float(cfg.get("tolerance_fraction", 0.01))
    tolerance_absolute = cfg.get("tolerance_absolute", None)
    tolerance = float(tolerance_absolute) if tolerance_absolute is not None else tolerance_fraction * float(np.min(lengths))
    volume_tolerance = float(cfg.get("volume_tolerance", 1e-14))
    orient_positive = bool(cfg.get("orient_tets_positive", True))

    original_points = len(points)
    original_cells = len(cells)
    snapped_points, snap_counts = snap_points_to_bounds(points, bounds_min, bounds_max, tolerance)
    moved_nodes = int(np.count_nonzero(np.linalg.norm(snapped_points - points, axis=1) > 0.0))

    volumes = tetra_volumes(snapped_points, cells)
    duplicate_vertex_cells = np.any(np.diff(np.sort(cells, axis=1), axis=1) == 0, axis=1)
    tiny_cells = np.abs(volumes) <= volume_tolerance
    inverted_cells = volumes < -volume_tolerance

    keep = ~(duplicate_vertex_cells | tiny_cells)
    kept_cells = cells[keep].copy()
    kept_volumes = volumes[keep]
    if orient_positive:
        flip = kept_volumes < 0.0
        kept_cells[flip] = kept_cells[flip][:, [1, 0, 2, 3]]
        inverted_removed = 0
        inverted_reoriented = int(np.count_nonzero(flip))
    else:
        keep2 = kept_volumes >= -volume_tolerance
        inverted_removed = int(np.count_nonzero(~keep2))
        inverted_reoriented = 0
        kept_cells = kept_cells[keep2]

    compact_points, compact_cells, used_old_indices = compact_mesh(snapped_points, kept_cells)

    cell_data = {}
    for name, data_list in mesh.cell_data.items():
        if tetra_index < len(data_list) and len(data_list[tetra_index]) == original_cells:
            cell_data[name] = [np.asarray(data_list[tetra_index])[keep]]
    if not orient_positive and inverted_removed:
        # Cell data for the uncommon drop-inverted mode would need a second mask; keep config default.
        cell_data = {}

    point_data = {}
    for name, data in mesh.point_data.items():
        if len(data) == original_points:
            point_data[name] = np.asarray(data)[used_old_indices]

    out = meshio.Mesh(
        points=compact_points,
        cells={"tetra": compact_cells},
        point_data=point_data,
        cell_data=cell_data,
        field_data=mesh.field_data,
    )
    meshio.write(output_path, out)

    info = {
        "mesh": mesh_path,
        "output": output_path,
        "bounds_min": bounds_min.tolist(),
        "bounds_max": bounds_max.tolist(),
        "tolerance": tolerance,
        "tolerance_fraction": tolerance_fraction,
        "original_points": original_points,
        "final_points": int(len(compact_points)),
        "removed_unreferenced_points": int(original_points - len(compact_points)),
        "original_tetrahedra": original_cells,
        "final_tetrahedra": int(len(compact_cells)),
        "removed_duplicate_vertex_tetrahedra": int(np.count_nonzero(duplicate_vertex_cells)),
        "removed_tiny_or_zero_volume_tetrahedra": int(np.count_nonzero(tiny_cells)),
        "removed_inverted_tetrahedra": inverted_removed,
        "reoriented_inverted_tetrahedra": inverted_reoriented,
        "moved_nodes": moved_nodes,
        **{f"snapped_nodes_{key}": value for key, value in snap_counts.items()},
    }
    write_report(report_path, info)
    print(f"Snapped {moved_nodes} nodes to crop boundary; removed {original_cells - len(compact_cells)} tetrahedra.")
    print(f"Wrote mesh: {output_path}")
    print(f"Wrote report: {report_path}")


if __name__ == "__main__":
    main()
