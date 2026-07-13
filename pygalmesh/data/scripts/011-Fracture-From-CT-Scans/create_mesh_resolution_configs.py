#!/usr/bin/env python3
"""Create isolated coarse/medium/fine configs for the CT mesh-only jobs."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


RESOLUTIONS = {
    "coarse": (1.0, 0.3),
    "medium": (0.75, 0.2),
    "fine": (0.5, 0.1),
}


def replace_strings(value: Any, old: str, new: str) -> Any:
    if isinstance(value, dict):
        return {key: replace_strings(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_strings(item, old, new) for item in value]
    if isinstance(value, str):
        return value.replace(old, new)
    return value


def set_meshing_parameters(
    config: dict[str, Any], element_size: float, facet_distance: float
) -> None:
    mesh_config = config["03_mesh_3D_array"]
    parameter_sets = [
        mesh_config["pygalmesh_parameters"],
        mesh_config["sdf_pygalmesh_parameters"]["pygalmesh_parameters"],
    ]
    for parameters in parameter_sets:
        parameters["max_element_size_factor"] = element_size
        parameters["max_facet_distance_factor"] = facet_distance


def parse_arguments() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-config",
        type=Path,
        default=script_dir / "config-Bin4-reduce-2-cluster-fine.json",
    )
    parser.add_argument("--output-dir", type=Path, default=script_dir)
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    with args.base_config.open() as handle:
        base_config = json.load(handle)

    old_case_name = base_config["03_mesh_3D_array"]["specimen_name"]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for resolution, (element_size, facet_distance) in RESOLUTIONS.items():
        case_name = f"JM-25-74_Bin4_reduce-2_segmented_mesh_{resolution}"
        config = replace_strings(copy.deepcopy(base_config), old_case_name, case_name)
        set_meshing_parameters(config, element_size, facet_distance)
        config["mesh_resolution"] = {
            "name": resolution,
            "max_element_size_factor": element_size,
            "max_facet_distance_factor": facet_distance,
        }

        output_path = args.output_dir / f"config-Bin4-reduce-2-mesh-{resolution}.json"
        with output_path.open("w") as handle:
            json.dump(config, handle, indent=2)
            handle.write("\n")
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
