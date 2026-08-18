# Yield-surface generation on the cluster

This directory contains the preprocessing, simulation, result collection, and
ParaView export tools for generating a yield surface from CT-derived meshes.
The example below prepares 192 approximately uniform loading directions in the
three-dimensional strain-eigenvalue space.

## Current material and yield criterion

The checked-in configuration selects the `std` material:

```text
E = 70000.0
nu = 0.35
sig_y = 140.0
hard = 0.0
```

The simulation records a yield point when the configured fraction of the
reduced material volume has yielded. The effective yield stress is read from
`yield_surface.material_sets.<material>.sig_y` in the job's `config.json`.
Every generated job contains a `parameters.txt` showing the resolved settings.

## 1. Generate 192 jobs

The direct job generator is `setup_yield_surface_jobs.sh`. Run it from the
yield-surface pipeline directory:

```bash
cd "$HOME/meshing/Meshing/pygalmesh/data/scripts/010-Yield-Surface-Generation"

./setup_yield_surface_jobs.sh 192
```

To specify the norm of the target strain tensor explicitly:

```bash
YIELD_SURFACE_STRAIN_RADIUS=0.25 \
./setup_yield_surface_jobs.sh 192
```

The wrapper performs the following steps:

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/config.sh"
POINTS="${1:-${YIELD_SURFACE_POINTS:-6}}"
RADIUS="${YIELD_SURFACE_STRAIN_RADIUS:-0.25}"
python3 "$SCRIPT_DIR/setup_yield_surface_jobs.py" \
  --points "$POINTS" \
  --radius "$RADIUS"
```

It creates:

```text
yield_surface_jobs/n192/
├── manifest.csv
├── submit_all_yield_surface_points.sh
└── 192 ys_... directories
```

Each `ys_...` directory contains its own `config.json`, SLURM job script, and
resolved `parameters.txt`.

## 2. Generate and synchronize in one command

`02_create_folders_CLUSTER.sh` calls the generator above and then synchronizes
the complete project from the home-directory copy to cluster scratch. The
recommended single command is:

```bash
cd "$HOME/meshing/Meshing/pygalmesh"

YIELD_SURFACE_POINTS=192 \
data/scripts/010-Yield-Surface-Generation/02_create_folders_CLUSTER.sh
```

This generates the individual jobs and synchronizes the project to:

```text
$HPC_SCRATCH/pygalmesh/data/scripts/010-Yield-Surface-Generation/
```

Therefore, it is not necessary to run both commands. Choose one of these
workflows:

- Run `setup_yield_surface_jobs.sh 192` to generate only.
- Run `YIELD_SURFACE_POINTS=192 02_create_folders_CLUSTER.sh` to generate and
  synchronize.

For more than six points, loading directions are distributed over the sphere
using Fibonacci-sphere sampling. The default norm of the target strain vector
is `0.25`. This vector defines a direction and solver horizon; it is multiplied
by the evolving strain scale, and the calculation normally stops at a much
smaller critical strain.

The target-vector norm can be set explicitly during generation:

```bash
YIELD_SURFACE_POINTS=192 \
YIELD_SURFACE_STRAIN_RADIUS=0.25 \
data/scripts/010-Yield-Surface-Generation/02_create_folders_CLUSTER.sh
```

## 3. Validate the generated jobs

```bash
SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/010-Yield-Surface-Generation"
YS_DIR="$SCRIPT_DIR/yield_surface_jobs/n192"

find "$YS_DIR" -name 'job_*_CLUSTER.sh' | wc -l
find "$YS_DIR" -name config.json | wc -l
find "$YS_DIR" -name parameters.txt | wc -l
```

All three commands should print `192`. Inspect the manifest and one resolved
parameter report before submission:

```bash
head "$YS_DIR/manifest.csv"
find "$YS_DIR" -name parameters.txt -print -quit | xargs cat
```

## 4. Prepare the mesh once

All yield-point jobs reuse the prepared Bin4 reduce-2 mesh. Submit its
preparation job once:

```bash
PREP_JOB_ID=$(
  sbatch --parsable \
    "$SCRIPT_DIR/job_prepare_mesh_Bin4_reduce_2_CLUSTER.sh"
)

echo "$PREP_JOB_ID"
squeue -j "$PREP_JOB_ID"
```

After it completes, inspect its log:

```bash
less "$SCRIPT_DIR/prep-ys-b4-r2.out.$PREP_JOB_ID"
```

Do not submit the point jobs until mesh preparation has completed successfully.

## 5. Submit the 192 independent point jobs

```bash
bash "$YS_DIR/submit_all_yield_surface_points.sh"
```

Each generated job currently requests one node, 32 tasks, 9000 MB per CPU, an
`i01` node constraint, and a 24-hour time limit. The cluster scheduler controls
how many of the 192 jobs run concurrently.

Monitor the jobs with:

```bash
squeue -u "$USER"
```

SLURM standard-output and error logs are written into the corresponding
`yield_surface_jobs/n192/<sample_id>/` directory.

## 6. Check and collect completed yield points

After the point jobs finish, check whether each expected summary exists and
contains a critical strain state:

```bash
python3 "$SCRIPT_DIR/check_yield_surface_points.py" --points 192
```

Collect valid states into one CSV file:

```bash
python3 "$SCRIPT_DIR/collect_yield_surface_points.py"
```

The collector only accepts summaries containing a `final_yield_state`. Its
default output is:

```text
00_results/yield_surface_points.csv
```

## 7. Create the ParaView surfaces

```bash
"$SCRIPT_DIR/create_yield_surface_paraview.sh"
```

This recursively reads result JSON files and writes:

```text
00_results/yield_surface_paraview/
├── yield_surface_points.csv
├── yield_surface_strain.vtk
├── yield_surface_stress_normal.vtk
└── yield_surface_stress_principal.vtk
```

The strain dataset uses `eps_mac_eigenvalues_current` and exposes the scalar
`norm_of_the_strain_tensor`. The fixed-axis stress dataset uses
`(sigma_xx, sigma_yy, sigma_zz)`. The principal-stress dataset contains the
sorted eigenvalues of `sigma_avg_reduced_volume`.

Sorting principal stresses maps all points into one ordered sector and may not
form a closed surface. If, and only if, the effective response can be assumed
isotropic, all principal-stress permutations can be added with:

```bash
python3 "$SCRIPT_DIR/create_yield_surface_paraview.py" \
  --input "$SCRIPT_DIR/00_results" \
  --expand-principal-permutations
```

The exporter removes duplicate geometric points and creates a convex-hull
triangulation when at least four non-coplanar points are available. JSON files
without a complete `final_yield_state` are skipped.

## Restarting or regenerating

Running the setup command again regenerates `yield_surface_jobs/n192` from the
base configuration. Because `02_create_folders_CLUSTER.sh` uses
`rsync --update`, a newer file already present in scratch is not overwritten by
an older source file. Check timestamps if an expected update does not appear in
the scratch copy.
