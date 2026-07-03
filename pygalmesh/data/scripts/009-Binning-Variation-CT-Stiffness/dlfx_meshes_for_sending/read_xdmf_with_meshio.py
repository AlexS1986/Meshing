#!/usr/bin/env python3
import argparse
from pathlib import Path

import meshio


def main():
    parser = argparse.ArgumentParser(description="Read a DOLFINx XDMF mesh with meshio.")
    parser.add_argument("xdmf", type=Path, help="Path to dlfx_mesh.xdmf")
    parser.add_argument(
        "--write-vtk",
        type=Path,
        help="Optional output path for writing the mesh as VTK, e.g. mesh.vtu",
    )
    args = parser.parse_args()

    mesh = meshio.read(args.xdmf)

    print(f"Mesh file: {args.xdmf}")
    print(f"Number of points: {len(mesh.points)}")
    print("Cell blocks:")
    for block in mesh.cells:
        print(f"  {block.type}: {len(block.data)}")

    tetra = mesh.get_cells_type("tetra")
    if len(tetra):
        print(f"Tetrahedra array shape: {tetra.shape}")

    if mesh.cell_data_dict:
        print("Cell data:")
        for data_name, by_cell_type in mesh.cell_data_dict.items():
            print(f"  {data_name}: {list(by_cell_type)}")
    else:
        print("Cell data: none")

    if args.write_vtk:
        mesh.write(args.write_vtk)
        print(f"Wrote {args.write_vtk}")


if __name__ == "__main__":
    main()
