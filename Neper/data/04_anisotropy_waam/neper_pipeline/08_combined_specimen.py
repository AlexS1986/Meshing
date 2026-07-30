#!/usr/bin/env python3
"""
Step 8: Simplified *composite* tensile specimen (V orientation) for FEniCSx.

A single flat gauge bar built from three EQUAL-LENGTH regions stacked along the
load / build axis x (V orientation -> build direction = load axis):

      x = 0 ......... LX/3 ......... 2LX/3 ......... LX
        |   316L    |   transition   |   17-4PH    |     (bottom -> top)
        (austenite)  (Uebergangsber.)  (martensite)

Each region carries its OWN fitted WAAM microstructure:
  * 316L    : columnar FCC austenite  (params_316L.json)
  * trans   : Uebergangsbereich - HOMOGENEOUS by default: a single block
              (1 region = 1 grain, n=1) with one representative orientation
              from the transition EBSD map. Set HOMOGENEOUS="" to model it as a
              resolved polycrystal instead.
  * 17-4PH  : columnar BCC martensite  (params_17-4PH.json)

Method ("multi-domain, merged mesh"):
  1. For each region, tessellate an equiaxed structure in the *scaled*
     (isotropic) space of a sub-box, then stretch along x by that region's
     elongation k  ->  columnar grains along the load axis (Neper, proven flags).
  2. Mesh each region separately (neper -M -> .msh).
  3. Merge the three region meshes into ONE mesh in Python (meshio): shift each
     region to its x-slot, offset grain ids so they stay globally unique, and
     attach three cell tags:
        grain    = globally unique grain id (1..sum n_r)
        region   = 0 (316L) / 1 (trans) / 2 (17-4PH)
        material = same as region here (kept separate for clarity/extensibility)
  4. Write spec_combined_V.xdmf/.h5 + grain_ori_combined.txt
        (grain_id  phi1 Phi phi2  crystal  material  region).

Orientations: area-weighted bootstrap from each material's build-section EBSD
map, rotated so the build direction lands along the load axis x (alpha = 0, V).

IMPORTANT - interfaces: the three region meshes are generated independently, so
the two interface planes (x = LX/3, 2LX/3) are geometrically coincident but the
surface meshes are NOT node-conforming.  For a bonded (displacement-continuous)
elasticity model in dolfinx you must tie the interfaces (e.g. a mortar / MPC
constraint on the matching facet sets) OR regenerate with a single conforming
tessellation (see README "conforming variant").  Facet sets for the interfaces
are not written here; the region tag lets you identify the two sides.

Run inside the container (after step 1 for 316L, 17-4PH and trans):
    python3 01_fit_ebsd.py --material 316L
    python3 01_fit_ebsd.py --material 17-4PH
    python3 01_fit_ebsd.py --material trans
    python3 08_combined_specimen.py

Env (all optional):
    LX, LY, LZ    gauge length/width/thickness in um  (default 1800/600/300)
    MAXGRAINS     cap on grains per region             (default 700)
    MINGRAINS     floor on grains per region           (default 20)
    RCL           Neper relative element size          (default 0.75)
    MORPHOSTOP    Neper morpho stop criterion          (default val=1e-2||itermax=100000)
    FAST=1        use -morpho voronoi (seconds, no size optimisation)
    SEED          base RNG seed                         (default 1)
"""
import json
import os
import subprocess
import sys
import zlib

import numpy as np

import materials as M

HERE = os.path.dirname(os.path.abspath(__file__))

# Region order along +x (bottom -> top).  (material, region_label)
REGIONS = [("316L", "bottom"), ("trans", "middle"), ("17-4PH", "top")]
MAT_ID = {"316L": 0, "trans": 1, "17-4PH": 2}

# Materials modelled as a single homogeneous block (1 region = 1 grain, n=1)
# instead of a resolved polycrystal. The transition zone is a homogeneous
# buffer by default; override with e.g. HOMOGENEOUS="" to make it a polycrystal.
HOMOGENEOUS = set(os.environ.get("HOMOGENEOUS", "trans").split())

GAUGE = (float(os.environ.get("LX", 1800.0)),   # length (load / build axis x)
         float(os.environ.get("LY", 600.0)),    # width  y
         float(os.environ.get("LZ", 300.0)))    # thickness z
MAXGRAINS = int(os.environ.get("MAXGRAINS", 700))
MINGRAINS = int(os.environ.get("MINGRAINS", 20))
RCL = os.environ.get("RCL", "0.75")
# Per-region grain counts are small, so the morpho objective usually cannot
# reach `val` and would otherwise burn the full itermax (hours). A modest
# itermax gives a good-enough columnar structure in minutes.
MORPHOSTOP = os.environ.get("MORPHOSTOP", "val=2e-2||itermax=8000")
FAST = os.environ.get("FAST", "0") == "1"
SEED = int(os.environ.get("SEED", 1))
# rcl values tried in order when meshing; escalating (coarser) values are a
# robust workaround for the occasional gmsh 3D-meshing SIGABRT.
RCL_RETRIES = [RCL] + [r for r in ("1.0", "1.5", "2.0") if r != RCL]


def run(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=HERE, **kw)


def mesh_with_retry(out):
    """neper -M with escalating rcl; robust against gmsh 3D-meshing crashes."""
    for i, rcl in enumerate(RCL_RETRIES):
        try:
            run(["neper", "-M", f"{out}.tess", "-rcl", rcl, "-order", "1",
                 "-format", "msh", "-o", out])
            if i > 0:
                print(f"  (meshed at coarser rcl={rcl})", flush=True)
            return
        except subprocess.CalledProcessError:
            print(f"  meshing failed at rcl={rcl}; retrying coarser...", flush=True)
    raise RuntimeError(f"neper -M failed for {out}.tess at all rcl in {RCL_RETRIES}")


def region_params(mat):
    """Load the fitted params for a material and derive scaled-space size."""
    pj = os.path.join(HERE, f"params_{mat}.json")
    if not os.path.exists(pj):
        sys.exit(f"missing {pj} - run: python3 01_fit_ebsd.py --material {mat}")
    P = json.load(open(pj))
    k = P["elongation"]["k_used"]
    d_med = P["transverse"]["d3D_median_um"]
    # effective CV used for the Neper target (capped if cv_cap set)
    cv = round(P["neper"].get("morpho_cv",
                              P["transverse"].get("cv_used_for_neper",
                                                  P["transverse"]["width2D_cv"])), 2)
    s_ln = float(np.sqrt(np.log(1 + cv ** 2)))
    mean_vol = np.pi / 6.0 * d_med ** 3 * np.exp(4.5 * s_ln ** 2)   # scaled space
    theta = np.deg2rad(P["build_axis_in_vertical_map_deg"])
    # grain-shape stretch in the build frame (x=build=load for the V bar):
    # columnar (k,1,1) | equiaxed (1,1,1) | orthotropic (k_build,1,1/k_inplane)
    sb = [float(s) for s in P["neper"].get("scale_build_frame", [k, 1.0, 1.0])]
    scale_prod = sb[0] * sb[1] * sb[2]
    return dict(P=P, k=k, d_med=d_med, cv=cv, s_ln=s_ln, mean_vol=mean_vol,
                theta=theta, sb=sb, scale_prod=scale_prod)


def sample_orientations(mat, n, theta, seed, alpha_deg=0.0):
    """Bootstrap n Bunge Eulers (deg) from the material's build-section map,
    rotated so the build direction lands at angle alpha to the load axis x in
    the x-y plane (alpha = 0 for the V specimen).  Also returns crystal system
    per orientation."""
    rng = np.random.default_rng(seed)
    cfg = M.MATERIALS[mat]
    dv = M.load_sections(mat)[cfg["build_section"]]
    a = theta - np.deg2rad(alpha_deg)
    # specimen basis in map coords (map normal -> specimen z / thickness)
    R = np.array([[np.cos(a), -np.sin(a), 0],
                  [np.sin(a),  np.cos(a), 0],
                  [0,          0,         1]])
    p = dv.area_um2.values / dv.area_um2.values.sum()
    idx = rng.choice(len(dv), size=n, p=p)
    eulers = np.deg2rad(dv[["phi1_deg", "PHI_deg", "phi2_deg"]].values[idx])
    crystals = dv["crystal"].values[idx]
    out = []
    for e in eulers:
        g = M.euler_to_g(*e) @ R @ M.random_smallrot(3.0, rng)
        out.append(np.rad2deg(M.g_to_euler(g)))
    return np.array(out), crystals


def grain_count(mat, rp, seg_len):
    """Physically-representative and (capped) grain count for a region.
    Homogeneous materials collapse to a single grain (n=1)."""
    lx, ly, lz = GAUGE
    v_scaled = (seg_len * ly * lz) / rp["scale_prod"]   # scaled (pre-stretch) volume
    if mat in HOMOGENEOUS:
        return 1, 1, None, v_scaled                # single homogeneous block
    n_phys = int(round(v_scaled / rp["mean_vol"]))
    n = max(MINGRAINS, min(MAXGRAINS, n_phys))
    # effective transverse diameter if capped (grains coarsened to fit)
    d_eff = (6.0 * v_scaled / (np.pi * n) / np.exp(4.5 * rp["s_ln"] ** 2)) ** (1 / 3)
    return n_phys, n, d_eff, v_scaled


def tessellate_and_mesh_region(mat, rp, n, seg_len, seed):
    """Neper -T (scaled box, stretch -> columns along x) then -M. Returns the
    region mesh path.  Orientations are written to a per-region .ori and read
    back so grain_ori order matches the mesh cell ids."""
    lx, ly, lz = GAUGE
    out = f"spec_comb_{mat}"
    sbx, sby, sbz = rp["sb"]                         # build-frame grain stretch
    # scaled (pre-stretch) box so that after scale(sb) it fills seg x ly x lz
    bx, byd, bzd = seg_len / sbx, ly / sby, lz / sbz

    # orientations for this region (V: build dir -> x). Deterministic in `seed`,
    # so re-deriving on resume reproduces the exact cell<->crystal alignment.
    ori, crystals = sample_orientations(mat, n, rp["theta"], seed, alpha_deg=0.0)
    ori_file = f"{out}.ori_in"
    np.savetxt(os.path.join(HERE, ori_file), ori, fmt="%.3f")

    def tessellate(morpho):
        cmd = ["neper", "-T", "-n", str(n),
               "-domain", f"cube({bx},{byd},{bzd})",
               "-morpho", morpho]
        if morpho != "voronoi":
            cmd += ["-morphooptistop", MORPHOSTOP]
        cmd += ["-ori", f"file({ori_file},des=euler-bunge)",
                "-oridescriptor", "euler-bunge",
                "-transform", f"scale({sbx},{sby},{sbz})",  # grain-shape stretch
                "-statcell", "id,vol,x,y,z",
                "-o", out, "-format", "tess,ori"]
        run(cmd)

    homog = mat in HOMOGENEOUS or n == 1     # single homogeneous block
    lognormal = f"diameq:lognormal(1,{rp['cv']}),1-sphericity:lognormal(0.145,0.03)"
    morpho = "voronoi" if (FAST or homog) else lognormal

    def cached_match():
        """True only if the cached tessellation matches BOTH the current cell
        count AND the current region box length (x-extent ~ seg_len). Guards
        against reusing a stale region when only the grain count coincides
        (e.g. both capped at MAXGRAINS) but the gauge/segment length changed."""
        p = os.path.join(HERE, f"{out}.stcell")
        if not (os.path.exists(os.path.join(HERE, f"{out}.tess")) and os.path.exists(p)):
            return False
        try:
            d = np.loadtxt(p, ndmin=2)               # cols: id,vol,x,y,z (final)
        except Exception:
            return False
        if len(d) != n:
            return False
        max_x = float(d[:, 2].max())                  # cell-centroid x extent
        return max_x > 0.6 * seg_len                  # ~seg_len for a fresh region

    def drop_cached():
        for ext in (".tess", ".msh", ".stcell", ".ori"):
            p = os.path.join(HERE, out + ext)
            if os.path.exists(p):
                os.remove(p)

    # --- tessellation ---
    # Resume only a cached tessellation that still matches the current fit
    # (cell count AND box length). A homogeneous region (n=1) or a stale cache
    # from an earlier parametrization/gauge is regenerated automatically.
    tess_ok = (not homog and cached_match())
    if tess_ok:
        print(f"  resume: reusing existing {out}.tess ({n} cells)", flush=True)
    else:
        if os.path.exists(os.path.join(HERE, f"{out}.tess")):
            print(f"  cache stale (fit/gauge changed) -> regenerating {out}", flush=True)
        drop_cached()
        tessellate(morpho)

    # --- meshing (resume if already present, else retry with coarser rcl) ---
    if os.path.exists(os.path.join(HERE, f"{out}.msh")):
        print(f"  resume: reusing existing {out}.msh", flush=True)
    else:
        try:
            mesh_with_retry(out)
        except RuntimeError:
            if morpho == "voronoi":
                raise
            # Last resort: an optimized tessellation can trip a gmsh 3D-meshing
            # crash. Rebuild this region as a clean Voronoi structure (meshes
            # robustly) and try again. Same orientations/columnar stretch.
            print(f"  fallback: re-tessellating {out} as Voronoi and remeshing",
                  flush=True)
            for ext in (".tess", ".msh"):
                p = os.path.join(HERE, out + ext)
                if os.path.exists(p):
                    os.remove(p)
            tessellate("voronoi")
            mesh_with_retry(out)

    # crystal per cell, in cell-id order (Neper writes .ori in cell order)
    crys_by_cell = [c for c in crystals]  # index i -> cell id i+1
    return os.path.join(HERE, f"{out}.msh"), crys_by_cell


# ===========================================================================
# Pure merge logic (Neper-independent -> unit-testable).
# ===========================================================================
def _tetra_and_tags(mesh):
    """Extract tetra connectivity + grain (physical) tags from a meshio mesh."""
    etype = "tetra10" if any(cb.type == "tetra10" for cb in mesh.cells) else "tetra"
    cells = np.vstack([cb.data for cb in mesh.cells if cb.type == etype])
    tag_key = None
    for key in ("gmsh:physical", "gmsh:geometrical"):
        if key in mesh.cell_data_dict and etype in mesh.cell_data_dict[key]:
            tag_key = key
            break
    if tag_key is None:
        raise ValueError("no element tags in region mesh")
    tags = np.concatenate(
        [d for t, d in zip([cb.type for cb in mesh.cells], mesh.cell_data[tag_key])
         if t == etype]).astype(np.int64)
    return etype, cells, tags


def merge_regions(region_meshes, x_shifts, region_ids, material_ids):
    """Merge region meshes into one (points, etype, cells, grain, region, material).

    * region_meshes : list of meshio.Mesh (each region box at x in [0, seg])
    * x_shifts      : per-region translation along x to its slot
    * region_ids    : per-region integer region id
    * material_ids  : per-region integer material id

    Grain ids are renumbered globally (offset by the running grain count) so a
    cell's grain tag is unique across the whole specimen.  Returns a dict; also
    returns per-region (global_first_grain_id, n_local_grains) so orientation
    tables can be stitched in the same order.
    """
    all_pts, all_cells, grain, region, material = [], [], [], [], []
    pt_off = 0
    grain_off = 0
    etypes = set()
    grain_maps = []   # (mat_region_index, grain_off, n_local)
    for m, dx, rid, mid in zip(region_meshes, x_shifts, region_ids, material_ids):
        etype, cells, tags = _tetra_and_tags(m)
        etypes.add(etype)
        pts = m.points.copy()
        pts[:, 0] += dx
        all_pts.append(pts)
        all_cells.append(cells + pt_off)
        # remap local tags (1..n_local, possibly non-contiguous) -> global ids
        uniq = np.unique(tags)
        remap = {int(u): grain_off + i + 1 for i, u in enumerate(uniq)}
        g = np.array([remap[int(t)] for t in tags], dtype=np.int64)
        grain.append(g)
        region.append(np.full(len(tags), rid, dtype=np.int64))
        material.append(np.full(len(tags), mid, dtype=np.int64))
        grain_maps.append((grain_off, uniq))
        pt_off += len(pts)
        grain_off += len(uniq)
    if len(etypes) != 1:
        raise ValueError(f"mixed element types across regions: {etypes}")
    etype = etypes.pop()
    return dict(
        points=np.vstack(all_pts),
        etype=etype,
        cells=np.vstack(all_cells),
        grain=np.concatenate(grain),
        region=np.concatenate(region),
        material=np.concatenate(material),
        grain_maps=grain_maps,
    )


def main():
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        return
    import meshio  # imported here so the merge unit test can run without meshio

    lx, ly, lz = GAUGE
    seg = lx / 3.0
    print(f"combined V specimen: gauge {lx:.0f} x {ly:.0f} x {lz:.0f} um, "
          f"3 x {seg:.0f} um segments along load axis x")
    print(f"regions (bottom->top): {[m for m, _ in REGIONS]}\n")

    region_meshes, x_shifts, region_ids, material_ids = [], [], [], []
    crystals_per_region = []
    ori_per_region = []

    for ridx, (mat, label) in enumerate(REGIONS):
        rp = region_params(mat)
        n_phys, n, d_eff, v_scaled = grain_count(mat, rp, seg)
        if mat in HOMOGENEOUS:
            note = "  [HOMOGENEOUS: single block, 1 grain]"
        elif n != n_phys:
            note = (f"  [CAPPED from {n_phys}; grains coarsened to d_eff~{d_eff:.0f} "
                    f"um (true ~{rp['d_med']:.0f})]")
        else:
            note = ""
        print(f"[{label:6s}] {mat:7s} k={rp['k']:.2f} d_med={rp['d_med']:.0f} um "
              f"-> n={n} grains{note}")
        # warn if the (stretched) grains barely fit along the load axis x
        grain_len_x = rp["d_med"] * rp["sb"][0]
        n_along = seg / grain_len_x if grain_len_x > 0 else 99
        if mat not in HOMOGENEOUS and n_along < 3:
            print(f"    WARNING: only ~{n_along:.1f} grains along the load axis "
                  f"(grain ~{grain_len_x:.0f} um vs segment {seg:.0f} um). "
                  f"Increase LX (longer bar) for a resolved {mat} region.")
        seed = SEED + zlib.crc32(mat.encode()) % 100000
        msh_path, crys = tessellate_and_mesh_region(mat, rp, n, seg, seed)
        region_meshes.append(meshio.read(msh_path))
        x_shifts.append(ridx * seg)
        region_ids.append(ridx)
        material_ids.append(MAT_ID[mat])
        crystals_per_region.append(crys)
        # read back the per-cell orientations Neper actually assigned
        oout = os.path.splitext(msh_path)[0]
        ori = [l.split() for l in open(f"{oout}.ori")
               if l.strip() and not l.startswith(("#", "$"))]
        ori_per_region.append(np.array(ori, dtype=float))

    merged = merge_regions(region_meshes, x_shifts, region_ids, material_ids)

    out = os.path.join(HERE, "spec_combined_V")
    meshio.write(out + ".xdmf", meshio.Mesh(
        points=merged["points"],
        cells=[(merged["etype"], merged["cells"])],
        cell_data={"grain": [merged["grain"]],
                   "region": [merged["region"]],
                   "material": [merged["material"]]},
    ))
    print(f"\nwrote {out}.xdmf/.h5  "
          f"({len(merged['cells'])} {merged['etype']} elements, "
          f"{merged['grain'].max()} grains, 3 regions) - units: um")

    # ---- global orientation / phase table -------------------------------
    with open(out + "_grain_ori.txt", "w") as f:
        f.write("# grain_id phi1 Phi phi2 (Bunge, deg) crystal material region\n")
        gid = 0
        for ridx, (mat, label) in enumerate(REGIONS):
            ori = ori_per_region[ridx]
            crys = crystals_per_region[ridx]
            for i in range(len(ori)):
                gid += 1
                phi1, Phi, phi2 = ori[i, -3], ori[i, -2], ori[i, -1]
                c = crys[i] if i < len(crys) else "unknown"
                f.write(f"{gid} {phi1:.3f} {Phi:.3f} {phi2:.3f} {c} {mat} {ridx}\n")
    print(f"wrote {out}_grain_ori.txt ({gid} grains)")

    # optional visualisation
    subprocess.run(["neper", "-V", out + ".tess"], cwd=HERE,
                   capture_output=True)
    print("\n=== done: spec_combined_V.xdmf/.h5 + spec_combined_V_grain_ori.txt ===")
    print("NOTE: region interfaces are non-conforming (see module docstring / README).")


if __name__ == "__main__":
    main()
