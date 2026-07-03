# DOLFINx Mesh Packaging

This folder contains `package_dlfx_meshes.sh`, a helper script for collecting and zipping
the DOLFINx mesh files

- `dlfx_mesh.xdmf`
- `dlfx_mesh.h5`

from the binning result folders.

The script keeps each `xdmf`/`h5` pair together in one subfolder before zipping it. This is
important because `dlfx_mesh.xdmf` references the accompanying `dlfx_mesh.h5`.

## Basic Usage On The Cluster

Run from the `009-Binning-Variation-CT-Stiffness` directory:

```bash
./package_dlfx_meshes.sh
```

By default, the script uses:

```text
00_results
```

as source if that directory exists. This is the expected cluster case.

It writes the packaged files to:

```text
dlfx_meshes_for_sending/
```

The relevant outputs are:

```text
dlfx_meshes_for_sending/zips/
dlfx_meshes_for_sending/dlfx_mesh_manifest.csv
```

Each file in `zips/` contains exactly one mesh pair.

Temporary staging copies are removed at the end of a normal run.

## Usage With Explicit Paths

You can also pass a source directory and an output directory:

```bash
./package_dlfx_meshes.sh /path/to/00_results /path/to/output_folder
```

Example:

```bash
./package_dlfx_meshes.sh \
  /work/scratch/as12vapa/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness/00_results \
  /work/scratch/as12vapa/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness/dlfx_meshes_for_sending
```

## Local Downloaded Results

If `00_results` does not exist, the script falls back to:

```text
results/cases
```

This is useful after running `download_binning_results.sh` locally.

## Optional Combined Zip

By default, only individual per-case zip files are created. This is faster and usually
better for sending selected cases.

To also create one large combined archive, run:

```bash
CREATE_COMBINED_ZIP=1 ./package_dlfx_meshes.sh
```

This writes:

```text
dlfx_meshes_for_sending/dlfx_meshes_all.zip
```

The combined archive can be large and may take a while to create.

## Keeping The Staging Folder

The script uses a temporary staging folder internally:

```text
dlfx_meshes_for_sending/staging/
```

By default this folder is removed after the zip files are created. To keep it for
debugging, run:

```bash
KEEP_STAGING=1 ./package_dlfx_meshes.sh
```

## Manifest

The manifest file:

```text
dlfx_meshes_for_sending/dlfx_mesh_manifest.csv
```

contains one row per packaged mesh pair:

```text
package_name,source_xdmf,source_h5,zip_path
```

Use it to see which original result folder each zip file came from.

## Notes

- The script searches recursively for `dlfx_mesh.xdmf`.
- A mesh is only packaged if the matching `dlfx_mesh.h5` exists in the same folder.
- Existing `dlfx_meshes_for_sending/staging` and `dlfx_meshes_for_sending/zips` folders are recreated on each run.
- The staging folder is removed after a normal run unless `KEEP_STAGING=1` is set.
- The original result files are not modified.
