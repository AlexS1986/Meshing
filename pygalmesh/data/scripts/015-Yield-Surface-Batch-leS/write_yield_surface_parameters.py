#!/usr/bin/env python3
"""Write the effective parameters of one yield-surface simulation."""

import argparse
import json
from pathlib import Path


def parameter_text(config, material=None, loading_direction=None):
    ys = config.get("yield_surface", {})
    materials = [material] if material else ys.get("materials", ["std"])
    directions = [loading_direction] if loading_direction else ys.get("loading_directions", ["x"])
    material_sets = ys.get("material_sets", {})
    default_material = ys.get("default_material", {"E": 2.5, "nu": 0.25, "sig_y": 1.0, "hard": 0.01})

    lines = [
        f"sample_id = {ys.get('sample_id', 'not_set')}",
        f"sample_index = {ys.get('sample_index', 'not_set')}",
        f"sample_count = {ys.get('sample_count', 'not_set')}",
        f"sample_method = {ys.get('sample_method', 'not_set')}",
        f"sample_radius = {ys.get('sample_radius', 'not_set')}",
        f"sample_direction_unit = {ys.get('sample_direction_unit', 'not_set')}",
        f"eps_mac_eigenvalues = {ys.get('eps_mac_eigenvalues', 'not_set')}",
        f"materials = {materials}",
        f"loading_directions = {directions}",
        f"max_mean_strain = {ys.get('max_mean_strain', 0.25)}",
        f"time_step = {ys.get('time_step', 0.0001)}",
        f"total_time = {ys.get('total_time', 1.0e9)}",
        f"dt_min = {ys.get('dt_min', 1e-11)}",
        f"strain_scale_start = {ys.get('strain_scale_start', 1e-6)}",
        f"strain_scale_rate = {ys.get('strain_scale_rate', 1.0)}",
        f"yielded_volume_fraction = {ys.get('yielded_volume_fraction', 0.02)}",
        f"alpha_yield_tolerance = {ys.get('alpha_yield_tolerance', 1e-5)}",
        f"quadrature_degree = {ys.get('quadrature_degree', 1)}",
    ]
    for name in materials:
        values = material_sets.get(name.lower(), default_material)
        lines.extend([
            "",
            f"material.{name}.E = {values.get('E', 2.5)}",
            f"material.{name}.nu = {values.get('nu', 0.25)}",
            f"material.{name}.sig_y = {values.get('sig_y', 1.0)}",
            f"material.{name}.hard = {values.get('hard', 0.01)}",
        ])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--material")
    parser.add_argument("--loading-direction")
    args = parser.parse_args()
    with open(args.config) as handle:
        config = json.load(handle)
    Path(args.output).write_text(parameter_text(config, args.material, args.loading_direction))


if __name__ == "__main__":
    main()
