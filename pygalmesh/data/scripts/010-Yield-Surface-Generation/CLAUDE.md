# CLAUDE.md — Folgepaper: Homogenisierung von elasto-plastischen Eigenschaften

Diese Datei beschreibt, **wie in diesem Projekt gearbeitet wird**: wo welche
Daten und Skripte liegen, welche Konventionen gelten und was bereits entschieden
wurde. Sie ist die erste Datei, die in einer neuen Session gelesen werden soll.

**Grundregel (Projektvorgabe):** Alles, was entschieden oder gelernt wird, wird
in einer `.md`-Datei dokumentiert — projektübergreifend hier, code-nah in
`CLAUDE_PROJECT_NOTES.md` im jeweiligen Skriptordner.

---

## 1. Ordnerstruktur

| Zweck | Pfad (macOS) |
|---|---|
| Paper-/Publikationsordner (dieser Ordner) | `~/Work/Hypo/Hypo/Publications/Folgepaper Homogenisierung von elasto-plastischen Eigenschaften/` |
| **Pipeline- und Simulationsordner (Arbeitspferd)** | `~/Work/Hypo/Hypo/Simulation/Meshing/pygalmesh/data/scripts/010-Yield-Surface-Generation/` |
| Simulations-Root | `~/Work/Hypo/Hypo/Simulation` |
| CT-Rohdaten / segmentierte Volumen | `~/Work/Hypo/Hypo/Simulation/Meshing/pygalmesh/data/resources/` |
| DolfinX-Module | `~/Work/Hypo/Hypo/Simulation/dolfinx_alex/shared/utils/alex/` |

### Container- und Cluster-Mapping

Alle Skripte laufen im Container. Dort ist `Meshing/pygalmesh/data` als `/data`
eingehängt:

```text
Host (Mac)     : .../Meshing/pygalmesh/data/scripts/010-Yield-Surface-Generation/
Host (Cluster) : $HPC_SCRATCH/pygalmesh/data/scripts/010-Yield-Surface-Generation/
Container      : /data/scripts/010-Yield-Surface-Generation/
```

In JSON-Configs steht **immer der Container-Pfad** (`/data/...`), nie ein
unaufgelöstes `$HPC_SCRATCH`. Die Cluster-Skripte rechnen `/data` per
`${pfad/#\/data/$HPC_SCRATCH/pygalmesh/data}` auf den Host zurück.

### Wichtige Dokumentationsdateien im Pipeline-Ordner

- `CLAUDE_PROJECT_NOTES.md` — laufendes Session-Protokoll.
- `PIPELINE_ANNAHMEN_DICOM_TO_FEM.md` — vollständige Beschreibung DICOM →
  segmentiertes Array → FEM-Netz inkl. aller Algorithmen und Annahmen.
- **`LES_PIPELINE.md`** — Bedienung der .leS-Pipeline (Default-Pfad, Cluster).
- **`FILES.md`** — Dateiverzeichnis: jede Datei mit Zweck, Aufrufer und
  Config-Abschnitt; listet auch, was in `_archive/` liegt und warum.
- `README.md` — Yield-Surface-Jobs auf dem Cluster (SLURM).
- `SCAN_DATASET_WORKFLOW.md` — DICOM-Workflow für weitere Scans.

---

## 2. Arbeitsweise / Konventionen

1. **Vor dem Bauen lesen:** `CLAUDE_PROJECT_NOTES.md`, `LES_PIPELINE.md` und
   `PIPELINE_ANNAHMEN_DICOM_TO_FEM.md`.
2. **Skripte werden vorbereitet, nicht blind ausgeführt.** Rechenintensive
   Läufe (Konvertierung des vollen Volumens, Vernetzung, FEM) startet der Nutzer
   selbst im Container bzw. auf dem Cluster. Ausnahme: kleine Verifikationsläufe
   auf Teilausschnitten.
3. **Nummerierung der Skripte** spiegelt die Pipeline-Reihenfolge wider.
   Der .leS-Zweig verwendet das Präfix `A0x`.
4. **Konfiguration über JSON-Configs** im Pipeline-Ordner; Skripte akzeptieren
   `--config` und meist zusätzlich explizite Pfad-Argumente. `config.json` ist
   die Default-Config ohne `--config` und ist eine Kopie von
   `config-A01-les.json`; der DICOM-Pfad braucht explizit
   `--config config-Bin4-reduce-2.json`. Neue Configs werden
   aus einer bestehenden, validierten Config **abgeleitet**
   (`create_les_dataset_config.py`, `create_scan_dataset_config.py`), nicht von
   Hand geschrieben.
5. **Array-Konvention:** `uint8`-Arrays der Form `(x, y, z)`, `z` ist die
   Slice-Achse.
6. **⚠ Phasenkonvention:** Vor Schritt 03 gilt im Array **1 = Pore,
   0 = Aluminium** — entgegen der Benennung `material_value = 1` in den Configs.
   Schritt 03 invertiert erneut (`invert_contrast()`), erst danach ist
   `material_mask == 1` das Aluminium; die Randschale aus 02d (Wert 0) ist genau
   darauf abgestimmt. Details: `PIPELINE_ANNAHMEN_DICOM_TO_FEM.md` §3 und §9.1.
7. **Voxelgröße** wird aus `metadata.json → 00_dicom2npy.SliceThickness`
   gelesen (Einheit **mm**, DICOM-Herkunft). `A01_les_2_npy.py` schreibt diesen
   Wert für den .leS-Pfad selbst (Voxelgröße × Reduktionsfaktor).
8. **Dokumentieren statt merken:** nach jeder Session Erkenntnisse hier bzw. in
   `CLAUDE_PROJECT_NOTES.md` festhalten.

---

## 3. Datenquelle .leS (Default-Pfad)

Bereits segmentierte Voxelbilder im ASCII-Format `.leS`.

```text
Cluster  : $HPC_SCRATCH/pygalmesh/data/resources/A01_segmented/JM-25-77*.leS
Container: /data/resources/A01_segmented/
lokal    : /data/scripts/010-Yield-Surface-Generation/A01_segmented/
```

Aktueller Datensatz `JM-25_77_85p55.leS` (2,5 GB):

- Header `nx ny nz voxel_size` = `1187 1188 886 1.670000e-05`
  → 1 249 398 216 Voxel, 16,7 µm isotrop, 19,8 × 19,8 × 14,8 mm.
- Danach genau `nx*ny` Zeilen mit je `nz` Werten (Voxelsäulen entlang z),
  Zeilenindex `l = ix*ny + iy` (**C-Order**), feste Zeilenbreite 1773 Byte.
- Labels in der Quelldatei: **1 = Material, 0 = void** — also invertiert
  gegenüber der Pipeline-Konvention (siehe §2.6).
- Globale Porosität **85,551 %** = das `85p55` im Dateinamen.

**Belege für die Interpretation:** Dateigröße geht exakt auf
(`27 + 1 410 156 × 1773` Byte); Ausschnitt `x[600:602]` ist bitgleich mit den
Rohzeilen; Übergangsdichte 0,94 / 0,96 / 1,00 % in x/y/z (bei falscher
Zeilenordnung wären ~21 % zu erwarten).

---

## 4. Skripte des .leS-Zweigs

### `A01_les_2_npy.py`

Ersetzt `00_dicom_2_npy.py`, `01_segment_slice_wise.py`,
`02_build3D_segmented_array.py` und `02a_rotate_pic_to_align_with_axis.py`.
Schreibt `segmented_3D_volume.npy` (uint8, Pipeline-Konvention) und die
Metadaten, die `02b` (`02a_...`-Eintrag mit `material_bounds`) und `03`/`04`
(`00_dicom2npy.SliceThickness`) erwarten.

```bash
python3 A01_les_2_npy.py --config config-A01-les.json
python3 A01_les_2_npy.py --input /data/resources/A01_segmented --output /tmp/v.npy --reduce 4
```

Wichtige Optionen: `--reduce N` (+ `--reduce-mode majority|threshold|any|all`,
`--reduce-threshold`, `--smooth-sigma`), `--x/y/z-range`, `--line-order C|F`,
`--phase-convention pipeline|raw`, `--bounds-mode full|material`, `--dry-run`.

Speicher: Streaming über `np.lib.format.open_memmap`, RAM-Bedarf konstant
(~64 MB) unabhängig von der Volumengröße. Volle Datei in ~9 s gelesen.

### `A02_preview_voxel_volume.py`

Sichtprüfung eines beliebigen Voxelvolumens: drei orthogonale Schnitte und zwei
Schrägansichten (First-Hit-Tiefenpuffer + Lambert-Shading, nur
numpy/scipy/matplotlib, kein VTK/OpenGL). Default `--material-value 0`
(Pipeline-Konvention).

### `create_les_dataset_config.py` / `create_les_config.sh`

Erzeugen `config-A01-les.json` aus einer bestehenden DICOM-Config, damit
Vernetzungs-, Randschalen- und Fließflächenparameter identisch bleiben.
Steuervariablen: der `LES_*`-Block am Ende von `config.sh`.

---

## 5. Cluster: die .leS-Pipeline ist Default

- `job_prepare_mesh_CLUSTER.sh` ohne Argument verwendet **`config-A01-les.json`**.
- `job_prepare_mesh_Bin4_reduce_2_CLUSTER.sh` (wird vom Wrapper aufgerufen)
  entscheidet anhand von `A01_les_2_npy.enabled` in der Config, ob `A01` oder die
  DICOM-Kette `00/01/02/02a` läuft; ab `02b` ist der Ablauf identisch.
- `setup_yield_surface_jobs.sh` verwendet ebenfalls `config-A01-les.json` als
  Basisconfig (überschreibbar über `YIELD_SURFACE_BASE_CONFIG`).
- Zurück auf DICOM: `sbatch job_prepare_mesh_CLUSTER.sh config-Bin4-reduce-2.json`.

Details, Reduktionstabelle und Kommandos: **`LES_PIPELINE.md`**.

---

## 6. Auflösung (entschieden)

`reduce = N` fasst N×N×N Voxel zusammen, Blockwert per Majority-Vote über die
Aluminiumphase.

| reduce | Gitter | Voxel | Voxelgröße | |
|---:|---|---:|---|---|
| 1 | 1187 × 1188 × 886 | 1249 MVoxel | 16,7 µm | nur mit Crop |
| **2** | 593 × 594 × 443 | 156 MVoxel | 33,4 µm | **Default-Config** |
| 4 | 296 × 297 × 221 | 19 MVoxel | 66,8 µm | |
| 8 | 148 × 148 × 110 | 2,4 MVoxel | 133,6 µm | ≈ bisherige `Bin4-reduce-2`-Studie (0,1339 mm) |

Die Reduktion verschiebt die relative Dichte kaum (reduce=4: −0,08 pp,
reduce=8: −0,13 pp).

**Kein zusätzlicher Gauß-Filter auf den Labels.** Begründung: der Gauß in
`01`/`03` hat σ = `sigma_factor × SliceThickness` und ist bei mm-Voxelgrößen
faktisch wirkungslos (σ ≈ 0,03 Voxel); die wirksame Glättung ist
`sdf_sigma_voxels = 1.0` auf dem Signed-Distance-Field in Schritt 03. Labels zu
verwaschen würde die relative Dichte verschieben und dünne Stege abschnüren.
Für Experimente existiert `reduce.smooth_sigma` (Default 0 = aus).

---

## 7. Offene Punkte

- **Auflösung für den Produktionslauf festlegen:** reduce=2 ist 4× feiner als
  die bestehende Studie bei gleichzeitig größerem Gebiet — Vernetzung und FE
  werden entsprechend teuer (Elementgröße ist über
  `max_cell_circumradius = 1,485 · dx` an die Voxelgröße gekoppelt). Für
  Vergleichbarkeit mit der bestehenden Fließfläche wäre reduce=8 die passende
  Wahl.
- `02c` (scipy) und `03` (nanomesh/pygalmesh) sind lokal nicht lauffähig und
  bisher nur konfigurativ geprüft, nicht ausgeführt.
- Randschalendicken aus der DICOM-Config (`y = 12` Voxel gegenüber `x/z = 3`)
  sind auf die alte Voxelgröße abgestimmt und sollten für den .leS-Datensatz
  überprüft werden.
- Prüfen, ob `A01_segmented/` (2,5 GB) mit auf den Cluster synchronisiert wird
  oder nur die konvertierte `.npy`.
