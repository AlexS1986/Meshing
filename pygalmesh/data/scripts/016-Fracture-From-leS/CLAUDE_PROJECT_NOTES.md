# CLAUDE_PROJECT_NOTES — 016 Phasenfeld-Bruch aus .leS-Daten

Laufendes Protokoll. Neueste Session oben.

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

1. **Gitter von JM-25-88 ist nicht verifiziert.** Die mitgelieferten Configs
   wurden mit dem Gitter von JM-25-77 erzeugt (1187 × 1188 × 886 @ 16,7 µm),
   weil die `.leS`-Dateien nur auf dem Cluster liegen.
   `02_create_folders_CLUSTER.sh` erzeugt die Configs vor jedem Sync aus dem
   echten Header neu — **beim ersten Lauf die Ausgabe prüfen**: passt der
   Riegel (Crop-Indizes, mm-Maße) zum tatsächlichen Volumen?
   ```bash
   python3 A04_les_header_info.py /data/resources/A01_segmented/JM-25-88_78p86.leS
   ```
2. **Elementgröße gegen Stegdicke prüfen.** 400 µm können in der Größenordnung
   der Stege selbst liegen. Dann bildet das Netz die Struts nicht mehr ab und
   die effektive Steifigkeit fällt. Messen mit
   `evaluate_pore_size_distribution.py`; danach entweder die Elementgröße
   senken oder bewusst dokumentieren, dass gerechnet wird, was aufgelöst ist.
3. **`epsilon ≈ 1 mm` ist größer als die Stegdicke.** Der Riss wird damit über
   mehrere Stege verschmiert; die Simulation bildet eher einen effektiven
   Bruchvorgang im homogenisierten Schaum ab als das Versagen einzelner Stege.
   Das ist die bewusst in Kauf genommene Folge der groben Auflösung — beim
   Auswerten und im Paper klar benennen.
4. **Riegelmaße gegen `epsilon` prüfen.** `epsilon/Ly = 1/8` ist relativ groß.
   Ein höherer Riegel (`LES_BAR_Y_MM`) senkt das Verhältnis, kostet aber
   Elemente. Nach dem ersten Lauf mit den J-Werten abwägen.
5. **Tetraederzahl ist nur geschätzt.** Nach dem ersten Netz nachziehen:
   ```bash
   grep mesh_tetrahedra .../subvolume_x0_y0/mesh.quality.txt
   ```
6. **Randschalendicke in y** ist mit dem Faktor 1,5 aus 015 übernommen
   (dort 12 gegenüber 8 Voxeln). Ob y bei den Surfing-BCs überhaupt dicker sein
   muss als x/z, ist nicht geprüft.
7. **`Gc = 7,2 N/mm`** gilt für kompaktes AlSi10Mg (DOI
   10.1016/j.ijmecsci.2021.106868, Bereich 6,0–8,4). Ob der Wert für die
   Stege eines geschäumten Bauteils gilt, ist offen.
8. **Rechenzeit unbekannt.** `-t 10080` (7 Tage) ist aus 012 übernommen, dort
   für ein deutlich kleineres Gebiet. Nach dem ersten Lauf mit `sacct`
   nachmessen.
