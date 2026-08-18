#!/usr/bin/env python3
"""
A03_plot_les_structure.py — schnelle 3D-Bilder der segmentierten .leS-Struktur.

Gedacht für den lokalen Container: eine `.leS`-Datei rein, PNGs raus, ohne
Umweg über die Pipeline und ohne VTK/OpenGL (nur numpy/scipy/matplotlib).

Das Skript setzt nur zusammen, was schon da ist:

* Einlesen, Reduktion und Ausschnitt kommen aus `A01_les_2_npy.py`
  (gleiche Optionen, gleiche Verifikation),
* die Darstellung aus `A02_preview_voxel_volume.py`
  (First-Hit-Tiefenpuffer mit Lambert-Shading).

Beispiele
---------
    # Schnellansicht des ganzen Volumens (reduce=8 -> 148x148x110, ein paar Sekunden)
    python3 A03_plot_les_structure.py --reduce 8

    # feiner, mit Schnittbildern dazu
    python3 A03_plot_les_structure.py --reduce 4 --slices

    # nur ein Ausschnitt, andere Blickwinkel, eigener Zielordner
    python3 A03_plot_les_structure.py --reduce 2 \
        --x-range 300 900 --y-range 300 900 --z-range 200 800 \
        --views -40 22 55 18 130 15 --output-dir /data/scripts/014-Yield-Surface-From-leS/plots

Ausgabe: `<name>_3d.png`, optional `<name>_slices.png` und (mit `--keep-npy`)
das reduzierte Volumen als `.npy`.
"""

import argparse
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import A01_les_2_npy as les          # noqa: E402  Einlesen + Reduktion
import A02_preview_voxel_volume as prev  # noqa: E402  Darstellung


def load_les(args, output_path):
    """Ruft A01 mit denselben Optionen auf und liefert das Volumen (1 = Aluminium)."""
    a01 = les.build_parser().parse_args([])
    a01.input = args.input
    a01.output = output_path
    a01.metadata = os.path.splitext(output_path)[0] + ".json"
    a01.reduce = args.reduce
    a01.reduce_mode = args.reduce_mode
    a01.reduce_threshold = args.reduce_threshold
    a01.smooth_sigma = args.smooth_sigma
    a01.x_range = args.x_range
    a01.y_range = args.y_range
    a01.z_range = args.z_range
    a01.line_order = args.line_order
    a01.les_material_value = args.les_material_value
    a01.phase_convention = "raw"      # fürs Bild ist 1 = Aluminium bequemer
    a01.pipeline_metadata = None
    metadata = les.convert(a01)
    return np.load(output_path), metadata


def main():
    parser = argparse.ArgumentParser(
        description="3D-Ansichten und Schnitte einer segmentierten .leS-Struktur.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", default=None,
                        help="Datei, Ordner oder Glob mit der .leS-Datei "
                             f"(Default-Suche: {', '.join(les.DEFAULT_INPUT_CANDIDATES)})")
    parser.add_argument("--output-dir", default=None,
                        help="Zielordner der PNGs (Default: Ordner der .leS-Datei)")
    parser.add_argument("--name", default=None, help="Präfix der Ausgabedateien")
    parser.add_argument("--reduce", type=int, default=8,
                        help="N×N×N Voxel zusammenfassen; 8 ist die schnelle Übersicht")
    parser.add_argument("--reduce-mode", default="majority",
                        choices=["majority", "threshold", "any", "all"])
    parser.add_argument("--reduce-threshold", type=float, default=0.5)
    parser.add_argument("--smooth-sigma", type=float, default=0.0)
    parser.add_argument("--x-range", nargs=2, type=int, default=None)
    parser.add_argument("--y-range", nargs=2, type=int, default=None)
    parser.add_argument("--z-range", nargs=2, type=int, default=None)
    parser.add_argument("--line-order", default="C", choices=["C", "F"])
    parser.add_argument("--les-material-value", type=int, default=1)
    parser.add_argument("--views", nargs="*", type=float, default=[-40, 22, 55, 18],
                        help="Paare aus Azimut und Elevation in Grad")
    parser.add_argument("--slices", action="store_true",
                        help="zusätzlich drei orthogonale Schnitte zeichnen")
    parser.add_argument("--keep-npy", action="store_true",
                        help="das reduzierte Volumen als .npy behalten")
    parser.add_argument("--dpi", type=int, default=190)
    args = parser.parse_args()

    source = les.resolve_input(args.input)
    output_dir = args.output_dir or os.path.dirname(os.path.abspath(source))
    os.makedirs(output_dir, exist_ok=True)
    stem = args.name or f"{os.path.splitext(os.path.basename(source))[0]}_r{args.reduce}"

    if args.keep_npy:
        volume_path = os.path.join(output_dir, f"{stem}.npy")
        volume, metadata = load_les(args, volume_path)
        print(f"💾 Volumen behalten: {volume_path}")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            volume, metadata = load_les(args, os.path.join(tmp, "volume.npy"))
            volume = np.array(volume)

    voxel_mm = metadata["voxel_size_mm"]
    extent = np.array(volume.shape) * voxel_mm
    density = float((volume == 1).mean())
    print(f"📐 {volume.shape} Voxel à {voxel_mm * 1e3:.1f} µm = "
          f"{extent[0]:.1f} × {extent[1]:.1f} × {extent[2]:.1f} mm, "
          f"relative Dichte {density * 100:.2f} %")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    mask = volume == 1
    views = [(args.views[i], args.views[i + 1]) for i in range(0, len(args.views) - 1, 2)]
    fig, axes = plt.subplots(1, len(views), figsize=(7.5 * len(views), 7),
                             dpi=args.dpi, squeeze=False)
    for axis, (azim, elev) in zip(axes[0], views):
        axis.imshow(prev.depth_render(mask, azim, elev), cmap="bone", vmin=0, vmax=1,
                    interpolation="bilinear")
        axis.set_axis_off()
        axis.set_title(f"Azimut {azim:.0f}°, Elevation {elev:.0f}°", fontsize=10)
    fig.suptitle(f"{os.path.basename(source)} — Aluminiumphase, reduce={args.reduce} "
                 f"({voxel_mm * 1e3:.1f} µm/Voxel)\n"
                 f"{volume.shape[0]}×{volume.shape[1]}×{volume.shape[2]} Voxel = "
                 f"{extent[0]:.1f} × {extent[1]:.1f} × {extent[2]:.1f} mm, "
                 f"relative Dichte {density * 100:.2f} % "
                 f"(Porosität {100 - density * 100:.2f} %)", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    render_path = os.path.join(output_dir, f"{stem}_3d.png")
    fig.savefig(render_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"🖼  {render_path}")

    if args.slices:
        mid = [dim // 2 for dim in volume.shape]
        panels = [
            (mask[:, :, mid[2]].T, f"xy-Schnitt, z = {mid[2]}", "x", "y", (0, extent[0], 0, extent[1])),
            (mask[:, mid[1], :].T, f"xz-Schnitt, y = {mid[1]}", "x", "z", (0, extent[0], 0, extent[2])),
            (mask[mid[0], :, :].T, f"yz-Schnitt, x = {mid[0]}", "y", "z", (0, extent[1], 0, extent[2])),
        ]
        fig, axes = plt.subplots(1, 3, figsize=(16, 5.6), dpi=args.dpi)
        for axis, (image, title, xlabel, ylabel, ext) in zip(axes, panels):
            axis.imshow(image, cmap="gray_r", origin="lower", extent=ext, interpolation="nearest")
            axis.set_title(title, fontsize=10)
            axis.set_xlabel(f"{xlabel} [mm]")
            axis.set_ylabel(f"{ylabel} [mm]")
            axis.set_aspect("equal")
        fig.suptitle(f"{os.path.basename(source)} — orthogonale Schnitte (schwarz = Aluminium)",
                     fontsize=12)
        fig.tight_layout(rect=[0, 0, 1, 0.94])
        slices_path = os.path.join(output_dir, f"{stem}_slices.png")
        fig.savefig(slices_path, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print(f"🖼  {slices_path}")


if __name__ == "__main__":
    main()
