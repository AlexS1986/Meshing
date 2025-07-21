import numpy as np
import argparse
import os
import sys

def overwrite_edges(volume, direction, thickness):
    # Overwrite values at both ends of the specified axis with 0.0
    if direction == 'x':
        volume[:thickness, :, :] = 0.0  # Start of axis 0
        volume[-thickness:, :, :] = 0.0  # End of axis 0
    elif direction == 'y':
        volume[:, :thickness, :] = 0.0  # Start of axis 1
        volume[:, -thickness:, :] = 0.0  # End of axis 1
    else:
        raise ValueError("Direction must be 'x' or 'y'.")
    return volume

def extend_array(volume, direction, thickness):
    dtype = volume.dtype

    # Adjust padding direction: x = first axis, y = second axis
    if direction == 'x':
        pad_width = ((thickness, thickness), (0, 0), (0, 0))  # Pad along the first axis
    elif direction == 'y':
        pad_width = ((0, 0), (thickness, thickness), (0, 0))  # Pad along the second axis
    else:
        raise ValueError("Direction must be 'x' or 'y'.")

    # Fill the extended areas with 0.0 (instead of 1.0)
    extended = np.pad(volume, pad_width=pad_width, mode='constant', constant_values=dtype.type(0.0))
    return extended

def count_values(array):
    # Count number of 1s and 0s in the array
    ones = np.sum(array == 1)
    zeros = np.sum(array == 0)
    return ones, zeros

def main():
    script_path = os.path.dirname(__file__)
    
    parser = argparse.ArgumentParser(description="Extend a 3D voxel array by adding 0.0-filled cuboids at both ends in x or y direction.")
    parser.add_argument("volume_path", nargs="?", default=os.path.join(script_path, "volume.npy"), help="Path to the volume.npy file (default: volume.npy)")
    parser.add_argument("direction", nargs="?", default="x", choices=["x", "y"], help="Direction to extend: 'x' or 'y' (default: x)")
    parser.add_argument("-t", "--thickness", type=int, default=10, help="Thickness of cuboid extensions (default: 10)")

    args = parser.parse_args()

    # Check that the volume file exists
    if not os.path.isfile(args.volume_path):
        print(f"Error: File '{args.volume_path}' not found.", file=sys.stderr)
        sys.exit(1)

    # Validate thickness
    if args.thickness < 1:
        print("Error: Thickness must be at least 1.", file=sys.stderr)
        sys.exit(1)

    # Load volume
    volume = np.load(args.volume_path)
    if volume.ndim != 3:
        print("Error: Input array must be 3D.", file=sys.stderr)
        sys.exit(1)

    # Print original info
    print(f"Original shape: {volume.shape}")
    ones, zeros = count_values(volume)
    print(f"Original volume - 1s: {ones}, 0s: {zeros}")

    # Overwrite interior start and end slices
    volume = overwrite_edges(volume, args.direction, args.thickness)

    # Extend volume
    extended_volume = extend_array(volume, args.direction, args.thickness)

    # Print extended info
    print(f"Extended shape: {extended_volume.shape}")
    ext_ones, ext_zeros = count_values(extended_volume)
    print(f"Extended volume - 1s: {ext_ones}, 0s: {ext_zeros}")

    # Save to file
    #output_path = os.path.join(script_path, "volume.npy")
    output_path = args.volume_path
    np.save(output_path, extended_volume)
    print(f"Volume extended in '{args.direction}' direction with thickness {args.thickness}.")
    print(f"Extended volume saved to '{output_path}'.")

if __name__ == "__main__":
    main()


