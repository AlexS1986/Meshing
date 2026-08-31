# CLAUDE_PROJECT_NOTES — 016 Phasenfeld-Bruch aus .leS-Daten

Laufendes Protokoll. Neueste Session oben.

**Aktueller Datensatz: JM-25-77** (seit 2026-08-31; davor JM-25-88).

---

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
2. **Elementgröße gegen Stegdicke prüfen.** 400 µm können in der Größenordnung
   der Stege selbst liegen. Dann bildet das Netz die Struts nicht mehr ab und
   die effektive Steifigkeit fällt. Messen mit
   `evaluate_pore_size_distribution.py`; danach entweder die Elementgröße
   senken oder bewusst dokumentieren, dass gerechnet wird, was aufgelöst ist.
3. **`epsilon ≈ 0,84 mm` ist größer als die Stegdicke.** Der Riss wird damit über
   mehrere Stege verschmiert; die Simulation bildet eher einen effektiven
   Bruchvorgang im homogenisierten Schaum ab als das Versagen einzelner Stege.
   Das ist die bewusst in Kauf genommene Folge der groben Auflösung — beim
   Auswerten und im Paper klar benennen.
4. **Riegelmaße.** `epsilon/Ly = 1/20` wie 011, aber `Lx/Ly ≈ 1,2` statt 4,9.
   Ob die 19 epsilon Lauflänge für einen stationären J-Verlauf reichen, zeigt
   der erste Lauf; sonst `02e`-Spiegelung (011-Route) erwägen.
5. **Tetraederzahl ist nur geschätzt.** Nach dem ersten Netz nachziehen:
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
   für ein deutlich kleineres Gebiet. Nach dem ersten Lauf mit `sacct`
   nachmessen.
