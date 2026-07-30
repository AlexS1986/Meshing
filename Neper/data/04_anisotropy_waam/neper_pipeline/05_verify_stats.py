#!/usr/bin/env python3
"""
Step 5: Verify the generated tessellation against the EBSD targets.

Reads waam_n<N>.stcell (id, vol, diameq, sphericity, x, y, z, ori) of the
FINAL (stretched) tessellation and compares:
  - transverse grain size (from vol and elongation k)
  - grain volume distribution vs. the fitted lognormal target
Also generates virtual 2D sections through the tessellation with Neper
(if available) and compares section statistics with the EBSD maps.

Run inside the container after 02.  Output: verify_comparison.png + console.
"""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MAT = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("MAT", "316L")
P = json.load(open(os.path.join(HERE, f"params_{MAT}.json")))
n = P["n_grains"]
# scale product = volume growth from the anisotropic stretch (columnar: k;
# orthotropic: k_build/k_inplane; equiaxed: 1). Reconstruct the base equiaxed
# diameter d0 = (6 V / (pi * scale_product))^(1/3) for the size comparison.
k = P["neper"].get("scale_product", P["elongation"]["k_used"])
L = P["neper"]["domain_cube_um"]
BASE = f"waam_{MAT}_n{n}"
print(f"# verifying {MAT}: {BASE}")

data = np.loadtxt(os.path.join(HERE, f"{BASE}.stcell"), usecols=(0, 1, 2, 3))
vol, diameq, sph = data[:, 1], data[:, 2], data[:, 3]

# grains are ~ellipsoids d_t x d_t x k*d_t  ->  vol = pi/6 k d_t^3
d_t = (6.0 * vol / (np.pi * k)) ** (1.0 / 3.0)
tgt_med, tgt_mean = (P["transverse"]["d3D_median_um"], P["transverse"]["d3D_mean_um"])
# CV target = the (possibly capped) value Neper was actually told to build
cv_tgt = P["neper"].get("morpho_cv",
                        P["transverse"].get("cv_used_for_neper",
                                            P["transverse"]["width2D_cv"]))
cv_meas = P["transverse"]["width2D_cv"]
cv_note = "" if abs(cv_tgt - cv_meas) < 1e-6 else f", measured EBSD {cv_meas}"
print(f"transverse diameter d_t : median {np.median(d_t):7.1f} um  (target {tgt_med})")
print(f"                          mean   {d_t.mean():7.1f} um  (target {tgt_mean})")
print(f"                          CV     {d_t.std()/d_t.mean():7.2f}     "
      f"(target {cv_tgt}{cv_note})")
print(f"sphericity (scaled space n/a, final): mean {sph.mean():.3f}")

# ---- virtual sections via Neper slicing (optional) -------------------
# vertical section (plane x = L/2, contains build dir z):
#   neper -T -loadtess waam_n<N>.tess -transform "slice(<L/2>,1,0,0)" ...
# horizontal section (plane z = k*L/2, perpendicular to build dir):
#   neper -T -loadtess waam_n<N>.tess -transform "slice(<k*L/2>,0,0,1)" ...
for name, (d, a, b, c) in {
    "slice_vert": (L / 2, 1, 0, 0),
    "slice_horiz": (k * L / 2, 0, 0, 1),
}.items():
    cmd = ["neper", "-T", "-loadtess", os.path.join(HERE, f"{BASE}.tess"),
           "-transform", f"slice({d},{a},{b},{c})",
           "-statcell", "area,diameq",
           "-o", os.path.join(HERE, f"{MAT}_{name}")]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        s = np.loadtxt(os.path.join(HERE, f"{MAT}_{name}.stcell"), ndmin=2)
        area, d2 = s[:, 0], s[:, 1]
        wmed = d2[np.argsort(d2)][np.searchsorted(
            np.cumsum(area[np.argsort(d2)]), 0.5 * area.sum())]
        print(f"{name}: {len(d2)} grains, 2D diameq area-weighted median "
              f"{wmed:.0f} um")
    except Exception as exc:
        print(f"{name}: neper slicing skipped ({exc})")

# ---- plot -------------------------------------------------------------
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 4))
    bins = np.geomspace(d_t.min() * 0.8, d_t.max() * 1.2, 20)
    ax.hist(d_t, bins=bins, density=True, alpha=0.6, label="Tessellation $d_t$")
    s_ln = np.sqrt(np.log(1 + cv_tgt ** 2))
    xx = np.geomspace(bins[0], bins[-1], 200)
    mu = np.log(tgt_med)
    ax.plot(xx, np.exp(-(np.log(xx) - mu) ** 2 / (2 * s_ln ** 2))
            / (xx * s_ln * np.sqrt(2 * np.pi)), "r-", label="EBSD-Target")
    ax.set_xscale("log")
    ax.set_xlabel("transversaler Korndurchmesser [um]")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, f"verify_comparison_{MAT}.png"), dpi=150)
    print(f"wrote verify_comparison_{MAT}.png")
except Exception as exc:
    print("plot skipped:", exc)
