#!/usr/bin/env python3
"""
A02_preview_voxel_volume.py — Sichtprüfung eines Voxelvolumens (.npy) im Container.

Erzeugt ohne 3D-Renderer (nur numpy/scipy/matplotlib):

* `<name>_slices.png`  — drei orthogonale Schnitte durch die Volumenmitte
* `<name>_3d.png`      — zwei Schrägansichten der Materialphase
                         (Orthogonalprojektion mit First-Hit-Tiefenpuffer und
                         Lambert-Beleuchtung; kein OpenGL/VTK nötig)

Phasenkonvention
----------------
Vor Schritt 03 gilt im Repository **0 = Aluminium, 1 = Pore**
(siehe PIPELINE_ANNAHMEN_DICOM_TO_FEM.md). Default ist deshalb
`--material-value 0`. Bei einer .leS-Rohdatei-Konvertierung mit
`--phase-convention raw` ist stattdessen `--material-value 1` richtig.
Mit `--config` wird der Wert aus dem Abschnitt `A01_les_2_npy` übernommen,
mit `--auto-material-value` aus der Sidecar-JSON neben der .npy-Datei.

Beispiele
---------
    # Ergebnis der .leS-Konvertierung ansehen (Pipeline-Konvention)
    python3 A02_preview_voxel_volume.py \
        --npy /data/scripts/015-Yield-Surface-Batch-leS/JM-25-77_A01_les_segmented/JM-25-77_A01_les_segmented_3D/segmented_3D_volume.npy

    # Vernetzungs-Input (nach 02d) mit gröberer Vorschau
    python3 A02_preview_voxel_volume.py --npy .../volume_boundary_shell_aniso.npy --preview-reduce 2
"""

import argparse
import json
import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from scipy.ndimage import gaussian_filter, rotate  # noqa: E402


def block_reduce_max_fraction(mask, factor):
    """Boxfilter + 50 %-Schwelle, nur für die Vorschau."""
    if factor <= 1:
        return mask
    shape = tuple((dim // factor) * factor for dim in mask.shape)
    cropped = mask[: shape[0], : shape[1], : shape[2]]
    counts = cropped.reshape(
        shape[0] // factor, factor, shape[1] // factor, factor, shape[2] // factor, factor
    ).sum(axis=(1, 3, 5), dtype=np.int32)
    return counts >= (factor ** 3) / 2.0


def depth_render(mask, azim, elev, fog=0.28, light=(-0.45, 0.35, 0.8)):
    """Orthogonale Projektion mit First-Hit-Tiefe und Lambert-Shading."""
    rotated = rotate(mask.astype(np.uint8), azim, axes=(0, 1), order=0, reshape=True, prefilter=False)
    rotated = rotate(rotated, elev, axes=(1, 2), order=0, reshape=True, prefilter=False)
    solid = rotated > 0
    hit = solid.any(axis=1)
    if not hit.any():
        raise ValueError("Keine Materialvoxel im Volumen gefunden — stimmt --material-value?")
    first = np.argmax(solid, axis=1).astype(np.float32)
    far = float(first[hit].max())
    near = float(first[hit].min())
    filled = gaussian_filter(np.where(hit, first, far + 5.0), 0.7)
    grad_x, grad_z = np.gradient(filled)
    normals = np.stack([-grad_x, np.ones_like(grad_x), -grad_z], axis=-1)
    normals /= np.linalg.norm(normals, axis=-1, keepdims=True)
    light_vec = np.asarray(light, dtype=float)
    light_vec /= np.linalg.norm(light_vec)
    lambert = np.clip(normals @ light_vec, 0.0, 1.0)
    depth = np.clip((filled - near) / max(1e-9, far - near), 0.0, 1.0)
    image = (0.30 + 0.70 * lambert ** 0.85) * (1.0 - fog * depth)
    return np.ma.masked_invalid(np.where(hit, image, np.nan)).T[::-1]


def resolve_material_value(args):
    if args.config:
        with open(args.config) as handle:
            config = json.load(handle)
        section = config.get("A01_les_2_npy", {})
        if section.get("phase_convention", "pipeline") == "pipeline":
            return 0
        return int(section.get("les_material_value", 1))
    if args.auto_material_value:
        sidecar = os.path.splitext(args.npy)[0] + ".json"
        if os.path.exists(sidecar):
            with open(sidecar) as handle:
                meta = json.load(handle)
            if "array_material_value" in meta:
                return int(meta["array_material_value"])
    return args.material_value


def main():
    parser = argparse.ArgumentParser(description="Schnitte und 3D-Ansichten eines Voxelvolumens.")
    parser.add_argument("--npy", required=True, help="Pfad zum Voxelvolumen (.npy, uint8)")
    parser.add_argument("--output-dir", default=None, help="Default: Ordner der .npy-Datei")
    parser.add_argument("--prefix", default=None, help="Default: Dateiname ohne Endung")
    parser.add_argument("--material-value", type=int, default=0,
                        help="Arraywert des Aluminiums (Pipeline-Konvention: 0)")
    parser.add_argument("--auto-material-value", action="store_true",
                        help="Wert aus der Sidecar-JSON neben der .npy-Datei lesen")
    parser.add_argument("--config", default=None, help="Projekt-Config, um die Phasenkonvention zu lesen")
    parser.add_argument("--voxel-size-mm", type=float, default=None,
                        help="Voxelkantenlänge in mm für die Achsenbeschriftung")
    parser.add_argument("--metadata", default=None,
                        help="metadata.json, aus der 00_dicom2npy.SliceThickness gelesen wird")
    parser.add_argument("--preview-reduce", type=int, default=1,
                        help="Volumen für die Vorschau zusätzlich gröber machen (Faktor)")
    parser.add_argument("--views", nargs="*", type=float, default=[-40, 22, 55, 18],
                        help="Paare aus Azimut und Elevation in Grad")
    parser.add_argument("--dpi", type=int, default=190)
    args = parser.parse_args()

    volume = np.load(args.npy, mmap_mode="r")
    material_value = resolve_material_value(args)
    mask = np.asarray(volume) == material_value
    print(f"📦 {args.npy}  Shape {mask.shape}  Aluminium = Arraywert {material_value}")
    print(f"📊 relative Dichte: {mask.mean() * 100:.3f} %  (Porosität {100 - mask.mean() * 100:.3f} %)")

    voxel_mm = args.voxel_size_mm
    if voxel_mm is None and args.metadata and os.path.exists(args.metadata):
        with open(args.metadata) as handle:
            meta = json.load(handle)
        entry = meta.get("00_dicom2npy", {})
        thickness = entry.get("SliceThickness")
        if thickness is not None:
            unit = entry.get("SliceThicknessUnit", "mm")
            voxel_mm = float(thickness) * {"m": 1e3, "mm": 1.0, "um": 1e-3}[unit]
    if voxel_mm is None:
        voxel_mm = 1.0
        unit_label = "Voxel"
    else:
        unit_label = "mm"

    preview = block_reduce_max_fraction(mask, args.preview_reduce)
    preview_mm = voxel_mm * max(1, args.preview_reduce)
    extent = np.array(mask.shape) * voxel_mm

    output_dir = args.output_dir or os.path.dirname(os.path.abspath(args.npy))
    prefix = args.prefix or os.path.splitext(os.path.basename(args.npy))[0]
    os.makedirs(output_dir, exist_ok=True)

    # --- Schnitte ---
    mid = [dim // 2 for dim in mask.shape]
    panels = [
        (mask[:, :, mid[2]].T, f"xy-Schnitt, z = {mid[2]}", "x", "y", (0, extent[0], 0, extent[1])),
        (mask[:, mid[1], :].T, f"xz-Schnitt, y = {mid[1]}", "x", "z", (0, extent[0], 0, extent[2])),
        (mask[mid[0], :, :].T, f"yz-Schnitt, x = {mid[0]}", "y", "z", (0, extent[1], 0, extent[2])),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.6), dpi=args.dpi)
    for axis, (image, title, xlabel, ylabel, ext) in zip(axes, panels):
        axis.imshow(image, cmap="gray_r", origin="lower", extent=ext, interpolation="nearest")
        axis.set_title(title, fontsize=10)
        axis.set_xlabel(f"{xlabel} [{unit_label}]")
        axis.set_ylabel(f"{ylabel} [{unit_label}]")
        axis.set_aspect("equal")
    fig.suptitle(f"{prefix} — orthogonale Schnitte (schwarz = Aluminium)", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    slices_path = os.path.join(output_dir, f"{prefix}_slices.png")
    fig.savefig(slices_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"🖼  {slices_path}")

    # --- 3D-Ansichten ---
    views = [(args.views[i], args.views[i + 1]) for i in range(0, len(args.views) - 1, 2)]
    fig, axes = plt.subplots(1, len(views), figsize=(7.5 * len(views), 7), dpi=args.dpi, squeeze=False)
    for axis, (azim, elev) in zip(axes[0], views):
        axis.imshow(depth_render(preview, azim, elev), cmap="bone", vmin=0, vmax=1,
                    interpolation="bilinear")
        axis.set_axis_off()
        axis.set_title(f"Azimut {azim:.0f}°, Elevation {elev:.0f}°", fontsize=10)
    density = preview.mean() * 100
    size_text = (f"{mask.shape[0]}x{mask.shape[1]}x{mask.shape[2]} Voxel"
                 + (f" = {extent[0]:.1f} x {extent[1]:.1f} x {extent[2]:.1f} mm"
                    if unit_label == "mm" else ""))
    fig.suptitle(f"{prefix} — Aluminiumphase\n{size_text}, relative Dichte {density:.2f} % "
                 f"(Vorschau-Voxel {preview_mm:.4f} {unit_label})", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    render_path = os.path.join(output_dir, f"{prefix}_3d.png")
    fig.savefig(render_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"🖼  {render_path}")


if __name__ == "__main__":
    main()
