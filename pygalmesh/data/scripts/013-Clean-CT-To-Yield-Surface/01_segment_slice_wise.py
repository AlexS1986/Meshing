#!/usr/bin/env python3
"""Segment the CT grey-value stack into a binary volume.

Differences to 010-Yield-Surface-Generation/01_segment_slice_wise.py
--------------------------------------------------------------------
1. The Gaussian smoothing actually takes effect. In 010 the sigma was computed
   as ``gaussian_filter_sigma_factor * SliceThickness`` (a length in mm) and
   handed to ``scipy.ndimage.gaussian_filter``, which expects sigma in *voxels*.
   For JM-25-74 that produced sigma = 0.134 voxels, i.e. a kernel with central
   weight 1.000000 -- the identity. Here sigma is declared in voxels.
2. Smoothing is applied to the 3D volume by default instead of slice by slice.
   The reconstruction grid is isotropic, so there is no reason to smooth in
   x/y but not in z. The filter is separable and is applied in two streaming
   passes, so peak memory stays at one z-slab, not the whole stack.
3. Dead knobs removed (median filter, per-slice morphology). 3D morphology
   belongs in 02c_voxel_topology_cleanup.py, where it can see real components.

Phase convention -- unchanged on purpose
----------------------------------------
``mask = image <= threshold`` selects the *dark* phase. In the AlSi10Mg scans
the aluminium is the bright phase, therefore the stored array is

    1 = pore / surrounding air
    0 = aluminium

03_mesh_3D_array_pygalmesh.py meshes the voxels with value 0. This is exactly
the convention of 010 and must not be changed without changing 02d and 03 as
well.
"""

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import ndimage as ndi
from skimage import filters

THRESHOLD_METHODS = {
    "otsu": filters.threshold_otsu,
    "yen": filters.threshold_yen,
    "li": filters.threshold_li,
    "triangle": filters.threshold_triangle,
    "isodata": filters.threshold_isodata,
    "mean": filters.threshold_mean,
    "minimum": filters.threshold_minimum,
}


def load_config(config_path):
    with open(config_path, "r") as handle:
        config = json.load(handle)
    return config["01_segment_slice_wise"], config["metadata_output_path"]


def read_voxel_size(metadata_path):
    """Only used for the metadata record; sigma is defined in voxels."""
    with open(metadata_path, "r") as handle:
        metadata = json.load(handle)
    return float(metadata["00_dicom2npy"]["SliceThickness"])


def compute_threshold(values, method, multiplier, offset):
    if isinstance(method, (int, float)):
        return float(method) * multiplier + offset
    key = str(method).lower()
    if key not in THRESHOLD_METHODS:
        raise ValueError(
            f"Unsupported threshold method '{method}'. "
            f"Use a number or one of: {', '.join(sorted(THRESHOLD_METHODS))}"
        )
    return float(THRESHOLD_METHODS[key](values)) * multiplier + offset


def gaussian_kernel_report(sigma):
    """Prove that the configured sigma does something. Printed to the log."""
    if sigma <= 0.0:
        return "sigma = 0 -> smoothing disabled"
    impulse = np.zeros(2 * int(np.ceil(4 * sigma)) + 1, dtype=np.float64)
    impulse[len(impulse) // 2] = 1.0
    kernel = ndi.gaussian_filter1d(impulse, sigma=sigma)
    centre = kernel[len(kernel) // 2]
    neighbour = kernel[len(kernel) // 2 + 1] if len(kernel) > 1 else 0.0
    verdict = "effective" if centre < 0.999 else "NO-OP -- sigma is far too small"
    return (
        f"sigma = {sigma:g} voxels -> centre weight {centre:.6f}, "
        f"neighbour weight {neighbour:.6f} ({verdict})"
    )


def smooth_stack(slice_paths, sigma, mode, work_path):
    """Separable Gaussian over the stack, streaming.

    Pass 1 filters each slice in-plane and writes float32 into a memmap.
    Pass 2 filters along z column-block by column-block. Columns are
    independent under a 1D filter along z, so in-place is safe.

    Returns an open read-only memmap of shape (Z, H, W).
    """
    first = np.load(slice_paths[0])
    height, width = first.shape
    depth = len(slice_paths)

    volume = np.lib.format.open_memmap(
        work_path, mode="w+", dtype=np.float32, shape=(depth, height, width)
    )

    in_plane = sigma if mode in ("3d", "2d") else 0.0
    for index, path in enumerate(slice_paths):
        data = np.load(path).astype(np.float32, copy=False)
        if data.shape != (height, width):
            raise ValueError(
                f"Slice {path} has shape {data.shape}, expected {(height, width)}"
            )
        if in_plane > 0.0:
            data = ndi.gaussian_filter(data, sigma=in_plane)
        volume[index] = data

    if mode == "3d" and sigma > 0.0:
        column_block = max(1, int(64 * 1024 * 1024 / (depth * height * 4)))
        for start in range(0, width, column_block):
            stop = min(start + column_block, width)
            block = np.array(volume[:, :, start:stop])
            volume[:, :, start:stop] = ndi.gaussian_filter1d(block, sigma=sigma, axis=0)

    volume.flush()
    del volume
    return np.load(work_path, mmap_mode="r")


def save_preview(mask, output_path):
    fig, ax = plt.subplots()
    ax.imshow(mask, cmap="gray", interpolation="nearest")
    ax.axis("off")
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def write_metadata(metadata_path, record):
    with open(metadata_path, "r") as handle:
        metadata = json.load(handle)
    metadata["01_segment_slice_wise"] = record
    with open(metadata_path, "w") as handle:
        json.dump(metadata, handle, indent=4)


def main():
    script_path = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=os.path.join(script_path, "config.json"))
    args = parser.parse_args()

    config_path = (
        args.config if os.path.isabs(args.config) else os.path.join(script_path, args.config)
    )
    config, metadata_path = load_config(config_path)

    input_folder = config["input_folder"]
    output_folder = config["output_folder"]
    os.makedirs(output_folder, exist_ok=True)

    sigma = float(config.get("gaussian_sigma_voxels", 1.0))
    smoothing_mode = str(config.get("smoothing_mode", "3d")).lower()
    if smoothing_mode not in ("3d", "2d", "none"):
        raise ValueError("smoothing_mode must be one of '3d', '2d', 'none'")
    if smoothing_mode == "none":
        sigma = 0.0

    method = config.get("seg_algorithm", "otsu")
    threshold_scope = str(config.get("threshold_scope", "slice")).lower()
    if threshold_scope not in ("slice", "volume"):
        raise ValueError("threshold_scope must be 'slice' or 'volume'")
    multiplier = float(config.get("threshold_multiplier", 1.0))
    offset = float(config.get("threshold_offset", 0.0))
    invert_contrast = bool(config.get("invert_contrast", True))
    preview_index = int(config.get("preview_slice_index", -1))

    slice_names = sorted(name for name in os.listdir(input_folder) if name.endswith(".npy"))
    if not slice_names:
        raise FileNotFoundError(f"No .npy slices found in {input_folder}")
    slice_paths = [os.path.join(input_folder, name) for name in slice_names]

    print(f"Slices: {len(slice_paths)} from {input_folder}")
    print(f"Smoothing mode: {smoothing_mode}")
    print(f"Gaussian check: {gaussian_kernel_report(sigma)}")
    print(f"Threshold: {method} (scope={threshold_scope}, x{multiplier} {offset:+g})")

    work_path = os.path.join(output_folder, "_smoothing_work.npy")
    volume = smooth_stack(slice_paths, sigma, smoothing_mode, work_path)

    global_threshold = None
    if threshold_scope == "volume":
        step = max(1, int(round((volume.size / 8e6) ** (1 / 3))))
        sample = np.asarray(volume[::step, ::step, ::step], dtype=np.float32).ravel()
        global_threshold = compute_threshold(sample, method, multiplier, offset)
        print(f"Global threshold on {sample.size} sampled voxels (step {step}): {global_threshold:.6g}")

    thresholds = []
    for index in range(volume.shape[0]):
        image = np.asarray(volume[index], dtype=np.float32)
        threshold = (
            global_threshold
            if global_threshold is not None
            else compute_threshold(image, method, multiplier, offset)
        )
        thresholds.append(float(threshold))

        mask = image <= threshold
        if not invert_contrast:
            mask = ~mask
        segmented = mask.astype(np.uint8)

        np.save(os.path.join(output_folder, f"segmented_slice_{index:04d}.npy"), segmented)
        if index == preview_index:
            save_preview(segmented, os.path.join(output_folder, f"preview_slice_{index:04d}.png"))

    del volume
    os.remove(work_path)

    pore_fraction = None
    if thresholds:
        preview = np.load(os.path.join(output_folder, f"segmented_slice_{len(thresholds)//2:04d}.npy"))
        pore_fraction = float(preview.mean())

    write_metadata(
        metadata_path,
        {
            "voxel_size_mm": read_voxel_size(metadata_path),
            "smoothing_mode": smoothing_mode,
            "gaussian_sigma_voxels": sigma,
            "gaussian_kernel_check": gaussian_kernel_report(sigma),
            "threshold_method": method,
            "threshold_scope": threshold_scope,
            "threshold_multiplier": multiplier,
            "threshold_offset": offset,
            "invert_contrast": invert_contrast,
            "threshold_min": min(thresholds),
            "threshold_max": max(thresholds),
            "threshold_mean": float(np.mean(thresholds)),
            "slices": len(thresholds),
            "array_value_1_meaning": "pore / air",
            "array_value_0_meaning": "aluminium (this is the phase that gets meshed)",
            "mid_slice_value_1_fraction": pore_fraction,
        },
    )
    print(f"Wrote {len(thresholds)} segmented slices to {output_folder}")


if __name__ == "__main__":
    main()
