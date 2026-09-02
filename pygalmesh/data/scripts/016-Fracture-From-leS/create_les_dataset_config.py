#!/usr/bin/env python3
"""Erzeugt eine 010-Config für die .leS-Pipeline aus einer bestehenden, validierten Config.

Die Config wird aus einer bestehenden, validierten Config abgeleitet (in 014 aus
`config-A01-les.json` selbst), damit Vernetzungs-, Randschalen- und
Fließflächen-Parameter erhalten bleiben und nur die bewusst geänderten Werte
abweichen.

Beispiel (Cluster-Pfade, HPC_SCRATCH wird automatisch auf /data abgebildet):

    python3 create_les_dataset_config.py \
      --base-config config-Bin4-reduce-2.json \
      --output config-A01-les.json \
      --dataset-id JM-25-77_A01_les \
      --les-input "$HPC_SCRATCH/pygalmesh/data/resources/A01_segmented" \
      --reduce 2

Einzelne Werte lassen sich überschreiben:

    --set '02b_build_subvolume_arrays.xy_divisions=2' \
    --set '02d_axis_aligned_cuboid_crop.boundary_seal.thickness=2'
"""

import argparse
import copy
import json
import os
from pathlib import Path

PROJECT_CONTAINER_DIR = "/data/scripts/015-Yield-Surface-Batch-leS"


def container_path(value):
    """Host-Pfad unter $HPC_SCRATCH/pygalmesh/data -> Container-Pfad /data/..."""
    path = str(value).rstrip("/")
    if path == "/data" or path.startswith("/data/"):
        return path
    scratch = os.environ.get("HPC_SCRATCH") or os.environ.get("HPC_Scratch")
    if scratch:
        data_root = str(Path(scratch) / "pygalmesh" / "data")
        if path == data_root or path.startswith(data_root + "/"):
            return "/data" + path[len(data_root):]
    marker = "/pygalmesh/data/"
    if marker in path:
        return "/data/" + path.split(marker, 1)[1]
    raise ValueError(
        f"{value!r} liegt nicht unter /data oder $HPC_SCRATCH/pygalmesh/data. "
        "Bitte einen Container-Pfad (/data/...) oder einen Host-Pfad unter "
        "$HPC_SCRATCH/pygalmesh/data angeben."
    )


def parse_json_value(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def set_dotted(config, assignment):
    if "=" not in assignment:
        raise ValueError(f"Ungültiges --set {assignment!r}; erwartet dotted.path=JSON_VALUE")
    dotted_key, raw_value = assignment.split("=", 1)
    keys = [key for key in dotted_key.split(".") if key]
    target = config
    for key in keys[:-1]:
        child = target.setdefault(key, {})
        if not isinstance(child, dict):
            raise ValueError(f"Kann nicht in {key!r} absteigen (kein Objekt)")
        target = child
    target[keys[-1]] = parse_json_value(raw_value)


def build_config(base, args):
    config = copy.deepcopy(base)
    run_name = args.dataset_id
    les_input = container_path(args.les_input)
    output_base = f"{PROJECT_CONTAINER_DIR}/{run_name}_segmented"
    volume_folder = f"{output_base}/{run_name}_segmented_3D"
    label = args.binning_label or f"leS-reduce-{args.reduce}"

    config["dataset"] = {"id": run_name, "resource_folder": les_input}
    config["metadata_output_path"] = f"{output_base}/metadata.json"

    # Auflösungsinformation; `binning.label` wird von den Yield-Jobs für die
    # Ergebnisordner gelesen und muss deshalb gesetzt bleiben.
    config["binning"] = {
        "id": args.reduce,
        "label": label,
        "resource_folder": les_input,
        "script_reduce_factor": args.reduce if args.reduce > 1 else None,
        "effective_binning_factor": args.reduce,
        "source": "les",
    }

    config["A01_les_2_npy"] = {
        "enabled": True,
        "input": les_input,
        "output_folder": volume_folder,
        "output_filename": "segmented_3D_volume.npy",
        "line_order": args.line_order,
        "les_material_value": args.les_material_value,
        "phase_convention": "pipeline",
        "bounds_mode": args.bounds_mode,
        "voxel_size": args.voxel_size,
        "voxel_size_unit": args.voxel_size_unit,
        "crop": {
            "x_range": args.x_range,
            "y_range": args.y_range,
            "z_range": args.z_range,
        },
        "reduce": {
            "factor": args.reduce,
            "mode": args.reduce_mode,
            "threshold": args.reduce_threshold,
            "smooth_sigma": args.smooth_sigma,
        },
        "comment": (
            "Ersetzt 00_dicom_2_npy, 01_segment_slice_wise, 02_build3D_segmented_array "
            "und 02a_rotate_pic_to_align_with_axis. Schreibt segmented_3D_volume.npy in "
            "der Pipeline-Phasenkonvention (0 = Aluminium, 1 = Pore) sowie die von 02b "
            "benoetigten Metadaten."
        ),
    }

    # Die DICOM-Abschnitte gibt es in 014 nicht mehr. Zwei Reste bleiben, weil sie
    # von anderen Skripten gelesen werden:
    #   01_segment_slice_wise.specimen_name -> job_yield_surface_point_CLUSTER.sh
    #   02a_...material_value/pore_value    -> A01_les_2_npy.py (Metadaten fuer 02b)
    for dead in ("dicom2npy", "02_segmented_3D_array", "06_gmsh_postprocess"):
        config.pop(dead, None)

    config["01_segment_slice_wise"] = {
        "specimen_name": run_name,
        "comment": "nur der Name; gelesen von job_yield_surface_point_CLUSTER.sh",
    }
    config["02a_rotate_pic_to_align_with_axis"] = {
        "material_value": 1,
        "pore_value": 0,
        "comment": (
            "Keine Rotation im .leS-Pfad. A01_les_2_npy.py schreibt mit diesen Werten "
            "den Metadateneintrag, den 02b erwartet."
        ),
    }

    subvolume = config.setdefault("02b_build_subvolume_arrays", {})
    subvolume["subvolume_output_folder"] = volume_folder
    if args.xy_divisions is not None:
        subvolume["xy_divisions"] = args.xy_divisions

    mesh = config.setdefault("03_mesh_3D_array", {})
    mesh["specimen_name"] = f"{run_name}_segmented"
    mesh["input_folder"] = volume_folder
    mesh["mesh_output_path"] = f"{output_base}/mesh.xdmf"

    # Robustheit der SDF-Oberflaeche. pad_width = 1 ist grenzwertig, sobald die
    # Randschale aus 02d bis an den Arrayrand reicht: die geglaettete Isoflaeche
    # kann aus dem gepolsterten Array herauslaufen und wird abgeschnitten
    # ("open edges" im Topologie-Audit). Gemessen an einem 300^3-Ausschnitt bei
    # reduce=2: pad_width=1 mit sigma=1.25 -> 7180 offene Kanten, pad_width=3
    # mit sigma=1.25 und 1.5 -> 0. Der Versatz wird nach Marching Cubes wieder
    # herausgerechnet, die Geometrie aendert sich dadurch nicht.
    sdf = mesh.setdefault("sdf_pygalmesh_parameters", {})
    sdf["pad_width"] = args.sdf_pad_width
    sdf["keep_largest_component"] = bool(args.keep_largest_component)

    # Netzfeinheit. Drei Wege, in dieser Reihenfolge ausgewertet:
    #   1. --max-element-size-um: absolute Zielkantenlaenge; der Faktor wird aus der
    #      Voxelgroesse (voxel_size * reduce) berechnet. Unabhaengig von reduce.
    #   2. --current-tets/--target-tets: Elementzahl skaliert mit 1/h^3.
    #   3. --mesh-size-scale: direkter Faktor.
    scale = float(args.mesh_size_scale)
    voxel_um = (args.voxel_size if args.voxel_size else 1.67e-05) * 1e6 * args.reduce
    pygal_blocks = [b for b in (mesh.get("pygalmesh_parameters"),
                                sdf.get("pygalmesh_parameters")) if isinstance(b, dict)]
    if args.max_element_size_um:
        reference = pygal_blocks[-1].get("max_element_size_factor", 1.4853084267560892)
        scale = (float(args.max_element_size_um) / voxel_um) / float(reference)
    elif args.current_tets and args.target_tets:
        scale = (float(args.current_tets) / float(args.target_tets)) ** (1.0 / 3.0)
    if abs(scale - 1.0) > 1e-9:
        for block in pygal_blocks:
            for key in ("max_element_size_factor", "max_facet_distance_factor"):
                if key in block and block[key]:
                    block[key] = float(block[key]) * scale
        mesh["mesh_size_scale_applied"] = scale
    # Metadatum immer aus Faktor x aktueller Voxelgroesse ableiten - auch wenn der
    # Faktor unveraendert bleibt (z. B. reduce 2 -> 4 bei 75 -> 150 um: gleicher
    # Faktor 2,2455, aber andere Voxelgroesse). Vorher blieb hier der Wert der
    # Basisconfig stehen (Fix aus 015 vom 01.09.2026, in 016 am 02.09. nachgezogen).
    if pygal_blocks:
        mesh["max_element_size_um"] = pygal_blocks[-1]["max_element_size_factor"] * voxel_um

    # Randschale (02d): muss vom Netz aufloesbar bleiben, sonst traegt sie die
    # Dirichlet-Raender nicht. Faustregel: mindestens drei Elemente Dicke.
    seal = config.setdefault("02d_axis_aligned_cuboid_crop", {}).setdefault("boundary_seal", {})
    thick = seal.setdefault("thicknesses", {})
    if args.boundary_shell_xz:
        thick["x_min"] = thick["x_max"] = thick["z_min"] = thick["z_max"] = args.boundary_shell_xz
    if args.boundary_shell_y:
        thick["y_min"] = thick["y_max"] = args.boundary_shell_y

    # --- Fliessgrenze und Fliesskriterien -------------------------------------
    ys = config.setdefault("yield_surface", {})
    if args.sig_y:
        for name in (args.sig_y_materials or ["std"]):
            if name in ys.get("material_sets", {}):
                ys["material_sets"][name]["sig_y"] = float(args.sig_y)

    threshold = float(args.plastic_strain_threshold)
    ys["primary_criterion"] = args.primary_criterion
    ys["criteria"] = [
        {"name": "eps_p_eq_macroscopic",
         "quantity": "eps_p_eq_macroscopic",
         "threshold": threshold, "blocking": True,
         "comment": "sqrt(2/3 E_p:E_p), E_p = Volumenmittel des plastischen Dehnungstensors "
                    "ueber das reduzierte RVE-Volumen -> Rp0,2-Analogon"},
        {"name": "alpha_avg_material",
         "quantity": "alpha_avg_reduced_material_volume",
         "threshold": threshold, "blocking": True,
         "comment": "<alpha> (akkumulierte aequivalente plastische Dehnung) ueber die Materialphase"},
        {"name": "yielded_fraction_material" if args.yielded_volume_reference == "material"
                 else "yielded_fraction_rve",
         "quantity": "yielded_fraction_reduced_material_volume"
                     if args.yielded_volume_reference == "material"
                     else "yielded_fraction_reduced_volume",
         "threshold": float(args.yielded_volume_fraction), "blocking": True,
         "comment": ("Kriterium der bisherigen Studie: Anteil des Materialvolumens mit "
                     "alpha > alpha_yield_tolerance"
                     if args.yielded_volume_reference == "material"
                     else "Anteil des reduzierten RVE-Volumens mit alpha > alpha_yield_tolerance "
                          "(Materialanteil x relative Dichte)")},
    ]

    for assignment in args.set or []:
        set_dotted(config, assignment)
    return config


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-config", default="config-A01-les.json",
                        help="Bestehende, validierte Config als Vorlage (in 014 die eigene)")
    parser.add_argument("--output", default="config-A01-les.json")
    parser.add_argument("--dataset-id", default="JM-25-77_A01_les")
    parser.add_argument("--les-input", default="/data/resources/A01_segmented",
                        help="Datei, Ordner oder Glob mit der .leS-Datei (Container- oder Host-Pfad)")
    parser.add_argument("--reduce", type=int, default=2,
                        help="Kantenlänge der zusammengefassten Voxelblöcke")
    parser.add_argument("--reduce-mode", default="majority",
                        choices=["majority", "threshold", "any", "all"])
    parser.add_argument("--reduce-threshold", type=float, default=0.5)
    parser.add_argument("--smooth-sigma", type=float, default=0.0)
    parser.add_argument("--x-range", nargs=2, type=int, default=None)
    parser.add_argument("--y-range", nargs=2, type=int, default=None)
    parser.add_argument("--z-range", nargs=2, type=int, default=None)
    parser.add_argument("--line-order", default="C", choices=["C", "F"])
    parser.add_argument("--les-material-value", type=int, default=1,
                        help="Labelwert des Aluminiums in der .leS-Datei")
    parser.add_argument("--bounds-mode", default="full", choices=["full", "material"])
    parser.add_argument("--voxel-size", type=float, default=None,
                        help="Voxelgröße in m überschreiben (sonst aus dem .leS-Header)")
    parser.add_argument("--voxel-size-unit", default="mm", choices=["m", "mm", "um"],
                        help="Einheit, in der SliceThickness in die metadata.json geschrieben wird")
    parser.add_argument("--binning-label", default=None,
                        help="Label für die Ergebnisordner (Default: leS-reduce-<N>)")
    parser.add_argument("--xy-divisions", type=int, default=None)
    parser.add_argument("--sdf-pad-width", type=int, default=3,
                        help="Padding vor dem Signed-Distance-Field (Schutz gegen "
                             "abgeschnittene Isoflaechen am Domaenenrand)")
    parser.add_argument("--sig-y", type=float, default=100.0,
                        help="Anfangsfliessgrenze in MPa")
    parser.add_argument("--sig-y-materials", nargs="*", default=["std"],
                        help="Materialsaetze, fuer die --sig-y gilt")
    parser.add_argument("--plastic-strain-threshold", type=float, default=0.002,
                        help="Schwelle der drei plastischen Dehnungsmasse (0.002 = Rp0,2)")
    parser.add_argument("--yielded-volume-fraction", type=float, default=0.002,
                        help="Schwelle des Volumenanteil-Kriteriums (drittes Abbruchkriterium)")
    parser.add_argument("--yielded-volume-reference", default="material",
                        choices=["material", "rve"],
                        help="Bezugsvolumen des Volumenanteil-Kriteriums: Materialphase "
                             "(porositaetsunabhaengig) oder reduziertes RVE-Volumen")
    parser.add_argument("--primary-criterion", default="eps_p_eq_macroscopic",
                        help="Kriterium, dessen Zustand als final_yield_state ausgegeben wird")
    parser.add_argument("--max-element-size-um", type=float, default=None,
                        help="Zielkantenlaenge der Elemente in um (max_cell_circumradius). "
                             "Setzt die Groessenfaktoren passend zur Voxelgroesse; hat Vorrang.")
    parser.add_argument("--boundary-shell-xz", type=int, default=None,
                        help="Dicke der Randschale in x und z (Voxel)")
    parser.add_argument("--boundary-shell-y", type=int, default=None,
                        help="Dicke der Randschale in y (Voxel)")
    parser.add_argument("--mesh-size-scale", type=float, default=1.0,
                        help="Skaliert max_element_size_factor und max_facet_distance_factor; "
                             ">1 = groebere Elemente (Elementzahl ~ 1/scale^3)")
    parser.add_argument("--current-tets", type=float, default=None,
                        help="Tetraederzahl des bisherigen Netzes (aus mesh.quality.txt)")
    parser.add_argument("--target-tets", type=float, default=None,
                        help="gewuenschte Tetraederzahl; zusammen mit --current-tets wird "
                             "--mesh-size-scale daraus berechnet")
    parser.add_argument("--keep-largest-component", action="store_true",
                        help="nur die groesste zusammenhaengende Aluminiumkomponente vernetzen "
                             "(entfernt freischwebende Inseln und damit Starrkoerpermoden)")
    parser.add_argument("--project-dir", default=None,
                        help="Default: Ordner dieses Skripts")
    parser.add_argument("--set", action="append", default=None,
                        metavar="dotted.path=JSON", help="Einzelnen Config-Wert überschreiben")
    return parser


def main():
    args = build_parser().parse_args()
    project_dir = Path(args.project_dir).resolve() if args.project_dir else Path(__file__).resolve().parent

    base_path = Path(args.base_config)
    if not base_path.is_absolute():
        base_path = project_dir / base_path
    with base_path.open() as handle:
        base = json.load(handle)

    config = build_config(base, args)

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = project_dir / output_path
    with output_path.open("w") as handle:
        json.dump(config, handle, indent=2)
        handle.write("\n")

    section = config["A01_les_2_npy"]
    print(f"Wrote {output_path}")
    print(f"  dataset.id         : {config['dataset']['id']}")
    print(f"  binning.label      : {config['binning']['label']}")
    print(f"  .leS-Eingabe       : {section['input']}")
    print(f"  reduce             : {section['reduce']['factor']} ({section['reduce']['mode']})")
    print(f"  Volumenordner      : {section['output_folder']}")
    sdf_params = config["03_mesh_3D_array"]["sdf_pygalmesh_parameters"]
    print(f"  sdf pad_width      : {sdf_params['pad_width']}")
    print(f"  keep_largest_comp. : {sdf_params['keep_largest_component']}")
    pg = sdf_params.get("pygalmesh_parameters", {})
    print(f"  max_element_size   : {pg.get('max_element_size_factor')} x dx")
    print(f"  max_facet_distance : {pg.get('max_facet_distance_factor')} x dx")
    if "mesh_size_scale_applied" in config["03_mesh_3D_array"]:
        f = config["03_mesh_3D_array"]["mesh_size_scale_applied"]
        h = config["03_mesh_3D_array"]["max_element_size_um"]
        print(f"  Netzfeinheit       : Faktor {f:.4f} grober -> Elementzahl ~ 1/{f**3:.2f}")
        print(f"  Elementgroesse     : {h:.1f} um (max_cell_circumradius)")
    t = config["02d_axis_aligned_cuboid_crop"]["boundary_seal"]["thicknesses"]
    print(f"  Randschale (Voxel) : x/z = {t['x_min']}, y = {t['y_min']}")
    ys = config["yield_surface"]
    print(f"  sig_y (std)        : {ys['material_sets']['std']['sig_y']} MPa")
    print(f"  Fliesskriterien    : {', '.join(c['name'] + ('' if c['blocking'] else ' (nur Doku)') for c in ys['criteria'])}")
    print(f"  Schwelle           : {ys['criteria'][0]['threshold']:g}  | final_yield_state aus: {ys['primary_criterion']}")
    print(f"  metadata_output_path: {config['metadata_output_path']}")


if __name__ == "__main__":
    main()
