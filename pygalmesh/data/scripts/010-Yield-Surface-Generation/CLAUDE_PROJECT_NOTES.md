# Projekt-Notizen: 010-Yield-Surface-Generation

Diese Datei dokumentiert, was in diesem Ordner verstanden, entschieden und
gebaut wurde. Sie wird von Claude gepflegt (gelesen und editiert) und liegt
bewusst direkt im Projektordner, damit sie in künftigen Sessions wieder
gefunden wird.

## Wo liegt der Code (Kurzreferenz)

Projekt-Root: `~/Work/Hypo/Hypo/Simulation` (Container-Bind:
`Meshing/pygalmesh/data` → `/data`).

- Preprocessing + Vernetzung: `Meshing/pygalmesh/data/scripts/010-Yield-Surface-Generation/`
- Simulationstemplate: `.../010-Yield-Surface-Generation/00_template/elastoplastic.py`
- DolfinX-Module: `dolfinx_alex/shared/utils/alex/` (`plasticity.py`,
  `homogenization.py`, `boundaryconditions.py`, `materials.py`,
  `postprocessing.py`, `linearelastic.py`, `imageprocessing.py`)
- CT-Rohdaten: `Meshing/pygalmesh/data/resources/`
- Verwandte Studien: `009-Binning-Variation-CT-Stiffness` (linear-elastisch),
  `007-Plasticity-From-CT-Scans` (Solver-Ursprung),
  `011-Fracture-From-CT-Scans` / `012-Fracture-Mesh-Sim-Split`

Detaillierte Beschreibung von DICOM → segmentiertem Array → FEM-Netz inklusive
aller Algorithmen, Parameter und Annahmen:
**`PIPELINE_ANNAHMEN_DICOM_TO_FEM.md`** (in diesem Ordner).

## Was macht dieses Projekt

Pipeline zur Erzeugung einer Fließfläche (yield surface) für ein
CT-basiertes Mikrostruktur-Netz (Bin4, reduce-2). Elasto-plastisches
Pendant zu `009-Binning-Variation-CT-Stiffness`: gleiche CT-Vorverarbeitung
und Vernetzung, aber am Ende ein elasto-plastischer DolfinX-Solve
(`00_template/elastoplastic.py`, abgeleitet aus
`007-Plasticity-From-CT-Scans`).

Materialmodell (Standard-Konfiguration, Material `std`):
- E = 70000.0, nu = 0.35, sig_y = 140.0, hard = 0.0

Ablauf:
1. `setup_yield_surface_jobs.sh N` erzeugt N Belastungsrichtungen im
   eps_1/eps_2/eps_3-Raum (bei N>6 per Fibonacci-Sphere-Sampling) unter
   `yield_surface_jobs/nNNN/`, je Richtung ein eigener Job-Ordner mit
   `config.json` + SLURM-Skript.
2. Mesh-Vorbereitung einmalig (`job_prepare_mesh_Bin4_reduce_2_CLUSTER.sh`).
3. Alle N Punkt-Jobs werden unabhängig submittet
   (`submit_all_yield_surface_points.sh`).
4. Jeder Job steigert eine diagonale Makro-Dehnung
   `strain_scale(t) * [eps_1, eps_2, eps_3]` bis der konfigurierte Anteil
   des reduzierten Materialvolumens fließt (`alpha > alpha_yield_tolerance`,
   Default-Zielanteil 2 %). Ergebnis: `final_yield_state` in
   `yield_run_std_tensor.json` mit u.a. `eps_mac_eigenvalues_current` und
   `sigma_avg_reduced_volume`.
5. `collect_yield_surface_points.py` sammelt gültige Endzustände in einer
   CSV.
6. `create_yield_surface_paraview.py` liest rekursiv alle JSONs mit
   vollständigem `final_yield_state`, dedupliziert Punkte und schreibt
   Punktwolken + Konvexhüllen-VTKs für Dehnung, Fixachsen-Spannung und
   Hauptspannung nach `00_results/.../yield_surface_paraview/`.

## Stand der Daten unter `00_results/`

- `00_results/yield_run_std_tensor_jsons/` + `00_results/yield_surface_paraview/`:
  bereits ausgewertete **48-Punkte-Studie** (ys_000–ys_047, ältere/gröbere
  Sampling-Auflösung).
- `00_results/n192/yield_run_std_tensor_jsons/` (auch als `.zip` vorhanden):
  die **192-Punkte-Studie**. Enthält aber **240 JSON-Dateien**, nicht 192:
  - 192 Dateien im neuen Namensschema
    (`ys_NNN_..._e3_<val>__target_...__std_tensor.json`) – das eigentliche
    n192-Sampling.
  - 48 zusätzliche Dateien im alten Namensschema mit `-std-tensor__target`
    direkt nach dem letzten eps-Wert – das sind Kopien der alten 48er-Studie,
    die mit kollidierenden `ys_000`–`ys_047`-Indizes in denselben Ordner
    gemischt wurden (gleicher Inhalt wie oben, nur andere eps-Werte als die
    "echten" n192-Punkte mit demselben Index).
  - **Entscheidung:** Für die n192-Fließfläche werden nur die 192 Dateien
    im neuen Namensschema verwendet; die 48 alten Duplikate werden über
    einen Dateinamen-Ausschlussfilter (`-std-tensor__target`) ausgeschlossen.
  - Von den 192 n192-Dateien haben **153** ein vollständiges
    `final_yield_state` (eps/sigma endlich); die restlichen 39 haben im
    Solver-Horizont keinen Fließzustand erreicht (`_na_` im Dateinamen) und
    werden vom Skript ohnehin automatisch übersprungen.

## Vorbereitetes Skript (noch nicht ausgeführt)

Auf Wunsch des Nutzers wurde das Skript nur **vorbereitet**, nicht
ausgeführt — der Nutzer führt es selbst lokal im Container aus.

- `create_yield_surface_paraview.py` wurde um eine optionale Option
  `--exclude-substring` erweitert (generisch nutzbar, filtert Dateinamen).
- Neuer Wrapper `create_yield_surface_n192.sh` ruft das Hauptskript mit den
  richtigen Pfaden und dem Ausschlussfilter für die n192-Studie auf:

  ```bash
  ./create_yield_surface_n192.sh
  ```

  Erwartete Ausgabe unter:
  `00_results/n192/yield_surface_paraview/`
  (`yield_surface_points.csv`, `yield_surface_strain.vtk`,
  `yield_surface_stress_normal.vtk`, `yield_surface_stress_principal.vtk`)

## Offene Punkte / mögliche nächste Schritte

- Prüfen, ob die 48 "alten" Duplikat-Dateien im n192-Ordner aufgeräumt
  (gelöscht oder in einen eigenen Unterordner verschoben) werden sollen,
  statt sie nur beim Erzeugen der Fließfläche zu filtern.
- `--expand-principal-permutations` nur verwenden, falls isotrope Antwort
  angenommen werden darf (siehe README.md, Abschnitt 7).

## Neue Datenquelle: segmentierte .leS-Voxelbilder (A01)

- Rohdatei `JM-25_77_85p55.leS` (2,5 GB) liegt jetzt unter
  `A01_segmented/` (Container: `/data/scripts/010-Yield-Surface-Generation/A01_segmented/`).
- Neues Skript `A01_les_2_npy.py` konvertiert `.leS` → `volume.npy`
  (uint8, Shape `(x, y, z)`, 0 = Pore, 1 = Material) und schreibt eine
  Sidecar-JSON mit Voxelgröße, Labelhistogramm und Porosität.
- Format verifiziert: Header `nx ny nz voxel_size` = `1187 1188 886 1.67e-05`,
  danach genau `nx*ny` Zeilen mit je `nz` Werten (Voxelsäulen entlang z),
  Zeilenindex `l = ix*ny + iy` (C-Order). Feste Zeilenbreite 1773 Byte.
- Verifikation: Ausschnitt `x[600:602]` bitgleich mit den Rohzeilen;
  Übergangsdichte 0,94/0,96/1,00 % in x/y/z (bei falscher Ordnung wären ~21 %
  zu erwarten); mittlerer Materialanteil ≈ 15 % → Porosität ≈ 85 %, passend
  zum `85p55` im Dateinamen.
- Volles Volumen = 1,25 GVoxel = 1,25 GB `.npy`; für Vernetzung Ausschnitt
  über `--x-range/--y-range/--z-range` direkt beim Konvertieren wählen.
- Offen: Einheit für `00_dicom2npy.SliceThickness` (m vs. mm) beim Übergeben
  der Voxelgröße 1,67e-05 m an `03_mesh_3D_array_pygalmesh.py` prüfen.
- Übergeordnete Arbeitsweise/Ordnerkonventionen: siehe `CLAUDE.md` (liegt in
  diesem Ordner und im Publications-Ordner
  `~/Work/Hypo/Hypo/Publications/Folgepaper Homogenisierung von elasto-plastischen Eigenschaften/`).

## .leS-Pipeline ist jetzt der Default (A01)

Die Cluster-Pipeline kann den Datensatz `JM-25-77*.leS` direkt verwenden.
Bedienung, Reduktionstabelle und Kommandos: **`LES_PIPELINE.md`**.

Entscheidungen dieser Session:

- **Integration ohne zweites Jobskript:** `job_prepare_mesh_Bin4_reduce_2_CLUSTER.sh`
  entscheidet anhand von `A01_les_2_npy.enabled` in der Config, ob `A01_les_2_npy.py`
  oder die DICOM-Kette `00/01/02/02a` läuft. Ab `02b` ist der Ablauf identisch.
- **02a entfällt im .leS-Pfad**: das Volumen ist bereits segmentiert und
  achsparallel; A01 schreibt den von `02b` gelesenen Metadateneintrag
  (`input_path`, `material_value`, `material_bounds`) selbst. Das vermeidet auch
  die float64-Konvertierung in 02a (beim vollen Volumen ~10 GB).
- **Default-Configs umgestellt:** `job_prepare_mesh_CLUSTER.sh` und
  `setup_yield_surface_jobs.sh` verwenden ohne Argument `config-A01-les.json`.
  Der DICOM-Pfad bleibt über das Config-Argument bzw. `YIELD_SURFACE_BASE_CONFIG`
  nutzbar.
- **Auflösung:** Default `reduce = 2` (593x594x443, 33,4 µm). Majority-Vote
  über die Aluminiumphase; Änderung der relativen Dichte < 0,15 Prozentpunkte.
  `reduce = 8` (133,6 µm) entspricht der Auflösung der bisherigen
  `Bin4-reduce-2`-Studie und wäre die vergleichbare Wahl.
- **Kein zusätzlicher Gauß-Filter auf den Labels.** Der Gauß in `01`/`03` ist mit
  σ = `sigma_factor × SliceThickness` bei mm-Voxelgrößen wirkungslos (σ ≈ 0,03
  Voxel); wirksam ist nur `sdf_sigma_voxels = 1.0` in Schritt 03. Optionaler
  Schalter `reduce.smooth_sigma` (Default 0) für Experimente bei großen
  Reduktionsfaktoren.
- **Phasenkonvention:** die .leS-Datei hat 1 = Material, die Pipeline erwartet
  vor Schritt 03 aber 1 = Pore / 0 = Aluminium. A01 invertiert deshalb per
  Default (`phase_convention = "pipeline"`). Ohne diese Inversion würde Schritt 03
  den Porenraum vernetzen.

Neue Dateien in diesem Ordner: `A01_les_2_npy.py`, `A02_preview_voxel_volume.py`,
`create_les_dataset_config.py`, `create_les_config.sh`, `config-A01-les.json`,
`LES_PIPELINE.md`, `CLAUDE.md`; geändert: `config.sh` (LES_*-Block),
`job_prepare_mesh_CLUSTER.sh`, `job_prepare_mesh_Bin4_reduce_2_CLUSTER.sh`,
`setup_yield_surface_jobs.sh`.

Verifikation: Unit-Tests gegen synthetische .leS-Dateien (Phasenkonvention,
reduce-Modi, Crop-Kürzung, F-Order, Puffergrößen, Config-Modus, bounds_mode) und
ein End-to-End-Lauf auf den echten Daten (`A01 -> 02b -> 02d`, reduce=8) mit
korrekter Randschale. `02c` (scipy) und `03` (nanomesh) sind lokal nicht
lauffähig und wurden nicht ausgeführt.

### Nachtrag: Einreichen als Jobkette

- `submit_les_pipeline_CLUSTER.sh` (neu) reicht `job_prepare_mesh_CLUSTER.sh` ein
  und haengt alle Punkt-Jobs per `--dependency=afterok:<prep-id>` daran
  (`--kill-on-invalid-dep=yes`). Damit ist nach `02_create_folders_CLUSTER.sh`
  nur noch ein Aufruf noetig. Optionen: `SKIP_PREPARE=1`, `DRY_RUN=1`,
  Argumente `<config> <punkte>`.
- Das mitgenerierte `submit_all_yield_surface_points.sh` bleibt nutzbar, muss
  aber mit `bash` gestartet werden: es leitet seinen Pfad aus `BASH_SOURCE` ab,
  was unter `sbatch` auf das SLURM-Spool-Verzeichnis zeigen wuerde.
- Der Default des inneren `job_prepare_mesh_Bin4_reduce_2_CLUSTER.sh` wurde
  ebenfalls auf `config-A01-les.json` gesetzt (vorher `config-Bin4-reduce-2.json`),
  damit ein direktes `sbatch` auf dieses Skript nicht stillschweigend den
  DICOM-Pfad laeuft. README Abschnitt 4 verweist jetzt auf den Wrapper.
