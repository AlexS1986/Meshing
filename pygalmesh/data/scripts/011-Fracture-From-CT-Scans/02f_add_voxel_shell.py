#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import numpy as np


DEFAULT_CONFIG = {
    "enabled": False,
    "value": 1,
    "output_filename": "volume_additive_shell.npy",
    "report_filename": "volume_additive_shell.txt",
    "use_shell_for_meshing": False,
    "thickness": 1,
    "thicknesses": None,
}


def load_config(path):
    with open(path, "r") as handle:
        full = json.load(handle)
    cfg = DEFAULT_CONFIG.copy()
    cfg.update(full.get("02f_add_voxel_shell", {}))
    return cfg


def resolve_thicknesses(cfg):
    base = int(cfg.get("thickness", 1) or 0)
    result = {
        "x_min": base, "x_max": base,
        "y_min": base, "y_max": base,
        "z_min": base, "z_max": base,
    }
    aliases = {"x": ("x_min", "x_max"), "y": ("y_min", "y_max"), "z": ("z_min", "z_max")}
    for key, value in (cfg.get("thicknesses") or {}).items():
        if key in aliases:
            for face in aliases[key]:
                result[face] = int(value)
        elif key in result:
            result[key] = int(value)
        else:
            raise ValueError(f"Unsupported shell thickness key: {key}")
    for key, value in result.items():
        if value < 0:
            raise ValueError(f"Shell thickness {key} must be >= 0")
    return result


def value_counts(volume):
    values, counts = np.unique(volume, return_counts=True)
    return {str(int(v)): int(c) for v, c in zip(values, counts)}


def add_shell(volume, cfg):
    thicknesses = resolve_thicknesses(cfg)
    tx0, tx1 = thicknesses["x_min"], thicknesses["x_max"]
    ty0, ty1 = thicknesses["y_min"], thicknesses["y_max"]
    tz0, tz1 = thicknesses["z_min"], thicknesses["z_max"]
    value = cfg.get("value", 1)
    new_shape = (volume.shape[0] + tx0 + tx1, volume.shape[1] + ty0 + ty1, volume.shape[2] + tz0 + tz1)
    shelled = np.full(new_shape, value, dtype=volume.dtype)
    shelled[tx0:tx0 + volume.shape[0], ty0:ty0 + volume.shape[1], tz0:tz0 + volume.shape[2]] = volume
    shell_voxels = int(shelled.size - volume.size)
    return shelled, {
        "shell_value": int(value),
        "thicknesses": thicknesses,
        "original_shape": tuple(int(v) for v in volume.shape),
        "shelled_shape": tuple(int(v) for v in shelled.shape),
        "original_voxels": int(volume.size),
        "shelled_voxels": int(shelled.size),
        "added_shell_voxels": shell_voxels,
        "volume_multiplier": float(shelled.size / volume.size) if volume.size else 0.0,
    }


def write_report(path, input_path, output_path, before_counts, after_counts, info):
    lines = [
        "Additive voxel shell report",
        "===========================",
        f"Input volume: {input_path}",
        f"Output volume: {output_path}",
        "",
    ]
    for key, value in info.items():
        lines.append(f"{key}: {value}")
    lines.extend([
        f"before_value_counts: {before_counts}",
        f"after_value_counts: {after_counts}",
        "",
        "Interpretation: this step pads the volume outward and fills only the newly added padding region; it does not overwrite the original cropped/mirrored voxel data.",
    ])
    Path(path).write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Pad a voxel volume outward with an additive shell before meshing.")
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--npy", required=True, help="Input volume.npy")
    parser.add_argument("--output", required=True, help="Output shelled .npy")
    parser.add_argument("--report", required=True, help="Output report .txt")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if not cfg.get("enabled", False):
        print("Additive voxel shell disabled in config; leaving volume unchanged.")
        return

    volume = np.load(args.npy)
    before_counts = value_counts(volume)
    shelled, info = add_shell(volume, cfg)
    np.save(args.output, shelled)
    write_report(args.report, args.npy, args.output, before_counts, value_counts(shelled), info)
    print(f"Additive voxel shell written: {args.output} shape={shelled.shape}")
    print(f"Wrote report: {args.report}")


if __name__ == "__main__":
    main()
