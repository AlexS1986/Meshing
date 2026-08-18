import numpy as np
from scipy.ndimage import rotate
import os
import matplotlib.pyplot as plt

# === Configuration ===
material_value = 1  # Voxel value representing material
pore_value = 0      # Voxel value representing pore/void

# Global default buffer width
buffer_width = 15

# Individual buffer widths (fallback to `buffer_width` if not set)
buffer_width_min_x = 5*buffer_width
buffer_width_max_x = buffer_width
buffer_width_min_y = buffer_width
buffer_width_max_y = buffer_width
buffer_width_min_z = buffer_width
buffer_width_max_z = buffer_width

# === File Paths ===
script_path = os.path.dirname(__file__)
input_path = os.path.join(script_path, "segmented_3D_volume.npy")
output_path = os.path.join(script_path, "segmented_3D_volume.npy")

def plot_slices(volume, prefix, script_path):
    x_mid = volume.shape[0] // 2
    y_mid = volume.shape[1] // 2
    z_mid = volume.shape[2] // 2

    save_slice(volume[:, :, z_mid], f"{prefix}_xy.png", script_path)
    save_slice(volume[:, y_mid, :], f"{prefix}_xz.png", script_path)
    save_slice(volume[x_mid, :, :], f"{prefix}_yz.png", script_path)

def save_slice(slice_2d, filename, script_path):
    print(f"🖼 Saving {filename} with shape {slice_2d.shape}")
    fig, ax = plt.subplots()
    ax.imshow(slice_2d.T, cmap='gray', origin='lower')
    ax.axis('off')
    output_path = os.path.join(script_path, filename)
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"✅ Saved image to {output_path}")

def clear_boundary_artifacts(volume, replace_value=0,
                              min_x=0, max_x=0, min_y=0, max_y=0, min_z=0, max_z=0):
    """Sets voxels within specified boundary widths to pore_value."""
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
        return
    x_min, y_min, z_min = coords.min(axis=0)
    x_max, y_max, z_max = coords.max(axis=0)
    print(f"📦 Material bounds:")
    print(f"  x: {x_min} to {x_max}")
    print(f"  y: {y_min} to {y_max}")
    print(f"  z: {z_min} to {z_max}")

# === Load Volume ===
volume = np.load(input_path)
print(f"📏 Original volume shape: {volume.shape}")

# === Prepare Volume (binary mask) ===
volume = (volume == material_value).astype(float)

# === Plot original middle slices in 3 planes ===
plot_slices(volume, "before_rotation", script_path)

# === Rotation Angles (Z, Y, X) ===
angles = (-12.9, 4, 2.5)

# === Apply Rotations ===
rotated = rotate(volume, angle=angles[0], axes=(1, 0), reshape=False,
                 order=0, prefilter=False, cval=material_value)
rotated = rotate(rotated, angle=angles[1], axes=(2, 0), reshape=False,
                 order=0, prefilter=False, cval=material_value)
rotated = rotate(rotated, angle=angles[2], axes=(2, 1), reshape=False,
                 order=0, prefilter=False, cval=material_value)

# === Re-binarize and Cast to Material Values ===
rotated = np.where(rotated > 0.5, material_value, pore_value).astype(np.uint8)

# === Clean up artifacts near boundaries with per-side offsets ===
rotated = clear_boundary_artifacts(
    rotated,
    replace_value=material_value,
    min_x=buffer_width_min_x,
    max_x=buffer_width_max_x,
    min_y=buffer_width_min_y,
    max_y=buffer_width_max_y,
    min_z=buffer_width_min_z,
    max_z=buffer_width_max_z
)

# === Print new shape after rotation ===
print(f"📏 Rotated volume shape: {rotated.shape}")

# === Plot rotated middle slices in 3 planes ===
plot_slices(rotated, "after_rotation", script_path)

# === Print material bounds ===
print_material_bounds(rotated, material_value)

# === Save Rotated Volume ===
np.save(output_path, rotated)
print(f"✅ Rotated volume saved to: {output_path}")