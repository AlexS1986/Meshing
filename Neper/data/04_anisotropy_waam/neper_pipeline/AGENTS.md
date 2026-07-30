# AGENTS.md — WAAM elastic anisotropy project

Guidance for AI agents working in this project. Keep this file and
`documentation.txt` current (see "Maintenance" at the end).
Last updated: 2026-07-27.

## What this project is
EBSD → Neper polycrystal → mesh → per-grain anisotropic linear-elastic FE
(dolfinx) to get the effective elastic anisotropy of WAAM 316L and 17-4PH.
Full human docs: `documentation.txt` (this folder) and `README.md`
(German, detailed model + assumptions). The FE side has its own
`README.md` in `.../dolfinx_alex/shared/scripts/069-waam-polycrystal-anisotropy`.

## Two parts, two containers (do not conflate)
- **Neper pipeline** (this folder): mesh generation. Runs in the Neper/Gmsh
  container (`docker compose ... ubuntu_custom`).
- **dolfinx FE** (`069-waam-polycrystal-anisotropy`): runs in the dolfinx
  container (`alex-dolfinx`, **dolfinx v0.7.3**), which mounts `shared/ -> /home`
  and sets `PYTHONPATH=/home/utils` (the shared `alex` package). The dolfinx
  container does **not** see the Neper folder — meshes are staged into
  `069/inputs/` by `prepare_inputs.py` (host-side).

## Hard constraints (read before editing)
- **Cannot run Neper or dolfinx in the agent sandbox** (not installed; the
  registry/pip may be blocked). Validate Python logic with numpy standalone and
  `py_compile`; validate shell with `bash -n`. Do NOT claim a mesh/FE run
  succeeded — only the user's containers run those.
- **dolfinx is v0.7.3.** Use `ufl.VectorElement` / `ufl.TensorElement` +
  `dlfx.fem.FunctionSpace(domain, element)`. Do NOT use the 0.8 API
  (`dlfx.fem.functionspace(domain, ("Lagrange", 1))`). Mirror the existing
  reference `Meshing/pygalmesh/.../009-.../00_template/linearelastic.py`.
- **Do NOT modify the shared `alex` package** (`dolfinx_alex/shared/utils/alex`)
  — many other projects depend on it. Add per-project helpers instead
  (e.g. `waam_crystal.py`).
- **Voigt convention** everywhere: order `[xx,yy,zz,yz,xz,xy]`, engineering
  shear strains (matches `alex.linearelastic`). The 6x6 stress Bond matrix in
  `waam_crystal.py` / `06_fenicsx_example.py` is verified against cubic
  invariants — keep it consistent if you touch it.
- **Single-crystal constants in `config.json` are literature placeholders.**
  Results scale with them; never present absolute moduli as final without
  flagging this.

## Model geometry (current, confirmed 2026-07)
- EBSD polish planes are cross-sections PERPENDICULAR to the specimen axis
  (V||build, H||weld, 45deg). So the V-section (⊥build) gives weld/wall-normal
  (aspect 3.18) and its NORMAL = build; the H-section (⊥weld) gives
  build/wall-normal (aspect 3.41). 316L orthotropic shape L_z:L_x:L_y ≈ 3.4:3.2:1
  (plate-like). Section→axis mapping is set in `materials.py`
  (`k_build_section=horizontal`, `k_inplane_section=vertical`,
  `build_normal_section=vertical`). Texture: build = V-section normal → z.
  Transform `scale(k_inplane,1,k_build)=scale(3.18,1,3.41)`. 45deg-section cross
  check supports this geometry (pred 3.29 vs meas 2.60; old assumption 4.60).

## Where to make common changes
- Material fit behaviour (phase, min_points, size metric, columnar/equiaxed,
  cv_cap): `materials.py` (per-material dict) — this drives everything downstream.
- Grain statistics / orientation sampling: `01_fit_ebsd.py` (+ shared math in
  `materials.py`).
- RVE resolution for homogenization: `09_homogenization_rve.sh` (N, RCL).
- FE material law / per-grain stiffness: `069/waam_crystal.py`.
- Boundary conditions / load cases: `069/homogenize_rve.py` (KUBC),
  `069/uniaxial_tension.py` (uniaxial).
- Plots/tables: `069/evaluation.py` (+ `069/engineering_constants.py` for the
  orthotropic constants table, `069/experimental_comparison.py` for the vs-
  experiment E-modulus comparison — experimental values hardcoded there). Report source: `069/report/report.md` → PDF via
  `bash report/build_report.sh` (pandoc + xelatex). Figures/tables auto-number via
  `{#fig:label}`/`\label{tbl:label}` in captions + `\ref{...}` in text — never
  hand-number "Abb. N"/"Tabelle N" again. (docx retired: `\ref` won't resolve there.)

## Conventions
- Meshes: `waam_<MAT>_n<N>.xdmf/.h5` (RVE), `spec_<MAT>_<V|H|45deg>.*` (bars),
  `spec_combined_V.*` (trilayer). Cell tag `grain` = grain id.
- Orientation tables: `grain_ori_<MAT>[_<orient>].txt` =
  `grain_id phi1 Phi phi2 crystal [material region]` (Bunge degrees).
- Generated files are disposable; `clean_generated.sh` keeps only source scripts
  (whitelist). Don't commit generated meshes/results as source.
- Materials: `316L`, `17-4PH`, `trans`. Orientations: `V` (load ∥ build),
  `H` (⊥), `45deg`.

## How to verify work (in the sandbox)
- `python3 -m py_compile <file>.py`; `bash -n <file>.sh`.
- Crystal-elasticity math: rotate cubic C by random orientations and check the
  average tends to isotropic; check identity/90° cubic invariance (see the
  standalone checks used during development).
- Reading meshes for dolfinx uses `read_mesh(name="Grid")` +
  `read_meshtags(name="Grid")` (single "grain" attribute in the meshio XDMF).

## Run entry points
- Full mesh build: `run_pipeline.sh` (Neper container; `CLEAN=1` to start fresh).
- Stage: `prepare_inputs.py` (host). FE: `run_fem.sh` (dolfinx container).
- Post: `evaluation.py`.

## Maintenance (required)
Update this file and `documentation.txt` whenever scripts are added/renamed or
their CLI/env interface changes, when modeling assumptions change, when the
container/run workflow changes, or when new results supersede the snapshot in
`documentation.txt` §7. Keep the "Last updated" date current.
