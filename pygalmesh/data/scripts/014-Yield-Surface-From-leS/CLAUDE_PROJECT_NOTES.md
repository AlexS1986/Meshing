# Projekt-Notizen 014-Yield-Surface-From-leS

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

# Projekt-Notizen: 014-Yield-Surface-From-leS

Diese Datei dokumentiert, was in diesem Ordner verstanden, entschieden und
gebaut wurde. Sie wird von Claude gepflegt (gelesen und editiert) und liegt
bewusst direkt im Projektordner, damit sie in künftigen Sessions wieder
gefunden wird.

## Wo liegt der Code (Kurzreferenz)

Projekt-Root: `~/Work/Hypo/Hypo/Simulation` (Container-Bind:
`Meshing/pygalmesh/data` → `/data`).

- Preprocessing + Vernetzung: `Meshing/pygalmesh/data/scripts/014-Yield-Surface-From-leS/`
- Simulationstemplate: `.../014-Yield-Surface-From-leS/00_template/elastoplastic.py`
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
  `A01_segmented/` (Container: `/data/scripts/014-Yield-Surface-From-leS/A01_segmented/`).
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
