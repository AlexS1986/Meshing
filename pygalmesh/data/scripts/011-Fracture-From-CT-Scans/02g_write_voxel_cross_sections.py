#!/usr/bin/env python3
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def parse_args():
    parser = argparse.ArgumentParser(
        description="Write a middle-z cross-section PNG for a voxel .npy file."
    )
    parser.add_argument("--npy", required=True, help="Input voxel .npy file")
    parser.add_argument("--output-dir", required=True, help="Output folder for PNG files")
    parser.add_argument("--stage", required=True, help="Stage label used in the output filename")
    parser.add_argument("--axis", default="z", choices=("x", "y", "z"), help="Slice normal axis")
    parser.add_argument("--index", type=int, default=None, help="Slice index. Defaults to middle slice.")
    return parser.parse_args()


def safe_stage_name(stage):
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in stage)


def extract_slice(volume, axis, index):
    axis_index = {"x": 0, "y": 1, "z": 2}[axis]
    if index is None:
        index = volume.shape[axis_index] // 2
    if index < 0 or index >= volume.shape[axis_index]:
        raise ValueError(f"Slice index {index} is outside axis {axis} with size {volume.shape[axis_index]}")

    if axis == "x":
        image = volume[index, :, :].T
        xlabel = "y"
        ylabel = "z"
    elif axis == "y":
        image = volume[:, index, :].T
        xlabel = "x"
        ylabel = "z"
    else:
        image = volume[:, :, index].T
        xlabel = "x"
        ylabel = "y"
    return image, index, xlabel, ylabel


def main():
    args = parse_args()
    npy_path = Path(args.npy)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    volume = np.load(npy_path)
    image, index, xlabel, ylabel = extract_slice(volume, args.axis, args.index)
    stage = safe_stage_name(args.stage)
    output_path = output_dir / f"{stage}_middle_{args.axis}{index:04d}.png"

    fig_width = max(4.0, min(14.0, image.shape[1] / 40.0))
    fig_height = max(4.0, min(14.0, image.shape[0] / 40.0))
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=160)
    ax.imshow(image, cmap="gray", origin="lower", interpolation="nearest", vmin=0, vmax=1)
    ax.set_title(f"{stage} | shape={tuple(int(v) for v in volume.shape)} | {args.axis}={index}")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)

    print(f"Wrote voxel cross-section: {output_path}")


if __name__ == "__main__":
    main()
