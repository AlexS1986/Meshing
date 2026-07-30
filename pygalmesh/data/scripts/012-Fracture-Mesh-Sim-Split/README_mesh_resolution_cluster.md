# Coarse, medium, and fine DOLFINx meshes on the cluster

The SLURM array job creates the complete meshing pipeline output through
`dlfx_mesh.xdmf`, then archives only `dlfx_mesh.xdmf`/`.h5` (per subvolume)
under `data/resources/generated_meshes/` -- intermediate voxel arrays, QA
reports, and cross-section previews are left under the working directory,
not archived. It does not start a fracture simulation
-- that is `job_run_simulation_CLUSTER.sh` (or one of the
`job_run_simulation_Bin4_reduce_2_{coarse,medium,fine}_CLUSTER.sh` wrappers),
a separate job, run afterwards against the archived mesh. Each task requests
32 processes and has a maximum runtime of 1440 minutes. The individual
preprocessing, meshing, postprocessing, and DOLFINx-conversion commands each
run with one `srun` task, exactly as in `job_generate_mesh_CLUSTER.sh`.

Apart from the intentionally reduced runtime, the array uses the established
mesh-generation-job resources: partition `mem`, one node, 15000 MB per task,
and constraint `m01&mem1536g`.

The job runs the full preprocessing and meshing pipeline: DICOM conversion,
segmentation, 3D volume and subvolume creation, voxel transformations,
Pygalmesh generation, mesh postprocessing, and DOLFINx conversion. It stops
immediately before the fracture simulation.

The JSON configs continue to use this container path:

```text
/data/resources/B02_Mevert_AlSi10MgSchaum_JM-26-74_Binning_Variation/Binning 4/JM-25-74_6min15_750^C_erodiert_nach Trockenschrank_Bin4/DICOMDIR
```

The cluster script locates the corresponding host resource directory in this
order and binds it read-only to `/data/resources`:

1. `$HPC_RESOURCE_DIR`, when explicitly set.
2. `$HPC_SCRATCH/pygalmesh/data/resources`.
3. `$HPC_SCRATCH/resources`.
4. `$HOME/meshing/Meshing/pygalmesh/data/resources`.

If the data is stored elsewhere, submit with its resource root:

```bash
HPC_RESOURCE_DIR=/absolute/scratch/path/to/resources \
  sbatch job_generate_mesh_Bin4_reduce_2_CLUSTER.sh
```

The "coarse" tier is `config-Bin4-reduce-2-cluster-fine.json` itself --
the pre-existing baseline (max_element_size_factor=3.0 /
max_facet_distance_factor=1.0) you already had before this resolution
family existed. It is used directly, not regenerated. Only "medium" and
"fine" are new configs, generated from that same baseline by
`create_mesh_resolution_configs.py`, scaling it down proportionally:

| Resolution | `max_element_size_factor` | `max_facet_distance_factor` | Config file |
| --- | ---: | ---: | --- |
| coarse | 3.0 | 1.0 | `config-Bin4-reduce-2-cluster-fine.json` (pre-existing) |
| medium | 2.25 | 0.67 | `config-Bin4-reduce-2-mesh-medium.json` (generated) |
| fine | 1.5 | 0.33 | `config-Bin4-reduce-2-mesh-fine.json` (generated) |

Both `03_mesh_3D_array.pygalmesh_parameters` and
`03_mesh_3D_array.sdf_pygalmesh_parameters.pygalmesh_parameters` are set to
the same values -- the latter is what's actually read when
`meshing_method = sdf_pygalmesh` (the active method), the former is kept in
sync in case a config ever switches methods.

Separate resolved configs are useful because every resolution gets its own
specimen/output directory and cannot overwrite another mesh. The generator is
the single place where the medium/fine resolution values are maintained.

Before synchronizing to cluster scratch, regenerate the medium/fine configs
if the table in the generator was changed (this never touches
`config-Bin4-reduce-2-cluster-fine.json`, the coarse tier):

```bash
python3 create_mesh_resolution_configs.py
```

After running `02_create_folders_CLUSTER.sh`, submit all three resolutions:

```bash
cd "$HPC_SCRATCH/pygalmesh/data/scripts/012-Fracture-Mesh-Sim-Split"
sbatch job_generate_mesh_Bin4_reduce_2_CLUSTER.sh
```

The array is limited to one active task (`0-2%1`) so the shared DICOM-to-NPY
preprocessing directory is not written concurrently. To submit only one
resolution, select its array index:

```bash
sbatch --array=0 job_generate_mesh_Bin4_reduce_2_CLUSTER.sh  # coarse
sbatch --array=1 job_generate_mesh_Bin4_reduce_2_CLUSTER.sh  # medium
sbatch --array=2 job_generate_mesh_Bin4_reduce_2_CLUSTER.sh  # fine
```

The resulting meshes are written below the respective working directories,
then archived to `data/resources/generated_meshes/<specimen>/<binning_label>/<run_name>/`
(run_name is each tier's `specimen_name`, so the three tiers never
overwrite each other):

```text
JM-25-74_Bin4_reduce-2_segmented_cluster_fine/.../dlfx_mesh.xdmf   (coarse)
JM-25-74_Bin4_reduce-2_segmented_mesh_medium/.../dlfx_mesh.xdmf
JM-25-74_Bin4_reduce-2_segmented_mesh_fine/.../dlfx_mesh.xdmf

data/resources/generated_meshes/JM-25-74/Bin4/JM-25-74_Bin4_reduce-2_segmented_cluster_fine/.../dlfx_mesh.xdmf   (coarse)
data/resources/generated_meshes/JM-25-74/Bin4/JM-25-74_Bin4_reduce-2_segmented_mesh_medium/.../dlfx_mesh.xdmf
data/resources/generated_meshes/JM-25-74/Bin4/JM-25-74_Bin4_reduce-2_segmented_mesh_fine/.../dlfx_mesh.xdmf
```

The coarse tier's directory name still says "cluster_fine" -- that's the
original name from before the medium/fine tiers existed, kept as-is so it
lines up with any mesh you already generated under that config.

Run the matching simulation wrapper against each archived mesh:

```bash
sbatch job_run_simulation_Bin4_reduce_2_coarse_CLUSTER.sh
sbatch job_run_simulation_Bin4_reduce_2_medium_CLUSTER.sh
sbatch job_run_simulation_Bin4_reduce_2_fine_CLUSTER.sh
```

Each just calls `job_run_simulation_CLUSTER.sh` with the matching config, so
none of the preprocessing/meshing steps above are repeated. For any other
config, call `job_run_simulation_CLUSTER.sh config-file.json` directly.
