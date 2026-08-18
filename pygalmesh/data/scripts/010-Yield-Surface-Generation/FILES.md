# Dateiverzeichnis 010-Yield-Surface-Generation

Vollständige Übersicht aller Dateien in diesem Ordner: wozu sie da sind, wer sie
aufruft und wo sie dokumentiert sind. Aussortiertes liegt in `_archive/`
(Abschnitt 9).

**Aktiver Standardpfad:** `.leS` → Netz → Fließfläche. Details in
`LES_PIPELINE.md`. Der DICOM-Pfad bleibt als Alternative erhalten
(`SCAN_DATASET_WORKFLOW.md`), die Annahmen beider Wege stehen in
`PIPELINE_ANNAHMEN_DICOM_TO_FEM.md`.

---

## 1. Netzvorbereitung — die Kette im Prepare-Job

Aufgerufen von `run_prepare_mesh_CLUSTER.sh` in dieser Reihenfolge.
Schritte 1–4 laufen einmal, Schritte 5–11 je Subvolumen.

| # | Datei | Eingabe → Ausgabe | Config-Abschnitt |
|---|---|---|---|
| 1 | **`A01_les_2_npy.py`** | `.leS` → `segmented_3D_volume.npy` + `metadata.json` (`00_dicom2npy`, `02a_…`-Eintrag) | `A01_les_2_npy` |
| 1′ | `00_dicom_2_npy.py`, `01_segment_slice_wise.py`, `02_build3D_segmented_array.py`, `02a_rotate_pic_to_align_with_axis.py` | DICOM-Alternative zu Schritt 1 (nur wenn `A01_les_2_npy.enabled` ≠ true) | `dicom2npy`, `01_…`, `02_…`, `02a_…` |
| 2 | `02b_build_subvolume_arrays.py` | `segmented_3D_volume.npy` → `subvolume_x<i>_y<j>/volume.npy` | `02b_build_subvolume_arrays` |
| 3 | `02c_voxel_topology_cleanup.py` | `volume.npy` → `volume_topology.txt` (+ optional bereinigtes Volumen) | `02c_voxel_topology_cleanup` |
| 4 | `02d_axis_aligned_cuboid_crop.py` | `volume.npy` → `volume_boundary_shell_aniso.npy` (**Vernetzungs-Input**) | `02d_axis_aligned_cuboid_crop` |
| 5 | `03_mesh_3D_array_pygalmesh.py` | Voxelvolumen → `mesh.xdmf` (SDF → Marching Cubes → CGAL) | `03_mesh_3D_array` |
| 6 | `04_scale_and_translate_mesh_mod.py` | `mesh.xdmf` → auf physikalische Maße skaliert/verschoben | liest `metadata.json` |
| 7 | `05_tetgen_postprocess_mesh.py` | `mesh.xdmf` → nachbearbeitet + `.tetgen.log` | `05_tetgen_postprocess` |
| 8 | `08_mesh_quality_report.py` | `.tetgen.log` → `.quality.txt` | `08_mesh_quality_report` |
| 9 | `09_mesh_topology_audit.py` | `mesh.xdmf` → `.topology.txt` | `09_mesh_topology_audit` |
| 10 | `make_mesh_dlfx_compatible_cluster.py` | `mesh.xdmf` → `dlfx_mesh.xdmf/.h5` (im DolfinX-Container) | — |

`06_gmsh_postprocess_mesh.py` ist die Gmsh-Alternative zu Schritt 7. Der
Config-Abschnitt `06_gmsh_postprocess` steht auf `enabled: false`, und der
Prepare-Job ruft das Skript nicht auf — es ist derzeit **inaktiv**.

## 2. Fließflächen-Jobs

| Datei | Zweck | Aufgerufen von |
|---|---|---|
| `setup_yield_surface_jobs.sh` | Wrapper, liest `config.sh` | `02_create_folders_CLUSTER.sh`, manuell |
| `setup_yield_surface_jobs.py` | erzeugt N Belastungsrichtungen, je Richtung `config.json` + SLURM-Job + `parameters.txt`, dazu `manifest.csv` und `submit_all_yield_surface_points.sh` | `setup_yield_surface_jobs.sh` |
| `write_yield_surface_parameters.py` | rendert `parameters.txt` aus einer Config | `setup_yield_surface_jobs.py` |
| `job_yield_surface_point_CLUSTER.sh` | führt einen Punkt-Job aus: `00_template/elastoplastic.py` im DolfinX-Container → `yield_run_std_tensor.json` | die generierten `ys_*/job_*_CLUSTER.sh` |

## 3. Einreichen und Synchronisieren

| Datei | Zweck |
|---|---|
| `02_create_folders_CLUSTER.sh` | erzeugt die Punkt-Jobs und synchronisiert `$HOME/meshing/…` → `$HPC_SCRATCH/pygalmesh/…` (Login-Node) |
| **`submit_les_pipeline_CLUSTER.sh`** | reicht Netzvorbereitung ein und hängt alle Punkt-Jobs mit `--dependency=afterok` daran; Optionen `DEPEND_ON_JOB`, `SKIP_PREPARE`, `DRY_RUN` |
| `job_prepare_mesh_CLUSTER.sh` | SLURM-Wrapper der Netzvorbereitung; ohne Argument `config-A01-les.json` |
| `run_prepare_mesh_CLUSTER.sh` | die eigentliche Netzvorbereitung (Abschnitt 1); wählt anhand von `A01_les_2_npy.enabled` zwischen `.leS`- und DICOM-Kette. Hieß früher `job_prepare_mesh_Bin4_reduce_2_CLUSTER.sh`. |

## 4. Configs und ihre Generatoren

| Datei | Inhalt |
|---|---|
| `config.json` | **aktive Default-Config** aller Python-Skripte ohne `--config`; Kopie von `config-A01-les.json` |
| `config-A01-les.json` | `.leS`-Pipeline, Default der Cluster-Jobs |
| `config-Bin4-reduce-2.json` | DICOM-Pfad (Bin4, reduce 2) — zugleich **Vorlage**, aus der die `.leS`-Config abgeleitet wird |
| `config.sh` | Shell-Variablen für beide Generatoren; der `LES_*`-Block steuert die `.leS`-Config |
| `create_les_config.sh` → `create_les_dataset_config.py` | erzeugen `config-A01-les.json` aus einer bestehenden Config |
| `create_config.sh` | erzeugt die DICOM-Configs aus `config.sh` |
| `create_scan_dataset_config.py` | leitet eine DICOM-Config für einen weiteren Scan ab (`SCAN_DATASET_WORKFLOW.md`) |

## 5. Auswertung

| Datei | Zweck |
|---|---|
| `check_yield_surface_points.py` | prüft, welche Punkt-Jobs ein vollständiges `final_yield_state` haben |
| `collect_yield_surface_points.py` | sammelt gültige Punkte in `00_results/…/yield_surface_points.csv` |
| `create_yield_surface_paraview.py`, `create_yield_surface_paraview.sh` | Punktwolken + Konvexhüllen als VTK für ParaView; Option `--exclude-substring` |

## 6. Werkzeuge (nicht im automatischen Ablauf)

| Datei | Zweck |
|---|---|
| `A02_preview_voxel_volume.py` | Sichtprüfung eines Voxelvolumens: orthogonale Schnitte + zwei Schrägansichten, ohne VTK/OpenGL |
| `01_segmentation_topology_sweep.py` | Sweep über Segmentierungsparameter mit Topologiebewertung (DICOM-Pfad) |
| `07_pygalmesh_parameter_sweep.py` | Sweep über die Vernetzungsparameter; hat die aktuell verwendeten Faktoren `max_element_size_factor` und `max_facet_distance_factor` bestimmt |
| `evaluate_pore_size_distribution.py` | Porengrößenverteilung eines Voxelvolumens |
| `06_gmsh_postprocess_mesh.py` | Gmsh-Alternative zu `05`, derzeit deaktiviert (siehe Abschnitt 1) |

## 7. Dokumentation

| Datei | Inhalt |
|---|---|
| `CLAUDE.md` | Arbeitsweise, Ordnerstruktur, Konventionen — Einstiegspunkt |
| **`LES_PIPELINE.md`** | Bedienung der `.leS`-Pipeline: Datenablage, Auflösung, Config, Cluster-Kommandos |
| `README.md` | Fließflächen-Jobs auf dem Cluster (Erzeugen, Einreichen, Auswerten) |
| `PIPELINE_ANNAHMEN_DICOM_TO_FEM.md` | alle Algorithmen, Parameter und Annahmen von DICOM bis FEM — inkl. Phasenkonvention |
| `SCAN_DATASET_WORKFLOW.md` | DICOM-Workflow für weitere Scans |
| `CLAUDE_PROJECT_NOTES.md` | Session-Protokoll: was entschieden und gebaut wurde |
| `FILES.md` | diese Datei |

## 8. Daten- und Ergebnisordner

| Ordner | Inhalt |
|---|---|
| `A01_segmented/` | `.leS`-Quelldatei; `preview/` enthält reduzierte Volumen für Sichtprüfungen |
| `00_template/` | `elastoplastic.py` (DolfinX-Solver der Punkt-Jobs) und zugehörige Hilfsdateien |
| `00_results/` | gesammelte Fließflächen-Ergebnisse (48er- und n192-Studie) |
| `yield_surface_jobs/` | generierte Punkt-Jobs je Sampling |
| `<dataset>_segmented/` | wird von der Pipeline angelegt: Volumen, `metadata.json`, Netze |

## 9. `_archive/` — aussortiert

Keine dieser Dateien wird von einem aktiven Skript aufgerufen (geprüft per
Referenzsuche über alle `.py`/`.sh`/`.json`).

| Datei | Grund |
|---|---|
| `job_yield_surface_LOCAL.sh`, `job_yield_Bin4_reduce_2_LOCAL.sh` | lokaler Komplettlauf, ersetzt durch den Cluster-Weg |
| `job_yield_surface_from_scans_CLUSTER.sh`, `job_yield_Bin4_reduce_2_CLUSTER.sh` | Vorgänger der Punkt-Jobs (`setup_yield_surface_jobs` + `job_yield_surface_point_CLUSTER.sh`) |
| `create_yield_surface_n192.sh` | Einmal-Wrapper der n192-Auswertung |
| `package_yield_run_jsons.py`, `package_yield_run_std_tensor_CLUSTER.sh` | Einmal-Werkzeug zum Einsammeln der Ergebnis-JSONs |
| `04_scale_and_translate_mesh.py` | ersetzt durch `04_scale_and_translate_mesh_mod.py` |
| `make_mesh_dlfx_compatible.py` | ersetzt durch `make_mesh_dlfx_compatible_cluster.py` |
| `02a_rotate_pic_to_align_with_axis_bu.py` | Backup-Kopie |
| `PIPELINE_DOCUMENTATION.txt` | veraltete Gesamtübersicht; ersetzt durch `LES_PIPELINE.md`, `README.md` und `PIPELINE_ANNAHMEN_DICOM_TO_FEM.md` |

`_to_delete/` enthält nur Wegwerf-Material (`__pycache__`, `.DS_Store`, ein
lokaler Testlauf) und kann gelöscht werden.
