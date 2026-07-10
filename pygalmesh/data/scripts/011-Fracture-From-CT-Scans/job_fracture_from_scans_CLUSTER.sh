#!/bin/bash

#SBATCH -J fracture-ct
#SBATCH -A p0023647
#SBATCH -t 10080
#SBATCH -n 96
#SBATCH -N 1
#SBATCH --mem-per-cpu=4000
#SBATCH -C i01
#SBATCH -e /work/scratch/as12vapa/pygalmesh/data/scripts/011-Fracture-From-CT-Scans/%x.err.%j
#SBATCH -o /work/scratch/as12vapa/pygalmesh/data/scripts/011-Fracture-From-CT-Scans/%x.out.%j
#SBATCH --mail-type=END

set -euo pipefail

working_directory="$HPC_SCRATCH/pygalmesh/data/scripts/011-Fracture-From-CT-Scans"
source "$working_directory/config.sh"

CONFIG_ARG="${1:-config-Bin4-reduce-2-cluster-fine.json}"
if [[ "$CONFIG_ARG" = /* ]]; then
  CONFIG_PATH="$CONFIG_ARG"
else
  CONFIG_PATH="/data/scripts/011-Fracture-From-CT-Scans/$CONFIG_ARG"
fi
CONFIG_HOST_PATH="${CONFIG_PATH/#\/data/$HPC_SCRATCH/pygalmesh/data}"

CONTAINER_PATH="$HOME/meshing/Meshing/pygalmesh/pygalmesh.sif"
BIND_PATHS="$HOME/meshing/Meshing/pygalmesh/data:/home,$HPC_SCRATCH/pygalmesh/data:/data"
SIM_CONTAINER="$HOME/dolfinx_alex/alex-dolfinx.sif"
SIM_BIND="$HOME/dolfinx_alex/shared:/home,$HPC_SCRATCH/pygalmesh/data:/data"

SOURCE_DIR="$working_directory/00_template"
VOLUME_FILENAME="volume.npy"
output_directory_variable="fracture"
sim_ntasks="${SLURM_NTASKS:-96}"
SRUN_TIME="${SRUN_TIME:-1440}"
SRUN_MEM_PER_CPU="${SRUN_MEM_PER_CPU:-9000}"

PREPROCESS_SCRIPTS=(
  "00_dicom_2_npy.py"
  "01_segment_slice_wise.py"
  "02_build3D_segmented_array.py"
  "02a_rotate_pic_to_align_with_axis.py"
  "02b_build_subvolume_arrays.py"
)

CONFIG_INFO=$(
  srun -n 1 --time="$SRUN_TIME" --mem-per-cpu="$SRUN_MEM_PER_CPU" apptainer exec --bind "$BIND_PATHS" "$CONTAINER_PATH" \
    python3 - "$CONFIG_PATH" <<'PYINFO'
import json
import sys
with open(sys.argv[1], "r") as handle:
    config = json.load(handle)
frac = config.get("fracture", {})
print(config["binning"]["label"])
print(config["01_segment_slice_wise"]["specimen_name"])
print(config["02b_build_subvolume_arrays"]["subvolume_output_folder"])
print(" ".join(frac.get("materials", ["std"])))
print(" ".join(frac.get("directions", ["y"])))
print(frac.get("mesh_file", "dlfx_mesh"))
print(frac.get("lam_param", 1.0))
print(frac.get("mue_param", 1.0))
print(frac.get("Gc_param", 1.0))
print(frac.get("eps_factor_param", 20.0))
print(frac.get("element_order", 2))
print(frac.get("fracture_toughness", "alsi10mg_as_built"))
PYINFO
)

binning_label="$(echo "$CONFIG_INFO" | sed -n '1p')"
run_name="$(echo "$CONFIG_INFO" | sed -n '2p')"
base_subvolume_container_path="$(echo "$CONFIG_INFO" | sed -n '3p')"
materials_line="$(echo "$CONFIG_INFO" | sed -n '4p')"
directions_line="$(echo "$CONFIG_INFO" | sed -n '5p')"
fracture_mesh_file="$(echo "$CONFIG_INFO" | sed -n '6p')"
fracture_lam="$(echo "$CONFIG_INFO" | sed -n '7p')"
fracture_mue="$(echo "$CONFIG_INFO" | sed -n '8p')"
fracture_gc="$(echo "$CONFIG_INFO" | sed -n '9p')"
fracture_eps_factor="$(echo "$CONFIG_INFO" | sed -n '10p')"
fracture_element_order="$(echo "$CONFIG_INFO" | sed -n '11p')"
fracture_toughness="$(echo "$CONFIG_INFO" | sed -n '12p')"
read -r -a MATERIALS <<< "$materials_line"
read -r -a DIRECTIONS <<< "$directions_line"
base_subvolume_folder="${base_subvolume_container_path/#\/data/$HPC_SCRATCH/pygalmesh/data}"
case_scratch="$working_directory/scratch/${run_name}_${SLURM_JOB_ID:-manual}"

rm -rf "$case_scratch"
mkdir -p "$case_scratch/tmp"

echo "Processing fracture case $binning_label"
echo "Using config: $CONFIG_PATH"
echo "Case scratch: $case_scratch"
echo "Fracture params: mesh=$fracture_mesh_file material_toughness=$fracture_toughness fallback_lam=$fracture_lam fallback_mue=$fracture_mue fallback_Gc=$fracture_gc eps_factor=$fracture_eps_factor order=$fracture_element_order"

run_container() {
  local ntasks="$1"
  local chdir="$2"
  local bind_paths="$3"
  local container="$4"
  shift 4
  local srun_args=(-n "$ntasks" --time="$SRUN_TIME" --mem-per-cpu="$SRUN_MEM_PER_CPU")
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
    echo "TMPDIR: $TMPDIR"
    apptainer exec --bind "$bind_paths,$case_scratch:$case_scratch" "$container" "$@"
  ' bash "$case_scratch" "$bind_paths" "$container" "$@"
}

write_voxel_cross_section() {
  local npy_path="$1"
  local stage_name="$2"
  local output_dir="$3"

  if [[ -f "$npy_path" ]]; then
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/02g_write_voxel_cross_sections.py" \
        --npy "$npy_path" \
        --output-dir "$output_dir" \
        --stage "$stage_name" \
        --axis z
  fi
}

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

for script in "${PREPROCESS_SCRIPTS[@]}"; do
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
    echo "Could not extract center_x and center_y from $folder_name"
    continue
  fi

  meshing_npy_file="$npy_file"
  cross_section_dir="$subfolder/voxel_cross_sections"
  write_voxel_cross_section "$meshing_npy_file" "00_original_subvolume" "$cross_section_dir"
  if [[ "$(config_bool 02c_voxel_topology_cleanup.enabled)" == "1" ]]; then
    cleaned_npy_file="$subfolder/$(config_value_default 02c_voxel_topology_cleanup.output_filename volume_topology_cleaned.npy)"
    voxel_report_file="$subfolder/$(config_value_default 02c_voxel_topology_cleanup.report_filename volume_topology.txt)"
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/02c_voxel_topology_cleanup.py" --config "$CONFIG_PATH" --npy "$npy_file" --output "$cleaned_npy_file" --report "$voxel_report_file"
    write_voxel_cross_section "$cleaned_npy_file" "01_topology_cleanup" "$cross_section_dir"
    if [[ "$(config_bool 02c_voxel_topology_cleanup.use_cleaned_for_meshing)" == "1" ]]; then
      meshing_npy_file="$cleaned_npy_file"
    fi
  fi


  if [[ "$(config_bool 02e_mirror_extrude_voxel.enabled)" == "1" ]]; then
    mirrored_npy_file="$subfolder/$(config_value_default 02e_mirror_extrude_voxel.output_filename volume_mirrored_x.npy)"
    mirrored_report_file="$subfolder/$(config_value_default 02e_mirror_extrude_voxel.report_filename volume_mirrored_x.txt)"
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/02e_mirror_extrude_voxel.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --output "$mirrored_npy_file" --report "$mirrored_report_file"
    write_voxel_cross_section "$mirrored_npy_file" "02_voxel_mirror" "$cross_section_dir"
    if [[ "$(config_bool 02e_mirror_extrude_voxel.use_mirrored_for_meshing)" == "1" ]]; then
      meshing_npy_file="$mirrored_npy_file"
    fi
  fi

  if [[ "$(config_bool 02d_axis_aligned_cuboid_crop.enabled)" == "1" ]]; then
    cuboid_npy_file="$subfolder/$(config_value_default 02d_axis_aligned_cuboid_crop.output_filename volume_cuboid.npy)"
    cuboid_report_file="$subfolder/$(config_value_default 02d_axis_aligned_cuboid_crop.report_filename volume_cuboid.txt)"
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/02d_axis_aligned_cuboid_crop.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --output "$cuboid_npy_file" --report "$cuboid_report_file"
    write_voxel_cross_section "$cuboid_npy_file" "03_internal_aniso_shell" "$cross_section_dir"
    if [[ "$(config_bool 02d_axis_aligned_cuboid_crop.use_cuboid_for_meshing)" == "1" ]]; then
      meshing_npy_file="$cuboid_npy_file"
    fi
  fi

  if [[ "$(config_bool 02f_add_voxel_shell.enabled)" == "1" ]]; then
    shelled_npy_file="$subfolder/$(config_value_default 02f_add_voxel_shell.output_filename volume_additive_shell.npy)"
    shelled_report_file="$subfolder/$(config_value_default 02f_add_voxel_shell.report_filename volume_additive_shell.txt)"
    run_container 1 "" "$BIND_PATHS" "$CONTAINER_PATH" \
      python3 "$working_directory/02f_add_voxel_shell.py" --config "$CONFIG_PATH" --npy "$meshing_npy_file" --output "$shelled_npy_file" --report "$shelled_report_file"
    write_voxel_cross_section "$shelled_npy_file" "04_external_shell" "$cross_section_dir"
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

for mat in "${MATERIALS[@]}"; do
  for dir in "${DIRECTIONS[@]}"; do
    final_output_dir="$working_directory/00_results/${SPECIMEN_NAME}/${binning_label}/${output_directory_variable}/${run_name}-${mat}-${dir}"
    for subfolder in "$base_subvolume_folder"/*/; do
      [ -d "$subfolder" ] || continue
      cp -v "$SOURCE_DIR"/* "$subfolder"
      cp -v "$CONFIG_HOST_PATH" "$subfolder/config.json"
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
    cp -rv "$base_subvolume_folder" "$final_output_dir/"
    cp -v "$working_directory/${run_name}_segmented/metadata.json" "$final_output_dir/" || true
    cp -v "$CONFIG_HOST_PATH" "$final_output_dir/" || true
  done
done

rm -rf "$case_scratch"
echo "Fracture run complete."
