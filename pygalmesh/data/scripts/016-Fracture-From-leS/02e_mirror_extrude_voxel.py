#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import numpy as np


DEFAULT_CONFIG = {
    "enabled": False,
    "axis": "x",
    "plane": "min",
    "material_value": 1,
    "output_filename": "volume_mirrored_x.npy",
    "report_filename": "volume_mirrored_x.txt",
    "use_mirrored_for_meshing": False,
    "drop_duplicate_plane": True,
    "repetitions": 1,
}


def load_config(path):
    with open(path, "r") as handle:
        full = json.load(handle)
    cfg = DEFAULT_CONFIG.copy()
    cfg.update(full.get("02e_mirror_extrude_voxel", {}))
    return cfg


def axis_index(axis):
    axis = str(axis).lower()
    mapping = {"x": 0, "y": 1, "z": 2}
    if axis not in mapping:
        raise ValueError(f"Unsupported axis: {axis}; expected x, y, or z")
    return mapping[axis], axis


def mirror_once(volume, axis, plane, drop_duplicate_plane=True):
    axis_i, axis_name = axis_index(axis)
    plane = str(plane).lower()
    if plane in ("xmin", "ymin", "zmin"):
        plane = "min"
    if plane in ("xmax", "ymax", "zmax"):
        plane = "max"
    if plane not in ("min", "max"):
        raise ValueError(f"Unsupported plane: {plane}; expected min/max or {axis_name}min/{axis_name}max")

    mirrored = np.flip(volume, axis=axis_i)
    if drop_duplicate_plane and volume.shape[axis_i] > 1:
        if plane == "min":
            slicer = [slice(None)] * volume.ndim
            slicer[axis_i] = slice(0, -1)
            mirrored_part = mirrored[tuple(slicer)]
            result = np.concatenate((mirrored_part, volume), axis=axis_i)
        else:
            slicer = [slice(None)] * volume.ndim
            slicer[axis_i] = slice(1, None)
            mirrored_part = mirrored[tuple(slicer)]
            result = np.concatenate((volume, mirrored_part), axis=axis_i)
    else:
        result = np.concatenate((mirrored, volume), axis=axis_i) if plane == "min" else np.concatenate((volume, mirrored), axis=axis_i)
    return result, {
        "axis": axis_name,
        "plane": plane,
        "drop_duplicate_plane": bool(drop_duplicate_plane),
        "input_shape": tuple(int(v) for v in volume.shape),
        "output_shape": tuple(int(v) for v in result.shape),
        "input_voxels": int(volume.size),
        "output_voxels": int(result.size),
        "volume_multiplier": float(result.size / volume.size) if volume.size else 0.0,
    }


def mirror_volume(volume, axis, plane, drop_duplicate_plane=True, repetitions=1):
    repetitions = int(repetitions or 1)
    if repetitions < 1:
        raise ValueError(f"repetitions must be >= 1, got {repetitions}")
    current = volume
    steps = []
    original_shape = tuple(int(v) for v in volume.shape)
    original_voxels = int(volume.size)
    for index in range(repetitions):
        current, info = mirror_once(current, axis, plane, drop_duplicate_plane)
        info["step"] = index + 1
        steps.append(info)
    return current, {
        "axis": steps[-1]["axis"],
        "plane": steps[-1]["plane"],
        "drop_duplicate_plane": bool(drop_duplicate_plane),
        "repetitions": repetitions,
        "original_shape": original_shape,
        "mirrored_shape": tuple(int(v) for v in current.shape),
        "original_voxels": original_voxels,
        "mirrored_voxels": int(current.size),
        "volume_multiplier": float(current.size / original_voxels) if original_voxels else 0.0,
        "steps": steps,
    }


def write_report(path, info, before_material, after_material):
    lines = [
        "Voxel mirror extrusion report",
        "==============================",
        "",
    ]
    for key, value in info.items():
        lines.append(f"{key}: {value}")
    lines.extend([
        f"original_material_voxels: {before_material}",
        f"mirrored_material_voxels: {after_material}",
        f"material_multiplier: {after_material / before_material if before_material else 0.0}",
    ])
    Path(path).write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Mirror-extrude a cropped voxel volume before meshing.")
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--npy", required=True, help="Input volume.npy")
    parser.add_argument("--output", required=True, help="Output mirrored .npy")
    parser.add_argument("--report", required=True, help="Output report .txt")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if not cfg.get("enabled", False):
        print("Voxel mirror extrusion disabled in config; leaving volume unchanged.")
        return

    volume = np.load(args.npy)
    material_value = cfg.get("material_value", 1)
    mirrored, info = mirror_volume(
        volume,
        cfg.get("axis", "x"),
        cfg.get("plane", "min"),
        bool(cfg.get("drop_duplicate_plane", True)),
        int(cfg.get("repetitions", 1) or 1),
    )
    np.save(args.output, mirrored)
    write_report(
        args.report,
        info,
        int(np.count_nonzero(volume == material_value)),
        int(np.count_nonzero(mirrored == material_value)),
    )
    print(f"Voxel mirror extrusion written: {args.output} shape={mirrored.shape}")
    print(f"Wrote report: {args.report}")


if __name__ == "__main__":
    main()
