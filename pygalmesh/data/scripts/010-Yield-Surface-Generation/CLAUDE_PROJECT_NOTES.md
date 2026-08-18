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
