import os
import json
import numpy as np
import nanomesh
import matplotlib.pyplot as plt
import argparse

def load_config(config_path):
    with open(config_path, "r") as file:
        config = json.load(file)
    return config["01_segment_slice_wise"], config["metadata_output_path"]

def load_original_voxel_size(metadata_path):
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"❌ Metadata file not found at: {metadata_path}")
    with open(metadata_path, "r") as f:
        metadata = json.load(f)
    return float(metadata["00_dicom2npy"]["SliceThickness"])

def segment_slice_with_nanomesh(slice_data, threshold_method, sigma):
    slice_image = nanomesh.Image(slice_data)
    smoothed_slice = slice_image.gaussian(sigma=sigma)
    segmented_slice = smoothed_slice.binary_digitize(threshold=threshold_method)
    segmented_slice = segmented_slice.invert_contrast()
    return np.array(segmented_slice.image, dtype=np.uint8)

def save_metadata(metadata_output_path, algorithm_name, sigma_factor, actual_sigma):
    os.makedirs(os.path.dirname(metadata_output_path), exist_ok=True)

    if os.path.exists(metadata_output_path):
        with open(metadata_output_path, "r") as f:
            try:
                all_metadata = json.load(f)
            except json.JSONDecodeError:
                all_metadata = {}
    else:
        all_metadata = {}

    all_metadata["01_segment_slice_wise"] = {
        "algorithm": algorithm_name,
        "gaussian_sigma_factor": sigma_factor,
        "computed_gaussian_sigma": actual_sigma
    }

    with open(metadata_output_path, "w") as f:
        json.dump(all_metadata, f, indent=4)

    print(f"📝 Saved/updated metadata to {metadata_output_path}")

def visualize_slice(slice_data, output_path):
    plt.imshow(slice_data, cmap='gray')
    plt.axis('off')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"🖼️ Saved slice visualization to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Segment slices using nanomesh.")
    parser.add_argument(
        "--config",
        type=str,
        default="config_JM-25-26.json",
        help="Path to the configuration JSON file. Defaults to 'config_JM-25-26.json'."
    )
    args = parser.parse_args()

    script_path = os.path.dirname(__file__)
    config_path = args.config if os.path.isabs(args.config) else os.path.join(script_path, args.config)

    config, metadata_output_path = load_config(config_path)
    original_voxel_size = load_original_voxel_size(metadata_output_path)

    specimen_name = config["specimen_name"]
    input_folder = config["input_folder"]
    output_folder = config["output_folder"]
    preview_slice_index = config.get("preview_slice_index", -1)
    seg_algorithm = config["seg_algorithm"]
    gaussian_filter_sigma_factor = config["gaussian_filter_sigma_factor"]

    # Compute effective sigma using voxel size
    actual_sigma = gaussian_filter_sigma_factor * original_voxel_size

    visualization_folder = os.path.join(script_path, "visualizations")
    os.makedirs(visualization_folder, exist_ok=True)
    os.makedirs(output_folder, exist_ok=True)

    save_metadata(metadata_output_path, algorithm_name=seg_algorithm,
                  sigma_factor=gaussian_filter_sigma_factor, actual_sigma=actual_sigma)

    print("📥 Processing slices individually to save memory...")
    slice_filenames = sorted([f for f in os.listdir(input_folder) if f.endswith(".npy")])

    if not slice_filenames:
        print("❌ No .npy slice files found in the folder!")
        return

    first_slice_data = np.load(os.path.join(input_folder, slice_filenames[0]))
    height, width = first_slice_data.shape
    depth = len(slice_filenames)

    if 0 <= preview_slice_index < depth:
        preview_slice_path = os.path.join(input_folder, slice_filenames[preview_slice_index])
        preview_slice_data = np.load(preview_slice_path)
        preview_segmented_slice = segment_slice_with_nanomesh(
            preview_slice_data, threshold_method=seg_algorithm, sigma=actual_sigma
        )
        preview_visualization_path = os.path.join(script_path, f"preview_slice_{preview_slice_index:04d}.png")
        visualize_slice(preview_segmented_slice, preview_visualization_path)
        del preview_slice_data, preview_segmented_slice

    save_visualizations = False
    for i, filename in enumerate(slice_filenames):
        slice_path = os.path.join(input_folder, filename)
        slice_data = np.load(slice_path)
        segmented_slice = segment_slice_with_nanomesh(
            slice_data, threshold_method=seg_algorithm, sigma=actual_sigma
        )

        segmented_slice_path = os.path.join(output_folder, f"segmented_slice_{i:04d}.npy")
        np.save(segmented_slice_path, segmented_slice)
        print(f"✅ Saved segmented slice {i} to {segmented_slice_path}")

        if save_visualizations:
            visualization_path = os.path.join(visualization_folder, f"slice_{i:04d}.png")
            visualize_slice(segmented_slice, visualization_path)

        del slice_data, segmented_slice

    print("🎉 All slices processed and saved individually!")

if __name__ == "__main__":
    main()











