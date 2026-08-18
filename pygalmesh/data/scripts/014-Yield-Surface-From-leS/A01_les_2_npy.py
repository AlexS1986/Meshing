#!/usr/bin/env python3
"""
A01_les_2_npy.py — Einstiegspunkt der .leS-Pipeline in 014-Yield-Surface-From-leS.

Konvertiert ein bereits segmentiertes Voxelbild im ASCII-Format `.leS` in
`segmented_3D_volume.npy` und ersetzt damit die DICOM-Schritte
`00_dicom_2_npy.py`, `01_segment_slice_wise.py`, `02_build3D_segmented_array.py`
und `02a_rotate_pic_to_align_with_axis.py`. Alle folgenden Schritte
(`02b`, `02c`, `02d`, `03`, …) laufen unverändert weiter.

.leS-Format
-----------
Zeile 1 (Header):   nx ny nz voxel_size     z.B. "1187 1188 886 1.670000e-05"
                    (voxel_size in Metern, isotrop)
Zeile 2 ... nx*ny+1: je Zeile nz Labelwerte, durch Leerzeichen getrennt.
                    Jede Zeile ist eine Voxelsäule entlang z,
                    Zeilenindex l = ix*ny + iy (C-Order, per --line-order umschaltbar).
                    In der Quelldatei gilt: 1 = Material (Aluminium), 0 = void.

⚠ Phasenkonvention der Pipeline
-------------------------------
Im Repository gilt in allen Arrays **vor** Schritt 03: **1 = Pore, 0 = Aluminium**
(siehe PIPELINE_ANNAHMEN_DICOM_TO_FEM.md, Abschnitte 3 und 9.1). Schritt 03
wendet ein zweites `invert_contrast()` an, erst danach ist `material_mask == 1`
das Aluminium; auch die Randschale aus 02d (Wert 0) ist darauf abgestimmt.

Dieses Skript **invertiert deshalb per Default** die Labels der .leS-Datei
(`phase_convention = "pipeline"`): Aluminium wird zu 0, Pore zu 1.
Mit `--phase-convention raw` bleiben die Labels der Quelldatei erhalten —
das ist dann *nicht* kompatibel mit 02d/03.

Auflösung reduzieren
--------------------
`--reduce N` fasst N×N×N Voxel zu einem zusammen. Der Blockwert wird auf der
**Aluminiumphase** bestimmt:

    majority   Block wird Aluminium, wenn ≥ threshold (Default 0.5) der
               Untervoxel Aluminium sind  (Boxfilter + Schwelle)
    threshold  wie majority, aber mit explizitem --reduce-threshold
    any        Block wird Aluminium, sobald ein Untervoxel Aluminium ist
    all        Block wird Aluminium, nur wenn alle Untervoxel Aluminium sind

Optional `--smooth-sigma S` (Default 0 = aus): Gauß-Glättung des
Belegungsanteils **im reduzierten Gitter** vor dem Schwellwert. Für reduce ≤ 2
in der Regel unnötig — die eigentliche Oberflächenglättung passiert in Schritt 03
über `sdf_sigma_voxels`.

Speicher
--------
Streaming über np.lib.format.open_memmap: der RAM-Bedarf ist unabhängig von der
Volumengröße (Standard-Lesepuffer 64 MB).

Aufrufe
-------
    # Cluster/Container, gesteuert über die Projekt-Config
    python3 A01_les_2_npy.py --config /data/scripts/014-Yield-Surface-From-leS/config-A01-les.json

    # frei, ohne Config
    python3 A01_les_2_npy.py --input /data/resources/A01_segmented \
        --output /tmp/volume.npy --reduce 4 --x-range 300 700
"""

import argparse
import glob
import json
import math
import os
import sys
import time

import numpy as np

PROJECT_CONTAINER_DIR = "/data/scripts/014-Yield-Surface-From-leS"
CONFIG_SECTION = "A01_les_2_npy"
DEFAULT_OUTPUT_FILENAME = "segmented_3D_volume.npy"

# Reihenfolge, in der ohne --input/--config nach der .leS-Datei gesucht wird.
DEFAULT_INPUT_CANDIDATES = (
    "/data/resources/A01_segmented",
    f"{PROJECT_CONTAINER_DIR}/A01_segmented",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "A01_segmented"),
)


# --------------------------------------------------------------------------- #
# Eingabe auflösen
# --------------------------------------------------------------------------- #
def resolve_input(spec):
    """Akzeptiert Datei, Ordner oder Glob und liefert genau eine .leS-Datei."""
    candidates = [spec] if spec else list(DEFAULT_INPUT_CANDIDATES)
    tried = []
    for candidate in candidates:
        tried.append(candidate)
        if os.path.isfile(candidate):
            return candidate
        if os.path.isdir(candidate):
            matches = sorted(
                glob.glob(os.path.join(candidate, "*.leS"))
                + glob.glob(os.path.join(candidate, "*.les"))
                + glob.glob(os.path.join(candidate, "*.LES"))
            )
        elif any(char in candidate for char in "*?["):
            matches = sorted(glob.glob(candidate))
        else:
            continue
        matches = [m for m in matches if os.path.isfile(m)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(
                f"Mehrere .leS-Dateien unter {candidate!r} gefunden — bitte die Datei "
                f"explizit angeben:\n  " + "\n  ".join(matches)
            )
    raise FileNotFoundError(
        "Keine .leS-Datei gefunden. Gesucht wurde in:\n  " + "\n  ".join(tried)
    )


# --------------------------------------------------------------------------- #
# Header / Layout
# --------------------------------------------------------------------------- #
def read_header(path):
    """Liest die erste Zeile: (nx, ny, nz, voxel_size, header_bytes)."""
    with open(path, "rb") as handle:
        first = handle.readline()
    if not first:
        raise ValueError(f"Datei ist leer: {path}")
    parts = first.split()
    if len(parts) < 3:
        raise ValueError(f"Unerwarteter Header (erwartet 'nx ny nz [voxel_size]'): {first[:120]!r}")
    nx, ny, nz = (int(p) for p in parts[:3])
    voxel_size = float(parts[3]) if len(parts) > 3 else None
    return nx, ny, nz, voxel_size, len(first)


def probe_fixed_width(path, header_bytes, nz, n_lines):
    """Bytes pro Datenzeile, falls alle Zeilen gleich lang sind (einstellige Labels)."""
    file_size = os.path.getsize(path)
    data_bytes = file_size - header_bytes
    if n_lines <= 0 or data_bytes % n_lines != 0:
        return None
    bytes_per_line = data_bytes // n_lines
    if bytes_per_line not in (2 * nz, 2 * nz + 1):
        return None
    with open(path, "rb") as handle:
        handle.seek(header_bytes)
        line = handle.read(bytes_per_line)
    if not line.endswith(b"\n"):
        return None
    values = line.split()
    if len(values) != nz or any(len(v) != 1 for v in values):
        return None
    return bytes_per_line


# --------------------------------------------------------------------------- #
# Parser (liefern Blöcke von Zeilen als (n_lines, nz_crop) uint8)
# --------------------------------------------------------------------------- #
def parse_fast(handle, header_bytes, bytes_per_line, nz, line_start, n_lines, z_slice, chunk_mb=64.0):
    handle.seek(header_bytes + line_start * bytes_per_line)
    block = max(1, int(chunk_mb * 1024 * 1024) // bytes_per_line)
    remaining = n_lines
    while remaining > 0:
        take = min(block, remaining)
        raw = handle.read(take * bytes_per_line)
        if len(raw) != take * bytes_per_line:
            raise ValueError("Datei endet früher als vom Header angekündigt.")
        arr = np.frombuffer(raw, dtype=np.uint8).reshape(take, bytes_per_line)
        values = arr[:, 0 : 2 * nz : 2] - np.uint8(48)  # ASCII-Ziffer -> Zahl
        yield values[:, z_slice]
        remaining -= take


def parse_generic(handle, header_bytes, nz, line_start, n_lines, z_slice, lines_per_block=4096):
    handle.seek(header_bytes)
    for _ in range(line_start):
        if not handle.readline():
            raise ValueError("Datei endet früher als vom Header angekündigt.")
    remaining = n_lines
    while remaining > 0:
        take = min(lines_per_block, remaining)
        rows = []
        for _ in range(take):
            line = handle.readline()
            if not line:
                raise ValueError("Datei endet früher als vom Header angekündigt.")
            row = np.array(line.split(), dtype=np.uint8)
            if row.size != nz:
                raise ValueError(f"Zeile hat {row.size} Werte, erwartet {nz}.")
            rows.append(row[z_slice])
        yield np.asarray(rows, dtype=np.uint8)
        remaining -= take


# --------------------------------------------------------------------------- #
# Blockbildung
# --------------------------------------------------------------------------- #
def outer_row_cubes(blocks, inner_len, inner_lo, inner_hi):
    """Wandelt Zeilenblöcke in Quader (n_outer, y_crop, z_crop)."""
    carry = None
    for block in blocks:
        if carry is not None:
            block = np.concatenate([carry, block], axis=0)
            carry = None
        n_full = block.shape[0] // inner_len
        if n_full == 0:
            carry = block
            continue
        rest = block.shape[0] - n_full * inner_len
        if rest:
            carry = block[n_full * inner_len :]
            block = block[: n_full * inner_len]
        yield block.reshape(n_full, inner_len, -1)[:, inner_lo:inner_hi, :]
    if carry is not None and carry.size:
        raise ValueError("Unvollständiger Zeilenblock am Dateiende.")


def grouped_cubes(cubes, group):
    """Bündelt Quader zu Vielfachen von `group` äußeren Zeilen."""
    buffer = []
    rows = 0
    for cube in cubes:
        buffer.append(cube)
        rows += cube.shape[0]
        if rows < group:
            continue
        merged = np.concatenate(buffer, axis=0) if len(buffer) > 1 else buffer[0]
        keep = (merged.shape[0] // group) * group
        if keep:
            yield merged[:keep]
        rest = merged[keep:]
        buffer = [rest] if rest.shape[0] else []
        rows = rest.shape[0]
    if rows:
        raise ValueError("Unvollständige Blockgruppe am Dateiende (Crop nicht durch reduce teilbar?).")


def reduce_block(material, factor, mode, threshold):
    """
    material: bool-Array (k*factor, Y*factor, Z*factor)
    Rückgabe: (reduziertes bool-Array, Belegungsanteil float32) — der Anteil wird
    nur für --smooth-sigma gebraucht.
    """
    if factor == 1:
        return material, None
    k = material.shape[0] // factor
    y = material.shape[1] // factor
    z = material.shape[2] // factor
    counts = material.reshape(k, factor, y, factor, z, factor).sum(axis=(1, 3, 5), dtype=np.int32)
    total = factor ** 3
    fraction = counts.astype(np.float32) / total
    if mode == "any":
        reduced = counts >= 1
    elif mode == "all":
        reduced = counts >= total
    else:  # majority / threshold
        needed = max(1, int(math.ceil(threshold * total - 1e-9)))
        reduced = counts >= needed
    return reduced, fraction


# --------------------------------------------------------------------------- #
# Konvertierung
# --------------------------------------------------------------------------- #
def convert(args):
    input_path = resolve_input(args.input)
    nx, ny, nz, header_voxel_size, header_bytes = read_header(input_path)
    n_lines_total = nx * ny

    voxel_size = args.voxel_size if args.voxel_size is not None else header_voxel_size
    if voxel_size is None:
        raise ValueError("Keine Voxelgröße im Header — bitte --voxel-size angeben.")

    reduce_factor = max(1, int(args.reduce))
    x0, x1 = args.x_range if args.x_range else (0, nx)
    y0, y1 = args.y_range if args.y_range else (0, ny)
    z0, z1 = args.z_range if args.z_range else (0, nz)
    for name, (lo, hi), full in (("x", (x0, x1), nx), ("y", (y0, y1), ny), ("z", (z0, z1), nz)):
        if not (0 <= lo < hi <= full):
            raise ValueError(f"Ungültiger --{name}-range {lo} {hi} (gültig: 0 .. {full}).")

    # Auf Vielfache des Reduktionsfaktors kürzen (Rest am oberen Ende verwerfen)
    dropped = {}
    for name, lo, hi in (("x", x0, x1), ("y", y0, y1), ("z", z0, z1)):
        rest = (hi - lo) % reduce_factor
        if rest:
            dropped[name] = rest
    x1 -= (x1 - x0) % reduce_factor
    y1 -= (y1 - y0) % reduce_factor
    z1 -= (z1 - z0) % reduce_factor
    if min(x1 - x0, y1 - y0, z1 - z0) <= 0:
        raise ValueError("Ausschnitt ist kleiner als der Reduktionsfaktor.")

    src_shape = (x1 - x0, y1 - y0, z1 - z0)
    out_shape = tuple(dim // reduce_factor for dim in src_shape)
    n_voxels_src = int(np.prod(src_shape))
    n_voxels_out = int(np.prod(out_shape))
    out_voxel_size = voxel_size * reduce_factor

    if args.phase_convention == "pipeline":
        material_out, pore_out = 0, 1
    else:
        material_out, pore_out = 1, 0

    print(f"📥 Eingabe : {input_path}")
    print(f"📐 Header  : nx={nx} ny={ny} nz={nz}  voxel_size={voxel_size:.6e} m ({voxel_size * 1e6:.3f} µm)")
    print(f"✂️  Ausschnitt: x[{x0}:{x1}] y[{y0}:{y1}] z[{z0}:{z1}] = {src_shape}"
          + (f"  (verworfener Rest: {dropped})" if dropped else ""))
    print(f"🔻 Reduktion: Faktor {reduce_factor} ({args.reduce_mode}"
          + (f", Schwelle {args.reduce_threshold}" if args.reduce_mode in ("majority", "threshold") else "")
          + (f", smooth_sigma {args.smooth_sigma}" if args.smooth_sigma > 0 else "")
          + f") -> Shape {out_shape} ({n_voxels_out / 1e6:.1f} MVoxel, "
            f"{n_voxels_out / 1e9:.3f} GB als uint8)")
    print(f"📏 Voxelgröße nach Reduktion: {out_voxel_size:.6e} m ({out_voxel_size * 1e6:.3f} µm, "
          f"{out_voxel_size * 1e3:.6f} mm)")
    print(f"🔢 Zeilenordnung: {args.line_order}-Order "
          f"({'l = ix*ny + iy' if args.line_order == 'C' else 'l = iy*nx + ix'})")
    print(f"🧪 Phasenkonvention: {args.phase_convention} -> Aluminium = {material_out}, Pore = {pore_out}"
          + ("  (Pipeline-Konvention, kompatibel mit 02d/03)" if args.phase_convention == "pipeline"
             else "  ⚠ Rohkonvention — NICHT kompatibel mit 02d/03"))

    bytes_per_line = probe_fixed_width(input_path, header_bytes, nz, n_lines_total)
    if args.force_generic:
        bytes_per_line = None
    print(f"⚙️  Parser  : {'fast (feste Zeilenbreite)' if bytes_per_line else 'generic (split, langsam)'}")

    if args.dry_run:
        print("🛑 --dry-run: es wird nichts geschrieben.")
        return None

    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    volume = np.lib.format.open_memmap(output_path, mode="w+", dtype=np.uint8, shape=out_shape)

    fraction_path = None
    fraction_map = None
    if args.smooth_sigma > 0.0 and reduce_factor > 1:
        fraction_path = os.path.splitext(output_path)[0] + ".fraction.tmp.npy"
        fraction_map = np.lib.format.open_memmap(
            fraction_path, mode="w+", dtype=np.float32, shape=out_shape
        )

    z_slice = slice(z0, z1)
    if args.line_order == "C":
        outer_lo, outer_hi, inner_len, inner_lo, inner_hi = x0, x1, ny, y0, y1
        target = volume
        target_fraction = fraction_map
    else:
        outer_lo, outer_hi, inner_len, inner_lo, inner_hi = y0, y1, nx, x0, x1
        target = volume.transpose(1, 0, 2)
        target_fraction = None if fraction_map is None else fraction_map.transpose(1, 0, 2)

    raw_counts = np.zeros(256, dtype=np.int64)
    any_axis0 = np.zeros(out_shape[0] if args.line_order == "C" else out_shape[1], dtype=bool)
    any_axis1 = np.zeros(out_shape[1] if args.line_order == "C" else out_shape[0], dtype=bool)
    any_axis2 = np.zeros(out_shape[2], dtype=bool)

    t_start = time.time()
    written = 0
    out_row = 0
    with open(input_path, "rb") as handle:
        line_start = outer_lo * inner_len
        n_lines = (outer_hi - outer_lo) * inner_len
        if bytes_per_line:
            blocks = parse_fast(handle, header_bytes, bytes_per_line, nz, line_start,
                                n_lines, z_slice, chunk_mb=args.chunk_mb)
        else:
            blocks = parse_generic(handle, header_bytes, nz, line_start, n_lines, z_slice,
                                   lines_per_block=args.lines_per_block)
        cubes = outer_row_cubes(blocks, inner_len, inner_lo, inner_hi)
        for cube in grouped_cubes(cubes, reduce_factor):
            raw_counts += np.bincount(cube.reshape(-1), minlength=256)
            material = cube == args.les_material_value
            reduced, fraction = reduce_block(material, reduce_factor, args.reduce_mode,
                                             args.reduce_threshold)
            k = reduced.shape[0]
            if target_fraction is not None:
                target_fraction[out_row : out_row + k] = fraction
            values = np.where(reduced, np.uint8(material_out), np.uint8(pore_out))
            target[out_row : out_row + k] = values
            any_axis0[out_row : out_row + k] |= reduced.any(axis=(1, 2))
            any_axis1 |= reduced.any(axis=(0, 2))
            any_axis2 |= reduced.any(axis=(0, 1))
            out_row += k
            written += int(np.prod(cube.shape))
            frac = written / max(1, n_voxels_src)
            elapsed = time.time() - t_start
            print(f"   … {frac * 100:5.1f} %  ({written / 1e6:8.1f} MVoxel gelesen, "
                  f"{elapsed:6.1f} s, ETA {elapsed / max(frac, 1e-9) - elapsed:6.1f} s)", flush=True)

    # Optionale Glättung des Belegungsanteils im reduzierten Gitter
    smoothing_applied = False
    if fraction_map is not None:
        from scipy import ndimage as ndi  # nur bei Bedarf

        print(f"🌫  Gauß-Glättung des Belegungsanteils, sigma = {args.smooth_sigma} (reduzierte Voxel)")
        smoothed = ndi.gaussian_filter(np.asarray(fraction_map), sigma=args.smooth_sigma,
                                       output=np.float32)
        reduced = smoothed >= args.reduce_threshold
        np.copyto(np.asarray(volume), np.where(reduced, np.uint8(material_out), np.uint8(pore_out)))
        # `reduced` liegt in (x, y, z) — unabhängig von der Zeilenordnung.
        smoothed_any = (reduced.any(axis=(1, 2)), reduced.any(axis=(0, 2)), reduced.any(axis=(0, 1)))
        smoothing_applied = True
        del smoothed, fraction_map
        os.remove(fraction_path)

    volume.flush()
    elapsed = time.time() - t_start

    if args.line_order == "F":
        any_x, any_y = any_axis1, any_axis0
    else:
        any_x, any_y = any_axis0, any_axis1
    if smoothing_applied:
        any_x, any_y, any_axis2 = smoothed_any

    def bounds_of(flags, length):
        indices = np.flatnonzero(flags)
        if indices.size == 0:
            return None
        return [int(indices[0]), int(indices[-1])]

    material_bbox = {
        "x": bounds_of(any_x, out_shape[0]),
        "y": bounds_of(any_y, out_shape[1]),
        "z": bounds_of(any_axis2, out_shape[2]),
    }
    full_bounds = {
        "x": [0, out_shape[0] - 1],
        "y": [0, out_shape[1] - 1],
        "z": [0, out_shape[2] - 1],
    }
    if args.bounds_mode == "material":
        if any(value is None for value in material_bbox.values()):
            raise ValueError("Kein Aluminium im Ausschnitt gefunden — bounds_mode 'material' unmöglich.")
        used_bounds = material_bbox
    else:
        used_bounds = full_bounds

    raw_label_counts = {int(v): int(c) for v, c in enumerate(raw_counts) if c}
    material_raw = raw_label_counts.get(args.les_material_value, 0)
    fraction_raw = material_raw / n_voxels_src if n_voxels_src else float("nan")
    material_out_count = int(np.count_nonzero(np.asarray(volume) == material_out))
    fraction_out = material_out_count / n_voxels_out if n_voxels_out else float("nan")

    print(f"✅ Geschrieben: {output_path}  Shape {out_shape}  dtype uint8  ({elapsed:.1f} s)")
    print(f"📊 Aluminium vor Reduktion : {fraction_raw * 100:.3f} %  (Porosität {100 - fraction_raw * 100:.3f} %)")
    print(f"📊 Aluminium nach Reduktion: {fraction_out * 100:.3f} %  (Porosität {100 - fraction_out * 100:.3f} %)")
    if reduce_factor > 1:
        delta = (fraction_out - fraction_raw) * 100
        print(f"📊 Änderung der relativen Dichte durch die Reduktion: {delta:+.3f} Prozentpunkte")
    print(f"📦 Bounding-Box des Aluminiums (reduziertes Gitter): {material_bbox}")

    metadata = {
        "source_file": os.path.abspath(input_path),
        "output_file": output_path,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "les_header": {"nx": nx, "ny": ny, "nz": nz, "voxel_size": header_voxel_size},
        "line_order": args.line_order,
        "axis_order": "x, y, z",
        "crop": {"x_range": [x0, x1], "y_range": [y0, y1], "z_range": [z0, z1],
                 "dropped_for_reduce": dropped},
        "reduce": {
            "factor": reduce_factor,
            "mode": args.reduce_mode,
            "threshold": args.reduce_threshold,
            "smooth_sigma": args.smooth_sigma,
            "smoothing_applied": smoothing_applied,
        },
        "source_shape": list(src_shape),
        "output_shape": list(out_shape),
        "dtype": "uint8",
        "phase_convention": args.phase_convention,
        "les_material_value": args.les_material_value,
        "array_material_value": material_out,
        "array_pore_value": pore_out,
        "voxel_size_source_m": voxel_size,
        "voxel_size_m": out_voxel_size,
        "voxel_size_mm": out_voxel_size * 1e3,
        "voxel_size_um": out_voxel_size * 1e6,
        "raw_label_counts": raw_label_counts,
        "material_volume_fraction_source": fraction_raw,
        "material_volume_fraction_output": fraction_out,
        "porosity_output": 1.0 - fraction_out,
        "material_bounds_material": material_bbox,
        "material_bounds_full": full_bounds,
        "bounds_mode": args.bounds_mode,
        "runtime_seconds": elapsed,
    }
    sidecar_path = args.metadata or (os.path.splitext(output_path)[0] + ".json")
    with open(sidecar_path, "w") as handle:
        json.dump(metadata, handle, indent=2)
    print(f"🧾 Sidecar-Metadaten: {sidecar_path}")

    if args.pipeline_metadata:
        write_pipeline_metadata(args, metadata, out_voxel_size, out_shape, used_bounds, reduce_factor)
    return metadata


def write_pipeline_metadata(args, metadata, out_voxel_size, out_shape, used_bounds, reduce_factor):
    """
    Schreibt die Einträge, die die nachfolgenden Pipeline-Schritte erwarten:

    * 00_dicom2npy.SliceThickness              -> von 03_mesh_3D_array gelesen
    * 02a_rotate_pic_to_align_with_axis.py     -> von 02b gelesen
      (input_path, material_value, material_bounds)
    """
    scale = {"m": 1.0, "mm": 1e3, "um": 1e6}[args.pipeline_unit]
    path = args.pipeline_metadata
    payload = {}
    if os.path.exists(path):
        with open(path) as handle:
            payload = json.load(handle)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)

    payload["00_dicom2npy"] = {
        "source": "A01_les_2_npy.py",
        "NumberOfSlices": int(out_shape[2]),
        "ReductionFactor": reduce_factor if reduce_factor > 1 else None,
        "SliceThickness": out_voxel_size * scale,
        "PixelSpacing": [out_voxel_size * scale, out_voxel_size * scale],
        "SliceThicknessUnit": args.pipeline_unit,
    }
    payload["A01_les_2_npy"] = metadata
    # 02b liest genau diesen Schlüssel; A01 ersetzt den Rotationsschritt.
    payload["02a_rotate_pic_to_align_with_axis.py"] = {
        "timestamp": metadata["created"],
        "input_path": metadata["output_file"],
        "written_by": "A01_les_2_npy.py (no rotation applied)",
        "angles_deg": [0.0, 0.0, 0.0],
        "material_value": args.metadata_material_value,
        "pore_value": 1 - args.metadata_material_value,
        "final_shape": list(out_shape),
        "material_bounds": used_bounds,
        "bounds_mode": args.bounds_mode,
    }
    with open(path, "w") as handle:
        json.dump(payload, handle, indent=2)
    print(f"🧾 Pipeline-Metadaten: {path}  "
          f"(SliceThickness = {out_voxel_size * scale:.8g} {args.pipeline_unit}, "
          f"material_bounds aus '{args.bounds_mode}')")


# --------------------------------------------------------------------------- #
# Config / CLI
# --------------------------------------------------------------------------- #
def apply_config(args, config_path):
    """Werte aus der Projekt-Config übernehmen; explizite CLI-Argumente gewinnen."""
    with open(config_path) as handle:
        config = json.load(handle)
    section = config.get(CONFIG_SECTION, {})
    if not section:
        raise ValueError(f"Config {config_path} enthält keinen Abschnitt '{CONFIG_SECTION}'.")

    given = set()
    for token in sys.argv[1:]:
        if token.startswith("--"):
            given.add(token.split("=", 1)[0].lstrip("-").replace("-", "_"))

    def take(name, value):
        if value is not None and name not in given:
            setattr(args, name, value)

    take("input", section.get("input"))
    output_folder = section.get("output_folder")
    if output_folder and "output" not in given:
        args.output = os.path.join(output_folder, section.get("output_filename",
                                                              DEFAULT_OUTPUT_FILENAME))
    take("line_order", section.get("line_order"))
    take("les_material_value", section.get("les_material_value"))
    take("phase_convention", section.get("phase_convention"))
    take("bounds_mode", section.get("bounds_mode"))
    take("voxel_size", section.get("voxel_size"))
    take("pipeline_unit", section.get("voxel_size_unit"))

    crop = section.get("crop", {}) or {}
    for axis in ("x", "y", "z"):
        value = crop.get(f"{axis}_range")
        if value and f"{axis}_range" not in given:
            setattr(args, f"{axis}_range", [int(value[0]), int(value[1])])

    reduce_cfg = section.get("reduce", {}) or {}
    take("reduce", reduce_cfg.get("factor"))
    take("reduce_mode", reduce_cfg.get("mode"))
    take("reduce_threshold", reduce_cfg.get("threshold"))
    take("smooth_sigma", reduce_cfg.get("smooth_sigma"))

    if "pipeline_metadata" not in given:
        args.pipeline_metadata = section.get("metadata_output_path",
                                             config.get("metadata_output_path"))
    if "metadata_material_value" not in given:
        args.metadata_material_value = int(
            config.get("02a_rotate_pic_to_align_with_axis", {}).get("material_value", 1)
        )
    return args


def build_parser():
    parser = argparse.ArgumentParser(
        description="Konvertiert ein segmentiertes .leS-Voxelbild in ein uint8-.npy-Volumen (x, y, z).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", default=None,
                        help=f"Projekt-Config; nutzt den Abschnitt '{CONFIG_SECTION}'")
    parser.add_argument("--input", default=None,
                        help="Datei, Ordner oder Glob mit der .leS-Datei "
                             f"(Default-Suche: {', '.join(DEFAULT_INPUT_CANDIDATES)})")
    parser.add_argument("--output", default=None, help="Ausgabe-.npy (Default: <input-Ordner>/volume.npy)")
    parser.add_argument("--metadata", default=None, help="Sidecar-JSON (Default: wie --output mit .json)")
    parser.add_argument("--pipeline-metadata", default=None,
                        help="metadata.json der Pipeline (SliceThickness + 02a-Eintrag für 02b)")
    parser.add_argument("--pipeline-unit", default="mm", choices=["m", "mm", "um"],
                        help="Einheit für SliceThickness in der Pipeline-Metadatendatei")
    parser.add_argument("--metadata-material-value", type=int, default=1,
                        help="Wert, der im 02a-Metadateneintrag als material_value steht "
                             "(02b prüft damit, ob ein Subvolumen belegt ist)")
    parser.add_argument("--x-range", nargs=2, type=int, metavar=("X0", "X1"), default=None)
    parser.add_argument("--y-range", nargs=2, type=int, metavar=("Y0", "Y1"), default=None)
    parser.add_argument("--z-range", nargs=2, type=int, metavar=("Z0", "Z1"), default=None)
    parser.add_argument("--reduce", type=int, default=1,
                        help="Kantenlänge der zusammengefassten Voxelblöcke (1 = keine Reduktion)")
    parser.add_argument("--reduce-mode", default="majority",
                        choices=["majority", "threshold", "any", "all"])
    parser.add_argument("--reduce-threshold", type=float, default=0.5,
                        help="Aluminium-Anteil, ab dem ein Block Aluminium wird")
    parser.add_argument("--smooth-sigma", type=float, default=0.0,
                        help="Gauß-Sigma (in reduzierten Voxeln) auf dem Belegungsanteil, 0 = aus")
    parser.add_argument("--line-order", choices=["C", "F"], default="C",
                        help="Zeilenindex -> (ix, iy): C = ix*ny+iy, F = iy*nx+ix")
    parser.add_argument("--les-material-value", type=int, default=1,
                        help="Labelwert des Aluminiums in der .leS-Datei")
    parser.add_argument("--phase-convention", default="pipeline", choices=["pipeline", "raw"],
                        help="pipeline: Aluminium=0/Pore=1 (Repo-Konvention); raw: Labels unverändert")
    parser.add_argument("--bounds-mode", default="full", choices=["full", "material"],
                        help="material_bounds für 02b: ganzes Array oder Bounding-Box des Aluminiums")
    parser.add_argument("--voxel-size", type=float, default=None,
                        help="Voxelgröße in m überschreiben (sonst aus dem Header)")
    parser.add_argument("--chunk-mb", type=float, default=64.0, help="Lesepuffer in MB (Fast-Path)")
    parser.add_argument("--lines-per-block", type=int, default=4096,
                        help="Zeilen pro Block im generischen Parser")
    parser.add_argument("--force-generic", action="store_true", help="Fast-Path deaktivieren")
    parser.add_argument("--dry-run", action="store_true", help="Nur Header/Layout prüfen")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.config:
        apply_config(args, args.config)
    if args.output is None:
        resolved = resolve_input(args.input)
        args.output = os.path.join(os.path.dirname(os.path.abspath(resolved)), "volume.npy")
    convert(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
