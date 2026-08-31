#!/bin/bash

#SBATCH -J frac-les-sim
#SBATCH -A p0023647
#SBATCH -t 1440
#SBATCH --mem-per-cpu=3800
#SBATCH -n 24
#SBATCH -N 1
#SBATCH -C i01
# Ressourcen (2026-08-31): i01 hat 96 Kerne / 364 800 MB. Die 011/012-Werte
# -n 96 x 4000 MB = 384 000 MB passen NICHT auf einen Knoten -> mit -N 1 lehnt
# SLURM den Job ab ("Requested node configuration is not available").
# 3800 MB x 96 = 364 800 MB waere das Maximum. Das coarse-Netz hat nur ~35k
# Tetraeder (~47k DOFs); 24 Ranks sind dafuer reichlich. submit_fracture_
# pipeline_CLUSTER.sh ueberschreibt diese Werte aus config.sh (SIM_JOB_*).
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/016-Fracture-From-leS/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/016-Fracture-From-leS/%x.out.%j
#SBATCH --mail-type=END

# Stufe 2 der Bruchpipeline: Phasenfeld-Bruchsimulation gegen ein bereits
# archiviertes Netz aus job_generate_mesh_CLUSTER.sh. Es wird NICHTS neu
# vernetzt. Fehlt das Archiv, bricht das Skript mit klarer Meldung ab.
#
# Usage: sbatch job_run_simulation_CLUSTER.sh [config-file.json]
#        Dieselbe Config wie bei der Netzerzeugung verwenden - sonst zeigt der
#        Archivpfad (specimen/label/run_name) ins Leere.

set -euo pipefail

working_directory="$HPC_SCRATCH/pygalmesh/data/scripts/016-Fracture-From-leS"
# Immer aus dem Projektordner unter /work/scratch arbeiten - Apptainer haengt das
# aktuelle Verzeichnis mit ein; ein cwd ausserhalb der Binds erzeugt die Warnung
# "Error changing the container working directory" (siehe run_generate_mesh_CLUSTER.sh).
cd "$working_directory"
source "$working_directory/config.sh"

CONFIG_ARG="${1:-${FRACTURE_SIM_CONFIG:-config-fracture-${SPECIMEN_NAME}-${DEFAULT_TIER}.json}}"
if [[ "$CONFIG_ARG" = /* ]]; then
  CONFIG_PATH="$CONFIG_ARG"
else
  CONFIG_PATH="/data/scripts/016-Fracture-From-leS/$CONFIG_ARG"
fi
CONFIG_HOST_PATH="${CONFIG_PATH/#\/data/$HPC_SCRATCH/pygalmesh/data}"
if [[ ! -f "$CONFIG_HOST_PATH" ]]; then
  echo "Config nicht gefunden: $CONFIG_HOST_PATH" >&2
  exit 2
fi

SIM_CONTAINER="$HOME/dolfinx_alex/alex-dolfinx.sif"
SIM_BIND="$HOME/dolfinx_alex/shared:/home,$HPC_SCRATCH/pygalmesh/data:/data"
SOURCE_DIR="$working_directory/00_template"
sim_ntasks="${SLURM_NTASKS:-$SIM_JOB_NTASKS}"
SRUN_MEM_PER_CPU="${SRUN_MEM_PER_CPU:-}"

CONFIG_INFO=$(python3 - "$CONFIG_HOST_PATH" <<'PYINFO'
import json, sys
with open(sys.argv[1]) as handle:
    config = json.load(handle)
frac = config.get("fracture", {})
print(config["binning"]["label"])
# Aufloesungsspezifisch - 01_segment_slice_wise.specimen_name waere es nicht.
print(config["03_mesh_3D_array"]["specimen_name"])
print(config.get("dataset", {}).get("specimen", config["dataset"]["id"]))
print(" ".join(frac.get("materials", ["std"])))
print(" ".join(frac.get("directions", ["y"])))
print(frac.get("mesh_file", "dlfx_mesh"))
print(frac.get("lam_param", 1.0))
print(frac.get("mue_param", 1.0))
print(frac.get("Gc_param", 1.0))
print(frac.get("eps_factor_param", 20.0))
print(frac.get("element_order", 1))
print(frac.get("fracture_toughness", "alsi10mg_as_built"))
check = config.get("fracture_geometry_check", {})
print(check.get("elements_per_epsilon") or "")
PYINFO
)

binning_label="$(echo "$CONFIG_INFO" | sed -n '1p')"
run_name="$(echo "$CONFIG_INFO" | sed -n '2p')"
specimen="$(echo "$CONFIG_INFO" | sed -n '3p')"
materials_line="$(echo "$CONFIG_INFO" | sed -n '4p')"
directions_line="$(echo "$CONFIG_INFO" | sed -n '5p')"
fracture_mesh_file="$(echo "$CONFIG_INFO" | sed -n '6p')"
fracture_lam="$(echo "$CONFIG_INFO" | sed -n '7p')"
fracture_mue="$(echo "$CONFIG_INFO" | sed -n '8p')"
fracture_gc="$(echo "$CONFIG_INFO" | sed -n '9p')"
fracture_eps_factor="$(echo "$CONFIG_INFO" | sed -n '10p')"
fracture_element_order="$(echo "$CONFIG_INFO" | sed -n '11p')"
fracture_toughness="$(echo "$CONFIG_INFO" | sed -n '12p')"
elements_per_epsilon="$(echo "$CONFIG_INFO" | sed -n '13p')"
read -r -a MATERIALS <<< "$materials_line"
read -r -a DIRECTIONS <<< "$directions_line"

MESH_ARCHIVE_DIR="$HPC_SCRATCH/pygalmesh/data/resources/generated_meshes/${specimen}/${binning_label}/${run_name}"
if [[ ! -d "$MESH_ARCHIVE_DIR" ]]; then
  echo "Kein archiviertes Netz unter: $MESH_ARCHIVE_DIR" >&2
  echo "Zuerst job_generate_mesh_CLUSTER.sh mit derselben Config laufen lassen." >&2
  exit 1
fi

base_subvolume_folder="$working_directory/${run_name}_from_resources"
case_scratch="$working_directory/scratch/${run_name}_${SLURM_JOB_ID:-manual}"
rm -rf "$base_subvolume_folder" "$case_scratch"
mkdir -p "$case_scratch/tmp"
cp -r "$MESH_ARCHIVE_DIR" "$base_subvolume_folder"

echo "Bruchsimulation: $specimen / $binning_label / $run_name"
echo "Config     : $CONFIG_PATH"
echo "Netzarchiv : $MESH_ARCHIVE_DIR"
echo "Parameter  : mesh=$fracture_mesh_file toughness=$fracture_toughness eps_factor=$fracture_eps_factor order=$fracture_element_order"
if [[ -n "$elements_per_epsilon" ]]; then
  echo "Elemente je epsilon (aus der Config): $elements_per_epsilon"
  awk -v v="$elements_per_epsilon" 'BEGIN { if (v+0 < 2.0) print "WARNUNG: weniger als 2 Elemente je epsilon - das Ergebnis wird netzabhaengig sein." }'
fi
# Surfing-BC greift nur bei |y - y_mid| >= 4*epsilon (alex.boundaryconditions).
# eps_factor <= 8 -> 4*epsilon >= Ly/2 -> BC auf keinem Knoten -> Starrkoerpermoden.
if awk -v v="$fracture_eps_factor" 'BEGIN { exit !(v+0 <= 8.0) }'; then
  echo "FEHLER: eps_factor_param = $fracture_eps_factor <= 8: die Surfing-Randbedingung wuerde nirgends greifen." >&2
  echo "        (BC-Band = 1 - 8/eps_factor der Hoehe; 011 nutzte 20.) Abbruch." >&2
  exit 3
fi
awk -v v="$fracture_eps_factor" 'BEGIN { f = 1.0 - 8.0 / (v+0); printf "Surfing-BC wirkt auf %.0f %% der Riegelhoehe (|y-y_mid| >= 4*epsilon)\n", 100*f; if (f < 0.5) print "WARNUNG: BC-Band unter 50 % - eps_factor_param >= 16 empfohlen." }'

run_container() {
  local ntasks="$1"
  local chdir="$2"
  local bind_paths="$3"
  local container="$4"
  shift 4
  local srun_args=(-n "$ntasks")
  # Zeit und Speicher NICHT fest setzen: der Step erbt sie vom Job. Feste
  # --mem-per-cpu-Werte im Step haben in 015 zu
  # "More processors requested than permitted" gefuehrt, sobald der Job
  # weniger Speicher je CPU bekam als der Step anforderte.
  [[ -n "$SRUN_MEM_PER_CPU" ]] && srun_args+=(--mem-per-cpu="$SRUN_MEM_PER_CPU")
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

for mat in "${MATERIALS[@]}"; do
  for dir in "${DIRECTIONS[@]}"; do
    final_output_dir="$working_directory/00_results/${specimen}/${binning_label}/fracture/${run_name}-${mat}-${dir}"
    for subfolder in "$base_subvolume_folder"/*/; do
      [ -d "$subfolder" ] || continue
      [ -f "$subfolder/dlfx_mesh.xdmf" ] || continue
      cp "$SOURCE_DIR"/* "$subfolder"
      cp "$CONFIG_HOST_PATH" "$subfolder/config.json"
      run_container "$sim_ntasks" "$subfolder" "$SIM_BIND" "$SIM_CONTAINER" \
        python3 "$subfolder/script.py" \
          --mesh_file "$fracture_mesh_file" \
          --material "$mat" \
          --fracture-toughness "$fracture_toughness" \
          --config "$subfolder/config.json" \
          --lam_param "$fracture_lam" \
          --mue_param "$fracture_mue" \
          --Gc_param "$fracture_gc" \
          --eps_factor_param "$fracture_eps_factor" \
          --element_order "$fracture_element_order"
    done
    mkdir -p "$final_output_dir"
    cp -r "$base_subvolume_folder" "$final_output_dir/"
    cp "$CONFIG_HOST_PATH" "$final_output_dir/" || true
  done
done

rm -rf "$case_scratch"
echo "Bruchsimulation fertig."
echo "Ergebnisse: $working_directory/00_results/${specimen}/${binning_label}/fracture/"
