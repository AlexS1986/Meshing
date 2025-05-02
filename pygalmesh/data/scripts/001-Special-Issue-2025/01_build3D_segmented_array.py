import os
import numpy as np

def load_subregion_from_slices(input_folder, min_x=None, max_x=None, min_y=None, max_y=None, min_z=None, max_z=None):
    """
    Load a 3D numpy array from a specified subregion across multiple 2D slice files.
    """
    slice_filenames = sorted([f for f in os.listdir(input_folder) if f.endswith(".npy")])
    num_total_slices = len(slice_filenames)

    if num_total_slices == 0:
        raise ValueError("No .npy slice files found in the folder.")
    
    #first_file_path = os.path.join(input_folder, npy_files[0])
    
    npy_files = sorted([f for f in os.listdir(input_folder) if f.endswith(".npy") and os.path.isfile(os.path.join(input_folder, f))])
    first_slice_path = os.path.join(input_folder, npy_files[0])
    first_slice = np.load(first_slice_path)
    
    height, width = first_slice.shape

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
    subregion_shape = (num_slices, max_y - min_y, max_x - min_x)
    volume = np.zeros(subregion_shape, dtype=np.uint8)

    for i, slice_idx in enumerate(range(min_z, max_z)):
        slice_path = os.path.join(input_folder, slice_filenames[slice_idx])
        slice_data = np.load(slice_path)
        volume[i] = slice_data[min_y:max_y, min_x:max_x]

    return volume


# Example usage
if __name__ == "__main__":
    script_path = os.path.dirname(__file__)
    specimen_name = "JM-25-26_segmented"
    input_folder = os.path.join(script_path, specimen_name)
    output_folder = os.path.join(input_folder, specimen_name + "_3D")
    os.makedirs(output_folder, exist_ok=True)

    # Optional subregion size and center selection
    desired_width_x = 400    # Set to None to use full width
    desired_height_y = 400   # Set to None to use full height
    center_x = None        # Default: center of the image width
    center_y = None        # Default: center of the image height

    # Load one slice to get shape
    # first_slice_path = os.path.join(input_folder, sorted(os.listdir(input_folder))[2])
    # first_slice = np.load(first_slice_path)
    npy_files = sorted([f for f in os.listdir(input_folder) if f.endswith(".npy") and os.path.isfile(os.path.join(input_folder, f))])
    first_slice_path = os.path.join(input_folder, npy_files[0])
    first_slice = np.load(first_slice_path)
    height, width = first_slice.shape

    center_x = center_x if center_x is not None else width // 2
    center_y = center_y if center_y is not None else height // 2

    if desired_width_x is not None:
        min_x = max(0, center_x - desired_width_x // 2)
        max_x = min(width, center_x + desired_width_x // 2)
    else:
        min_x = 0
        max_x = width

    if desired_height_y is not None:
        min_y = max(0, center_y - desired_height_y // 2)
        max_y = min(height, center_y + desired_height_y // 2)
    else:
        min_y = 0
        max_y = height

    # Depth bounds
    min_z = 500
    max_z = 900

    volume = load_subregion_from_slices(
        input_folder,
        min_x=min_x, max_x=max_x,
        min_y=min_y, max_y=max_y,
        min_z=min_z, max_z=max_z
    )

    output_path = os.path.join(output_folder, specimen_name + "_3D.npy")
    np.save(output_path, volume)
    print(f"✅ Saved volume to {output_path}")

