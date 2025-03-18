import os
import numpy as np
import nanomesh
import matplotlib.pyplot as plt
import json

seg_algorithm = 'otsu'
gaussian_filter_sigma = 1

def segment_slice_with_nanomesh(slice_data, sigma=1):
    """Perform segmentation on a single slice using nanomesh."""
    # Convert slice to nanomesh Image object
    slice_image = nanomesh.Image(slice_data)

    # Apply Gaussian smoothing
    smoothed_slice = slice_image.gaussian(sigma=gaussian_filter_sigma)

    # Perform binary segmentation using 'otsu' threshold method
    segmented_slice = smoothed_slice.binary_digitize(threshold=seg_algorithm)
    segmented_slice = segmented_slice.invert_contrast()

    return np.array(segmented_slice.image, dtype=np.uint8)


def save_metadata(output_folder, algorithm_name, sigma):
    """Save segmentation metadata to a file."""
    metadata = {
        "algorithm": algorithm_name,
        "gaussian_sigma": sigma
    }
    metadata_path = os.path.join(output_folder, "segmentation_metadata.json")
    with open(metadata_path, "w") as meta_file:
        json.dump(metadata, meta_file, indent=4)
    print(f"📝 Saved metadata to {metadata_path}")


def visualize_slice(slice_data, output_path):
    """Save a visualization of a single slice."""
    plt.imshow(slice_data, cmap='gray')
    plt.axis('off')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"🖼️ Saved slice visualization to {output_path}")


def main():
    # --- Paths ---
    script_path = os.path.dirname(__file__)
    specimen_name = "JM-25-02"
    input_folder = os.path.join("/data", "resources", "special_issue_hannover", specimen_name)
    output_folder = os.path.join(script_path, specimen_name + "_segmented")
    visualization_folder = os.path.join(script_path, "visualizations")
    os.makedirs(visualization_folder, exist_ok=True)

    # Visualization flag (set to True to save visualizations for each slice)
    save_visualizations = False

    # Option to preview a specific slice (set to the index of the slice you want to preview)
    preview_slice_index = 600  # For example, preview slice number 600 (change as needed)

    # Ensure output folder exists
    os.makedirs(output_folder, exist_ok=True)

    # Save segmentation metadata
    save_metadata(output_folder, algorithm_name=seg_algorithm, sigma=gaussian_filter_sigma)

    # --- Process slices one by one ---
    print("📥 Processing slices individually to save memory...")

    slice_filenames = sorted([f for f in os.listdir(input_folder) if f.endswith(".npy")])

    if not slice_filenames:
        print("❌ No .npy slice files found in the folder!")
        return

    # Determine the dimensions of the 3D volume (based on the first slice)
    first_slice_path = os.path.join(input_folder, slice_filenames[0])
    first_slice_data = np.load(first_slice_path)
    height, width = first_slice_data.shape
    depth = len(slice_filenames)

    # Preview the specified slice if requested
    if 0 <= preview_slice_index < depth:
        preview_slice_path = os.path.join(input_folder, slice_filenames[preview_slice_index])
        preview_slice_data = np.load(preview_slice_path)
        preview_segmented_slice = segment_slice_with_nanomesh(preview_slice_data)

        # Save a preview visualization of the selected slice
        preview_visualization_path = os.path.join(script_path, f"preview_slice_{preview_slice_index:04d}.png")
        visualize_slice(preview_segmented_slice, preview_visualization_path)

        # Release memory for the preview slice
        del preview_slice_data, preview_segmented_slice

    # Process and save each slice
    for i, filename in enumerate(slice_filenames):
        slice_path = os.path.join(input_folder, filename)

        # Load and segment the current slice
        slice_data = np.load(slice_path)
        segmented_slice = segment_slice_with_nanomesh(slice_data)

        # Save the segmented slice as a .npy file
        segmented_slice_path = os.path.join(output_folder, f"segmented_slice_{i:04d}.npy")
        np.save(segmented_slice_path, segmented_slice)
        print(f"✅ Saved segmented slice {i} to {segmented_slice_path}")

        # Save a visualization of each slice if the flag is set
        if save_visualizations:
            visualization_path = os.path.join(visualization_folder, f"slice_{i:04d}.png")
            visualize_slice(segmented_slice, visualization_path)

        # Release memory for the current slice
        del slice_data, segmented_slice

    print("🎉 All slices processed and saved individually!")


if __name__ == "__main__":
    main()







