#!/usr/bin/env python3
"""Create publication-ready plots from the phase-field graph output.

By default, all ``pfmfrac*_graphs.txt`` files below ``00_results`` are
plotted. Both graph layouts written by ``pfmfrac_function.py`` are supported:

    legacy:  time, J_x, J_y, J_z, x_tip, x_tip_prescribed, ...
    current: time, J_x, J_y, J_z, J_x/t_z, ..., x_tip, x_tip_prescribed, ...

The plots use the measured phase-field crack tip, not the prescribed surfing
position. Quantities are nondimensionalized consistently with the plots in
``061-plasticity-fracture-noll-3D`` and exported as PNG, PDF, and PGF.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re

import matplotlib.pyplot as plt
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "00_results"
DEFAULT_OUTPUT = RESULTS_DIR / "Jx_vs_real_crack_tip.png"
DEFAULT_MONOTONIC_OUTPUT = RESULTS_DIR / "Jx_vs_monotonic_real_crack_tip.png"
DEFAULT_TIME_OUTPUT = RESULTS_DIR / "Jx_vs_time.png"
DEFAULT_RAW_OUTPUT = RESULTS_DIR / "Jx_vs_real_crack_tip_unnormalized.png"
DEFAULT_RAW_MONOTONIC_OUTPUT = (
    RESULTS_DIR / "Jx_vs_monotonic_real_crack_tip_unnormalized.png"
)
DEFAULT_RAW_TIME_OUTPUT = RESULTS_DIR / "Jx_vs_time_unnormalized.png"

TIME_COLUMN = 0
LEGACY_COLUMN_COUNT = 12
CURRENT_COLUMN_COUNT = 15

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 16,
        "axes.labelsize": 18,
        "xtick.labelsize": 18,
        "ytick.labelsize": 18,
        "legend.fontsize": 16,
        "text.usetex": True,
        "text.latex.preamble": r"\usepackage{type1cm}",
        "pgf.rcfonts": False,
    }
)


def find_graph_files() -> list[Path]:
    """Return all phase-field graph files below the ignored results folder."""
    return sorted(RESULTS_DIR.rglob("pfmfrac*_graphs.txt"))


def load_graph_data(graph_file: Path) -> np.ndarray:
    """Load and validate one phase-field graph file."""
    data = np.loadtxt(graph_file, comments="#", ndmin=2)
    if data.shape[1] not in (LEGACY_COLUMN_COUNT, CURRENT_COLUMN_COUNT):
        raise ValueError(
            f"{graph_file} has {data.shape[1]} columns; expected "
            f"{LEGACY_COLUMN_COUNT} (legacy) or {CURRENT_COLUMN_COUNT} (current)."
        )
    return data


def find_mesh_report(graph_file: Path) -> Path:
    """Find the mesh report containing the physical specimen bounds."""
    for directory in (graph_file.parent, *graph_file.parents):
        report = directory / "mesh.snap_boundary.txt"
        if report.is_file():
            return report
        if directory == RESULTS_DIR:
            break
    raise FileNotFoundError(
        f"No mesh.snap_boundary.txt found above {graph_file}; it is required "
        "for the L and thickness normalization."
    )


def read_specimen_bounds(graph_file: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read bounds_min and bounds_max from the mesh snap report."""
    report = find_mesh_report(graph_file)
    text = report.read_text(encoding="utf-8")

    def parse_vector(key: str) -> np.ndarray:
        match = re.search(rf"^{key}:\s*\[([^]]+)\]", text, re.MULTILINE)
        if match is None:
            raise ValueError(f"Missing {key} in {report}.")
        return np.fromstring(match.group(1), sep=",")

    bounds_min = parse_vector("bounds_min")
    bounds_max = parse_vector("bounds_max")
    if bounds_min.size != 3 or bounds_max.size != 3:
        raise ValueError(f"Invalid three-dimensional bounds in {report}.")
    return bounds_min, bounds_max


def read_gc(graph_file: Path) -> float:
    """Read G_c from the simulation directory name produced by script.py."""
    match = re.search(r"_Gc([-+0-9.eE]+)_eps", graph_file.parent.name)
    if match is None:
        raise ValueError(f"Cannot determine G_c from {graph_file.parent.name!r}.")
    gc = float(match.group(1))
    if gc <= 0.0:
        raise ValueError(f"G_c must be positive, got {gc}.")
    return gc


def normalized_plot_data(
    graph_file: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return dimensionless time, measured crack position, and J_x."""
    data = load_graph_data(graph_file)
    bounds_min, bounds_max = read_specimen_bounds(graph_file)
    length = bounds_max[1] - bounds_min[1]
    thickness = bounds_max[2] - bounds_min[2]
    if length <= 0.0 or thickness <= 0.0:
        raise ValueError(f"Invalid specimen dimensions for {graph_file}.")

    if data.shape[1] == LEGACY_COLUMN_COUNT:
        jx_per_thickness = data[:, 1] / thickness
        crack_tip = data[:, 4]
        prescribed_tip = data[:, 5]
    else:
        jx_per_thickness = data[:, 4]
        crack_tip = data[:, 7]
        prescribed_tip = data[:, 8]

    time = data[:, TIME_COLUMN]
    if len(time) < 2:
        raise ValueError(f"At least two time values are required in {graph_file}.")
    prescribed_velocity = np.polyfit(time, prescribed_tip, deg=1)[0]
    if not np.isfinite(prescribed_velocity) or prescribed_velocity <= 0.0:
        raise ValueError(f"Invalid prescribed crack velocity in {graph_file}.")

    normalized_time = time / (length / prescribed_velocity)
    normalized_crack_tip = (crack_tip - bounds_min[0]) / length
    normalized_jx = jx_per_thickness / read_gc(graph_file)
    return normalized_time, normalized_crack_tip, normalized_jx


def unnormalized_plot_data(
    graph_file: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return raw time, measured crack position, and integrated 3D J_x."""
    data = load_graph_data(graph_file)
    if data.shape[1] == LEGACY_COLUMN_COUNT:
        crack_tip = data[:, 4]
    else:
        crack_tip = data[:, 7]
    return data[:, TIME_COLUMN], crack_tip, data[:, 1]


def load_jx_and_crack_tip(graph_file: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load finite normalized J_x and measured crack-tip values."""
    _, crack_tip, jx = normalized_plot_data(graph_file)

    finite = np.isfinite(jx) & np.isfinite(crack_tip)
    if not np.any(finite):
        raise ValueError(f"{graph_file} contains no finite J_x/crack-tip pairs.")
    return crack_tip[finite], jx[finite]


def load_time_and_jx(graph_file: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load finite normalized time and J_x values from one graph file."""
    time, _, jx = normalized_plot_data(graph_file)
    finite = np.isfinite(time) & np.isfinite(jx)
    if not np.any(finite):
        raise ValueError(f"{graph_file} contains no finite time/J_x pairs.")
    return time[finite], jx[finite]


def dataset_label(graph_file: Path) -> str:
    """Build a concise label from the simulation directory."""
    try:
        relative_parent = graph_file.parent.relative_to(RESULTS_DIR)
    except ValueError:
        relative_parent = graph_file.parent
    return str(relative_parent)


def plot_jx_vs_crack_tip(graph_files: list[Path], output: Path) -> None:
    """Create and save the J_x-versus-real-crack-tip plot."""
    fig, ax = plt.subplots(figsize=(10.0, 6.0))

    for graph_file in graph_files:
        crack_tip, jx = load_jx_and_crack_tip(graph_file)
        ax.plot(
            crack_tip,
            jx,
            marker="o",
            markersize=3,
            linewidth=1,
            label=dataset_label(graph_file),
        )

    ax.set_xlabel(r"$(x_{\mathrm{tip}}-x_{\min})/L$")
    ax.set_ylabel(r"$J_x/G_c$")
    ax.grid(True, alpha=0.3)
    if len(graph_files) > 1:
        ax.legend()

    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    save_latex_ready_figure(fig, output)
    plt.close(fig)


def plot_jx_vs_monotonic_crack_tip(graph_files: list[Path], output: Path) -> None:
    """Plot J_x against the furthest crack-tip position reached so far."""
    fig, ax = plt.subplots(figsize=(10.0, 6.0))

    for graph_file in graph_files:
        crack_tip, jx = load_jx_and_crack_tip(graph_file)
        monotonic_crack_tip = np.maximum.accumulate(crack_tip)
        ax.plot(
            monotonic_crack_tip,
            jx,
            marker="o",
            markersize=3,
            linewidth=1,
            label=dataset_label(graph_file),
        )

    ax.set_xlabel(
        r"$\max_{\tau\leq t}(x_{\mathrm{tip}}(\tau)-x_{\min})/L$"
    )
    ax.set_ylabel(r"$J_x/G_c$")
    ax.grid(True, alpha=0.3)
    if len(graph_files) > 1:
        ax.legend()

    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    save_latex_ready_figure(fig, output)
    plt.close(fig)


def plot_jx_vs_time(graph_files: list[Path], output: Path) -> None:
    """Create and save the J_x-versus-time plot."""
    fig, ax = plt.subplots(figsize=(10.0, 6.0))

    for graph_file in graph_files:
        time, jx = load_time_and_jx(graph_file)
        ax.plot(
            time,
            jx,
            marker="o",
            markersize=3,
            linewidth=1,
            label=dataset_label(graph_file),
        )

    ax.set_xlabel(r"$t/[L/\dot{x}_{\mathrm{bc}}]$")
    ax.set_ylabel(r"$J_x/G_c$")
    ax.grid(True, alpha=0.3)
    if len(graph_files) > 1:
        ax.legend()

    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    save_latex_ready_figure(fig, output)
    plt.close(fig)


def plot_unnormalized_jx_vs_crack_tip(
    graph_files: list[Path], output: Path, monotonic: bool = False
) -> None:
    """Plot raw integrated J_x against the raw measured crack position."""
    fig, ax = plt.subplots(figsize=(10.0, 6.0))

    for graph_file in graph_files:
        _, crack_tip, jx = unnormalized_plot_data(graph_file)
        finite = np.isfinite(crack_tip) & np.isfinite(jx)
        crack_tip = crack_tip[finite]
        jx = jx[finite]
        if monotonic:
            crack_tip = np.maximum.accumulate(crack_tip)
        ax.plot(
            crack_tip,
            jx,
            marker="o",
            markersize=3,
            linewidth=1,
            label=dataset_label(graph_file),
        )

    if monotonic:
        ax.set_xlabel(r"$\max_{\tau\leq t}x_{\mathrm{tip}}(\tau)$")
    else:
        ax.set_xlabel(r"$x_{\mathrm{tip}}$")
    ax.set_ylabel(r"$J_x$")
    ax.grid(True, alpha=0.3)
    if len(graph_files) > 1:
        ax.legend()

    fig.tight_layout()
    save_latex_ready_figure(fig, output)
    plt.close(fig)


def plot_unnormalized_jx_vs_time(graph_files: list[Path], output: Path) -> None:
    """Plot raw integrated J_x against raw simulation time."""
    fig, ax = plt.subplots(figsize=(10.0, 6.0))

    for graph_file in graph_files:
        time, _, jx = unnormalized_plot_data(graph_file)
        finite = np.isfinite(time) & np.isfinite(jx)
        ax.plot(
            time[finite],
            jx[finite],
            marker="o",
            markersize=3,
            linewidth=1,
            label=dataset_label(graph_file),
        )

    ax.set_xlabel(r"$t$")
    ax.set_ylabel(r"$J_x$")
    ax.grid(True, alpha=0.3)
    if len(graph_files) > 1:
        ax.legend()

    fig.tight_layout()
    save_latex_ready_figure(fig, output)
    plt.close(fig)


def save_latex_ready_figure(fig: plt.Figure, output: Path) -> None:
    """Save raster, vector, and directly includable LaTeX versions."""
    output.parent.mkdir(parents=True, exist_ok=True)
    for suffix in (".png", ".pdf", ".pgf"):
        target = output.with_suffix(suffix)
        options = {"dpi": 300} if suffix == ".png" else {}
        fig.savefig(target, bbox_inches="tight", **options)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot J_x versus the measured phase-field crack-tip position."
    )
    parser.add_argument(
        "graph_files",
        metavar="GRAPH_FILE",
        nargs="*",
        type=Path,
        help=(
            "graph file(s) to plot; defaults to every pfmfrac*_graphs.txt "
            "below 00_results"
        ),
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"output image (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--time-output",
        type=Path,
        default=DEFAULT_TIME_OUTPUT,
        help=f"J_x-versus-time output image (default: {DEFAULT_TIME_OUTPUT})",
    )
    parser.add_argument(
        "--monotonic-output",
        type=Path,
        default=DEFAULT_MONOTONIC_OUTPUT,
        help=(
            "J_x-versus-monotonic-crack-tip output image "
            f"(default: {DEFAULT_MONOTONIC_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--raw-output",
        type=Path,
        default=DEFAULT_RAW_OUTPUT,
        help=f"unnormalized crack-tip plot (default: {DEFAULT_RAW_OUTPUT})",
    )
    parser.add_argument(
        "--raw-monotonic-output",
        type=Path,
        default=DEFAULT_RAW_MONOTONIC_OUTPUT,
        help=(
            "unnormalized monotonic crack-tip plot "
            f"(default: {DEFAULT_RAW_MONOTONIC_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--raw-time-output",
        type=Path,
        default=DEFAULT_RAW_TIME_OUTPUT,
        help=f"unnormalized time plot (default: {DEFAULT_RAW_TIME_OUTPUT})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    graph_files = [path.resolve() for path in args.graph_files] or find_graph_files()
    if not graph_files:
        raise FileNotFoundError(
            f"No pfmfrac*_graphs.txt files found below {RESULTS_DIR}."
        )

    missing = [path for path in graph_files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Graph file not found: {missing[0]}")

    output = args.output.resolve()
    monotonic_output = args.monotonic_output.resolve()
    time_output = args.time_output.resolve()
    raw_output = args.raw_output.resolve()
    raw_monotonic_output = args.raw_monotonic_output.resolve()
    raw_time_output = args.raw_time_output.resolve()
    plot_jx_vs_crack_tip(graph_files, output)
    plot_jx_vs_monotonic_crack_tip(graph_files, monotonic_output)
    plot_jx_vs_time(graph_files, time_output)
    plot_unnormalized_jx_vs_crack_tip(graph_files, raw_output)
    plot_unnormalized_jx_vs_crack_tip(
        graph_files, raw_monotonic_output, monotonic=True
    )
    plot_unnormalized_jx_vs_time(graph_files, raw_time_output)
    for base in (
        output,
        monotonic_output,
        time_output,
        raw_output,
        raw_monotonic_output,
        raw_time_output,
    ):
        print(f"Wrote {base.with_suffix('.png')}")
        print(f"Wrote {base.with_suffix('.pdf')}")
        print(f"Wrote {base.with_suffix('.pgf')}")


if __name__ == "__main__":
    main()
