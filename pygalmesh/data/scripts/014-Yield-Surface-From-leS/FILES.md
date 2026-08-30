# Dateiverzeichnis 014-Yield-Surface-From-leS

Jede Datei dieses Ordners mit Zweck, Aufrufer und Config-Abschnitt. Der
DICOM-Zweig aus `010-Yield-Surface-Generation` ist hier nicht enthalten; wer ihn
braucht, findet ihn dort.

---

## 1. Netzvorbereitung — die Kette im Prepare-Job

Aufgerufen von `run_prepare_mesh_CLUSTER.sh` in dieser Reihenfolge; Schritte 1–4
einmal, 5–10 je Subvolumen.

| # | Datei | Eingabe → Ausgabe | Config-Abschnitt |
|---|---|---|---|
| 1 | **`A01_les_2_npy.py`** | `.leS` → `segmented_3D_volume.npy` + `metadata.json` (`00_dicom2npy.SliceThickness`, `02a_…`-Eintrag für 02b) | `A01_les_2_npy` |
| 2 | `02b_build_subvolume_arrays.py` | `segmented_3D_volume.npy` → `subvolume_x<i>_y<j>/volume.npy` | `02b_build_subvolume_arrays` |
| 3 | `02c_voxel_topology_cleanup.py` | `volume.npy` → `volume_topology.txt` (Report; Bereinigung abschaltbar aktiviert) | `02c_voxel_topology_cleanup` |
| 4 | `02d_axis_aligned_cuboid_crop.py` | `volume.npy` → `volume_boundary_shell_aniso.npy` (**Vernetzungs-Input**) | `02d_axis_aligned_cuboid_crop` |
| 5 | `03_mesh_3D_array_pygalmesh.py` | Voxelvolumen → `mesh.xdmf` (SDF → Marching Cubes → Reparatur → CGAL) | `03_mesh_3D_array` |
| 6 | `04_scale_and_translate_mesh_mod.py` | `mesh.xdmf` → auf physikalische Maße skaliert | liest `metadata.json` |
| 7 | `05_tetgen_postprocess_mesh.py` | `mesh.xdmf` → nachbearbeitet + `.tetgen.log` | `05_tetgen_postprocess` |
| 8 | `08_mesh_quality_report.py` | `.tetgen.log` → `.quality.txt` | `08_mesh_quality_report` |
| 9 | `09_mesh_topology_audit.py` | `mesh.xdmf` → `.topology.txt` | `09_mesh_topology_audit` |
| 10 | `make_mesh_dlfx_compatible_cluster.py` | `mesh.xdmf` → `dlfx_mesh.xdmf/.h5` (DolfinX-Container) | — |

## 2. Fließflächen-Jobs

| Datei | Zweck |
|---|---|
| `setup_yield_surface_jobs.sh` / `.py` | erzeugen N Belastungsrichtungen, je Richtung `config.json` + SLURM-Job + `parameters.txt`, dazu `manifest.csv` und `submit_all_yield_surface_points.sh` |
| `write_yield_surface_parameters.py` | rendert `parameters.txt` aus einer Config (von `setup_yield_surface_jobs.py` importiert) |
| `job_yield_surface_point_CLUSTER.sh` | führt einen Punkt-Job aus: `00_template/elastoplastic.py` im DolfinX-Container → `yield_run_std_tensor.json`; seit 30.08.2026 restart-fähig: vorhandener Rechenstand im Zielordner wird fortgesetzt statt gelöscht (`YS_FORCE_FRESH=1` erzwingt Neustart) |
| `resubmit_yield_surface_timeouts_CLUSTER.sh` | findet am Zeitlimit abgebrochene Punkt-Jobs und reicht je Punkt eine Restart-Kette ein (`afternotok`-Dependencies, `MAX_CHAIN`, `DRY_RUN`, `INCLUDE_FAILED`); Details `RESTART_NACH_TIMEOUT.md` |

## 3. Einreichen und Synchronisieren

| Datei | Zweck |
|---|---|
| `02_create_folders_CLUSTER.sh` | erzeugt die Punkt-Jobs und synchronisiert `$HOME/meshing/…` → `$HPC_SCRATCH/pygalmesh/…` (Login-Node) |
| **`submit_les_pipeline_CLUSTER.sh`** | reicht Netzvorbereitung ein und hängt alle Punkt-Jobs mit `--dependency=afterok` daran; Optionen `DEPEND_ON_JOB`, `SKIP_PREPARE`, `DRY_RUN` |
| `job_prepare_mesh_CLUSTER.sh` | SLURM-Wrapper der Netzvorbereitung; ohne Argument `config-A01-les.json` |
| `run_prepare_mesh_CLUSTER.sh` | die eigentliche Netzvorbereitung (Abschnitt 1) |

## 4. Configs und Generatoren

| Datei | Inhalt |
|---|---|
| `config.json` | Default-Config aller Python-Skripte ohne `--config`; Kopie von `config-A01-les.json` |
| `config-A01-les.json` | die Config dieses Projekts; zugleich Vorlage für abgeleitete Varianten |
| `config.sh` | Steuervariablen (`LES_*`, Sampling der Fließfläche) |
| `create_les_config.sh` → `create_les_dataset_config.py` | erzeugen `config-A01-les.json` aus einer bestehenden Config |

## 5. Auswertung

| Datei | Zweck |
|---|---|
| `check_yield_surface_points.py` | prüft, welche Punkt-Jobs ein vollständiges `final_yield_state` haben |
| `collect_yield_surface_points.py` | sammelt gültige Punkte in einer CSV |
| `create_yield_surface_paraview.py`, `create_yield_surface_paraview.sh` | Punktwolken + Konvexhüllen als VTK für ParaView |

## 6. Werkzeuge

| Datei | Zweck |
|---|---|
| **`A03_plot_les_structure.py`** | schnelle 3D-Bilder direkt aus einer `.leS`-Datei (nutzt A01 zum Lesen, A02 zum Rendern); `--reduce`, `--x/y/z-range`, `--views`, `--slices`, `--keep-npy` |
| `A02_preview_voxel_volume.py` | dasselbe für ein beliebiges Voxelvolumen (`.npy`), z. B. den Vernetzungs-Input nach 02d |
| `07_pygalmesh_parameter_sweep.py` | Sweep über die Vernetzungsparameter; hat `max_element_size_factor` und `max_facet_distance_factor` bestimmt |
| `evaluate_pore_size_distribution.py` | Porengrößenverteilung eines Voxelvolumens |

## 6b. Einmal-Werkzeug: Rueckbau von 010

`restore_010_pre_leS.sh` setzt den Nachbarordner
`010-Yield-Surface-Generation` auf den Stand vor der .leS-Session zurueck
(Datei fuer Datei, weil ein pauschales `git checkout` auch aeltere,
erst heute mitcommittete Vorarbeit verwerfen wuerde). Laeuft von jedem
Verzeichnis aus, aendert nur den 010-Pfad und committet nichts.

## 7. Dokumentation

| Datei | Inhalt |
|---|---|
| `CLAUDE.md` | Arbeitsweise, Konventionen, Entscheidungen — Einstiegspunkt |
| `LES_PIPELINE.md` | Bedienung der Pipeline, Auflösungstabelle, Diagnose bei Abbrüchen |
| `README.md` | Fließflächen-Jobs auf dem Cluster |
| `PIPELINE_ANNAHMEN_DICOM_TO_FEM.md` | Algorithmen, Parameter und Annahmen der Kette bis zum FE-Netz (Name aus 010) |
| `CLAUDE_PROJECT_NOTES.md` | Session-Protokoll inkl. Vorgeschichte aus 010 |
| `FILES.md` | diese Datei |

## 8. Ordner

| Ordner | Inhalt |
|---|---|
| `00_template/` | `elastoplastic.py` (DolfinX-Solver der Punkt-Jobs, restart-fähig: setzt nach Timeout aus der eigenen XDMF/HDF5-Ausgabe fort, schreibt `restart_meta_*.json`), `yield_restart.py` (Restart-Logik: XDMF zurücklesen, Partitionierung verifizieren, e_p/alpha rekonstruieren) und Hilfsdateien |
| `<dataset>_segmented/` | wird von der Pipeline angelegt: Volumen, `metadata.json`, Netze |
| `yield_surface_jobs/` | wird von `setup_yield_surface_jobs` angelegt |
| `00_results/` | wird von der Auswertung angelegt |

## 9. Was gegenüber 010 fehlt

`00_dicom_2_npy.py`, `01_segment_slice_wise.py`, `02_build3D_segmented_array.py`,
`02a_rotate_pic_to_align_with_axis.py`, `01_segmentation_topology_sweep.py`,
`06_gmsh_postprocess_mesh.py`, `create_config.sh`, `create_scan_dataset_config.py`,
`config-Bin4-reduce-2.json`, `SCAN_DATASET_WORKFLOW.md` sowie das Archiv der alten
Ausführungswege. Der Prepare-Runner hat keine Quellen-Weiche mehr, die Config
keine `dicom2npy`- und `02_segmented_3D_array`-Abschnitte. Zwei Reste bleiben,
weil andere Skripte sie lesen: `01_segment_slice_wise.specimen_name`
(`job_yield_surface_point_CLUSTER.sh`) und `02a_….material_value/pore_value`
(`A01_les_2_npy.py` für den Metadateneintrag, den `02b` erwartet).
