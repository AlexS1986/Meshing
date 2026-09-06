#!/bin/bash
#
# Steuervariablen des Projekts 016 (Phasenfeld-Bruch aus .leS-Daten).
#
#   * Der LES_*-Block ist derselbe wie in 015, nur mit anderen Defaults:
#     ganze Probe, in x gespiegelt und in eine homogene Schale eingebettet
#     (Route aus 011), reduce = 4 mit 200-um-Elementen (seit 2026-09-02).
#     Datensatz seit 2026-08-31: JM-25-77 (Gitter in 014 verifiziert).
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
SPECIMEN_NAME="${SPECIMEN_NAME:-JM-25-77}"

# --- .leS-Eingabe -------------------------------------------------------------
# Container-Pfad; auf dem Host liegt das unter
# $HPC_SCRATCH/pygalmesh/data/resources/A01_segmented.
LES_RESOURCE_DIR="${LES_RESOURCE_DIR:-/data/resources/A01_segmented}"
# Genau EINE Datei angeben - im Ordner liegen vier .leS-Datensaetze, und
# A01_les_2_npy.py bricht bei mehr als einer Datei ab.
LES_FILENAME="${LES_FILENAME:-JM-25_77_85p55.leS}"   # Achtung: Unterstrich statt Bindestrich im Dateinamen
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

# --- Probengeometrie: ganze Probe, in x gespiegelt (seit 2026-09-02) ---------
# Die Surfing-Randbedingungen in 00_template/pfmfrac_function.py setzen den
# Rissstart bei x = 0,2*Lx und lassen den Riss nach +x laufen. Das Gebiet muss
# deshalb in x deutlich laenger sein als in y und z.
#
# Entscheidung 2026-09-02 (Nutzer): KEIN Riegel-Ausschnitt mehr. Die ganze
# Probe (JM-25-77: 19,8 x 19,8 x 14,8 mm) wird modelliert, als Voxelvolumen
# in x gespiegelt (02e, Route aus 011/012) und aussen in eine homogene
# Aluminiumschale eingebettet (02f, wie 011: 0,4 mm in y/z, 4 mm Endbloecke
# in x). Mit einer Spiegelung: Schaum 39,6 x 19,8 x 14,8 mm, Box inkl. Schale
# ca. 47,5 x 20,6 x 15,6 mm, Lx/Ly = 2,3, Risslauf ca. 35 epsilon.
# Die Spiegelebene liegt in der Mitte des Schaums (x = Lx_Schaum/2).
#
# Der Riegel-Ausschnitt aus der Session 2026-08-31 (x voll, y = 16, z = 4 mm)
# bleibt ueber LES_BAR_*_MM verfuegbar: leer = volle Ausdehnung der Achse.
# Ein Ausschnitt wird mittig platziert und auf Vielfache von reduce gekuerzt.
# Die externe Schale (02f) kommt AUSSEN dazu.
LES_BAR_X_MM="${LES_BAR_X_MM:-}"       # leer = volle Laenge in x (Risslaufrichtung)
LES_BAR_Y_MM="${LES_BAR_Y_MM:-}"       # leer = volle Hoehe (19,8 mm); vorher 16.0
LES_BAR_Z_MM="${LES_BAR_Z_MM:-}"       # leer = volle Dicke (14,8 mm); vorher 4.0
# Spiegelung des Voxelvolumens in x vor der Schale (02e): 0 = aus,
# 1 = einmal (2*Nx-1, Default), 2 = zweimal (4*Nx-3, wie 011). Jede weitere
# Spiegelung verdoppelt den Schaumanteil des Netzes.
LES_MIRROR_X_REPETITIONS="${LES_MIRROR_X_REPETITIONS:-1}"

# Gitter und Voxelgroesse des .leS-Datensatzes. Werden sie leer gelassen, liest
# create_fracture_config.sh sie mit A04_les_header_info.py aus der Datei - das
# geht nur dort, wo die .leS-Datei erreichbar ist (Cluster/Container). Auf einem
# Rechner ohne die Daten koennen sie hier von Hand eingetragen werden.
#   JM-25-77: 1187 1188 886, 1.670000e-05 m  (in 014 verifiziert)
# Die Werte unten gelten NUR fuer JM-25-77. Bei einem anderen Datensatz beide
# leeren, dann liest create_fracture_config.sh den Header auf dem Cluster.
LES_GRID="${LES_GRID:-1187 1188 886}"  # "nx ny nz"
LES_VOXEL_SIZE_M="${LES_VOXEL_SIZE_M:-1.670000e-05}"

# --- Randschale ---------------------------------------------------------------
# Seit 2026-08-31 wie in 011: EXTERNE Schale ueber 02f_add_voxel_shell. Sie wird
# aussen an den Ausschnitt angefuegt (Wert 0 = Aluminium) und frisst keinen
# Schaum. 011 hatte 3 Voxel (0,4 mm) in y/z.
#
# Der bis dahin genutzte innere Seal aus 02d (LES_SHELL_MODE=seal) ueberschrieb
# bei 400-um-Elementen 9/14/9 Voxel = 1,2/1,9/1,2 mm Schaum je Seite - vom
# 4-mm-Riegel blieben in z nur 1,6 mm Schaum. Das war der Grund fuer die dicken
# Waende und die wenigen Poren im ersten 016-Lauf.
LES_SHELL_MODE="${LES_SHELL_MODE:-external}"   # external | seal | none
# Dicke in um, je Stufe in Voxel umgerechnet (ceil). Muss >= Elementgroesse sein,
# sonst loest das Netz die Schale nicht auf: 400 um = 3 Voxel bei coarse,
# 6 Voxel bei medium/fine. Entspricht 011 (3 x 134 um).
LES_SHELL_UM="${LES_SHELL_UM:-400}"
LES_SHELL_VOXELS="${LES_SHELL_VOXELS:-}"       # alternativ fest in Voxeln (leer = aus LES_SHELL_UM)
# Homogene Endbloecke an den x-Enden, in um. 011: 30 Voxel x 134 um = 4 mm -
# dort liegen Kerb-Anfang und Auslauf der Surfing-BC in Vollmaterial. Die
# Bloecke sind massiv und kosten Elemente (bei 200 um rund ein Viertel des
# Netzes); 2000 spart davon die Haelfte. Leer = wie LES_SHELL_UM.
LES_SHELL_X_UM="${LES_SHELL_X_UM:-4000}"
LES_SHELL_VOXELS_X="${LES_SHELL_VOXELS_X:-}"   # alternativ fest in Voxeln (ueberschreibt LES_SHELL_X_UM)
# 10_snap_mesh_to_crop_boundary wie in 011: Knoten nahe der Box-Flaechen exakt auf
# die Flaeche ziehen, damit die BC-Suche (atol = 2 % Lx) den Rand sauber findet.
LES_SNAP_MESH_TO_BOX="${LES_SNAP_MESH_TO_BOX:-true}"
# max_facet_distance = max_element_size / Ratio. 011: 3. Die 015-Basis hat 16,7,
# was bei 400-um-Elementen 24 um Facettenabstand ergaebe (viel zu fein).
LES_FACET_DISTANCE_RATIO="${LES_FACET_DISTANCE_RATIO:-3}"

# Nur fuer LES_SHELL_MODE=seal (02d): Dicke in Voxeln, leer = ceil(3 * h / dx).
LES_BOUNDARY_SHELL_XZ="${LES_BOUNDARY_SHELL_XZ:-}"
LES_BOUNDARY_SHELL_Y="${LES_BOUNDARY_SHELL_Y:-}"
LES_BOUNDARY_SHELL_ELEMENTS="${LES_BOUNDARY_SHELL_ELEMENTS:-3}"

# --- Aufloesungsfamilie -------------------------------------------------------
# Je Zeile:  <tier>|<reduce>|<max_element_size_um>
#
# Entscheidung 2026-09-02 (Nutzer: "Vernetzung deutlich zu grob"): alle Stufen
# auf reduce = 4 (66,8 um Voxel). reduce = 8 (133,6 um) hatte per Majority-Vote
# bereits Stege unter ~70 um geloescht und um 130 um verklumpt, bevor ueberhaupt
# vernetzt wurde. reduce = 4 ist der Kompromiss: 19 MVoxel je Probe, rel. Dichte
# -0,08 Prozentpunkte (015, CLAUDE.md), Stege ab ~130 um bleiben erhalten.
#
# Massgeblich fuer den Phasenfeld-Bruch bleibt die Regularisierungslaenge
# epsilon = Ly / FRACTURE_EPS_FACTOR_PARAM. Bei ganzer Probe (Ly = 19,8 mm
# + 2 x 0,4 mm Schale = 20,6 mm) und eps_factor = 20 ist epsilon = 1,03 mm.
#
#   tier    reduce  Voxel*    Elementgroesse  El./epsilon  Tets (Schaetzung**)
#   coarse    4     66,8 um      250 um           4,1         ~2,5 Mio
#   medium    4     66,8 um      200 um           5,2         ~5 Mio   (Default)
#   fine      4     66,8 um      150 um           6,9         ~12 Mio  (Speicher!)
#   (*  Voxelgroesse fuer eine Quelle mit 16,7 um, wie JM-25-77.)
#   (** ganze Probe, 1x gespiegelt, 4-mm-Endbloecke; kalibriert an 011
#       (381k Tets bei 400 um) und 015 (12,3 Mio dofs bei 75 um/reduce 2).
#       Etwa die Haelfte der Elemente sitzt in der massiven Schale.)
#
# Frueher (bis 2026-09-02): coarse 8|400, medium 4|267, fine 4|200 auf einem
# Riegel 19,8 x 16 x 4 mm; 011 rechnete mit 134-um-Voxeln und 402-um-Elementen.
MESH_TIERS=(
  "coarse|4|250"
  "medium|4|200"
  "fine|4|150"
)
# Welche Stufe die Jobskripte ohne Argument verwenden.
DEFAULT_TIER="${DEFAULT_TIER:-medium}"
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
# 20 wie in 011/012. NIEMALS <= 8: alex.boundaryconditions.get_boundary_of_box_
# as_function wendet die Surfing-Verschiebung nur bei |y - y_mid| >= 4*epsilon an;
# mit eps_factor = 8 ist 4*epsilon = Ly/2 und die BC greift auf keinem Knoten
# (erster 016-Lauf: reine Starrkoerperrotation statt Belastung). Anteil der
# Hoehe mit BC = 1 - 8/eps_factor (20 -> 60 %, 16 -> 50 %, 12 -> 33 %).
# Grobe Elemente werden ueber die Riegelhoehe LES_BAR_Y_MM aufgefangen, nicht
# ueber eps_factor.
FRACTURE_EPS_FACTOR_PARAM="${FRACTURE_EPS_FACTOR_PARAM:-20.0}"
FRACTURE_ELEMENT_ORDER="${FRACTURE_ELEMENT_ORDER:-1}"

# --- Ressourcen der Jobs ------------------------------------------------------
# Netzerzeugung: es arbeitet nur ein Task (srun -n 1), die Zuteilung dient dem
# Speicher. Uebernommen aus 015/012.
MESH_JOB_TIME="${MESH_JOB_TIME:-1440}"
MESH_JOB_PARTITION="${MESH_JOB_PARTITION:-mem}"
# Bruchsimulation: -n 96 x 4000 MB wie in 011/012, aber ohne -N 1 (Nutzer-
# entscheidung 2026-08-31). 96 x 4000 = 384 000 MB passen nicht auf einen
# i01-Knoten (364 800 MB); ohne -N 1 verteilt SLURM auf zwei Knoten.
SIM_JOB_NTASKS="${SIM_JOB_NTASKS:-96}"
SIM_JOB_MEM_PER_CPU="${SIM_JOB_MEM_PER_CPU:-4000}"
SIM_JOB_TIME="${SIM_JOB_TIME:-10080}"
SIM_JOB_CONSTRAINT="${SIM_JOB_CONSTRAINT:-i01}"

# --- OpenBLAS-Workaround fuer i02 (Sapphire Rapids) ----------------------------
# OpenBLAS 0.3.20 im Container waehlt auf Sapphire Rapids (i02, Xeon 8470Q) den
# Kernel "Cooperlake" und rechnet falsch (MUMPS -10, NO CONVERGENCE). Fix aus
# Studie 015, 05.09.2026; harmlos auf i01. Siehe Bericht_OpenBLAS_SapphireRapids_20260905.md
export OPENBLAS_CORETYPE="${OPENBLAS_CORETYPE:-SkylakeX}"
export APPTAINERENV_OPENBLAS_CORETYPE="${APPTAINERENV_OPENBLAS_CORETYPE:-$OPENBLAS_CORETYPE}"
export SINGULARITYENV_OPENBLAS_CORETYPE="${SINGULARITYENV_OPENBLAS_CORETYPE:-$OPENBLAS_CORETYPE}"
