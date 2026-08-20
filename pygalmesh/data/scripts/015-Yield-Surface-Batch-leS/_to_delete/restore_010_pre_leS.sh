#!/usr/bin/env bash
#
# Setzt 010-Yield-Surface-Generation auf den Stand vor der .leS-Session zurueck.
#
# WICHTIG vorher:
#   * 014-Yield-Surface-From-leS muss angelegt und committet sein — dieser
#     Ordner haelt den neuen Stand.
#   * Das Skript aendert NUR den 010-Pfad. Es laesst 011/012/014 in Ruhe.
#
# Warum nicht einfach "git checkout 45a7db2 -- 010"? Weil der letzte Commit vor
# heute (45a7db2, 30.07.) mehrere Dateien noch gar nicht kannte, die es auf der
# Platte laengst gab und die erst heute mitcommittet wurden — darunter README.md,
# PIPELINE_ANNAHMEN_DICOM_TO_FEM.md, SCAN_DATASET_WORKFLOW.md,
# create_scan_dataset_config.py, write_yield_surface_parameters.py,
# create_yield_surface_paraview.py/.sh und job_prepare_mesh_CLUSTER.sh. Ein
# pauschales Zuruecksetzen wuerde also auch Deine eigene Vorarbeit wegwerfen.
# Deshalb geht dieses Skript Datei fuer Datei vor.
#
# Muss auf dem Mac laufen, NICHT im Container: der Container sieht nur
# Meshing/pygalmesh/data als /data, das Repository liegt mit Meshing/.git eine
# Ebene darueber und ist dort nicht sichtbar.
#
# Aufruf:
#   DRY_RUN=1 bash restore_010_pre_leS.sh  # nur anzeigen, nichts aendern
#   bash restore_010_pre_leS.sh            # A01_segmented/ (2,5 GB .leS) bleibt liegen
#   REMOVE_LES_DATA=1 bash restore_010_pre_leS.sh   # A01_segmented/ ebenfalls loeschen
#
set -euo pipefail

REPO="${REPO:-$HOME/Work/Hypo/Hypo/Simulation/Meshing}"
P="pygalmesh/data/scripts/010-Yield-Surface-Generation"
cd "$REPO"

DRY="${DRY_RUN:-0}"
run() {
  if [ "$DRY" = "1" ]; then printf '   [dry-run] %s\n' "$*"; else "$@"; fi
}
if [ "$DRY" = "1" ]; then
  echo "### TROCKENLAUF — es wird nichts geaendert ###"
fi

if [ ! -d .git ]; then
  echo "Kein Git-Repository in $REPO." >&2
  echo "Dieses Skript gehoert auf den Mac, nicht in den Container." >&2
  exit 2
fi

echo "== 0. Aufraeumen: verwaiste index.lock =="
run rm -f .git/index.lock

echo "== 1. Von mir geaenderte Dateien auf die Version vor meiner Aenderung =="
# ACHTUNG: "git checkout HEAD" taugt hier nicht, sobald meine Aenderungen
# einmal mitcommittet wurden — dann ist HEAD bereits mein Stand. Deshalb
# durchgaengig explizite Commits.
# meine Aenderung steckt in 1425e9b -> Version davor nehmen
run git checkout 75123e8 -- "$P/config.json" \
                             "$P/PIPELINE_ANNAHMEN_DICOM_TO_FEM.md"
# meine Aenderung steckt in c4d7943/1495944/75123e8 -> Version aus 13ae749 nehmen
# (13ae749 enthaelt Deine eigene Vorarbeit, aber noch nicht meine Eingriffe)
run git checkout 13ae749 -- "$P/config.sh" \
                        "$P/setup_yield_surface_jobs.py" \
                        "$P/setup_yield_surface_jobs.sh" \
                        "$P/job_prepare_mesh_Bin4_reduce_2_CLUSTER.sh" \
                        "$P/job_prepare_mesh_CLUSTER.sh" \
                        "$P/job_yield_surface_point_CLUSTER.sh" \
                        "$P/03_mesh_3D_array_pygalmesh.py" \
                        "$P/README.md"

echo "== 2. Meine Anhaenge in CLAUDE_PROJECT_NOTES.md abschneiden =="
python3 - "$P/CLAUDE_PROJECT_NOTES.md" "$DRY" <<'PYEOF'
import sys
path, dry = sys.argv[1], sys.argv[2] == "1"
text = open(path).read()
marker = "\n## Neue Datenquelle: segmentierte .leS-Voxelbilder (A01)"
if marker not in text:
    print("   Marker nicht gefunden — Datei bleibt unveraendert, bitte pruefen.")
elif dry:
    cut = text[:text.index(marker)].count("\n") + 1
    print(f"   [dry-run] wuerde ab Zeile {cut} kuerzen "
          f"({text.count(chr(10)) + 1} -> {cut} Zeilen)")
else:
    open(path, "w").write(text[:text.index(marker)].rstrip() + "\n")
    print("   Anhaenge entfernt.")
PYEOF

echo "== 2b. Umbenennung im Fliesstext von CLAUDE_PROJECT_NOTES.md zuruecknehmen =="
python3 - "$P/CLAUDE_PROJECT_NOTES.md" "$DRY" <<'PYEOF'
import sys
path, dry = sys.argv[1], sys.argv[2] == "1"
text = open(path).read()
n = text.count("run_prepare_mesh_CLUSTER.sh")
if not n:
    print("   nichts zu tun.")
elif dry:
    print(f"   [dry-run] wuerde {n} Erwaehnung(en) zurueckbenennen")
else:
    open(path, "w").write(text.replace("run_prepare_mesh_CLUSTER.sh",
                                       "job_prepare_mesh_Bin4_reduce_2_CLUSTER.sh"))
    print(f"   {n} Erwaehnung(en) zurueckbenannt.")
PYEOF

echo "== 3. Archivierte Originale zurueck an ihren Platz =="
# Diese Dateien waren nie versioniert; git kann sie nicht zurueckholen.
if [ -d "$P/_archive" ]; then
  for f in "$P"/_archive/*; do
    [ -e "$f" ] || continue
    b="$(basename "$f")"
    if [ -e "$P/$b" ]; then
      echo "   liegt schon oben, uebersprungen: $b"
    else
      run mv "$f" "$P/$b"
      echo "   zurueck: $b"
    fi
  done
fi

echo "== 4. Meine neuen Dateien entfernen =="
MINE=(
  A01_les_2_npy.py
  A02_preview_voxel_volume.py
  CLAUDE.md
  FILES.md
  LES_PIPELINE.md
  config-A01-les.json
  create_les_config.sh
  create_les_dataset_config.py
  submit_les_pipeline_CLUSTER.sh
  run_prepare_mesh_CLUSTER.sh
)
for f in "${MINE[@]}"; do
  if [ "$DRY" = "1" ]; then printf '   [dry-run] entfernen: %s\n' "$f"; else
    git rm -q -f --ignore-unmatch -- "$P/$f" 2>/dev/null || rm -f "$P/$f"
  fi
done
if [ "$DRY" = "1" ]; then echo "   [dry-run] entfernen: _archive/ _to_delete/"; else
  git rm -r -q -f --ignore-unmatch -- "$P/_archive" "$P/_to_delete" 2>/dev/null || true
  rm -rf "$P/_archive" "$P/_to_delete"
fi

if [ "${REMOVE_LES_DATA:-0}" = "1" ]; then
  echo "== 5. A01_segmented/ entfernen (2,5 GB .leS + Vorschauvolumen) =="
  if [ "$DRY" = "1" ]; then echo "   [dry-run] entfernen: A01_segmented/"; else
    git rm -r -q -f --ignore-unmatch -- "$P/A01_segmented" 2>/dev/null || true
    rm -rf "$P/A01_segmented"
  fi
else
  echo "== 5. A01_segmented/ bleibt liegen (REMOVE_LES_DATA=1 zum Loeschen) =="
fi

echo
echo "== Ergebnis: bitte pruefen, bevor Du committest =="
git status --short -- "$P"
echo
echo "Erwartet: nur noch Aenderungen, die von Dir stammen. Danach z.B."
echo "  git add -A -- $P && git commit -m '010: .leS-Arbeit nach 014 ausgelagert'"
