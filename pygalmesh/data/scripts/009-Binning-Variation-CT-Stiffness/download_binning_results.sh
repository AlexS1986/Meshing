#!/usr/bin/env bash
if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi

set -euo pipefail

# Download reduced binning result artifacts from the TU Darmstadt cluster.
# Run this from inside the pygalmesh container or from this script directory.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_BASE="${LOCAL_BASE:-$SCRIPT_DIR}"
RESULTS_DIR="${RESULTS_DIR:-$LOCAL_BASE/results}"

REMOTE_HOST="${REMOTE_HOST:-as12vapa@lcluster15.hrz.tu-darmstadt.de}"
REMOTE_BASE="${REMOTE_BASE:-/work/scratch/as12vapa/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness}"
SPECIMEN_NAME="${SPECIMEN_NAME:-JM-25-74}"
SUBVOLUME_DIR="${SUBVOLUME_DIR:-subvolume_x160_y160}"
SSH_BIN="${SSH_BIN:-ssh}"
SCP_BIN="${SCP_BIN:-scp}"
ONLY_BIN="${ONLY_BIN:-}"
ONLY_REDUCE="${ONLY_REDUCE:-}"
ONLY_CASE="${ONLY_CASE:-}"

usage() {
  cat <<'EOF'
Usage: download_binning_results.sh [options]

Options:
  --bin VALUE       Download only cases with this binning value.
  --reduce VALUE    Download only cases with this reduce value, e.g. null, 2, 4, or 8.
  --case NAME       Download only this exact canonical case folder name.
  -h, --help        Show this help.

Examples:
  ./download_binning_results.sh --bin 1 --reduce null
  ./download_binning_results.sh --case JM-25-74_Bin1_reduce-null_segmented
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --bin)
      [[ "$#" -ge 2 ]] || { printf 'Missing value for --bin\n' >&2; exit 2; }
      ONLY_BIN="$2"
      shift 2
      ;;
    --reduce)
      [[ "$#" -ge 2 ]] || { printf 'Missing value for --reduce\n' >&2; exit 2; }
      ONLY_REDUCE="$2"
      shift 2
      ;;
    --case)
      [[ "$#" -ge 2 ]] || { printf 'Missing value for --case\n' >&2; exit 2; }
      ONLY_CASE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

CASE_ROOT="$RESULTS_DIR/cases"
REMOTE_CONFIG_DIR="$RESULTS_DIR/remote_configs"
OVERVIEW_CSV="$RESULTS_DIR/download_overview.csv"

SSH_CONTROL_DIR="${SSH_CONTROL_DIR:-/tmp/pygalmesh-009-binning-ssh}"
SSH_CONTROL_SOCKET="$SSH_CONTROL_DIR/%C"
USE_CONTROLMASTER="${USE_CONTROLMASTER:-1}"
DISABLE_PUBKEY_AUTH="${DISABLE_PUBKEY_AUTH:-1}"
FORCE_IPV4="${FORCE_IPV4:-1}"
ACCEPT_NEW_HOST_KEYS="${ACCEPT_NEW_HOST_KEYS:-1}"
SSH_OPTS=(-o ServerAliveInterval=30 -o ServerAliveCountMax=4)
SCP_OPTS=()

mkdir -p "$CASE_ROOT" "$REMOTE_CONFIG_DIR" "$SSH_CONTROL_DIR"

require_command() {
  local command_name="$1"
  local package_hint="$2"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Required command not found: %s\n' "$command_name" >&2
    printf 'Install %s in the pygalmesh container, or set %s_BIN to an available executable.\n' "$package_hint" "${command_name^^}" >&2
    printf 'For Debian/Ubuntu containers, this is usually:\n' >&2
    printf '  apt-get update && apt-get install -y openssh-client\n' >&2
    exit 127
  fi
}

require_command "$SSH_BIN" "openssh-client"
require_command "$SCP_BIN" "openssh-client"

if [[ "$USE_CONTROLMASTER" == "1" ]]; then
  SSH_OPTS+=(-o ControlMaster=auto -o ControlPersist=15m -o ControlPath="$SSH_CONTROL_SOCKET")
  SCP_OPTS+=(-o ControlMaster=auto -o ControlPersist=15m -o ControlPath="$SSH_CONTROL_SOCKET")
fi

if [[ "$DISABLE_PUBKEY_AUTH" == "1" ]]; then
  SSH_OPTS+=(-o PubkeyAuthentication=no -o IdentitiesOnly=yes -o GSSAPIAuthentication=no -o PreferredAuthentications=keyboard-interactive,password)
  SCP_OPTS+=(-o PubkeyAuthentication=no -o IdentitiesOnly=yes -o GSSAPIAuthentication=no -o PreferredAuthentications=keyboard-interactive,password)
fi

if [[ "$FORCE_IPV4" == "1" ]]; then
  SSH_OPTS+=(-o AddressFamily=inet)
  SCP_OPTS+=(-o AddressFamily=inet)
fi

if [[ "$ACCEPT_NEW_HOST_KEYS" == "1" ]]; then
  SSH_OPTS+=(-o StrictHostKeyChecking=accept-new)
  SCP_OPTS+=(-o StrictHostKeyChecking=accept-new)
fi

ssh_remote() {
  "$SSH_BIN" "${SSH_OPTS[@]}" "$REMOTE_HOST" "$@"
}

scp_from_remote() {
  local remote_path="$1"
  local local_path="$2"
  "$SCP_BIN" "${SCP_OPTS[@]}" "$REMOTE_HOST:$remote_path" "$local_path"
}

csv_escape() {
  local value="${1:-}"
  value="${value//\"/\"\"}"
  printf '"%s"' "$value"
}

ensure_overview_header() {
  if [[ ! -s "$OVERVIEW_CSV" ]]; then
    {
      printf 'case_name,bin,reduce,remote_case_dir,local_case_dir,case_found,config_status,out_status,metadata_status,Chom_json,E_moduli_json,G_moduli_json,vol_json,dlfx_mesh_xdmf,dlfx_mesh_h5,out_metrics_status,notes\n'
    } > "$OVERVIEW_CSV"
  fi
}

append_overview_row() {
  local case_name="$1"
  local bin_value="$2"
  local reduce_value="$3"
  local remote_case_dir="$4"
  local local_case_dir="$5"
  local case_found="$6"
  local config_status="$7"
  local out_status="$8"
  local metadata_status="$9"
  local chom_status="${10}"
  local e_status="${11}"
  local g_status="${12}"
  local vol_status="${13}"
  local xdmf_status="${14}"
  local h5_status="${15}"
  local metrics_status="${16}"
  local notes="${17}"

  {
    csv_escape "$case_name"; printf ','
    csv_escape "$bin_value"; printf ','
    csv_escape "$reduce_value"; printf ','
    csv_escape "$remote_case_dir"; printf ','
    csv_escape "$local_case_dir"; printf ','
    csv_escape "$case_found"; printf ','
    csv_escape "$config_status"; printf ','
    csv_escape "$out_status"; printf ','
    csv_escape "$metadata_status"; printf ','
    csv_escape "$chom_status"; printf ','
    csv_escape "$e_status"; printf ','
    csv_escape "$g_status"; printf ','
    csv_escape "$vol_status"; printf ','
    csv_escape "$xdmf_status"; printf ','
    csv_escape "$h5_status"; printf ','
    csv_escape "$metrics_status"; printf ','
    csv_escape "$notes"; printf '\n'
  } >> "$OVERVIEW_CSV"
}

remote_exists() {
  local remote_path="$1"
  ssh_remote "test -e $(printf '%q' "$remote_path")"
}

fail_remote_command() {
  local message="$1"
  printf '%s\n' "$message" >&2
  printf 'Check SSH/2FA access to %s and rerun the script.\n' "$REMOTE_HOST" >&2
  exit 1
}

download_if_exists() {
  local remote_path="$1"
  local local_path="$2"
  mkdir -p "$(dirname "$local_path")"
  if remote_exists "$remote_path"; then
    scp_from_remote "$remote_path" "$local_path" >/dev/null
    printf 'downloaded'
  else
    printf 'missing'
  fi
}

find_remote_subvolume_dir() {
  local remote_3d_dir="$1"
  ssh_remote "REMOTE_3D_DIR=$(printf '%q' "$remote_3d_dir") python3 - <<'PY'
import os
from pathlib import Path

base = Path(os.environ['REMOTE_3D_DIR'])
if not base.is_dir():
    raise SystemExit(0)

subvolumes = sorted(path for path in base.iterdir() if path.is_dir() and path.name.startswith('subvolume_'))
if not subvolumes:
    raise SystemExit(0)

required = ['Chom.json', 'E_moduli.json', 'G_moduli.json', 'vol.json', 'dlfx_mesh.xdmf', 'dlfx_mesh.h5']

def score(path):
    return sum((path / name).exists() for name in required)

best = max(subvolumes, key=lambda path: (score(path), path.name))
print(best.name)
PY"
}

extract_remote_out_excerpt() {
  local remote_out_file="$1"
  local local_excerpt="$2"

  mkdir -p "$(dirname "$local_excerpt")"
  ssh_remote "awk '
    /^=== Homogenization Box Boundaries ===/ { capture = 1 }
    /^=== Total Domain Boundaries ===/ { capture = 1 }
    capture { print }
    capture && /^solving fem problem with [0-9]+ dofs/ { capture = 0 }
    /Wrote [0-9]+ rows? to .*binning_summary[.]csv/ { summary = \$0 }
    END {
      if (summary != \"\") {
        print summary
      }
    }
  ' $(printf '%q' "$remote_out_file")" > "$local_excerpt"

  [[ -s "$local_excerpt" ]]
}

extract_out_metrics() {
  local out_file="$1"
  local json_file="$2"
  local csv_file="$3"

  python3 - "$out_file" "$json_file" "$csv_file" <<'PY'
import csv
import json
import re
import sys
from pathlib import Path

out_path = Path(sys.argv[1])
json_path = Path(sys.argv[2])
csv_path = Path(sys.argv[3])
text = out_path.read_text(errors="replace")

def section_between(start, end=None):
    start_idx = text.find(start)
    if start_idx < 0:
        return ""
    start_idx += len(start)
    if end:
        end_idx = text.find(end, start_idx)
        if end_idx >= 0:
            return text[start_idx:end_idx]
    return text[start_idx:]

def parse_bounds(block):
    result = {}
    for axis in ("x", "y", "z"):
        match = re.search(rf"^{axis}:\s*\[([^\],]+),\s*([^\]]+)\]", block, re.MULTILINE)
        if match:
            result[f"{axis}_min"] = float(match.group(1))
            result[f"{axis}_max"] = float(match.group(2))
    return result

hom_block = section_between("=== Homogenization Box Boundaries ===", "=== Total Domain Boundaries ===")
total_block = section_between("=== Total Domain Boundaries ===")

metrics = {}
for key, value in parse_bounds(hom_block).items():
    metrics[f"homogenization_{key}"] = value
for key, value in parse_bounds(total_block).items():
    metrics[f"total_domain_{key}"] = value

patterns = {
    "homogenization_cuboid_volume": r"Volume of Cuboid for Homogenization:\s*([-+0-9.eE]+)",
    "homogenization_real_material_volume": r"Volume of Real Material in Homogenization Box:\s*([-+0-9.eE]+)",
    "total_domain_cuboid_volume": r"Volume of Cuboid Total:\s*([-+0-9.eE]+)",
    "fem_dofs": r"solving fem problem with\s+([0-9]+)\s+dofs",
}

for key, pattern in patterns.items():
    match = re.search(pattern, text)
    if match:
        raw = match.group(1)
        metrics[key] = int(raw) if key == "fem_dofs" else float(raw)

summary_matches = re.findall(r"^Wrote [0-9]+ rows? to .*binning_summary[.]csv$", text, re.MULTILINE)
if summary_matches:
    metrics["summary_write_line"] = summary_matches[-1]

json_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")

fieldnames = [
    "out_file",
    "homogenization_x_min",
    "homogenization_x_max",
    "homogenization_y_min",
    "homogenization_y_max",
    "homogenization_z_min",
    "homogenization_z_max",
    "homogenization_cuboid_volume",
    "homogenization_real_material_volume",
    "total_domain_x_min",
    "total_domain_x_max",
    "total_domain_y_min",
    "total_domain_y_max",
    "total_domain_z_min",
    "total_domain_z_max",
    "total_domain_cuboid_volume",
    "fem_dofs",
    "summary_write_line",
]
row = {"out_file": out_path.name}
row.update(metrics)
with csv_path.open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerow(row)
PY
}

download_global_configs() {
  local status
  status="$(download_if_exists "$REMOTE_BASE/config.json" "$REMOTE_CONFIG_DIR/config.json")"
  printf 'Global config.json: %s\n' "$status"
}

discover_case_folders() {
  ssh_remote "REMOTE_BASE=$(printf '%q' "$REMOTE_BASE") python3 - <<'PY'
import os
from pathlib import Path

base = Path(os.environ['REMOTE_BASE'])
for path in sorted(base.iterdir()):
    if not path.is_dir():
        continue
    name = path.name
    if '_Bin' not in name or '_reduce-' not in name:
        continue
    if name.endswith('_segmented') or name.endswith('_segmented_3D'):
        print(name)
PY"
}

discover_config_files() {
  ssh_remote "find $(printf '%q' "$REMOTE_BASE") -maxdepth 1 -type f -name 'config-Bin*-reduce-*.json' -printf '%f\n' | sort"
}

find_remote_out_file() {
  local bin_value="$1"
  local reduce_value="$2"
  local reduce_out="$reduce_value"
  if [[ "$reduce_out" == "null" ]]; then
    reduce_out="n"
  fi
  local out_pattern="$REMOTE_BASE/eb-b${bin_value}-r${reduce_out}.out.*"
  ssh_remote "ls -1t $out_pattern 2>/dev/null | head -n 1"
}

main() {
  printf 'Remote host: %s\n' "$REMOTE_HOST"
  printf 'Remote base: %s\n' "$REMOTE_BASE"
  printf 'Local results: %s\n' "$RESULTS_DIR"
  printf 'The first SSH/SCP operation may ask for cluster 2FA.\n\n'

  ensure_overview_header

  records_file="$RESULTS_DIR/.case_records.tsv"
  case_list_file="$RESULTS_DIR/.case_list.tsv"
  : > "$records_file"

  if ! download_global_configs; then
    fail_remote_command "Could not access the remote base path while downloading config.json."
  fi

  if ! discover_case_folders > "$RESULTS_DIR/.remote_case_folders.txt"; then
    fail_remote_command "Could not list remote case folders."
  fi

  if ! discover_config_files > "$RESULTS_DIR/.remote_config_files.txt"; then
    fail_remote_command "Could not list remote config files."
  fi

  while IFS= read -r case_name; do
    [[ -n "$case_name" ]] || continue
    if [[ "$case_name" =~ ^(.+)_Bin([0-9]+)_reduce-([^_]+)_segmented_3D$ ]]; then
      canonical_case_name="${BASH_REMATCH[1]}_Bin${BASH_REMATCH[2]}_reduce-${BASH_REMATCH[3]}_segmented"
      printf '%s\t%s\t%s\tfolder3d\n' "$canonical_case_name" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}" >> "$records_file"
    elif [[ "$case_name" =~ ^(.+)_Bin([0-9]+)_reduce-([^_]+)_segmented$ ]]; then
      printf '%s\t%s\t%s\tfolder\n' "$case_name" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}" >> "$records_file"
    else
      printf '%s\t\t\tfolder\n' "$case_name" >> "$records_file"
    fi
  done < "$RESULTS_DIR/.remote_case_folders.txt"

  while IFS= read -r config_name; do
    [[ -n "$config_name" ]] || continue
    if [[ "$config_name" =~ ^config-Bin([0-9]+)-reduce-(.+)\.json$ ]]; then
      bin_value="${BASH_REMATCH[1]}"
      reduce_value="${BASH_REMATCH[2]}"
      case_name="${SPECIMEN_NAME}_Bin${bin_value}_reduce-${reduce_value}_segmented"
      printf '%s\t%s\t%s\tconfig\n' "$case_name" "$bin_value" "$reduce_value" >> "$records_file"
    fi
  done < "$RESULTS_DIR/.remote_config_files.txt"

  if [[ ! -s "$records_file" ]]; then
    printf 'No remote case folders or config-Bin*-reduce-*.json files found. Wrote empty overview to %s\n' "$OVERVIEW_CSV" >&2
    exit 1
  fi

  awk -F '\t' '
    BEGIN { OFS = FS }
    {
      if (current != "" && $1 != current) {
        reduce_sort = reduce_value == "null" ? 0 : reduce_value + 0
        print bin_value + 0, reduce_sort, current, bin_value, reduce_value, sources
        sources = ""
      }
      current = $1
      bin_value = $2
      reduce_value = $3
      if (sources == "") {
        sources = $4
      } else if (index("\t" sources "\t", "\t" $4 "\t") == 0) {
        sources = sources "+" $4
      }
    }
    END {
      if (current != "") {
        reduce_sort = reduce_value == "null" ? 0 : reduce_value + 0
        print bin_value + 0, reduce_sort, current, bin_value, reduce_value, sources
      }
    }
  ' < <(sort -t $'\t' -k1,1 "$records_file") | sort -t $'\t' -k1,1nr -k2,2nr | cut -f3- > "$case_list_file"

  if [[ -n "$ONLY_BIN" || -n "$ONLY_REDUCE" || -n "$ONLY_CASE" ]]; then
    filtered_case_list="$RESULTS_DIR/.case_list.filtered.tsv"
    awk -F '\t' \
      -v only_bin="$ONLY_BIN" \
      -v only_reduce="$ONLY_REDUCE" \
      -v only_case="$ONLY_CASE" '
        (only_bin == "" || $2 == only_bin) &&
        (only_reduce == "" || $3 == only_reduce) &&
        (only_case == "" || $1 == only_case)
      ' "$case_list_file" > "$filtered_case_list"
    mv "$filtered_case_list" "$case_list_file"
  fi

  if [[ ! -s "$case_list_file" ]]; then
    printf 'No remote cases matched the requested filter' >&2
    [[ -n "$ONLY_BIN" ]] && printf ' --bin %s' "$ONLY_BIN" >&2
    [[ -n "$ONLY_REDUCE" ]] && printf ' --reduce %s' "$ONLY_REDUCE" >&2
    [[ -n "$ONLY_CASE" ]] && printf ' --case %s' "$ONLY_CASE" >&2
    printf '.\n' >&2
    exit 1
  fi

  case_count="$(wc -l < "$case_list_file" | tr -d ' ')"
  printf 'Discovered %s case(s):\n' "$case_count"
  cut -f1-3 "$case_list_file" | sed 's/\t/ /g; s/^/  /'

  while IFS=$'\t' read -r -u 3 case_name bin_value reduce_value sources; do
    if [[ ! "$case_name" =~ ^(.+)_Bin([0-9]+)_reduce-([^_]+)_segmented$ ]]; then
      append_overview_row "$case_name" "" "" "$REMOTE_BASE/$case_name" "" "found" "skipped" "skipped" "skipped" "skipped" "skipped" "skipped" "skipped" "skipped" "skipped" "skipped" "Could not parse Bin/reduce from folder name."
      continue
    fi

    bin_value="${bin_value:-${BASH_REMATCH[2]}}"
    reduce_value="${reduce_value:-${BASH_REMATCH[3]}}"
    remote_case_dir="$REMOTE_BASE/$case_name"
    remote_3d_dir="$remote_case_dir/${case_name}_3D"
    if [[ "$sources" == *folder3d* ]]; then
      remote_3d_dir="$REMOTE_BASE/${case_name}_3D"
    fi
    local_case_dir="$CASE_ROOT/$case_name"
    case_found="missing"
    if [[ "$sources" == *folder* || "$sources" == *folder3d* ]]; then
      case_found="found"
    fi
    remote_subvolume_dir="$(find_remote_subvolume_dir "$remote_3d_dir" || true)"
    if [[ -z "$remote_subvolume_dir" ]]; then
      remote_subvolume_dir="$SUBVOLUME_DIR"
    fi
    local_subvolume_dir="$local_case_dir/${case_name}_3D/$remote_subvolume_dir"
    mkdir -p "$local_subvolume_dir" "$local_case_dir/out"

    printf '\nDownloading %s (Bin=%s, reduce=%s, case=%s, subvolume=%s)\n' "$case_name" "$bin_value" "$reduce_value" "$case_found" "$remote_subvolume_dir"

    config_status="$(download_if_exists "$REMOTE_BASE/config-Bin${bin_value}-reduce-${reduce_value}.json" "$local_case_dir/config-Bin${bin_value}-reduce-${reduce_value}.json")"
    metadata_status="$(download_if_exists "$remote_case_dir/metadata.json" "$local_case_dir/metadata.json")"
    chom_status="$(download_if_exists "$remote_3d_dir/$remote_subvolume_dir/Chom.json" "$local_subvolume_dir/Chom.json")"
    e_status="$(download_if_exists "$remote_3d_dir/$remote_subvolume_dir/E_moduli.json" "$local_subvolume_dir/E_moduli.json")"
    g_status="$(download_if_exists "$remote_3d_dir/$remote_subvolume_dir/G_moduli.json" "$local_subvolume_dir/G_moduli.json")"
    vol_status="$(download_if_exists "$remote_3d_dir/$remote_subvolume_dir/vol.json" "$local_subvolume_dir/vol.json")"
    volume_status="$(download_if_exists "$remote_3d_dir/$remote_subvolume_dir/volume.npy" "$local_subvolume_dir/volume.npy")"
    xdmf_status="$(download_if_exists "$remote_3d_dir/$remote_subvolume_dir/dlfx_mesh.xdmf" "$local_subvolume_dir/dlfx_mesh.xdmf")"
    h5_status="$(download_if_exists "$remote_3d_dir/$remote_subvolume_dir/dlfx_mesh.h5" "$local_subvolume_dir/dlfx_mesh.h5")"

    out_status="missing"
    metrics_status="missing"
    notes=""
    remote_out_file="$(find_remote_out_file "$bin_value" "$reduce_value" || true)"
    if [[ -n "$remote_out_file" ]]; then
      out_excerpt="$local_case_dir/out/out_excerpt.txt"
      if extract_remote_out_excerpt "$remote_out_file" "$out_excerpt"; then
        out_status="excerpted"
      else
        out_status="empty_excerpt"
        notes="Found output file $(basename "$remote_out_file"), but no matching boundary/summary lines were extracted."
      fi

      if [[ "$out_status" == "excerpted" ]] && extract_out_metrics "$out_excerpt" "$local_case_dir/out_metrics.json" "$local_case_dir/out_metrics.csv"; then
        metrics_status="extracted"
      else
        metrics_status="failed"
        if [[ -z "$notes" ]]; then
          notes="Extracted output excerpt from $(basename "$remote_out_file"), but metric parsing failed."
        fi
      fi

      summary_line="$(grep -E '^Wrote [0-9]+ rows? to .*binning_summary[.]csv$' "$out_excerpt" | tail -n 1 || true)"
      if [[ -n "$summary_line" ]]; then
        if [[ -n "$notes" ]]; then
          notes="$notes $summary_line"
        else
          notes="$summary_line"
        fi
      fi
    fi

    if [[ "$volume_status" != "downloaded" ]]; then
      if [[ -n "$notes" ]]; then
        notes="$notes volume.npy $volume_status."
      else
        notes="volume.npy $volume_status."
      fi
    fi

    if [[ "$case_found" == "missing" && -z "$notes" ]]; then
      notes="Config was found, but no matching segmented result folder was found."
    fi

    append_overview_row "$case_name" "$bin_value" "$reduce_value" "$remote_case_dir" "$local_case_dir" "$case_found" "$config_status" "$out_status" "$metadata_status" "$chom_status" "$e_status" "$g_status" "$vol_status" "$xdmf_status" "$h5_status" "$metrics_status" "$notes"
  done 3< "$case_list_file"

  printf '\nDone.\n'
  printf 'Results folder: %s\n' "$RESULTS_DIR"
  printf 'Overview CSV: %s\n' "$OVERVIEW_CSV"
}

main "$@"
