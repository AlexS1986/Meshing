#!/bin/bash
#
# Erzeugt die Configs der Aufloesungsfamilie aus config.sh.
#
#   ./create_fracture_config.sh                 # alle Stufen aus MESH_TIERS
#   ONLY_TIERS="coarse" ./create_fracture_config.sh
#   LES_BAR_Y_MM=12 LES_BAR_Z_MM=4 ./create_fracture_config.sh  # Riegel statt ganzer Probe
#   LES_MIRROR_X_REPETITIONS=2 ./create_fracture_config.sh      # zweimal spiegeln wie 011
#
# Gitter und Voxelgroesse werden, wenn moeglich, aus der .leS-Datei gelesen.
# Ist die Datei hier nicht erreichbar (z.B. auf dem Mac), muessen LES_GRID und
# LES_VOXEL_SIZE_M in config.sh gesetzt werden - sonst entsteht eine Config
# ohne Riegel-Crop, die das volle Volumen vernetzen wuerde.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# --- Gitter und Voxelgroesse -------------------------------------------------
les_host_path="${LES_INPUT/#\/data/${HPC_SCRATCH:-}/pygalmesh/data}"
if [[ -z "${LES_GRID}" || -z "${LES_VOXEL_SIZE_M}" ]]; then
  for candidate in "$les_host_path" "$SCRIPT_DIR/A01_segmented/$LES_FILENAME" "$LES_INPUT"; do
    if [[ -f "$candidate" ]]; then
      echo "Lese .leS-Header: $candidate"
      eval "$(python3 "$SCRIPT_DIR/A04_les_header_info.py" "$candidate" --format shell)"
      break
    fi
  done
fi

if [[ -z "${LES_GRID}" || -z "${LES_VOXEL_SIZE_M}" ]]; then
  echo "WARNUNG: .leS-Datei nicht erreichbar und LES_GRID/LES_VOXEL_SIZE_M nicht" >&2
  echo "         gesetzt. Die Configs bekommen KEINEN Riegel-Ausschnitt." >&2
  echo "         Auf dem Cluster nachholen:" >&2
  echo "           python3 A04_les_header_info.py $LES_INPUT --format shell" >&2
  grid_args=()
  voxel_args=()
else
  read -r -a grid <<< "$LES_GRID"
  grid_args=(--grid "${grid[0]}" "${grid[1]}" "${grid[2]}")
  voxel_args=(--voxel-size "$LES_VOXEL_SIZE_M")
  echo "Gitter: ${grid[*]}   Voxelgroesse: $LES_VOXEL_SIZE_M m"
fi

# Riegel-Ausschnitt: leer = ganze Achse. Seit 2026-09-02 ist der Default die
# GANZE Probe (alle drei leer), gespiegelt ueber LES_MIRROR_X_REPETITIONS.
bar_args=()
[[ -n "$LES_BAR_X_MM" ]] && bar_args+=(--bar-x-mm "$LES_BAR_X_MM")
[[ -n "$LES_BAR_Y_MM" ]] && bar_args+=(--bar-y-mm "$LES_BAR_Y_MM")
[[ -n "$LES_BAR_Z_MM" ]] && bar_args+=(--bar-z-mm "$LES_BAR_Z_MM")
[[ -n "$LES_MIRROR_X_REPETITIONS" ]] && bar_args+=(--mirror-x-repetitions "$LES_MIRROR_X_REPETITIONS")

shell_args=()
[[ -n "$LES_BOUNDARY_SHELL_XZ" ]] && shell_args+=(--boundary-shell-xz "$LES_BOUNDARY_SHELL_XZ")
[[ -n "$LES_BOUNDARY_SHELL_Y" ]] && shell_args+=(--boundary-shell-y "$LES_BOUNDARY_SHELL_Y")

keep_args=()
[[ "$LES_KEEP_LARGEST_COMPONENT" == "true" ]] && keep_args+=(--keep-largest-component)

# Randschale: extern (02f, wie 011) / seal (02d, wie 015) / none
shell_mode_args=(--shell-mode "$LES_SHELL_MODE")
[[ -n "$LES_SHELL_UM" ]] && shell_mode_args+=(--shell-um "$LES_SHELL_UM")
[[ -n "$LES_SHELL_VOXELS" ]] && shell_mode_args+=(--shell-voxels "$LES_SHELL_VOXELS")
[[ -n "$LES_SHELL_X_UM" ]] && shell_mode_args+=(--shell-x-um "$LES_SHELL_X_UM")
[[ -n "$LES_SHELL_VOXELS_X" ]] && shell_mode_args+=(--shell-voxels-x "$LES_SHELL_VOXELS_X")
[[ "$LES_SNAP_MESH_TO_BOX" == "true" ]] && shell_mode_args+=(--snap-mesh-to-box) || shell_mode_args+=(--no-snap-mesh-to-box)
shell_mode_args+=(--facet-distance-ratio "$LES_FACET_DISTANCE_RATIO")

# --- Stufen durchgehen -------------------------------------------------------
for entry in "${MESH_TIERS[@]}"; do
  IFS='|' read -r tier reduce element_um <<< "$entry"
  if [[ -n "$ONLY_TIERS" ]] && ! grep -qw "$tier" <<< "$ONLY_TIERS"; then
    continue
  fi
  [[ -n "$LES_REDUCE_FACTOR" ]] && reduce="$LES_REDUCE_FACTOR"
  [[ -n "$LES_MAX_ELEMENT_SIZE_UM" ]] && element_um="$LES_MAX_ELEMENT_SIZE_UM"

  dataset_id="${SPECIMEN_NAME}_les_fracture_${tier}"
  output="config-fracture-${SPECIMEN_NAME}-${tier}.json"

  echo
  echo "=== Stufe $tier: reduce=$reduce, Elementgroesse=${element_um} um ==="
  python3 "$SCRIPT_DIR/create_fracture_config.py" \
    --base-config "$LES_BASE_CONFIG" \
    --output "$output" \
    --tier "$tier" \
    --specimen "$SPECIMEN_NAME" \
    --dataset-id "$dataset_id" \
    --les-input "$LES_INPUT" \
    --reduce "$reduce" \
    --reduce-mode "$LES_REDUCE_MODE" \
    --reduce-threshold "$LES_REDUCE_THRESHOLD" \
    --smooth-sigma "$LES_SMOOTH_SIGMA" \
    --line-order "$LES_LINE_ORDER" \
    --les-material-value "$LES_MATERIAL_VALUE" \
    --bounds-mode "$LES_BOUNDS_MODE" \
    --voxel-size-unit "$LES_VOXEL_SIZE_UNIT" \
    --xy-divisions "$LES_XY_DIVISIONS" \
    --sdf-pad-width "$LES_SDF_PAD_WIDTH" \
    --max-element-size-um "$element_um" \
    --boundary-shell-elements "$LES_BOUNDARY_SHELL_ELEMENTS" \
    --eps-factor "$FRACTURE_EPS_FACTOR_PARAM" \
    --element-order "$FRACTURE_ELEMENT_ORDER" \
    --lam-param "$FRACTURE_LAM_PARAM" \
    --mue-param "$FRACTURE_MUE_PARAM" \
    --gc-param "$FRACTURE_GC_PARAM" \
    --fracture-toughness-name "$FRACTURE_TOUGHNESS" \
    --fracture-materials $FRACTURE_MATERIALS \
    --fracture-directions $FRACTURE_DIRECTIONS \
    "${grid_args[@]}" "${voxel_args[@]}" "${bar_args[@]}" \
    "${shell_args[@]}" "${shell_mode_args[@]}" "${keep_args[@]}"
done

echo
echo "Fertig. Default-Stufe der Jobskripte: $DEFAULT_TIER"
echo "  -> config-fracture-${SPECIMEN_NAME}-${DEFAULT_TIER}.json"
