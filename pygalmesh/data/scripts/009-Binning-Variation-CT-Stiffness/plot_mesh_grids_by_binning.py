#!/usr/bin/env python3
import argparse
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import h5py
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


CASE_RE = re.compile(r"^(.+)_Bin(?P<bin>[0-9]+)_reduce-(?P<reduce>[^_]+)_segmented$")
REDUCE_ORDER = ["null", "2", "4", "8"]
TET_FACES = np.array([[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]], dtype=np.int64)


def reduce_sort_key(value):
    return 1.0 if value == "null" else float(value)


def configure_matplotlib(output_dir):
    cache_dir = output_dir / ".matplotlib"
    xdg_cache_dir = output_dir / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    xdg_cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_dir))
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ.setdefault("XDG_CACHE_HOME", str(xdg_cache_dir))
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm

    return plt, cm


def dataitem_reference(xdmf_path, xdmf_tag):
    root = ET.parse(xdmf_path).getroot()
    data_item = root.find(f".//{xdmf_tag}/DataItem")
    if data_item is None or not data_item.text:
        raise ValueError(f"Could not find {xdmf_tag}/DataItem in {xdmf_path}")
    h5_name, dataset_name = data_item.text.strip().split(":", 1)
    return xdmf_path.parent / h5_name, dataset_name


def sorted_face_counts(faces):
    faces = np.sort(faces, axis=1)
    order = np.lexsort((faces[:, 2], faces[:, 1], faces[:, 0]))
    faces = faces[order]
    unique, counts = np.unique(faces, axis=0, return_counts=True)
    return unique.astype(np.int64, copy=False), counts.astype(np.uint32, copy=False)


def save_face_counts(path, faces, counts):
    np.savez_compressed(path, faces=faces, counts=counts)


def load_face_counts(path):
    data = np.load(path)
    return data["faces"], data["counts"]


def merge_face_count_files(left_path, right_path, output_path):
    left_faces, left_counts = load_face_counts(left_path)
    right_faces, right_counts = load_face_counts(right_path)
    faces = np.vstack([left_faces, right_faces])
    counts = np.concatenate([left_counts, right_counts])
    order = np.lexsort((faces[:, 2], faces[:, 1], faces[:, 0]))
    faces = faces[order]
    counts = counts[order]

    unique, inverse = np.unique(faces, axis=0, return_inverse=True)
    summed = np.zeros(len(unique), dtype=np.uint32)
    np.add.at(summed, inverse, counts)
    save_face_counts(output_path, unique, summed)


def exterior_faces_from_xdmf(xdmf_path, chunk_tets, max_tets, work_dir):
    h5_path, topology_dataset = dataitem_reference(xdmf_path, "Topology")
    chunk_files = []

    with h5py.File(h5_path, "r") as handle:
        topology = handle[topology_dataset]
        total_tets = topology.shape[0]
        tet_limit = total_tets if max_tets is None else min(total_tets, max_tets)
        for start in range(0, tet_limit, chunk_tets):
            stop = min(start + chunk_tets, tet_limit)
            tets = topology[start:stop, :].astype(np.int64, copy=False)
            faces = tets[:, TET_FACES].reshape(-1, 3)
            unique, counts = sorted_face_counts(faces)
            chunk_path = work_dir / f"faces_{len(chunk_files):05d}.npz"
            save_face_counts(chunk_path, unique, counts)
            chunk_files.append(chunk_path)
            print(f"    processed tetrahedra {start:,}-{stop:,} of {tet_limit:,}", flush=True)

    round_index = 0
    while len(chunk_files) > 1:
        next_files = []
        for index in range(0, len(chunk_files), 2):
            if index + 1 == len(chunk_files):
                next_files.append(chunk_files[index])
                continue
            merged_path = work_dir / f"merge_{round_index:03d}_{index // 2:05d}.npz"
            merge_face_count_files(chunk_files[index], chunk_files[index + 1], merged_path)
            chunk_files[index].unlink(missing_ok=True)
            chunk_files[index + 1].unlink(missing_ok=True)
            next_files.append(merged_path)
        chunk_files = next_files
        round_index += 1

    faces, counts = load_face_counts(chunk_files[0])
    return faces[counts == 1], total_tets, tet_limit


def load_surface_triangles(xdmf_path, chunk_tets, max_tets, max_render_faces, work_dir):
    h5_path, geometry_dataset = dataitem_reference(xdmf_path, "Geometry")
    boundary_faces, total_tets, used_tets = exterior_faces_from_xdmf(xdmf_path, chunk_tets, max_tets, work_dir)
    if len(boundary_faces) == 0:
        return np.empty((0, 3, 3)), np.empty((0, 3)), total_tets, used_tets, 0

    if len(boundary_faces) > max_render_faces:
        indices = np.linspace(0, len(boundary_faces) - 1, max_render_faces, dtype=np.int64)
        boundary_faces = boundary_faces[indices]

    vertex_ids = np.unique(boundary_faces.reshape(-1))
    with h5py.File(h5_path, "r") as handle:
        points = handle[geometry_dataset][vertex_ids, :]

    remapped = np.searchsorted(vertex_ids, boundary_faces)
    triangles = points[remapped]
    return triangles, points, total_tets, used_tets, len(boundary_faces)


def discover_meshes(results_dir):
    records = []
    for case_dir in sorted((results_dir / "cases").iterdir()):
        if not case_dir.is_dir():
            continue
        match = CASE_RE.match(case_dir.name)
        if not match:
            continue
        xdmf_files = sorted(case_dir.glob("*_3D/subvolume_*/dlfx_mesh.xdmf"))
        if not xdmf_files:
            continue
        records.append(
            {
                "case_name": case_dir.name,
                "bin": int(match.group("bin")),
                "reduce": match.group("reduce"),
                "xdmf": xdmf_files[0],
            }
        )
    return sorted(records, key=lambda row: (row["bin"], reduce_sort_key(row["reduce"])))


def set_equal_3d_axes(ax, bounds):
    mins, maxs = bounds
    center = (mins + maxs) / 2.0
    radius = np.max(maxs - mins) / 2.0
    radius = radius if radius > 0 else 1.0
    ax.set_xlim(center[0] - radius, center[0] + radius)
    ax.set_ylim(center[1] - radius, center[1] + radius)
    ax.set_zlim(center[2] - radius, center[2] + radius)
    ax.set_box_aspect((1, 1, 1))


def plot_surface(ax, triangles, title, bounds, elev, azim, cm):
    if len(triangles) == 0:
        ax.text2D(0.5, 0.5, "no exterior faces", transform=ax.transAxes, ha="center", va="center")
        return

    z_face = triangles[:, :, 2].mean(axis=1)
    z_norm = (z_face - z_face.min()) / max(float(z_face.max() - z_face.min()), 1e-12)
    collection = Poly3DCollection(triangles, linewidths=0.0, edgecolors="none", alpha=0.98)
    collection.set_facecolor(cm.viridis(z_norm))
    ax.add_collection3d(collection)
    ax.set_title(title, fontsize=10)
    set_equal_3d_axes(ax, bounds)
    ax.view_init(elev=elev, azim=azim)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("z")


def plot_bin_grid(bin_value, records, output_path, args):
    plt, cm = configure_matplotlib(output_path.parent)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(10, 9), constrained_layout=True)
    reduce_to_record = {record["reduce"]: record for record in records}
    previews = {}
    all_points = []

    with tempfile.TemporaryDirectory(prefix=f"xdmf_surface_bin{bin_value}_", dir=args.temp_dir) as temp_name:
        temp_dir = Path(temp_name)
        for reduce_value in REDUCE_ORDER:
            record = reduce_to_record.get(reduce_value)
            if record is None:
                continue
            print(f"  reconstructing XDMF exterior surface for Bin {bin_value} reduce={reduce_value}", flush=True)
            work_dir = temp_dir / f"reduce_{reduce_value}"
            work_dir.mkdir(parents=True, exist_ok=True)
            triangles, points, total_tets, used_tets, face_count = load_surface_triangles(
                record["xdmf"],
                chunk_tets=args.chunk_tets,
                max_tets=args.max_tets,
                max_render_faces=args.max_render_faces,
                work_dir=work_dir,
            )
            previews[reduce_value] = {
                "triangles": triangles,
                "points": points,
                "total_tets": total_tets,
                "used_tets": used_tets,
                "face_count": face_count,
            }
            if len(points):
                all_points.append(points)

    bounds = (np.vstack(all_points).min(axis=0), np.vstack(all_points).max(axis=0)) if all_points else (np.zeros(3), np.ones(3))
    for index, reduce_value in enumerate(REDUCE_ORDER, start=1):
        ax = fig.add_subplot(2, 2, index, projection="3d")
        preview = previews.get(reduce_value)
        if preview is None:
            ax.text2D(0.5, 0.5, f"reduce={reduce_value}\nmissing", transform=ax.transAxes, ha="center", va="center")
            ax.set_axis_off()
            continue
        mode = "full" if preview["used_tets"] == preview["total_tets"] else "preview"
        title = f"reduce={reduce_value}\n{preview['face_count']:,} exterior faces rendered ({mode})"
        plot_surface(ax, preview["triangles"], title, bounds, args.elev, args.azim, cm)

    fig.suptitle(f"JM-25-74 Bin {bin_value}: XDMF-Reconstructed Exterior Surface", fontsize=14)
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def main():
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Create 2x2 exterior-surface grids reconstructed from XDMF tetrahedral meshes.")
    parser.add_argument("--results-dir", type=Path, default=script_dir / "results")
    parser.add_argument("--output-dir", type=Path, default=script_dir / "results" / "plots" / "mesh_grids")
    parser.add_argument("--chunk-tets", type=int, default=200_000, help="Tetrahedra per exact surface-counting chunk.")
    parser.add_argument("--max-tets", type=int, default=None, help="Use only the first N tetrahedra for a faster preview. Default: full mesh.")
    parser.add_argument("--max-render-faces", type=int, default=30_000, help="Maximum exterior triangles drawn per subplot.")
    parser.add_argument("--temp-dir", type=Path, default=None, help="Temporary directory for external face-count files.")
    parser.add_argument("--elev", type=float, default=24.0)
    parser.add_argument("--azim", type=float, default=-48.0)
    args = parser.parse_args()

    records = discover_meshes(args.results_dir)
    if not records:
        raise SystemExit(f"No dlfx_mesh.xdmf files found below {args.results_dir / 'cases'}")

    for bin_value in sorted({record["bin"] for record in records}):
        bin_records = [record for record in records if record["bin"] == bin_value]
        output_path = args.output_dir / f"mesh_grid_Bin{bin_value}.png"
        print(f"Rendering Bin {bin_value} with {len(bin_records)} mesh(es)", flush=True)
        plot_bin_grid(bin_value, bin_records, output_path, args)
        print(f"Wrote mesh grid to {output_path}")


if __name__ == "__main__":
    main()
