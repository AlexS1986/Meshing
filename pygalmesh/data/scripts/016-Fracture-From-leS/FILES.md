# FILES.md — Dateiverzeichnis 016

Jede Datei mit Zweck, Aufrufer und zugehörigem Config-Abschnitt.
Herkunft: **015** = unverändert aus `015-Yield-Surface-Batch-leS`,
**012**/**011** = unverändert aus dem jeweiligen Bruchprojekt,
**neu** = für dieses Projekt geschrieben.

## Steuerung und Configs

| Datei | Herkunft | Zweck |
|---|---|---|
| `config.sh` | neu | Alle Steuervariablen: Datensatz, Riegel, Auflösungsfamilie `MESH_TIERS`, Bruchparameter, Job-Ressourcen. Wird von allen `*_CLUSTER.sh` und von `create_fracture_config.sh` eingelesen. |
| `config-A01-les-base.json` | 015 | 1:1-Kopie der in 015 gelaufenen `config-A01-les.json`. **Basis für alle Ableitungen** — nicht von Hand ändern. |
| `create_fracture_config.py` | neu | Erzeugt eine Bruch-Config: Riegel-Crop in mm → Indizes, `fracture`-Block, `mesh_resolution`, `fracture_geometry_check`; entfernt `yield_surface`. Nutzt `create_les_dataset_config.py` als Bibliothek. |
| `create_fracture_config.sh` | neu | Wrapper: liest `config.sh`, holt das Gitter aus dem `.leS`-Header, erzeugt alle Stufen aus `MESH_TIERS`. |
| `create_les_dataset_config.py` | 015 | Der Generator aus 015. Wird von `create_fracture_config.py` importiert, nicht direkt aufgerufen. |
| `config-fracture-<Probe>-{coarse,medium,fine}.json` | erzeugt | Die drei Auflösungsstufen. Werden von `02_create_folders_CLUSTER.sh` vor dem Sync neu erzeugt. |

## Vorverarbeitung und Vernetzung

| Datei | Herkunft | Zweck | Config-Abschnitt |
|---|---|---|---|
| `A01_les_2_npy.py` | 015 | `.leS` → `segmented_3D_volume.npy` + Metadaten. Ersetzt `00`/`01`/`02`/`02a` des DICOM-Zweigs. Streaming über `open_memmap`, RAM konstant ≈ 64 MB. | `A01_les_2_npy` |
| `A02_preview_voxel_volume.py` | 015 | Sichtprüfung: drei Schnitte + zwei Schrägansichten, nur numpy/scipy/matplotlib. | — |
| `A03_plot_les_structure.py` | 015 | Schnelle Bilder direkt aus der `.leS`-Datei (nutzt A01 + A02). | — |
| `A04_les_header_info.py` | neu | Liest nur die erste Zeile der `.leS`-Datei: `nx ny nz voxel_size`. Liefert `--format shell` für `create_fracture_config.sh`. | — |
| `02b_build_subvolume_arrays.py` | 015 | Teilvolumen (`xy_divisions`). | `02b_build_subvolume_arrays` |
| `02c_voxel_topology_cleanup.py` | 015 | Komponenten-/Kavitäten-Audit; Cleanup im Default aus. | `02c_voxel_topology_cleanup` |
| `02d_axis_aligned_cuboid_crop.py` | 015 | Randschale aus Aluminium (Wert 0) — trägt die Dirichlet-Ränder. | `02d_axis_aligned_cuboid_crop` |
| `02e_mirror_extrude_voxel.py` | 012 | Optional: Voxelvolumen in x spiegeln. **Default aus** — der Riegel kommt direkt aus dem Volumen. | `02e_mirror_extrude_voxel` |
| `02f_add_voxel_shell.py` | 012 | Optional: additive Außenschale nach dem Spiegeln. **Default aus**. | `02f_add_voxel_shell` |
| `03_mesh_3D_array_pygalmesh.py` | 015 | SDF → Marching Cubes → CGAL-Tetraeder. Enthält die automatische Oberflächenreparatur. | `03_mesh_3D_array` |
| `04_scale_and_translate_mesh_mod.py` | 015 | Netz auf mm skalieren und positionieren. | `03_mesh_3D_array` |
| `05_tetgen_postprocess_mesh.py` | 015 | TetGen-Nachbearbeitung. | `05_tetgen_postprocess` |
| `07_pygalmesh_parameter_sweep.py` | 015 | Parameterstudie zur Vernetzung (nur manuell). | — |
| `08_mesh_quality_report.py` | 015 | Qualitätsreport `mesh.quality.txt` (auch die Tetraederzahl). | `08_mesh_quality_report` |
| `09_mesh_topology_audit.py` | 015 | Topologie-Audit `mesh.topology.txt`. | `09_mesh_topology_audit` |
| `10_snap_mesh_to_crop_boundary.py` | 011 | Optional: Knoten nahe der Crop-Ebene auf die Ebene projizieren. **Default aus**. | `10_snap_mesh_to_crop_boundary` |
| `11_mirror_extrude_mesh.py` | 011 | Optional: Tetraedernetz spiegeln. **Default aus**. | `11_mirror_extrude_mesh` |
| `make_mesh_dlfx_compatible_cluster.py` | 015 | `mesh.xdmf` → `dlfx_mesh.xdmf/.h5` (läuft im DOLFINx-Container). | — |
| `evaluate_pore_size_distribution.py` | 015 | Porengrößen- und Stegdickenverteilung — Grundlage für die Wahl der Elementgröße. | — |

## Cluster-Jobs

| Datei | Herkunft | Zweck |
|---|---|---|
| `02_create_folders_CLUSTER.sh` | neu | Configs neu erzeugen und Projekt nach `$HPC_SCRATCH` spiegeln. `SKIP_CONFIGS=1` überspringt das Erzeugen. |
| `job_generate_mesh_CLUSTER.sh` | neu | SBATCH-Wrapper für Stufe 1 (Partition `mem`). |
| `run_generate_mesh_CLUSTER.sh` | neu | Der eigentliche Runner von Stufe 1 inklusive Archivierung. Kann auf einem Knoten auch direkt gestartet werden. |
| `job_run_simulation_CLUSTER.sh` | neu | Stufe 2: Phasenfeld-Bruch gegen das archivierte Netz (Partition über `-C i01`, `-t 10080`). |
| `submit_fracture_pipeline_CLUSTER.sh` | neu | Reiht beide Stufen mit `--dependency=afterok` ein. `SKIP_MESH`, `ONLY_MESH`, `DRY_RUN`. |

## Simulationstemplate

`00_template/` wird von `job_run_simulation_CLUSTER.sh` in jeden Netzordner
kopiert. Alles unverändert aus **011**:

| Datei | Zweck |
|---|---|
| `script.py` | Einstieg: liest `fracture.material_sets` und `fracture_toughness_sets` aus der Config, ruft `pfmfrac_function.run_simulation`, räumt die Ausgabedateien in einen `simulation_<zeitstempel>_…`-Ordner. |
| `pfmfrac_function.py` | Das Modell: Phasenfeld-Bruch mit Surfing-Randbedingungen, J-Integral aus dem Eshelby-Tensor, Rissspitzenverfolgung. |
| `linearelastic.py`, `linearelastic_pressure_test.py` | Elastische Vergleichsrechnungen (nicht Teil der Bruchkette). |
| `find_e33.py`, `write_e33_to_mesh.py`, `print_e_body_2_paraview.py`, `update_trafo.py`, `plot_pressure_experiment_results.py` | Auswertungshilfen aus 011. |
| `trafo.f`, `matfunc.f`, `dgefa.f`, `dgedi.f`, `dgesubs.f`, `Makefile`, `emodul.lay`, `.trafo.m` | Fortran-Materialroutinen aus 005/011. |

## Dokumentation

| Datei | Inhalt |
|---|---|
| `CLAUDE.md` | Wie in diesem Ordner gearbeitet wird; Konventionen und getroffene Entscheidungen. **Zuerst lesen.** |
| `LES_FRACTURE_PIPELINE.md` | Bedienung: Configs, Cluster, was die Simulation rechnet, Fehlerbilder. |
| `README.md` | Kurzeinstieg mit den vier Kommandos. |
| `CLAUDE_PROJECT_NOTES.md` | Laufendes Session-Protokoll und offene Punkte. |
| `PIPELINE_ANNAHMEN_DICOM_TO_FEM.md` | Aus 015: alle Algorithmen und Annahmen der Voxel→FEM-Kette. |
| `FILES.md` | Diese Datei. |
