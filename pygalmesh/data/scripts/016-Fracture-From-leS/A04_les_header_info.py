#!/usr/bin/env python3
"""Liest den Kopf einer .leS-Datei und gibt Gitter und Voxelgroesse aus.

Die erste Zeile einer .leS-Datei enthaelt vier Werte:

    nx ny nz voxel_size

`voxel_size` steht in Metern (JM-25-77: 1.670000e-05 = 16,7 um). Danach folgen
genau nx*ny Zeilen mit je nz Werten (Voxelsaeulen entlang z, Zeilenindex
l = ix*ny + iy, C-Order).

Das Skript liest nur die erste Zeile - es funktioniert also auch bei 2,5-GB-
Dateien in Millisekunden und braucht weder numpy noch scipy. Damit koennen
create_fracture_config.sh und die Jobskripte den Riegel-Ausschnitt in mm
rechnen, ohne das Volumen zu laden.

    python3 A04_les_header_info.py /data/resources/A01_segmented/JM-25_77_85p55.leS
    python3 A04_les_header_info.py <datei> --format shell
    python3 A04_les_header_info.py <ordner>          # genau eine .leS-Datei darin
"""

import argparse
import glob
import json
import os
import sys


def resolve_les_file(target):
    """Datei, Ordner oder Glob -> genau eine .leS-Datei."""
    if os.path.isfile(target):
        return target
    if os.path.isdir(target):
        candidates = sorted(
            glob.glob(os.path.join(target, "*.leS"))
            + glob.glob(os.path.join(target, "*.les"))
        )
    else:
        candidates = sorted(glob.glob(target))
    if not candidates:
        raise SystemExit(f"Keine .leS-Datei gefunden: {target}")
    if len(candidates) > 1:
        names = "\n  ".join(os.path.basename(c) for c in candidates)
        raise SystemExit(
            f"Mehr als eine .leS-Datei unter {target}:\n  {names}\n"
            "Bitte die Datei genau angeben."
        )
    return candidates[0]


def read_header(path):
    with open(path, "r") as handle:
        first_line = handle.readline()
    parts = first_line.split()
    if len(parts) < 4:
        raise SystemExit(
            f"Unerwarteter Header in {path!r}: {first_line!r}\n"
            "Erwartet werden vier Werte: nx ny nz voxel_size"
        )
    nx, ny, nz = (int(float(value)) for value in parts[:3])
    voxel_size = float(parts[3])
    return {
        "path": path,
        "nx": nx,
        "ny": ny,
        "nz": nz,
        "voxels": nx * ny * nz,
        "voxel_size_m": voxel_size,
        "voxel_size_um": voxel_size * 1e6,
        "extent_mm": [nx * voxel_size * 1e3, ny * voxel_size * 1e3, nz * voxel_size * 1e3],
        "header_bytes": len(first_line),
    }


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("input", help="Datei, Ordner oder Glob-Muster")
    parser.add_argument(
        "--format",
        default="text",
        choices=["text", "json", "shell", "grid"],
        help="text = lesbar, json = maschinenlesbar, shell = Variablenzuweisungen "
        "zum eval-en, grid = nur 'nx ny nz voxel_size_m'",
    )
    args = parser.parse_args()

    info = read_header(resolve_les_file(args.input))

    if args.format == "json":
        json.dump(info, sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif args.format == "shell":
        print(f"LES_GRID='{info['nx']} {info['ny']} {info['nz']}'")
        print(f"LES_VOXEL_SIZE_M='{info['voxel_size_m']:.6e}'")
    elif args.format == "grid":
        print(f"{info['nx']} {info['ny']} {info['nz']} {info['voxel_size_m']:.6e}")
    else:
        ex = info["extent_mm"]
        print(f"Datei        : {info['path']}")
        print(f"Gitter       : {info['nx']} x {info['ny']} x {info['nz']} "
              f"= {info['voxels']:,} Voxel".replace(",", " "))
        print(f"Voxelgroesse : {info['voxel_size_um']:.2f} um ({info['voxel_size_m']:.6e} m)")
        print(f"Ausdehnung   : {ex[0]:.2f} x {ex[1]:.2f} x {ex[2]:.2f} mm")


if __name__ == "__main__":
    main()
