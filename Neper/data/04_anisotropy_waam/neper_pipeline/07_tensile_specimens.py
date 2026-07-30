#!/usr/bin/env python3
"""
Step 7 (optional): Three flat tensile-gauge meshes (V / H / 45deg) with the
fitted WAAM microstructure, for FEniCSx.  Material-parametrized.

Specimen frame:  x = load axis (length), y = width, z = thickness.
Gauge box (default 3000 x 1200 x 500 um) centered at the origin.
Columnar grain axis (= build direction) lies in the x-y plane at angle
ALPHA to the load axis:  V: 0deg, H: 90deg, 45deg: 45deg.

Method per specimen:
  1. inverse-transform the gauge box with T^-1 (T = rotate_z(alpha) . scale_x(k))
     -> convex parallelepiped, written as a Neper `planes()` domain
     (the plane-file convention is auto-detected with a quick voronoi test)
  2. neper -T with the fitted relative diameq/sphericity distributions
     (equiaxed in the scaled space), then -transform "scale(k,1,1),rotate(z,alpha)"
     -> exact gauge box with tilted columnar grains
  3. neper -M  -> .msh,   meshio -> .xdmf (cell tag "grain")
  4. orientations: area-weighted bootstrap from the material's build-section
     EBSD map, rotated so the build direction lands at angle alpha in the x-y
     plane -> grain_ori_<MAT>_<name>.txt (id phi1 Phi phi2 crystal).  Geometry
     and crystallography are decoupled (statistically equivalent here).

Material selection:  MAT=316L (default) | 17-4PH
Run inside the container:  MAT=316L python3 07_tensile_specimens.py
Env: RCL (default 0.75), MORPHOSTOP (default val=1e-2||itermax=100000),
     FAST=1 -> voronoi.
"""
import json
import os
import subprocess
import zlib

import numpy as np

import materials as M

HERE = os.path.dirname(os.path.abspath(__file__))

MAT = os.environ.get("MAT", "316L")
PJSON = os.path.join(HERE, f"params_{MAT}.json")
if not os.path.exists(PJSON):
    raise SystemExit(f"missing {PJSON} - run: python3 01_fit_ebsd.py --material {MAT}")
P = json.load(open(PJSON))
K = P["elongation"]["k_used"]
CV = P["transverse"]["width2D_cv"]
D_MED = P["transverse"]["d3D_median_um"]
THETA = np.deg2rad(P["build_axis_in_vertical_map_deg"])
# grain-shape scale in the BUILD frame (x=build, y=weld, z=wall-normal); this is
# rotated by the specimen angle alpha about z so build lands at alpha to the load
# axis. columnar -> (k,1,1); equiaxed -> (1,1,1); orthotropic -> (k_build,1,1/k_inplane).
SB = P["neper"].get("scale_build_frame", [K, 1.0, 1.0])
SBX, SBY, SBZ = float(SB[0]), float(SB[1]), float(SB[2])
SCALE_PROD = SBX * SBY * SBZ

GAUGE = (float(os.environ.get("LX", 3000.0)),
         float(os.environ.get("LY", 1200.0)),
         float(os.environ.get("LZ", 500.0)))     # um: length x width x thickness
SPECIMENS = {"V": 0.0, "H": 90.0, "45deg": 45.0}
RCL = os.environ.get("RCL", "0.75")
# Grain cap keeps fine-grained steels (17-4PH ~10 um) tractable: without it a
# mm-scale bar needs ~2000 grains/specimen (hours of optimization + meshing
# risk). Capping coarsens the grains to fit; a warning is printed.
MAXGRAINS = int(os.environ.get("MAXGRAINS", 500))
# NOTE: for the flat gauge (only ~3-4 grains through thickness) the objective
# plateaus around f~0.008, so a strict val never terminates; itermax bounds it.
MORPHOSTOP = os.environ.get("MORPHOSTOP", "val=1e-2||itermax=20000")
FAST = os.environ.get("FAST", "0") == "1"
# escalating rcl retry: robust against the occasional gmsh 3D-meshing SIGABRT.
RCL_RETRIES = [RCL] + [r for r in ("1.0", "1.5", "2.0") if r != RCL]

s_ln = float(np.sqrt(np.log(1 + round(CV, 2) ** 2)))
MEAN_VOL = np.pi / 6.0 * D_MED ** 3 * np.exp(4.5 * s_ln ** 2)   # scaled space
MORPHO = ("voronoi" if FAST else
          f"diameq:lognormal(1,{round(CV,2)}),1-sphericity:lognormal(0.145,0.03)")


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


def run(cmd):
    print("  $", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=HERE)


def parallelepiped_planes(alpha_deg):
    """6 outward half-planes of T^-1(gauge box), T = Rz(alpha).S with
    S = diag(SBX,SBY,SBZ) the grain-shape stretch (build frame). Plane n.x = d
    maps to (T^T n).x' = d under x' = T^-1 x."""
    a = np.deg2rad(alpha_deg)
    Rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    S = np.diag([SBX, SBY, SBZ])
    T = Rz @ S
    planes = []
    for i in range(3):
        for sgn in (+1.0, -1.0):
            n = np.zeros(3)
            n[i] = sgn
            d = GAUGE[i] / 2.0
            m = T.T @ n
            nm = np.linalg.norm(m)
            planes.append(np.concatenate([[d / nm], m / nm]))   # d a b c
    return np.array(planes)


def write_planes(planes, path, order):
    with open(path, "w") as f:
        f.write(f"{len(planes)}\n")
        for p in planes:
            d, a, b, c = p
            f.write(f"{a} {b} {c} {d}\n" if order == "abcd" else f"{d} {a} {b} {c}\n")


def detect_planes_order(planes, v_expected):
    """Try file conventions until a quick voronoi run reproduces the volume."""
    for order in ("dabc", "abcd"):
        for flip in (1.0, -1.0):
            pl = planes.copy()
            pl[:, 1:] *= flip
            pl[:, 0] *= flip
            write_planes(pl, os.path.join(HERE, "_domtest.txt"), order)
            try:
                subprocess.run(
                    ["neper", "-T", "-n", "20", "-domain", "planes(_domtest.txt)",
                     "-statcell", "vol", "-o", "_domtest", "-format", "tess"],
                    check=True, cwd=HERE, capture_output=True, text=True)
                v = np.loadtxt(os.path.join(HERE, "_domtest.stcell")).sum()
                if abs(v - v_expected) < 0.01 * v_expected:
                    print(f"  planes() convention: order={order}, flip={flip:+.0f}")
                    return order, flip
            except subprocess.CalledProcessError:
                continue
    raise RuntimeError("could not determine Neper planes() file convention")


def sample_orientations(n, alpha_deg, seed):
    """Bootstrap Eulers from the material's build-section map; build dir ->
    angle alpha in x-y.  Returns (eulers_deg, crystal_system)."""
    rng = np.random.default_rng(seed)
    cfg = M.MATERIALS[MAT]
    dv = M.load_sections(MAT)[cfg["build_section"]]
    a = THETA - np.deg2rad(alpha_deg)
    # specimen basis in map coords (map normal -> specimen z/thickness)
    R = np.array([[np.cos(a), -np.sin(a), 0],
                  [np.sin(a),  np.cos(a), 0],
                  [0,          0,         1]])
    idx = rng.choice(len(dv), size=n, p=dv.area_um2.values / dv.area_um2.values.sum())
    eulers = np.deg2rad(dv[["phi1_deg", "PHI_deg", "phi2_deg"]].values[idx])
    crystals = dv["crystal"].values[idx]
    out = []
    for e in eulers:
        g = M.euler_to_g(*e) @ R @ M.random_smallrot(3.0, rng)
        out.append(np.rad2deg(M.g_to_euler(g)))
    return np.array(out), crystals


def main():
    lx, ly, lz = GAUGE
    v_scaled = lx * ly * lz / SCALE_PROD          # scaled (pre-stretch) volume
    n_phys = int(round(v_scaled / MEAN_VOL))
    n = min(n_phys, MAXGRAINS)
    note = "" if n == n_phys else f"  [CAPPED from {n_phys} via MAXGRAINS={MAXGRAINS}]"
    print(f"# [{MAT}] gauge {lx:.0f}x{ly:.0f}x{lz:.0f} um, shape scale(build)={SBX},{SBY},{SBZ} "
          f"-> n={n} grains/specimen{note}")
    print(f"# morpho: {MORPHO}  (stop: {MORPHOSTOP})")

    planes0 = parallelepiped_planes(45.0)
    order, flip = detect_planes_order(planes0, v_scaled)

    # ---- phase 1: the three tessellations run IN PARALLEL ---------------
    procs = {}
    for name, alpha in SPECIMENS.items():
        out = f"spec_{MAT}_{name}"
        pl = parallelepiped_planes(alpha)
        pl[:, 1:] *= flip
        pl[:, 0] *= flip
        write_planes(pl, os.path.join(HERE, f"{out}_dom.txt"), order)

        cmd = ["neper", "-T", "-n", str(n),
               "-domain", f"planes({out}_dom.txt)",
               "-morpho", MORPHO]
        if not FAST:
            cmd += ["-morphooptistop", MORPHOSTOP]
        cmd += ["-transform", f"scale({SBX},{SBY},{SBZ}),rotate(0,0,1,{alpha})",
                "-statcell", "id,vol,diameq,sphericity,x,y,z",
                "-o", out, "-format", "tess"]
        log = open(os.path.join(HERE, f"{out}.log"), "w")
        print(f"start {out} (alpha={alpha} deg) -> {out}.log", flush=True)
        procs[name] = (subprocess.Popen(cmd, cwd=HERE, stdout=log, stderr=log), log)

    for name, (p, log) in procs.items():
        rc = p.wait()
        log.close()
        if rc != 0:
            raise RuntimeError(f"neper -T failed for {name}, see spec_{MAT}_{name}.log")
        print(f"done: spec_{MAT}_{name}", flush=True)

    # ---- phase 2: meshing + conversion + orientations -------------------
    for name, alpha in SPECIMENS.items():
        out = f"spec_{MAT}_{name}"
        print(f"\n=== meshing {MAT} {name} ===", flush=True)
        mesh_with_retry(out)
        run(["python3", "04_convert_to_xdmf.py", os.path.join(HERE, f"{out}.msh")])

        ori, crystals = sample_orientations(
            n, alpha, seed=zlib.crc32(f"{MAT}_{name}".encode()))
        with open(os.path.join(HERE, f"grain_ori_{MAT}_{name}.txt"), "w") as f:
            f.write(f"# material={MAT}; build dir at {alpha} deg to load axis x "
                    "in x-y plane\n# grain_id phi1 Phi phi2 (Bunge, deg) crystal\n")
            for i, (e, c) in enumerate(zip(ori, crystals), 1):
                f.write(f"{i} {e[0]:.3f} {e[1]:.3f} {e[2]:.3f} {c}\n")

        # sanity: domain volume
        v = np.loadtxt(os.path.join(HERE, f"{out}.stcell"), usecols=1).sum()
        print(f"  volume check: {v:.3e} um^3 (target {lx*ly*lz:.3e})")
        subprocess.run(["neper", "-V", f"{out}.tess", "-datacellcol", "id",
                        "-print", f"{out}_view"], cwd=HERE,
                       capture_output=True)

    for f in os.listdir(HERE):
        if f.startswith("_domtest"):
            os.remove(os.path.join(HERE, f))
    print(f"\n=== done: spec_{MAT}_V / _H / _45deg (.tess/.msh/.xdmf) "
          f"+ grain_ori_{MAT}_<name>.txt ===")


if __name__ == "__main__":
    main()
