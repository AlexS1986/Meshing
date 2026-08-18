#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import meshio
import numpy as np


CELL_TAG_CANDIDATES = ("medit:ref", "tetgen:ref", "gmsh:physical", "gmsh:geometrical")


DEFAULT_CONFIG = {
    "enabled": False,
    "active_ref": 1,
    "all_tets": False,
    "volume_tolerance": 1.0e-14,
    "tiny_volume_absolute": 1.0e-12,
    "tiny_volume_relative_to_median": 1.0e-8,
    "face_area_tolerance": 1.0e-14,
    "write_boundary_surface": False,
    "repair": {
        "enabled": False,
        "drop_duplicate_tets": True,
        "drop_degenerate_tets": True,
        "drop_tiny_tets": False,
        "orient_tets_positive": True,
        "output_mesh_path": None,
    },
}


def deep_update(base, update):
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = value
    return base


def load_config(config_path):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if not config_path:
        return cfg
    with open(config_path, "r") as handle:
        full_config = json.load(handle)
    return deep_update(cfg, full_config.get("09_mesh_topology_audit", {}))


def find_tetra_block(mesh):
    for index, block in enumerate(mesh.cells):
        if block.type == "tetra":
            return index, np.asarray(block.data, dtype=np.int64)
    raise ValueError("No tetrahedral cells found in input mesh")


def find_tetra_tags(mesh, tetra_block_index):
    for tag_name in CELL_TAG_CANDIDATES:
        values_by_type = mesh.cell_data_dict.get(tag_name)
        if values_by_type and "tetra" in values_by_type:
            return tag_name, np.asarray(values_by_type["tetra"])

    for tag_name, blocks in mesh.cell_data.items():
        if tetra_block_index < len(blocks):
            values = np.asarray(blocks[tetra_block_index])
            if values.ndim == 1:
                return tag_name, values

    return None, None


def select_tetrahedra(mesh, active_ref, all_tets):
    tetra_block_index, tetra_cells = find_tetra_block(mesh)
    tag_name, tetra_tags = find_tetra_tags(mesh, tetra_block_index)
    if tetra_tags is not None and not all_tets:
        mask = tetra_tags == active_ref
        if not np.any(mask):
            raise ValueError(f"No tetrahedra found with {tag_name} == {active_ref}")
        return tetra_cells[mask], f"{int(mask.sum())} / {len(mask)} tetrahedra with {tag_name} == {active_ref}"
    return tetra_cells, f"all {len(tetra_cells)} tetrahedra"


def compact_mesh(points, tetra_cells):
    used = np.unique(tetra_cells.reshape(-1))
    remap = np.full(points.shape[0], -1, dtype=np.int64)
    remap[used] = np.arange(len(used), dtype=np.int64)
    return points[used, :3], remap[tetra_cells]


def tetra_signed_volumes(points, tets):
    a = points[tets[:, 0]]
    b = points[tets[:, 1]]
    c = points[tets[:, 2]]
    d = points[tets[:, 3]]
    return np.einsum("ij,ij->i", np.cross(b - a, c - a), d - a) / 6.0


def tetra_faces(tets):
    return np.vstack(
        (
            tets[:, [1, 2, 3]],
            tets[:, [0, 3, 2]],
            tets[:, [0, 1, 3]],
            tets[:, [0, 2, 1]],
        )
    )


def face_areas(points, faces):
    a = points[faces[:, 0]]
    b = points[faces[:, 1]]
    c = points[faces[:, 2]]
    return 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)


def boundary_edges(faces):
    edges = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [0, 2]]))
    edges.sort(axis=1)
    return edges


def count_components_from_faces(faces):
    if len(faces) == 0:
        return 0
    vertices = np.unique(faces.reshape(-1))
    parent = {int(v): int(v) for v in vertices}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        root_a = find(int(a))
        root_b = find(int(b))
        if root_a != root_b:
            parent[root_b] = root_a

    for face in faces:
        union(face[0], face[1])
        union(face[1], face[2])
    return len({find(int(v)) for v in vertices})


def optional_surface_checks(points, boundary_faces):
    checks = {
        "trimesh_available": False,
        "pyvista_available": False,
        "surface_watertight": None,
        "surface_winding_consistent": None,
        "self_intersection_check": "not_available",
    }
    try:
        import trimesh

        tri = trimesh.Trimesh(vertices=points, faces=boundary_faces, process=False)
        checks["trimesh_available"] = True
        checks["surface_watertight"] = bool(tri.is_watertight)
        checks["surface_winding_consistent"] = bool(tri.is_winding_consistent)
    except Exception as exc:
        checks["trimesh_error"] = str(exc)

    try:
        import pyvista  # noqa: F401

        checks["pyvista_available"] = True
    except Exception as exc:
        checks["pyvista_error"] = str(exc)

    return checks


def repair_tetrahedra(points, tets, cfg, volumes, duplicate_keep_mask, degenerate_mask, tiny_mask):
    repair_cfg = cfg["repair"]
    keep = np.ones(len(tets), dtype=bool)
    actions = []

    if repair_cfg.get("drop_duplicate_tets", True):
        keep &= duplicate_keep_mask
        actions.append(f"dropped_duplicate_tets={int((~duplicate_keep_mask).sum())}")
    if repair_cfg.get("drop_degenerate_tets", True):
        keep &= ~degenerate_mask
        actions.append(f"dropped_degenerate_tets={int(degenerate_mask.sum())}")
    if repair_cfg.get("drop_tiny_tets", False):
        keep &= ~tiny_mask
        actions.append(f"dropped_tiny_tets={int(tiny_mask.sum())}")

    repaired = tets[keep].copy()
    repaired_volumes = volumes[keep].copy()
    if repair_cfg.get("orient_tets_positive", True):
        flip = repaired_volumes < 0
        repaired[flip, 0], repaired[flip, 1] = repaired[flip, 1].copy(), repaired[flip, 0].copy()
        actions.append(f"oriented_negative_tets={int(flip.sum())}")

    repaired_points, repaired = compact_mesh(points, repaired)
    return repaired_points, repaired, actions


def classify(metrics, cfg):
    hard_failure_keys = (
        "duplicate_tetrahedra",
        "degenerate_tetrahedra",
        "nonmanifold_tetra_faces",
        "degenerate_boundary_faces",
        "open_boundary_edges",
        "nonmanifold_boundary_edges",
    )
    if any(metrics[key] > 0 for key in hard_failure_keys):
        return "bad"
    if metrics["tiny_tetrahedra"] > 0:
        return "acceptable"
    return "good"


def format_metric(value):
    if value is None:
        return "not_available"
    if isinstance(value, float):
        if value != 0.0 and abs(value) < 0.01:
            return f"{value:.4e}"
        return f"{value:.6g}"
    return str(value)


def write_report(output_path, mesh_path, selected_note, metrics, checks, verdict, repair_actions, repair_output):
    lines = [
        f"Mesh topology verdict: {verdict}",
        f"Mesh: {mesh_path}",
        f"Selection: {selected_note}",
        "",
        "Tetrahedral topology:",
        f"  points: {metrics['points']}",
        f"  tetrahedra: {metrics['tetrahedra']}",
        f"  duplicate_tetrahedra: {metrics['duplicate_tetrahedra']}",
        f"  degenerate_tetrahedra: {metrics['degenerate_tetrahedra']}",
        f"  tiny_tetrahedra: {metrics['tiny_tetrahedra']}",
        f"  negative_orientation_tetrahedra: {metrics['negative_orientation_tetrahedra']}",
        f"  smallest_abs_volume: {format_metric(metrics['smallest_abs_volume'])}",
        f"  median_abs_volume: {format_metric(metrics['median_abs_volume'])}",
        f"  tiny_volume_limit: {format_metric(metrics['tiny_volume_limit'])}",
        f"  nonmanifold_tetra_faces: {metrics['nonmanifold_tetra_faces']}",
        "",
        "Boundary surface topology:",
        f"  boundary_faces: {metrics['boundary_faces']}",
        f"  degenerate_boundary_faces: {metrics['degenerate_boundary_faces']}",
        f"  boundary_edges: {metrics['boundary_edges']}",
        f"  open_boundary_edges: {metrics['open_boundary_edges']}",
        f"  nonmanifold_boundary_edges: {metrics['nonmanifold_boundary_edges']}",
        f"  boundary_components: {metrics['boundary_components']}",
        "",
        "Optional surface checks:",
        f"  trimesh_available: {checks.get('trimesh_available')}",
        f"  pyvista_available: {checks.get('pyvista_available')}",
        f"  surface_watertight: {checks.get('surface_watertight')}",
        f"  surface_winding_consistent: {checks.get('surface_winding_consistent')}",
        f"  self_intersection_check: {checks.get('self_intersection_check')}",
        "",
        "Repair:",
    ]
    if repair_actions:
        lines.extend(f"  {action}" for action in repair_actions)
        lines.append(f"  output_mesh: {repair_output}")
    else:
        lines.append("  not_run")

    lines.extend(
        [
            "",
            "Repair guidance:",
            "  duplicate/degenerate/tiny tetrahedra can be removed mechanically, but this may create holes if many elements are removed.",
            "  negative tetra orientation can be fixed by swapping two local vertex indices.",
            "  open or non-manifold boundary edges usually require remeshing from a cleaner surface or voxel mask.",
            "  true surface self-intersections are best repaired before tetrahedralization, using surface repair/remeshing tools rather than editing the tetra mesh blindly.",
            "",
        ]
    )
    output_path.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Audit tetra mesh topology and boundary manifoldness.")
    parser.add_argument("--config", default=None, help="Optional config JSON containing 09_mesh_topology_audit")
    parser.add_argument("--mesh", required=True, help="Input tetrahedral mesh path")
    parser.add_argument("--output", default=None, help="Output topology report path")
    parser.add_argument("--repair-output", default=None, help="Write a mechanically repaired tetra mesh to this path")
    parser.add_argument("--active-ref", type=int, default=None, help="Only keep tetrahedra with this cell tag value")
    parser.add_argument("--all-tets", action="store_true", help="Use all tetrahedra even if region tags are present")
    args = parser.parse_args()

    cfg = load_config(args.config)
    mesh_path = Path(args.mesh)
    output_path = Path(args.output) if args.output else mesh_path.with_suffix(".topology.txt")
    active_ref = args.active_ref if args.active_ref is not None else cfg["active_ref"]
    all_tets = args.all_tets or bool(cfg["all_tets"])

    mesh = meshio.read(mesh_path)
    points = mesh.points[:, :3]
    tets, selected_note = select_tetrahedra(mesh, active_ref, all_tets)

    sorted_tets = np.sort(tets, axis=1)
    _, first_indices, duplicate_inverse, duplicate_counts = np.unique(
        sorted_tets,
        axis=0,
        return_index=True,
        return_inverse=True,
        return_counts=True,
    )
    duplicate_keep_mask = np.zeros(len(tets), dtype=bool)
    duplicate_keep_mask[first_indices] = True
    duplicate_tetrahedra = int(np.sum(duplicate_counts[duplicate_inverse] > 1) - np.sum(duplicate_counts > 1))

    volumes = tetra_signed_volumes(points, tets)
    abs_volumes = np.abs(volumes)
    median_volume = float(np.median(abs_volumes)) if len(abs_volumes) else 0.0
    tiny_limit = max(float(cfg["tiny_volume_absolute"]), median_volume * float(cfg["tiny_volume_relative_to_median"]))
    degenerate_mask = abs_volumes <= float(cfg["volume_tolerance"])
    tiny_mask = (abs_volumes > float(cfg["volume_tolerance"])) & (abs_volumes <= tiny_limit)

    faces = tetra_faces(tets)
    sorted_faces = np.sort(faces, axis=1)
    unique_faces, unique_face_indices, face_counts = np.unique(
        sorted_faces,
        axis=0,
        return_index=True,
        return_counts=True,
    )
    boundary_faces = faces[unique_face_indices[face_counts == 1]]
    nonmanifold_tetra_faces = int(np.sum(face_counts > 2))

    boundary_face_areas = face_areas(points, boundary_faces) if len(boundary_faces) else np.array([])
    degenerate_boundary_faces = int(np.sum(boundary_face_areas <= float(cfg["face_area_tolerance"])))

    edges = boundary_edges(boundary_faces) if len(boundary_faces) else np.empty((0, 2), dtype=np.int64)
    unique_edges, edge_counts = np.unique(edges, axis=0, return_counts=True) if len(edges) else (np.empty((0, 2), dtype=np.int64), np.array([], dtype=np.int64))
    open_boundary_edges = int(np.sum(edge_counts == 1))
    nonmanifold_boundary_edges = int(np.sum(edge_counts > 2))

    metrics = {
        "points": int(len(points)),
        "tetrahedra": int(len(tets)),
        "duplicate_tetrahedra": duplicate_tetrahedra,
        "degenerate_tetrahedra": int(np.sum(degenerate_mask)),
        "tiny_tetrahedra": int(np.sum(tiny_mask)),
        "negative_orientation_tetrahedra": int(np.sum(volumes < 0.0)),
        "smallest_abs_volume": float(np.min(abs_volumes)) if len(abs_volumes) else None,
        "median_abs_volume": median_volume,
        "tiny_volume_limit": tiny_limit,
        "nonmanifold_tetra_faces": nonmanifold_tetra_faces,
        "boundary_faces": int(len(boundary_faces)),
        "degenerate_boundary_faces": degenerate_boundary_faces,
        "boundary_edges": int(len(unique_edges)),
        "open_boundary_edges": open_boundary_edges,
        "nonmanifold_boundary_edges": nonmanifold_boundary_edges,
        "boundary_components": count_components_from_faces(boundary_faces),
    }
    checks = optional_surface_checks(points, boundary_faces)
    verdict = classify(metrics, cfg)

    repair_actions = []
    repair_output = None
    repair_output_cfg = cfg["repair"].get("output_mesh_path")
    repair_requested = bool(cfg["repair"].get("enabled", False)) or args.repair_output
    if repair_requested:
        repair_output = Path(args.repair_output or repair_output_cfg or mesh_path.with_name(mesh_path.stem + "_topology_repaired.xdmf"))
        repaired_points, repaired_tets, repair_actions = repair_tetrahedra(
            points,
            tets,
            cfg,
            volumes,
            duplicate_keep_mask,
            degenerate_mask,
            tiny_mask,
        )
        repaired_mesh = meshio.Mesh(
            repaired_points,
            [("tetra", repaired_tets)],
            cell_data={"medit:ref": [np.ones(len(repaired_tets), dtype=np.int32)]},
        )
        repair_output.parent.mkdir(parents=True, exist_ok=True)
        meshio.write(repair_output, repaired_mesh)

    if cfg.get("write_boundary_surface", False):
        surface_path = output_path.with_suffix(".boundary_surface.xdmf")
        surface_mesh = meshio.Mesh(points, [("triangle", boundary_faces)])
        meshio.write(surface_path, surface_mesh)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_report(output_path, mesh_path, selected_note, metrics, checks, verdict, repair_actions, repair_output)
    print(f"Wrote mesh topology audit: {output_path}")
    print(f"Mesh topology verdict: {verdict}")
    if repair_output:
        print(f"Wrote topology repair mesh: {repair_output}")


if __name__ == "__main__":
    main()
