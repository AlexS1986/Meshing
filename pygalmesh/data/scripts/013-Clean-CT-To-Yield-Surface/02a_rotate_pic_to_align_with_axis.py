import os
import json
import argparse
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from scipy.ndimage import rotate

# === Utility Functions ===

def load_config(config_path, fallback_path):
    if not os.path.exists(config_path):
        print(f"⚠️ Config not found at {config_path}, using fallback: {fallback_path}")
        config_path = fallback_path

    with open(config_path, "r") as f:
        config = json.load(f)

    base_config = config.get("02a_rotate_pic_to_align_with_axis", {})
    mesh_config = config.get("03_mesh_3D_array", {})

    input_folder = mesh_config.get("input_folder", ".")
    input_filename = "segmented_3D_volume.npy"
    input_path = os.path.join(input_folder, input_filename)

    metadata_output_path = config.get("metadata_output_path", "metadata.json")

    material_value = base_config.get("material_value", 1)
    pore_value = base_config.get("pore_value", 0)
    buffer_width = base_config.get("buffer_width", 15)

    def get_buffer(key, fallback):
        return base_config.get(key, fallback)

    buffer_widths = {
        "min_x": get_buffer("buffer_width_min_x", 5 * buffer_width),
        "max_x": get_buffer("buffer_width_max_x", buffer_width),
        "min_y": get_buffer("buffer_width_min_y", buffer_width),
        "max_y": get_buffer("buffer_width_max_y", buffer_width),
        "min_z": get_buffer("buffer_width_min_z", buffer_width),
        "max_z": get_buffer("buffer_width_max_z", buffer_width),
    }

    angles = tuple(base_config.get("angles", [-12.9, 4, 2.5]))

    return input_path, input_folder, metadata_output_path, material_value, pore_value, buffer_widths, angles

def plot_slices(volume, prefix, output_folder):
    x_mid = volume.shape[0] // 2
    y_mid = volume.shape[1] // 2
    z_mid = volume.shape[2] // 2

    save_slice(volume[:, :, z_mid], f"{prefix}_xy.png", output_folder)
    save_slice(volume[:, y_mid, :], f"{prefix}_xz.png", output_folder)
    save_slice(volume[x_mid, :, :], f"{prefix}_yz.png", output_folder)

def save_slice(slice_2d, filename, output_folder):
    print(f"🖼 Saving {filename} with shape {slice_2d.shape}")
    fig, ax = plt.subplots()
    ax.imshow(slice_2d.T, cmap='gray', origin='lower')
    ax.axis('off')
    output_path = os.path.join(output_folder, filename)
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"✅ Saved image to {output_path}")

def clear_boundary_artifacts(volume, replace_value=0,
                              min_x=0, max_x=0, min_y=0, max_y=0, min_z=0, max_z=0):
    x, y, z = volume.shape
    if min_x > 0: volume[:min_x, :, :] = replace_value
    if max_x > 0: volume[-max_x:, :, :] = replace_value
    if min_y > 0: volume[:, :min_y, :] = replace_value
    if max_y > 0: volume[:, -max_y:, :] = replace_value
    if min_z > 0: volume[:, :, :min_z] = replace_value
    if max_z > 0: volume[:, :, -max_z:] = replace_value
    return volume

def print_material_bounds(volume, material_value):
    coords = np.argwhere(volume == material_value)
    if coords.size == 0:
        print("⚠️ No material voxels found in the volume.")
        return None
    x_min, y_min, z_min = coords.min(axis=0)
    x_max, y_max, z_max = coords.max(axis=0)
    print(f"📦 Material bounds:")
    print(f"  x: {x_min} to {x_max}")
    print(f"  y: {y_min} to {y_max}")
    print(f"  z: {z_min} to {z_max}")
    return {
        "x": [int(x_min), int(x_max)],
        "y": [int(y_min), int(y_max)],
        "z": [int(z_min), int(z_max)],
    }

def save_metadata(metadata_path, data):
    if os.path.exists(metadata_path):
        with open(metadata_path, "r") as f:
            existing_metadata = json.load(f)
    else:
        existing_metadata = {}

    existing_metadata["02a_rotate_pic_to_align_with_axis.py"] = data

    with open(metadata_path, "w") as f:
        json.dump(existing_metadata, f, indent=4)

    print(f"✅ Metadata saved to {metadata_path}")

# === Main ===

def main():
    script_path = os.path.dirname(__file__)
    default_config_path = os.path.join(script_path, "config.json")

    parser = argparse.ArgumentParser(description="Rotate segmented 3D volume based on config.json")
    parser.add_argument("--config", type=str, default=default_config_path, help="Path to config.json")
    args = parser.parse_args()

    input_path, input_folder, metadata_output_path, material_value, pore_value, buffer_widths, angles = load_config(args.config, default_config_path)

    volume = np.load(input_path)
    print(f"📏 Loaded volume from: {input_path}")
    print(f"📏 Original volume shape: {volume.shape}")

    volume = (volume == material_value).astype(float)

    plot_slices(volume, "before_rotation", input_folder)

    rotated = rotate(volume, angle=angles[0], axes=(1, 0), reshape=False,
                     order=0, prefilter=False, cval=material_value)
    rotated = rotate(rotated, angle=angles[1], axes=(2, 0), reshape=False,
                     order=0, prefilter=False, cval=material_value)
    rotated = rotate(rotated, angle=angles[2], axes=(2, 1), reshape=False,
                     order=0, prefilter=False, cval=material_value)

    rotated = np.where(rotated > 0.5, material_value, pore_value).astype(np.uint8)

    rotated = clear_boundary_artifacts(
        rotated,
        replace_value=material_value,
        min_x=buffer_widths["min_x"],
        max_x=buffer_widths["max_x"],
        min_y=buffer_widths["min_y"],
        max_y=buffer_widths["max_y"],
        min_z=buffer_widths["min_z"],
        max_z=buffer_widths["max_z"]
    )

    print(f"📏 Rotated volume shape: {rotated.shape}")
    plot_slices(rotated, "after_rotation", input_folder)
    material_bounds = print_material_bounds(rotated, pore_value)

    np.save(input_path, rotated)
    print(f"✅ Rotated volume saved to: {input_path}")

    metadata = {
        "timestamp": datetime.now().isoformat(),
        "input_path": input_path,
        "angles_deg": angles,
        "buffer_widths": buffer_widths,
        "material_value": material_value,
        "pore_value": pore_value,
        "final_shape": rotated.shape,
    }
    if material_bounds is not None:
        metadata["material_bounds"] = material_bounds

    save_metadata(metadata_output_path, metadata)

if __name__ == "__main__":
    main()


