#!/bin/bash
#
# Steuervariablen des Projekts 014 (.leS-Pipeline). Aus diesen Werten erzeugt
# create_les_config.sh die Datei config-A01-les.json.

BASE_PATH="/data/scripts/014-Yield-Surface-From-leS"

# Sampling der Fliessflaeche (setup_yield_surface_jobs.sh)
# Ressourcen je Punkt-Job. Der Punkt-Job liest die Taskzahl ueber SLURM_NTASKS,
# es genuegt also, sie hier zu aendern. YIELD_JOB_NODES=1 haelt den Job auf einem
# Knoten (0 wuerde SBATCH -N weglassen und SLURM frei verteilen lassen).
# Gesamtspeicher je Job = YIELD_JOB_NTASKS x YIELD_JOB_MEM_PER_CPU und muss auf
# EINEN Knoten passen. i01 (mpsc): 96 Kerne, RealMemory = 364800 MB.
#   64 x 5600 MB = 358400 MB  <- Default, 6400 MB Reserve zum Knotenlimit
#   64 x 5700 MB = 364800 MB     exakt das Knotenlimit, keine Reserve
#   64 x 4000 MB = 256000 MB     genuegsam, falls MUMPS weniger braucht
# Reicht das nicht: -C i02 (104 Kerne, 490000 MB) -> 64 x 7500 = 480000 MB.
YIELD_JOB_NTASKS="${YIELD_JOB_NTASKS:-64}"
YIELD_JOB_NODES="${YIELD_JOB_NODES:-1}"
YIELD_JOB_MEM_PER_CPU="${YIELD_JOB_MEM_PER_CPU:-5600}"
YIELD_JOB_CONSTRAINT="${YIELD_JOB_CONSTRAINT:-i01}"
YIELD_JOB_TIME="${YIELD_JOB_TIME:-1440}"
# Partition. Leer = Default "deflt": i01-Knoten (96 Kerne, 364800 MB), max. 24 h.
# "long" hat dieselben Knoten, aber bis zu 7 Tagen Laufzeit (330 i01-Knoten).
# Bei "long" auch YIELD_JOB_TIME hochsetzen, z.B. YIELD_JOB_TIME=3-00:00:00.
YIELD_JOB_PARTITION="${YIELD_JOB_PARTITION:-}"
YIELD_SURFACE_POINTS="${YIELD_SURFACE_POINTS:-6}"
YIELD_SURFACE_STRAIN_RADIUS="${YIELD_SURFACE_STRAIN_RADIUS:-0.25}"

# --- .leS-Pipeline (A01) -----------------------------------------------------
# Standardpfad dieses Projekts: bereits segmentiertes Voxelbild im .leS-Format
# statt DICOM. A01_les_2_npy.py ersetzt 00/01/02/02a.
LES_ENABLED="${LES_ENABLED:-true}"
LES_DATASET_ID="${LES_DATASET_ID:-JM-25-77_A01_les}"
# Cluster: $HPC_SCRATCH/pygalmesh/data/resources/A01_segmented  ->  /data/resources/A01_segmented
LES_INPUT="${LES_INPUT:-/data/resources/A01_segmented}"
LES_BASE_CONFIG="${LES_BASE_CONFIG:-config-A01-les.json}"
LES_CONFIG_FILENAME="${LES_CONFIG_FILENAME:-config-A01-les.json}"
# Aufloesung: reduce=N fasst NxNxN Voxel zusammen (Quelle: 16,7 um/Voxel).
#   1 -> 1187x1188x886 = 1249 MVoxel (16,7 um)   nur mit Crop sinnvoll
#   2 ->  593x594x443  =  156 MVoxel (33,4 um)   <- Default
#   4 ->  296x297x221  =   19 MVoxel (66,8 um)
#   8 ->  148x148x110  =    2 MVoxel (133,6 um)  entspricht Bin4-reduce-2 der DICOM-Studie
LES_REDUCE_FACTOR="${LES_REDUCE_FACTOR:-2}"
LES_REDUCE_MODE="${LES_REDUCE_MODE:-majority}"
LES_REDUCE_THRESHOLD="${LES_REDUCE_THRESHOLD:-0.5}"
LES_SMOOTH_SIGMA="${LES_SMOOTH_SIGMA:-0.0}"
LES_LINE_ORDER="${LES_LINE_ORDER:-C}"
LES_MATERIAL_VALUE="${LES_MATERIAL_VALUE:-1}"
LES_BOUNDS_MODE="${LES_BOUNDS_MODE:-full}"
LES_VOXEL_SIZE_UNIT="${LES_VOXEL_SIZE_UNIT:-mm}"
LES_XY_DIVISIONS="${LES_XY_DIVISIONS:-1}"
# Padding vor dem Signed-Distance-Field in Schritt 03. 1 ist grenzwertig und
# fuehrt zu abgeschnittenen Isoflaechen ("open edges"); 3 ist geprueft.
LES_SDF_PAD_WIDTH="${LES_SDF_PAD_WIDTH:-3}"
# --- Netzfeinheit -------------------------------------------------------------
# Zielkantenlaenge der Tetraeder in um (max_cell_circumradius). Das ist die
# bevorzugte Angabe: sie ist unabhaengig von LES_REDUCE_FACTOR, weil der
# Groessenfaktor aus der Voxelgroesse berechnet wird.
#   75 um  -> erwartet 4-6 Mio. Tetraeder bei reduce=2  (Default)
#   50 um  -> das zu feine Netz vom ersten Lauf (Faktor 1,4853 x 33,4 um)
#  199 um  -> Elementgroesse der alten Bin4-reduce-2-Studie
LES_MAX_ELEMENT_SIZE_UM="${LES_MAX_ELEMENT_SIZE_UM:-75}"
# Alternativen, falls LES_MAX_ELEMENT_SIZE_UM leer ist:
#   direkter Faktor auf die Groessenparameter (Elementzahl ~ 1/scale^3)
LES_MESH_SIZE_SCALE="${LES_MESH_SIZE_SCALE:-1.0}"
#   oder aus gemessener Ist- und gewuenschter Zielgroesse rechnen lassen:
# LES_CURRENT_TETS=16000000
# LES_TARGET_TETS=6000000

# --- Fliessgrenze und Fliesskriterien -----------------------------------------
# Anfangsfliessgrenze des Aluminiums (Materialsatz "std").
YIELD_SIG_Y="${YIELD_SIG_Y:-100}"
# Schwelle der drei plastischen Dehnungsmasse. 0.002 = 0,2 % = Rp0,2-Definition.
# Der Lauf endet erst, wenn ALLE drei ueberschritten sind; jedes liefert einen
# eigenen Fliessflaechenpunkt (yield_states in der Ergebnis-JSON).
YIELD_PLASTIC_STRAIN_THRESHOLD="${YIELD_PLASTIC_STRAIN_THRESHOLD:-0.002}"
# Drittes Kriterium: Anteil des Volumens, der bereits fliesst (alpha > 1e-5).
# Bezug "material" = Anteil der Aluminiumphase (porositaetsunabhaengig).
# Bezug "rve" = Anteil des reduzierten RVE-Volumens; beide unterscheiden sich um
# die relative Dichte (hier rund 0,148), 2 % des Materials = 0,30 % des RVE.
# Schwelle 0,002 = 0,2 % des Materials fliesst. Die bisherige Studie verwendete
# 0,02; dieses Kriterium spricht jetzt also deutlich frueher an (Fliessbeginn).
YIELD_YIELDED_VOLUME_FRACTION="${YIELD_YIELDED_VOLUME_FRACTION:-0.002}"
YIELD_YIELDED_VOLUME_REFERENCE="${YIELD_YIELDED_VOLUME_REFERENCE:-material}"
# Welches Kriterium final_yield_state fuellt (collect_/create_yield_surface_*).
YIELD_PRIMARY_CRITERION="${YIELD_PRIMARY_CRITERION:-eps_p_eq_macroscopic}"

# --- Randschale (02d) ---------------------------------------------------------
# Dicke in Voxeln. Sie muss vom Netz aufloesbar bleiben: bei 33,4 um Voxeln und
# 75 um Elementen sind 8 Voxel = 267 um rund 3,5 Elemente. Die alten 3 Voxel
# waeren nur 100 um bzw. 1,3 Elemente gewesen.
LES_BOUNDARY_SHELL_XZ="${LES_BOUNDARY_SHELL_XZ:-8}"
LES_BOUNDARY_SHELL_Y="${LES_BOUNDARY_SHELL_Y:-12}"
# true = nur die groesste zusammenhaengende Aluminiumkomponente vernetzen.
# Im Datensatz JM-25-77 sind das 99,98 % des Aluminiums; der Rest sind
# freischwebende Inseln (meist <= 10 Voxel), die im FE Starrkoerpermoden geben.
LES_KEEP_LARGEST_COMPONENT="${LES_KEEP_LARGEST_COMPONENT:-true}"
# Optionaler Ausschnitt im Originalgitter, Format "start ende" (leer = alles)
LES_X_RANGE="${LES_X_RANGE:-}"
LES_Y_RANGE="${LES_Y_RANGE:-}"
LES_Z_RANGE="${LES_Z_RANGE:-}"
