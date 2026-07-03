#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -d "$SCRIPT_DIR/00_results" ]]; then
  DEFAULT_SOURCE="$SCRIPT_DIR/00_results"
else
  DEFAULT_SOURCE="$SCRIPT_DIR/results/cases"
fi

SOURCE_DIR="${1:-$DEFAULT_SOURCE}"
OUTPUT_DIR="${2:-$SCRIPT_DIR/dlfx_meshes_for_sending}"
STAGING_DIR="$OUTPUT_DIR/staging"
ZIP_DIR="$OUTPUT_DIR/zips"
MANIFEST="$OUTPUT_DIR/dlfx_mesh_manifest.csv"
COMBINED_ZIP="$OUTPUT_DIR/dlfx_meshes_all.zip"
CREATE_COMBINED_ZIP="${CREATE_COMBINED_ZIP:-0}"
KEEP_STAGING="${KEEP_STAGING:-0}"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "Source directory not found: $SOURCE_DIR" >&2
  echo "Usage: $0 [source_dir] [output_dir]" >&2
  exit 1
fi

if ! command -v zip >/dev/null 2>&1; then
  echo "zip command not found. Please install zip or run on a system where zip is available." >&2
  exit 1
fi

rm -rf "$STAGING_DIR" "$ZIP_DIR"
mkdir -p "$STAGING_DIR" "$ZIP_DIR"
printf 'package_name,source_xdmf,source_h5,zip_path\n' > "$MANIFEST"

count=0
while IFS= read -r -d '' xdmf_path; do
  h5_path="$(dirname "$xdmf_path")/dlfx_mesh.h5"
  if [[ ! -f "$h5_path" ]]; then
    echo "Skipping $(dirname "$xdmf_path"): dlfx_mesh.h5 missing" >&2
    continue
  fi

  rel_dir="${xdmf_path%/dlfx_mesh.xdmf}"
  rel_dir="${rel_dir#"$SOURCE_DIR"/}"
  package_name="$(printf '%s' "$rel_dir" | tr '/ ' '__' | tr -c 'A-Za-z0-9._-' '_')"
  package_dir="$STAGING_DIR/$package_name"
  package_zip="$ZIP_DIR/$package_name.zip"

  mkdir -p "$package_dir"
  cp "$xdmf_path" "$package_dir/dlfx_mesh.xdmf"
  cp "$h5_path" "$package_dir/dlfx_mesh.h5"

  (
    cd "$STAGING_DIR"
    zip -qr "$package_zip" "$package_name"
  )

  printf '"%s","%s","%s","%s"\n' "$package_name" "$xdmf_path" "$h5_path" "$package_zip" >> "$MANIFEST"
  count=$((count + 1))
done < <(find "$SOURCE_DIR" -type f -name 'dlfx_mesh.xdmf' -print0 | sort -z)

if [[ "$count" -eq 0 ]]; then
  echo "No dlfx_mesh.xdmf/dlfx_mesh.h5 pairs found below $SOURCE_DIR" >&2
  exit 1
fi

if [[ "$CREATE_COMBINED_ZIP" == "1" ]]; then
  rm -f "$COMBINED_ZIP"
  (
    cd "$STAGING_DIR"
    zip -qr "$COMBINED_ZIP" .
  )
fi

if [[ "$KEEP_STAGING" != "1" ]]; then
  rm -rf "$STAGING_DIR"
fi

echo "Packaged $count dlfx mesh pair(s)."
echo "Per-case zips: $ZIP_DIR"
if [[ "$CREATE_COMBINED_ZIP" == "1" ]]; then
  echo "Combined zip: $COMBINED_ZIP"
fi
echo "Manifest: $MANIFEST"
