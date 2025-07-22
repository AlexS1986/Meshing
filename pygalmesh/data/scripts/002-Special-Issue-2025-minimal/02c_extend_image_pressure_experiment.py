import numpy as np
import argparse
import os
import sys

def find_real_bounds(volume, direction):
    """Find min and max indices along the specified axis where volume == 0.0"""
    if direction == 'x':
        axis = 0
    elif direction == 'y':
        axis = 1
    else:
        raise ValueError("Direction must be 'x' or 'y'.")

    # Mask of where volume is 0
    mask = (volume == 0.0)
    coords = np.any(mask, axis=tuple(i for i in range(3) if i != axis))
    indices = np.where(coords)[0]

    if indices.size == 0:
        return None, None  # No material (0.0) found

    return indices.min(), indices.max()

def overwrite_edges(volume, direction, thickness):
    """Overwrite only the detected start and end slices of material with 0.0"""
    start, end = find_real_bounds(volume, direction)
    if start is None:
        print("Warning: No 0.0 regions found in volume to determine bounds.")
        return volume

    if direction == 'x':
        volume[start:start + thickness, :, :] = 0.0
        volume[end - thickness + 1:end + 1, :, :] = 0.0
    elif direction == 'y':
        volume[:, start:start + thickness, :] = 0.0
        volume[:, end - thickness + 1:end + 1, :] = 0.0
    return volume

def extend_array(volume, direction, thickness):
    """Pad the array only on ends where material was found"""
    start, end = find_real_bounds(volume, direction)
    if start is None:
        return volume  # Nothing to extend

    shape = volume.shape
    pad_before = (thickness if start - thickness >= 0 else start)
    pad_after = (thickness if end + thickness < shape[{'x': 0, 'y': 1}[direction]] else shape[{'x': 0, 'y': 1}[direction]] - end - 1)

    if direction == 'x':
        pad_width = ((pad_before, pad_after), (0, 0), (0, 0))
    elif direction == 'y':
        pad_width = ((0, 0), (pad_before, pad_after), (0, 0))
    else:
        raise ValueError("Direction must be 'x' or 'y'.")

    return np.pad(volume, pad_width=pad_width, mode='constant', constant_values=volume.dtype.type(0.0))

def count_values(array):
    ones = np.sum(array == 1)
    zeros = np.sum(array == 0)
    return ones, zeros

def main():
    script_path = os.path.dirname(__file__)

    parser = argparse.ArgumentParser(description="Extend a 3D voxel array by adding 0.0-filled cuboids at the real ends in x or y direction.")
    parser.add_argument("volume_path", nargs="?", default=os.path.join(script_path, "volume.npy"), help="Path to the volume.npy file (default: volume.npy)")
    parser.add_argument("direction", nargs="?", default="x", choices=["x", "y"], help="Direction to extend: 'x' or 'y' (default: x)")
    parser.add_argument("-t", "--thickness", type=int, default=10, help="Thickness of cuboid extensions (default: 10)")

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

    volume = overwrite_edges(volume, args.direction, args.thickness)
    extended_volume = extend_array(volume, args.direction, args.thickness)

    print(f"Extended shape: {extended_volume.shape}")
    ext_ones, ext_zeros = count_values(extended_volume)
    print(f"Extended volume - 1s: {ext_ones}, 0s: {ext_zeros}")

    np.save(args.volume_path, extended_volume)
    print(f"Volume extended in '{args.direction}' direction with thickness {args.thickness}.")
    print(f"Extended volume saved to '{args.volume_path}'.")

if __name__ == "__main__":
    main()


