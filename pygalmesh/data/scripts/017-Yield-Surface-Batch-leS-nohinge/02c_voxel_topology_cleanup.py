#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi


DEFAULT_CONFIG = {
    "enabled": False,
    "material_value": 1,
    "output_filename": "volume_topology_cleaned.npy",
    "report_filename": "volume_topology.txt",
    "use_cleaned_for_meshing": False,
    "connectivity": {
        "material": 6,
        "pore": 6,
    },
    "cleanup": {
        "enabled": False,
        "keep_largest_material_component": False,
        "min_material_component_voxels": 0,
        "fill_pore_cavities_max_voxels": 0,
        "binary_opening_iterations": 0,
        "binary_closing_iterations": 0,
    },
}


def deep_update(base, update):
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = value
    return base


def load_config(config_path):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if not config_path:
        return cfg
    with open(config_path, "r") as handle:
        full_config = json.load(handle)
    return deep_update(cfg, full_config.get("02c_voxel_topology_cleanup", {}))


def structure_for_connectivity(connectivity):
    if connectivity == 6:
        return ndi.generate_binary_structure(3, 1)
    if connectivity == 18:
        return ndi.generate_binary_structure(3, 2)
    if connectivity == 26:
        return ndi.generate_binary_structure(3, 3)
    raise ValueError(f"Unsupported 3D connectivity: {connectivity}; expected 6, 18, or 26")


def component_stats(mask, connectivity):
    labels, count = ndi.label(mask, structure=structure_for_connectivity(connectivity))
    if count == 0:
        sizes = np.array([], dtype=np.int64)
    else:
        sizes = np.bincount(labels.ravel())[1:]
    return labels, int(count), sizes


def border_touching_labels(labels):
    if labels.size == 0:
        return np.array([], dtype=np.int64)
    faces = [
        labels[0, :, :],
        labels[-1, :, :],
        labels[:, 0, :],
        labels[:, -1, :],
        labels[:, :, 0],
        labels[:, :, -1],
    ]
    values = np.unique(np.concatenate([face.ravel() for face in faces]))
    return values[values != 0]


def build_ambiguous_block_table():
    ambiguous = np.zeros(256, dtype=bool)
    mixed = np.zeros(256, dtype=bool)
    local6 = structure_for_connectivity(6)
    local26 = structure_for_connectivity(26)
    for code in range(256):
        values = np.array([(code >> bit) & 1 for bit in range(8)], dtype=bool)
        block = values.reshape((2, 2, 2))
        n = int(block.sum())
        if n == 0 or n == 8:
            continue
        mixed[code] = True
        _, n6 = ndi.label(block, structure=local6)
        _, n26 = ndi.label(block, structure=local26)
        ambiguous[code] = n26 == 1 and n6 > 1
    return ambiguous, mixed


AMBIGUOUS_BLOCK_TABLE, MIXED_BLOCK_TABLE = build_ambiguous_block_table()


def count_local_ambiguous_blocks(mask):
    mask = np.asarray(mask, dtype=np.uint8)
    codes = np.zeros(tuple(dim - 1 for dim in mask.shape), dtype=np.uint8)
    bit = 0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                codes |= mask[dx : dx + codes.shape[0], dy : dy + codes.shape[1], dz : dz + codes.shape[2]] << bit
                bit += 1
    return int(AMBIGUOUS_BLOCK_TABLE[codes].sum()), int(MIXED_BLOCK_TABLE[codes].sum())


def apply_cleanup(mask, cfg):
    cleanup = cfg["cleanup"]
    cleaned = mask.copy()
    actions = []

    if cleanup.get("keep_largest_material_component", False):
        labels, count, sizes = component_stats(cleaned, 6)
        if count > 1:
            keep_label = int(np.argmax(sizes) + 1)
            removed = int(cleaned.sum() - np.count_nonzero(labels == keep_label))
            cleaned = labels == keep_label
            actions.append(f"keep_largest_material_component: removed_voxels={removed}")
        else:
            actions.append("keep_largest_material_component: no_action")

    min_material = int(cleanup.get("min_material_component_voxels", 0) or 0)
    if min_material > 0:
        labels, count, sizes = component_stats(cleaned, 6)
        remove_labels = np.where(sizes < min_material)[0] + 1
        if len(remove_labels):
            remove = np.isin(labels, remove_labels)
            cleaned[remove] = False
            actions.append(f"remove_small_material_components: threshold={min_material}, components={len(remove_labels)}, voxels={int(remove.sum())}")
        else:
            actions.append(f"remove_small_material_components: threshold={min_material}, no_action")

    fill_max = int(cleanup.get("fill_pore_cavities_max_voxels", 0) or 0)
    if fill_max > 0:
        pore_labels, count, sizes = component_stats(~cleaned, 6)
        border = set(int(value) for value in border_touching_labels(pore_labels))
        fill_labels = [index + 1 for index, size in enumerate(sizes) if size <= fill_max and (index + 1) not in border]
        if fill_labels:
            fill = np.isin(pore_labels, fill_labels)
            cleaned[fill] = True
            actions.append(f"fill_small_pore_cavities: threshold={fill_max}, components={len(fill_labels)}, voxels={int(fill.sum())}")
        else:
            actions.append(f"fill_small_pore_cavities: threshold={fill_max}, no_action")

    opening_iterations = int(cleanup.get("binary_opening_iterations", 0) or 0)
    if opening_iterations > 0:
        before = int(cleaned.sum())
        cleaned = ndi.binary_opening(cleaned, structure=structure_for_connectivity(6), iterations=opening_iterations)
        actions.append(f"binary_opening: iterations={opening_iterations}, material_voxel_delta={int(cleaned.sum()) - before}")

    closing_iterations = int(cleanup.get("binary_closing_iterations", 0) or 0)
    if closing_iterations > 0:
        before = int(cleaned.sum())
        cleaned = ndi.binary_closing(cleaned, structure=structure_for_connectivity(6), iterations=closing_iterations)
        actions.append(f"binary_closing: iterations={closing_iterations}, material_voxel_delta={int(cleaned.sum()) - before}")

    return cleaned, actions


def analyze(mask, cfg):
    material = bool_mask(mask, cfg["material_value"])
    pore = ~material
    _, material_6_count, material_6_sizes = component_stats(material, 6)
    _, material_26_count, material_26_sizes = component_stats(material, 26)
    pore_6_labels, pore_6_count, pore_6_sizes = component_stats(pore, 6)
    _, pore_26_count, pore_26_sizes = component_stats(pore, 26)

    border_pores = set(int(value) for value in border_touching_labels(pore_6_labels))
    enclosed_pore_components = [index + 1 for index in range(len(pore_6_sizes)) if (index + 1) not in border_pores]
    enclosed_pore_voxels = int(sum(int(pore_6_sizes[index - 1]) for index in enclosed_pore_components))

    material_ambiguous_blocks, mixed_blocks = count_local_ambiguous_blocks(material)
    pore_ambiguous_blocks, _ = count_local_ambiguous_blocks(pore)

    metrics = {
        "shape": tuple(int(v) for v in material.shape),
        "total_voxels": int(material.size),
        "material_voxels": int(material.sum()),
        "pore_voxels": int(pore.sum()),
        "relative_density": float(material.mean()),
        "material_components_6": material_6_count,
        "material_components_26": material_26_count,
        "material_components_joined_only_by_edge_or_corner": max(0, material_6_count - material_26_count),
        "largest_material_component_6": int(material_6_sizes.max()) if len(material_6_sizes) else 0,
        "smallest_material_component_6": int(material_6_sizes.min()) if len(material_6_sizes) else 0,
        "pore_components_6": pore_6_count,
        "pore_components_26": pore_26_count,
        "pore_components_joined_only_by_edge_or_corner": max(0, pore_6_count - pore_26_count),
        "enclosed_pore_components_6": len(enclosed_pore_components),
        "enclosed_pore_voxels_6": enclosed_pore_voxels,
        "mixed_2x2x2_blocks": mixed_blocks,
        "material_ambiguous_2x2x2_blocks": material_ambiguous_blocks,
        "pore_ambiguous_2x2x2_blocks": pore_ambiguous_blocks,
    }
    return metrics


def bool_mask(volume, material_value=1):
    return np.asarray(volume == material_value, dtype=bool)


def verdict(metrics):
    if metrics["material_ambiguous_2x2x2_blocks"] > 0 or metrics["pore_ambiguous_2x2x2_blocks"] > 0:
        return "bad"
    if metrics["material_components_joined_only_by_edge_or_corner"] > 0 or metrics["pore_components_joined_only_by_edge_or_corner"] > 0:
        return "acceptable"
    return "good"


def write_report(path, input_path, output_path, before, after, actions, cfg):
    lines = [
        f"Voxel topology verdict: {verdict(after if after else before)}",
        f"Input volume: {input_path}",
        f"Cleaned output: {output_path if output_path else 'not_written'}",
        f"Cleanup enabled: {cfg['cleanup'].get('enabled', False)}",
        f"Use cleaned for meshing: {cfg.get('use_cleaned_for_meshing', False)}",
        "",
        "Before cleanup:",
    ]
    for key, value in before.items():
        lines.append(f"  {key}: {value}")
    if after:
        lines.append("")
        lines.append("After cleanup:")
        for key, value in after.items():
            lines.append(f"  {key}: {value}")
        lines.append("")
        lines.append("Cleanup deltas:")
        lines.append(f"  material_voxels: {after['material_voxels'] - before['material_voxels']}")
        lines.append(f"  relative_density: {after['relative_density'] - before['relative_density']:.8g}")
    lines.append("")
    lines.append("Actions:")
    if actions:
        lines.extend(f"  {action}" for action in actions)
    else:
        lines.append("  none")
    lines.extend(
        [
            "",
            "Interpretation:",
            "  material/pore components joined only by edge or corner indicate digital topology ambiguity.",
            "  ambiguous 2x2x2 blocks are likely sources of non-manifold extracted surfaces.",
            "  small component removal and small cavity filling are conservative cleanup operations.",
            "  binary opening/closing is stronger and can change density and thin struts; use only after checking the report.",
            "",
        ]
    )
    path.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Audit and optionally clean binary voxel topology before meshing.")
    parser.add_argument("--config", default=None, help="Optional config JSON containing 02c_voxel_topology_cleanup")
    parser.add_argument("--npy", required=True, help="Input volume.npy path")
    parser.add_argument("--output", default=None, help="Optional cleaned .npy output path")
    parser.add_argument("--report", default=None, help="Optional topology report path")
    parser.add_argument("--clean", action="store_true", help="Force cleanup even if config cleanup.enabled is false")
    args = parser.parse_args()

    cfg = load_config(args.config)
    input_path = Path(args.npy)
    output_path = Path(args.output) if args.output else input_path.with_name(cfg["output_filename"])
    report_path = Path(args.report) if args.report else input_path.with_name(cfg["report_filename"])

    volume = np.load(input_path)
    before = analyze(volume, cfg)
    cleanup_enabled = bool(cfg["cleanup"].get("enabled", False)) or args.clean
    actions = []
    after = None
    written_output = None

    if cleanup_enabled:
        cleaned_mask, actions = apply_cleanup(bool_mask(volume, cfg["material_value"]), cfg)
        cleaned = np.where(cleaned_mask, cfg["material_value"], 0).astype(volume.dtype, copy=False)
        after = analyze(cleaned, cfg)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(output_path, cleaned)
        written_output = output_path

    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_report(report_path, input_path, written_output, before, after, actions, cfg)
    print(f"Wrote voxel topology report: {report_path}")
    print(f"Voxel topology verdict: {verdict(after if after else before)}")
    if written_output:
        print(f"Wrote cleaned volume: {written_output}")


if __name__ == "__main__":
    main()
