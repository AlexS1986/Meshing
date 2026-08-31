# CLAUDE.md — 016 Phasenfeld-Bruch aus .leS-Daten

Diese Datei beschreibt, **wie in diesem Ordner gearbeitet wird**. Sie ist die
erste Datei, die in einer neuen Session gelesen werden soll.

**Grundregel (Projektvorgabe):** Alles, was entschieden oder gelernt wird, wird
in einer `.md`-Datei dokumentiert — hier bzw. in `CLAUDE_PROJECT_NOTES.md`.

---

## 1. Was dieses Projekt ist

016 kombiniert zwei bestehende Zweige:

| Herkunft | was übernommen wurde |
|---|---|
| **015-Yield-Surface-Batch-leS** | die komplette `.leS`-Vorverarbeitung und Vernetzung (`A01` → `02b` → `02c` → `02d` → `03` → `04` → `05/08/09` → DolfinX-Netz) |
| **012-Fracture-Mesh-Sim-Split** | die Aufteilung in zwei unabhängige SLURM-Jobs: Netz erzeugen, dann simulieren; Archiv unter `generated_meshes/` |
| **011-Fracture-From-CT-Scans** | `00_template/` mit `script.py` und `pfmfrac_function.py` — die Phasenfeld-Bruchsimulation mit Surfing-Randbedingungen und J-Integral |

Was **nicht** übernommen wurde: der DICOM-Zweig (`00`/`01`/`02`/`02a`) und der
gesamte Fließflächen-Teil aus 015 (`yield_surface`-Block, `setup_yield_surface_jobs`,
`collect_yield_surface_points`). Dieses Projekt rechnet Bruch, keine Fließfläche.

**Ausgewählter Datensatz (seit 2026-08-31):** `JM-25_77_85p55.leS` — JM-25-77,
85,55 % Porosität, der einzige Datensatz mit in 014 verifiziertem Gitter
(1187 × 1188 × 886 @ 16,7 µm; fest in `config.sh`). Davor JM-25-88 (Nutzerwahl
ohne physikalischen Grund). Wechsel über `SPECIMEN_NAME`/`LES_FILENAME` in
`config.sh`; dann `LES_GRID`/`LES_VOXEL_SIZE_M` leeren.

---

## 2. Ordner und Container-Mapping

```text
Host (Mac)     : ~/Work/Hypo/Hypo/Simulation/Meshing/pygalmesh/data/scripts/016-Fracture-From-leS/
Host (Cluster) : $HPC_SCRATCH/pygalmesh/data/scripts/016-Fracture-From-leS/
Container      : /data/scripts/016-Fracture-From-leS/
```

In JSON-Configs steht **immer der Container-Pfad** (`/data/...`), nie ein
unaufgelöstes `$HPC_SCRATCH`. Die Cluster-Skripte rechnen `/data` per
`${pfad/#\/data/$HPC_SCRATCH/pygalmesh/data}` auf den Host zurück.

`.leS`-Daten: `/data/resources/A01_segmented/` (Container) bzw.
`$HPC_SCRATCH/pygalmesh/data/resources/A01_segmented/` (Host).

---

## 3. Arbeitsweise / Konventionen

1. **Vor dem Bauen lesen:** diese Datei, `CLAUDE_PROJECT_NOTES.md`,
   `LES_FRACTURE_PIPELINE.md`; für Details der Voxel→FEM-Kette
   `PIPELINE_ANNAHMEN_DICOM_TO_FEM.md`.
2. **Skripte werden vorbereitet, nicht blind ausgeführt.** Vernetzung und FE
   startet der Nutzer selbst auf dem Cluster. Ausnahme: kleine
   Verifikationsläufe auf Teilausschnitten.
3. **Configs werden abgeleitet, nicht von Hand geschrieben.** Basis ist
   `config-A01-les-base.json` (1:1-Kopie der in 015 gelaufenen Config);
   `create_fracture_config.sh` erzeugt daraus die Stufen coarse/medium/fine.
4. **Array-Konvention:** `uint8`-Arrays der Form `(x, y, z)`, `z` ist die
   Slice-Achse.
5. **⚠ Phasenkonvention:** In der `.leS`-Quelle gilt 1 = Material, 0 = void.
   `A01_les_2_npy.py` invertiert auf die Pipeline-Konvention **1 = Pore,
   0 = Aluminium**; Schritt 03 invertiert erneut, erst danach ist
   `material_mask == 1` das Aluminium. Die Randschale aus 02d (Wert 0) ist
   genau darauf abgestimmt.
6. **Voxelgröße** kommt aus dem `.leS`-Header (Einheit m) und wird von
   `A01_les_2_npy.py` als `00_dicom2npy.SliceThickness` in mm weitergegeben.
7. **Dokumentieren statt merken.**

---

## 4. Die zentrale Größe: epsilon, nicht die Voxelgröße

Beim Phasenfeld-Bruch ist die bindende Auflösungsgrenze **nicht** die
Voxelgröße, sondern die Regularisierungslänge

```text
epsilon = (y_max - y_min) / eps_factor_param
```

(gebildet in `pfmfrac_function.py` aus der Bounding-Box des Netzes). Der Riss
wird über `epsilon` verschmiert; das Netz muss `epsilon` auflösen, sonst ist das
Ergebnis netzabhängig. Faustregel: **mindestens 2, besser 4 Elemente je
epsilon**.

Daraus folgt die Kopplung, die dieses Projekt bestimmt:

* Grobe Elemente ⇒ `epsilon` muss groß sein ⇒ **hoher Riegel**, nicht kleiner
  `eps_factor_param`.
* **⚠ `eps_factor_param` darf nie ≤ 8 sein.** Die Surfing-BC
  (`alex.boundaryconditions.get_boundary_of_box_as_function`) wird nur bei
  `|y − y_mid| ≥ 4·epsilon` aufgebracht; der Anteil der Höhe mit BC ist
  `1 − 8/eps_factor`. Mit 8 greift sie **nirgends** (freie Starrkörpermoden —
  genau das zeigte der erste 016-Lauf am 31.08.). 011/012 verwendeten 20
  (BC auf 60 % der Höhe); 016 steht seit dem 31.08. ebenfalls auf **20**.
* Ly folgt aus `Ly ≥ 2·h·eps_factor`: bei h = 400 µm und eps_factor 20 sind
  das 16 mm → `epsilon ≈ 0,84 mm` (inkl. Schale), 2,1 Elemente je epsilon in
  der Stufe `coarse`.

`create_fracture_config.py` schreibt `fracture_geometry_check.elements_per_epsilon`
und `surfing_bc_band_fraction` in jede Config, warnt unter 2 Elementen je
epsilon und **bricht bei `eps_factor ≤ 8` ab**; `job_run_simulation_CLUSTER.sh`
prüft beides beim Start noch einmal.

**Offener Punkt:** `epsilon ≈ 0,84 mm` ist größer als die Stegdicke des Schaums.
Der Riss wird damit über mehrere Stege verschmiert — das ist die bewusst in Kauf
genommene Folge der groben Auflösung. Siehe `CLAUDE_PROJECT_NOTES.md`, Abschnitt
„Offene Punkte".

---

## 5. Probengeometrie (entschieden)

Die Surfing-Randbedingungen setzen den Rissstart bei `x = 0,2·Lx` und lassen den
Riss nach `+x` laufen. Das Gebiet muss deshalb in x deutlich länger sein als in
y und z.

**Entscheidung (Stand 2026-08-31):** Riegel direkt aus dem `.leS`-Volumen
geschnitten — x voll (≈ 19,8 mm), **y = 16 mm**, z = 4 mm, mittig platziert;
außen eine 0,4-mm-Aluminiumschale (`02f`, wie 011) → Box ≈ 20,6 × 16,7 × 4,8 mm.
Die ursprünglichen 8 mm Höhe waren mit `eps_factor = 20` und 400-µm-Elementen
nicht vereinbar (Abschnitt 4). `Lx/Ly ≈ 1,2` ist deutlich kürzer als in 011
(4,9); die Risslauflänge von ≈ 16 mm entspricht 19 epsilon.

Anders als in 012: dort war das CT-Teilvolumen zu klein und wurde voxelseitig
zweimal in x gespiegelt (`4·Nx − 3`). Das `.leS`-Volumen ist groß genug, die
künstliche Symmetrie entfällt. Die Spiegel-Route (`02e`/`02f`/`11`) ist
mitkopiert und über `enabled` weiterhin zuschaltbar.

Steuerung: `LES_BAR_X_MM` / `LES_BAR_Y_MM` / `LES_BAR_Z_MM` in `config.sh`.

---

## 6. Auflösungsfamilie (entschieden)

Deutlich gröber als 015 (dort 75 µm bei reduce = 2). `MESH_TIERS` in `config.sh`:

| Stufe | reduce | Voxelgröße* | Elementgröße | Elemente je epsilon** |
|---|---:|---:|---:|---:|
| **coarse** (Default) | 8 | 133,6 µm | **400 µm** | 2,1 |
| medium | 4 | 66,8 µm | 267 µm | 3,1 |
| fine | 4 | 66,8 µm | 200 µm | 4,2 |

\* für JM-25-77 (16,7 µm/Voxel).
\** bei `Ly ≈ 16,7 mm` (inkl. Schale) und `eps_factor = 20`, also `epsilon ≈ 0,84 mm`.

Zum Vergleich: 011 rechnete mit Voxel 134 µm und `max_element_size_factor = 3,0`
= 402 µm (nicht 199 µm, wie früher notiert), epsilon 0,71 mm, ~1,8 Elemente je
epsilon — `coarse` ist also die 011-Auflösung. 015 rechnete mit 75 µm.
`epsilon` bleibt über alle drei Stufen gleich — die Familie ist damit eine
saubere Netzkonvergenzstudie und keine Variation der Physik.

`max_facet_distance = max_element_size / 3` wie in 011 (`LES_FACET_DISTANCE_RATIO`).
Die 015-Basis hätte 24 µm Facettenabstand unter 400-µm-Elementen ergeben.

**Randschale (seit 2026-08-31 wie 011): extern.** `02f_add_voxel_shell` fügt
außen `LES_SHELL_UM = 400 µm` Aluminium an (3 Voxel coarse, 6 Voxel medium/fine —
mindestens eine Elementgröße dick), der innere Seal aus 02d ist **aus**. Der
Seal hatte im ersten Lauf 1,2 / 1,9 / 1,2 mm Schaum je Seite überschrieben.
`04_scale_and_translate_mesh_mod.py` ist deshalb die **011-Version** (mit
`--npy`), die die Schale beim Positionieren herausrechnet; `10_snap_mesh_to_crop_boundary`
zieht Randknoten exakt auf die Box-Flächen. `LES_SHELL_MODE=seal` schaltet
auf die alte Variante zurück.

---

## 7. Ablauf auf dem Cluster

```bash
# 1. Configs erzeugen + nach $HPC_SCRATCH synchronisieren (Login-Node)
cd "$HOME/meshing/Meshing/pygalmesh"
data/scripts/016-Fracture-From-leS/02_create_folders_CLUSTER.sh

# 2. Netz + Simulation als abhängige Kette einreihen
"$HPC_SCRATCH/pygalmesh/data/scripts/016-Fracture-From-leS/submit_fracture_pipeline_CLUSTER.sh"
```

Einzeln geht auch:

```bash
sbatch job_generate_mesh_CLUSTER.sh  config-fracture-JM-25-77-coarse.json
sbatch job_run_simulation_CLUSTER.sh config-fracture-JM-25-77-coarse.json
```

**Beide Stufen müssen dieselbe Config bekommen**, sonst zeigt der Archivpfad
(`specimen/label/run_name`) ins Leere. Details: `LES_FRACTURE_PIPELINE.md`.

---

## 8. Offene Punkte

Siehe `CLAUDE_PROJECT_NOTES.md`, Abschnitt „Offene Punkte" — kurz:

- **Erster Lauf mit der korrigierten BC steht aus.** Prüfliste in
  `CLAUDE_PROJECT_NOTES.md` (Session 2026-08-31): uY muss antisymmetrisch in y
  sein, Schale außen, Tetraederzahl.
- **Elementgröße gegen Stegdicke prüfen.** 400 µm können dicker sein als die
  Stege. `evaluate_pore_size_distribution.py` liegt im Ordner und misst das.
- `02c` (scipy) und `03` (nanomesh/pygalmesh) sind lokal nicht lauffähig.
- **Apptainer sieht Host-Pfade unter `/work/scratch` nur über das cwd.** Die
  Runner machen deshalb `cd "$working_directory"` (aus 015 übernommen, in 016
  am 31.08. nachgezogen). Nie entfernen.
