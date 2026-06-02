#!/usr/bin/env python3
import argparse
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import h5py
import numpy as np
import pyvista as pv


CASE_RE = re.compile(r"^(.+)_Bin(?P<bin>[0-9]+)_reduce-(?P<reduce>[^_]+)_segmented$")
REDUCE_ORDER = ["null", "2", "4", "8"]
BIN_COLORS = {
    1: "#4c78a8",
    2: "#59a14f",
    4: "#e15759",
}


def reduce_sort_key(value):
    return 1.0 if value == "null" else float(value)


def dataitem_reference(xdmf_path, xdmf_tag):
    root = ET.parse(xdmf_path).getroot()
    data_item = root.find(f".//{xdmf_tag}/DataItem")
    if data_item is None or not data_item.text:
        raise ValueError(f"Could not find {xdmf_tag}/DataItem in {xdmf_path}")
    h5_name, dataset_name = data_item.text.strip().split(":", 1)
    return xdmf_path.parent / h5_name, dataset_name


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


def load_full_tetra_grid(xdmf_path):
    geometry_h5, geometry_dataset = dataitem_reference(xdmf_path, "Geometry")
    topology_h5, topology_dataset = dataitem_reference(xdmf_path, "Topology")
    if geometry_h5 != topology_h5:
        raise ValueError(f"Expected geometry and topology in same HDF5 file for {xdmf_path}")

    with h5py.File(geometry_h5, "r") as handle:
        points = np.asarray(handle[geometry_dataset][:], dtype=np.float64)
        topology = np.asarray(handle[topology_dataset][:], dtype=np.int64)

    cells = np.empty((topology.shape[0], 5), dtype=np.int64)
    cells[:, 0] = 4
    cells[:, 1:] = topology
    cell_types = np.full(topology.shape[0], pv.CellType.TETRA, dtype=np.uint8)
    return pv.UnstructuredGrid(cells.ravel(), cell_types, points)


def camera_from_bounds(bounds):
    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    center = np.array([(xmin + xmax) / 2.0, (ymin + ymax) / 2.0, (zmin + zmax) / 2.0])
    span = np.array([xmax - xmin, ymax - ymin, zmax - zmin])
    radius = max(float(span.max()), 1.0)
    position = center + np.array([1.55 * radius, -2.1 * radius, 0.75 * radius])
    return [tuple(position), tuple(center), (0.0, 0.0, 1.0)]


def merged_bounds(meshes):
    bounds = np.array([mesh.bounds for mesh in meshes if mesh is not None], dtype=float)
    return (
        bounds[:, 0].min(),
        bounds[:, 1].max(),
        bounds[:, 2].min(),
        bounds[:, 3].max(),
        bounds[:, 4].min(),
        bounds[:, 5].max(),
    )


def add_missing_panel(plotter, row, col, reduce_value):
    plotter.subplot(row, col)
    plotter.add_text(f"reduce={reduce_value}\nmissing", position="upper_edge", font_size=13, color="black")


def plot_bin_grid(bin_value, records, output_path, show_internal=False):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")
    pv.OFF_SCREEN = True

    reduce_to_record = {record["reduce"]: record for record in records}
    meshes = {}
    counts = {}

    for reduce_value in REDUCE_ORDER:
        record = reduce_to_record.get(reduce_value)
        if record is None:
            continue

        print(f"  loading full XDMF tetra mesh for Bin {bin_value} reduce={reduce_value}", flush=True)
        grid = load_full_tetra_grid(record["xdmf"])
        counts[reduce_value] = (grid.n_cells, grid.n_points)
        if show_internal:
            meshes[reduce_value] = grid
        else:
            print(f"  extracting exterior surface for Bin {bin_value} reduce={reduce_value}", flush=True)
            meshes[reduce_value] = grid.extract_surface(nonlinear_subdivision=0).clean()
        del grid

    plotter = pv.Plotter(off_screen=True, shape=(2, 2), window_size=(2600, 2200), border=False)
    plotter.set_background("white")
    camera = camera_from_bounds(merged_bounds(list(meshes.values()))) if meshes else None
    color = BIN_COLORS.get(bin_value, "#8fb7c9")

    for index, reduce_value in enumerate(REDUCE_ORDER):
        row = 0 if index < 2 else 1
        col = index % 2
        mesh = meshes.get(reduce_value)
        if mesh is None:
            add_missing_panel(plotter, row, col, reduce_value)
            continue

        n_cells, n_points = counts[reduce_value]
        plotter.subplot(row, col)
        plotter.add_mesh(
            mesh,
            color=color,
            show_edges=False,
            smooth_shading=True,
            opacity=0.22 if show_internal else 1.0,
            specular=0.12,
            roughness=0.7,
        )
        plotter.add_text(
            f"reduce={reduce_value}\n{n_cells:,} tetrahedra, {n_points:,} nodes",
            position="upper_edge",
            font_size=11,
            color="black",
        )
        plotter.show_bounds(grid=False, location="outer", xtitle="x", ytitle="y", ztitle="z", font_size=8)
        if camera is not None:
            plotter.camera_position = camera
            plotter.camera.zoom(1.12)

    plotter.link_views()
    mode = "Full Tetrahedra" if show_internal else "Full Exterior Surface from All Tetrahedra"
    plotter.add_title(f"JM-25-74 Bin {bin_value}: {mode}", font_size=18, color="black")
    plotter.screenshot(str(output_path))
    plotter.close()


def main():
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Plot full XDMF tetrahedral meshes with uniform colors.")
    parser.add_argument("--results-dir", type=Path, default=script_dir / "results")
    parser.add_argument("--output-dir", type=Path, default=script_dir / "results" / "plots" / "mesh_grids_full")
    parser.add_argument("--bin", type=int, choices=[1, 2, 4], help="Render only one binning.")
    parser.add_argument("--show-internal", action="store_true", help="Render tetrahedral volume transparently instead of exterior surface.")
    args = parser.parse_args()

    records = discover_meshes(args.results_dir)
    if args.bin is not None:
        records = [record for record in records if record["bin"] == args.bin]
    if not records:
        raise SystemExit(f"No dlfx_mesh.xdmf files found below {args.results_dir / 'cases'}")

    for bin_value in sorted({record["bin"] for record in records}):
        bin_records = [record for record in records if record["bin"] == bin_value]
        suffix = "_internal" if args.show_internal else ""
        output_path = args.output_dir / f"mesh_grid_Bin{bin_value}_full{suffix}.png"
        print(f"Rendering Bin {bin_value} with {len(bin_records)} full mesh(es)", flush=True)
        plot_bin_grid(bin_value, bin_records, output_path, show_internal=args.show_internal)
        print(f"Wrote full mesh grid to {output_path}")


if __name__ == "__main__":
    main()
