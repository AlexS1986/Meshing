#!/bin/bash
#
# Steuervariablen des Projekts 015 (.leS-Batch-Pipeline).
#
#   * Der LES_*/YIELD_*-Block ist derselbe wie in 014 und erzeugt ueber
#     create_les_config.sh eine einzelne Config.
#   * Der BATCH_*-Block am Ende beschreibt die Studie: vier .leS-Datensaetze
#     x zwei Anfangsfliessgrenzen = acht Kombinationen. Die batch_*-Skripte
#     leiten daraus Configs, Job-Ordner und Ergebnispfade ab.
#
# Alle Variablen sind als VAR="${VAR:-wert}" geschrieben und lassen sich fuer
# einen einzelnen Aufruf ueber die Umgebung ueberschreiben.

BASE_PATH="/data/scripts/015-Yield-Surface-Batch-leS"

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
# Seit reduce=4 (01.09.2026): ~1,5-2 Mio. dofs, LU braucht geschaetzt < 50 GB.
# 32 x 5600 MB = 179 GB -> zwei Punkt-Jobs je i01-Knoten; nach Messung von
# MaxRSS der ersten Laeufe ggf. weiter senken (z. B. 24 x 3700 = 89 GB, vier je Knoten).
YIELD_JOB_NTASKS="${YIELD_JOB_NTASKS:-32}"
YIELD_JOB_NODES="${YIELD_JOB_NODES:-1}"
YIELD_JOB_MEM_PER_CPU="${YIELD_JOB_MEM_PER_CPU:-5600}"
YIELD_JOB_CONSTRAINT="${YIELD_JOB_CONSTRAINT:-i01}"
# Zeitlimit je Punkt-Job in Minuten (oder d-hh:mm:ss).
# 10080 min = 7 d = das Maximum der Partition "long" (gleiche i01-Knoten).
# Die Default-Partition "deflt" erlaubt nur 1440 min, YIELD_JOB_PARTITION muss
# deshalb auf "long" stehen; sonst lehnt SLURM mit "Requested time limit is
# invalid" ab. elastoplastic.py beendet sich vor dem Limit selbst und schreibt
# davor einen Snapshot (siehe yield_surface.walltime in der Config).
# Seit reduce=4: 1440 min in der Default-Partition (bessere Prioritaet als
# "long"); laeuft ein Punkt laenger, uebernimmt die Fortsetzungskette
# (resubmit_yield_surface_timeouts_CLUSTER.sh).
YIELD_JOB_TIME="${YIELD_JOB_TIME:-1440}"
YIELD_JOB_PARTITION="${YIELD_JOB_PARTITION:-}"
YIELD_SURFACE_POINTS="${YIELD_SURFACE_POINTS:-96}"
YIELD_SURFACE_STRAIN_RADIUS="${YIELD_SURFACE_STRAIN_RADIUS:-0.25}"

# Netzvorbereitung. Der SBATCH-Header in job_prepare_mesh_CLUSTER.sh ist fest
# (deflt, -C i01, -n 8, --mem-per-cpu=15000 = 120 GB); batch_submit_CLUSTER.sh
# ueberschreibt Zeit und Partition auf der sbatch-Kommandozeile (CLI schlaegt
# Header). Seit 02.09.2026: 120 min statt 1440 und deflt statt mem — die
# Vorbereitung braucht 13-18 min (r4) und 24-34 GB (r2), ein kurzes Limit
# macht sie zum Backfill-Kandidaten, waehrend mem tagelang wartete.
PREP_JOB_TIME="${PREP_JOB_TIME:-120}"
PREP_JOB_PARTITION="${PREP_JOB_PARTITION:-deflt}"

# --- .leS-Pipeline (A01) -----------------------------------------------------
# Standardpfad dieses Projekts: bereits segmentiertes Voxelbild im .leS-Format
# statt DICOM. A01_les_2_npy.py ersetzt 00/01/02/02a.
LES_ENABLED="${LES_ENABLED:-true}"
LES_DATASET_ID="${LES_DATASET_ID:-JM-25-77_les_r4}"
# Ordner mit den .leS-Dateien (Container-Pfad).
# Cluster: $HPC_SCRATCH/pygalmesh/data/resources/A01_segmented -> /data/resources/A01_segmented
LES_RESOURCE_DIR="${LES_RESOURCE_DIR:-/data/resources/A01_segmented}"
# Einzeleingabe fuer create_les_config.sh ohne Batch (Datei, Ordner oder Glob).
LES_INPUT="${LES_INPUT:-$LES_RESOURCE_DIR}"
LES_BASE_CONFIG="${LES_BASE_CONFIG:-config-A01-les.json}"
LES_CONFIG_FILENAME="${LES_CONFIG_FILENAME:-config-A01-les.json}"
# Aufloesung: reduce=N fasst NxNxN Voxel zusammen (Quelle: 16,7 um/Voxel).
#   1 -> 1187x1188x886 = 1249 MVoxel (16,7 um)   nur mit Crop sinnvoll
#   2 ->  593x594x443  =  156 MVoxel (33,4 um)   Studie bis 01.09.2026 (12-16 Mio. dofs,
#                                                LU/MUMPS am Speicherlimit, abgebrochen)
#   4 ->  296x297x221  =   19 MVoxel (66,8 um)   <- Default seit 01.09.2026
#   8 ->  148x148x110  =    2 MVoxel (133,6 um)  entspricht Bin4-reduce-2 der DICOM-Studie
# (Die Zahlen gelten fuer JM-25-77; die anderen Datensaetze koennen andere
#  Gittergroessen haben, die Voxelgroesse steht im jeweiligen .leS-Header.)
LES_REDUCE_FACTOR="${LES_REDUCE_FACTOR:-4}"
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
#   75 um  -> 4-6 Mio. Tetraeder bei reduce=2, 12,3 Mio. dofs (JM-25-77) - zu gross fuer LU
#  150 um  -> gleiches Verhaeltnis Element/Voxel (2,25) bei reduce=4, ~1/8 der dofs (Default seit 01.09.2026)
#   50 um  -> das zu feine Netz vom ersten Lauf (Faktor 1,4853 x 33,4 um)
#  199 um  -> Elementgroesse der alten Bin4-reduce-2-Studie
LES_MAX_ELEMENT_SIZE_UM="${LES_MAX_ELEMENT_SIZE_UM:-150}"
# Alternativen, falls LES_MAX_ELEMENT_SIZE_UM leer ist:
#   direkter Faktor auf die Groessenparameter (Elementzahl ~ 1/scale^3)
LES_MESH_SIZE_SCALE="${LES_MESH_SIZE_SCALE:-1.0}"
#   oder aus gemessener Ist- und gewuenschter Zielgroesse rechnen lassen:
# LES_CURRENT_TETS=16000000
# LES_TARGET_TETS=6000000

# --- Fliessgrenze und Fliesskriterien -----------------------------------------
# Anfangsfliessgrenze des Aluminiums (Materialsatz "std") fuer einen
# Einzellauf. Im Batch kommt der Wert aus BATCH_SIG_Y (siehe unten).
YIELD_SIG_Y="${YIELD_SIG_Y:-100}"
# Schwelle der drei plastischen Dehnungsmasse. 0.002 = 0,2 % = Rp0,2-Definition.
# Der Lauf endet erst, wenn ALLE drei ueberschritten sind; jedes liefert einen
# eigenen Fliessflaechenpunkt (yield_states in der Ergebnis-JSON).
YIELD_PLASTIC_STRAIN_THRESHOLD="${YIELD_PLASTIC_STRAIN_THRESHOLD:-0.002}"
# Drittes Kriterium: Anteil des Volumens, der bereits fliesst (alpha > 1e-5).
# Bezug "material" = Anteil der Aluminiumphase (porositaetsunabhaengig).
YIELD_YIELDED_VOLUME_FRACTION="${YIELD_YIELDED_VOLUME_FRACTION:-0.002}"
YIELD_YIELDED_VOLUME_REFERENCE="${YIELD_YIELDED_VOLUME_REFERENCE:-material}"
# Welches Kriterium final_yield_state fuellt (collect_/create_yield_surface_*).
YIELD_PRIMARY_CRITERION="${YIELD_PRIMARY_CRITERION:-eps_p_eq_macroscopic}"

# --- Randschale (02d) ---------------------------------------------------------
# Dicke in Voxeln. Sie muss vom Netz aufloesbar bleiben: bei 33,4 um Voxeln und
# 75 um Elementen waren 8/12 Voxel = 267/400 um rund 3,5/5,3 Elemente.
# Seit reduce=4 / 150 um (01.09.2026): 6/9 Voxel = 401/601 um = 2,7/4 Elemente
# (4/6 Voxel haetten die physische Dicke gehalten, aber nur 1,8 Elemente).
LES_BOUNDARY_SHELL_XZ="${LES_BOUNDARY_SHELL_XZ:-6}"
LES_BOUNDARY_SHELL_Y="${LES_BOUNDARY_SHELL_Y:-9}"
# true = nur die groesste zusammenhaengende Aluminiumkomponente vernetzen.
LES_KEEP_LARGEST_COMPONENT="${LES_KEEP_LARGEST_COMPONENT:-true}"
# Optionaler Ausschnitt im Originalgitter, Format "start ende" (leer = alles)
LES_X_RANGE="${LES_X_RANGE:-}"
LES_Y_RANGE="${LES_Y_RANGE:-}"
LES_Z_RANGE="${LES_Z_RANGE:-}"

# ==============================================================================
# BATCH: vier Datensaetze x zwei Anfangsfliessgrenzen
# ==============================================================================
# Je Zeile:  <dataset-id>|<dateiname der .leS-Datei in LES_RESOURCE_DIR>
# Die dataset-id taucht in Config-, Job- und Ergebnisnamen auf und darf keine
# Leerzeichen enthalten. Findet batch_lib.sh den Dateinamen nicht, sucht es
# ersatzweise per Glob nach "<dataset-id mit _ statt -am 3. Feld>*.leS" und
# meldet, was es gefunden hat.
BATCH_DATASETS=(
  "JM-25-77|JM-25_77_85p55.leS"
  "JM-25-71|JM-25-71_79p85.leS"
  "JM-25-83|JM-25-83_80p55.leS"
  "JM-25-88|JM-25-88_78p86.leS"
)

# Anfangsfliessgrenzen in MPa (Materialsatz "std"). Ganzzahlig angeben.
BATCH_SIG_Y="${BATCH_SIG_Y:-75 100}"

# Filter fuer einzelne Aufrufe (leer = alles), z.B.
#   ONLY_DATASETS="JM-25-77 JM-25-83" ONLY_SIG_Y=100 ./batch_submit_CLUSTER.sh
ONLY_DATASETS="${ONLY_DATASETS:-}"
ONLY_SIG_Y="${ONLY_SIG_Y:-}"

# SLURM-Account fuer alle Jobs (Prep + Punkt-Jobs). p0023647 ist seit 12/2025
# ohne Kontingent (csreport: Granted 0) -> FairShare 0,016, Jobs starten nicht.
# l0003507 (Lichtenberg small project, 30k Kernstunden/Monat, geteilt) traegt
# die Netzvorbereitung und Messtranchen, NICHT den vollen Batch (768 x 32 Kerne
# x T h). Bulk: p0025962 = aktuelle Phase des HyPo-Projekts (01.12.2025-
# 30.11.2026); sobald die SLURM-Assoziation eingetragen ist (Ralf/JARDS,
# Anfrage 02.09.2026), hier JOB_ACCOUNT=p0025962 setzen.
JOB_ACCOUNT="${JOB_ACCOUNT:-l0003507}"

# Obergrenze fuer gleichzeitig eingereichte Jobs (l0003507: MaxSubmit = 1000,
# MaxJobs = 200; p0023647 hatte MaxJobs = 400). batch_submit_CLUSTER.sh prueft das vorher.
BATCH_MAX_SUBMIT="${BATCH_MAX_SUBMIT:-1000}"
