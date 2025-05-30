#!/usr/bin/env python3
import os
import json
import argparse
import numpy as np

def load_config_and_metadata(config_path):
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"❌ Config not found at {config_path}")
    with open(config_path, "r") as f:
        config = json.load(f)

    subvol_config = config.get("02b_build_subvolume_arrays", {})
    xy_divisions = subvol_config.get("xy_divisions")
    subvolume_output_folder = subvol_config.get("subvolume_output_folder", "output_subvolumes")

    if xy_divisions is None:
        raise ValueError("❌ 'xy_divisions' must be specified in config under '02b_build_subvolume_arrays'")

    metadata_path = config.get("metadata_output_path", "metadata.json")
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"❌ Metadata file not found: {metadata_path}")
    with open(metadata_path, "r") as f:
        metadata = json.load(f)

    metadata_entry = metadata.get("02a_rotate_pic_to_align_with_axis.py", {})
    input_path = metadata_entry.get("input_path")
    input_folder = os.path.dirname(input_path)
    material_value = metadata_entry.get("material_value")
    material_bounds = metadata_entry.get("material_bounds")

    if not input_path or material_value is None or material_bounds is None:
        raise ValueError("❌ Missing required metadata fields: input_path, material_value, or material_bounds")

    return config, metadata, metadata_path, input_path, input_folder, xy_divisions, subvolume_output_folder, material_value, material_bounds

def subdivide_and_save_subvolumes(volume, bounds, xy_divisions, output_base, material_value):
    os.makedirs(output_base, exist_ok=True)

    x_start, x_end = bounds["x"]
    y_start, y_end = bounds["y"]
    z_start, z_end = bounds["z"]
    z_slice = slice(z_start, z_end + 1)

    x_len = x_end - x_start + 1
    y_len = y_end - y_start + 1

    x_step = x_len // xy_divisions
    y_step = y_len // xy_divisions

    saved_subvolumes = []
    count = 0

    for i in range(xy_divisions):
        for j in range(xy_divisions):
            x0 = x_start + i * x_step
            x1 = x_start + (i + 1) * x_step if i < xy_divisions - 1 else x_end + 1
            y0 = y_start + j * y_step
            y1 = y_start + (j + 1) * y_step if j < xy_divisions - 1 else y_end + 1

            subvol = volume[x0:x1, y0:y1, z_slice]
            if np.any(subvol == material_value):
                folder_name = f"subvolume_x{x0}_y{y0}"
                folder_path = os.path.join(output_base, folder_name)
                os.makedirs(folder_path, exist_ok=True)

                np.save(os.path.join(folder_path, "volume.npy"), subvol)
                print(f"💾 Saved: {folder_path}/volume.npy (shape={subvol.shape})")
                saved_subvolumes.append({
                    "x_start": x0,
                    "x_end": x1 - 1,
                    "y_start": y0,
                    "y_end": y1 - 1,
                    "z_start": z_start,
                    "z_end": z_end,
                    "shape": subvol.shape,
                    "path": os.path.relpath(folder_path, output_base)
                })
                count += 1

    print(f"✅ Total subvolumes saved: {count}")
    return saved_subvolumes

def write_metadata(metadata_path, metadata, subvolume_info, xy_divisions, output_folder, bounds):
    metadata["02b_build_subvolume_arrays.py"] = {
        "subvolume_count": len(subvolume_info),
        "xy_divisions": xy_divisions,
        "material_bounds": bounds,
        "subvolume_output_folder": output_folder,
        "subvolumes": subvolume_info
    }
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"📝 Metadata updated at: {metadata_path}")

def main():
    script_path = os.path.dirname(__file__)
    parser = argparse.ArgumentParser(description="Subdivide rotated volume into equal subvolumes across full bounds.")
    parser.add_argument("--config", type=str, default=os.path.join(script_path, "config.json"), help="Path to config.json")
    args = parser.parse_args()

    config, metadata, metadata_path, input_path, input_folder, xy_divisions, output_folder, material_value, material_bounds = load_config_and_metadata(args.config)

    print(f"📦 Loading volume from: {input_path}")
    volume = np.load(input_path)
    print(f"📏 Volume shape: {volume.shape}")
    print(f"📐 Material bounds: {material_bounds}")
    print(f"🔢 XY divisions: {xy_divisions}")
    print(f"📁 Base output folder: {output_folder}")

    subvolume_info = subdivide_and_save_subvolumes(volume, material_bounds, xy_divisions, output_folder, material_value)
    write_metadata(metadata_path, metadata, subvolume_info, xy_divisions, output_folder, material_bounds)

if __name__ == "__main__":
    main()




