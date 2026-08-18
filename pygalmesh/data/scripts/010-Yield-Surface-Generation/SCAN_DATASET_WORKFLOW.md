# Running 010 with another scan dataset

The cluster bind maps:

```text
$HPC_SCRATCH/pygalmesh/data  ->  /data
```

Therefore this host dataset:

```text
$HPC_SCRATCH/pygalmesh/data/resources/JM-26-29_55mm_Bin4
```

must be stored in a JSON config as:

```text
/data/resources/JM-26-29_55mm_Bin4
```

`HPC_SCRATCH` is the environment variable used by the cluster scripts (uppercase
`SCRATCH`). Do not put an unexpanded `$HPC_SCRATCH` string into JSON.

## 1. Create a separate base config

From `data/scripts/010-Yield-Surface-Generation`, run:

```bash
NEW_MIN_Z=...
NEW_MAX_Z=...

python3 create_scan_dataset_config.py \
  --base-config config-Bin4-reduce-2.json \
  --output config-JM-26-29_55mm_Bin4.json \
  --dataset-id JM-26-29_55mm_Bin4 \
  --resource-folder "$HPC_SCRATCH/pygalmesh/data/resources/JM-26-29_55mm_Bin4" \
  --binning 4 \
  --min-z "$NEW_MIN_Z" \
  --max-z "$NEW_MAX_Z"
```

`min_z` is inclusive and `max_z` is exclusive. They index the slices *after*
`00_dicom_2_npy.py`. The command above applies no additional reduction, because
the dataset is already Bin4. If `--reduce-factor 2` is added, the chosen indices
must refer to the reduced slice stack.

The old values `220` and `570` describe the old reference region; the active old
Bin4 + reduce-2 config scales them to `55` and `143`. They should not be copied
to the new scan unless visual inspection confirms that they select the intended
physical region.

The generator creates independent preprocessing/output paths and automatically
rescales inherited buffer widths when the effective binning changes. Parameters
which describe this particular scan still need validation, especially:

- segmentation threshold/filter and `invert_contrast`;
- rotation angles;
- x/y crop or center;
- boundary-shell thickness;
- meshing size and surface-distance factors.

Any value can be overridden while creating the config, for example:

```bash
  --set '01_segment_slice_wise.threshold_offset=150' \
  --set '02a_rotate_pic_to_align_with_axis.angles=[0.0,0.0,0.0]'
```

## 2. Generate a dataset-specific yield job set

Keep its jobs separate from the existing specimen:

```bash
YIELD_SURFACE_BASE_CONFIG=config-JM-26-29_55mm_Bin4.json \
YIELD_SURFACE_OUTPUT_DIR=yield_surface_jobs/JM-26-29_55mm_Bin4/n006 \
./setup_yield_surface_jobs.sh 6
```

For 192 directions, replace both `6` and `n006` with `192` and `n192`.

## 3. Sync and prepare the mesh once

After the project is under `$HPC_SCRATCH/pygalmesh`, submit:

```bash
sbatch \
  "$HPC_SCRATCH/pygalmesh/data/scripts/010-Yield-Surface-Generation/job_prepare_mesh_CLUSTER.sh" \
  config-JM-26-29_55mm_Bin4.json
```

The job checks that both the config and scan directory exist before starting the
expensive preprocessing.

## 4. Submit the yield points

After mesh preparation completes:

```bash
bash \
  "$HPC_SCRATCH/pygalmesh/data/scripts/010-Yield-Surface-Generation/yield_surface_jobs/JM-26-29_55mm_Bin4/n006/submit_all_yield_surface_points.sh"
```

Check and collect only this dataset:

```bash
SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/010-Yield-Surface-Generation"

python3 "$SCRIPT_DIR/check_yield_surface_points.py" \
  --jobs-dir "$SCRIPT_DIR/yield_surface_jobs/JM-26-29_55mm_Bin4/n006"

python3 "$SCRIPT_DIR/collect_yield_surface_points.py" \
  --dataset-id JM-26-29_55mm_Bin4
```

Results are kept below:

```text
00_results/JM-26-29_55mm_Bin4/Bin4/yield_surface/
00_results/JM-26-29_55mm_Bin4/yield_surface_points.csv
```
