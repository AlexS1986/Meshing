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


def scale_and_translate_mesh(input_path, output_path,
                             x_min_target, x_max_target,
                             y_min_target, y_max_target,
                             z_min_target, z_max_target,
                             target_center_vox_xy,
                             dx):
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
    args = parser.parse_args()

    # Load config and metadata
    if not os.path.isfile(args.config):
        raise FileNotFoundError(f"❌ Config file not found: {args.config}")
    config = load_config(args.config)

    metadata_path = config.get("metadata_output_path")
    if not metadata_path or not os.path.isfile(metadata_path):
        raise FileNotFoundError(f"❌ Metadata file not found at: {metadata_path}")

    dx = load_voxel_size(metadata_path)

    # Load shape of subvolumes [Nx, Ny, Nz]
    Nx, Ny, Nz = load_subvolume_shape(metadata_path)

    # Target physical space bounding box
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
        dx=dx
    )


if __name__ == "__main__":
    main()



