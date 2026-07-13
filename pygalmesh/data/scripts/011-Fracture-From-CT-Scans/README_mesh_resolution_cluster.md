# Coarse, medium, and fine DOLFINx meshes on the cluster

The SLURM array job creates the complete meshing pipeline output through
`dlfx_mesh.xdmf` and then stops. It does not start a fracture simulation.
Each task requests 8 processes and has a maximum runtime of 1440 minutes. The
DOLFINx conversion runs on all 8 MPI ranks; the Pygalmesh generation stage is
serial in the existing pipeline.

The job does not read the original DICOM files. It reuses the existing
`volume.npy` from the `011` working tree below `$HPC_SCRATCH`, then runs only
the voxel transformations, meshing, mesh postprocessing, and DOLFINx
conversion. By default it searches these sources in order:

```text
$HPC_SCRATCH/pygalmesh/data/scripts/011-Fracture-From-CT-Scans/JM-25-74_Bin4_reduce-2_segmented/JM-25-74_Bin4_reduce-2_segmented_3D/subvolume_x52_y74/volume.npy
$HPC_SCRATCH/pygalmesh/data/scripts/011-Fracture-From-CT-Scans/00_results/JM-25-74_Bin4_reduce-2_segmented_cluster_fine/JM-25-74_Bin4_reduce-2_segmented_cluster_fine_3D/subvolume_x52_y74/volume.npy
```

An alternative scratch subvolume can be selected at submission time:

```bash
MESH_SOURCE_SUBVOLUME_DIR=/absolute/scratch/path/subvolume_x52_y74 \
  sbatch job_generate_dlfx_mesh_Bin4_reduce_2_CLUSTER.sh
```

The three independent configurations are generated from
`config-Bin4-reduce-2-cluster-fine.json` by
`create_mesh_resolution_configs.py`:

| Resolution | `max_element_size_factor` | `max_facet_distance_factor` |
| --- | ---: | ---: |
| coarse | 1.0 | 0.3 |
| medium | 0.75 | 0.2 |
| fine | 0.5 | 0.1 |

Separate resolved configs are useful because every resolution gets its own
specimen/output directory and cannot overwrite another mesh. The generator is
the single place where the resolution values are maintained.

Before synchronizing to cluster scratch, regenerate the configs if the table
in the generator was changed:

```bash
python3 create_mesh_resolution_configs.py
```

After running `02_create_folders_CLUSTER.sh`, submit all three resolutions:

```bash
cd "$HPC_SCRATCH/pygalmesh/data/scripts/011-Fracture-From-CT-Scans"
sbatch job_generate_dlfx_mesh_Bin4_reduce_2_CLUSTER.sh
```

The array is limited to one active task (`0-2%1`) so the shared DICOM-to-NPY
preprocessing directory is not written concurrently. To submit only one
resolution, select its array index:

```bash
sbatch --array=0 job_generate_dlfx_mesh_Bin4_reduce_2_CLUSTER.sh  # coarse
sbatch --array=1 job_generate_dlfx_mesh_Bin4_reduce_2_CLUSTER.sh  # medium
sbatch --array=2 job_generate_dlfx_mesh_Bin4_reduce_2_CLUSTER.sh  # fine
```

The resulting meshes are written below the respective directories:

```text
JM-25-74_Bin4_reduce-2_segmented_mesh_coarse/.../dlfx_mesh.xdmf
JM-25-74_Bin4_reduce-2_segmented_mesh_medium/.../dlfx_mesh.xdmf
JM-25-74_Bin4_reduce-2_segmented_mesh_fine/.../dlfx_mesh.xdmf
```
