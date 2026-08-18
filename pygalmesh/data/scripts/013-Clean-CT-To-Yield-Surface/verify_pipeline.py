#!/usr/bin/env python3
"""Self-checks for the 013 pipeline. Run this before trusting a production run.

    python3 verify_pipeline.py                 # all checks on synthetic data
    python3 verify_pipeline.py --npy PATH      # additionally check a real volume

Checks
------
A  Phase convention: the mask handed to marching_cubes/pygalmesh in 013 is
   bit-identical to what 010 produced. This is the hard requirement -- the
   meshing libraries must keep seeing exactly the same 0/1 regions.
B  Smoothing: the configured sigma actually changes the data, and 010's sigma
   did not.
C  Separable 3D Gaussian: the streaming two-pass implementation in 01 matches
   a direct scipy.ndimage.gaussian_filter on the full volume.
D  Metadata bookkeeping: solid volume fraction is reported as the solid
   fraction, not as the porosity.
"""

import argparse
import importlib.util
import os
import sys
import tempfile

import numpy as np
from scipy import ndimage as ndi
from skimage import filters

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_module(filename, name):
    path = os.path.join(SCRIPT_DIR, filename)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mask_010(volume):
    """Reproduce 010's chain on a binary array, without nanomesh.

    010 did:
        subvol.gaussian(sigma = smoothing_sigma_factor * SliceThickness)
            -> no-op, sigma was ~0.13 voxels (see check B)
        .binary_digitize(threshold='otsu')   -> image > otsu(image)
        .invert_contrast()                   -> logical complement
        material_mask = (result == 1)
    """
    threshold = filters.threshold_otsu(volume.astype(np.float32))
    digitized = volume > threshold
    inverted = ~digitized
    return inverted


def check_phase_convention():
    rng = np.random.default_rng(0)
    failures = []
    mesh_mod = load_module("03_mesh_3D_array_pygalmesh.py", "mesh013")

    for trial in range(20):
        shape = tuple(int(v) for v in rng.integers(6, 20, size=3))
        volume = rng.integers(0, 2, size=shape).astype(np.uint8)
        if volume.min() == volume.max():          # Otsu needs two levels
            continue
        expected = mask_010(volume)
        actual = mesh_mod.build_material_mask(volume, 0)
        if not np.array_equal(expected, actual):
            failures.append(f"trial {trial}: shape {shape}, {int((expected != actual).sum())} voxels differ")

    if failures:
        return False, "Mask differs from 010:\n    " + "\n    ".join(failures)

    # A binary-only guard must exist: grey values must be rejected, not silently meshed.
    try:
        mesh_mod.build_material_mask(np.array([[[0, 5, 250]]], dtype=np.uint16), 0)
    except ValueError:
        pass
    else:
        return False, "build_material_mask accepted a non-binary array"

    return True, "013 mask == 010 mask on 20 random volumes; non-binary input rejected"


def check_smoothing_effectiveness():
    seg = load_module("01_segment_slice_wise.py", "seg013")

    broken_sigma = 0.13390576171875          # 010: 1 * SliceThickness in mm
    fixed_sigma = 1.0                        # 013: voxels

    broken = seg.gaussian_kernel_report(broken_sigma)
    fixed = seg.gaussian_kernel_report(fixed_sigma)

    if "NO-OP" not in broken:
        return False, f"Expected 010's sigma to be a no-op, got: {broken}"
    if "effective" not in fixed:
        return False, f"Expected sigma=1.0 voxels to be effective, got: {fixed}"

    rng = np.random.default_rng(1)
    image = rng.random((64, 64)).astype(np.float32)
    if not np.array_equal(image, ndi.gaussian_filter(image, sigma=broken_sigma)):
        return False, "010's sigma did change the image -- assumption wrong"
    changed = float(np.abs(image - ndi.gaussian_filter(image, sigma=fixed_sigma)).mean())
    if changed <= 0.0:
        return False, "sigma=1.0 voxels did not change the image"

    return True, (
        f"010 sigma={broken_sigma:g}mm -> unchanged data. "
        f"013 sigma={fixed_sigma:g} voxels -> mean |delta| = {changed:.5f}. "
        f"[{fixed}]"
    )


def check_separable_3d_gaussian():
    seg = load_module("01_segment_slice_wise.py", "seg013b")
    rng = np.random.default_rng(2)
    depth, height, width = 17, 23, 29
    volume = rng.random((depth, height, width)).astype(np.float32)
    sigma = 1.3

    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for index in range(depth):
            path = os.path.join(tmp, f"slice_{index:04d}.npy")
            np.save(path, volume[index])
            paths.append(path)
        work = os.path.join(tmp, "work.npy")
        streamed = np.asarray(seg.smooth_stack(paths, sigma, "3d", work), dtype=np.float32)
        reference = ndi.gaussian_filter(volume, sigma=sigma)
        max_error = float(np.abs(streamed - reference).max())

    if max_error > 1e-4:
        return False, f"Streaming 3D Gaussian deviates from scipy: max error {max_error:.3g}"
    return True, f"Streaming 3D Gaussian == scipy.gaussian_filter (max error {max_error:.2g})"


def check_density_bookkeeping():
    """02b must report the solid fraction as relative_density.

    Array value 1 = pore, so counting value-1 voxels (as 010 did) yields the
    porosity. Emulate 02b's corrected arithmetic on a volume with a known
    solid fraction.
    """
    volume = np.ones((10, 10, 10), dtype=np.uint8)
    volume[:4] = 0                       # 40 % aluminium (value 0)
    material_value = 1                   # config label: the pore phase

    total = volume.size
    pore_count = int(np.count_nonzero(volume == material_value))
    relative_density = (total - pore_count) / total
    porosity = pore_count / total

    if abs(relative_density - 0.4) > 1e-12 or abs(porosity - 0.6) > 1e-12:
        return False, f"relative_density={relative_density}, porosity={porosity}; expected 0.4 / 0.6"
    return True, "relative_density = solid fraction (0.40), porosity = 0.60 -- no longer swapped"


def check_real_volume(npy_path):
    mesh_mod = load_module("03_mesh_3D_array_pygalmesh.py", "mesh013real")
    volume = np.load(npy_path)
    expected = mask_010(volume)
    actual = mesh_mod.build_material_mask(volume, 0)
    if not np.array_equal(expected, actual):
        return False, f"{npy_path}: {int((expected != actual).sum())} voxels differ from 010"
    fraction = float(actual.mean())
    return True, (
        f"{os.path.basename(npy_path)}: mask identical to 010, "
        f"solid volume fraction {fraction:.4f} (porosity {1 - fraction:.4f})"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--npy", help="Optional real voxel volume to cross-check")
    args = parser.parse_args()

    checks = [
        ("A  phase convention identical to 010", check_phase_convention),
        ("B  smoothing is effective", check_smoothing_effectiveness),
        ("C  streaming 3D Gaussian correct", check_separable_3d_gaussian),
        ("D  density bookkeeping", check_density_bookkeeping),
    ]
    if args.npy:
        checks.append((f"E  real volume {os.path.basename(args.npy)}",
                       lambda: check_real_volume(args.npy)))

    failed = 0
    for label, check in checks:
        try:
            ok, message = check()
        except Exception as exc:                      # noqa: BLE001
            ok, message = False, f"{type(exc).__name__}: {exc}"
        print(f"[{'PASS' if ok else 'FAIL'}] {label}\n       {message}")
        failed += not ok

    print()
    if failed:
        print(f"{failed} of {len(checks)} checks FAILED")
        return 1
    print(f"all {len(checks)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
