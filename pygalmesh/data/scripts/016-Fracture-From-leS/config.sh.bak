#!/bin/bash
#
# Steuervariablen des Projekts 016 (Phasenfeld-Bruch aus .leS-Daten).
#
#   * Der LES_*-Block ist derselbe wie in 015, nur mit anderen Defaults:
#     anderer Datensatz (JM-25-88), Riegel-Crop statt Vollvolumen und eine
#     deutlich groebere Netzfeinheit.
#   * Der FRACTURE_*-Block ersetzt den YIELD_*-Block aus 015: dieses Projekt
#     rechnet keine Fliessflaeche, sondern eine Phasenfeld-Bruchsimulation
#     (00_template/script.py + pfmfrac_function.py aus 011).
#   * Der MESH_TIER_*-Block beschreibt die Aufloesungsfamilie coarse/medium/fine
#     nach dem Vorbild von 012.
#
# Alle Variablen sind als VAR="${VAR:-wert}" geschrieben und lassen sich fuer
# einen einzelnen Aufruf ueber die Umgebung ueberschreiben, ohne die Datei zu
# aendern:
#
#     LES_MAX_ELEMENT_SIZE_UM=300 ./create_fracture_config.sh

BASE_PATH="/data/scripts/016-Fracture-From-leS"

# Name der Probe. Taucht im Archivpfad der Netze auf
# ($HPC_SCRATCH/pygalmesh/data/resources/generated_meshes/<SPECIMEN_NAME>/...).
SPECIMEN_NAME="${SPECIMEN_NAME:-JM-25-88}"

# --- .leS-Eingabe -------------------------------------------------------------
# Container-Pfad; auf dem Host liegt das unter
# $HPC_SCRATCH/pygalmesh/data/resources/A01_segmented.
LES_RESOURCE_DIR="${LES_RESOURCE_DIR:-/data/resources/A01_segmented}"
# Genau EINE Datei angeben - im Ordner liegen vier .leS-Datensaetze, und
# A01_les_2_npy.py bricht bei mehr als einer Datei ab.
LES_FILENAME="${LES_FILENAME:-JM-25-88_78p86.leS}"
LES_INPUT="${LES_INPUT:-$LES_RESOURCE_DIR/$LES_FILENAME}"

# Basis, aus der die Configs abgeleitet werden. Das ist die in 015 validierte
# .leS-Config; sie liegt als Kopie hier im Ordner (Projektregel: Configs werden
# abgeleitet, nicht von Hand geschrieben).
LES_BASE_CONFIG="${LES_BASE_CONFIG:-config-A01-les-base.json}"

LES_REDUCE_MODE="${LES_REDUCE_MODE:-majority}"
LES_REDUCE_THRESHOLD="${LES_REDUCE_THRESHOLD:-0.5}"
LES_SMOOTH_SIGMA="${LES_SMOOTH_SIGMA:-0.0}"
LES_LINE_ORDER="${LES_LINE_ORDER:-C}"
LES_MATERIAL_VALUE="${LES_MATERIAL_VALUE:-1}"
LES_BOUNDS_MODE="${LES_BOUNDS_MODE:-full}"
LES_VOXEL_SIZE_UNIT="${LES_VOXEL_SIZE_UNIT:-mm}"
LES_XY_DIVISIONS="${LES_XY_DIVISIONS:-1}"
# Padding vor dem Signed-Distance-Field in Schritt 03. 1 ist grenzwertig
# (abgeschnittene Isoflaechen), 3 ist in 014/015 geprueft.
LES_SDF_PAD_WIDTH="${LES_SDF_PAD_WIDTH:-3}"
LES_KEEP_LARGEST_COMPONENT="${LES_KEEP_LARGEST_COMPONENT:-true}"

# --- Probengeometrie: langer Riegel ------------------------------------------
# Die Surfing-Randbedingungen in 00_template/pfmfrac_function.py setzen den
# Rissstart bei x = 0,2*Lx und lassen den Riss nach +x laufen. Das Gebiet muss
# deshalb in x deutlich laenger sein als in y und z.
#
# Anders als in 012 (dort war das CT-Teilvolumen zu klein und wurde zweimal in x
# gespiegelt, 4*Nx-3) ist das .leS-Volumen gross genug: JM-25-77 misst
# 19,8 x 19,8 x 14,8 mm. Der Riegel wird also direkt herausgeschnitten.
#
# Angaben in mm; leer = volle Ausdehnung der Achse. Der Ausschnitt wird
# mittig im Volumen platziert und auf Vielfache des reduce-Faktors gekuerzt.
LES_BAR_X_MM="${LES_BAR_X_MM:-}"       # leer = volle Laenge in x (Risslaufrichtung)
LES_BAR_Y_MM="${LES_BAR_Y_MM:-8.0}"    # Hoehe, bestimmt ueber eps_factor die Rissbandbreite
LES_BAR_Z_MM="${LES_BAR_Z_MM:-4.0}"    # Dicke

# Gitter und Voxelgroesse des .leS-Datensatzes. Werden sie leer gelassen, liest
# create_fracture_config.sh sie mit A04_les_header_info.py aus der Datei - das
# geht nur dort, wo die .leS-Datei erreichbar ist (Cluster/Container). Auf einem
# Rechner ohne die Daten koennen sie hier von Hand eingetragen werden.
#   JM-25-77: 1187 1188 886, 1.670000e-05 m
LES_GRID="${LES_GRID:-}"               # "nx ny nz"
LES_VOXEL_SIZE_M="${LES_VOXEL_SIZE_M:-}"

# --- Randschale (02d) ---------------------------------------------------------
# Dicke in Voxeln. Sie traegt die Dirichlet-Raender der Surfing-BCs und muss vom
# Netz aufgeloest bleiben - Faustregel mindestens drei Elemente dick. Weil die
# Elemente hier viel groeber sind als in 015, muss die Schale in Voxeln
# entsprechend dicker sein.
# Der Generator rechnet die Dicke automatisch aus, wenn LES_BOUNDARY_SHELL_*
# leer bleibt: ceil(3 * Elementgroesse / Voxelgroesse).
LES_BOUNDARY_SHELL_XZ="${LES_BOUNDARY_SHELL_XZ:-}"
LES_BOUNDARY_SHELL_Y="${LES_BOUNDARY_SHELL_Y:-}"
LES_BOUNDARY_SHELL_ELEMENTS="${LES_BOUNDARY_SHELL_ELEMENTS:-3}"

# --- Aufloesungsfamilie -------------------------------------------------------
# Je Zeile:  <tier>|<reduce>|<max_element_size_um>
#
# Bewusst deutlich groeber als 015 (dort 75 um bei reduce=2). Massgeblich fuer
# den Phasenfeld-Bruch ist nicht die Voxelgroesse, sondern die Regularisierungs-
# laenge epsilon = Ly / FRACTURE_EPS_FACTOR_PARAM: das Netz muss epsilon
# aufloesen, sonst ist das Ergebnis netzabhaengig. Bei Ly = 8 mm und
# eps_factor = 8 ist epsilon = 1,0 mm, also 2,5 / 3,7 / 5,0 Elemente je epsilon.
#
#   tier    reduce  Voxel*     Elementgroesse   Elemente je epsilon
#   coarse    8     133,6 um       400 um            2,5
#   medium    4      66,8 um       267 um            3,7
#   fine      4      66,8 um       200 um            5,0
#   (* Voxelgroesse fuer eine Quelle mit 16,7 um; JM-25-88 kann abweichen,
#      der Generator rechnet mit dem Wert aus dem .leS-Header.)
#
# Zum Vergleich: 011/012 rechneten mit 199 um Elementen, 015 mit 75 um.
MESH_TIERS=(
  "coarse|8|400"
  "medium|4|267"
  "fine|4|200"
)
# Welche Stufe die Jobskripte ohne Argument verwenden.
DEFAULT_TIER="${DEFAULT_TIER:-coarse}"
# Filter fuer einzelne Aufrufe, z.B. ONLY_TIERS="coarse" ./create_fracture_config.sh
ONLY_TIERS="${ONLY_TIERS:-}"

# Einzelwerte, falls ohne Tier-Tabelle gearbeitet wird (create_fracture_config.py
# direkt aufgerufen). Leer = aus der Tabelle.
LES_REDUCE_FACTOR="${LES_REDUCE_FACTOR:-}"
LES_MAX_ELEMENT_SIZE_UM="${LES_MAX_ELEMENT_SIZE_UM:-}"

# --- Bruchsimulation ----------------------------------------------------------
# Gelesen von job_run_simulation_CLUSTER.sh und an 00_template/script.py
# durchgereicht.
FRACTURE_MATERIALS="${FRACTURE_MATERIALS:-std}"
FRACTURE_DIRECTIONS="${FRACTURE_DIRECTIONS:-y}"
FRACTURE_MESH_FILE="${FRACTURE_MESH_FILE:-dlfx_mesh}"
# Fallback-Elastizitaet, falls der Materialsatz fehlt. Normalfall: E/nu aus
# fracture.material_sets, daraus rechnet script.py lambda und mu.
FRACTURE_LAM_PARAM="${FRACTURE_LAM_PARAM:-1.0}"
FRACTURE_MUE_PARAM="${FRACTURE_MUE_PARAM:-1.0}"
FRACTURE_GC_PARAM="${FRACTURE_GC_PARAM:-1.0}"
# Bruchzaehigkeit: benannter Satz aus fracture.fracture_toughness_sets.
#   alsi10mg_as_built: Gc = 7,2 N/mm (Literatur 6,0-8,4), DOI 10.1016/j.ijmecsci.2021.106868
FRACTURE_TOUGHNESS="${FRACTURE_TOUGHNESS:-alsi10mg_as_built}"
# epsilon = (y_max - y_min) / FRACTURE_EPS_FACTOR_PARAM.
# 011/012 verwendeten 20. Bei den hier gewaehlten groben Netzen waere epsilon
# damit zu klein, um vom Netz aufgeloest zu werden -> 8.
FRACTURE_EPS_FACTOR_PARAM="${FRACTURE_EPS_FACTOR_PARAM:-8.0}"
FRACTURE_ELEMENT_ORDER="${FRACTURE_ELEMENT_ORDER:-1}"

# --- Ressourcen der Jobs ------------------------------------------------------
# Netzerzeugung: es arbeitet nur ein Task (srun -n 1), die Zuteilung dient dem
# Speicher. Uebernommen aus 015/012.
MESH_JOB_TIME="${MESH_JOB_TIME:-1440}"
MESH_JOB_PARTITION="${MESH_JOB_PARTITION:-mem}"
# Bruchsimulation: laeuft ueber Tage, deshalb Partition long.
SIM_JOB_NTASKS="${SIM_JOB_NTASKS:-96}"
SIM_JOB_MEM_PER_CPU="${SIM_JOB_MEM_PER_CPU:-4000}"
SIM_JOB_TIME="${SIM_JOB_TIME:-10080}"
SIM_JOB_CONSTRAINT="${SIM_JOB_CONSTRAINT:-i01}"
