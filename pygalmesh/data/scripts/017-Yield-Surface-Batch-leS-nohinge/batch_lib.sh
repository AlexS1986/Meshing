#!/usr/bin/env bash
#
# Gemeinsame Helfer der batch_*-Skripte in 015. Wird mit `source` eingebunden
# und laedt seinerseits config.sh.
#
# Namenskonvention einer Kombination (Datensatz x Anfangsfliessgrenze):
#
#   dataset id      JM-25-77
#   sig_y-Tag       075                      (dreistellig, aus 75 MPa)
#   run id          JM-25-77_les_r2          -> dataset.id in der Config,
#                                               bestimmt die Netzordner
#   binning label   leS-r2-sigy075           -> zweite Ebene unter 00_results/
#   combo id        JM-25-77_sigy075
#   Config          config-JM-25-77-r2-sigy075.json
#   Job-Ordner      yield_surface_jobs/JM-25-77_sigy075/n096/
#   Ergebnisse      00_results/JM-25-77_les_r2/leS-r2-sigy075/yield_surface/...
#
# Wichtig: die run id enthaelt KEIN sig_y. Das Netz haengt nicht von der
# Fliessgrenze ab, beide sig_y-Varianten eines Datensatzes teilen sich also
# dasselbe vorbereitete Netz und die Netzvorbereitung laeuft nur einmal je
# Datensatz. Getrennt werden die Laeufe ueber das binning label.

set -euo pipefail

BATCH_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$BATCH_LIB_DIR/config.sh"

PROJECT_NAME="$(basename "$BATCH_LIB_DIR")"
PROJECT_CONTAINER_DIR="/data/scripts/$PROJECT_NAME"

# --- Pfadabbildung Container <-> Host ----------------------------------------
batch_container_to_host() {
  local p="$1"
  if [[ "$p" == /data/* || "$p" == /data ]]; then
    if [[ -n "${HPC_SCRATCH:-}" ]]; then
      printf '%s\n' "${p/#\/data/$HPC_SCRATCH/pygalmesh/data}"
    else
      # Lokal (Mac/Container ohne Cluster): relativ zum Projektordner raten.
      printf '%s\n' "${p/#\/data\/scripts\/$PROJECT_NAME/$BATCH_LIB_DIR}"
    fi
  else
    printf '%s\n' "$p"
  fi
}

# --- Namen -------------------------------------------------------------------
batch_sigy_tag()      { printf '%03d\n' "$1"; }
batch_run_id()        { printf '%s_les_r%s\n' "$1" "${LES_REDUCE_FACTOR}"; }
batch_binning_label() { printf 'leS-r%s-sigy%s\n' "${LES_REDUCE_FACTOR}" "$(batch_sigy_tag "$2")"; }
batch_combo_id()      { printf '%s_sigy%s\n' "$1" "$(batch_sigy_tag "$2")"; }
batch_config_name()   { printf 'config-%s-r%s-sigy%s.json\n' "$1" "${LES_REDUCE_FACTOR}" "$(batch_sigy_tag "$2")"; }
batch_points_tag()    { printf 'n%03d\n' "${YIELD_SURFACE_POINTS}"; }
batch_jobs_dir_rel()  { printf 'yield_surface_jobs/%s/%s\n' "$(batch_combo_id "$1" "$2")" "$(batch_points_tag)"; }

# --- Datensaetze -------------------------------------------------------------
batch_dataset_ids() {
  local entry
  for entry in "${BATCH_DATASETS[@]}"; do
    printf '%s\n' "${entry%%|*}"
  done
}

batch_dataset_filename() {
  local want="$1" entry
  for entry in "${BATCH_DATASETS[@]}"; do
    if [[ "${entry%%|*}" == "$want" ]]; then
      printf '%s\n' "${entry#*|}"
      return 0
    fi
  done
  echo "Unbekannter Datensatz: $want" >&2
  return 1
}

# Container-Pfad der .leS-Datei. Existiert der konfigurierte Dateiname auf dem
# Host nicht, wird per Glob nach einer passenden Datei gesucht (die Namen der
# Datensaetze mischen "-" und "_" nach der Scan-Nummer).
batch_dataset_les_path() {
  local ds="$1"
  local filename; filename="$(batch_dataset_filename "$ds")"
  local host_dir;  host_dir="$(batch_container_to_host "$LES_RESOURCE_DIR")"

  if [[ -f "$host_dir/$filename" ]]; then
    printf '%s/%s\n' "$LES_RESOURCE_DIR" "$filename"
    return 0
  fi
  if [[ -d "$host_dir" ]]; then
    local prefix="${ds%-*}" number="${ds##*-}" hit=() f
    shopt -s nullglob
    for f in "$host_dir/$prefix"[-_]"$number"*.leS "$host_dir/$prefix"[-_]"$number"*.les; do
      hit+=("$f")
    done
    shopt -u nullglob
    if [[ "${#hit[@]}" -eq 1 ]]; then
      echo "[INFO] $ds: '$filename' nicht gefunden, verwende $(basename "${hit[0]}")" >&2
      printf '%s/%s\n' "$LES_RESOURCE_DIR" "$(basename "${hit[0]}")"
      return 0
    fi
    if [[ "${#hit[@]}" -gt 1 ]]; then
      echo "[FEHLER] $ds: mehrere passende .leS-Dateien in $host_dir:" >&2
      printf '         %s\n' "${hit[@]}" >&2
      return 2
    fi
    echo "[FEHLER] $ds: weder '$filename' noch '$prefix[-_]$number*.leS' in $host_dir" >&2
    return 2
  fi
  # Host-Ordner nicht sichtbar (z.B. Generierung auf dem Mac): Namen so
  # uebernehmen, wie er in config.sh steht. Der Prepare-Job prueft spaeter.
  echo "[WARNUNG] $host_dir nicht vorhanden - verwende '$filename' ungeprueft." >&2
  printf '%s/%s\n' "$LES_RESOURCE_DIR" "$filename"
}

# --- Kombinationen -----------------------------------------------------------
# Gibt je Zeile aus:  <dataset> <sig_y> <combo_id> <config_name> <jobs_dir_rel>
# Beruecksichtigt die Filter ONLY_DATASETS und ONLY_SIG_Y.
batch_combos() {
  local ds sig
  for ds in $(batch_dataset_ids); do
    if [[ -n "${ONLY_DATASETS// /}" ]] && [[ " $ONLY_DATASETS " != *" $ds "* ]]; then
      continue
    fi
    for sig in $BATCH_SIG_Y; do
      if [[ -n "${ONLY_SIG_Y// /}" ]] && [[ " $ONLY_SIG_Y " != *" $sig "* ]]; then
        continue
      fi
      printf '%s %s %s %s %s\n' \
        "$ds" "$sig" "$(batch_combo_id "$ds" "$sig")" \
        "$(batch_config_name "$ds" "$sig")" "$(batch_jobs_dir_rel "$ds" "$sig")"
    done
  done
}

# Datensaetze, die nach der Filterung uebrig bleiben (fuer die Netzvorbereitung).
batch_active_datasets() {
  batch_combos | awk '{print $1}' | awk '!seen[$0]++'
}

batch_require_scratch() {
  if [[ -z "${HPC_SCRATCH:-}" ]]; then
    echo "HPC_SCRATCH ist nicht gesetzt - dieses Skript gehoert auf den Cluster." >&2
    exit 2
  fi
}

batch_print_plan() {
  local line ds sig combo cfg jobs
  echo "Projekt        : $PROJECT_NAME"
  echo "reduce         : $LES_REDUCE_FACTOR   Elementgroesse: ${LES_MAX_ELEMENT_SIZE_UM} um"
  echo "Punkte je Kombi: $YIELD_SURFACE_POINTS   Radius: $YIELD_SURFACE_STRAIN_RADIUS"
  echo "Punkt-Job      : -n $YIELD_JOB_NTASKS  --mem-per-cpu=$YIELD_JOB_MEM_PER_CPU  -t $YIELD_JOB_TIME  -p ${YIELD_JOB_PARTITION:-deflt}  -C $YIELD_JOB_CONSTRAINT"
  echo "Kombinationen  :"
  while read -r ds sig combo cfg jobs; do
    [[ -n "$ds" ]] || continue
    printf '  %-18s sig_y=%-4s %-42s %s\n' "$ds" "$sig" "$cfg" "$jobs"
  done < <(batch_combos)
}
