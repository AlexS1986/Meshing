#!/usr/bin/env python3
import os
import json
import meshio
import numpy as np
import argparse


def load_config(config_path):
    with open(config_path, "r") as file:
        return json.load(file)


def load_voxel_size(metadata_path):
    with open(metadata_path, "r") as file:
        metadata = json.load(file)
    return float(metadata["00_dicom2npy"]["SliceThickness"])


def load_shape_from_npy(npy_path):
    return tuple(int(v) for v in np.load(npy_path, mmap_mode="r").shape)


def load_subvolume_shape(metadata_path):
    with open(metadata_path, "r") as file:
        metadata = json.load(file)
    try:
        subvolumes = metadata["02b_build_subvolume_arrays.py"]["subvolumes"]
        if not subvolumes:
            raise ValueError("❌ No subvolumes found in metadata.")
        shape = subvolumes[0]["shape"]  # [Nx, Ny, Nz]
        return shape
    except (KeyError, IndexError, ValueError) as e:
        raise RuntimeError("❌ Failed to extract 'shape' from first saved subvolume in metadata.") from e



def load_subvolume_entry(metadata_path, center_x, center_y):
    with open(metadata_path, "r") as file:
        metadata = json.load(file)
    subvolumes = metadata["02b_build_subvolume_arrays.py"].get("subvolumes", [])
    for entry in subvolumes:
        if int(entry.get("x_start", -1)) == int(center_x) and int(entry.get("y_start", -1)) == int(center_y):
            return entry
    if subvolumes:
        return subvolumes[0]
    raise ValueError("No subvolume entries found in metadata")


def boundary_thicknesses(cfg):
    base = int(cfg.get("thickness", 0) or 0)
    thicknesses = {
        "x_min": base,
        "x_max": base,
        "y_min": base,
        "y_max": base,
        "z_min": base,
        "z_max": base,
    }
    aliases = {"x": ("x_min", "x_max"), "y": ("y_min", "y_max"), "z": ("z_min", "z_max")}
    for key, value in (cfg.get("thicknesses") or {}).items():
        if key in aliases:
            for face in aliases[key]:
                thicknesses[face] = int(value)
        elif key in thicknesses:
            thicknesses[key] = int(value)
    return thicknesses


def transformed_voxel_bounds(config, metadata_path, npy_shape, center_x, center_y):
    entry = load_subvolume_entry(metadata_path, center_x, center_y)
    origin = np.array([
        int(entry["x_start"]),
        int(entry["y_start"]),
        int(entry.get("z_start", 0)),
    ], dtype=float)
    shape = np.array(entry["shape"], dtype=int)

    mirror_cfg = config.get("02e_mirror_extrude_voxel", {})
    if mirror_cfg.get("enabled", False) and mirror_cfg.get("use_mirrored_for_meshing", False):
        axis_name = str(mirror_cfg.get("axis", "x")).lower()
        axis = {"x": 0, "y": 1, "z": 2}[axis_name]
        plane = str(mirror_cfg.get("plane", "min")).lower()
        if plane in (f"{axis_name}min", "min"):
            plane = "min"
        elif plane in (f"{axis_name}max", "max"):
            plane = "max"
        else:
            raise ValueError(f"Unsupported voxel mirror plane: {plane}")
        drop_duplicate = bool(mirror_cfg.get("drop_duplicate_plane", True))
        repetitions = int(mirror_cfg.get("repetitions", 1) or 1)
        for _ in range(repetitions):
            old_len = int(shape[axis])
            if plane == "min":
                origin[axis] -= old_len - 1 if drop_duplicate else old_len
            shape[axis] = 2 * old_len - 1 if drop_duplicate else 2 * old_len

    shell_cfg = config.get("02f_add_voxel_shell", {})
    if shell_cfg.get("enabled", False) and shell_cfg.get("use_shell_for_meshing", False):
        t = boundary_thicknesses(shell_cfg)
        origin -= np.array([t["x_min"], t["y_min"], t["z_min"]], dtype=float)
        shape += np.array([
            t["x_min"] + t["x_max"],
            t["y_min"] + t["y_max"],
            t["z_min"] + t["z_max"],
        ], dtype=int)

    actual = np.array(npy_shape, dtype=int)
    if not np.array_equal(shape, actual):
        print(f"⚠️ Computed transformed voxel shape {tuple(shape)} differs from meshed npy shape {tuple(actual)}; using actual shape with computed origin.")
        shape = actual
    return origin, shape

def scale_and_translate_mesh(input_path, output_path,
                             x_min_target, x_max_target,
                             y_min_target, y_max_target,
                             z_min_target, z_max_target,
                             target_center_vox_xy,
                             dx,
                             translate_to_center=True):
    mesh = meshio.read(input_path)
    points = mesh.points[:, :3].copy()

    # Compute original bounds
    x_min, x_max = points[:, 0].min(), points[:, 0].max()
    y_min, y_max = points[:, 1].min(), points[:, 1].max()
    z_min, z_max = points[:, 2].min(), points[:, 2].max()

    # Scaling factors
    scale_x = (x_max_target - x_min_target) / (x_max - x_min)
    scale_y = (y_max_target - y_min_target) / (y_max - y_min)
    scale_z = (z_max_target - z_min_target) / (z_max - z_min)

    # Scale
    points[:, 0] = (points[:, 0] - x_min) * scale_x + x_min_target
    points[:, 1] = (points[:, 1] - y_min) * scale_y + y_min_target
    points[:, 2] = (points[:, 2] - z_min) * scale_z + z_min_target

    if translate_to_center:
        # Current center after scaling
        current_center = np.array([
            (x_min_target + x_max_target) / 2,
            (y_min_target + y_max_target) / 2,
            (z_min_target + z_max_target) / 2,
        ])

        # Target center in physical units
        target_center = np.array([
            target_center_vox_xy[0] * dx,
            target_center_vox_xy[1] * dx,
            (z_min_target + z_max_target) / 2  # Z center auto
        ])

        # Translate
        translation = target_center - current_center
        points += translation

    mesh.points[:, :3] = points
    meshio.write(output_path, mesh)
    print(f"✅ Mesh written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Scale and translate a mesh based on config and metadata.")
    parser.add_argument("--config", type=str, required=True, help="Path to config.json")
    parser.add_argument("--mesh", type=str, required=True, help="Path to input/output mesh file")
    parser.add_argument("--center_x", type=float, required=True, help="Target center X (in voxel coordinates)")
    parser.add_argument("--center_y", type=float, required=True, help="Target center Y (in voxel coordinates)")
    parser.add_argument("--npy", type=str, default=None, help="Optional meshing .npy; if provided, use its shape instead of metadata subvolume shape")
    args = parser.parse_args()

    # Load config and metadata
    if not os.path.isfile(args.config):
        raise FileNotFoundError(f"❌ Config file not found: {args.config}")
    config = load_config(args.config)

    metadata_path = config.get("metadata_output_path")
    if not metadata_path or not os.path.isfile(metadata_path):
        raise FileNotFoundError(f"❌ Metadata file not found at: {metadata_path}")

    dx = load_voxel_size(metadata_path)

    translate_to_center = True
    # Load shape of the volume that was actually meshed [Nx, Ny, Nz].
    if args.npy:
        npy_shape = load_shape_from_npy(args.npy)
        origin_vox, shape = transformed_voxel_bounds(config, metadata_path, npy_shape, args.center_x, args.center_y)
        Nx, Ny, Nz = shape
        x_min_t, y_min_t, z_min_t = origin_vox * dx
        x_max_t, y_max_t, z_max_t = (origin_vox + shape) * dx
        translate_to_center = False
        print(f"📐 Using transformed voxel bounds from {args.npy}: origin_vox={tuple(origin_vox)}, shape={tuple(shape)}")
    else:
        Nx, Ny, Nz = load_subvolume_shape(metadata_path)
        x_min_t, x_max_t = 0, Nx * dx
        y_min_t, y_max_t = 0, Ny * dx
        z_min_t, z_max_t = 0, Nz * dx

    # Apply transformation
    scale_and_translate_mesh(
        input_path=args.mesh,
        output_path=args.mesh,  # overwrite in-place
        x_min_target=x_min_t,
        x_max_target=x_max_t,
        y_min_target=y_min_t,
        y_max_target=y_max_t,
        z_min_target=z_min_t,
        z_max_target=z_max_t,
        target_center_vox_xy=(args.center_x, args.center_y),
        dx=dx,
        translate_to_center=translate_to_center
    )


if __name__ == "__main__":
    main()



