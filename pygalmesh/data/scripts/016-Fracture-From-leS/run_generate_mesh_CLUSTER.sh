#!/bin/bash
#
# Runner der Netzerzeugung (Stufe 1). Wird von job_generate_mesh_CLUSTER.sh
# aufgerufen und kann auf einem Rechenknoten auch direkt gestartet werden.
#
# Kette:  A01 (.leS -> Voxel) -> 02b -> [02c] -> [02e] -> [02d] -> [02f]
#         -> 03 (pygalmesh) -> 04 -> [10] -> [11] -> [05/08] -> [09]
#         -> make_mesh_dlfx_compatible -> Archiv
#
# Die Schritte in eckigen Klammern haengen an ihrem `enabled`-Flag in der Config.
# Am Ende werden NUR die DolfinX-Netze archiviert unter
#   $HPC_SCRATCH/pygalmesh/data/resources/generated_meshes/<specimen>/<label>/<run_name>/
# Zwischenarrays und QA-Reports bleiben im Arbeitsverzeichnis und lassen sich
# durch einen erneuten Lauf wiederherstellen.

set -euo pipefail

working_directory="$HPC_SCRATCH/pygalmesh/data/scripts/016-Fracture-From-leS"
# Die Schritte unten geben Apptainer HOST-Pfade unter /work/scratch (Skripte,
# volume.npy, mesh.xdmf). Gebunden sind aber nur .../pygalmesh/data:/home und
# $HPC_SCRATCH/pygalmesh/data:/data - sichtbar wird der Host-Pfad nur, weil
# Apptainer das aktuelle Arbeitsverzeichnis mit einhaengt. Ohne dieses cd erbt
# der srun-Step das Verzeichnis, aus dem sbatch abgeschickt wurde; liegt das
# ausserhalb von /work/scratch (z.B. $HOME/meshing/Meshing/pygalmesh), bricht
# schon A01 mit "can't open file .../A01_les_2_npy.py" ab (Falle aus 015,
# in 016 am 2026-08-31 erneut aufgetreten).
cd "$working_directory"
source "$working_directory/config.sh"

CONFIG_ARG="${1:-${FRACTURE_MESH_CONFIG:-config-fracture-${SPECIMEN_NAME}-${DEFAULT_TIER}.json}}"
if [[ "$CONFIG_ARG" = /* ]]; then
  CONFIG_PATH="$CONFIG_ARG"
else
  CONFIG_PATH="/data/scripts/016-Fracture-From-leS/$CONFIG_ARG"
fi
CONFIG_HOST_PATH="${CONFIG_PATH/#\/data/$HPC_SCRATCH/pygalmesh/data}"
if [[ ! -f "$CONFIG_HOST_PATH" ]]; then
  echo "Config nicht auf dem Host gefunden: $CONFIG_HOST_PATH" >&2
  echo "Zuerst ./create_fracture_config.sh laufen lassen und neu synchronisieren." >&2
  exit 2
fi

CONTAINER_PATH="$HOME/meshing/Meshing/pygalmesh/pygalmesh.sif"
BIND_PATHS="$HOME/meshing/Meshing/pygalmesh/data:/home,$HPC_SCRATCH/pygalmesh/data:/data"
SIM_CONTAINER="$HOME/dolfinx_alex/alex-dolfinx.sif"
SIM_BIND="$HOME/dolfinx_alex/shared:/home,$HPC_SCRATCH/pygalmesh/data:/data"
VOLUME_FILENAME="volume.npy"
case_scratch="$working_directory/scratch/generate_mesh_${SLURM_JOB_ID:-manual}"
rm -rf "$case_scratch"
mkdir -p "$case_scratch/tmp"

run_container() {
  local ntasks="$1"
  local chdir="$2"
  local bind_paths="$3"
  local container="$4"
  shift 4
  local srun_args=(-n "$ntasks")
  if [[ -n "$chdir" ]]; then
    srun_args+=(--chdir="$chdir")
  fi
  srun "${srun_args[@]}" bash -lc '
    case_scratch="$1"
    bind_paths="$2"
    container="$3"
    shift 3
    mkdir -p "$case_scratch/tmp"
    export TMPDIR="$case_scratch/tmp"
    apptainer exec --bind "$bind_paths,$case_scratch:$case_scratch" "$container" "$@"
  ' bash "$case_scratch" "$bind_paths" "$container" "$@"
}

# Die Config wird auf dem HOST gelesen (kein srun noetig) - das spart pro
# Abfrage einen Job-Step. In 015 lief das noch durch den Container.
config_bool() {
  python3 - "$CONFIG_HOST_PATH" "$1" <<'PYBOOL'
import json, sys
with open(sys.argv[1]) as handle:
    config = json.load(handle)
value = config
for key in sys.argv[2].split('.'):
    value = value.get(key, {}) if isinstance(value, dict) else {}
print("1" if value is True else "0")
PYBOOL
}

config_value_default() {
  python3 - "$CONFIG_HOST_PATH" "$1" "$2" <<'PYVAL'
import json, sys
with open(sys.argv[1]) as handle:
    config = json.load(handle)
value = config
for key in sys.argv[2].split('.'):
    if not isinstance(value, dict) or key not in value:
        print(sys.argv[3]); raise SystemExit
    value = value[key]
print(sys.argv[3] if value is None else value)
PYVAL
}

CONFIG_INFO=$(python3 - "$CONFIG_HOST_PATH" <<'PYINFO'
import json, sys
with open(sys.argv[1]) as handle:
    config = json.load(handle)
print(config["02b_build_subvolume_arrays"]["subvolume_output_folder"])
# run_name muss aufloesungsspezifisch sein, sonst ueberschreiben sich die
# Stufen coarse/medium/fine gegenseitig im Archiv (Falle aus 012).
print(config["03_mesh_3D_array"]["specimen_name"])
print(config["binning"]["label"])
print(config.get("dataset", {}).get("specimen", config["dataset"]["id"]))
print(config["A01_les_2_npy"]["input"])
PYINFO
)
base_subvolume_container_path="$(echo "$CONFIG_INFO" | sed -n '1p')"
run_name="$(echo "$CONFIG_INFO" | sed -n '2p')"
binning_label="$(echo "$CONFIG_INFO" | sed -n '3p')"
specimen="$(echo "$CONFIG_INFO" | sed -n '4p')"
resource_container_path="$(echo "$CONFIG_INFO" | sed -n '5p')"
base_subvolume_folder="${base_subvolume_container_path/#\/data/$HPC_SCRATCH/pygalmesh/data}"
resource_host_path="${resource_container_path/#\/data/$HPC_SCRATCH/pygalmesh/data}"

# --- Eingabe pruefen, bevor Rechenzeit verbrannt wird ------------------------
if [[ ! -e "$resource_host_path" ]]; then
  echo "Segmentierte .leS-Eingabe nicht gefunden: $resource_host_path" >&2
  echo "Container-Pfad aus der Config: $resource_container_path" >&2
  exit 2
fi
if [[ -d "$resource_host_path" ]]; then
  les_file_count="$(find "$resource_host_path" -maxdepth 1 -type f \( -name '*.leS' -o -name '*.les' \) | wc -l)"
  if [[ "$les_file_count" -ne 1 ]]; then
    echo "In $resource_host_path liegen $les_file_count .leS-Dateien - genau eine wird erwartet." >&2
    echo "A01_les_2_npy.input in der Config auf die konkrete Datei setzen." >&2
    exit 2
  fi
fi

echo "Netzerzeugung fuer $specimen / $binning_label / $run_name"
echo "Config      : $CONFIG_PATH"
echo ".leS-Eingabe: $resource_host_path"
echo "Riegel      : $(config_value_default fracture_geometry_check.bar_extent_mm.x '?') x $(config_value_default fracture_geometry_check.bar_extent_mm.y '?') x $(config_value_default fracture_geometry_check.bar_extent_mm.z '?') mm"
echo "Elementgroesse: $(config_value_default mesh_resolution.max_element_size_um '?') um"

for script in A01_les_2_npy.py 02b_build_subvolume_arrays.py; do
  run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
    python3 "$working_directory/$script" --config "$CONFIG_PATH"
done

for subfolder in "$base_subvolume_folder"/subvolume_x*_y*/; do
  [ -d "$subfolder" ] || continue
  npy_file="$subfolder/$VOLUME_FILENAME"
  mesh_output="$subfolder/mesh.xdmf"
  folder_name="$(basename "$subfolder")"
  if [[ "$folder_name" =~ subvolume_x([0-9]+)_y([0-9]+) ]]; then
    center_x="${BASH_REMATCH[1]}"
    center_y="${BASH_REMATCH[2]}"
  else
    echo "center_x/center_y nicht aus $folder_name ableitbar - uebersprungen"
    continue
  fi
  meshing_npy_file="$npy_file"

  if [[ "$(config_bool 02c_voxel_topology_cleanup.enabled)" == "1" ]]; then
    cleaned_npy_file="$subfolder/$(config_value_default 02c_voxel_topology_cleanup.output_filename volume_topology_cleaned.npy)"
    voxel_report_file="$subfolder/$(config_value_default 02c_voxel_topology_cleanup.report_filename volume_topology.txt)"
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/02c_voxel_topology_cleanup.py" --config "$CONFIG_PATH" --npy "$npy_file" --output "$cleaned_npy_file" --report "$voxel_report_file"
    if [[ "$(config_bool 02c_voxel_topology_cleanup.use_cleaned_for_meshing)" == "1" ]]; then
      meshing_npy_file="$cleaned_npy_file"
    fi
  fi

  # Optionale Spiegel-Extrusion in x (Route aus 012). Im Default AUS, weil das
  # .leS-Volumen gross genug fuer einen echten Riegel ist.
  if [[ "$(config_bool 02e_mirror_extrude_voxel.enabled)" == "1" ]]; then
    mirrored_npy_file="$subfolder/$(config_value_default 02e_mirror_extrude_voxel.output_filename volume_mirrored_x.npy)"
    mirrored_report_file="$subfolder/$(config_value_default 02e_mirror_extrude_voxel.report_filename volume_mirrored_x.txt)"
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/02e_mirror_extrude_voxel.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --output "$mirrored_npy_file" --report "$mirrored_report_file"
    if [[ "$(config_bool 02e_mirror_extrude_voxel.use_mirrored_for_meshing)" == "1" ]]; then
      meshing_npy_file="$mirrored_npy_file"
    fi
  fi

  if [[ "$(config_bool 02d_axis_aligned_cuboid_crop.enabled)" == "1" ]]; then
    cuboid_npy_file="$subfolder/$(config_value_default 02d_axis_aligned_cuboid_crop.output_filename volume_cuboid.npy)"
    cuboid_report_file="$subfolder/$(config_value_default 02d_axis_aligned_cuboid_crop.report_filename volume_cuboid.txt)"
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/02d_axis_aligned_cuboid_crop.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --output "$cuboid_npy_file" --report "$cuboid_report_file"
    if [[ "$(config_bool 02d_axis_aligned_cuboid_crop.use_cuboid_for_meshing)" == "1" ]]; then
      meshing_npy_file="$cuboid_npy_file"
    fi
  fi

  if [[ "$(config_bool 02f_add_voxel_shell.enabled)" == "1" ]]; then
    shelled_npy_file="$subfolder/$(config_value_default 02f_add_voxel_shell.output_filename volume_additive_shell.npy)"
    shelled_report_file="$subfolder/$(config_value_default 02f_add_voxel_shell.report_filename volume_additive_shell.txt)"
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/02f_add_voxel_shell.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --output "$shelled_npy_file" --report "$shelled_report_file"
    if [[ "$(config_bool 02f_add_voxel_shell.use_shell_for_meshing)" == "1" ]]; then
      meshing_npy_file="$shelled_npy_file"
    fi
  fi

  run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
    python3 "$working_directory/03_mesh_3D_array_pygalmesh.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --mesh "$mesh_output"
  run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
    python3 "$working_directory/04_scale_and_translate_mesh_mod.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --center_x "$center_x" --center_y "$center_y" --npy "$meshing_npy_file"

  if [[ "$(config_bool 10_snap_mesh_to_crop_boundary.enabled)" == "1" ]]; then
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/10_snap_mesh_to_crop_boundary.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --report "${mesh_output%.xdmf}.snap_boundary.txt"
  fi
  if [[ "$(config_bool 11_mirror_extrude_mesh.enabled)" == "1" ]]; then
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/11_mirror_extrude_mesh.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --report "${mesh_output%.xdmf}.mirror_extrude.txt"
  fi

  if [[ "$(config_bool 05_tetgen_postprocess.enabled)" == "1" ]]; then
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/05_tetgen_postprocess_mesh.py" --config "$CONFIG_PATH" --mesh "$mesh_output"
    if [[ "$(config_bool 08_mesh_quality_report.enabled)" == "1" ]]; then
      run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
        python3 "$working_directory/08_mesh_quality_report.py" --config "$CONFIG_PATH" --tetgen-log "${mesh_output%.xdmf}.tetgen.log" --output "${mesh_output%.xdmf}.quality.txt"
    fi
  fi
  if [[ "$(config_bool 09_mesh_topology_audit.enabled)" == "1" ]]; then
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/09_mesh_topology_audit.py" --config "$CONFIG_PATH" --mesh "$mesh_output" --output "${mesh_output%.xdmf}.topology.txt"
  fi
done

for subfolder in "$base_subvolume_folder"/*/; do
  [ -d "$subfolder" ] || continue
  if [ -f "$subfolder/mesh.xdmf" ]; then
    run_container 1 "" "$SIM_BIND" "$SIM_CONTAINER" \
      python3 "$working_directory/make_mesh_dlfx_compatible_cluster.py" "$subfolder" -f mesh.xdmf
  fi
done

rm -rf "$case_scratch"

# --- Archiv: nur die DolfinX-Netze -------------------------------------------
MESH_ARCHIVE_DIR="$HPC_SCRATCH/pygalmesh/data/resources/generated_meshes/${specimen}/${binning_label}/${run_name}"
rm -rf "$MESH_ARCHIVE_DIR"
mkdir -p "$MESH_ARCHIVE_DIR"

archived_any=0
for subfolder in "$base_subvolume_folder"/*/; do
  [ -d "$subfolder" ] || continue
  [ -f "$subfolder/dlfx_mesh.xdmf" ] || continue
  folder_name="$(basename "$subfolder")"
  mkdir -p "$MESH_ARCHIVE_DIR/$folder_name"
  cp -v "$subfolder/dlfx_mesh.xdmf" "$MESH_ARCHIVE_DIR/$folder_name/"
  cp -v "$subfolder/dlfx_mesh.h5" "$MESH_ARCHIVE_DIR/$folder_name/"
  # Qualitaets- und Topologiereport mit archivieren - sie gehoeren zum Netz und
  # sind spaeter die einzige Spur, wie es entstanden ist.
  for report in mesh.quality.txt mesh.topology.txt mesh_sdf_surface.topology.txt; do
    [ -f "$subfolder/$report" ] && cp "$subfolder/$report" "$MESH_ARCHIVE_DIR/$folder_name/"
  done
  archived_any=1
done
cp "$CONFIG_HOST_PATH" "$MESH_ARCHIVE_DIR/config.json" || true

if [[ "$archived_any" != "1" ]]; then
  echo "Kein dlfx_mesh.xdmf/.h5 unter $base_subvolume_folder - nichts archiviert." >&2
  exit 1
fi

echo "Netzerzeugung abgeschlossen."
echo "Archiv: $MESH_ARCHIVE_DIR"
echo "Weiter mit: sbatch job_run_simulation_CLUSTER.sh $(basename "$CONFIG_PATH")"
