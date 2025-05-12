import os
import json
import argparse
import numpy as np

def load_config(config_path):
    with open(config_path, "r") as f:
        config = json.load(f)
    return config["02_segmented_3D_array"], config["metadata_output_path"]

def load_subregion_from_slices(input_folder, min_x=None, max_x=None, min_y=None, max_y=None, min_z=None, max_z=None):
    slice_filenames = sorted([f for f in os.listdir(input_folder) if f.endswith(".npy")])
    num_total_slices = len(slice_filenames)

    if num_total_slices == 0:
        raise ValueError("No .npy slice files found in the folder.")

    first_slice = np.load(os.path.join(input_folder, slice_filenames[0]))
    width, height = first_slice.shape

    min_x = 0 if min_x is None else min_x
    max_x = width if max_x is None else max_x
    min_y = 0 if min_y is None else min_y
    max_y = height if max_y is None else max_y
    min_z = 0 if min_z is None else min_z
    max_z = num_total_slices if max_z is None else max_z

    if max_x > width or max_y > height:
        raise ValueError(f"max_x or max_y exceed slice dimensions ({width}, {height})")
    if max_z > num_total_slices:
        raise ValueError(f"max_z ({max_z}) exceeds number of slices ({num_total_slices})")

    num_slices = max_z - min_z
    subregion_shape = (max_x - min_x, max_y - min_y, num_slices)
    volume = np.zeros(subregion_shape, dtype=np.uint8)

    for i, slice_idx in enumerate(range(min_z, max_z)):
        slice_data = np.load(os.path.join(input_folder, slice_filenames[slice_idx]))
        volume[:, :, i] = slice_data[min_x:max_x, min_y:max_y]

    return volume, {
        "min_x": min_x, "max_x": max_x,
        "min_y": min_y, "max_y": max_y,
        "min_z": min_z, "max_z": max_z,
        "output_shape": list(volume.shape)
    }

def main():
    script_path = os.path.dirname(__file__)
    default_config_path = os.path.join(script_path, "config_JM-25-26.json")

    parser = argparse.ArgumentParser(description="Extract a 3D subregion from segmented slices.")
    parser.add_argument(
        "--config",
        type=str,
        default=default_config_path,
        help=f"Path to configuration JSON file (default: {default_config_path})"
    )
    args = parser.parse_args()

    config_path = args.config
    cfg, metadata_output_path = load_config(config_path)

    input_folder = cfg["input_folder"]
    output_folder = cfg["output_folder"]
    os.makedirs(output_folder, exist_ok=True)

    desired_width = cfg.get("desired_width")
    desired_height = cfg.get("desired_height")
    center_x = cfg.get("center_x")
    center_y = cfg.get("center_y")
    min_z = cfg.get("min_z")
    max_z = cfg.get("max_z")

    npy_files = sorted([f for f in os.listdir(input_folder) if f.endswith(".npy")])
    first_slice = np.load(os.path.join(input_folder, npy_files[0]))
    width, height = first_slice.shape

    center_x = width // 2 if center_x is None else center_x
    center_y = height // 2 if center_y is None else center_y

    if desired_width is not None:
        min_x = max(0, center_x - desired_width // 2)
        max_x = min(width, center_x + desired_width // 2)
    else:
        min_x = 0
        max_x = width

    if desired_height is not None:
        min_y = max(0, center_y - desired_height // 2)
        max_y = min(height, center_y + desired_height // 2)
    else:
        min_y = 0
        max_y = height

    volume, subregion_metadata = load_subregion_from_slices(
        input_folder, min_x, max_x, min_y, max_y, min_z, max_z
    )

    volume_output_path = os.path.join(output_folder, "segmented_3D_volume.npy")
    np.save(volume_output_path, volume)
    print(f"✅ Saved volume to {volume_output_path}")

    if not os.path.exists(metadata_output_path):
        raise FileNotFoundError(f"❌ Metadata file not found at: {metadata_output_path}")

    with open(metadata_output_path, "r") as f:
        metadata = json.load(f)

    metadata["02_segmented_3D_array"] = subregion_metadata

    with open(metadata_output_path, "w") as f:
        json.dump(metadata, f, indent=4)
    print(f"📝 Saved subregion metadata to {metadata_output_path}")

if __name__ == "__main__":
    main()





