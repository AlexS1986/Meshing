import numpy as np
import argparse
import os
import sys

def find_real_bounds(volume, direction, threshold=0.01):
    """
    Find the first and last indices along the specified axis where at least
    `threshold` fraction of voxels in a slice are material (value == 0.0).
    """
    axis = {'x': 0, 'y': 1, 'z': 2}[direction]
    slices = np.moveaxis(volume, axis, 0)  # Bring target axis to front

    material_ratio = np.mean(slices == 0.0, axis=(1, 2))
    valid_indices = np.where(material_ratio >= threshold)[0]

    if valid_indices.size == 0:
        return None, None

    return valid_indices.min(), valid_indices.max()

def get_all_real_bounds(volume, threshold=0.01):
    """Return real bounds in all directions as a dict: {'x': (start, end), ...}"""
    bounds = {}
    for d in ['x', 'y', 'z']:
        bounds[d] = find_real_bounds(volume, d, threshold)
    return bounds

def overwrite_edges(volume, direction, thickness, threshold):
    """Overwrite real start and end slices of material with 0.0, only within bounds in other dims"""
    bounds = get_all_real_bounds(volume, threshold)
    start, end = bounds[direction]
    if start is None:
        print("Warning: No slice met the threshold. Skipping overwrite.")
        return volume

    x_start, x_end = bounds['x']
    y_start, y_end = bounds['y']
    z_start, z_end = bounds['z']

    if direction == 'x':
        volume[start:start + thickness, y_start:y_end + 1, z_start:z_end + 1] = 0.0
        volume[end - thickness + 1:end + 1, y_start:y_end + 1, z_start:z_end + 1] = 0.0
    elif direction == 'y':
        volume[x_start:x_end + 1, start:start + thickness, z_start:z_end + 1] = 0.0
        volume[x_start:x_end + 1, end - thickness + 1:end + 1, z_start:z_end + 1] = 0.0
    elif direction == 'z':
        volume[x_start:x_end + 1, y_start:y_end + 1, start:start + thickness] = 0.0
        volume[x_start:x_end + 1, y_start:y_end + 1, end - thickness + 1:end + 1] = 0.0
    return volume

def extend_array(volume, direction, thickness, threshold):
    """Pad the array only at real material ends and only within the real bounds of other dims"""
    bounds = get_all_real_bounds(volume, threshold)
    start, end = bounds[direction]
    if start is None:
        print("Warning: No slice met the threshold. Skipping padding.")
        return volume

    shape = volume.shape
    dim = {'x': 0, 'y': 1, 'z': 2}[direction]
    size = shape[dim]

    pad_before = thickness if start >= thickness else start
    pad_after = thickness if (size - end - 1) >= thickness else (size - end - 1)

    if direction == 'x':
        pad_width = ((pad_before, pad_after), (0, 0), (0, 0))
    elif direction == 'y':
        pad_width = ((0, 0), (pad_before, pad_after), (0, 0))
    elif direction == 'z':
        pad_width = ((0, 0), (0, 0), (pad_before, pad_after))
    else:
        raise ValueError("Direction must be 'x', 'y', or 'z'.")

    padded = np.pad(volume, pad_width=pad_width, mode='constant', constant_values=volume.dtype.type(0.0))
    return padded

def crop_to_real_bounds(volume, direction_to_exclude, threshold=0.01):
    """Crop the volume to real material bounds, excluding the given direction."""
    bounds = get_all_real_bounds(volume, threshold)
    slices = [slice(None)] * 3  # full slices by default
    for d, axis in zip(['x', 'y', 'z'], [0, 1, 2]):
        if d != direction_to_exclude:
            start, end = bounds[d]
            if start is not None and end is not None:
                slices[axis] = slice(start, end + 1)
    return volume[tuple(slices)]

def count_values(array):
    ones = np.sum(array == 1)
    zeros = np.sum(array == 0)
    return ones, zeros

def get_non_overwritten_shape(bounds, direction, thickness):
    """Return the shape (x, y, z) of the region inside the real bounds, excluding overwritten thickness."""
    shape = {}
    for d in ['x', 'y', 'z']:
        start, end = bounds[d]
        if start is None or end is None:
            shape[d] = 0
            continue
        if d == direction:
            length = max(0, (end - start + 1) - 2 * thickness)
        else:
            length = end - start + 1
        shape[d] = length
    return (shape['x'], shape['y'], shape['z'])

def main():
    script_path = os.path.dirname(__file__)

    parser = argparse.ArgumentParser(description="Extend a 3D voxel array by adding 0.0-filled cuboids at the real material ends in x, y, or z direction.")
    parser.add_argument("volume_path", nargs="?", default=os.path.join(script_path, "volume.npy"),
                        help="Path to the volume.npy file (default: volume.npy)")
    parser.add_argument("direction", nargs="?", default="x", choices=["x", "y", "z"],
                        help="Direction to extend: 'x', 'y', or 'z' (default: x)")
    parser.add_argument("-t", "--thickness", type=int, default=10,
                        help="Thickness of cuboid extensions (default: 10)")
    parser.add_argument("--threshold", type=float, default=0.01,
                        help="Minimum fraction of material per slice to count as filled (default: 0.01)")

    args = parser.parse_args()

    if not os.path.isfile(args.volume_path):
        print(f"Error: File '{args.volume_path}' not found.", file=sys.stderr)
        sys.exit(1)

    if args.thickness < 1:
        print("Error: Thickness must be at least 1.", file=sys.stderr)
        sys.exit(1)

    volume = np.load(args.volume_path)
    if volume.ndim != 3:
        print("Error: Input array must be 3D.", file=sys.stderr)
        sys.exit(1)

    print(f"Original shape: {volume.shape}")
    ones, zeros = count_values(volume)
    print(f"Original volume - 1s: {ones}, 0s: {zeros}")

    volume = overwrite_edges(volume, args.direction, args.thickness, args.threshold)
    extended_volume = extend_array(volume, args.direction, args.thickness, args.threshold)

    print(f"Extended shape: {extended_volume.shape}")
    ext_ones, ext_zeros = count_values(extended_volume)
    print(f"Extended volume - 1s: {ext_ones}, 0s: {ext_zeros}")

    cropped_volume = crop_to_real_bounds(extended_volume, args.direction, args.threshold)
    print(f"Cropped shape (lateral bounds only): {cropped_volume.shape}")
    final_ones, final_zeros = count_values(cropped_volume)
    print(f"Final volume - 1s: {final_ones}, 0s: {final_zeros}")

    # Compute and print real dimensions excluding overwritten edges
    real_bounds = get_all_real_bounds(volume, args.threshold)
    non_overwritten_shape = get_non_overwritten_shape(real_bounds, args.direction, args.thickness)
    print(f"Non-overwritten real bounds shape (x, y, z): {non_overwritten_shape}")

    np.save(args.volume_path, cropped_volume)
    print(f"Volume extended in '{args.direction}' direction with thickness {args.thickness}, then cropped laterally.")
    print(f"Final volume saved to '{args.volume_path}'.")

if __name__ == "__main__":
    main()



