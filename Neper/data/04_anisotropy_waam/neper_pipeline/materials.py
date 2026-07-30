#!/usr/bin/env python3
"""
Shared configuration + robust EBSD loader for the WAAM anisotropy pipeline.

Handles the two steels (316L, 17-4PH) and the transition region
(Uebergangsbereich) with a single code path.  Encapsulates the awkward parts
of the raw TSL/OIM exports so the rest of the pipeline stays clean:

  * The 17-4PH / transition files use Windows (CRLF) line endings and live in
    a sub-folder whose name contains a non-ASCII character ("Uebergangsbereich"
    vs. "uebergangsbereich" depending on the mount).  ``find_grain_file`` locates
    files by a case-insensitive substring, recursively, so naming/mount quirks
    do not matter.
  * The files have 44 documented columns.  ``load`` reads them CRLF-safely.
  * Phase handling differs per material (see PHASE_POLICY below): 316L is
    single-phase FCC austenite; 17-4PH is a multi-phase martensitic steel
    (BCC matrix + retained FCC austenite + minor epsilon); the transition
    region contains both FCC and BCC.  Per-grain phase is always preserved so
    the downstream (dolfinx) elasticity can pick the right stiffness tensor.

Units are microns throughout.
"""
import glob
import os

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# The 44 documented columns of the TSL/OIM "Grain Size" export.
# (17-4PH/transition files add a trailing CR from CRLF endings; the
#  whitespace separator below absorbs it, so all files parse to 44 columns.)
# ---------------------------------------------------------------------------
COLUMNS = [
    "grain_id", "phase",
    "phi1_deg", "PHI_deg", "phi2_deg",
    "phi1_rad", "PHI_rad", "phi2_rad",
    "h", "k", "l", "u", "v", "w",
    "h_f", "k_f", "l_f", "u_f", "v_f", "w_f",
    "x_um", "y_um", "IQ", "CI", "fit_deg", "video_signal",
    "R", "G", "B", "edge_grain", "n_points",
    "area_um2", "diameter_um", "ASTM", "aspect_ratio",
    "major_um", "minor_um", "ellipse_deg", "ellipticity",
    "circularity", "feret_max", "feret_min",
    "ori_spread", "neigh_misori",
]

MIN_POINTS = 10          # noise-grain filter (drop tiny "dust"/cell-structure grains)
STEREO = 4.0 / np.pi     # mean 2D section diameter of a sphere = (pi/4) * D_3D

# Human-readable crystal system per phase id, so downstream code can map to an
# elastic stiffness tensor. Phase ids follow the TSL export legend.
#   316L      : 1 = FCC (austenite)
#   17-4PH    : 1 = FCC (retained austenite), 2 = BCC (martensite/ferrite),
#               3 = epsilon (hexaferrum, negligible)
#   transition: 1 = FCC, 2 = BCC
PHASE_CRYSTAL = {1: "fcc", 2: "bcc", 3: "hcp"}


def phase_all_valid(df):
    """Keep every real grain (phase > 0), i.e. drop anti-grains (phase -1)."""
    return df[df.phase > 0]


def phase_fcc_only(df):
    """Keep only FCC austenite (phase == 1)."""
    return df[df.phase == 1]


# ---------------------------------------------------------------------------
# Material registry.
#   sections     : label -> filename substring used to locate the grain file
#   phase        : filter policy (callable on the raw dataframe)
#   size/elong/build_section : which sections feed which statistic
#   min_points   : noise-grain filter (drop grains with fewer measurement pts).
#                  Higher for fine-grained/heavily-segmented maps (17-4PH) to
#                  suppress the tiny-grain tail that inflates the CV.
#   size_metric  : "width"  -> transverse grain width = 2 * ellipse minor axis
#                              (correct size measure for COLUMNAR grains)
#                  "diameq" -> equivalent-circle diameter (col 33), the robust
#                              size measure for ~EQUIAXED grains
#   morphology   : "columnar" -> grains stretched by the fitted elongation k
#                                along the build direction (aligned columns)
#                  "equiaxed" -> k forced to 1 (no global stretch). Use when the
#                                grain elongation is directionally INCOHERENT
#                                (low build-axis concentration R): imposing a
#                                common columnar axis would fabricate a
#                                morphological anisotropy the data do not show.
#                                Elastic anisotropy then comes purely from the
#                                (measured) crystallographic texture.
#   r_warn       : warn if the fitted build-axis concentration R falls below
#                  this (build direction weakly defined from morphology).
# ---------------------------------------------------------------------------
MATERIALS = {
    "316L": {
        "pretty": "WAAM 316L (austenitic, FCC)",
        "phase": phase_fcc_only,
        "sections": {
            "vertical": "316L_Vertical",
            "horizontal": "316L_Horizontal",
            "deg45": "316L_45",
        },
        "size_sections": ["vertical", "deg45"],
        "elong_sections": ["vertical", "deg45"],
        "build_section": "vertical",
        "min_points": 10,
        "size_metric": "width",
        # --- Sectioning geometry -------------------------------------------
        # CONFIRMED (2026-07): every EBSD polish plane is a cross-section
        # PERPENDICULAR to the tensile-specimen axis. The specimens are V
        # (load || build), H (load _|_ build, i.e. || weld) and 45deg. Hence:
        #   * V-section _|_ build  -> plane (weld x wall-normal); its aspect
        #     3.18 = weld/wall-normal (in-plane), and its NORMAL = build.
        #   * H-section _|_ weld   -> plane (build x wall-normal); its aspect
        #     3.41 = build/wall-normal.
        # An independent check on the 45deg section confirms this geometry
        # (predicted 45deg aspect 3.29 vs measured 2.60; the old "V = wall
        # face" assumption predicted 4.60). Resulting 3D grain shape
        # L_z:L_x:L_y ~ 3.4:3.2:1 (build ~ weld, both ~3.3x the wall-normal;
        # plate-like, NOT strongly columnar).
        # section that gives each elongation ratio (aspect = long/wall-normal):
        "k_build_section": "horizontal",   # H _|_ weld  -> build/wall-normal
        "k_inplane_section": "vertical",   # V _|_ build -> weld /wall-normal
        # section whose NORMAL is the build direction (used for the texture
        # frame + orientation sampling): build = normal of the V-section.
        "build_normal_section": "vertical",
        "morphology": "orthotropic",
        # Crystallographic texture: "ebsd" = use the measured EBSD orientations
        # (the data-based model; DEFAULT). A "cube100" option exists in
        # 01_fit_ebsd.py purely as a DIAGNOSTIC sensitivity check (imposes an
        # idealised <100> texture) — it is deliberately NOT used for the model,
        # because the microstructure must come from the scan, not be reverse-
        # engineered to match the tensile tests.
        "texture": "ebsd",
        # Shape calibration: the anisotropic stretch of the (irregular) base cells
        # inflates the realised per-grain aspect above the nominal stretch. Measured
        # amplification ≈ 1.22 (2D-section aspect 3.89/4.20 vs EBSD target 3.18/3.41).
        # The applied stretch is divided by shape_amp so the generated grain
        # elongation matches the EBSD target. Set 1.0 to disable. Re-generate the
        # RVE (Neper) for this to take effect; verify with matching_extra.py.
        "shape_amp": 1.22,
        "r_warn": 0.3,
    },
    "17-4PH": {
        "pretty": "WAAM 17-4PH (martensitic, mostly BCC + retained FCC)",
        "phase": phase_all_valid,
        "sections": {
            "vertical": "17-4PH_Vertikal",
            "horizontal": "17-4PH_Horizontal",
            "deg45": "17-4PH_45",
        },
        "size_sections": ["vertical", "deg45"],
        "elong_sections": ["vertical", "deg45"],
        "build_section": "vertical",
        # Fine, heavily-segmented martensite: stronger noise filter + robust
        # equivalent-diameter size; grains are elongated but directionally
        # incoherent (R~0.1) -> modelled EQUIAXED, anisotropy via texture.
        "min_points": 50,
        "size_metric": "diameq",
        "morphology": "equiaxed",
        "r_warn": 0.3,
        # The pooled size distribution is inherently very broad (measured
        # CV~1.4). Cap the CV used for the Neper TARGET distribution so the
        # tessellation converges and meshes robustly (no extreme tiny grains).
        # The median is preserved; this only narrows the size scatter and does
        # NOT affect the crystallographic elastic anisotropy. Set to None to
        # use the full measured CV.
        "cv_cap": 0.8,
    },
    # Transition region: only a single EBSD map is available.  We treat it as a
    # "vertical" section (build direction visible) and reuse it for every
    # statistic.  Contains both FCC and BCC grains, pooled.  (In the combined
    # specimen this region is modelled as a single homogeneous block, so its
    # morphology parameters are not critical.)
    "trans": {
        "pretty": "WAAM 316L<->17-4PH transition (Uebergangsbereich)",
        "phase": phase_all_valid,
        "sections": {
            "vertical": "uebergang",
        },
        "size_sections": ["vertical"],
        "elong_sections": ["vertical"],
        "build_section": "vertical",
        "min_points": 10,
        "size_metric": "width",
        "morphology": "columnar",
        "r_warn": 0.3,
    },
}


def mat_cfg(material, key, default=None):
    """Config accessor with sensible fallbacks for optional keys."""
    fallback = {"min_points": MIN_POINTS, "size_metric": "width",
                "morphology": "columnar", "r_warn": 0.3, "cv_cap": None,
                "texture": "ebsd", "texture_spread_deg": 20.0, "shape_amp": 1.0}
    return MATERIALS[material].get(key, fallback.get(key, default))


def default_data_dir(here=None):
    here = here or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "data_c04")


def find_grain_file(data_dir, substring):
    """Locate a .txt grain file whose basename contains ``substring``
    (case-insensitive), searching ``data_dir`` recursively.  Robust to
    sub-folders and non-ASCII folder names."""
    sub = substring.lower()
    hits = []
    for p in glob.glob(os.path.join(data_dir, "**", "*.txt"), recursive=True):
        if sub in os.path.basename(p).lower():
            hits.append(p)
    if not hits:
        raise FileNotFoundError(
            f"no grain file matching '{substring}' under {data_dir}")
    # Prefer the shortest path (avoids accidental deeper duplicates)
    return sorted(hits, key=len)[0]


def load(fp, phase_filter=phase_all_valid, min_points=MIN_POINTS):
    """Read a TSL/OIM grain export into a named DataFrame (CRLF-safe).

    Applies the noise filter (valid grain id, >= min_points, positive ellipse
    axes) and the given phase policy.  Returns a copy with the columns of
    ``COLUMNS`` plus a string ``crystal`` column derived from the phase id.
    """
    df = pd.read_csv(fp, comment="#", sep=r"\s+", header=None, names=COLUMNS)
    df = df[(df.grain_id > 0) & (df.n_points >= min_points)]
    df = df[(df.aspect_ratio > 0) & (df.minor_um > 0) & (df.major_um > 0)]
    df = phase_filter(df).copy()
    df["crystal"] = df.phase.map(PHASE_CRYSTAL).fillna("unknown")
    return df


def load_sections(material, data_dir=None, min_points=None):
    """Load every configured section of a material -> {label: DataFrame}.
    Uses the material's configured ``min_points`` unless overridden."""
    if material not in MATERIALS:
        raise KeyError(f"unknown material '{material}', "
                       f"choose from {list(MATERIALS)}")
    cfg = MATERIALS[material]
    mp = cfg.get("min_points", MIN_POINTS) if min_points is None else min_points
    data_dir = data_dir or default_data_dir()
    out = {}
    for label, sub in cfg["sections"].items():
        fp = find_grain_file(data_dir, sub)
        out[label] = load(fp, cfg["phase"], mp)
    return out


def phase_fractions(df):
    """Area fraction per crystal system in a (already filtered) dataframe."""
    a = df.groupby("crystal").area_um2.sum()
    return (a / a.sum()).to_dict()


# ===========================================================================
# Shared statistics + orientation helpers (used by 01_fit_ebsd, 07, 08)
# ===========================================================================
def wmedian(x, w):
    """Weighted median of x with weights w."""
    x = np.asarray(x); w = np.asarray(w)
    i = np.argsort(x)
    c = np.cumsum(w[i])
    return float(x[i][np.searchsorted(c, 0.5 * c[-1])])


def axis_mean(theta_deg, w):
    """Dominant axis of axial data (period 180 deg) + concentration R in [0,1]."""
    t = np.deg2rad(theta_deg) * 2.0
    C, S = np.average(np.cos(t), weights=w), np.average(np.sin(t), weights=w)
    return float(np.rad2deg(np.arctan2(S, C)) / 2.0 % 180.0), float(np.hypot(C, S))


# --- Bunge Euler <-> rotation matrix (v_crystal = g . v_sample) ------------
def euler_to_g(phi1, Phi, phi2):
    c1, s1 = np.cos(phi1), np.sin(phi1)
    c, s = np.cos(Phi), np.sin(Phi)
    c2, s2 = np.cos(phi2), np.sin(phi2)
    return np.array([
        [c1 * c2 - s1 * s2 * c,  s1 * c2 + c1 * s2 * c, s2 * s],
        [-c1 * s2 - s1 * c2 * c, -s1 * s2 + c1 * c2 * c, c2 * s],
        [s1 * s,                 -c1 * s,                c],
    ])


def g_to_euler(g):
    if abs(g[2, 2]) > 1 - 1e-8:
        Phi = 0.0 if g[2, 2] > 0 else np.pi
        phi1 = np.arctan2(g[0, 1], g[0, 0])
        phi2 = 0.0
    else:
        Phi = np.arccos(np.clip(g[2, 2], -1, 1))
        phi1 = np.arctan2(g[2, 0], -g[2, 1])
        phi2 = np.arctan2(g[0, 2], g[1, 2])
    return np.array([phi1 % (2 * np.pi), Phi, phi2 % (2 * np.pi)])


def random_smallrot(max_deg, rng):
    """Random rotation with angle <= max_deg about a uniform random axis."""
    ax = rng.normal(size=3)
    ax /= np.linalg.norm(ax)
    ang = np.deg2rad(max_deg) * rng.random()
    K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    return np.eye(3) + np.sin(ang) * K + (1 - np.cos(ang)) * K @ K
