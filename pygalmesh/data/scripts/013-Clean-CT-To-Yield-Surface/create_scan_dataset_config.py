#!/usr/bin/env python3
"""Create a dataset-specific 010 config from an existing, validated config."""

import argparse
import copy
import json
import os
import re
from pathlib import Path


PROJECT_CONTAINER_DIR = "/data/scripts/013-Clean-CT-To-Yield-Surface"


def container_resource_path(value):
    """Return the resource path as seen through the cluster /data bind."""
    path = str(value).rstrip("/")
    if path == "/data" or path.startswith("/data/"):
        return path

    scratch = os.environ.get("HPC_SCRATCH") or os.environ.get("HPC_Scratch")
    if scratch:
        data_root = str(Path(scratch) / "pygalmesh" / "data")
        if path == data_root or path.startswith(data_root + "/"):
            return "/data" + path[len(data_root) :]

    marker = "/pygalmesh/data/"
    if marker in path:
        return "/data/" + path.split(marker, 1)[1]

    raise ValueError(
        "The resource folder must be /data/... or a host path below "
        "$HPC_SCRATCH/pygalmesh/data."
    )


def parse_json_value(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def set_dotted(config, assignment):
    if "=" not in assignment:
        raise ValueError(f"Invalid --set value {assignment!r}; expected dotted.path=JSON_VALUE")
    dotted_key, raw_value = assignment.split("=", 1)
    keys = [key for key in dotted_key.split(".") if key]
    if not keys:
        raise ValueError(f"Invalid --set path in {assignment!r}")

    target = config
    for key in keys[:-1]:
        child = target.setdefault(key, {})
        if not isinstance(child, dict):
            raise ValueError(f"Cannot descend into non-object config key {key!r}")
        target = child
    target[keys[-1]] = parse_json_value(raw_value)


def scale_integer(value, factor):
    if value is None:
        return None
    return max(0, int(round(float(value) * factor)))


def build_config(base, args):
    config = copy.deepcopy(base)
    resource_folder = container_resource_path(args.resource_folder)
    dataset_id = args.dataset_id
    run_name = dataset_id
    output_base = f"{PROJECT_CONTAINER_DIR}/{run_name}_segmented"
    npy_output = f"{PROJECT_CONTAINER_DIR}/{run_name}/npy"
    volume_output = f"{output_base}/{run_name}_segmented_3D"

    old_effective_binning = float(config.get("binning", {}).get("effective_binning_factor", args.binning))
    reduce_factor = args.reduce_factor
    effective_binning = args.binning * (reduce_factor or 1)
    buffer_scale = old_effective_binning / effective_binning

    config["dataset"] = {
        "id": dataset_id,
        "resource_folder": resource_folder,
    }
    config["metadata_output_path"] = f"{output_base}/metadata.json"
    config["binning"] = {
        "id": args.binning,
        "label": args.binning_label or f"Bin{args.binning}",
        "resource_folder": resource_folder,
        "script_reduce_factor": reduce_factor,
        "effective_binning_factor": effective_binning,
        "region_reference": {
            "binning_id": args.binning,
            "reduce_factor": reduce_factor or 1,
            "min_z": args.min_z,
            "max_z": args.max_z,
        },
    }

    dicom = config.setdefault("dicom2npy", {})
    dicom.update(
        {
            "foldername": resource_folder,
            "option": "reduce" if reduce_factor else "full",
            "slice_start": 0,
            "slice_end": None,
            "output_folder": npy_output,
        }
    )
    dicom.setdefault("crop", {"x_start": None, "x_end": None, "y_start": None, "y_end": None})
    dicom["reduce"] = {"factor": reduce_factor}

    segmentation = config.setdefault("01_segment_slice_wise", {})
    segmentation.update(
        {
            "specimen_name": run_name,
            "input_folder": npy_output,
            "output_folder": output_base,
        }
    )

    volume = config.setdefault("02_segmented_3D_array", {})
    volume.update(
        {
            "input_folder": output_base,
            "output_folder": volume_output,
            "min_z": args.min_z,
            "max_z": args.max_z,
        }
    )

    mesh = config.setdefault("03_mesh_3D_array", {})
    mesh.update(
        {
            "specimen_name": f"{run_name}_segmented",
            "input_folder": volume_output,
            "mesh_output_path": f"{output_base}/mesh.xdmf",
        }
    )
    config.setdefault("02b_build_subvolume_arrays", {})["subvolume_output_folder"] = volume_output

    if not args.keep_buffer_voxels and buffer_scale != 1.0:
        rotation = config.setdefault("02a_rotate_pic_to_align_with_axis", {})
        for key in (
            "buffer_width",
            "buffer_width_min_x",
            "buffer_width_max_x",
            "buffer_width_min_y",
            "buffer_width_max_y",
            "buffer_width_min_z",
            "buffer_width_max_z",
        ):
            if key in rotation:
                rotation[key] = scale_integer(rotation[key], buffer_scale)

    for assignment in args.set_values:
        set_dotted(config, assignment)
    return config


def dataset_id(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise argparse.ArgumentTypeError(
            "dataset id may contain only letters, digits, underscore, dash, and dot"
        )
    return value


def main():
    parser = argparse.ArgumentParser(
        description="Create a separate 010 config for another cluster scan dataset."
    )
    parser.add_argument("--base-config", default="config-Bin4-reduce-2.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--dataset-id", required=True, type=dataset_id)
    parser.add_argument(
        "--resource-folder",
        required=True,
        help=(
            "Either /data/resources/... (container path) or "
            "$HPC_SCRATCH/pygalmesh/data/resources/... (host path)."
        ),
    )
    parser.add_argument("--binning", type=int, default=4)
    parser.add_argument("--binning-label", default=None)
    parser.add_argument(
        "--reduce-factor",
        type=int,
        default=None,
        help="Additional 3-D reduction applied by 00_dicom_2_npy.py; omit for none.",
    )
    parser.add_argument("--min-z", type=int, required=True)
    parser.add_argument("--max-z", type=int, required=True)
    parser.add_argument(
        "--keep-buffer-voxels",
        action="store_true",
        help="Do not scale inherited buffer widths to the new effective binning.",
    )
    parser.add_argument(
        "--set",
        dest="set_values",
        action="append",
        default=[],
        metavar="PATH=VALUE",
        help="Override any config value; VALUE is parsed as JSON when possible. Repeatable.",
    )
    args = parser.parse_args()

    if args.binning <= 0:
        parser.error("--binning must be positive")
    if args.reduce_factor is not None and args.reduce_factor <= 1:
        parser.error("--reduce-factor must be greater than 1; omit it for no extra reduction")
    if args.min_z < 0 or args.max_z <= args.min_z:
        parser.error("require 0 <= --min-z < --max-z")

    script_dir = Path(__file__).resolve().parent
    base_path = Path(args.base_config)
    if not base_path.is_absolute():
        base_path = script_dir / base_path
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = script_dir / output_path

    with base_path.open() as handle:
        base = json.load(handle)
    config = build_config(base, args)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")

    print(f"Wrote dataset config: {output_path}")
    print(f"Container resource: {config['dataset']['resource_folder']}")
    print(
        "Selected post-conversion layers: "
        f"[{config['02_segmented_3D_array']['min_z']}, "
        f"{config['02_segmented_3D_array']['max_z']})"
    )


if __name__ == "__main__":
    main()
