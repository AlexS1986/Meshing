import os
import json
import argparse
import numpy as np
import pydicom
import matplotlib.pyplot as plt
from pydicom.fileset import FileSet

# --- Helper Functions --- #

def read_dicom_folder(dicom_folder):
    dicomdir_path = os.path.join(dicom_folder, "DICOMDIR")
    dicomdir = pydicom.dcmread(dicomdir_path)
    return FileSet(dicomdir)

def crop_image(scan_array, x_start, x_end, y_start, y_end):
    return scan_array[y_start:y_end, x_start:x_end]

def reduce_grid(image, N):
    if image.shape[0] % N != 0 or image.shape[1] % N != 0:
        raise ValueError("Image dimensions must be divisible by N.")
    return image.reshape(image.shape[0] // N, N, image.shape[1] // N, N).mean(axis=(1, 3))

def reduce_3d_chunk(chunk, factor):
    """Reduce a 3D chunk of shape (N, H, W) by averaging over N×N×N cubes."""
    if any(dim % factor != 0 for dim in chunk.shape[1:]):
        raise ValueError("Image dimensions must be divisible by the reduction factor.")
    return chunk.reshape(
        factor, chunk.shape[1] // factor, factor, chunk.shape[2] // factor, factor
    ).mean(axis=(0, 2, 4))

def plot_image(image, output_path):
    plt.imsave(output_path, image, cmap='gray')

def save_array_and_image(image_array, slice_index, output_folder):
    base_name = f"slice_{slice_index:03d}"
    np.save(os.path.join(output_folder, f"{base_name}.npy"), image_array)
    plot_image(image_array, os.path.join(output_folder, f"{base_name}.png"))

def save_metadata(data, metadata_output_path, num_slices, option, reduce_factor=None):
    slice_thickness = float(data.SliceThickness)
    pixel_spacing = [float(ps) for ps in data.PixelSpacing]

    if option == "reduce" and reduce_factor:
        slice_thickness *= reduce_factor
        pixel_spacing = [ps * reduce_factor for ps in pixel_spacing]

    metadata = {
        "00_dicom2npy": {
            "Option": option,
            "ReductionFactor": reduce_factor if reduce_factor else None,
            "SliceThickness": slice_thickness,
            "PixelSpacing": pixel_spacing,
            "ImageDimensions": [int(data.Rows), int(data.Columns)],
            "NumberOfSlices": num_slices
        }
    }
    os.makedirs(os.path.dirname(metadata_output_path), exist_ok=True)
    with open(metadata_output_path, "w") as f:
        json.dump(metadata, f, indent=4)
    print(f"📝 Saved metadata to {metadata_output_path}")

# --- Main Processing Function --- #

def main():
    # --- Argument parser for config path --- #
    default_config_path = os.path.join(os.path.dirname(__file__), "config_JM-25-26.json")
    parser = argparse.ArgumentParser(description="Process DICOM slices into .npy files.")
    parser.add_argument("--config", type=str, default=default_config_path, help="Path to configuration JSON")
    args = parser.parse_args()

    # --- Load config --- #
    with open(args.config, "r") as f:
        full_config = json.load(f)
        config = full_config["dicom2npy"]
        metadata_output_path = full_config.get(
            "metadata_output_path",
            os.path.join(config.get("output_folder", "."), "metadata.json")
        )

    foldername = config["foldername"]
    option = config.get("option", "full").lower()
    slice_start = config.get("slice_start", 0)
    slice_end = config.get("slice_end", None)
    output_folder = config.get("output_folder", os.path.join(os.path.dirname(__file__), "output"))

    crop_params = config.get("crop", {}) if option == "crop" else None
    reduce_factor = config.get("reduce", {}).get("factor", 2) if option == "reduce" else None

    # --- Setup paths --- #
    dicom_folder = foldername
    os.makedirs(output_folder, exist_ok=True)

    # --- Load DICOMDIR --- #
    fs = read_dicom_folder(dicom_folder)
    num_slices = len(fs)

    metadata_saved = False

    if option == "reduce":
        chunk_buffer = []
        z_counter = 0
        for slice_index, instance in enumerate(fs):
            if (slice_start is not None and slice_index < slice_start) or \
               (slice_end is not None and slice_index >= slice_end):
                continue

            print(f"📄 Reading slice {slice_index:03d}: {instance.path}")
            data = pydicom.dcmread(instance.path)

            if not metadata_saved:
                save_metadata(data, metadata_output_path, num_slices, option, reduce_factor)
                metadata_saved = True

            scan_array = np.array(data.pixel_array, dtype=np.uint16)
            chunk_buffer.append(scan_array)

            if len(chunk_buffer) == reduce_factor:
                chunk_array = np.stack(chunk_buffer, axis=0)
                reduced_slice = reduce_3d_chunk(chunk_array, reduce_factor)
                save_array_and_image(reduced_slice, z_counter, output_folder)
                print(f"✅ Saved reduced slice {z_counter:03d}")
                z_counter += 1
                chunk_buffer.clear()

        if chunk_buffer:
            print("⚠️ Remaining slices ignored due to incomplete reduction block.")

    else:
        for slice_index, instance in enumerate(fs):
            if (slice_start is not None and slice_index < slice_start) or \
               (slice_end is not None and slice_index >= slice_end):
                continue

            print(f"📄 Processing slice {slice_index:03d}: {instance.path}")
            data = pydicom.dcmread(instance.path)

            if not metadata_saved:
                save_metadata(data, metadata_output_path, num_slices, option)
                metadata_saved = True

            scan_array = np.array(data.pixel_array, dtype=np.uint16)

            if option == "crop":
                processed_image = crop_image(
                    scan_array,
                    crop_params["x_start"],
                    crop_params["x_end"],
                    crop_params["y_start"],
                    crop_params["y_end"]
                )
            elif option == "full":
                processed_image = scan_array
            else:
                raise ValueError(f"Unsupported option: {option}")

            print(f"   Slice Thickness: {data.SliceThickness}")
            print(f"   Pixel Spacing: {data.PixelSpacing}")
            print(f"   Slice Location: {getattr(data, 'SliceLocation', 'N/A')}")
            print(f"   Max Intensity: {np.max(processed_image)}")

            save_array_and_image(processed_image, slice_index, output_folder)

    print("🏁 Finished processing all slices.")

# --- Entry Point --- #
if __name__ == "__main__":
    main()






