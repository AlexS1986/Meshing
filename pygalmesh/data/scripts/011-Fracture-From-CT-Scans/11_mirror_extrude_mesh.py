#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import meshio
import numpy as np
from scipy.spatial import cKDTree


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


def tolerance_from_config(cfg, lengths):
    absolute = cfg.get("merge_tolerance_absolute", None)
    if absolute is not None:
        return float(absolute)
    fraction = float(cfg.get("merge_tolerance_fraction", 1e-6))
    return fraction * float(np.min(lengths))


def mirror_points(points, axis, plane_value):
    mirrored = points.copy()
    mirrored[:, axis] = 2.0 * plane_value - mirrored[:, axis]
    return mirrored


def build_mirrored_connectivity(points, mirrored_points, cells, axis, plane_value, tolerance):
    original_plane_mask = np.abs(points[:, axis] - plane_value) <= tolerance
    original_plane_indices = np.flatnonzero(original_plane_mask)

    old_to_combined = np.full(len(points), -1, dtype=np.int64)
    appended_points = []
    glued_count = 0

    if len(original_plane_indices) > 0:
        tree = cKDTree(points[original_plane_indices])
    else:
        tree = None

    for mirrored_index, point in enumerate(mirrored_points):
        glued = False
        if tree is not None and abs(point[axis] - plane_value) <= tolerance:
            distance, nearest = tree.query(point, distance_upper_bound=tolerance)
            if np.isfinite(distance) and nearest < len(original_plane_indices):
                old_to_combined[mirrored_index] = int(original_plane_indices[nearest])
                glued = True
                glued_count += 1
        if not glued:
            old_to_combined[mirrored_index] = len(points) + len(appended_points)
            appended_points.append(point)

    if appended_points:
        combined_points = np.vstack((points, np.asarray(appended_points)))
    else:
        combined_points = points.copy()

    mirrored_cells = old_to_combined[cells]
    mirrored_cells = mirrored_cells[:, [1, 0, 2, 3]]
    combined_cells = np.vstack((cells, mirrored_cells))
    return combined_points, combined_cells, glued_count, len(appended_points)


def clean_cells(points, cells, volume_tolerance, orient_positive=True):
    volumes = tetra_volumes(points, cells)
    duplicate_vertex_cells = np.any(np.diff(np.sort(cells, axis=1), axis=1) == 0, axis=1)
    tiny_cells = np.abs(volumes) <= volume_tolerance
    keep = ~(duplicate_vertex_cells | tiny_cells)
    kept_cells = cells[keep].copy()
    kept_volumes = volumes[keep]

    if orient_positive:
        flip = kept_volumes < -volume_tolerance
        kept_cells[flip] = kept_cells[flip][:, [1, 0, 2, 3]]
        inverted_removed = 0
        inverted_reoriented = int(np.count_nonzero(flip))
        second_keep = np.ones(len(kept_cells), dtype=bool)
    else:
        second_keep = kept_volumes >= -volume_tolerance
        inverted_removed = int(np.count_nonzero(~second_keep))
        inverted_reoriented = 0
        kept_cells = kept_cells[second_keep]

    compact_points, compact_cells, used = compact_mesh(points, kept_cells)
    return compact_points, compact_cells, used, {
        "removed_duplicate_vertex_tetrahedra": int(np.count_nonzero(duplicate_vertex_cells)),
        "removed_tiny_or_zero_volume_tetrahedra": int(np.count_nonzero(tiny_cells)),
        "removed_inverted_tetrahedra": inverted_removed,
        "reoriented_inverted_tetrahedra": inverted_reoriented,
        "first_keep_mask": keep,
        "second_keep_mask": second_keep,
    }


def tetra_cell_data(mesh, tetra_index, original_count, first_keep_mask, second_keep_mask):
    cell_data = {}
    combined_keep = None
    if len(second_keep_mask) == int(np.count_nonzero(first_keep_mask)):
        combined_keep = first_keep_mask.copy()
        combined_keep[first_keep_mask] = second_keep_mask

    for name, data_list in mesh.cell_data.items():
        if tetra_index >= len(data_list):
            continue
        data = np.asarray(data_list[tetra_index])
        if len(data) != original_count:
            continue
        doubled = np.concatenate((data, data.copy()))
        if combined_keep is not None and len(combined_keep) == len(doubled):
            doubled = doubled[combined_keep]
        cell_data[name] = [doubled]
    return cell_data


def write_report(path, info):
    lines = ["Mesh mirror extrusion report", "============================", ""]
    for key, value in info.items():
        lines.append(f"{key}: {value}")
    Path(path).write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Mirror-extrude a tetra mesh once and glue it along a selected crop-boundary plane.")
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--mesh", required=True, help="Input/output mesh path")
    parser.add_argument("--output", default=None, help="Optional output mesh path. Defaults to overwrite --mesh")
    parser.add_argument("--report", default=None, help="Optional report path")
    args = parser.parse_args()

    config = load_config(args.config)
    cfg = config.get("11_mirror_extrude_mesh", {})
    if not cfg.get("enabled", False):
        print("Mirror extrusion disabled in config; leaving mesh unchanged.")
        return

    axis_name = str(cfg.get("axis", "x")).lower()
    axis_map = {"x": 0, "y": 1, "z": 2}
    if axis_name not in axis_map:
        raise ValueError(f"Unsupported mirror axis: {axis_name}; expected x, y, or z")
    axis = axis_map[axis_name]

    plane = str(cfg.get("plane", f"{axis_name}min")).lower()
    if plane not in (f"{axis_name}min", f"{axis_name}max"):
        raise ValueError(f"Unsupported mirror plane: {plane}; expected {axis_name}min or {axis_name}max")

    mesh_path = args.mesh
    output_path = args.output or args.mesh
    report_path = args.report or str(Path(output_path).with_suffix(".mirror_extrude.txt"))

    mesh = meshio.read(mesh_path)
    tetra_index = tetra_block_index(mesh)
    points = np.asarray(mesh.points[:, :3], dtype=float)
    cells = np.asarray(mesh.cells[tetra_index].data, dtype=np.int64)
    original_bounds_min = points.min(axis=0)
    original_bounds_max = points.max(axis=0)
    lengths = original_bounds_max - original_bounds_min
    if np.any(lengths <= 0.0):
        raise ValueError(f"Invalid mesh bounds for mirror extrusion: min={original_bounds_min}, max={original_bounds_max}")

    plane_value = float(original_bounds_min[axis] if plane.endswith("min") else original_bounds_max[axis])
    tolerance = tolerance_from_config(cfg, lengths)
    volume_tolerance = float(cfg.get("volume_tolerance", 1e-14))
    orient_positive = bool(cfg.get("orient_tets_positive", True))

    mirrored = mirror_points(points, axis, plane_value)
    combined_points, combined_cells, glued_nodes, appended_nodes = build_mirrored_connectivity(
        points, mirrored, cells, axis, plane_value, tolerance
    )
    compact_points, compact_cells, used_indices, cleanup = clean_cells(
        combined_points, combined_cells, volume_tolerance, orient_positive=orient_positive
    )

    cell_data = tetra_cell_data(
        mesh, tetra_index, len(cells), cleanup["first_keep_mask"], cleanup["second_keep_mask"]
    )
    cleanup.pop("first_keep_mask")
    cleanup.pop("second_keep_mask")

    out = meshio.Mesh(
        points=compact_points,
        cells={"tetra": compact_cells},
        cell_data=cell_data,
        field_data=mesh.field_data,
    )
    meshio.write(output_path, out)

    final_bounds_min = compact_points.min(axis=0)
    final_bounds_max = compact_points.max(axis=0)
    info = {
        "mesh": mesh_path,
        "output": output_path,
        "axis": axis_name,
        "plane": plane,
        "plane_value": plane_value,
        "merge_tolerance": tolerance,
        "volume_tolerance": volume_tolerance,
        "original_bounds_min": original_bounds_min.tolist(),
        "original_bounds_max": original_bounds_max.tolist(),
        "final_bounds_min": final_bounds_min.tolist(),
        "final_bounds_max": final_bounds_max.tolist(),
        "original_points": int(len(points)),
        "glued_plane_nodes": int(glued_nodes),
        "appended_mirrored_nodes": int(appended_nodes),
        "final_points": int(len(compact_points)),
        "original_tetrahedra": int(len(cells)),
        "mirrored_tetrahedra_before_cleanup": int(len(cells)),
        "combined_tetrahedra_before_cleanup": int(len(combined_cells)),
        "final_tetrahedra": int(len(compact_cells)),
        **cleanup,
    }
    write_report(report_path, info)
    print(f"Mirror-extruded mesh along {plane}; glued {glued_nodes} nodes; final tets: {len(compact_cells)}")
    print(f"Wrote mesh: {output_path}")
    print(f"Wrote report: {report_path}")


if __name__ == "__main__":
    main()
