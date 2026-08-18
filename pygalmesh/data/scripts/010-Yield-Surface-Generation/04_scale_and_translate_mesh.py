import os
import json
import meshio
import numpy as np
import argparse

def load_config(config_path):
    with open(config_path, "r") as file:
        config = json.load(file)
    return config

def load_voxel_size(metadata_path):
    with open(metadata_path, "r") as file:
        metadata = json.load(file)
    return float(metadata["00_dicom2npy"]["SliceThickness"])

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
    parser = argparse.ArgumentParser(description="Scale and translate mesh using config/metadata.")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config.json. Defaults to 'config.json' in the same folder as the script."
    )
    args = parser.parse_args()

    script_dir = os.path.dirname(__file__)
    config_path = args.config or os.path.join(script_dir, "config.json")

    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"❌ Config file not found at: {config_path}")

    # Load config and metadata
    config = load_config(config_path)
    metadata_path = config["metadata_output_path"]

    if not os.path.isfile(metadata_path):
        raise FileNotFoundError(f"❌ Metadata file not found at: {metadata_path}")

    dx = load_voxel_size(metadata_path)

    # Read transformation settings
    seg3d_cfg = config["02_segmented_3D_array"]
    mesh_cfg = config["03_mesh_3D_array"]

    Nx = seg3d_cfg["desired_width_x"]
    Ny = seg3d_cfg["desired_width_y"]
    Nz = seg3d_cfg["max_z"] - seg3d_cfg["min_z"]

    x_min_t, x_max_t = 0, Nx * dx
    y_min_t, y_max_t = 0, Ny * dx
    z_min_t, z_max_t = 0, Nz * dx

    center_x = seg3d_cfg["center_x"]
    center_y = seg3d_cfg["center_y"]
    target_center_vox_xy = (center_x, center_y)

    input_mesh_path = mesh_cfg["mesh_output_path"]
    output_mesh_path = input_mesh_path #os.path.join(os.path.dirname(input_mesh_path), "scaled_translated_mesh.xdmf")

    # Transform mesh
    scale_and_translate_mesh(
        input_mesh_path,
        output_mesh_path,
        x_min_t, x_max_t,
        y_min_t, y_max_t,
        z_min_t, z_max_t,
        target_center_vox_xy,
        dx
    )

if __name__ == "__main__":
    main()



