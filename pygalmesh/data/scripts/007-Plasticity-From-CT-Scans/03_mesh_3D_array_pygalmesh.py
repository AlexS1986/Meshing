#!/usr/bin/env python3
import os
import json
import argparse
import numpy as np
import matplotlib.pyplot as plt
import nanomesh
from datetime import datetime
from skimage.transform import rescale
import pygalmesh


def load_config(config_path):
    with open(config_path, "r") as file:
        config = json.load(file)
    return config["03_mesh_3D_array"], config["metadata_output_path"]


def load_original_voxel_size(metadata_path):
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"❌ Metadata file not found at: {metadata_path}")
    with open(metadata_path, "r") as f:
        metadata = json.load(f)
    return float(metadata["00_dicom2npy"]["SliceThickness"])


def plot_image_of_slice_in_subvol(script_path, subvol, z_coordinate_of_slice, filename):
    plane = subvol.select_plane(x=z_coordinate_of_slice)
    plane_array = np.array(plane.image).astype(np.float32)

    fig, ax = plt.subplots()
    ax.imshow(plane_array, cmap='gray')
    ax.axis('off')

    output_path = os.path.join(script_path, filename)
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"✅ Saved image to {output_path}")


def main():
    script_path = os.path.dirname(__file__)
    default_config_path = os.path.join(script_path, "config.json")

    parser = argparse.ArgumentParser(description="Generate a 3D mesh from segmented volume slices.")
    parser.add_argument("--config", type=str, default=default_config_path, help="Path to configuration JSON file")
    parser.add_argument("--npy", type=str, default=os.path.join(script_path,"volume.npy"), help="Path to the input .npy volume file (overrides config)")
    parser.add_argument("--mesh", type=str, default=os.path.join(script_path,"mesh.xdmf"), help="Path to save the output mesh file (overrides config)")
    args = parser.parse_args()

    config_path = args.config
    config, metadata_output_path = load_config(config_path)

    specimen_name = config["specimen_name"]
    x_range = tuple(config.get("x_range", [0, 0]))  # updated after load if needed
    smoothing_sigma = config["smoothing_sigma_factor"]
    segmentation_algorithm = config["segmentation_algorithm"]
    z_slice = config["z_slice"]
    scale_factor = config["scale_factor"]
    meshing_method = config.get("meshing_method", "pygalmesh").lower()

    # Use provided npy file or fallback to config
    if args.npy:
        input_path = args.npy
    else:
        input_folder = config["input_folder"]
        input_path = os.path.join(input_folder, "segmented_3D_volume.npy")

    # Use provided mesh path or fallback to config
    mesh_output_path = args.mesh if args.mesh else os.path.join(config["mesh_output_path"])

    original_voxel_size = load_original_voxel_size(metadata_output_path)

    print(f"📦 Loading volume from: {input_path}")
    intensity_at_voxels = np.load(input_path)
    vol = nanomesh.Image(intensity_at_voxels)

    if x_range == (0, 0):
        x_range = (0, vol.image.shape[0])

    plot_image_of_slice_in_subvol(script_path, vol, 0, "vol_output_plane.png")

    # Process and segment
    subvol = vol.select_subvolume(xs=x_range)
    plot_image_of_slice_in_subvol(script_path, subvol, z_slice, "subvol_output_plane.png")

    subvol_gauss = subvol.apply(rescale, scale=scale_factor).gaussian(sigma=smoothing_sigma * original_voxel_size)
    subvol_seg = subvol_gauss.binary_digitize(threshold=segmentation_algorithm).invert_contrast()
    plot_image_of_slice_in_subvol(script_path, subvol_seg, z_slice, "subvol_seg_output_plane.png")

    voxel_dim = original_voxel_size / scale_factor
    voxel_size = (voxel_dim, voxel_dim, voxel_dim)

    mesh_metadata = {
        "specimen_name": specimen_name,
        "input_volume_shape": vol.image.shape,
        "subvolume_bounds": {"x_range": list(x_range)},
        "smoothing_sigma": smoothing_sigma,
        "threshold_method": segmentation_algorithm,
        "scale_factor": scale_factor,
        "voxel_size": voxel_size,
        "voxel_dim": voxel_dim,
        "mesh_output_path": mesh_output_path,
        "meshing_method": meshing_method,
        "timestamp": datetime.now().isoformat()
    }

    os.makedirs(os.path.dirname(mesh_output_path), exist_ok=True)

    if meshing_method == "pygalmesh":
        params = config.get("pygalmesh_parameters", {})
        max_element_size_factor = params.get("max_element_size_factor", 1.0)
        max_facet_distance_factor = params.get("max_facet_distance_factor", 0.1)

        vol_pygal = np.array(subvol_seg.image, dtype=np.uint8)
        mesh = pygalmesh.generate_from_array(
            vol_pygal,
            voxel_size,
            max_cell_circumradius=max_element_size_factor * voxel_dim,
            max_facet_distance=max_facet_distance_factor * voxel_dim
        )
        mesh.write(mesh_output_path)

        mesh_metadata["pygalmesh_parameters"] = {
            "max_element_size_factor": max_element_size_factor,
            "max_facet_distance_factor": max_facet_distance_factor,
            "max_cell_circumradius": max_element_size_factor * voxel_dim,
            "max_facet_distance": max_facet_distance_factor * voxel_dim
        }

    elif meshing_method == "nanomesh":
        params = config.get("nanomesh_parameters", {})
        meshing_options = params.get("meshing_options", "-pq")
        output_format = params.get("output_format", "gmsh22")
        output_binary = params.get("output_binary", False)

        mesher = nanomesh.Mesher(subvol_seg)
        mesher.generate_contour()
        mesh = mesher.tetrahedralize(opts=meshing_options)
        mesh.write(mesh_output_path, file_format=output_format, binary=output_binary)

        mesh_metadata["nanomesh_parameters"] = {
            "meshing_options": meshing_options,
            "output_format": output_format,
            "output_binary": output_binary
        }

    else:
        raise ValueError(f"Unsupported meshing method: {meshing_method}")

    # Update metadata
    if not os.path.exists(metadata_output_path):
        raise FileNotFoundError(f"❌ Metadata file not found at: {metadata_output_path}")

    with open(metadata_output_path, "r") as f:
        existing_metadata = json.load(f)

    existing_metadata["03_mesh_3D_array"] = mesh_metadata

    with open(metadata_output_path, "w") as f:
        json.dump(existing_metadata, f, indent=4)

    print(f"✅ Mesh and metadata appended to {metadata_output_path}")


if __name__ == "__main__":
    main()


