# DOLFINx Mesh Files

This directory contains packaged DOLFINx mesh files generated from XRM measurement data.

## Data Source

The underlying measurement data comes from High Seas:

```text
/iw-hypo/Messdaten XRM Hannover/B02_IW/B02_Mevert_AlSi10MgSchaum_JM-26-74_Binning_Variation
```

The specimen series is the Mevert AlSi10Mg foam binning variation dataset.

## Processing

The meshes were generated with the `pygalmesh` workflow in:

```text
009-Binning-Variation-CT-Stiffness
```

Processing steps:

- CT/XRM image stacks were converted to voxel arrays.
- The material phase was segmented with Otsu thresholding.
- The segmented 3D volumes were meshed with `pygalmesh`.
- The resulting meshes were converted to DOLFINx-compatible `xdmf`/`h5` files.

Each mesh package contains:

```text
dlfx_mesh.xdmf
dlfx_mesh.h5
```

Keep these two files in the same folder. The `.xdmf` file references the `.h5` file.

## Files

- `zips/`: individual zip archives, one archive per mesh.
- `dlfx_meshes_all.zip`: combined archive containing all mesh folders.
- `dlfx_mesh_manifest.csv`: mapping from package name to original mesh file paths.

## Reading A Mesh With meshio In Python

Install `meshio` if needed:

```bash
python3 -m pip install meshio
```

Read an XDMF mesh in Python:

```python
import meshio

mesh = meshio.read("dlfx_mesh.xdmf")

print(mesh.points.shape)
print(mesh.cells)
print(mesh.cell_data_dict)
```

For tetrahedral meshes, the tetrahedra can usually be accessed like this:

```python
import meshio

mesh = meshio.read("dlfx_mesh.xdmf")

points = mesh.points
tetra_cells = mesh.get_cells_type("tetra")

print("points:", points.shape)
print("tetrahedra:", tetra_cells.shape)
```

If the mesh contains physical or marker data, inspect available cell data:

```python
print(mesh.cell_data_dict.keys())
```

This directory also contains a small Python helper:

```bash
python3 read_xdmf_with_meshio.py path/to/dlfx_mesh.xdmf
```

Optionally write the mesh to VTK/VTU for inspection:

```bash
python3 read_xdmf_with_meshio.py path/to/dlfx_mesh.xdmf --write-vtk mesh.vtu
```

## Reading In DOLFINx

These files are intended for DOLFINx-style workflows. A typical DOLFINx read pattern is:

```python
from mpi4py import MPI
from dolfinx.io import XDMFFile

with XDMFFile(MPI.COMM_WORLD, "dlfx_mesh.xdmf", "r") as xdmf:
    mesh = xdmf.read_mesh(name="Grid")
```

Depending on how the mesh was written, cell tags or additional data may need to be read
separately.

## Notes

- The archives preserve the folder structure required for the `.xdmf` to find the `.h5`.
- Do not rename only one of the two mesh files unless the `.xdmf` reference is updated.
- The meshes were generated from Otsu-segmented voxel data, so mesh geometry reflects the segmented material phase rather than the raw gray-value image.
