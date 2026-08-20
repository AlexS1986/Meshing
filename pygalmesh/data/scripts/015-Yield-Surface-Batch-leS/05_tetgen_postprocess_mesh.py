#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import meshio
import numpy as np


CELL_TAG_CANDIDATES = ("medit:ref", "tetgen:ref", "gmsh:physical", "gmsh:geometrical")


def load_config(config_path):
    with open(config_path, "r") as handle:
        config = json.load(handle)
    return config.get("05_tetgen_postprocess", {})


def find_tetra_block(mesh):
    for index, block in enumerate(mesh.cells):
        if block.type == "tetra":
            return index, block.data
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


def compact_tetra_mesh(points, tetra_cells):
    used = np.unique(tetra_cells.reshape(-1))
    remap = np.full(points.shape[0], -1, dtype=np.int64)
    remap[used] = np.arange(used.shape[0], dtype=np.int64)
    return points[used, :3], remap[tetra_cells]


def backup_mesh(mesh_path):
    mesh_path = Path(mesh_path)
    suffix = ".pre_tetgen"
    backups = []
    for candidate in (mesh_path, mesh_path.with_suffix(".h5")):
        if candidate.exists():
            backup = candidate.with_name(candidate.stem + suffix + candidate.suffix)
            shutil.copy2(candidate, backup)
            backups.append(str(backup))
    return backups


def normalize_switches(switches):
    switches = switches.strip()
    if not switches:
        switches = "-rCV"
    if not switches.startswith("-"):
        switches = "-" + switches
    if "r" not in switches[1:]:
        switches = switches[:1] + "r" + switches[1:]
    return switches


def main():
    parser = argparse.ArgumentParser(description="Run TetGen check/optimization/refinement on an existing tetrahedral mesh.")
    parser.add_argument("--config", required=True, help="Path to config JSON containing optional 05_tetgen_postprocess settings")
    parser.add_argument("--mesh", required=True, help="Input mesh path, usually mesh.xdmf")
    parser.add_argument("--output", default=None, help="Output mesh path. Defaults to overwriting --mesh")
    parser.add_argument("--switches", default=None, help="TetGen switches, e.g. -rCV, -rO2CV, -rq2.0/0O2CV")
    parser.add_argument("--active-ref", type=int, default=None, help="Only keep tetrahedra with this cell tag value")
    parser.add_argument("--all-tets", action="store_true", help="Use all tetrahedra even if region tags are present")
    parser.add_argument("--keep-workdir", action="store_true", help="Keep temporary TetGen files for debugging")
    args = parser.parse_args()

    cfg = load_config(args.config)
    mesh_path = Path(args.mesh)
    output_path = Path(args.output or cfg.get("output_mesh_path") or mesh_path)
    switches = normalize_switches(args.switches or cfg.get("switches", "-rCV"))
    active_ref = args.active_ref if args.active_ref is not None else cfg.get("active_ref", 1)
    all_tets = args.all_tets or bool(cfg.get("all_tets", False))

    print(f"Reading mesh: {mesh_path}")
    mesh = meshio.read(mesh_path)
    tetra_block_index, tetra_cells = find_tetra_block(mesh)
    tag_name, tetra_tags = find_tetra_tags(mesh, tetra_block_index)

    if tetra_tags is not None and not all_tets:
        mask = tetra_tags == active_ref
        if not np.any(mask):
            raise ValueError(f"No tetrahedra found with {tag_name} == {active_ref}")
        print(f"Using {int(mask.sum())} / {len(mask)} tetrahedra with {tag_name} == {active_ref}")
        tetra_cells = tetra_cells[mask]
    else:
        print(f"Using all {len(tetra_cells)} tetrahedra")

    points, tetra_cells = compact_tetra_mesh(mesh.points, tetra_cells)
    tetgen_mesh = meshio.Mesh(points, [("tetra", tetra_cells)])

    tmp_context = tempfile.TemporaryDirectory(prefix="tetgen-postprocess-")
    workdir = Path(tmp_context.name)
    try:
        base = workdir / "mesh"
        meshio.write(str(base.with_suffix(".node")), tetgen_mesh, file_format="tetgen")
        print(f"Running: tetgen {switches} {base}")
        result = subprocess.run(
            ["tetgen", switches, str(base)],
            cwd=workdir,
            text=True,
            capture_output=True,
            check=False,
        )

        log_path = output_path.with_suffix(".tetgen.log")
        log_path.write_text(result.stdout + ("\n--- stderr ---\n" + result.stderr if result.stderr else ""))
        print(f"TetGen log: {log_path}")
        if result.returncode != 0:
            raise RuntimeError(f"TetGen failed with exit code {result.returncode}; see {log_path}")

        output_node = base.with_name(base.name + ".1.node")
        if not output_node.exists():
            raise FileNotFoundError(f"TetGen did not write expected output: {output_node}")

        refined = meshio.read(str(output_node), file_format="tetgen")
        _, refined_tets = find_tetra_block(refined)
        out_mesh = meshio.Mesh(
            refined.points[:, :3],
            [("tetra", refined_tets)],
            cell_data={"medit:ref": [np.ones(len(refined_tets), dtype=np.int32)]},
        )

        if output_path == mesh_path:
            backups = backup_mesh(mesh_path)
            if backups:
                print("Backed up original mesh files:")
                for backup in backups:
                    print(f"  {backup}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        meshio.write(output_path, out_mesh)
        print(f"Wrote TetGen postprocessed mesh: {output_path}")
        print(f"Points: {len(refined.points)}; tetrahedra: {len(refined_tets)}")

        if args.keep_workdir or cfg.get("keep_workdir", False):
            print(f"Keeping TetGen workdir: {workdir}")
            tmp_context = None
    finally:
        if tmp_context is not None:
            tmp_context.cleanup()


if __name__ == "__main__":
    main()
