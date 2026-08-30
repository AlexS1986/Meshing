#!/bin/bash
set -euo pipefail

working_directory="$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS"
CONFIG_ARG="${1:?Usage: job_yield_surface_point_CLUSTER.sh /data/path/to/sample/config.json}"
if [[ "$CONFIG_ARG" = /* ]]; then
  CONFIG_PATH="$CONFIG_ARG"
else
  CONFIG_PATH="/data/scripts/015-Yield-Surface-Batch-leS/$CONFIG_ARG"
fi
CONFIG_HOST_PATH="${CONFIG_PATH/#\/data/$HPC_SCRATCH/pygalmesh/data}"
if [[ ! -f "$CONFIG_HOST_PATH" ]]; then
  echo "Config not found on the host: $CONFIG_HOST_PATH" >&2
  exit 2
fi

CONTAINER_PATH="$HOME/meshing/Meshing/pygalmesh/pygalmesh.sif"
BIND_PATHS="$HOME/meshing/Meshing/pygalmesh/data:/home,$HPC_SCRATCH/pygalmesh/data:/data"
SIM_CONTAINER="$HOME/dolfinx_alex/alex-dolfinx.sif"
SIM_BIND="$HOME/dolfinx_alex/shared:/home,$HPC_SCRATCH/pygalmesh/data:/data"
SOURCE_DIR="$working_directory/00_template"
sim_ntasks="${SLURM_NTASKS:-32}"
# Ohne explizite Vorgabe erbt der srun-Step die Zuteilung des Jobs. Feste Werte
# hier fuehren zu "More processors requested than permitted", sobald der Job
# weniger Speicher je CPU hat als der Step anfordert: SLURM rechnet den
# Speicherwunsch in CPUs um und verlangt dann mehr, als der Job besitzt.
# (Beispiel: Job 64 x 5600 MB, Step wollte 64 x 9000 MB -> braeuchte 103 CPUs.)
SRUN_TIME="${SRUN_TIME:-}"
SRUN_MEM_PER_CPU="${SRUN_MEM_PER_CPU:-}"
SRUN_LIMITS=()
if [[ -n "$SRUN_TIME" ]]; then SRUN_LIMITS+=(--time="$SRUN_TIME"); fi
if [[ -n "$SRUN_MEM_PER_CPU" ]]; then SRUN_LIMITS+=(--mem-per-cpu="$SRUN_MEM_PER_CPU"); fi
case_scratch="$working_directory/scratch/yield_point_${SLURM_JOB_ID:-manual}"
rm -rf "$case_scratch"
mkdir -p "$case_scratch/tmp"

# ---------------------------------------------------------------------------
# Wandzeit-Deadline an den Solver weiterreichen
# ---------------------------------------------------------------------------
# elastoplastic.py duennt die Feldausgabe aus (Default: ein Snapshot alle zwoelf
# Stunden) und beendet sich deshalb rechtzeitig VOR dem SLURM-Zeitlimit selbst,
# um den zuletzt gerechneten Zeitschritt noch als Snapshot plus restart_meta zu
# schreiben. Dafuer braucht es die Endzeit des Jobs. Reihenfolge: bereits
# gesetzte Variable, SLURM_JOB_END_TIME, sonst squeue.
deadline_epoch="${YIELD_WALLTIME_DEADLINE_EPOCH:-${SLURM_JOB_END_TIME:-}}"
if [[ -z "$deadline_epoch" && -n "${SLURM_JOB_ID:-}" ]] && command -v squeue > /dev/null; then
  end_str="$(squeue -h -j "$SLURM_JOB_ID" -O EndTime 2> /dev/null | head -n 1 | tr -d ' ' || true)"
  if [[ -n "$end_str" && "$end_str" != "N/A" && "$end_str" != "Unknown" ]]; then
    deadline_epoch="$(date -d "$end_str" +%s 2> /dev/null || true)"
  fi
fi
if [[ -n "$deadline_epoch" ]]; then
  # Apptainer reicht das Environment durch; die APPTAINERENV_/SINGULARITYENV_-
  # Varianten sind die Absicherung fuer --cleanenv-artige Voreinstellungen.
  export YIELD_WALLTIME_DEADLINE_EPOCH="$deadline_epoch"
  export APPTAINERENV_YIELD_WALLTIME_DEADLINE_EPOCH="$deadline_epoch"
  export SINGULARITYENV_YIELD_WALLTIME_DEADLINE_EPOCH="$deadline_epoch"
  echo "Job-Endzeit (Deadline fuer den Solver): $(date -d "@$deadline_epoch" 2> /dev/null || echo "$deadline_epoch")"
else
  echo "[WARNUNG] Job-Endzeit nicht ermittelbar - der Solver kann sich nicht"
  echo "          rechtzeitig beenden und wird am Zeitlimit hart abgeschossen."
  echo "          Notfalls YIELD_WALLTIME_LIMIT_MINUTES=<Minuten> setzen."
fi

run_container() {
  local ntasks="$1"
  local chdir="$2"
  local bind_paths="$3"
  local container="$4"
  shift 4
  local srun_args=(-n "$ntasks" ${SRUN_LIMITS[@]+"${SRUN_LIMITS[@]}"})
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

CONFIG_INFO=$(srun -n 1 ${SRUN_LIMITS[@]+"${SRUN_LIMITS[@]}"} apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" python3 - "$CONFIG_PATH" <<'PYINFO'
import json, sys
with open(sys.argv[1]) as handle:
    config = json.load(handle)
ys = config.get("yield_surface", {})
print(config["binning"]["label"])
print(config["01_segment_slice_wise"]["specimen_name"])
print(config["02b_build_subvolume_arrays"]["subvolume_output_folder"])
print(" ".join(ys.get("materials", ["std"])))
print(" ".join(ys.get("loading_directions", ["tensor"])))
print(ys.get("sample_id", "yield_sample"))
print(config.get("02d_axis_aligned_cuboid_crop", {}).get("output_filename", "volume_boundary_shell_aniso.npy"))
dataset_id = config.get("dataset", {}).get("id")
if not dataset_id:
    dataset_id = config["01_segment_slice_wise"]["specimen_name"].split("_Bin", 1)[0]
print(dataset_id)
PYINFO
)

binning_label="$(echo "$CONFIG_INFO" | sed -n '1p')"
run_name="$(echo "$CONFIG_INFO" | sed -n '2p')"
base_subvolume_container_path="$(echo "$CONFIG_INFO" | sed -n '3p')"
materials_line="$(echo "$CONFIG_INFO" | sed -n '4p')"
directions_line="$(echo "$CONFIG_INFO" | sed -n '5p')"
sample_id="$(echo "$CONFIG_INFO" | sed -n '6p')"
shell_volume_filename="$(echo "$CONFIG_INFO" | sed -n '7p')"
dataset_id="$(echo "$CONFIG_INFO" | sed -n '8p')"
read -r -a MATERIALS <<< "$materials_line"
read -r -a DIRECTIONS <<< "$directions_line"
base_subvolume_folder="${base_subvolume_container_path/#\/data/$HPC_SCRATCH/pygalmesh/data}"
# Das binning label enthaelt sig_y. Ohne es wuerden sich die beiden
# sig_y-Varianten desselben Datensatzes denselben Arbeitsordner teilen und
# sich gegenseitig ueberschreiben, weil sie dieselbe dataset.id haben.
run_root="$working_directory/yield_surface_runs/$dataset_id/$binning_label/$sample_id"
mkdir -p "$run_root"

echo "Running yield-surface point: $sample_id"
echo "Dataset: $dataset_id"
echo "Using config: $CONFIG_PATH"
echo "Using prepared mesh folder: $base_subvolume_folder"
echo "Run root: $run_root"

# Restart-Verhalten (wie in 014, siehe dort RESTART_NACH_TIMEOUT.md): Existiert
# im Zielordner bereits ein (abgebrochener) Rechenstand (elastoplastic_*.xdmf
# bzw. restart_meta_*.json), wird er NICHT geloescht; nur die Skripte werden
# aktualisiert und elastoplastic.py setzt den Lauf selbst fort (siehe
# 00_template/yield_restart.py). Mit YS_FORCE_FRESH=1 wird der alte Stand
# verworfen und neu gerechnet.
FORCE_FRESH="${YS_FORCE_FRESH:-0}"

for mat in "${MATERIALS[@]}"; do
  for direction in "${DIRECTIONS[@]}"; do
    final_output_dir="$working_directory/00_results/${dataset_id}/${binning_label}/yield_surface/${sample_id}-${mat}-${direction}"
    for subfolder in "$base_subvolume_folder"/*/; do
      [ -d "$subfolder" ] || continue
      if [ ! -f "$subfolder/dlfx_mesh.xdmf" ]; then
        echo "Missing $subfolder/dlfx_mesh.xdmf. Run run_prepare_mesh_CLUSTER.sh first." >&2
        exit 1
      fi
      target="$run_root/$(basename "$subfolder")"
      mat_lc="$(echo "$mat" | tr '[:upper:]' '[:lower:]')"
      summary_file="$target/yield_run_${mat_lc}_${direction}.json"
      if [[ "$FORCE_FRESH" != "1" && -f "$summary_file" ]]; then
        echo "[RESTART] $(basename "$summary_file") existiert bereits - Solverlauf wird uebersprungen."
        continue
      fi
      has_state=0
      if [[ "$FORCE_FRESH" != "1" && -d "$target" && -f "$target/dlfx_mesh.xdmf" ]]; then
        if compgen -G "$target/elastoplastic_*.xdmf" > /dev/null || \
           compgen -G "$target/restart_meta_*.json" > /dev/null; then
          has_state=1
        fi
      fi
      if [[ "$has_state" == "1" ]]; then
        echo "[RESTART] Vorhandener Rechenstand in $target wird fortgesetzt (kein rm -rf)."
        cp -v "$SOURCE_DIR"/* "$target"/
        cp -v "$working_directory/write_yield_surface_parameters.py" "$target/"
        cp -v "$CONFIG_HOST_PATH" "$target/config.json"
      else
        rm -rf "$target"
        mkdir -p "$target"
        cp -v "$subfolder"/dlfx_mesh.* "$target"/
        cp -v "$subfolder"/mesh.xdmf "$target"/ 2>/dev/null || true
        cp -v "$subfolder"/mesh.h5 "$target"/ 2>/dev/null || true
        cp -v "$subfolder/$shell_volume_filename" "$target"/ 2>/dev/null || true
        cp -v "$subfolder"/volume*.npy "$target"/ 2>/dev/null || true
        cp -v "$SOURCE_DIR"/* "$target"/
        cp -v "$working_directory/write_yield_surface_parameters.py" "$target/"
        cp -v "$CONFIG_HOST_PATH" "$target/config.json"
      fi
      run_container 1 "$target" "$SIM_BIND" "$SIM_CONTAINER" \
        python3 "$target/write_yield_surface_parameters.py" --config "$target/config.json" --output "$target/parameters.txt" --material "$mat" --loading-direction "$direction"
      # Exit-Code 3 = elastoplastic.py hat sich kontrolliert vor dem Zeitlimit
      # beendet (Snapshot und restart_meta sind geschrieben). Der Job muss dann
      # mit != 0 enden, sonst raeumt sbatch --dependency=afternotok die
      # restlichen Glieder der Fortsetzungskette ab.
      set +e
      run_container "$sim_ntasks" "$target" "$SIM_BIND" "$SIM_CONTAINER" \
        python3 "$target/elastoplastic.py" --material "$mat" --loading-direction "$direction" --config "$target/config.json"
      solver_rc=$?
      set -e
      if [[ "$solver_rc" -eq 3 ]]; then
        echo "YIELD_WALLTIME_STOP: $sample_id ($mat/$direction) wurde kontrolliert vor dem" >&2
        echo "Zeitlimit beendet - Rechenstand liegt in $target, Fortsetzung per Resubmit." >&2
        rm -rf "$case_scratch" || true
        exit 3
      elif [[ "$solver_rc" -ne 0 ]]; then
        echo "elastoplastic.py fehlgeschlagen (Exit $solver_rc)" >&2
        rm -rf "$case_scratch" || true
        exit "$solver_rc"
      fi
    done
    mkdir -p "$final_output_dir"
    if [[ "${KEEP_FULL_RUN_COPY:-0}" == "1" ]]; then
      # Wie in 014: der komplette Arbeitsordner inklusive Netz und Feldausgabe.
      cp -rv "$run_root" "$final_output_dir/"
    else
      # Default in 015: nur die Auswertungsdateien nach 00_results. Bei 8
      # Kombinationen x N Punkten wuerde die Vollkopie (Netz, XDMF/H5, Voxel)
      # 00_results um viele hundert GB aufblaehen; die Netzdaten liegen ohnehin
      # unveraendert im vorbereiteten Netzordner und im Arbeitsordner
      # yield_surface_runs/.
      for sub in "$run_root"/*/; do
        [ -d "$sub" ] || continue
        slim_target="$final_output_dir/$(basename "$run_root")/$(basename "$sub")"
        mkdir -p "$slim_target"
        cp -v "$sub"/yield_run_*.json     "$slim_target"/ 2>/dev/null || true
        cp -v "$sub"/yield_averages_*.json "$slim_target"/ 2>/dev/null || true
        cp -v "$sub"/*.txt                "$slim_target"/ 2>/dev/null || true
        cp -v "$sub"/*.log                "$slim_target"/ 2>/dev/null || true
        cp -v "$sub"/*.png                "$slim_target"/ 2>/dev/null || true
      done
    fi
    cp -v "$CONFIG_HOST_PATH" "$final_output_dir/config.json" || true
    cp -v "$run_root"/*/parameters.txt "$final_output_dir/parameters.txt" 2>/dev/null || true
  done
done

rm -rf "$case_scratch"
echo "Yield-surface point complete: $sample_id"
