# Projekt-Notizen 015-Yield-Surface-Batch-leS

Dieser Ordner ist am 20.08.2026 aus `014-Yield-Surface-From-leS` kopiert worden.
Die Pipeline ist **unveraendert**; neu ist eine Batch-Schicht fuer vier
`.leS`-Datensaetze x zwei Anfangsfliessgrenzen. Bedienung: `README.md`.

## Entscheidungen dieser Session (20.08.2026)

**Studie.** Vier segmentierte Voxelbilder x zwei Anfangsfliessgrenzen:

| | |
|---|---|
| Datensaetze | `JM-25-77` (`JM-25_77_85p55.leS`), `JM-25-71` (`JM-25-71_79p85.leS`), `JM-25-83` (`JM-25-83_80p55.leS`), `JM-25-88` (`JM-25-88_78p86.leS`) |
| sig_y | 75 MPa und 100 MPa (Materialsatz `std`) |
| Aufloesung | `reduce = 2` wie in 014 (Nutzerentscheidung), Elementgroesse 75 um |
| Punkte je Kombination | 96 (Fibonacci-Sphere) |
| Zeitlimit je Punkt-Job | `-t 10080` Minuten (7 d, Maximum der Partition `long`; bis 30.08.2026 `-t 3000`) |

**Ein Netz je Datensatz, nicht je Kombination.** Das Netz haengt nicht von
`sig_y` ab. Beide sig_y-Varianten bekommen deshalb dieselbe `dataset.id`
(`<ds>_les_r2`) und benutzen dasselbe vorbereitete Netz; die Netzvorbereitung
laeuft nur vier Mal. Unterschieden werden die Laeufe ueber
`binning.label` = `leS-r2-sigy075` bzw. `leS-r2-sigy100`, das in allen
Ergebnispfaden auftaucht.

**Daraus folgte eine noetige Korrektur an `job_yield_surface_point_CLUSTER.sh`:**
`run_root` war `yield_surface_runs/<dataset_id>/<sample_id>`. Da beide sig_y
dieselbe `dataset_id` haben und die `sample_id` nur aus Index und
Dehnungsrichtung besteht, haetten sich die beiden Varianten desselben Punktes
denselben Arbeitsordner geteilt und sich gegenseitig ueberschrieben. `run_root`
enthaelt jetzt zusaetzlich das `binning_label`.

**Langes Zeitlimit erzwingt `-p long`.** Die Default-Partition `deflt` erlaubt
maximal 1440 Minuten und lehnt alles darueber mit *"Requested time limit is
invalid"* ab. `long` hat dieselben i01-Knoten und bis zu 7 Tage. In `config.sh`
stehen deshalb `YIELD_JOB_TIME=10080` (seit 30.08.2026, vorher 3000) **und**
`YIELD_JOB_PARTITION=long`. Die Netzvorbereitung
bleibt auf `mem` mit 1440 Minuten (ueber `PREP_JOB_TIME` auf der
sbatch-Kommandozeile ueberschreibbar, weil SBATCH-Header nicht expandiert
werden).

**Punktzahl 96 statt 192 — wegen des Queue-Limits.** Account `p0023647`:
`MaxSubmit = 1000`, `MaxJobs = 400`. 8 Kombinationen x 192 = 1536 Jobs waeren
nicht einreihbar; 8 x 96 + 4 Netzvorbereitungen = 772 passen. `MaxJobs` begrenzt
nur, wie viele gleichzeitig *laufen* — der Rest wartet als PENDING.
`batch_submit_CLUSTER.sh` zaehlt vor dem Einreichen `squeue -u $USER` und bricht
ab, statt in ein Limit zu laufen; `ONLY_SIG_Y` / `ONLY_DATASETS` erlauben
teilweises Einreichen.

**Kurze SLURM-Jobnamen.** 768 Jobs mit dem Namen `ys_000_e1_...` waeren in
`squeue` nicht zuzuordnen. `setup_yield_surface_jobs.py` kennt jetzt
`--job-name-prefix`; die Batch-Schicht setzt ihn auf `<dataset>_s<sigy>`, der
Jobname wird `JM-25-77_s075-ys000`. Der lange Name bleibt Ordnername und steht
zusaetzlich als `job_name` im `manifest.csv`.

**`00_results` bekommt nur noch die Auswertungsdateien.** In 014 kopierte jeder
Punkt-Job seinen kompletten Arbeitsordner (Netz, XDMF/H5, Voxelvolumen) nach
`00_results`. Bei 768 Jobs waeren das mehrere hundert GB auf dem Scratch.
Default in 015: nur `yield_run_*.json`, `yield_averages_*.json`, `*.txt`,
`*.log`, `*.png`. `KEEP_FULL_RUN_COPY=1` stellt das alte Verhalten her; die
vollstaendigen Laufordner bleiben ohnehin unter `yield_surface_runs/`.

**Einsammeln und Zippen.** `batch_collect_results.sh` (+ `.py`, nur
Standardbibliothek, laeuft ohne Container auf dem Login-Node) legt unter
`00_results/_packages/<name>/` ein Paket an und zippt es:

- `summary.csv` — je Kombination erwartet / gefunden / mit `final_yield_state`
- `yield_points_all.csv` — alle Punkte aller Kombinationen, **eine Zeile je
  Fliesskriterium** (`criterion`-Spalte: `final`, `eps_p_eq_macroscopic`,
  `alpha_avg_material`, `yielded_fraction_material`). Damit sind die drei
  Fliessflaechen aus einem Lauf direkt auswertbar, ohne die JSONs erneut zu
  oeffnen.
- je Kombination `config.json`, `manifest.csv`, `parameters.txt`, die
  Netzreports und die unveraenderten `yield_run_*.json`.

`collect_yield_surface_points.py` aus 014 bleibt liegen, taugt fuer die Studie
aber nicht: es leitet die `dataset_id` aus dem Pfad ab und wuerde die beiden
sig_y-Varianten in eine CSV mischen.

**Dateinamen der Datensaetze mischen `-` und `_`** (`JM-25_77_85p55.leS` gegen
`JM-25-71_79p85.leS`). `batch_lib.sh` sucht deshalb bei fehlendem Treffer per
Glob `JM-25[-_]<nummer>*.leS` und meldet, welche Datei es genommen hat.

**Nicht ausgefuehrt.** Wie in 014 wurden die Skripte nur vorbereitet. Geprueft
wurden: Erzeugung aller acht Configs, Erzeugung der Punkt-Jobs (Testlauf mit 6
Punkten je Kombination, korrekte `-t <YIELD_JOB_TIME> -p long`-Header und eindeutige
Jobnamen), `batch_submit_CLUSTER.sh` im `DRY_RUN`, sowie
`batch_collect_results.sh` gegen synthetische Ergebnis-JSONs (Paketstruktur,
CSV-Spalten, Zip). Netzvorbereitung und DolfinX-Solve sind lokal nicht
lauffaehig und wurden nicht gerechnet.

**Offen.**

- Ob `reduce = 2` fuer alle vier Datensaetze bezahlbar ist, zeigt erst die erste
  Netzvorbereitung (`sacct -j <prep-jobid> --format=JobID,MaxRSS,Elapsed`).
  Die anderen drei Datensaetze koennen andere Gittergroessen haben als JM-25-77.
- Randschalendicke (8/12/8 Voxel) ist an JM-25-77 kalibriert und sollte fuer die
  drei neuen Datensaetze anhand ihrer Voxelgroesse geprueft werden.
- Zeitlimit je Punkt-Job seit 30.08.2026 `-t 10080` = 7 d, also das Maximum der
  `long`-Partition. Mehr geht nicht; laengere Rechnungen laufen ueber die
  Fortsetzungskette (`resubmit_yield_surface_timeouts_CLUSTER.sh`).

---

## Vorgeschichte (uebernommen aus 014)

Dieser Ordner ist am 18.08.2026 aus `010-Yield-Surface-Generation` abgespalten
worden: gleicher Stand, aber **ohne den DICOM-Zweig**. Das folgende Protokoll ist
aus 010 übernommen und enthält deshalb auch die Vorgeschichte des DICOM-Pfads;
was hier nicht mehr existiert, steht in `FILES.md`, Abschnitt 9.

Unterschiede zu 010 zum Zeitpunkt der Abspaltung:

- kein DICOM-Zweig (`00`, `01`, `02`, `02a`, `create_config.sh`,
  `create_scan_dataset_config.py`, `config-Bin4-reduce-2.json`,
  `SCAN_DATASET_WORKFLOW.md`, `01_segmentation_topology_sweep.py`,
  `06_gmsh_postprocess_mesh.py`) und keine Quellen-Weiche im Prepare-Runner;
- `sdf_pygalmesh_parameters.keep_largest_component` ist **Default `true`**;
- neu: `A03_plot_les_structure.py` für schnelle 3D-Bilder direkt aus `.leS`.

---

# Projekt-Notizen: 015-Yield-Surface-Batch-leS

Diese Datei dokumentiert, was in diesem Ordner verstanden, entschieden und
gebaut wurde. Sie wird von Claude gepflegt (gelesen und editiert) und liegt
bewusst direkt im Projektordner, damit sie in künftigen Sessions wieder
gefunden wird.

## Wo liegt der Code (Kurzreferenz)

Projekt-Root: `~/Work/Hypo/Hypo/Simulation` (Container-Bind:
`Meshing/pygalmesh/data` → `/data`).

- Preprocessing + Vernetzung: `Meshing/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS/`
- Simulationstemplate: `.../015-Yield-Surface-Batch-leS/00_template/elastoplastic.py`
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
2. Mesh-Vorbereitung einmalig (`run_prepare_mesh_CLUSTER.sh`).
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
  `A01_segmented/` (Container: `/data/scripts/015-Yield-Surface-Batch-leS/A01_segmented/`).
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

- **Integration ohne zweites Jobskript:** `run_prepare_mesh_CLUSTER.sh`
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
`job_prepare_mesh_CLUSTER.sh`, `run_prepare_mesh_CLUSTER.sh`,
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
- Der Default des inneren `run_prepare_mesh_CLUSTER.sh` wurde
  ebenfalls auf `config-A01-les.json` gesetzt (vorher `config-Bin4-reduce-2.json`),
  damit ein direktes `sbatch` auf dieses Skript nicht stillschweigend den
  DICOM-Pfad laeuft. README Abschnitt 4 verweist jetzt auf den Wrapper.

### Aufräumen des Ordners (Inventar)

- Neu: **`FILES.md`** — vollständiges Dateiverzeichnis mit Zweck, Aufrufer und
  Config-Abschnitt je Datei, inklusive der Kette im Prepare-Job in Reihenfolge.
- `_archive/` (nicht mehr aufgerufen, per Referenzsuche geprüft):
  `job_yield_surface_LOCAL.sh`, `job_yield_Bin4_reduce_2_LOCAL.sh`,
  `job_yield_surface_from_scans_CLUSTER.sh`, `job_yield_Bin4_reduce_2_CLUSTER.sh`,
  `create_yield_surface_n192.sh`, `package_yield_run_jsons.py`,
  `package_yield_run_std_tensor_CLUSTER.sh`, `04_scale_and_translate_mesh.py`,
  `make_mesh_dlfx_compatible.py`, `02a_rotate_pic_to_align_with_axis_bu.py`,
  `PIPELINE_DOCUMENTATION.txt`.
- `config.json` ist jetzt eine Kopie von `config-A01-les.json` (vorher identisch
  mit `config-Bin4-reduce-2.json`). Damit trifft ein Aufruf ohne `--config` den
  aktiven Standardpfad; DICOM braucht explizit
  `--config config-Bin4-reduce-2.json`.
- Behalten wurden der komplette DICOM-Zweig (00/01/02/02a + Generatoren; die
  Bin4-Config ist zugleich die Vorlage der .leS-Config) und die
  Analyse-/Sweep-Werkzeuge (`01_segmentation_topology_sweep.py`,
  `07_pygalmesh_parameter_sweep.py`, `evaluate_pore_size_distribution.py`).
- `06_gmsh_postprocess_mesh.py` ist im Cluster-Pfad **inaktiv** (nur der jetzt
  archivierte LOCAL-Weg rief es auf, Config-Abschnitt steht auf `enabled: false`).

### Umbenennung des Prepare-Runners

`job_prepare_mesh_Bin4_reduce_2_CLUSTER.sh` heißt jetzt
**`run_prepare_mesh_CLUSTER.sh`** — der alte Name suggerierte, es laufe die
DICOM-Bin4-Kette, obwohl das Skript seit der .leS-Umstellung quellenunabhängig
ist (Weiche über `A01_les_2_npy.enabled`). Alle Referenzen wurden angepasst
(`job_prepare_mesh_CLUSTER.sh`, `job_yield_surface_point_CLUSTER.sh`,
`FILES.md`, `CLAUDE.md`, `LES_PIPELINE.md`, `PIPELINE_ANNAHMEN_DICOM_TO_FEM.md`),
der SLURM-Jobname im Kopf des Skripts lautet jetzt `prep-ys-mesh`.
Die alte Datei liegt unverändert in `_archive/`.

**Achtung beim Sync:** Ein bereits eingereihter Prepare-Job ruft den alten
Dateinamen auf dem Scratch auf. Da `rsync` ohne `--delete` läuft, bleibt die
alte Datei dort liegen und der Job funktioniert weiter. Erst nach Abschluss
laufender Prepare-Jobs auf dem Scratch aufräumen.

### Abbruch in Schritt 03: "SDF surface is not watertight/manifold"

Reproduktion des SDF-Schritts außerhalb der Pipeline (numpy/scipy/skimage/trimesh,
identische Kette: EDT -> Gauß -> Marching Cubes -> trimesh-Reparatur -> Kantenaudit)
an Ausschnitten des Datensatzes JM-25-77:

| Fall | Ergebnis |
|---|---|
| reduce=8, Randschale 3/12/3, sigma=1.0, pad=1 | watertight, 0 offene/nicht-mannigfaltige Kanten -> good |
| reduce=4, ebenso | good (4,66 Mio. Flächen, 561 Oberflächenkomponenten) |
| reduce=2 (300³-Ausschnitt), ebenso | good (4,44 Mio. Flächen) |
| reduce=2, **sigma=1.25 bei pad_width=1** | **7180 offene Kanten -> bad** |
| reduce=2, sigma=1.25 bzw. 1.5 bei **pad_width=3** | wieder good |

Schlussfolgerung: `pad_width = 1` ist grenzwertig, sobald die Randschale aus 02d
bis an den Arrayrand reicht — die geglättete Isofläche läuft aus dem gepolsterten
Array heraus und wird abgeschnitten. Das ist der wahrscheinlichste Grund für den
Abbruch im vollen Gebiet (593x594x443), das rund 2,5-mal so viel Randfläche hat
wie der getestete Ausschnitt.

**Änderung:** `sdf_pygalmesh_parameters.pad_width` wird vom Config-Generator auf
**3** gesetzt (`LES_SDF_PAD_WIDTH` in `config.sh`); der Versatz wird nach Marching
Cubes herausgerechnet, die Geometrie ändert sich dadurch nicht. Neu außerdem
`LES_KEEP_LARGEST_COMPONENT` (Default false).

Struktur des Datensatzes (300³-Ausschnitt, reduce=2): 228 Aluminiumkomponenten,
die größte mit 99,978 % des Materials, 227 freischwebende Inseln (206 davon
<= 10 Voxel); 403 Porenkomponenten, also 402 eingeschlossene Kavitäten. Die
Inseln beschädigen die Oberfläche nicht, erzeugen im FE aber Starrkörpermoden.

**Korrektur einer früheren Empfehlung:** "bei zu treppiger Oberfläche
`sdf_sigma_voxels` auf 1,25-1,5 erhöhen" gilt nur mit `pad_width >= 3`.

### Ursache des 03-Abbruchs (aufgeklärt)

Der Topologie-Report des vollen Laufs (reduce=2, 593x594x443):

```
surface_open_edges: 0        surface_nonmanifold_edges: 3
surface_duplicate_faces: 2   surface_watertight: False
surface_faces: 23 087 896    surface_components: 1520
```

Also **kein** Randproblem (`pad_width` war nicht die Ursache; die Erhöhung auf 3
bleibt trotzdem als Absicherung drin). Es sind drei Stellen bei 34,6 Mio. Kanten,
an denen zwei Oberflächenblätter durch dieselbe Gitterkante laufen und von
`mesh.merge_vertices()` verschweißt werden — plus zwei daraus entstehende
Doppelflächen. Bei 1520 Oberflächenkomponenten und 23 Mio. Flächen ist das ein
punktueller Defekt, kein systematischer.

**Lösung:** `03_mesh_3D_array_pygalmesh.py` repariert das jetzt selbst
(`repair_nonmanifold_surface()`): doppelte Flächen entfernen, danach iterativ die
Flächen im Sternbereich der betroffenen Knoten entfernen und die Löcher schließen.
Die Reparatur wird verworfen, wenn sie das Ergebnis verschlechtert oder mehr als
`repair_nonmanifold_max_faces` Flächen beträfe. Getestet an synthetischen Fällen
(kantenberührende Würfel, Doppelflächen) und als No-Op an einer sauberen Kugel.

### Ressourcen der Jobs angepasst

- **Netzvorbereitung: `-n 96` -> `-n 32`, `--mem-per-cpu=15000` -> `45000`.**
  Der Runner startet jeden Schritt mit `run_container 1`, also `srun -n 1`;
  es rechnet nur ein Task. Die 96 Tasks dienten faktisch nur der
  Speicherzuteilung. 32 x 45 GB = 1,44 TB ist derselbe Gesamtspeicher wie
  vorher, belegt aber 64 Kerne weniger.
- **Punkt-Jobs: `-n 32` -> `-n 96`, `-N 1` entfaellt.** Der elasto-plastische
  Solve ist der teure Teil; `job_yield_surface_point_CLUSTER.sh` uebernimmt die
  Taskzahl aus `SLURM_NTASKS`. Ohne `-N` darf SLURM die Tasks ueber mehrere
  Knoten verteilen.
- Beides ist jetzt konfigurierbar: `YIELD_JOB_NTASKS`, `YIELD_JOB_NODES`,
  `YIELD_JOB_MEM_PER_CPU`, `YIELD_JOB_CONSTRAINT`, `YIELD_JOB_TIME` in
  `config.sh`, durchgereicht von `setup_yield_surface_jobs.sh` an den Generator.
  Der SBATCH-Header der Netzvorbereitung steht weiterhin fest in
  `job_prepare_mesh_CLUSTER.sh` und `run_prepare_mesh_CLUSTER.sh`.
- Neu ausserdem: `LES_MESH_SIZE_SCALE` bzw. `LES_CURRENT_TETS`/`LES_TARGET_TETS`
  in `config.sh` — skaliert `max_element_size_factor` und
  `max_facet_distance_factor` gemeinsam, Elementzahl ~ 1/scale^3.

### Netzfeinheit als Default festgelegt

- **`LES_MAX_ELEMENT_SIZE_UM=75`** ist jetzt der Default in `config.sh`. Die
  Elementgroesse wird absolut vorgegeben; der Generator rechnet daraus
  `max_element_size_factor` (2,2455 bei reduce=2) und skaliert
  `max_facet_distance_factor` im selben Verhaeltnis. Vorteil: die Elementgroesse
  bleibt konstant, wenn `LES_REDUCE_FACTOR` geaendert wird.
- Gegenueber dem ersten Lauf (49,6 um) ist das Faktor 1,51 groeber, also rund
  1/3,5 der Elementzahl -> erwartet 4-6 Mio. Tetraeder. Gegenueber der alten
  Bin4-reduce-2-Studie (199 um) ist es weiterhin etwa dreimal feiner.
- **`LES_BOUNDARY_SHELL_XZ=8`** statt 3 Voxel: bei 75 um Elementen waeren
  3 Voxel = 100 um nur 1,3 Elemente dick. 8 Voxel = 267 um ~ 3,5 Elemente und
  liegen naeher an den 400 um der alten Studie. `y` bleibt bei 12 Voxeln.
- Alle `LES_*`/`YIELD_JOB_*`-Variablen in `config.sh` sind jetzt als
  `VAR="${VAR:-wert}"` geschrieben und damit fuer einen einzelnen Aufruf ueber
  die Umgebung ueberschreibbar (vorher hat `source config.sh` sie ueberschrieben).

### Drei Fliesskriterien statt einem, sig_y = 100 MPa

- `yield_surface.material_sets.std.sig_y` 140 -> **100 MPa** (`YIELD_SIG_Y` in config.sh).
- `00_template/elastoplastic.py` zeichnet je Zeitschritt zusaetzlich auf:
  `eps_p_eq_macroscopic` (= sqrt(2/3 E_p:E_p) mit E_p = Volumenmittel des
  deviatorischen plastischen Dehnungstensors ueber das reduzierte RVE-Volumen),
  `eps_p_eq_avg_reduced_material_volume`, `eps_p_eq_avg_reduced_volume` und
  `e_p_avg_reduced_volume`. `alpha_avg_*` gab es bereits.
- **Drei blockierende Kriterien** (Schwelle je 0,002 = Rp0,2):
  `eps_p_eq_macroscopic`, `eps_p_eq_avg_material`, `alpha_avg_material`.
  Der Lauf endet erst, wenn alle drei erreicht sind; jedes haelt seinen
  Zustand beim **erstmaligen** Ueberschreiten in `yield_states.<name>`.
  Damit gibt es drei auswertbare Fliessflaechen aus einem Lauf.
- Das alte Kriterium (2 % des Materialvolumens mit alpha > 1e-5) laeuft als
  viertes, nicht abbrechendes Mass mit -> Vergleichbarkeit zur 192er-Studie.
- `final_yield_state` wird aus `primary_criterion` (Default
  `eps_p_eq_macroscopic`) gefuellt, damit collect_/create_yield_surface_*
  unveraendert funktionieren.
- **Wichtig:** Die Kriterienpruefung laeuft auf allen MPI-Raengen mit denselben
  kollektiv assemblierten Werten (der Zustand wird auf allen Raengen gebaut, nur
  die Historie wird auf Rang 0 gesammelt) — sonst wuerde StopSimulation
  asymmetrisch geworfen und der Lauf haengen.
- Verifiziert: die Kriterienlogik wurde als eigenstaendiges Skript mit
  synthetischen, unterschiedlich schnell wachsenden Massen durchgespielt
  (Erstschreiten je Kriterium korrekt, Abbruch erst bei allen drei,
  final_yield_state vom primaeren Kriterium). Der DolfinX-Teil ist lokal nicht
  lauffaehig und **nicht** ausgefuehrt worden.

### Korrektur der Kriterienauswahl

Auf Wunsch: das Kriterium `eps_p_eq_avg_material` (Mittel des Betrags der
lokalen plastischen Dehnung ueber die Materialphase) entfaellt. Die drei
abbrechenden Kriterien sind jetzt:

1. `eps_p_eq_macroscopic`      >= 0,002   (Rp0,2-Analogon, makroskopisch)
2. `alpha_avg_material`        >= 0,002
3. `yielded_fraction_material` >= 0,02    (Kriterium der bisherigen Studie)

Der Lauf endet, wenn alle drei erreicht sind; jedes liefert weiterhin seinen
eigenen Zustand in `yield_states`. Die Groesse
`eps_p_eq_avg_reduced_material_volume` wird weiterhin je Zeitschritt
aufgezeichnet, dient aber nur der Auswertung.

### Schwelle des dritten Kriteriums

`YIELD_YIELDED_VOLUME_FRACTION` steht jetzt auf **0,002** (0,2 % des
Materialvolumens fliesst), Bezug bleibt die Materialphase. Damit haben alle drei
Kriterien dieselbe Zahl 0,002, messen aber verschiedene Dinge: zwei Dehnungsmasse
und einen Volumenanteil. Das dritte Kriterium spricht damit frueher an als in der
bisherigen Studie (dort 0,02) und markiert eher den Fliessbeginn; ein
Vergleichslauf zur alten Fliessflaeche braucht
YIELD_YIELDED_VOLUME_FRACTION=0.02.

### Log-Dateien der Punkt-Jobs

`setup_yield_surface_jobs.py` schreibt jetzt `#SBATCH -e/-o` direkt in jeden
erzeugten Punkt-Job, mit dem jeweiligen `ys_*`-Ordner auf dem Scratch als Ziel.
Damit landen `.err`/`.out` auch bei einem blanken `sbatch job_ys_...sh` beim Job
und nicht im Aufrufverzeichnis. SBATCH-Zeilen werden nicht von der Shell
expandiert, der Pfad wird deshalb beim Erzeugen aus `$HPC_SCRATCH` aufgeloest
(ueberschreibbar mit --scratch-root bzw. YIELD_JOB_SCRATCH_ROOT). Fehlt
HPC_SCRATCH, warnt das Skript und laesst die Zeilen weg.

### Ressourcen der Punkt-Jobs (Clusterdaten)

Gemessen am Cluster: i01-Knoten (mpsc) haben 96 Kerne und RealMemory = 364800 MB,
i02 (mpsd) 104 Kerne und 490000 MB. Account p0023647: MaxJobs 400, MaxSubmit 1000
- 192 gleichzeitige Punkt-Jobs sind also zulaessig. Partition "deflt" begrenzt auf
24 h, "long" auf 7 Tage bei denselben i01-Knoten.

Default je Punkt-Job jetzt: **-n 64, -N 1, --mem-per-cpu=5600** = 358400 MB auf
einem Knoten, 6400 MB Reserve zum Knotenlimit. Neu konfigurierbar ausserdem
YIELD_JOB_PARTITION (leer = deflt) und YIELD_JOB_TIME (akzeptiert auch
"3-00:00:00"). Die Netzvorbereitung bleibt auf der mem-Partition (32 x 45000 MB).

### Fehler "More processors requested than permitted"

Ursache: `job_yield_surface_point_CLUSTER.sh` setzte in jedem srun-Aufruf fest
`--time=1440 --mem-per-cpu=9000`. Bei einem Job mit 64 x 5600 MB verlangte der
Step damit 64 x 9000 MB; SLURM rechnet das in CPUs um (103) und lehnt den Step ab.
Behoben: `SRUN_TIME` und `SRUN_MEM_PER_CPU` sind leer voreingestellt und werden
nur angehaengt, wenn gesetzt (`SRUN_LIMITS`-Array, an beiden srun-Stellen).
Der Step erbt damit Zeit und Speicher des Jobs. Verhindert zugleich, dass Steps
auf der long-Partition nach 24 h abgeschnitten werden.

---

## Session 30.08.2026 — Restart-Mechanismus aus 014 uebernommen

Der in 014 gebaute Restart nach SLURM-Timeout (fortsetzen statt neu rechnen,
Zustand exakt aus der eigenen XDMF/HDF5-Ausgabe rekonstruiert, e_p =
dev(eps(u)) - dev(sigma)/(2 mu) bei quadrature_degree = 1) gilt jetzt auch
fuer die Batch-Studie. Konzept und Einschraenkungen: RESTART_NACH_TIMEOUT.md
in 014; 015-Besonderheiten: RESTART_NACH_TIMEOUT.md hier.

- `00_template/elastoplastic.py` und `00_template/yield_restart.py` sind
  byteidentisch mit 014 (gepruefte Kopie).
- `job_yield_surface_point_CLUSTER.sh`: identischer Restart-Block wie in 014
  (kein `rm -rf` des Zielordners bei vorhandenem Rechenstand, Quick-Skip bei
  vorhandener yield_run-JSON, `YS_FORCE_FRESH=1` = altes Verhalten); die
  015-Eigenheiten (run_root mit binning_label, Slim-Copy nach 00_results)
  bleiben unveraendert.
- `resubmit_yield_surface_timeouts_CLUSTER.sh` (neu, 015-Fassung): durchsucht
  `yield_surface_jobs/<combo>/<nNNN>/ys_*`, liest den SLURM-Jobnamen aus der
  `#SBATCH -J`-Zeile (in 015 `<dataset>_s<sig_y>-ysNNN`, nicht sample_id) fuer
  den squeue-Abgleich, prueft Fertigsein gegen
  `00_results/<run_id>/<binning_label>/yield_surface/...` (Slim- und
  Vollkopie) und reicht je Timeout-Punkt eine `afternotok`-Kette ein
  (MAX_CHAIN, Default 5). Logs gehen wie beim batch_submit per
  --error/--output in den Sample-Ordner.
- Erst-Einreichung weiterhin `batch_submit_CLUSTER.sh`; Wiederanlaeufe nur
  ueber das Resubmit-Skript (batch_submit wuerde alle 768 Punkte einreichen).
- batch_status_CLUSTER.sh unveraendert nutzbar.

---

## Session 30.08.2026 (2) — Feldausgabe ausgeduennt + Wandzeit-Deadline

**Problem.** Die `.h5` der Punktlaeufe wird zu gross: `elastoplastic.py` schrieb
in **jedem** erfolgreichen Zeitschritt vier Felder (u, sigma, sig_vm, alpha).
Gleichzeitig darf nicht einfach seltener geschrieben werden, denn seit dem
Restart-Umbau ist die Feldausgabe **zugleich der Checkpoint** — und der letzte
Zeitschritt vor dem SLURM-Zeitlimit (seit 30.08.2026 10080 Minuten) soll auf
jeden Fall in der Datei stehen.

**Entscheidung.** Zwei Mechanismen in `00_template/elastoplastic.py`:

1. **Ausduennung nach Wandzeit.** Ein Snapshot hoechstens alle
   `yield_surface.field_output.min_minutes_between_writes` Minuten — **Default
   720 = 12 h** (Nutzervorgabe; anfangs 240 = 4 h, am selben Tag auf 12 h
   erhoeht). Zusaetzlich immer: erster Zeitschritt, jedes erstmalige Erreichen
   eines Fliesskriteriums, letzter Zeitschritt vor Abbruch.
   Damit haengt die Dateigroesse an der Laufzeit, nicht an der (wegen adaptiver
   Schrittweite unbekannten) Zahl der Zeitschritte: ein Punkt-Job ueber die
   vollen 7 Tage kommt auf 14 + wenige Snapshots statt einiger tausend. Alternativ konfigurierbar:
   `every_n_steps` und `strain_scale_interval` (beide 0 = aus, ODER-verknuepft).
2. **Deadline-Wache.** Das Skript kennt die Endzeit des Jobs und beendet sich
   rechtzeitig **selbst**, statt sich abschiessen zu lassen. Vor dem Beenden
   schreibt es den zuletzt gerechneten Zeitschritt als Snapshot plus
   `restart_meta`. Abbruchbedingung, ausgewertet vor jedem neuen Zeitschritt und
   nach jedem erfolgreichen:

   ```text
   Restzeit <= safety_margin_minutes + reserve_factor * (Dauer Zeitschritt + Dauer Schreiben)
   ```

   Dauer eines Zeitschritts = Maximum der letzten fuenf, Schreibdauer = bisheriges
   Maximum (vor dem ersten Snapshot ersatzweise die Schrittdauer). Default:
   `safety_margin_minutes = 15`, `reserve_factor = 2`.

**Warum das mehr ist als "letzter Snapshot".** Bei einem harten Kill gingen
bisher auch `yield_run_*.json` und `yield_averages_*.json` verloren; jetzt sind
Zustand *und* komplette Mittelwert-Historie in `restart_meta_*.json`, und die
Fortsetzung verliert hoechstens die Schritte seit dem letzten Snapshot.

### Details, die zusammenpassen muessen

- **`restart_meta` nur zusammen mit einem Snapshot.** Vorher wurde die
  Meta-Datei je Zeitschritt geschrieben. Mit ausgeduennter Feldausgabe zeigte
  sie damit auf einen Zeitschritt, den es in der XDMF gar nicht mehr gibt.
  Jetzt schreibt `write_fields_and_meta()` beides gemeinsam — erst die Felder,
  dann die Meta (bei einem Kill dazwischen bleibt die aeltere, konsistente
  Meta stehen). `--restart-meta-every` ist damit wirkungslos, das Argument
  bleibt nur der Kompatibilitaet halber bestehen.
- **u, sigma und alpha sind Pflichtfelder.** Aus ihnen rekonstruiert
  `yield_restart.py` den Zustand; wer sie in `field_output.fields` weglaesst,
  bekommt sie mit Hinweis wieder eingesetzt. Frei abwaehlbar ist nur `sig_vm`.
- **Kriterienpruefung jetzt VOR dem Schreiben.** Sonst landet der Zeitschritt,
  in dem ein Kriterium erstmals erreicht wird, nicht in der Felddatei.
- **Kein `yield_run_*.json` beim Wandzeit-Stop.** Diese Datei ist die
  Fertig-Markierung fuer den Idempotenz-Guard im Skript und fuer
  `resubmit_yield_surface_timeouts_CLUSTER.sh`. Ein unterbrochener Lauf darf sie
  nicht schreiben, sonst gilt der Punkt als fertig. `after_last_timestep()`
  wird beim Wandzeit-Stop daher uebersprungen.
- **Exit-Code 3 beim Wandzeit-Stop.** Die Fortsetzungskette haengt an
  `sbatch --dependency=afternotok`; ein sauberer Exit 0 wuerde die restlichen
  Kettenglieder abraeumen und den Punkt unfertig zuruecklassen. Der Job endet
  deshalb mit != 0. `job_yield_surface_point_CLUSTER.sh` faengt Exit 3 ab und
  gibt eine erklaerende Zeile aus.
- **Marker fuer das Resubmit-Skript.** Rang 0 schreibt beim Wandzeit-Stop
  `YIELD_WALLTIME_STOP: ...` nach stderr, also in die `.err`-Datei des Jobs.
  `resubmit_yield_surface_timeouts_CLUSTER.sh` behandelt diesen Marker jetzt
  wie `DUE TO TIME LIMIT` (sonst waere der Lauf "anderer Fehler" und wuerde
  ohne `INCLUDE_FAILED=1` uebersprungen).
- **Kollektive Entscheidungen.** Ob geschrieben und ob abgebrochen wird,
  entscheidet Rang 0 und verteilt es per `comm.bcast`. Uhren laufen auf den
  Raengen minimal auseinander; ohne bcast koennte ein Rang schreiben und ein
  anderer nicht — beides sind kollektive Operationen, das haengt.
- **`--signal` bewusst NICHT in den SBATCH-Headern.** Ein von SLURM gesendetes
  SIGUSR1 landet beim `bash -lc`-Wrapper des Steps und wuerde ihn ohne Handler
  sofort beenden. Die Deadline kommt deshalb aus der Job-Endzeit, nicht aus
  einem Signal. Ein Handler fuer SIGUSR1/SIGUSR2 existiert trotzdem im Solver
  (manuelles `scancel --signal=USR1 <jobid>` beendet den Lauf sauber).

### Woher die Job-Endzeit kommt

`job_yield_surface_point_CLUSTER.sh` ermittelt sie vor dem Solver-Start und
exportiert sie als `YIELD_WALLTIME_DEADLINE_EPOCH` (zusaetzlich mit
`APPTAINERENV_`/`SINGULARITYENV_`-Praefix, damit sie sicher im Container
ankommt):

1. bereits gesetzte Variable, sonst
2. `SLURM_JOB_END_TIME`, sonst
3. `squeue -h -j $SLURM_JOB_ID -O EndTime` + `date -d`.

Im Solver zusaetzlich moeglich: `--walltime-deadline-epoch`,
`--walltime-limit-minutes`, `YIELD_WALLTIME_LIMIT_MINUTES` oder
`yield_surface.walltime.limit_minutes` (ab Jobstart gerechnet). Ist gar nichts
bekannt, laeuft der Job wie frueher bis zum Kill — der Solver sagt das beim
Start deutlich an. Abschalten der Wache: `--no-walltime-stop` bzw.
`walltime.stop_before_deadline = false`.

### Neue Config-Bloecke (in allen `config*.json` ergaenzt)

```json
"yield_surface": {
  "field_output": {
    "enabled": true,
    "min_minutes_between_writes": 720.0,
    "every_n_steps": 0,
    "strain_scale_interval": 0.0,
    "write_first_step": true,
    "write_on_yield_event": true,
    "fields": ["u", "sigma", "sig_vm", "alpha"]
  },
  "walltime": {
    "stop_before_deadline": true,
    "safety_margin_minutes": 15.0,
    "reserve_factor": 2.0,
    "exit_code": 3
  }
}
```

`write_yield_surface_parameters.py` schreibt beide Bloecke mit in
`parameters.txt`, `yield_run_*.json` protokolliert am Ende zusaetzlich
`time_steps_computed`, `field_output.snapshots_written` und den
`walltime`-Block.

### Stand / offen

- Geaenderte Dateien: `00_template/elastoplastic.py`,
  `job_yield_surface_point_CLUSTER.sh`,
  `resubmit_yield_surface_timeouts_CLUSTER.sh`,
  `write_yield_surface_parameters.py`, alle `config*.json`.
- Die Entscheidungs- und Zeitlogik ist ausserhalb des Containers mit Stubs
  getestet (Intervall, erzwungenes Schreiben, Deadline, Signal). **Ein echter
  Lauf im Container steht aus** — beim ersten Punkt-Job den Kopf der `.out`
  pruefen: Block `=== Feldausgabe / Wandzeit ===` muss eine Deadline mit
  plausibler Restzeit zeigen, danach `[FIELDOUT] Snapshot ...`-Zeilen.
- Faustwert zum Nachjustieren: dauert ein Zeitschritt sehr lange (grosse Netze),
  waechst die Reserve automatisch mit; `safety_margin_minutes` deckt nur den
  Fixanteil (Start, Kopieren, Auslastungsschwankungen) ab.

### Nachtrag (Nutzervorgabe, 30.08.2026): 7-Tage-Limit und 12-h-Snapshots

- **Zeitlimit je Punkt-Job auf `-t 10080`** (7 d) erhoeht, also das Maximum der
  `long`-Partition. Gesetzt in `config.sh` (`YIELD_JOB_TIME`), als Default in
  `setup_yield_surface_jobs.py --job-time` und im Fallback von
  `setup_yield_surface_jobs.sh`. Partition bleibt `long` (Pflicht, `deflt`
  erlaubt nur 1440). Die Netzvorbereitung bleibt bei `PREP_JOB_TIME=1440`
  auf `mem`.
- **Snapshot-Abstand auf 720 Minuten (12 h)** erhoeht — in allen `config*.json`
  und als Default in `elastoplastic.py`. Ein Punkt-Job ueber die vollen 7 Tage
  schreibt damit hoechstens 14 Snapshots plus erster Schritt, Fliess-Ereignisse
  und Abschluss-Snapshot.
- **Wichtig beim Uebernehmen:** bereits erzeugte Punkt-Jobskripte unter
  `yield_surface_jobs/<combo>/nNNN/ys_*/job_*.sh` tragen das alte `-t` im
  SBATCH-Header und die alten Configs. Vor dem Einreichen deshalb
  `batch_create_configs.sh` und `batch_setup_jobs.sh` neu laufen lassen und
  mit `batch_create_folders_CLUSTER.sh` auf den Scratch synchronisieren
  (Kontrolle: `grep '^#SBATCH -t' yield_surface_jobs/*/*/ys_000*/job_*.sh`).
- Der Kompromiss ist bewusst: 12 h Snapshot-Abstand heisst, dass ein Absturz
  ohne Deadline-Wache (also nur bei unbekannter Job-Endzeit oder hartem
  Knotenausfall) bis zu 12 h Rechenzeit kostet. Mit funktionierender
  Deadline-Wache ist der Verlust bei einem Zeitlimit-Ende praktisch null.

---

## Session 30.08.2026 (3) — Runbook fuer den kompletten Neustart

Entscheidung: 015 wird mit dem Stand vom 30.08.2026 (ausgeduennte Feldausgabe,
Wandzeit-Deadline, `-t 10080` auf `long`) **komplett neu** gerechnet, nicht als
Fortsetzung der mit dem alten Stand begonnenen Laeufe.

Gelernt/festgehalten (Ablauf im Detail: `NEUSTART_KOMPLETT.md`):

- Der Punkt-Job ist seit dem Restart-Umbau idempotent: vorhandener Rechenstand
  wird fortgesetzt, vorhandenes `yield_run_*.json` uebersprungen. Ein Neustart
  braucht deshalb zwei Dinge: auf dem Scratch `yield_surface_runs/` und
  `00_results/` loeschen **und** die Erst-Einreichung mit `YS_FORCE_FRESH=1`
  fahren (wird per `sbatch --export=ALL` in jeden Job vererbt).
- `YS_FORCE_FRESH` darf nur an `batch_submit_CLUSTER.sh`, nie an
  `resubmit_yield_surface_timeouts_CLUSTER.sh` — sonst startet jede Fortsetzung
  wieder bei null.
- `batch_create_folders_CLUSTER.sh` synchronisiert mit `rsync -av --update` und
  **ohne** `--delete`: es raeumt auf dem Scratch nichts weg und ueberschreibt
  nichts, was dort neuer ist. Nach `git pull` haben die Dateien in HOME die
  Checkout-Zeit als mtime und gehen durch; alte generierte Ordner
  (`yield_surface_jobs/`) muessen von Hand weg.
- Erst `scancel -u $USER`, dann aufraeumen — sonst schreiben Kettenglieder aus
  `afterok`/`afternotok` in die frisch geleerten Ordner.
- Die vier vorbereiteten Netze bleiben liegen: sie haengen weder von sig_y noch
  von Feldausgabe oder Zeitlimit ab. `AUTO_SKIP_PREPARE=1` (Default) ueberspringt
  die Prepare-Jobs dann automatisch.
- Beim ersten laufenden Punkt-Job den Block `=== Feldausgabe / Wandzeit ===` in
  der `.out` pruefen: `walltime_deadline` muss einen Zeitpunkt zeigen, nicht
  `unbekannt`. Das ist der erste echte Containerlauf der Deadline-Wache.

### Nachtrag 30.08.2026: Netzvorbereitung scheitert je nach Absende-Verzeichnis

Symptom beim Neustart: `run_prepare_mesh_CLUSTER.sh` laeuft an ("Preparing mesh
for dataset: ...", Config und .leS werden gefunden) und bricht sofort ab mit

```text
WARNING: Error changing the container working directory. Using '/home/as12vapa'
  instead: chdir /home/as12vapa/meshing/Meshing/pygalmesh: no such file or directory
/usr/bin/python3: can't open file '/work/scratch/.../015-.../A01_les_2_npy.py':
  [Errno 2] No such file or directory
```

Die Datei liegt sehr wohl auf dem Scratch. Ursache: die Pipeline-Schritte
uebergeben dem Container **Host-Pfade** unter `/work/scratch` (Skripte,
`volume.npy`, `mesh.xdmf`), gebunden sind aber nur
`$HOME/meshing/Meshing/pygalmesh/data:/home` und
`$HPC_SCRATCH/pygalmesh/data:/data`. Sichtbar wird der Host-Pfad nur, weil
Apptainer das **aktuelle Arbeitsverzeichnis** mit einhaengt. Die Punkt-Jobs
rufen `run_container` mit `chdir="$target"` auf (Laufordner unter
`/work/scratch`) und funktionieren deshalb; die Netzvorbereitung ruft es mit
leerem chdir auf und erbt damit das Verzeichnis, aus dem `sbatch` abgeschickt
wurde. Aus `$HOME/meshing/Meshing/pygalmesh` (so steht es in README Schritt 1)
ist das ausserhalb von `/work/scratch` -> Abbruch. Frueher fiel das nicht auf,
weil aus dem Projektordner auf dem Scratch heraus eingereicht wurde.

Behoben: `cd "$working_directory"` direkt nach der Zuweisung in
`run_prepare_mesh_CLUSTER.sh` (mit Begruendung im Kommentar). Zusaetzliche
Faustregel: `batch_submit_CLUSTER.sh` aus `$HPC_SCRATCH/.../015-.../` heraus
aufrufen, nicht aus HOME.

### Nachtrag 30.08.2026 (2): Netzvorbereitung nur fuer JM-25-77 erfolgreich

Zweiter Anlauf (Prep-Jobs 54430515-518, aus `$S` heraus eingereicht): der
Container-Pfad-Fehler ist weg, A01/02b/02c/02d laufen durch. Ergebnis:

| Datensatz | Job | Zustand |
|---|---|---|
| JM-25-77 | 54430515 | COMPLETED nach 54:42 -> 192 Punkt-Jobs laufen |
| JM-25-71 | 54430516 | FAILED nach 18:21 in Schritt 03 |
| JM-25-83 | 54430517 | FAILED nach 22:07 in Schritt 03 |
| JM-25-88 | 54430518 | FAILED nach 16:36 in Schritt 03 |

Kein Speicherproblem (MaxRSS 24-34 GB bei 480 GB Anforderung), sondern:

```text
RuntimeError: SDF surface is not watertight/manifold enough for volume meshing;
see .../subvolume_x0_y0/mesh_sdf_surface.topology.txt
```

Also `surface_verdict(...) == "bad"` bei `require_watertight_surface = true`.
JM-25-77 ist der aus 014 bekannte, durchgetestete Datensatz; die drei neuen
`.leS` sind an dieser Stelle zum ersten Mal vernetzt worden. Die Konfiguration
ist fuer alle vier identisch (`sdf_sigma_voxels = 1.0`, `pad_width = 3`,
`level = 0.0`, `keep_largest_component = true`, `fill_holes = true`,
`min_surface_component_faces = 0`), es ist also ein Datenthema, kein Codethema.

Wichtig: `--kill-on-invalid-dep=yes` hat die 576 zugehoerigen Punkt-Jobs sofort
verworfen; die 192 Punkt-Jobs von JM-25-77 laufen ungestoert weiter. Nachreichen
spaeter je Datensatz mit `ONLY_DATASETS=...`.

Diagnose ueber `mesh_sdf_surface.topology.txt` (Tabelle in `LES_PIPELINE.md`,
Abschnitt "Wenn Schritt 03 mit ... abbricht"): `surface_open_edges > 0` ->
`pad_width` erhoehen; `surface_nonmanifold_edges > 0` -> Reparaturbudget
(`repair_nonmanifold_max_faces`) bzw. `level` minimal verschieben;
`surface_watertight = false` bei 0 offenen Kanten -> `min_surface_component_faces`.

### Nachtrag 30.08.2026 (3): warum die drei neuen Datensaetze nicht vernetzbar waren

Die Topologie-Reports zeigen einen sehr kleinen, lokalen Defekt:

| | JM-25-77 | JM-25-71 | JM-25-83 | JM-25-88 |
|---|---|---|---|---|
| offene Kanten | 0 | 0 | 0 | 0 |
| nicht-mannigfaltige Kanten | 0 | 2 | 4 | 4 |
| watertight | ja | nein | nein | nein |
| Flaechen | 22,3 Mio | 31,3 Mio | 38,1 Mio | 27,9 Mio |

Zwei bis vier kaputte Kanten unter 47 Millionen. `repair_nonmanifold_surface()`
loest sie auch (`nicht-mannigfaltig 4 -> 0`), reisst dabei aber Loecher auf, die
`trimesh.repair.fill_holes` **nicht** schliesst (`offen 0 -> 14 / 30 / 25`) —
fill_holes kann nur Drei- und Vierecksloecher, der entfernte Sternbereich
hinterlaesst aber Schleifen mit 6 bis 14 Randkanten. Die Schutzregel
(`sum(after) > sum(before)`) verwirft die Reparatur daraufhin komplett, und der
Report zeigt wieder die urspruenglichen 2-4 Kanten -> `verdict = bad` ->
`require_watertight_surface` bricht ab.

**Entscheidung:** nicht am `level` drehen (das haette die Geometrie aller vier
Datensaetze veraendert und JM-25-77 vom laufenden Stand abgekoppelt), sondern
die fehlende Lochfuellung nachruesten: neue Funktion `close_boundary_loops()`
in `03_mesh_3D_array_pygalmesh.py`, aufgerufen in der Reparaturschleife direkt
nach `fill_holes`. Sie schliesst einfache Randschleifen (jeder Randknoten genau
zwei Randnachbarn) bis `max_boundary_loop_edges` (Default 64) mit einem Faecher
um den Schleifenschwerpunkt; verzweigte oder sehr grosse Schleifen bleiben
unangetastet, damit ein echtes Loch am Domaenenrand nicht zugedeckelt wird.

Geprueft (trimesh 5.0, synthetisch): Loch aus dem Sternbereich eines
Kugelknotens, 5 Randkanten — `fill_holes` allein bleibt bei `offen 5`,
mit `close_boundary_loops` `offen 0, nicht-mannigfaltig 0, watertight True`,
Volumenabweichung zur ungestoerten Kugel 0,0035 %. Auf einer intakten
Oberflaeche ist die Funktion ein No-op (Flaechenzahl unveraendert) — **JM-25-77
bekommt also exakt dasselbe Netz wie bisher**, die 192 laufenden Punkt-Jobs
bleiben gueltig.

Der Beweis am echten Datensatz steht noch aus: im neuen Prep-Log muss
`🩹 Oberflaechenreparatur: ... (nicht-mannigfaltig 4 -> 0, offen 0 -> 0,
N Randschleifen ... geschlossen)` **ohne** "VERWORFEN" stehen und danach
`SDF surface topology verdict: good`.

Falls das nicht reicht, ist der naechste Griff `level = -0.05` in
`sdf_pygalmesh_parameters` (verschiebt die Isoflaeche um 0,05 Voxel und loest
den Pinch) — dann aber fuer alle vier Datensaetze, inklusive Neustart von
JM-25-77.

**Bestaetigt am echten Datensatz (30.08.2026, Prep-Jobs 54431644-46):**

```text
JM-25-71: nicht-mannigfaltig 2 -> 0, offen 0 -> 0, 1 Randschleife  mit 14 Flaechen geschlossen -> verdict good
JM-25-88: nicht-mannigfaltig 4 -> 0, offen 0 -> 0, 2 Randschleifen mit 25 Flaechen geschlossen -> verdict good
          "Prepared mesh and DolfinX files for JM-25-88_les_r2."
```

Kein "VERWORFEN" mehr; die geschlossenen Loecher sind mit 14 bzw. 25 Flaechen
unter 31 Mio. voellig lokal. Der `level`-Eingriff bleibt damit ungenutzt, alle
vier Datensaetze behalten `level = 0.0`. Laufzeit der Netzvorbereitung skaliert
erwartungsgemaess mit der Flaechenzahl (JM-25-77 22 Mio. -> 55 min;
JM-25-71 31 Mio. und JM-25-83 38 Mio. -> mehrere Stunden, Zeitlimit 1 d reicht).

## Session 31.08.2026 — Erster Stand der Punkt-Jobs, reale Ergebnisablage

### Queue-Stand (31.08., ~1 d nach Einreichung)

| Kombination | RUNNING | PENDING | COMPLETED | `yield_run_*.json` |
|---|---:|---:|---:|---:|
| JM-25-77_s075 | 79 | 0 | **17** | 17 |
| JM-25-77_s100 | 83 | 0 | **13** | 13 |
| JM-25-88_s075 | 84 | 12 | 0 | 0 |
| JM-25-88_s100 | 0 | 96 | 0 | 0 |
| JM-25-71 / JM-25-83 (beide sig_y) | 0 | je 96 | 0 | 0 |

Die 30 fertigen JM-25-77-Punkte liefen 1 h 10 min bis 5 h (`sacct`, ExitCode
0:0) — deutlich kuerzer als die restlichen, die nach >1 d noch laufen. Die
Laufzeit haengt also stark von der Belastungsrichtung ab.

**Merkregel fuer den Status:** `squeue` zeigt nur aktive Jobs. Fehlen fuer
eine Kombination Jobs (erwartet 96 minus RUNNING+PENDING), sind sie fertig oder
gescheitert — `sacct -u $USER --starttime=<Datum> -o JobID,JobName%30,State,ExitCode,Elapsed`
unterscheidet das. `squeue` kuerzt Jobnamen auf 8 Zeichen, daher immer
`-o "%.30j"` verwenden, sonst sind `_s075` und `_s100` nicht unterscheidbar.

### Reale Ablagestruktur (weicht von der Kurzform in FILES.md/README ab)

Die Doku schreibt `00_results/<dataset>/<binning_label>/yield_surface/...`.
Konkret sind die Platzhalter:

- `run_id` = **`<dataset>_les_r2`** (z. B. `JM-25-77_les_r2`), nicht `JM-25-77`
- `binning_label` = **`leS-r2-sigy075`** bzw. `leS-r2-sigy100`, nicht `sigy075`
- die Ergebnis-JSON liegt **drei Ebenen unter `yield_surface/`**:

```text
00_results/JM-25-77_les_r2/leS-r2-sigy075/yield_surface/
  <sample>-std-tensor/                      <sample> = ys_020_e1_m0p1313_e2_m0p1573_e3_p0p1432
    config.json
    parameters.txt
    <sample>/subvolume_x0_y0/yield_run_std_tensor.json   <-- der Fliessflaechenpunkt

yield_surface_runs/JM-25-77_les_r2/leS-r2-sigy075/<sample>/subvolume_x0_y0/
    yield_run_std_tensor.json (Original), dlfx_mesh.h5, config.json, Feldausgabe ...

yield_surface_jobs/JM-25-77_sigy075/n096/<sample>/
    job_<sample>_CLUSTER.sh, config.json, parameters.txt,
    JM-25-77_s075-ys020.out.<jobid>, JM-25-77_s075-ys020.err.<jobid>
```

Drei Namensraeume fuer dieselbe Kombination: Jobordner `JM-25-77_sigy075`,
SLURM-Jobname `JM-25-77_s075-ys020`, Ergebnisordner `JM-25-77_les_r2/leS-r2-sigy075`.

**Folge fuer Ad-hoc-Suchen:** `find ... -maxdepth 2` unter `yield_surface/`
findet nichts; ohne Tiefenlimit suchen oder ueber
`00_results/${dataset}_*/*sigy${sig}/yield_surface` globben. Der korrigierte
Status-Einzeiler steht in `RESTART_NACH_TIMEOUT_015.md` nicht, sondern nur im
Chat-Protokoll vom 31.08.; `batch_status_CLUSTER.sh` bleibt der offizielle Weg.

### Befund: alle 30 "fertigen" Punkte sind gescheitert (`dt_below_minimum`)

Inhaltliche Pruefung der 30 JSONs: **kein einziger Fliessflaechenpunkt**.
Bei allen 30 gilt `stop_reason = dt_below_minimum`, `criteria_reached = []`,
`criteria_missed = [alle drei]`, `yield_states = {}`, `final_yield_state = null`;
beim geprueften ys_020 `time_steps_computed = 4`. Die kurzen Laufzeiten
(1-5 h) sind also die *Ausfaelle*, die 162 noch laufenden JM-25-77-Jobs die
gesunden Laeufe. `batch_status` zaehlt diese JSONs unter ERGEBNIS, nicht unter
GUELTIG — GUELTIG ist die einzige belastbare Zahl.

Mechanik des Abbruchs (aus `alex/solution.py::solve_with_newton_adaptive_time_stepping`
und `00_template/elastoplastic.py`):

- Newton: `max_iters = 8`, dolfinx-`NewtonSolver` mit Default-Toleranzen
  (rtol 1e-9 relativ zum Startresiduum des Schritts, atol 1e-10), Tangente per
  `ufl.derivative` aus dem Radial-Return in `alex/plasticity.py::sig_plasticity`
  (Konsistente Tangente, `hard = 0`, Norm-Guard bei 1e3·eps).
- Zeitschritt: `time_step = 1e-4`, `dt_max = 10·dt = 1e-3`, Verdopplung wenn
  `iters < 4`, Halbierung bei RuntimeError des Newton, `dt_min = 1e-11`.
  Rekonstruierter Verlauf: dt 1e-4 -> 2e-4 -> 4e-4 -> 8e-4 (4 erfolgreiche
  Schritte, rein elastisch, 1-2 Iterationen) bis t = 1,5e-3; der 5. Schritt mit
  dt = 1e-3 scheitert und danach **jede** Halbierung bis 1e-11 (27 Versuche a
  <= 8 Newton-Iterationen auf dem grossen System = die 1-5 h).
- Das Scheitern ist damit **unabhaengig von der Schrittweite** — ein Faktor
  1e8 kleiner half nicht. Das schliesst "Inkrement zu gross" aus. Zeitpunkt:
  Makrodehnung ~4e-4 (Eigenwerte ~0,25 · strain_scale), d. h. genau der
  Beginn lokaler Plastizitaet in den duennsten Stegen.
- ys_039 scheitert bei beiden sig_y, die uebrigen 28 nur bei einem — kein
  rein geometrischer Richtungseffekt.

Hypothesen, die das Log entscheiden muss (`.out` des Jobs 54430539 = ys_020
unter `yield_surface_jobs/JM-25-77_sigy075/n096/ys_020_*/`):

1. **Residuum-Boden vs. relative Toleranz:** an der elastisch-plastischen
   Kante (`ufl.conditional`) wechseln einzelne Quadraturpunkte zwischen den
   Iterationen den Zustand -> Residuum stagniert auf einem zustandsabhaengigen
   Boden; das Startresiduum skaliert aber mit dt, also wird rtol = 1e-9 bei
   kleinerem dt *schwerer* erreichbar. Passt zu "keine Halbierung hilft".
   Log-Signatur: `Newton iteration k: r (rel)` stagniert bei ~1e-6..1e-8,
   8 Iterationen, dann Abbruch.
2. **Singulaere Tangente (Stegkollaps bei idealer Plastizitaet):** ein Steg
   ist ueber den Querschnitt plastisch, `hard = 0` -> Tangente in Belastungs-
   richtung null -> Direktloeser Zero-Pivot bzw. Newton divergiert (Residuum
   waechst, ggf. NaN). Waere physikalisch das Limit-Load des Stegs — und
   ebenfalls dt-unabhaengig.
3. **Linearer Loeser:** Default-KSP/PC des NewtonSolver (steht im Log als
   "Default KSP Type / PC Type"); bei iterativem Loeser Divergenz.

Pruefbefehle (Cluster): `grep -m2 "KSP Type\|PC Type" <out>`;
`grep -E "Computing solution at time|Current time step dt|NO CONVERGENCE|Newton iteration|STOP" <out> | head -80`;
`grep -i -m5 "nan|diverg|zero pivot|did not converge" <out> <err>`;
`yield_averages_std_tensor.json` der 30 Punkte (liegt in der Slim-Kopie):
Iterationszahlen der 4 Schritte, `sig_vm_avg`, `yielded_fraction` beim letzten
erfolgreichen Schritt.

Korrektur zu einer Vermutung von heute: `yielded_volume_fraction_target = 0.02`
in der JSON ist der **Legacy-Parameter** `yield_surface.yielded_volume_fraction`;
das aktive Kriterium `yielded_fraction_material` steht in
`yield_surface.criteria[2].threshold = 0.002`, wie in LES_PIPELINE.md dokumentiert.
Kein Handlungsbedarf.

**Operativ wichtig fuer eine Wiederholung dieser 30 Punkte:** die vorhandene
`yield_run_std_tensor.json` ist zugleich die Fertig-Markierung —
`job_yield_surface_point_CLUSTER.sh` ueberspringt den Solver, solange sie liegt,
und `resubmit_yield_surface_timeouts_CLUSTER.sh` wertet den Punkt als fertig.
Vor einem Neustart also JSON (in `00_results` **und** `yield_surface_runs`)
entfernen oder `YS_FORCE_FRESH=1` setzen; Parameteraenderungen (Newton-
Iterationen, Toleranzen, dt) greifen nur ueber neu erzeugte Punkt-Jobs
(`batch_setup_jobs.sh`), weil jeder `ys_*`-Ordner seine eigene Config traegt.

### Naechste Schritte

- Log von ys_020 (54430539) auswerten und die Hypothese festnageln; danach
  entscheiden: Newton robuster machen (`max_iters` 8 -> 25-50, absolute
  Toleranz, Line Search) vs. Loeserwechsel vs. Punkt als "kein Fliesspunkt
  im Modellhorizont" akzeptieren.
- Fortschritt der 162 laufenden JM-25-77-Jobs pruefen (Schrittzahl, dt,
  Anzahl `NO CONVERGENCE` im `.out`), damit klar ist, ob sie nur langsam sind
  oder dasselbe Problem vor sich herschieben.
- Nach dem Prep von JM-25-71/83 (30.08.) laufen deren 384 Punkt-Jobs an, sobald
  die `long`-Partition frei wird; Queue-Limit bisher kein Problem.

### Korrektur und Stand aller 192 JM-25-77-Laeufe (31.08., Auswertung der .out + restart_meta)

Scan aller `.out`-Dateien und `restart_meta_*.json` (Skript im Chat-Protokoll):

| Gruppe | s075 | s100 | Merkmal |
|---|---:|---:|---|
| gesund, `yielded_fraction_material` erreicht | 65 | 69 | 0-3 verworfene Schritte, strain_scale 5e-3 .. 1,3e-2 |
| "Kriecher", noch kein Kriterium | 14 | 14 | 5-16 verworfene Schritte, nach ~75 Schritten erst bei t = 1-2e-3 |
| `dt_below_minimum` | 17 | 13 | siehe unten |

**Korrektur zur Hypothese von oben:** die 30 Abbrueche liegen **nicht** am
Einsetzen der Plastizitaet, sondern im **ersten Schritt im rein elastischen
Bereich** (sig_vm_avg = 0,00, yf = 0, e_p = 0; die "erfolgreichen" 3-14
Schritte sind Artefakte bei dt ~ 1e-10 nach ~25 Halbierungen). Entscheidend:
im ersten Schritt ist das Problem fuer sig_y = 75 und 100 **identisch** (linear
elastisch), trotzdem scheitert ys_020/ys_022 nur bei s075 und laeuft bei s100
sauber (59/67 Schritte, 0 Verwerfungen), ys_001 umgekehrt. Dieselbe lineare
Gleichung konvergiert in einem Job und im anderen nie -> **nicht-deterministisch**:
linearer Loeser (MUMPS-Workspace, partitionsabhaengig), defekter Knoten oder
MPI/Speicher — nicht das Materialmodell. Die 28 Kriecher zeigen dasselbe
Muster in milder Form (Verwerfungen im elastischen Bereich halten dt klein).
Betroffen also 58 von 192, gesund 134.

Offen (Pruefbefehle im Chat-Protokoll vom 31.08.): (a) Fehlertext des ersten
verworfenen Schritts + "Default KSP/PC Type" im `.out`, (b) Knotenkorrelation
ueber `sacct -o NodeList`, (c) Speicher.

**Stand der Kriterien:** 134 Laeufe haben `yielded_fraction_material`
(0,2 % des Materialvolumens plastisch) bei strain_scale 1,8e-3 .. 4e-3
erreicht; **kein** Lauf hat `alpha_avg_material` oder das Primaerkriterium
`eps_p_eq_macroscopic`. Die am weitesten fortgeschrittenen Laeufe stehen bei
strain_scale ~1e-2 (Makrodehnung ~0,25 %) mit 15-26 % plastischem
Materialvolumen, aber eps_p_mac ~ 1-3e-5 (Schwelle 2e-3, Faktor ~65) und
<alpha> ~ 2-4e-4 (Faktor ~6). Physikalisch erwartbar (Volumenmittel ueber die
Box mit rho_rel ~ 0,15 und Richtungsausloeschung), aber: das Primaerkriterium
wird erst nahe der Traglast des RVE erreicht — bei `hard = 0` genau dort, wo
die Tangente singulaer wird. Restlaufzeit nicht abschaetzbar (beschleunigt).

**Was schon gesichert ist:** ein erreichtes Kriterium steht sofort in
`[YIELD]`-Zeile des `.out`, im `restart_meta_*.json` (erzwungener Snapshot,
enthaelt `yield_states` + komplette `averaged_history`) und am Ende in
`yield_run_*.json -> yield_states`; `batch_collect_results.py` schreibt daraus
je Kriterium eine Zeile in `yield_points_all.csv`, auch ohne
`final_yield_state`. Nur beim Walltime-Stop fehlt die Summary-JSON, dann gilt
`restart_meta`. Die 134 `yielded_fraction`-Zustaende sind damit bereits eine
Erstfliess-Flaeche (Kriterium der Vorgaengerstudie, Schwelle 0,002 statt 0,02)
und lassen sich jetzt aus den `restart_meta` nach
`00_results/_packages/partial_yield_states_from_restart_meta.csv` ziehen
(Skript im Chat-Protokoll).

### Ursache gefunden: MUMPS-Faktorisierung scheitert (KSPSolve error 76) — Patch eingebaut

Log des toten Punkts ys_020/s075 (Job 54430539): `Default KSP Type: preonly`,
`Default PC Type: lu` (dolfinx-NewtonSolver-Default = parallele LU ueber
MUMPS) und beim allerersten Schritt (dt = 1e-4, rein elastisch):

```text
Failed to successfully call PETSc function 'KSPSolve'. PETSc error code is: 76, Error in external library
!!! NO CONVERGENCE => dt:  5e-05
```

Error 76 = Fehler in der externen Bibliothek = die MUMPS-Faktorisierung selbst
(typisch INFOG(1) = -9: Workspace zu klein, oder -13/-17: Allokation). Die
dt-Halbierung des Reglers aendert die Matrix im elastischen Schritt nicht,
also scheitert jeder Wiederholungsversuch identisch (27-42 mal bis dt_min).

Knotenkorrelation (`sacct -o NodeList`, jeder Job auf genau einem Knoten):
tote und gesunde Jobs teilen sich Knoten (mpsc0617: 2 tot + 1 ok; mpsc0448,
0452, 0453, 0458, 0470, 0472, 0504, 0505, 0546, 0551, 0571, 0577, 0585, 0597,
0600, 0601, 0604, 0623: je 1 tot + 1 ok) -> **keine Hardware**. Es ist eine
Eigenschaft des einzelnen Jobs (Partitionierung/Ordering beim Start ->
MUMPS-Speicherschaetzung -> der Default-Zuschlag ICNTL(14) = 20 % reicht bei
~16 % der Jobs nicht), deshalb deterministisch innerhalb eines Jobs und
"zufaellig" zwischen Jobs mit identischer Matrix. Die 28 Kriecher sind
derselbe Effekt intermittierend in spaeteren Schritten (Pivotierung aendert
sich mit dem plastischen Zustand).

**Patch (31.08.2026, auf dem Mac eingebaut, Backups in `_to_delete/*.vor_mumps_patch_20260831`):**

1. `00_template/elastoplastic.py`, direkt nach `comm/rank`: globale
   PETSc-Optionen mit dem NewtonSolver-Prefix `nls_solve_`:
   `pc_factor_mat_solver_type = mumps`, `mat_mumps_icntl_14 = 200`
   (Workspace-Zuschlag in %, statt 20), `mat_mumps_icntl_4 = 1` (MUMPS druckt
   INFOG(1)/INFO(2) auf stdout). Ueberschreibbar/erweiterbar ueber
   `yield_surface.petsc_options` in der Config (Schluessel ohne Prefix,
   z. B. `{"mat_mumps_icntl_14": 300}` oder `{"ksp_view": true}` zur
   Kontrolle). Das Skript druckt die gesetzten Optionen als
   `PETSc options (prefix nls_solve_): {...}` ins `.out`.
2. `dolfinx_alex/shared/utils/alex/solution.py::get_solver`: eine Zeile
   `solver.krylov_solver.setFromOptions()` nach `solver.max_it`, damit die
   Optionen sicher greifen, falls der dolfinx-Build sie nicht schon im
   Konstruktor liest (sonst No-op).

Wirkung: jeder Punkt-Job kopiert `00_template/*` beim Start (auch beim
Fortsetzen) -> alle 576 wartenden Jobs und alle Resubmits nutzen den Patch,
sobald er auf `$HPC_SCRATCH` liegt; laufende Jobs bleiben unveraendert.
Speicher: ICNTL(14) = 200 erlaubt MUMPS bis zum 3-fachen der Schaetzung;
bei `--mem-per-cpu=9000` und einem Knoten je Job vertretbar, und ein
Speicherfehler steht jetzt als INFOG im Log statt stumm zu scheitern.

**Neustart-Rezept (Cluster, nach Sync von Template und alex/solution.py):**

```bash
H="$HOME/meshing/Meshing/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS"
S="$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS"
rsync -av "$H/00_template/" "$S/00_template/"               # nur das Template, keine Job-Neuerzeugung
grep -c mat_mumps_icntl_14 "$S/00_template/elastoplastic.py" # 1
grep -c "krylov_solver.setFromOptions" "$HOME/dolfinx_alex/shared/utils/alex/solution.py"   # 1

# tote Punkte: Slim-Kopie beiseite (sonst gelten sie fuer resubmit als fertig)
cd "$S"; mkdir -p 00_results/_failed_mumps_20260831
for o in $(grep -l "dt too small" yield_surface_jobs/JM-25-77_*/n096/ys_*/*.out.*); do
  d=$(dirname "$o"); sample=$(basename "$d"); combo=$(basename "$(dirname "$(dirname "$d")")"); sig=${combo##*sigy}
  r="00_results/JM-25-77_les_r2/leS-r2-sigy${sig}/yield_surface/${sample}-std-tensor"
  [ -d "$r" ] && mkdir -p "00_results/_failed_mumps_20260831/$combo" && mv -v "$r" "00_results/_failed_mumps_20260831/$combo/"
done

# frisch einreichen: MAX_CHAIN=1, weil YS_FORCE_FRESH=1 sonst auch jedes
# Kettenglied den Stand verwerfen wuerde; Fortsetzungsketten spaeter OHNE die Variable
DRY_RUN=1 INCLUDE_FAILED=1 YS_FORCE_FRESH=1 MAX_CHAIN=1 "$S/resubmit_yield_surface_timeouts_CLUSTER.sh" "$S/yield_surface_jobs/JM-25-77_sigy075/n096"   # 17 x "wuerde"
DRY_RUN=1 INCLUDE_FAILED=1 YS_FORCE_FRESH=1 MAX_CHAIN=1 "$S/resubmit_yield_surface_timeouts_CLUSTER.sh" "$S/yield_surface_jobs/JM-25-77_sigy100/n096"   # 13 x "wuerde"
# dann dieselben Zeilen ohne DRY_RUN=1
```

Kontrolle nach dem Start: `grep "PETSc options" <neues .out>` (Optionen
aktiv), nach 1-2 h `grep -c "NO CONVERGENCE"` = 0 und wachsende Zahl
`Computing solution`; scheitert MUMPS weiter, steht jetzt `INFOG(1)=...` im
`.out` (dann ICNTL(14) hoeher oder ICNTL(23)/Speicher).

Die 28 Kriecher laufen vorerst weiter (sie kommen voran). Option spaeter:
`scancel` + `INCLUDE_FAILED=1 MAX_CHAIN=3 resubmit... <combo>/n096` **ohne**
`YS_FORCE_FRESH` -> Fortsetzung vom letzten Snapshot (max. 12 h Verlust) mit
dem gepatchten Template.
