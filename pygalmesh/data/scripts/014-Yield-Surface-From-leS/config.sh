#!/bin/bash
#
# Steuervariablen des Projekts 014 (.leS-Pipeline). Aus diesen Werten erzeugt
# create_les_config.sh die Datei config-A01-les.json.

BASE_PATH="/data/scripts/014-Yield-Surface-From-leS"

# Sampling der Fliessflaeche (setup_yield_surface_jobs.sh)
YIELD_SURFACE_POINTS=6
YIELD_SURFACE_STRAIN_RADIUS=0.25

# --- .leS-Pipeline (A01) -----------------------------------------------------
# Standardpfad dieses Projekts: bereits segmentiertes Voxelbild im .leS-Format
# statt DICOM. A01_les_2_npy.py ersetzt 00/01/02/02a.
LES_ENABLED=true
LES_DATASET_ID="JM-25-77_A01_les"
# Cluster: $HPC_SCRATCH/pygalmesh/data/resources/A01_segmented  ->  /data/resources/A01_segmented
LES_INPUT="/data/resources/A01_segmented"
LES_BASE_CONFIG="config-A01-les.json"
LES_CONFIG_FILENAME="config-A01-les.json"
# Aufloesung: reduce=N fasst NxNxN Voxel zusammen (Quelle: 16,7 um/Voxel).
#   1 -> 1187x1188x886 = 1249 MVoxel (16,7 um)   nur mit Crop sinnvoll
#   2 ->  593x594x443  =  156 MVoxel (33,4 um)   <- Default
#   4 ->  296x297x221  =   19 MVoxel (66,8 um)
#   8 ->  148x148x110  =    2 MVoxel (133,6 um)  entspricht Bin4-reduce-2 der DICOM-Studie
LES_REDUCE_FACTOR=2
LES_REDUCE_MODE="majority"
LES_REDUCE_THRESHOLD=0.5
LES_SMOOTH_SIGMA=0.0
LES_LINE_ORDER="C"
LES_MATERIAL_VALUE=1
LES_BOUNDS_MODE="full"
LES_VOXEL_SIZE_UNIT="mm"
LES_XY_DIVISIONS=1
# Padding vor dem Signed-Distance-Field in Schritt 03. 1 ist grenzwertig und
# fuehrt zu abgeschnittenen Isoflaechen ("open edges"); 3 ist geprueft.
LES_SDF_PAD_WIDTH=3
# true = nur die groesste zusammenhaengende Aluminiumkomponente vernetzen.
# Im Datensatz JM-25-77 sind das 99,98 % des Aluminiums; der Rest sind
# freischwebende Inseln (meist <= 10 Voxel), die im FE Starrkoerpermoden geben.
LES_KEEP_LARGEST_COMPONENT=true
# Optionaler Ausschnitt im Originalgitter, Format "start ende" (leer = alles)
LES_X_RANGE=""
LES_Y_RANGE=""
LES_Z_RANGE=""
