# Dateiverzeichnis 015-Yield-Surface-Batch-leS

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

## 1a. Batch-Schicht (neu in 015)

Acht Kombinationen: vier `.leS`-Datensaetze x zwei Anfangsfliessgrenzen
(75 / 100 MPa). Bedienung: **`README.md`**.

| Datei | Zweck | Aufgerufen von |
|---|---|---|
| `batch_lib.sh` | Namens- und Pfadlogik der Kombinationen (`batch_combos`, `batch_run_id`, `batch_binning_label`, ...), laedt `config.sh` | alle `batch_*`-Skripte |
| `batch_create_configs.sh` | erzeugt je Kombination `config-<ds>-r<N>-sigy<XXX>.json` ueber `create_les_config.sh` | `batch_create_folders_CLUSTER.sh`, manuell |
| `batch_setup_jobs.sh` | erzeugt je Kombination die Punkt-Jobs unter `yield_surface_jobs/<combo>/nNNN/` | `batch_create_folders_CLUSTER.sh`, manuell |
| `batch_create_folders_CLUSTER.sh` | die beiden obigen + `rsync` nach `$HPC_SCRATCH` (Login-Node) — Gegenstueck zu `02_create_folders_CLUSTER.sh` | manuell |
| `batch_submit_CLUSTER.sh` | 4 Netzvorbereitungen (eine je Datensatz) + alle Punkt-Jobs mit `--dependency=afterok`; prueft vorher das Queue-Limit | manuell |
| `batch_status_CLUSTER.sh` | Tabelle: Netz vorhanden, Jobs erzeugt, Ergebnisse da, Jobs in der Queue | manuell |
| `batch_collect_results.sh` | Wrapper: liest die Kombinationen aus `config.sh` und ruft den Sammler | manuell |
| `batch_collect_results.py` | sammelt alle `yield_run_*.json`, schreibt `summary.csv` + `yield_points_all.csv` (eine Zeile je Fliesskriterium) und zippt das Paket nach `00_results/_packages/` | `batch_collect_results.sh` |

## 2. Fließflächen-Jobs

| Datei | Zweck |
|---|---|
| `setup_yield_surface_jobs.sh` / `.py` | erzeugen N Belastungsrichtungen, je Richtung `config.json` + SLURM-Job + `parameters.txt`, dazu `manifest.csv` und `submit_all_yield_surface_points.sh`. Neu in 015: `--job-name-prefix` bzw. `YIELD_JOB_NAME_PREFIX` fuer kurze, eindeutige SLURM-Jobnamen (`JM-25-77_s075-ys000`) |
| `write_yield_surface_parameters.py` | rendert `parameters.txt` aus einer Config (von `setup_yield_surface_jobs.py` importiert) |
| `job_yield_surface_point_CLUSTER.sh` | führt einen Punkt-Job aus: `00_template/elastoplastic.py` im DolfinX-Container → `yield_run_std_tensor.json`. In 015 enthaelt `run_root` zusaetzlich das `binning_label` (Trennung der beiden sig_y), und nach `00_results` werden nur die Auswertungsdateien kopiert — `KEEP_FULL_RUN_COPY=1` stellt das Verhalten aus 014 wieder her. Seit 30.08.2026 restart-fähig: vorhandener Rechenstand im Zielordner wird fortgesetzt statt gelöscht (`YS_FORCE_FRESH=1` erzwingt Neustart). Ermittelt ausserdem die Job-Endzeit und gibt sie als `YIELD_WALLTIME_DEADLINE_EPOCH` an den Solver weiter; Exit-Code 3 des Solvers = kontrolliert vor dem Zeitlimit beendet, der Job endet dann bewusst mit != 0 |
| `resubmit_yield_surface_timeouts_CLUSTER.sh` | findet am Zeitlimit abgebrochene Punkt-Jobs über alle Kombinationen und reicht je Punkt eine Restart-Kette ein (`afternotok`-Dependencies, `MAX_CHAIN`, `DRY_RUN`, `INCLUDE_FAILED`); erkennt neben `DUE TO TIME LIMIT` auch den Marker `YIELD_WALLTIME_STOP` (kontrolliertes Beenden vor dem Zeitlimit); Details `RESTART_NACH_TIMEOUT.md` |

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
| **`health_check_CLUSTER.sh`** | schneller Gesundheits-Check: Queue je Kombination, Ergebnis-JSONs **ohne** `final_yield_state` (Alarm), MUMPS-Fehler/`dt too small`/Kriecher im neuesten `.out`, ob der MUMPS-Patch aktiv ist, Stand der drei Fließkriterien aus `restart_meta_*.json`. Exit 0/1/2 = OK/Warnung/Alarm. Optionen: `QUICK=1` (ohne Logscan), `DATASET=JM-25-77`, `CRAWL_LIMIT=n` |
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

## 7. Dokumentation

| Datei | Inhalt |
|---|---|
| `CLAUDE.md` | Arbeitsweise, Konventionen, Entscheidungen — Einstiegspunkt |
| `LES_PIPELINE.md` | Bedienung der Pipeline, Auflösungstabelle, Diagnose bei Abbrüchen |
| `README.md` | **Bedienung der Batch-Studie**: acht Kombinationen erzeugen, einreichen, überwachen, einsammeln und zippen |
| `PIPELINE_ANNAHMEN_DICOM_TO_FEM.md` | Algorithmen, Parameter und Annahmen der Kette bis zum FE-Netz (Name aus 010) |
| `CLAUDE_PROJECT_NOTES.md` | Session-Protokoll inkl. Vorgeschichte aus 010 |
| `FILES.md` | diese Datei |

## 8. Ordner

| Ordner | Inhalt |
|---|---|
| `00_template/` | `elastoplastic.py` (DolfinX-Solver der Punkt-Jobs, restart-fähig: setzt nach Timeout aus der eigenen XDMF/HDF5-Ausgabe fort, schreibt `restart_meta_*.json`; Feldausgabe ausgedünnt — Default ein Snapshot je 12 h Wandzeit — und beendet sich mit garantiertem letzten Snapshot vor dem SLURM-Zeitlimit selbst, Config-Blöcke `yield_surface.field_output` / `yield_surface.walltime`), `yield_restart.py` (Restart-Logik: XDMF zurücklesen, Partitionierung verifizieren, e_p/alpha rekonstruieren) und Hilfsdateien |
| `<dataset>_segmented/` | wird von der Pipeline angelegt: Volumen, `metadata.json`, Netze |
| `yield_surface_jobs/` | wird von `setup_yield_surface_jobs` angelegt; in 015 je Kombination: `<dataset>_sigy<XXX>/nNNN/` |
| `yield_surface_runs/` | Arbeitsordner der Punkt-Jobs: `<dataset>/<binning_label>/<sample_id>/` (vollstaendig, inkl. Netz und Feldausgabe) |
| `00_results/` | Auswertungsdateien je Kombination: `<dataset>/<binning_label>/yield_surface/...` |
| `00_results/_packages/` | fertige Ergebnispakete und Zips von `batch_collect_results.sh` |
| `A01_segmented/` | leer — die vier `.leS`-Dateien liegen unter `/data/resources/A01_segmented/` (siehe `README.md`, Abschnitt 0) |

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


## 10. Was gegenüber 014 dazugekommen ist

Die komplette Pipeline ist unverändert aus `014-Yield-Surface-From-leS`
übernommen. Neu sind nur die `batch_*`-Dateien aus Abschnitt 1a sowie drei
Änderungen an bestehenden Dateien (`config.sh`, `setup_yield_surface_jobs.py/.sh`,
`job_yield_surface_point_CLUSTER.sh`) — im Detail in `README.md`, Abschnitt 3.
`restore_010_pre_leS.sh` gibt es hier nicht mehr; es liegt in `_to_delete/`.
