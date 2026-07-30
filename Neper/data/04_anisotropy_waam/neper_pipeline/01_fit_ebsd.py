#!/usr/bin/env python3
"""
Step 1: Fit Neper input parameters from the EBSD grain files.

Material-parametrized (WAAM 316L or 17-4PH; the transition region uses the
same code path via ``--material trans``).  Reads the TSL/OIM grain exports for
the material, derives the statistical targets for a transversely isotropic,
columnar 3D microstructure (build direction = z) and writes, suffixed by
material <MAT>:

  params_<MAT>.json          - fitted parameters + derived Neper arguments
  n<N>_<MAT>.ori             - N crystal orientations (Bunge Euler, deg),
                               area-weighted bootstrap from the V (build-normal)
                               section, sample frame rotated so build (= section
                               normal) -> +z, weld (in-plane axis) -> +x
  n<N>_<MAT>.meta            - per-orientation crystal system (fcc/bcc/...) in
                               the SAME line order as the .ori file, so the
                               downstream grain table can tag each grain's phase
  fit_ebsd_targets_<MAT>.png - diagnostic histograms (EBSD vs. fit)

Phase handling (see materials.py):
  * 316L : FCC austenite only (single phase).
  * 17-4PH: all valid phases pooled for morphology (BCC martensite dominates
    by area); per-grain crystal system is preserved for the elasticity model.
  * trans: FCC + BCC pooled (single available map, reused for every statistic).

Model assumptions (see README.md): columnar grains along the build direction,
transversely isotropic; transverse size + elongation from the Vertical and
45deg sections (area-weighted); stereological correction d_3D = d_2D * 4/pi.

Usage:  python3 01_fit_ebsd.py [--material 316L|17-4PH|trans]
                               [--data DIR] [--n 200] [--out DIR]
"""
import argparse
import json
import os

import numpy as np

import materials as M
# Re-export shared helpers so existing importers (07/08) keep working when they
# ``import 01_fit_ebsd as fit`` and call fit.load / fit.euler_to_g / ...
load = M.load
euler_to_g = M.euler_to_g
g_to_euler = M.g_to_euler
random_smallrot = M.random_smallrot
wmedian = M.wmedian
axis_mean = M.axis_mean

STEREO = M.STEREO


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--material", default="316L", choices=list(M.MATERIALS))
    p.add_argument("--data", default=M.default_data_dir())
    p.add_argument("--n", type=int, default=200, help="number of grains in the RVE")
    p.add_argument("--out", default=os.path.dirname(__file__) or ".")
    p.add_argument("--scatter-deg", type=float, default=3.0,
                   help="random scatter added to bootstrapped orientations")
    p.add_argument("--seed", type=int, default=1)
    args = p.parse_args()
    rng = np.random.default_rng(args.seed)

    mat = args.material
    cfg = M.MATERIALS[mat]
    print(f"# material: {mat}  ({cfg['pretty']})")

    dfs = M.load_sections(mat, data_dir=args.data)
    for lab, df in dfs.items():
        fr = {k: round(v, 3) for k, v in M.phase_fractions(df).items()}
        print(f"#   section {lab:10s}: {len(df):6d} grains, area-frac {fr}")

    import pandas as pd

    size_metric = M.mat_cfg(mat, "size_metric")       # "width" | "diameq"
    morphology = M.mat_cfg(mat, "morphology")         # "columnar" | "equiaxed"

    # ---- 2D grain size: pooled size_sections, area-weighted -------------
    # "width"  = 2 * ellipse minor axis  (transverse size of columnar grains)
    # "diameq" = equivalent-circle diameter (robust for equiaxed grains)
    size_dfs = [dfs[s] for s in cfg["size_sections"] if s in dfs]
    dfp = pd.concat(size_dfs)
    w = dfp.area_um2.values
    if size_metric == "diameq":
        width = dfp.diameter_um.values
    else:
        width = 2.0 * dfp.minor_um.values
    lw = np.log(width)
    m = np.average(lw, weights=w)
    s_width = float(np.sqrt(np.average((lw - m) ** 2, weights=w)))
    med_width = float(np.exp(m))
    d_t_median = med_width * STEREO                   # 3D size (Saltykov 4/pi)
    mean_width = float(np.average(width, weights=w))
    cv_width = float(np.sqrt(np.average((width - mean_width) ** 2, weights=w)) / mean_width)

    # ---- elongation (major/minor), area-weighted median -----------------
    elong = {lab: M.wmedian(df.major_um.values / df.minor_um.values,
                            df.area_um2.values)
             for lab, df in dfs.items()}
    k_measured = float(np.mean([elong[s] for s in cfg["elong_sections"] if s in elong]))
    # Grain shape per morphology:
    #   equiaxed   : no stretch (k=1); anisotropy from texture only.
    #   columnar   : uniaxial stretch by k along build z (transverse isotropic).
    #   orthotropic: TWO stretches. Every EBSD plane is a cross-section _|_ the
    #                specimen axis (see materials.py), so:
    #                  k_build   = build/wall-normal  from the H-section (_|_ weld)
    #                  k_inplane = weld /wall-normal  from the V-section (_|_ build)
    #                RVE frame x=weld, y=wall-normal, z=build; wall-normal is the
    #                base (=1). Transform scale(k_inplane, 1, k_build) on a cube
    #                -> grain L_z:L_x:L_y = k_build:k_inplane:1 (~3.4:3.2:1).
    k_build = float(elong.get(M.mat_cfg(mat, "k_build_section", "horizontal"),
                              k_measured))
    k_inplane = float(elong.get(M.mat_cfg(mat, "k_inplane_section", "vertical"),
                                1.0))
    # RVE frame (x=weld, y=wall-normal, z=build) -> transform applied by step 02.
    # Build frame (x=build, y=weld, z=wall-normal) -> scale for the specimen
    # scripts 07/08 (their local x is the load/build-related axis).
    shape_amp = float(M.mat_cfg(mat, "shape_amp", 1.0))
    if morphology == "equiaxed":
        k_used, sx, sy, sz = 1.0, 1.0, 1.0, 1.0
        sbx, sby, sbz = 1.0, 1.0, 1.0
    elif morphology == "orthotropic":
        # wall-normal is the base (=1); stretch weld by k_inplane, build by k_build.
        # Shape calibration: the anisotropic stretch of the (non-round) base cells
        # inflates the realised per-grain aspect by ~shape_amp. Dividing the APPLIED
        # stretch by shape_amp makes the generated grain elongation match the EBSD
        # target k_build/k_inplane (measured amp ≈ 1.22; verify with matching_extra.py
        # after re-generating the RVE). k_build/k_inplane below remain the TARGET.
        kb_app, ki_app = k_build / shape_amp, k_inplane / shape_amp
        k_used = round(kb_app, 2)                          # for 07/08 compatibility
        sx, sy, sz = round(ki_app, 3), 1.0, round(kb_app, 2)     # weld, wall, build
        sbx, sby, sbz = round(kb_app, 2), round(ki_app, 3), 1.0  # build, weld, wall
    else:                                                 # columnar
        k_used = round(k_measured, 2)
        sx, sy, sz = 1.0, 1.0, k_used
        sbx, sby, sbz = k_used, 1.0, 1.0
    transform = f"scale({sx},{sy},{sz})"
    scale_prod = round(sx * sy * sz, 3)

    # ---- in-plane elongation axis of the build-normal (V) section -------
    # The V-section is _|_ build, so its NORMAL is the build direction and its
    # dominant in-plane elongation axis (theta) is the WELD direction. The
    # orientations are sampled from this section and rotated so build (= section
    # normal) -> z and weld (= in-plane axis) -> x (see Q below).
    dv = dfs[M.mat_cfg(mat, "build_normal_section", cfg["build_section"])]
    wa = dv.area_um2.values * (1.0 - dv.aspect_ratio.values)
    theta_weld, R_conc = M.axis_mean(dv.ellipse_deg.values, wa)
    theta_build = theta_weld   # kept name for the params/plot below
    if R_conc < M.mat_cfg(mat, "r_warn"):
        print(f"#   WARNING: build-axis concentration R={R_conc:.2f} is low -> the "
              f"build direction is weakly defined from grain morphology.")
        if morphology != "equiaxed":
            print("#            (consider morphology='equiaxed' for this material)")

    # ---- Neper morpho parameters (scaled, isotropic space) --------------
    # The measured CV can be very broad (heavy tail). An optional cv_cap limits
    # the CV used for the Neper TARGET distribution -> faster convergence and
    # robust meshing (no extreme tiny grains). Median is preserved; the cap does
    # not affect the crystallographic elastic anisotropy, only size scatter.
    cv_cap = M.mat_cfg(mat, "cv_cap")
    cv_full = round(cv_width, 2)
    cv = round(min(cv_width, cv_cap), 2) if cv_cap else cv_full
    if cv < cv_full:
        print(f"#   CV capped for Neper target: measured {cv_full} -> used {cv} "
              f"(median preserved; anisotropy unaffected)")
    s_ln = np.sqrt(np.log(1 + cv ** 2))               # matching lognormal sigma
    d_t_mean = d_t_median * float(np.exp(0.5 * s_ln ** 2))
    n = args.n
    Ed3 = d_t_median ** 3 * np.exp(4.5 * s_ln ** 2)
    L = float((n * np.pi / 6.0 * Ed3) ** (1.0 / 3.0))
    L = round(L, -1)                                  # round to 10 um

    params = {
        "material": mat,
        "material_pretty": cfg["pretty"],
        "units": "um",
        "n_grains": n,
        "min_points": M.mat_cfg(mat, "min_points"),
        "size_metric": size_metric,
        "morphology": morphology,
        "phase_area_fraction": {k: round(v, 4)
                                for k, v in M.phase_fractions(dv).items()},
        "transverse": {
            "width2D_median_um": round(med_width, 1),
            "width2D_lognorm_sigma": round(s_width, 3),
            "width2D_cv": round(cv_width, 3),        # measured (full data)
            "cv_used_for_neper": cv,                 # capped target (cv_cap)
            "stereo_factor": round(STEREO, 4),
            "d3D_median_um": round(d_t_median, 1),
            "d3D_mean_um": round(d_t_mean, 1),
        },
        "elongation": {**{k: round(v, 2) for k, v in elong.items()},
                       "k_measured": round(k_measured, 2),
                       "k_used": round(k_used, 2),
                       "k_build": round(k_build, 2),      # TARGET build/wall-normal (horizontal, _|_ weld)
                       "k_inplane": round(k_inplane, 2),  # TARGET weld/wall-normal (vertical, _|_ build)
                       "shape_amp": round(shape_amp, 3),  # base-cell shape calibration (applied stretch = target/amp)
                       "axes_zxy": "z=build, x=weld, y=wall-normal"},
        "build_axis_in_vertical_map_deg": round(theta_build, 1),
        "build_axis_concentration_R": round(R_conc, 2),
        "neper": {
            "domain_cube_um": L,
            "final_rve_um": [round(L * sx, 1), round(L * sy, 1), round(L * sz, 1)],
            "morpho_cv": cv,
            "morpho": f"diameq:lognormal(1,{cv}),1-sphericity:lognormal(0.145,0.03)",
            "transform": transform,
            "scale_xyz": [sx, sy, sz],
            "scale_build_frame": [sbx, sby, sbz],
            "scale_product": scale_prod,
            "ori_file": f"n{n}_{mat}.ori",
        },
    }

    # ---- orientations: area-weighted bootstrap from the V (build-normal) map ---
    # The V-section is _|_ build, so build = map NORMAL. Sample frame:
    #   e_x' = weld  = in-plane elongation axis (angle theta in the map plane)
    #   e_y' = wall-normal = in-plane perpendicular
    #   e_z' = build = map normal (out of plane)
    # Q columns are these axes in map coords; g_new = g_old . Q puts build -> z,
    # weld -> x, wall-normal -> y (consistent with the RVE frame).
    th = np.deg2rad(theta_build)
    Q = np.array([[np.cos(th), -np.sin(th), 0.0],
                  [np.sin(th),  np.cos(th), 0.0],
                  [0.0,         0.0,        1.0]])
    # crystal label per grain: area-weighted bootstrap (preserves phase fractions)
    idx = rng.choice(len(dv), size=n, p=dv.area_um2.values / dv.area_um2.values.sum())
    crystals = dv["crystal"].values[idx]
    texture = M.mat_cfg(mat, "texture", "ebsd")
    out_eul = []
    if texture == "cube100":
        # IMPOSED <100> cube texture: each grain near the cube orientation
        # (<100> ∥ Aufbau, Schweiß und Wandnormale) with a misorientation spread.
        # Motivation: the tensile tests show 316L behaves nearly like a <100>
        # single crystal along V and H (E≈E<100>, ν≈ν<100>) — a sharp <100>
        # texture that the available EBSD scan does not carry (report §3.6).
        # texture_spread_deg is the max misorientation angle, calibrated so the
        # directional E matches the experiment (~20° -> E_V/H≈99, E_45≈189 GPa).
        spread = float(M.mat_cfg(mat, "texture_spread_deg", 20.0))
        for _ in range(n):
            g = M.random_smallrot(spread, rng)
            out_eul.append(np.rad2deg(M.g_to_euler(g)))
    else:
        # DEFAULT: area-weighted bootstrap of the measured EBSD orientations,
        # rotated into the RVE frame (build = V-section normal -> z).
        eulers = np.deg2rad(dv[["phi1_deg", "PHI_deg", "phi2_deg"]].values[idx])
        for e in eulers:
            g = M.euler_to_g(*e) @ Q
            g = g @ M.random_smallrot(args.scatter_deg, rng)  # avoid exact duplicates
            out_eul.append(np.rad2deg(M.g_to_euler(g)))
    ori_path = os.path.join(args.out, f"n{n}_{mat}.ori")
    np.savetxt(ori_path, np.array(out_eul), fmt="%.3f")
    with open(os.path.join(args.out, f"n{n}_{mat}.meta"), "w") as f:
        f.write("# crystal system per orientation (same order as .ori)\n")
        for c in crystals:
            f.write(f"{c}\n")

    with open(os.path.join(args.out, f"params_{mat}.json"), "w") as f:
        json.dump(params, f, indent=2)
    print(json.dumps(params, indent=2))
    print(f"\nwrote {ori_path} ({n} orientations, Bunge Euler deg) + .meta")

    # ---- diagnostic plot ------------------------------------------------
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axs = plt.subplots(1, 3, figsize=(14, 4))
        bins = np.geomspace(width.min(), width.max(), 25)
        axs[0].hist(width, bins=bins, weights=w / w.sum(), alpha=0.6,
                    label="EBSD (area-weighted)")
        axs[0].set_xscale("log")
        size_lbl = "equiv. diameter [um]" if size_metric == "diameq" else "grain width 2b [um]"
        axs[0].set_xlabel(size_lbl)
        axs[0].legend(fontsize=8)
        axs[0].set_title(f"{mat} size ({size_metric}): med={med_width:.0f} um, CV={cv_width:.2f}")

        for lab, df in dfs.items():
            e = df.major_um.values / df.minor_um.values
            axs[1].hist(e[e < 12], bins=24, weights=df.area_um2.values[e < 12],
                        histtype="step", density=True, label=lab)
        axs[1].axvline(k_measured, color="k", ls="--",
                       label=f"k_meas={k_measured:.2f} (used k={k_used:.2f})")
        axs[1].set_xlabel("elongation a/b")
        axs[1].legend(fontsize=8)

        axs[2].hist(dv.ellipse_deg.values, bins=36, weights=wa, density=True)
        axs[2].axvline(theta_build, color="r", ls="--",
                       label=f"in-plane (weld) axis {theta_build:.0f} deg")
        axs[2].set_xlabel("ellipse axis [deg] (V section, _|_ build)")
        axs[2].legend(fontsize=8)
        fig.suptitle(cfg["pretty"])
        fig.tight_layout()
        out_png = os.path.join(args.out, f"fit_ebsd_targets_{mat}.png")
        fig.savefig(out_png, dpi=150)
        print(f"wrote {out_png}")
    except Exception as exc:  # matplotlib optional
        print("plot skipped:", exc)


if __name__ == "__main__":
    main()
