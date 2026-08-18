#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import numpy as np


DEFAULT_CONFIG = {
    "enabled": False,
    "output_filename": "volume_cuboid.npy",
    "report_filename": "volume_cuboid.txt",
    "use_cuboid_for_meshing": False,
    "crop": {
        "enabled": False,
        "value": 0,
        "margin": 0,
    },
    "boundary_seal": {
        "enabled": False,
        "value": 0,
        "thickness": 1,
        "thicknesses": None,
    },
}


def deep_update(base, update):
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = value
    return base


def load_config(config_path):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if not config_path:
        return cfg
    with open(config_path, "r") as handle:
        full_config = json.load(handle)
    return deep_update(cfg, full_config.get("02d_axis_aligned_cuboid_crop", {}))


def value_counts(volume):
    values, counts = np.unique(volume, return_counts=True)
    return {str(int(value)): int(count) for value, count in zip(values, counts)}


def bounds_for_value(volume, value):
    coords = np.argwhere(volume == value)
    if coords.size == 0:
        raise ValueError(f"No voxels with crop value {value} found")
    lo = coords.min(axis=0)
    hi = coords.max(axis=0) + 1
    return lo, hi


def boundary_thicknesses(seal_cfg):
    base = int(seal_cfg.get("thickness", 1) or 1)
    thicknesses = {
        "x_min": base,
        "x_max": base,
        "y_min": base,
        "y_max": base,
        "z_min": base,
        "z_max": base,
    }
    configured = seal_cfg.get("thicknesses") or {}
    axis_aliases = {
        "x": ("x_min", "x_max"),
        "y": ("y_min", "y_max"),
        "z": ("z_min", "z_max"),
    }
    for key, value in configured.items():
        if key in axis_aliases:
            for face_key in axis_aliases[key]:
                thicknesses[face_key] = int(value)
        elif key in thicknesses:
            thicknesses[key] = int(value)
        else:
            raise ValueError(f"Unsupported boundary thickness key: {key}")
    for key, value in thicknesses.items():
        if value < 0:
            raise ValueError(f"Boundary thickness {key} must be >= 0")
    return thicknesses


def crop_to_value_bbox(volume, cfg):
    crop_cfg = cfg["crop"]
    if not crop_cfg.get("enabled", False):
        return volume, {
            "crop_enabled": False,
            "crop_value": crop_cfg.get("value", None),
            "crop_margin": crop_cfg.get("margin", 0),
            "crop_slices": "full_volume",
        }

    value = crop_cfg.get("value", 0)
    margin = int(crop_cfg.get("margin", 0) or 0)
    lo, hi = bounds_for_value(volume, value)
    lo = np.maximum(lo - margin, 0)
    hi = np.minimum(hi + margin, volume.shape)
    cropped = volume[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
    return cropped, {
        "crop_enabled": True,
        "crop_value": int(value),
        "crop_margin": margin,
        "crop_slices": {
            "x": [int(lo[0]), int(hi[0] - 1)],
            "y": [int(lo[1]), int(hi[1] - 1)],
            "z": [int(lo[2]), int(hi[2] - 1)],
        },
    }


def seal_boundary(volume, cfg):
    seal_cfg = cfg["boundary_seal"]
    if not seal_cfg.get("enabled", False):
        return volume, {
            "boundary_seal_enabled": False,
            "boundary_seal_value": seal_cfg.get("value", None),
            "boundary_seal_thickness": seal_cfg.get("thickness", 0),
            "boundary_voxels_changed": 0,
        }

    sealed = volume.copy()
    value = seal_cfg.get("value", 0)
    thicknesses = boundary_thicknesses(seal_cfg)
    if all(value == 0 for value in thicknesses.values()):
        return sealed, {
            "boundary_seal_enabled": True,
            "boundary_seal_value": int(value),
            "boundary_seal_thickness": 0,
            "boundary_seal_thicknesses": thicknesses,
            "boundary_voxels_changed": 0,
        }
    if sealed.shape[0] <= thicknesses["x_min"] + thicknesses["x_max"]:
        raise ValueError(f"Volume x-size {sealed.shape[0]} is too small for x boundary thicknesses {thicknesses}")
    if sealed.shape[1] <= thicknesses["y_min"] + thicknesses["y_max"]:
        raise ValueError(f"Volume y-size {sealed.shape[1]} is too small for y boundary thicknesses {thicknesses}")
    if sealed.shape[2] <= thicknesses["z_min"] + thicknesses["z_max"]:
        raise ValueError(f"Volume z-size {sealed.shape[2]} is too small for z boundary thicknesses {thicknesses}")

    before = sealed.copy()
    tx0, tx1 = thicknesses["x_min"], thicknesses["x_max"]
    ty0, ty1 = thicknesses["y_min"], thicknesses["y_max"]
    tz0, tz1 = thicknesses["z_min"], thicknesses["z_max"]
    if tx0 > 0:
        sealed[:tx0, :, :] = value
    if tx1 > 0:
        sealed[-tx1:, :, :] = value
    if ty0 > 0:
        sealed[:, :ty0, :] = value
    if ty1 > 0:
        sealed[:, -ty1:, :] = value
    if tz0 > 0:
        sealed[:, :, :tz0] = value
    if tz1 > 0:
        sealed[:, :, -tz1:] = value
    changed = int(np.count_nonzero(sealed != before))
    return sealed, {
        "boundary_seal_enabled": True,
        "boundary_seal_value": int(value),
        "boundary_seal_thickness": seal_cfg.get("thickness", 1),
        "boundary_seal_thicknesses": thicknesses,
        "boundary_voxels_changed": changed,
    }


def write_report(path, input_path, output_path, before, after, crop_info, seal_info):
    lines = [
        "Axis-aligned cuboid voxel preprocessing",
        f"Input volume: {input_path}",
        f"Output volume: {output_path}",
        "",
        "Before:",
        f"  shape: {before['shape']}",
        f"  value_counts: {before['value_counts']}",
        f"  value_0_fraction: {before.get('value_0_fraction', 'n/a')}",
        f"  value_1_fraction: {before.get('value_1_fraction', 'n/a')}",
        "",
        "Operations:",
    ]
    for key, value in crop_info.items():
        lines.append(f"  {key}: {value}")
    for key, value in seal_info.items():
        lines.append(f"  {key}: {value}")
    lines.extend([
        "",
        "After:",
        f"  shape: {after['shape']}",
        f"  value_counts: {after['value_counts']}",
        f"  value_0_fraction: {after.get('value_0_fraction', 'n/a')}",
        f"  value_1_fraction: {after.get('value_1_fraction', 'n/a')}",
        f"  voxel_count_delta: {after['voxel_count'] - before['voxel_count']}",
        "",
        "Interpretation:",
        "  crop.enabled cuts an axis-aligned rectangular voxel box around the chosen value.",
        "  boundary_seal.enabled forces configured outer face bands to one voxel value, giving SDF meshing a solid shell for boundary conditions.",
    ])
    path.write_text("\n".join(lines) + "\n")


def summarize(volume):
    total = int(volume.size)
    counts = value_counts(volume)
    summary = {
        "shape": tuple(int(v) for v in volume.shape),
        "voxel_count": total,
        "value_counts": counts,
    }
    for value in (0, 1):
        summary[f"value_{value}_fraction"] = int(np.count_nonzero(volume == value)) / total
    return summary


def main():
    parser = argparse.ArgumentParser(description="Optionally crop/seal a binary voxel volume to an axis-aligned cuboid before meshing.")
    parser.add_argument("--config", default=None, help="Optional config JSON containing 02d_axis_aligned_cuboid_crop")
    parser.add_argument("--npy", required=True, help="Input volume.npy path")
    parser.add_argument("--output", default=None, help="Output cuboid .npy path")
    parser.add_argument("--report", default=None, help="Output report .txt path")
    args = parser.parse_args()

    cfg = load_config(args.config)
    input_path = Path(args.npy)
    output_path = Path(args.output) if args.output else input_path.with_name(cfg["output_filename"])
    report_path = Path(args.report) if args.report else input_path.with_name(cfg["report_filename"])

    volume = np.load(input_path)
    before = summarize(volume)
    processed, crop_info = crop_to_value_bbox(volume, cfg)
    processed, seal_info = seal_boundary(processed, cfg)
    after = summarize(processed)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(output_path, processed.astype(volume.dtype, copy=False))
    write_report(report_path, input_path, output_path, before, after, crop_info, seal_info)

    print(f"Wrote cuboid volume: {output_path}")
    print(f"Wrote cuboid report: {report_path}")
    print(f"Shape: {before['shape']} -> {after['shape']}")
    print(f"Boundary voxels changed: {seal_info['boundary_voxels_changed']}")


if __name__ == "__main__":
    main()
