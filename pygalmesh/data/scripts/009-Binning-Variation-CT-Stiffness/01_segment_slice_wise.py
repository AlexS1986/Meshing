import os
import json
import numpy as np
import nanomesh
import matplotlib.pyplot as plt
import argparse
from scipy import ndimage as ndi
from skimage import filters, morphology


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


def get_threshold(image, threshold_method, multiplier=1.0, offset=0.0):
    if isinstance(threshold_method, (int, float)):
        threshold = float(threshold_method)
    else:
        method = str(threshold_method).lower()
        if method == "otsu":
            threshold = filters.threshold_otsu(image)
        elif method == "yen":
            threshold = filters.threshold_yen(image)
        elif method == "li":
            threshold = filters.threshold_li(image)
        elif method == "triangle":
            threshold = filters.threshold_triangle(image)
        elif method == "isodata":
            threshold = filters.threshold_isodata(image)
        elif method == "mean":
            threshold = filters.threshold_mean(image)
        elif method == "minimum":
            threshold = filters.threshold_minimum(image)
        else:
            # Preserve nanomesh-compatible string methods if a future version supports them.
            slice_image = nanomesh.Image(image)
            segmented = slice_image.binary_digitize(threshold=threshold_method)
            return None, np.array(segmented.image, dtype=bool)
    return threshold * multiplier + offset, None


def disk_or_none(radius):
    radius = int(radius or 0)
    return morphology.disk(radius) if radius > 0 else None


def apply_postprocess(mask, params):
    mask = np.asarray(mask, dtype=bool)

    remove_small_objects_min_size = int(params.get("remove_small_objects_min_size", 0) or 0)
    if remove_small_objects_min_size > 0:
        mask = morphology.remove_small_objects(mask, min_size=remove_small_objects_min_size)

    remove_small_holes_area_threshold = int(params.get("remove_small_holes_area_threshold", 0) or 0)
    if remove_small_holes_area_threshold > 0:
        mask = morphology.remove_small_holes(mask, area_threshold=remove_small_holes_area_threshold)

    opening_radius = disk_or_none(params.get("binary_opening_radius", 0))
    if opening_radius is not None:
        mask = morphology.binary_opening(mask, footprint=opening_radius)

    closing_radius = disk_or_none(params.get("binary_closing_radius", 0))
    if closing_radius is not None:
        mask = morphology.binary_closing(mask, footprint=closing_radius)

    return mask


def segment_slice(slice_data, params, default_threshold_method, default_sigma):
    image = np.asarray(slice_data, dtype=np.float32)

    median_size = int(params.get("median_filter_size", 0) or 0)
    if median_size > 1:
        image = ndi.median_filter(image, size=median_size)

    gaussian_sigma = params.get("gaussian_sigma_pixels", None)
    if gaussian_sigma is None:
        gaussian_sigma = default_sigma
    gaussian_sigma = float(gaussian_sigma or 0.0)
    if gaussian_sigma > 0.0:
        image = ndi.gaussian_filter(image, sigma=gaussian_sigma)

    threshold_method = params.get("seg_algorithm", default_threshold_method)
    threshold_multiplier = float(params.get("threshold_multiplier", 1.0))
    threshold_offset = float(params.get("threshold_offset", 0.0))
    threshold, presegmented = get_threshold(image, threshold_method, threshold_multiplier, threshold_offset)
    if presegmented is None:
        # Keep the old convention: after invert_contrast(), material is 1.
        mask = image <= threshold
    else:
        mask = ~presegmented

    if bool(params.get("invert_contrast", True)) is False:
        mask = ~mask

    mask = apply_postprocess(mask, params)
    return np.asarray(mask, dtype=np.uint8)


def segment_slice_with_nanomesh(slice_data, threshold_method, sigma):
    params = {
        "seg_algorithm": threshold_method,
        "gaussian_sigma_pixels": sigma,
        "invert_contrast": True,
    }
    return segment_slice(slice_data, params, threshold_method, sigma)


def save_metadata(metadata_output_path, algorithm_name, sigma_factor, actual_sigma, params):
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
        "computed_gaussian_sigma": actual_sigma,
        "parameters": params,
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
    parser = argparse.ArgumentParser(description="Segment slices using configurable filtering and thresholding.")
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to the configuration JSON file. Defaults to 'config.json'."
    )
    args = parser.parse_args()

    script_path = os.path.dirname(__file__)
    config_path = args.config if os.path.isabs(args.config) else os.path.join(script_path, args.config)

    config, metadata_output_path = load_config(config_path)
    original_voxel_size = load_original_voxel_size(metadata_output_path)

    input_folder = config["input_folder"]
    output_folder = config["output_folder"]
    preview_slice_index = config.get("preview_slice_index", -1)
    seg_algorithm = config["seg_algorithm"]
    gaussian_filter_sigma_factor = config.get("gaussian_filter_sigma_factor", 1.0)

    # Backward-compatible default. For pixel-scale smoothing, set gaussian_sigma_pixels explicitly.
    configured_sigma = config.get("gaussian_sigma_pixels", None)
    actual_sigma = float(gaussian_filter_sigma_factor * original_voxel_size if configured_sigma is None else configured_sigma)

    visualization_folder = os.path.join(script_path, "visualizations")
    os.makedirs(visualization_folder, exist_ok=True)
    os.makedirs(output_folder, exist_ok=True)

    save_metadata(metadata_output_path, algorithm_name=seg_algorithm,
                  sigma_factor=gaussian_filter_sigma_factor, actual_sigma=actual_sigma, params=config)

    print("📥 Processing slices individually to save memory...")
    print(f"📐 Segmentation parameters: {json.dumps(config, sort_keys=True)}")
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
        preview_segmented_slice = segment_slice(
            preview_slice_data, config, default_threshold_method=seg_algorithm, default_sigma=actual_sigma
        )
        preview_visualization_path = os.path.join(output_folder, f"preview_slice_{preview_slice_index:04d}.png")
        visualize_slice(preview_segmented_slice, preview_visualization_path)
        del preview_slice_data, preview_segmented_slice

    save_visualizations = bool(config.get("save_visualizations", False))
    for i, filename in enumerate(slice_filenames):
        slice_path = os.path.join(input_folder, filename)
        slice_data = np.load(slice_path)
        segmented_slice = segment_slice(
            slice_data, config, default_threshold_method=seg_algorithm, default_sigma=actual_sigma
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
