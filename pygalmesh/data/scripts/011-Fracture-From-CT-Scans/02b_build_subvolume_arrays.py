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


def reduce_factor_value(value):
    return 1 if value in (None, "", "null") else float(value)


def axis_key(axis, side):
    return f"{axis}_{side}"


def scale_reference_value(value, config, crop_cfg, rounding="round"):
    if value is None:
        return None

    binning_cfg = config.get("binning", {})
    reference_cfg = binning_cfg.get("region_reference", {})
    reference_binning = float(crop_cfg.get("reference_binning_id", reference_cfg.get("binning_id", 1)))
    reference_reduce = reduce_factor_value(crop_cfg.get("reference_reduce_factor", reference_cfg.get("reduce_factor", 1)))
    current_binning = float(binning_cfg.get("id", reference_binning))
    current_reduce = reduce_factor_value(binning_cfg.get("script_reduce_factor", 1))
    scaled = float(value) * reference_binning * reference_reduce / (current_binning * current_reduce)

    if rounding == "floor":
        return int(np.floor(scaled))
    if rounding == "ceil":
        return int(np.ceil(scaled))
    return int(np.rint(scaled))


def clamp_bounds(bounds, volume_shape):
    clamped = {}
    for axis_index, axis in enumerate(("x", "y", "z")):
        lo, hi = bounds[axis]
        lo = max(0, min(int(lo), volume_shape[axis_index] - 1))
        hi = max(0, min(int(hi), volume_shape[axis_index] - 1))
        if lo > hi:
            raise ValueError(
                f"❌ Invalid crop bounds for {axis}: min={lo}, max={hi}, "
                f"volume size={volume_shape[axis_index]}"
            )
        clamped[axis] = [lo, hi]
    return clamped


def resolve_crop_bounds(config, material_bounds, volume_shape):
    subvol_config = config.get("02b_build_subvolume_arrays", {})
    source = "material_bounds"
    details = {}
    bounds = {axis: list(material_bounds[axis]) for axis in ("x", "y", "z")}

    bounds_cfg = subvol_config.get("crop_bounds_reference", {})
    if bounds_cfg.get("enabled", False):
        source = "crop_bounds_reference"
        for axis in ("x", "y", "z"):
            lo_value = bounds_cfg.get(axis_key(axis, "min"))
            hi_value = bounds_cfg.get(axis_key(axis, "max"))
            if lo_value is None or hi_value is None:
                raise ValueError(
                    f"❌ crop_bounds_reference is enabled, but {axis}_min/{axis}_max is not fully specified"
                )
            bounds[axis] = [
                scale_reference_value(lo_value, config, bounds_cfg, rounding="floor"),
                scale_reference_value(hi_value, config, bounds_cfg, rounding="ceil"),
            ]
        details = {"config": bounds_cfg}
    else:
        offset_cfg = subvol_config.get("crop_offsets_reference", {})
        if offset_cfg.get("enabled", False):
            source = "crop_offsets_reference"
            for axis in ("x", "y", "z"):
                lower_offset = scale_reference_value(offset_cfg.get(axis_key(axis, "min"), 0), config, offset_cfg)
                upper_offset = scale_reference_value(offset_cfg.get(axis_key(axis, "max"), 0), config, offset_cfg)
                bounds[axis] = [
                    int(material_bounds[axis][0]) + lower_offset,
                    int(material_bounds[axis][1]) - upper_offset,
                ]
            details = {"config": offset_cfg}

    clamped = clamp_bounds(bounds, volume_shape)
    return clamped, {
        "source": source,
        "original_material_bounds": material_bounds,
        "requested_bounds_before_clamp": bounds,
        "resolved_bounds": clamped,
        **details,
    }


def inclusive_bounds_volume(bounds):
    return int(np.prod([int(bounds[axis][1]) - int(bounds[axis][0]) + 1 for axis in ("x", "y", "z")]))


def add_crop_volume_info(crop_info, material_bounds, crop_bounds, volume_shape):
    total_volume = int(np.prod(volume_shape))
    material_box_volume = inclusive_bounds_volume(material_bounds)
    crop_box_volume = inclusive_bounds_volume(crop_bounds)

    crop_info.update({
        "full_volume_voxels": total_volume,
        "material_bounds_volume_voxels": material_box_volume,
        "crop_volume_voxels": crop_box_volume,
        "cropped_from_full_volume_voxels": max(total_volume - crop_box_volume, 0),
        "cropped_from_material_bounds_voxels": max(material_box_volume - crop_box_volume, 0),
        "cropped_from_full_volume_percent": 100.0 * max(total_volume - crop_box_volume, 0) / total_volume if total_volume else 0.0,
        "cropped_from_material_bounds_percent": 100.0 * max(material_box_volume - crop_box_volume, 0) / material_box_volume if material_box_volume else 0.0,
        "retained_full_volume_percent": 100.0 * crop_box_volume / total_volume if total_volume else 0.0,
        "retained_material_bounds_percent": 100.0 * crop_box_volume / material_box_volume if material_box_volume else 0.0,
    })
    return crop_info

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
                
                total_elements = subvol.size
                material_count = np.count_nonzero(subvol == material_value)
                pore_count = total_elements - material_count
                relative_density = material_count / total_elements
                porosity = pore_count / total_elements

                print(f"💾 Saved: {folder_path}/volume.npy (shape={subvol.shape}, rel_density={relative_density:.4f}, porosity={porosity:.4f})")
                
                saved_subvolumes.append({
                    "x_start": x0,
                    "x_end": x1 - 1,
                    "y_start": y0,
                    "y_end": y1 - 1,
                    "z_start": z_start,
                    "z_end": z_end,
                    "shape": subvol.shape,
                    "path": os.path.relpath(folder_path, output_base),
                    "relative_density": relative_density,
                    "porosity": porosity
                })
                count += 1

    print(f"✅ Total subvolumes saved: {count}")
    return saved_subvolumes


def write_metadata(metadata_path, metadata, subvolume_info, xy_divisions, output_folder, bounds, crop_info):
    metadata["02b_build_subvolume_arrays.py"] = {
        "subvolume_count": len(subvolume_info),
        "xy_divisions": xy_divisions,
        "material_bounds": bounds,
        "crop": crop_info,
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
    crop_bounds, crop_info = resolve_crop_bounds(config, material_bounds, volume.shape)
    crop_info = add_crop_volume_info(crop_info, material_bounds, crop_bounds, volume.shape)

    print(f"📐 Material bounds: {material_bounds}")
    print(f"✂️ Crop source: {crop_info['source']}")
    print(f"✂️ Crop bounds: {crop_bounds}")
    print(f"✂️ Cropped from full volume: {crop_info['cropped_from_full_volume_percent']:.2f}%")
    print(f"✂️ Cropped from material-bounds box: {crop_info['cropped_from_material_bounds_percent']:.2f}%")
    print(f"🔢 XY divisions: {xy_divisions}")
    print(f"📁 Base output folder: {output_folder}")

    subvolume_info = subdivide_and_save_subvolumes(volume, crop_bounds, xy_divisions, output_folder, material_value)
    write_metadata(metadata_path, metadata, subvolume_info, xy_divisions, output_folder, crop_bounds, crop_info)

if __name__ == "__main__":
    main()



