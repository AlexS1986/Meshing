#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path


def iter_summary_files(search_root):
    yield from search_root.glob('00_results/**/yield_run_*.json')
    yield from search_root.glob('yield_surface_runs/**/yield_run_*.json')


def row_from_summary(path):
    with path.open() as handle:
        data = json.load(handle)
    final_state = data.get('final_yield_state') or {}
    eps = final_state.get('eps_mac_eigenvalues_current') or [None, None, None]
    target = data.get('eps_mac_eigenvalues_target') or [None, None, None]
    return {
        'summary_file': str(path),
        'material': data.get('material'),
        'loading_direction': data.get('loading_direction'),
        'stop_reason': data.get('stop_reason'),
        'eps_1': eps[0],
        'eps_2': eps[1],
        'eps_3': eps[2],
        'target_eps_1': target[0],
        'target_eps_2': target[1],
        'target_eps_3': target[2],
        'strain_scale': final_state.get('strain_scale'),
        'alpha_avg_reduced_material_volume': final_state.get('alpha_avg_reduced_material_volume'),
        'alpha_avg_reduced_volume': final_state.get('alpha_avg_reduced_volume'),
        'yielded_fraction_reduced_material_volume': final_state.get('yielded_fraction_reduced_material_volume'),
        'yielded_fraction_reduced_volume': final_state.get('yielded_fraction_reduced_volume'),
        'sig_vm_avg_reduced_volume': final_state.get('sig_vm_avg_reduced_volume'),
        'reaction_force_x': (final_state.get('reaction_force') or [None, None, None])[0],
        'reaction_force_y': (final_state.get('reaction_force') or [None, None, None])[1],
        'reaction_force_z': (final_state.get('reaction_force') or [None, None, None])[2],
    }


def main():
    parser = argparse.ArgumentParser(description='Collect final yield-surface points into a CSV.')
    parser.add_argument('--project-dir', default=Path(__file__).resolve().parent)
    parser.add_argument('--output', default=None)
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    output = Path(args.output) if args.output else project_dir / '00_results' / 'yield_surface_points.csv'
    output.parent.mkdir(parents=True, exist_ok=True)

    seen = set()
    rows = []
    for path in sorted(iter_summary_files(project_dir)):
        if path in seen:
            continue
        seen.add(path)
        row = row_from_summary(path)
        if row['eps_1'] is not None:
            rows.append(row)

    fieldnames = [
        'summary_file', 'material', 'loading_direction', 'stop_reason',
        'eps_1', 'eps_2', 'eps_3',
        'target_eps_1', 'target_eps_2', 'target_eps_3', 'strain_scale',
        'alpha_avg_reduced_material_volume', 'alpha_avg_reduced_volume',
        'yielded_fraction_reduced_material_volume', 'yielded_fraction_reduced_volume',
        'sig_vm_avg_reduced_volume', 'reaction_force_x', 'reaction_force_y', 'reaction_force_z',
    ]
    with output.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f'Wrote {len(rows)} yield-surface points to {output}')


if __name__ == '__main__':
    main()
