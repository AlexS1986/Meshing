# CLAUDE_PROJECT_NOTES — 016 Phasenfeld-Bruch aus .leS-Daten

Laufendes Protokoll. Neueste Session oben.

**Aktueller Datensatz: JM-25-77** (seit 2026-08-31; davor JM-25-88).

---

## Session 2026-09-02 — Ganze Probe statt Riegel, reduce = 4, Route aus 011

### Auftrag (Nutzer)

1. „Die Vernetzung ist deutlich zu grob" → sinnvollen Kompromiss finden,
   Vorschlag reduce = 4.
2. Es soll **nichts herausgeschnitten** werden: die ganze Probe modellieren,
   als Voxel spiegeln, in eine homogene Randschicht einbetten und dann
   vernetzen — wie in 011.

### Befund zur Grobheit

Das Problem lag vor der Vernetzung: `coarse` lief auf `reduce = 8`
(133,6-µm-Voxel). Der Majority-Vote über 8³ Voxel löscht Stege unter ~70 µm
und verklumpt solche um 130 µm; `sdf_sigma_voxels = 1` glättet danach noch
einmal um ein Voxel. Bei 85,55 % Porosität sind die Stege vermutlich nur ein
paar hundert µm dick — vernetzt wurde also eine bereits stark vereinfachte
Geometrie, und darauf saß ein 400-µm-Element je Stegdicke.

### Entscheidungen (Nutzer, nach Vorschlag)

| Frage | Entscheidung | Alternativen |
|---|---|---|
| Ausschnitt | **keiner** — ganze Probe 19,8 × 19,8 × 14,8 mm (`LES_BAR_*_MM` leer) | Riegel 16 × 4 mm bleibt über `LES_BAR_Y_MM`/`_Z_MM` verfügbar |
| Spiegelung | **1× in x** (`LES_MIRROR_X_REPETITIONS = 1`, 02e, `2·Nx − 1`) → Schaum 39,5 mm lang, `Lx/Ly = 2,3`, Risslauf ≈ 35 epsilon | 2× wie 011 (`4·Nx − 3`, `Lx/Ly ≈ 4`): ~1,7-fache Elementzahl |
| Endblöcke x | **4 mm** homogenes Aluminium wie 011 (`LES_SHELL_X_UM = 4000` → 60 Voxel bei reduce 4); Kerbspitze bei 0,2·Lx = 9,5 mm liegt 5,5 mm im Schaum | 2 mm spart ~¼ der Elemente |
| y/z-Schale | 0,4 mm wie bisher (6 Voxel) | — |
| Auflösung | **reduce = 4** in allen Stufen; Elemente **250 / 200 / 150 µm** (coarse/medium/fine), **Default `medium` = 200 µm** | 150 µm ≈ 12 Mio Tets, vermutlich zu teuer (015 lief bei 12 Mio dofs ans Speicherlimit) |
| `eps_factor` | 20 unverändert → `epsilon = 20,64 mm / 20 = 1,03 mm`, 4,1 / 5,2 / 6,9 Elemente je epsilon | — |

Die Kostenschätzung (kalibriert an 011: 381 k Tets bei 402 µm auf 4300 mm³
Material; 015: 12,3 Mio dofs bei 75 µm/reduce 2 auf der ganzen Probe):

| Stufe | Tets (Schätzung) | dofs (u, s) | Anmerkung |
|---|---:|---:|---|
| coarse 250 µm | ~2,5 Mio | ~2 Mio | Stege teils 1 Element dick |
| **medium 200 µm** | ~5 Mio | ~3,7 Mio | Default |
| fine 150 µm | ~12 Mio | ~9 Mio | Speicher/Laufzeit prüfen, bevor er eingereicht wird |

Rund die Hälfte der Elemente sitzt in der massiven Schale (Endblöcke
2 × 4 × 20,6 × 15,6 mm³ ≈ 2570 mm³ gegen ≈ 1670 mm³ Schaummaterial) — pygalmesh
kennt keine regionale Elementgröße. Laufzeit-Anhaltspunkt: 011 brauchte für
0,4 Mio dofs 66 min (191 Schritte, 96 Kerne); bei ~3,7 Mio dofs und
LU-Skalierung ~N² wären das Tage. `-t 10080` bleibt.

### Geänderte Dateien

| Datei | Änderung |
|---|---|
| `config.sh` | `LES_BAR_*_MM` leer (ganze Probe), neu `LES_MIRROR_X_REPETITIONS = 1`, `LES_SHELL_X_UM = 4000`; `MESH_TIERS` → `coarse|4|250`, `medium|4|200`, `fine|4|150`; `DEFAULT_TIER = medium`. Backup `config.sh.bak_20260902`. |
| `create_fracture_config.py` | neu `--mirror-x-repetitions` (schreibt den `02e`-Block wie 011, `plane = min`, `drop_duplicate_plane`), `--shell-x-um`; `--bar-y-mm`/`--bar-z-mm` ohne Default (leer = ganze Achse); `fracture_geometry_check` enthält jetzt `foam_extent_mm`, `mirror_x_repetitions`, `foam_voxels_reduced`, `crack_start_x_mm`, `crack_start_in_foam_mm`, `shell_x_thickness_mm`; `bar_extent_mm.x` rechnet die Spiegelung ein (voxelgenau `2n − 1`). Backup `create_fracture_config.py.bak_20260902`. |
| `create_fracture_config.sh` | `--bar-*-mm` nur noch, wenn gesetzt; reicht `LES_MIRROR_X_REPETITIONS` und `LES_SHELL_X_UM` durch. |
| `create_les_dataset_config.py` | Fix aus 015 (01.09.) nachgezogen: `03_mesh_3D_array.max_element_size_um` wird immer aus Faktor × Voxelgröße abgeleitet. Vorher stand in der 150-µm-Config „75.0" (gleicher Faktor 2,2455 wie die 75-µm-Basis bei reduce 2). Der Mesher nutzt nur den Faktor — kein Netz war falsch, nur das Metadatum. |
| `config-fracture-JM-25-77-{coarse,medium,fine}.json` | neu erzeugt (lokal, Gitter aus `config.sh`). |

`run_generate_mesh_CLUSTER.sh` brauchte keine Änderung: die Kette
`02b → 02c → 02e → 02f → 03 → 04 (--npy) → 10 → 05/08/09` ist seit 015/011 da
und hängt nur an den `enabled`-Flags. `04_scale_and_translate_mesh_mod.py`
(011-Version) rechnet Spiegelung und Schale über `--npy` heraus — geprüft im
Code (`transformed_voxel_bounds`).

### Verifikationsstand

- `create_fracture_config.sh` lokal gelaufen (Python 3.10): drei Configs,
  `A01.crop` = `null/null/null`, `02e` an (`repetitions = 1`), `02f`
  60/6/6 Voxel, `02d` aus, `10` an, `11` aus, `keep_largest_component = true`,
  `pad_width = 3`. Box 47,49 × 20,64 × 15,56 mm, Schaum 39,48 × 19,84 × 14,76 mm
  (591 × 297 × 221 reduzierte Voxel), epsilon 1,032 mm.
- Nicht lokal prüfbar: `A01` auf dem vollen Volumen mit `crop = null`
  (015 hat genau das mit `LES_BOUNDS_MODE = full` gemacht), `02e` auf
  19 MVoxel, Speicher/Laufzeit von `03`.

### Beim nächsten Lauf prüfen

1. `volume_mirrored_x1.txt`: `mirrored_shape = (591, 297, 221)`,
   `material_multiplier ≈ 2`.
2. `volume_external_shell.txt`: `shelled_shape = (711, 309, 233)`.
3. `04`-Log: `origin_vox`/`shape` ohne die Warnung „differs from meshed npy shape".
4. `mesh.quality.txt`: `mesh_tetrahedra` gegen die Schätzung (~5 Mio bei medium).
5. Simulationslog: Anzahl dofs; erste Schritte: `uY` antisymmetrisch in y,
   Kerb bei x < 9,5 mm; `x_tip` folgt `xtip_soll`.
6. Der Riss überquert die Spiegelebene bei x = 4 + 19,74 = 23,7 mm — dort im
   J-Verlauf auf Symmetrieartefakte achten.
7. `job_run_simulation_CLUSTER.sh` hat keine `-p`-Zeile bei `-t 10080`; der
   erste 016-Lauf wurde trotzdem angenommen. Falls SLURM den Job jetzt wegen
   des Zeitlimits ablehnt: `#SBATCH -p long` (015-Erfahrung: `deflt` max 1440 min).

## Session 2026-08-31 — Erster Cluster-Lauf ausgewertet: drei Fehler, drei Korrekturen

### Befund des ersten Laufs (JM-25-88, coarse)

Der Nutzer hat `job_generate_mesh_CLUSTER` und `job_run_simulation_CLUSTER`
laufen lassen. ParaView zeigte: (1) uY linear in x, uX linear in y, Dehnung ≈ 0
— **eine reine Starrkörperrotation, keine Belastung**; (2) sehr wenige Poren,
dicke Vollmaterialwände. Ursachenanalyse:

| Symptom | Ursache | Korrektur |
|---|---|---|
| keine Belastung, Starrkörpermode | `alex.boundaryconditions.get_boundary_of_box_as_function` wendet die Surfing-Verschiebung **nur bei `|y − y_mid| ≥ 4·epsilon`** an (Rissband ausgespart). Mit `eps_factor = 8` ist `4·epsilon = Ly/2` → BC auf **keinem** Knoten. 011 hatte `eps_factor = 20` → BC auf den äußeren 60 % der Höhe. `00_template/` selbst ist byte-identisch mit 011. | `eps_factor = 20` (wie 011). Grobe Elemente werden über die Riegelhöhe aufgefangen: `Ly = 16 mm` → `epsilon ≈ 0,84 mm` → 2,1 / 3,1 / 4,2 Elemente je epsilon. Harte Abbruchprüfung `eps_factor ≤ 8` in `create_fracture_config.py` und `job_run_simulation_CLUSTER.sh`; `surfing_bc_band_fraction = 1 − 8/eps_factor` steht jetzt in jeder Config. |
| dicke Wände, wenig Mikrostruktur | `02d boundary_seal` mit 9/14/9 Voxeln **eingeschaltet**: bei 133,6 µm Voxeln 1,2 / 1,9 / 1,2 mm Vollaluminium **in den Riegel hinein**. Von 4 mm Dicke blieben 1,6 mm Schaum, von 7,9 mm Höhe 4,1 mm. Dazu `keep_largest_component`: alles, was nach der 8×-Reduktion nicht an der Schale hängt, fiel weg. 011 hatte 02d **aus** und stattdessen `02f_add_voxel_shell` (externe Schale, 3 Voxel ≈ 0,4 mm in y/z). | Wie 011: `LES_SHELL_MODE=external`, `02f` mit `LES_SHELL_UM=400` (3 Voxel coarse, 6 Voxel medium/fine — die Schale muss ≥ 1 Element dick bleiben). 02d-Seal aus. `04_scale_and_translate_mesh_mod.py` durch die **011-Version** ersetzt (`--npy`, rechnet die Schalenverschiebung des Ursprungs heraus; die 015-Version hätte das Netz um die Schale gestaucht — in z um 20 %). `10_snap_mesh_to_crop_boundary` wie 011 aktiviert. |
| Datensatz | JM-25-88 war eine reine Nutzerentscheidung vom 21.08. („der dichteste"), kein physikalischer Grund. | **JM-25-77** (`JM-25_77_85p55.leS`, 85,55 %). Vorteil: einziger Datensatz mit in 014 verifiziertem Gitter (1187 × 1188 × 886 @ 16,7 µm) → `LES_GRID`/`LES_VOXEL_SIZE_M` fest in `config.sh`, Configs lokal erzeugbar. Bei Wechsel beide Variablen leeren. |

Nebenbefund: 011 rechnete tatsächlich mit **Voxel 134 µm und `max_element_size_factor = 3,0` = 402 µm Elementen** (nicht 199 µm, wie in den Notizen stand), Ly = 14,2 mm, epsilon = 0,71 mm → ~1,8 Elemente je epsilon, Lx ≈ 70 mm (gespiegelt), Lz ≈ 7,8 mm. Die Stufe `coarse` entspricht also der 011-Auflösung.

Zweiter Nebenbefund: die 015-Basis hat `max_element/max_facet = 16,7`; skaliert auf 400 µm wären das 24 µm Facettenabstand unter 400-µm-Elementen. 011 hatte 3,0/1,0. Neu: `LES_FACET_DISTANCE_RATIO=3` → 133 µm bei coarse.

### Neue Geometrie (alle Stufen, JM-25-77)

| | coarse | medium | fine |
|---|---:|---:|---:|
| Riegel inkl. Schale [mm] | 20,62 × 16,70 × 4,81 | 20,62 × 16,77 × 4,81 | 20,62 × 16,77 × 4,81 |
| Schaum-Crop (Originalgitter) | x voll, y [112, 1064], z [320, 560] | y [116, 1072] | y [116, 1072] |
| Schale extern | 3 Voxel = 401 µm | 6 Voxel = 401 µm | 6 Voxel = 401 µm |
| epsilon = Ly/20 [mm] | 0,835 | 0,838 | 0,838 |
| Elemente je epsilon | 2,1 | 3,1 | 4,2 |
| BC-Band `|y−y_mid| ≥ 4·eps` | 60 % der Höhe = 5,0 mm je Seite | 60 % | 60 % |
| max_facet_distance | 133 µm | 89 µm | 67 µm |

Riegel ist jetzt nur noch `Lx/Ly ≈ 1,2` (011: 4,9). Der Riss startet bei
`0,2·Lx ≈ 4 mm` und hat ≈ 16 mm = 19 epsilon Lauflänge — genug für einen
stationären Bereich. Wer ein längeres Gebiet will: `02e`-Spiegelung ist
weiterhin zuschaltbar (011-Route), bringt aber die künstliche Symmetrie zurück.

### Geänderte Dateien

`config.sh`, `create_fracture_config.sh`, `create_fracture_config.py`,
`job_run_simulation_CLUSTER.sh` (eps_factor-Guard), `run_generate_mesh_CLUSTER.sh`
(`--npy` an 04), `04_scale_and_translate_mesh_mod.py` (jetzt 011-Version; die
015-Version liegt als `*.from015.bak` daneben), alle `*.bak` sind die Stände vor
dieser Session. Alte `config-fracture-JM-25-88-*.json` in `_superseded_2026-08-31/`
(sie tragen den BC-Fehler und die dicke Schale — nicht mehr verwenden).

### Verifikationsstand

* `bash -n` auf allen geänderten Shell-Skripten, `py_compile` auf dem Generator.
* `create_fracture_config.sh` erzeugt die drei JM-25-77-Configs ohne Warnung
  (Ausgabe oben in der Tabelle).
* `transformed_voxel_bounds` der 011-`04_mod` gegen ein synthetisches
  016-Metadatum geprüft: Ursprung (−3, −3, −3) Voxel, Schaum liegt in
  [0, L], Schale außen — korrekt.
* **Nicht ausgeführt:** die Cluster-Kette. Vor dem ersten Lauf
  `02_create_folders_CLUSTER.sh` (synchronisiert die neuen Configs).

### Nachtrag: erster Start nach der Korrektur schlug fehl

`/usr/bin/python3: can't open file '/work/scratch/…/016-Fracture-From-leS/A01_les_2_npy.py'`
plus `WARNING: Error changing the container working directory … chdir
/home/as12vapa/meshing/Meshing/pygalmesh`. Ursache: `run_generate_mesh_CLUSTER.sh`
hatte das `cd "$working_directory"` aus 015 nicht übernommen. Apptainer bindet
nur `/home`, `/data` und das **aktuelle Verzeichnis**; wird `sbatch` aus
`$HOME/meshing/Meshing/pygalmesh` abgeschickt (so steht es im README für den
Sync-Schritt), sieht der Container die Host-Pfade unter `/work/scratch` nicht.
Behoben: `cd "$working_directory"` in `run_generate_mesh_CLUSTER.sh` und
`job_run_simulation_CLUSTER.sh`. Der erste 016-Lauf am 21./…08. ist vermutlich
nur deshalb durchgelaufen, weil damals aus `$HPC_SCRATCH` heraus submittiert wurde.

### Erstes Netz JM-25-77 coarse (Job 54434143) — Kennzahlen aus dem Log

* Header bestätigt: 1187 × 1188 × 886 @ 16,7 µm. Crop x[0:1184] y[112:1064]
  z[320:560] → reduziert (148, 119, 30); mit Schale (154, 125, 36).
* **Porosität im Riegel 90,2 %** (Aluminium 9,8 %; nach Reduktion 9,6 %) —
  deutlich poröser als die 85,55 % des Gesamtvolumens: der Riegel liegt im
  Probenkern, die dichtere Randzone fällt weg. Beim Vergleich mit Literatur-
  werten die lokale Porosität nehmen, nicht die aus dem Dateinamen.
* `keep_largest_component` hat nur ≈ 800 von ≈ 51 000 Schaum-Aluminium-Voxeln
  entfernt (214 695 Materialvoxel nach dem Filter, davon 164 640 Schale) — das
  Stegnetz ist bei 134 µm Voxeln also noch zusammenhängend.
* Netz: **34 657 Tetraeder, 11 711 Punkte** (011: 381 039 / 100 188 bei 6,6-fach
  größerem Materialvolumen). Mittleres Tetraedervolumen 0,015 mm³ ≈ 0,5 mm
  Kantenlänge — passt zur Zielgröße 400 µm. Die Simulation wird damit Minuten
  bis Stunden dauern, nicht Tage; `-t 10080` ist weit überdimensioniert.
* `04_mod` (011-Version): origin_vox = (−3, −3, −3), shape (154, 125, 36) —
  Schale liegt außen, wie vorgesehen. `10_snap`: 4851 Knoten gezogen.
* Verdicts: SDF-Oberfläche **good**, Netzqualität **good**, Voxeltopologie
  **bad** (mehrdeutige 2×2×2-Blöcke) und Netztopologie **bad** (nicht-mannig-
  faltige Randkanten) — **beides genauso in 011** (dort 3816 nicht-mannigfaltige
  Randkanten, 45 Randkomponenten) und dort ohne Folgen für DOLFINx. Kein Blocker.
* **Die Simulation startet nur dann automatisch, wenn die Kette über
  `submit_fracture_pipeline_CLUSTER.sh` eingereicht wurde** (`--dependency=afterok`).
  Ein direktes `sbatch job_generate_mesh_CLUSTER.sh` reiht nichts nach. Dann:
  `sbatch job_run_simulation_CLUSTER.sh config-fracture-JM-25-77-coarse.json`
  oder `SKIP_MESH=1 submit_fracture_pipeline_CLUSTER.sh`.

### Simulationsjob: `-N 1` abgelehnt

`-n 96 × --mem-per-cpu=4000 = 384 000 MB` übersteigt die 364 800 MB eines
i01-Knotens; mit `-N 1` ist der Job nicht platzierbar. In 011/012 stand
dasselbe — vermutlich ist die Knotenkonfiguration seither anders bilanziert.
**Entscheidung (Nutzer):** `-n 96 × 4000 MB` bleibt, **`-N 1` entfällt** —
SLURM darf auf zwei Knoten verteilen. Header und `submit_fracture_pipeline_
CLUSTER.sh` fordern dasselbe an (`-t 10080`). Die Zwischenlösung 24 × 3800
auf einem Knoten wurde verworfen.

### Beim nächsten Lauf prüfen

1. `pfmfrac_function_log.txt`: Newton konvergiert in wenigen Iterationen (011: 3–4).
2. ParaView, Schritt 1: uY muss **antisymmetrisch in y** sein (oben +, unten −),
   uX symmetrisch — das ist das K-Feld. Bleibt es eine Rotation, greift die BC
   immer noch nicht.
3. `mesh.quality.txt` → Tetraederzahl; `volume_external_shell.txt` → Schale
   ist außen (shelled_shape = original_shape + 6 bzw. + 12).
4. `x_tip` vs. `xtip_soll` in `pfmfrac_function_graphs.txt`.

---

## Session 2026-08-21 — Projekt angelegt

### Auftrag

Phasenfeld-Bruchsimulationen mit den neuen `.leS`-Netzen rechnen. Vorlagen sind
011 (Bruch aus CT-Scans, ein kombinierter Job) und 012 (dasselbe, aber Netz und
Simulation getrennt). Zunächst ein Datensatz.

### Entscheidungen

| Frage | Entscheidung | Begründung |
|---|---|---|
| Datensatz | **JM-25-88** (`JM-25-88_78p86.leS`, 78,86 % Porosität) | vom Nutzer gewählt; der dichteste der vier Datensätze |
| Probengeometrie | **langer Riegel direkt aus dem Volumen**, x voll (≈ 19,8 mm), y = 8 mm, z = 4 mm, mittig | Die Surfing-BCs brauchen ein in x langgestrecktes Gebiet. Anders als in 012 ist das `.leS`-Volumen groß genug — die dortige zweifache Spiegelung in x (`4·Nx − 3`) war nur nötig, weil das CT-Teilvolumen zu klein war. Ohne Spiegelung entfällt eine künstliche Symmetrie. |
| Auflösung | **Familie coarse/medium/fine**, deutlich gröber als 015 | Nutzer: „müssen auch mit einer deutlich gröberen Auflösung/Netzfeinheit durchgeführt werden". coarse = 400 µm Elemente (015: 75 µm, 011/012: 199 µm). |
| `eps_factor_param` | **8** statt 20 | `epsilon = Ly / eps_factor`. Mit 20 wäre `epsilon` bei 8 mm Riegelhöhe nur 0,4 mm — von 400-µm-Elementen nicht auflösbar. Mit 8 ist `epsilon ≈ 1,0 mm` und damit 2,5 Elemente breit. |
| Projektstruktur | **zweistufig wie 012** | Vernetzen (Partition `mem`, Stunden) und Rechnen (Partition `long`, Tage) haben völlig verschiedene Ressourcenprofile. Getrennt kann das Netz wiederverwendet werden, ohne neu zu vernetzen. |
| Fließflächenteil | **entfernt** | 016 rechnet Bruch. `yield_surface`-Block, `setup_yield_surface_jobs*`, `collect_yield_surface_points*`, `check_yield_surface_points*`, `batch_*` und `write_yield_surface_parameters` wurden nicht übernommen. |

### Die Auflösungsfamilie im Detail

`MESH_TIERS` in `config.sh`:

| Stufe | reduce | Voxel* | Elementgröße | Elemente je epsilon** |
|---|---:|---:|---:|---:|
| coarse | 8 | 133,6 µm | 400 µm | 2,46 |
| medium | 4 | 66,8 µm | 267 µm | 3,72 |
| fine | 4 | 66,8 µm | 200 µm | 4,97 |

\* bei 16,7 µm Quellvoxeln. \** bei `Ly ≈ 7,9 mm`, `eps_factor = 8`.

`epsilon` bleibt über alle Stufen praktisch gleich (0,985 / 0,994 / 0,994 mm),
weil es nur an der Riegelhöhe hängt. Die Familie variiert also **nur die
Diskretisierung** — sie ist eine Netzkonvergenzstudie im eigentlichen Sinn.
Das war in 012 anders: dort skalierten `max_element_size_factor` und
`max_facet_distance_factor` proportional (3,0/1,0 → 2,25/0,67 → 1,5/0,33), und
`eps_factor` blieb bei 20, wodurch `epsilon` mit der Probengröße mitwanderte.

### Randschale wird jetzt abgeleitet

In 015 standen 8 (x/z) und 12 (y) Voxel fest — abgestimmt auf 75-µm-Elemente bei
33,4-µm-Voxeln, also rund 3,5 Elemente Dicke. Bei 400-µm-Elementen wären 8 Voxel
(= 1069 µm) zwar dicker, bei 267 µm auf feinerem Gitter aber deutlich zu dünn.

`create_fracture_config.py` rechnet die Dicke deshalb aus:
`ceil(LES_BOUNDARY_SHELL_ELEMENTS · h / dx)` Voxel, `y` das 1,5-fache davon
(wie in 015, wo y ebenfalls dicker war als x/z). Ergebnis:

| Stufe | x/z | y |
|---|---:|---:|
| coarse | 9 | 14 |
| medium | 12 | 18 |
| fine | 9 | 14 |

Feste Werte weiterhin über `LES_BOUNDARY_SHELL_XZ` / `LES_BOUNDARY_SHELL_Y`.

### Übernommene Fallen aus 012 und 015

1. **`run_name` muss auflösungsspezifisch sein.** Der Archivpfad wird aus
   `03_mesh_3D_array.specimen_name` gebildet, **nicht** aus
   `01_segment_slice_wise.specimen_name` — letzteres ist über die Stufen hinweg
   gleich, und alle drei würden sich gegenseitig überschreiben. Kommentar steht
   an beiden Stellen im Code.
2. **`srun`-Steps erben Zeit und Speicher vom Job.** Feste `--mem-per-cpu`-Werte
   im Step führten in 015 zu `More processors requested than permitted`.
   `SRUN_MEM_PER_CPU` ist deshalb leer voreingestellt.
3. **`pad_width = 3`** statt 1 vor dem Signed-Distance-Field (in 014 gemessen:
   `pad_width = 1` mit `sigma = 1,25` → 7180 offene Kanten).
4. **`keep_largest_component = true`** — die kleinen Materialinseln erzeugen im
   FE Starrkörpermoden.
5. **Genau eine `.leS`-Datei.** `A01_les_2_npy.py` bricht ab, wenn im Ordner
   mehrere liegen; im `A01_segmented`-Ordner liegen vier. `config.sh` zeigt
   deshalb auf die konkrete Datei (`LES_FILENAME`), nicht auf den Ordner.

### Neu geschriebene Dateien

`config.sh`, `create_fracture_config.py`, `create_fracture_config.sh`,
`A04_les_header_info.py`, `02_create_folders_CLUSTER.sh`,
`job_generate_mesh_CLUSTER.sh`, `run_generate_mesh_CLUSTER.sh`,
`job_run_simulation_CLUSTER.sh`, `submit_fracture_pipeline_CLUSTER.sh`,
`CLAUDE.md`, `LES_FRACTURE_PIPELINE.md`, `FILES.md`, `README.md`, diese Datei.

Alles andere ist unverändert aus 015, 012 oder 011 kopiert — siehe `FILES.md`.

### Verifikationsstand

* `bash -n` auf allen sieben Shell-Skripten: fehlerfrei.
* `create_fracture_config.sh` erzeugt alle drei Configs; JSON validiert;
  Ausgabepfade zeigen auf `/data/scripts/016-Fracture-From-leS/`;
  `yield_surface` ist entfernt, `fracture` vorhanden.
* `A04_les_header_info.py` gegen eine synthetische Headerzeile geprüft
  (`1187 1188 886 1.670000e-05` → 19,82 × 19,84 × 14,80 mm).
* **Nicht ausgeführt:** die eigentliche Kette. `02c` (scipy) und `03`
  (nanomesh/pygalmesh) laufen lokal nicht; der erste echte Test ist der
  Cluster-Lauf.

---

## Offene Punkte

1. ~~Gitter von JM-25-88 ist nicht verifiziert.~~ **Erledigt durch Wechsel auf
   JM-25-77** (Gitter in 014 verifiziert, fest in `config.sh`). Gilt wieder,
   sobald ein anderer Datensatz gerechnet wird: dann `LES_GRID`/`LES_VOXEL_SIZE_M`
   leeren und den Header auf dem Cluster lesen lassen:
   ```bash
   python3 A04_les_header_info.py /data/resources/A01_segmented/<datei>.leS --format shell
   ```
2. **Elementgröße gegen Stegdicke prüfen.** Seit 02.09. reduce = 4 mit
   200 µm (Default) — Stege ab ~130 µm bleiben im Voxelbild erhalten, sind im
   Netz aber teils nur ein Element dick. Messen mit
   `evaluate_pore_size_distribution.py`; danach bewusst dokumentieren, was
   aufgelöst ist.
3. **`epsilon ≈ 1,03 mm` ist größer als die Stegdicke.** Der Riss wird damit über
   mehrere Stege verschmiert; die Simulation bildet eher einen effektiven
   Bruchvorgang im homogenisierten Schaum ab als das Versagen einzelner Stege.
   Mit 5 Elementen je epsilon (medium) wäre jetzt Spielraum, `eps_factor` auf
   30–40 zu erhöhen (epsilon 0,5–0,7 mm, BC-Band 73–80 %) — das rückt näher
   an das Versagen einzelner Stege. Erst nach dem ersten Lauf entscheiden.
4. **Geometrie.** Ganze Probe, 1× gespiegelt: `Lx/Ly = 2,3` (011: 4,9),
   Risslauf ≈ 35 epsilon. Reicht das nicht für einen stationären J-Verlauf,
   `LES_MIRROR_X_REPETITIONS = 2`. Die Spiegelebene bei x ≈ 23,7 mm ist eine
   künstliche Symmetrie — im J-Verlauf darauf achten.
5. **Tetraederzahl ist nur geschätzt** (~5 Mio medium). Nach dem ersten Netz nachziehen:
   ```bash
   grep mesh_tetrahedra .../subvolume_x0_y0/mesh.quality.txt
   ```
6. **Randschale** ist jetzt extern und isotrop 400 µm (wie 011). `atol` der
   BC-Suche in `pfmfrac_function.py` ist `0,02·Lx ≈ 0,41 mm` — praktisch gleich
   der Schalendicke, d.h. auch die Innenfläche der Schale bekommt die
   Dirichlet-Werte. War in 011 genauso (atol 1,4 mm bei 0,4 mm Schale) und hat
   funktioniert; trotzdem im Blick behalten.
7. **`Gc = 7,2 N/mm`** gilt für kompaktes AlSi10Mg (DOI
   10.1016/j.ijmecsci.2021.106868, Bereich 6,0–8,4). Ob der Wert für die
   Stege eines geschäumten Bauteils gilt, ist offen.
8. **Rechenzeit unbekannt.** `-t 10080` (7 Tage) ist aus 012 übernommen, dort
   für ein deutlich kleineres Gebiet. Anhaltspunkt: 011 brauchte 66 min für
   0,4 Mio dofs; bei ~3,7 Mio dofs (medium) sind Tage zu erwarten. Nach dem
   ersten Lauf mit `sacct` nachmessen; `fine` (≈ 9 Mio dofs) erst danach.
9. **Schale dominiert das Netz.** Die 4-mm-Endblöcke und die 0,4-mm-Hülle sind
   rund die Hälfte der Elemente. Wenn Kosten drücken: `LES_SHELL_X_UM=2000`.
