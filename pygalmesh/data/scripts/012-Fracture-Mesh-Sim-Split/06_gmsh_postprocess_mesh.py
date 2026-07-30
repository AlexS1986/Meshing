#!/usr/bin/env python3
import argparse
import json
import shutil
import tempfile
from pathlib import Path

import gmsh
import meshio
import numpy as np


CELL_TAG_CANDIDATES = ("medit:ref", "tetgen:ref", "gmsh:physical", "gmsh:geometrical")


def load_config(config_path):
    with open(config_path, "r") as handle:
        config = json.load(handle)
    return config.get("06_gmsh_postprocess", {})


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
    suffix = ".pre_gmsh"
    backups = []
    for candidate in (mesh_path, mesh_path.with_suffix(".h5")):
        if candidate.exists():
            backup = candidate.with_name(candidate.stem + suffix + candidate.suffix)
            shutil.copy2(candidate, backup)
            backups.append(str(backup))
    return backups


def as_methods(value):
    if value is None:
        return ["Netgen"]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(part).strip() for part in value if str(part).strip()]


def main():
    parser = argparse.ArgumentParser(description="Run Gmsh optimization on an existing tetrahedral mesh.")
    parser.add_argument("--config", required=True, help="Path to config JSON containing optional 06_gmsh_postprocess settings")
    parser.add_argument("--mesh", required=True, help="Input mesh path, usually mesh.xdmf")
    parser.add_argument("--output", default=None, help="Output mesh path. Defaults to overwriting --mesh")
    parser.add_argument("--methods", default=None, help="Comma-separated Gmsh optimization methods, e.g. Netgen")
    parser.add_argument("--active-ref", type=int, default=None, help="Only keep tetrahedra with this cell tag value")
    parser.add_argument("--all-tets", action="store_true", help="Use all tetrahedra even if region tags are present")
    parser.add_argument("--binary-msh", action="store_true", help="Use binary temporary .msh files")
    args = parser.parse_args()

    cfg = load_config(args.config)
    mesh_path = Path(args.mesh)
    output_path = Path(args.output or cfg.get("output_mesh_path") or mesh_path)
    methods = as_methods(args.methods if args.methods is not None else cfg.get("methods", ["Netgen"]))
    active_ref = args.active_ref if args.active_ref is not None else cfg.get("active_ref", 1)
    all_tets = args.all_tets or bool(cfg.get("all_tets", False))
    binary_msh = args.binary_msh or bool(cfg.get("binary_msh", False))

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
    gmsh_input_mesh = meshio.Mesh(points, [("tetra", tetra_cells)])

    with tempfile.TemporaryDirectory(prefix="gmsh-postprocess-") as workdir_name:
        workdir = Path(workdir_name)
        input_msh = workdir / "mesh.msh"
        output_msh = workdir / "mesh_optimized.msh"
        meshio.write(input_msh, gmsh_input_mesh, file_format="gmsh22", binary=binary_msh)

        gmsh_log = []
        gmsh.initialize(["gmsh", "-nopopup"])
        try:
            gmsh.option.setNumber("General.Terminal", 1)
            gmsh.logger.start()
            gmsh.open(str(input_msh))
            for method in methods:
                print(f"Running Gmsh optimize: {method}")
                gmsh.model.mesh.optimize(method)
            gmsh.write(str(output_msh))
            gmsh_log = gmsh.logger.get()
            gmsh.logger.stop()
        finally:
            gmsh.finalize()

        log_path = output_path.with_suffix(".gmsh.log")
        log_path.write_text("\n".join(gmsh_log) + ("\n" if gmsh_log else ""))
        print(f"Gmsh log: {log_path}")

        optimized = meshio.read(output_msh)
        _, optimized_tets = find_tetra_block(optimized)
        out_mesh = meshio.Mesh(
            optimized.points[:, :3],
            [("tetra", optimized_tets)],
            cell_data={"medit:ref": [np.ones(len(optimized_tets), dtype=np.int32)]},
        )

        if output_path == mesh_path:
            backups = backup_mesh(mesh_path)
            if backups:
                print("Backed up original mesh files:")
                for backup in backups:
                    print(f"  {backup}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        meshio.write(output_path, out_mesh)
        print(f"Wrote Gmsh postprocessed mesh: {output_path}")
        print(f"Points: {len(optimized.points)}; tetrahedra: {len(optimized_tets)}")


if __name__ == "__main__":
    main()
