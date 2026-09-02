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
* Ly folgt aus `Ly ≥ 2·h·eps_factor`. Seit 2026-09-02 ist Ly die ganze
  Probenhöhe (20,64 mm inkl. Schale) → `epsilon = 1,03 mm`; mit 200-µm-
  Elementen sind das 5,2 Elemente je epsilon.

`create_fracture_config.py` schreibt `fracture_geometry_check.elements_per_epsilon`
und `surfing_bc_band_fraction` in jede Config, warnt unter 2 Elementen je
epsilon und **bricht bei `eps_factor ≤ 8` ab**; `job_run_simulation_CLUSTER.sh`
prüft beides beim Start noch einmal.

**Offener Punkt:** `epsilon ≈ 1,03 mm` ist größer als die Stegdicke des Schaums.
Der Riss wird damit über mehrere Stege verschmiert — das ist die bewusst in Kauf
genommene Folge der groben Auflösung. Siehe `CLAUDE_PROJECT_NOTES.md`, Abschnitt
„Offene Punkte".

---

## 5. Probengeometrie (entschieden, Stand 2026-09-02)

Die Surfing-Randbedingungen setzen den Rissstart bei `x = 0,2·Lx` und lassen den
Riss nach `+x` laufen. Das Gebiet muss deshalb in x deutlich länger sein als in
y und z.

**Entscheidung (Nutzer, 2026-09-02): kein Ausschnitt.** Die **ganze Probe**
(JM-25-77: 19,8 × 19,8 × 14,8 mm) wird modelliert, als Voxelvolumen **einmal in
x gespiegelt** (`02e`, `2·Nx − 1`, Spiegelkopie an `x_min`) und außen in eine
**homogene Aluminiumschale** eingebettet (`02f`: 0,4 mm in y/z, **4 mm
Endblöcke in x** wie 011). Ergebnis: Schaum 39,5 × 19,8 × 14,8 mm, Box
≈ 47,5 × 20,6 × 15,6 mm, `Lx/Ly = 2,3`, Kerbspitze bei 9,5 mm (5,5 mm im
Schaum), Risslauf ≈ 35 epsilon. Die Spiegelebene liegt bei x ≈ 23,7 mm.

Das ist die Route aus 011/012 (dort `4·Nx − 3`, weil das CT-Teilvolumen klein
war). Der Riegel-Ausschnitt der Session 2026-08-31 (x voll, y = 16, z = 4 mm)
bleibt über `LES_BAR_Y_MM`/`LES_BAR_Z_MM` verfügbar; zweimal spiegeln über
`LES_MIRROR_X_REPETITIONS = 2`.

Steuerung in `config.sh`: `LES_BAR_X/Y/Z_MM` (leer = ganze Achse),
`LES_MIRROR_X_REPETITIONS`, `LES_SHELL_UM` (y/z), `LES_SHELL_X_UM` (Endblöcke).

---

## 6. Auflösungsfamilie (entschieden, Stand 2026-09-02)

**Alle Stufen auf `reduce = 4`** (66,8 µm Voxel). `reduce = 8` hatte per
Majority-Vote Stege unter ~70 µm gelöscht, bevor überhaupt vernetzt wurde —
das war der eigentliche Grund für „zu grob", nicht die Elementgröße.
`MESH_TIERS` in `config.sh`:

| Stufe | reduce | Voxelgröße* | Elementgröße | Elemente je epsilon** | Tets (Schätzung) |
|---|---:|---:|---:|---:|---:|
| coarse | 4 | 66,8 µm | 250 µm | 4,1 | ~2,5 Mio |
| **medium** (Default) | 4 | 66,8 µm | **200 µm** | 5,2 | ~5 Mio |
| fine | 4 | 66,8 µm | 150 µm | 6,9 | ~12 Mio — Speicher prüfen |

\* für JM-25-77 (16,7 µm/Voxel).
\** bei `Ly = 20,64 mm` (inkl. Schale) und `eps_factor = 20`, also `epsilon = 1,03 mm`.

`epsilon` ist über alle Stufen gleich — die Familie ist eine Netzkonvergenz-
studie. Rund die Hälfte der Elemente sitzt in der massiven Schale (Endblöcke).
Zum Vergleich: 011 rechnete mit 134-µm-Voxeln und 402-µm-Elementen
(~1,8 Elemente je epsilon); die 016-Familie bis 2026-09-02 war 400/267/200 µm
auf einem 16 × 4-mm-Riegel.

`max_facet_distance = max_element_size / 3` wie in 011 (`LES_FACET_DISTANCE_RATIO`).

**Randschale (wie 011): extern.** `02f_add_voxel_shell` fügt außen Aluminium an
(Wert 0): `LES_SHELL_UM = 400` in y/z (6 Voxel bei reduce 4), `LES_SHELL_X_UM =
4000` an den x-Enden (60 Voxel). Der innere Seal aus 02d ist **aus**.
`04_scale_and_translate_mesh_mod.py` ist die **011-Version** (mit `--npy`), die
Spiegelung und Schale beim Positionieren herausrechnet; `10_snap_mesh_to_crop_boundary`
zieht Randknoten exakt auf die Box-Flächen. `LES_SHELL_MODE=seal` schaltet auf
die alte Variante zurück.

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
- **Elementgröße gegen Stegdicke prüfen.** Bei 200 µm sind dünne Stege ein
  Element dick. `evaluate_pore_size_distribution.py` liegt im Ordner und misst das.
- `02c` (scipy) und `03` (nanomesh/pygalmesh) sind lokal nicht lauffähig.
- **Apptainer sieht Host-Pfade unter `/work/scratch` nur über das cwd.** Die
  Runner machen deshalb `cd "$working_directory"` (aus 015 übernommen, in 016
  am 31.08. nachgezogen). Nie entfernen.
