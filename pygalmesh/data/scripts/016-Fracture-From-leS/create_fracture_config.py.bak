#!/usr/bin/env python3
"""Erzeugt eine Config fuer den Phasenfeld-Bruch aus .leS-Daten (Projekt 016).

Aufbau: das Skript benutzt `create_les_dataset_config.py` aus 015 unveraendert
weiter (gleicher Import, gleiche Argumente) und ergaenzt danach

  1. den Riegel-Ausschnitt in mm  -> A01_les_2_npy.crop.{x,y,z}_range
  2. den `fracture`-Block         -> gelesen von 00_template/script.py
  3. den `mesh_resolution`-Block  -> Stufe coarse/medium/fine
  4. eine Konsistenzpruefung      -> Elementgroesse gegen Phasenfeldlaenge epsilon

und entfernt den `yield_surface`-Block, den dieses Projekt nicht braucht.

Projektregel: Configs werden aus einer bestehenden, validierten Config
abgeleitet. Basis ist `config-A01-les-base.json`, die 1:1-Kopie der in 015
gelaufenen `config-A01-les.json`.

Beispiel:

    python3 create_fracture_config.py \
      --tier coarse --reduce 8 --max-element-size-um 400 \
      --dataset-id JM-25-88_les_fracture_coarse \
      --specimen JM-25-88 \
      --les-input /data/resources/A01_segmented/JM-25-88_78p86.leS \
      --grid 1187 1188 886 --voxel-size 1.67e-05 \
      --bar-y-mm 8 --bar-z-mm 4 \
      --output config-fracture-JM-25-88-coarse.json
"""

import argparse
import json
import math
import sys
from pathlib import Path

import create_les_dataset_config as les

PROJECT_CONTAINER_DIR = "/data/scripts/016-Fracture-From-leS"

# Materialsaetze und Bruchzaehigkeiten aus 012 (config-Bin4-reduce-2-cluster-*).
# E in MPa, Gc in N/mm -> Laengen in mm, Spannungen in MPa.
MATERIAL_SETS = {
    "am": {"E": 73000.0, "nu": 0.36},
    "std": {"E": 70000.0, "nu": 0.35},
    "conv": {"E": 82000.0, "nu": 0.35},
}
FRACTURE_TOUGHNESS_SETS = {
    "original": {"Gc": 1.0, "units": "N/mm"},
    "alsi10mg_as_built": {
        "Gc": 7.2,
        "units": "N/mm",
        "literature_range": [6.0, 8.4],
        "source_doi": "10.1016/j.ijmecsci.2021.106868",
    },
}


def centred_range(n, length_mm, voxel_size_m, reduce_factor):
    """Mittiger Ausschnitt der Laenge `length_mm` im Originalgitter.

    Rueckgabe [start, stop] als Indizes im Originalgitter (vor der Reduktion),
    auf ein Vielfaches von `reduce_factor` gekuerzt, oder None fuer 'ganze Achse'.
    """
    if not length_mm:
        return None
    voxel_mm = voxel_size_m * 1e3
    want = int(round(length_mm / voxel_mm))
    want = max(reduce_factor, (want // reduce_factor) * reduce_factor)
    if want >= n:
        return None
    start = (n - want) // 2
    start -= start % reduce_factor
    return [start, start + want]


def axis_length_mm(rng, n, voxel_size_m):
    count = (rng[1] - rng[0]) if rng else n
    return count * voxel_size_m * 1e3


def build_parser():
    parser = les.build_parser()
    parser.set_defaults(
        base_config="config-A01-les-base.json",
        output="config-fracture.json",
        dataset_id="JM-25-88_les_fracture",
        les_input="/data/resources/A01_segmented/JM-25-88_78p86.leS",
        reduce=8,
        keep_largest_component=True,
    )
    group = parser.add_argument_group("016: Riegel, Bruch und Aufloesungsstufe")
    group.add_argument("--tier", default=None,
                       help="Name der Aufloesungsstufe (coarse/medium/fine); "
                            "landet in mesh_resolution.tier")
    group.add_argument("--specimen", default=None,
                       help="Probenname fuer den Archivpfad der Netze "
                            "(Default: erstes Feld der dataset-id)")
    group.add_argument("--grid", nargs=3, type=int, default=None,
                       metavar=("NX", "NY", "NZ"),
                       help="Gitter der .leS-Datei; noetig fuer den Riegel-Crop in mm. "
                            "Mit A04_les_header_info.py auslesen.")
    group.add_argument("--bar-x-mm", type=float, default=None,
                       help="Laenge des Riegels in x (Risslaufrichtung); leer = ganze Achse")
    group.add_argument("--bar-y-mm", type=float, default=8.0,
                       help="Hoehe des Riegels in y; bestimmt ueber eps_factor epsilon")
    group.add_argument("--bar-z-mm", type=float, default=4.0,
                       help="Dicke des Riegels in z")
    group.add_argument("--fracture-materials", nargs="*", default=["std"])
    group.add_argument("--fracture-directions", nargs="*", default=["y"])
    group.add_argument("--fracture-mesh-file", default="dlfx_mesh")
    group.add_argument("--fracture-toughness-name", default="alsi10mg_as_built")
    group.add_argument("--eps-factor", type=float, default=8.0,
                       help="epsilon = (y_max - y_min) / eps_factor. 011/012 nutzten 20; "
                            "bei groben Netzen muss der Wert kleiner sein, damit epsilon "
                            "vom Netz aufgeloest wird.")
    group.add_argument("--element-order", type=int, default=1)
    group.add_argument("--lam-param", type=float, default=1.0)
    group.add_argument("--mue-param", type=float, default=1.0)
    group.add_argument("--gc-param", type=float, default=1.0)
    group.add_argument("--boundary-shell-elements", type=float, default=3.0,
                       help="Zieldicke der Randschale in Elementen; daraus wird die "
                            "Dicke in Voxeln gerechnet, wenn --boundary-shell-xz/-y fehlen")
    return parser


def main():
    args = build_parser().parse_args()

    # Die Ausgabepfade in der abgeleiteten Config muessen auf 016 zeigen.
    les.PROJECT_CONTAINER_DIR = PROJECT_CONTAINER_DIR

    project_dir = Path(args.project_dir).resolve() if args.project_dir else Path(__file__).resolve().parent

    base_path = Path(args.base_config)
    if not base_path.is_absolute():
        base_path = project_dir / base_path
    with base_path.open() as handle:
        base = json.load(handle)

    voxel_size_m = args.voxel_size if args.voxel_size else 1.67e-05

    # --- 1. Riegel-Ausschnitt --------------------------------------------------
    # A01_les_2_npy.py schneidet im ORIGINALGITTER, also vor der Reduktion.
    if args.grid:
        nx, ny, nz = args.grid
        args.x_range = args.x_range or centred_range(nx, args.bar_x_mm, voxel_size_m, args.reduce)
        args.y_range = args.y_range or centred_range(ny, args.bar_y_mm, voxel_size_m, args.reduce)
        args.z_range = args.z_range or centred_range(nz, args.bar_z_mm, voxel_size_m, args.reduce)
    elif any((args.bar_x_mm, args.bar_y_mm, args.bar_z_mm)) and not any(
            (args.x_range, args.y_range, args.z_range)):
        print(
            "WARNUNG: --grid fehlt, der Riegel-Ausschnitt kann nicht in Indizes "
            "umgerechnet werden. Die Config vernetzt das VOLLE Volumen.\n"
            "         Gitter auslesen mit:\n"
            f"           python3 A04_les_header_info.py {args.les_input} --format shell\n",
            file=sys.stderr,
        )

    # --- 2. Randschale aus der Elementgroesse ableiten -------------------------
    # Die Schale traegt die Dirichlet-Raender der Surfing-BCs. Bei 400 um
    # Elementen und 133,6 um Voxeln sind drei Elemente rund 9 Voxel; die 8/12
    # aus 015 waren auf 75-um-Elemente abgestimmt.
    voxel_um = voxel_size_m * 1e6 * args.reduce
    if args.max_element_size_um and not args.boundary_shell_xz:
        args.boundary_shell_xz = int(math.ceil(
            args.boundary_shell_elements * float(args.max_element_size_um) / voxel_um))
    if args.boundary_shell_xz and not args.boundary_shell_y:
        # y traegt die Zug-/Surfing-Raender und war schon in 015 dicker (12 statt 8).
        args.boundary_shell_y = int(math.ceil(args.boundary_shell_xz * 1.5))

    # --- 3. Basiskonfiguration aus 015 ableiten --------------------------------
    config = les.build_config(base, args)

    # Der Bruchzweig rechnet keine Fliessflaeche.
    config.pop("yield_surface", None)

    specimen = args.specimen or args.dataset_id.split("_")[0]
    config["dataset"]["specimen"] = specimen

    # --- 4. fracture-Block -----------------------------------------------------
    x_len = axis_length_mm(args.x_range, args.grid[0] if args.grid else 0, voxel_size_m)
    y_len = axis_length_mm(args.y_range, args.grid[1] if args.grid else 0, voxel_size_m)
    z_len = axis_length_mm(args.z_range, args.grid[2] if args.grid else 0, voxel_size_m)

    element_um = float(args.max_element_size_um) if args.max_element_size_um else None
    epsilon_mm = (y_len / args.eps_factor) if y_len else None
    elements_per_epsilon = (
        (epsilon_mm * 1000.0) / element_um if (epsilon_mm and element_um) else None
    )

    config["fracture"] = {
        "materials": list(args.fracture_materials),
        "directions": list(args.fracture_directions),
        "mesh_file": args.fracture_mesh_file,
        "lam_param": args.lam_param,
        "mue_param": args.mue_param,
        "Gc_param": args.gc_param,
        "eps_factor_param": args.eps_factor,
        "element_order": args.element_order,
        "default_material": dict(MATERIAL_SETS["std"]),
        "material_sets": {k: dict(v) for k, v in MATERIAL_SETS.items()},
        "fracture_toughness": args.fracture_toughness_name,
        "fracture_toughness_sets": {k: dict(v) for k, v in FRACTURE_TOUGHNESS_SETS.items()},
        "comment": (
            "Gelesen von 00_template/script.py (aus 011). epsilon = (y_max-y_min)/"
            "eps_factor_param wird in pfmfrac_function.py aus der Netz-Bounding-Box "
            "gebildet, nicht aus den Werten hier."
        ),
    }

    # --- 5. Aufloesungsstufe und Konsistenzpruefung ----------------------------
    config["mesh_resolution"] = {
        "tier": args.tier,
        "reduce": args.reduce,
        "voxel_size_um": voxel_um,
        "max_element_size_um": element_um,
        "comment": "Aufloesungsfamilie nach dem Vorbild von 012 (coarse/medium/fine).",
    }
    config["fracture_geometry_check"] = {
        "grid_used": list(args.grid) if args.grid else None,
        "voxel_size_m_used": voxel_size_m,
        "grid_source": (
            "aus --grid uebergeben (Herkunft pruefen: A04_les_header_info.py)"
            if args.grid else "unbekannt - kein Riegel-Crop gesetzt"
        ),
        "bar_extent_mm": {"x": x_len or None, "y": y_len or None, "z": z_len or None},
        "epsilon_mm": epsilon_mm,
        "element_size_um": element_um,
        "elements_per_epsilon": elements_per_epsilon,
        "crack_start_x_fraction": 0.2,
        "boundary_shell_voxels": {
            "xz": args.boundary_shell_xz,
            "y": args.boundary_shell_y,
        },
        "comment": (
            "Richtwerte: mindestens 2 Elemente je epsilon, besser 4. Ist der Wert "
            "kleiner, ist das Bruchergebnis netzabhaengig - dann entweder die "
            "Elemente verfeinern oder eps_factor_param verkleinern (epsilon groesser). "
            "Werte gelten nur, wenn --grid gesetzt war."
        ),
    }

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = project_dir / output_path
    with output_path.open("w") as handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")

    section = config["A01_les_2_npy"]
    pg = config["03_mesh_3D_array"]["sdf_pygalmesh_parameters"]["pygalmesh_parameters"]
    seal = config["02d_axis_aligned_cuboid_crop"]["boundary_seal"]["thicknesses"]
    print(f"Wrote {output_path}")
    print(f"  Stufe / dataset.id : {args.tier} / {config['dataset']['id']}")
    print(f"  Probe (Archivpfad) : {specimen}")
    print(f"  .leS-Eingabe       : {section['input']}")
    print(f"  reduce             : {section['reduce']['factor']} -> Voxel {voxel_um:.1f} um")
    print(f"  Crop (Originalgitter): x={section['crop']['x_range']} "
          f"y={section['crop']['y_range']} z={section['crop']['z_range']}")
    if x_len:
        print(f"  Riegel             : {x_len:.2f} x {y_len:.2f} x {z_len:.2f} mm")
    print(f"  Elementgroesse     : "
          f"{config['03_mesh_3D_array'].get('max_element_size_um', float('nan')):.1f} um "
          f"(Faktor {pg['max_element_size_factor']:.4f} x dx)")
    print(f"  Randschale (Voxel) : x/z = {seal['x_min']}, y = {seal['y_min']}")
    if epsilon_mm:
        print(f"  epsilon            : {epsilon_mm:.3f} mm (Ly / {args.eps_factor:g})")
        print(f"  Elemente je epsilon: {elements_per_epsilon:.2f}"
              + ("   <-- ZU WENIG (< 2)" if elements_per_epsilon < 2.0 else ""))
    print(f"  Gc                 : {args.fracture_toughness_name} = "
          f"{FRACTURE_TOUGHNESS_SETS[args.fracture_toughness_name]['Gc']} N/mm")


if __name__ == "__main__":
    main()
