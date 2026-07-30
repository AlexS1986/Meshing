#!/bin/bash
# Remove ALL generated files from this pipeline folder, keeping only the source
# scripts. Use before a clean end-to-end run.
#
#   bash clean_generated.sh          # delete generated files
#   bash clean_generated.sh --dry    # only list what would be deleted
#
# Note: the raw EBSD data lives in ../data_c04 and is NOT touched.
set -e
cd "$(dirname "$0")"

# Source files to KEEP (everything else in this folder is generated output).
KEEP="
01_fit_ebsd.py 02_generate_tess.sh 03_mesh.sh 04_convert_to_xdmf.py
05_verify_stats.py 06_fenicsx_example.py 07_tensile_specimens.py
08_combined_specimen.py 09_homogenization_rve.sh materials.py
run_all.sh recover_and_continue.sh clean_generated.sh run_pipeline.sh
README.md documentation.txt AGENTS.md
"
# normalize to a single space-delimited line so line breaks don't break matching
KEEP=" $(echo $KEEP) "

dry=0
[ "$1" = "--dry" ] && dry=1

for f in * .[!.]*; do
    [ -e "$f" ] || continue
    case "$KEEP" in
        *" $f "*) ;;                       # keep source
        *)
            if [ "$dry" = "1" ]; then
                echo "would remove: $f"
            else
                echo "removing: $f"
                rm -rf "$f"
            fi
            ;;
    esac
done
echo "done."
