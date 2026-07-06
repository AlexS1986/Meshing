#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


METRIC_PATTERNS = {
    "mesh_points": r"Mesh points:\s+(\d+)",
    "mesh_tetrahedra": r"Mesh tetrahedra:\s+(\d+)",
    "smallest_volume": r"Smallest volume:\s+([0-9.eE+-]+)",
    "largest_volume": r"Largest volume:\s+([0-9.eE+-]+)",
    "shortest_edge": r"Shortest edge:\s+([0-9.eE+-]+)",
    "longest_edge": r"Longest edge:\s+([0-9.eE+-]+)",
    "smallest_aspect_ratio": r"Smallest asp\.ratio:\s+([0-9.eE+-]+)",
    "largest_aspect_ratio": r"Largest asp\.ratio:\s+([0-9.eE+-]+)",
    "smallest_facet_angle": r"Smallest facangle:\s+([0-9.eE+-]+)",
    "largest_facet_angle": r"Largest facangle:\s+([0-9.eE+-]+)",
    "smallest_dihedral": r"Smallest dihedral:\s+([0-9.eE+-]+)",
    "largest_dihedral": r"Largest dihedral:\s+([0-9.eE+-]+)",
}


DEFAULT_THRESHOLDS = {
    "largest_aspect_ratio": {"good": 20.0, "acceptable": 50.0, "direction": "max"},
    "smallest_dihedral": {"good": 10.0, "acceptable": 5.0, "direction": "min"},
    "dihedral_0_5_fraction": {"good": 0.0, "acceptable": 0.001, "direction": "max"},
    "dihedral_5_10_fraction": {"good": 0.01, "acceptable": 0.05, "direction": "max"},
    "smallest_facet_angle": {"good": 5.0, "acceptable": 2.0, "direction": "min"},
}


def load_thresholds(config_path):
    if not config_path:
        return DEFAULT_THRESHOLDS
    with open(config_path, "r") as handle:
        config = json.load(handle)
    thresholds = DEFAULT_THRESHOLDS.copy()
    thresholds.update(config.get("08_mesh_quality_report", {}).get("thresholds", {}))
    return thresholds


def parse_number(value):
    if value is None or value == "":
        return None
    try:
        if re.fullmatch(r"[+-]?\d+", str(value)):
            return int(value)
        return float(value)
    except ValueError:
        return None


def parse_tetgen_log(log_path):
    text = Path(log_path).read_text()
    metrics = {}
    for key, pattern in METRIC_PATTERNS.items():
        match = re.search(pattern, text)
        metrics[key] = parse_number(match.group(1)) if match else None

    low_dihedral = re.search(r"0 -\s+5 degrees:\s+(\d+).*\n\s+5 - 10 degrees:\s+(\d+)", text)
    metrics["dihedral_0_5_count"] = int(low_dihedral.group(1)) if low_dihedral else None
    metrics["dihedral_5_10_count"] = int(low_dihedral.group(2)) if low_dihedral else None

    n_tets = metrics.get("mesh_tetrahedra")
    if n_tets:
        # TetGen reports six dihedral angles per tetrahedron in the histogram.
        n_angles = 6 * n_tets
        metrics["dihedral_0_5_fraction"] = metrics["dihedral_0_5_count"] / n_angles if metrics["dihedral_0_5_count"] is not None else None
        metrics["dihedral_5_10_fraction"] = metrics["dihedral_5_10_count"] / n_angles if metrics["dihedral_5_10_count"] is not None else None
    else:
        metrics["dihedral_0_5_fraction"] = None
        metrics["dihedral_5_10_fraction"] = None

    metrics["consistent"] = "mesh appears to be consistent" in text
    metrics["boundary_consistent"] = "Mesh boundaries connected correctly" in text
    return metrics


def classify_metric(value, rule):
    if value is None:
        return "bad"
    direction = rule.get("direction", "max")
    good = rule["good"]
    acceptable = rule["acceptable"]
    if direction == "max":
        if value <= good:
            return "good"
        if value <= acceptable:
            return "acceptable"
        return "bad"
    if value >= good:
        return "good"
    if value >= acceptable:
        return "acceptable"
    return "bad"


def combine(statuses):
    statuses = list(statuses)
    if any(status == "bad" for status in statuses):
        return "bad"
    if any(status == "acceptable" for status in statuses):
        return "acceptable"
    return "good"


def format_value(value):
    if value is None:
        return "missing"
    if isinstance(value, float):
        if abs(value) < 0.01 and value != 0:
            return f"{value:.4e}"
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def build_report(metrics, thresholds, log_path):
    checks = []
    checks.append(("tetgen_consistency", "good" if metrics.get("consistent") else "bad", "mesh consistency check"))
    checks.append(("boundary_consistency", "good" if metrics.get("boundary_consistent") else "bad", "boundary connectivity check"))

    for key, rule in thresholds.items():
        value = metrics.get(key)
        checks.append((key, classify_metric(value, rule), f"value={format_value(value)}, good={rule['good']}, acceptable={rule['acceptable']}, direction={rule.get('direction', 'max')}"))

    verdict = combine(status for _, status, _ in checks)
    lines = [
        f"Mesh quality verdict: {verdict}",
        f"TetGen log: {log_path}",
        "",
        "Summary metrics:",
        f"  mesh_points: {format_value(metrics.get('mesh_points'))}",
        f"  mesh_tetrahedra: {format_value(metrics.get('mesh_tetrahedra'))}",
        f"  largest_aspect_ratio: {format_value(metrics.get('largest_aspect_ratio'))}",
        f"  smallest_dihedral: {format_value(metrics.get('smallest_dihedral'))}",
        f"  dihedral_0_5_count: {format_value(metrics.get('dihedral_0_5_count'))}",
        f"  dihedral_0_5_fraction: {format_value(metrics.get('dihedral_0_5_fraction'))}",
        f"  dihedral_5_10_count: {format_value(metrics.get('dihedral_5_10_count'))}",
        f"  dihedral_5_10_fraction: {format_value(metrics.get('dihedral_5_10_fraction'))}",
        f"  smallest_facet_angle: {format_value(metrics.get('smallest_facet_angle'))}",
        "",
        "Checks:",
    ]
    for name, status, detail in checks:
        lines.append(f"  [{status}] {name}: {detail}")
    lines.append("")
    return verdict, lines


def main():
    parser = argparse.ArgumentParser(description="Classify TetGen mesh quality metrics as good, acceptable, or bad.")
    parser.add_argument("--tetgen-log", required=True, help="TetGen .tetgen.log file")
    parser.add_argument("--output", default=None, help="Output .txt report path")
    parser.add_argument("--config", default=None, help="Optional config JSON with 08_mesh_quality_report.thresholds")
    args = parser.parse_args()

    log_path = Path(args.tetgen_log)
    output_path = Path(args.output) if args.output else log_path.with_suffix(".quality.txt")
    thresholds = load_thresholds(args.config)
    metrics = parse_tetgen_log(log_path)
    verdict, lines = build_report(metrics, thresholds, log_path)
    output_path.write_text("\n".join(lines))
    print(f"Wrote mesh quality report: {output_path}")
    print(f"Mesh quality verdict: {verdict}")


if __name__ == "__main__":
    main()
