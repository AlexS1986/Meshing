# .leS-Pipeline (A01) — Standardpfad in 010-Yield-Surface-Generation

Alternative zum DICOM-Pfad: statt Rekonstruktion + Segmentierung aus DICOM wird
ein **bereits segmentiertes** Voxelbild im ASCII-Format `.leS` eingelesen.
Seit dieser Umstellung ist die .leS-Pipeline der **Default** in diesem Ordner;
der DICOM-Pfad bleibt über ein Config-Argument vollständig nutzbar.

## 1. Was ersetzt wird

| DICOM-Pfad | .leS-Pfad |
|---|---|
| `00_dicom_2_npy.py` | **`A01_les_2_npy.py`** |
| `01_segment_slice_wise.py` | entfällt (Daten sind segmentiert) |
| `02_build3D_segmented_array.py` | entfällt |
| `02a_rotate_pic_to_align_with_axis.py` | entfällt (Volumen ist achsparallel) |
| `02b`, `02c`, `02d`, `03`, `04`, `05`, `08`, `09` | **unverändert** |

`A01_les_2_npy.py` schreibt `segmented_3D_volume.npy` und zusätzlich die
Metadaten, die die Folgeschritte erwarten:

* `00_dicom2npy.SliceThickness` (Voxelgröße, Einheit **mm**) — gelesen von `03` und `04`
* `02a_rotate_pic_to_align_with_axis.py` mit `input_path`, `material_value`,
  `material_bounds` — gelesen von `02b`

## 2. ⚠ Phasenkonvention

Im Repository gilt in allen Arrays **vor** Schritt 03: **1 = Pore, 0 = Aluminium**
(`PIPELINE_ANNAHMEN_DICOM_TO_FEM.md`, Abschnitte 3 und 9.1). Schritt 03 wendet
ein zweites `invert_contrast()` an, erst danach ist `material_mask == 1` das
Aluminium; die Randschale aus 02d (Wert 0) ist genau darauf abgestimmt.

In der `.leS`-Quelldatei ist es **umgekehrt**: 1 = Material, 0 = void.
`A01_les_2_npy.py` invertiert deshalb per Default
(`phase_convention = "pipeline"`). Wird das umgestellt, vernetzt Schritt 03 den
**Porenraum** statt des Aluminiums.

Für Sichtprüfungen: `A02_preview_voxel_volume.py` erwartet per Default
`--material-value 0` (Pipeline-Konvention).

## 3. Ablage der Daten

Der Cluster-Bind ist unverändert `$HPC_SCRATCH/pygalmesh/data -> /data`.

```text
Host      : $HPC_SCRATCH/pygalmesh/data/resources/A01_segmented/JM-25-77*.leS
Container : /data/resources/A01_segmented/JM-25-77*.leS
```

In der Config steht **immer der Container-Pfad**; niemals ein unaufgelöstes
`$HPC_SCRATCH`. `A01_les_2_npy.py` akzeptiert als `input` eine Datei, einen
Ordner (dann muss genau eine `.leS`-Datei darin liegen) oder ein Glob-Muster.
Das Prepare-Jobskript prüft vor dem Start, dass die Datei auf dem Host existiert
und eindeutig ist.

Lokal (Mac/Container ohne Cluster) liegt derselbe Datensatz unter
`/data/scripts/010-Yield-Surface-Generation/A01_segmented/` — dieser Pfad wird
automatisch als Fallback durchsucht.

## 4. Auflösung reduzieren

`reduce = N` fasst N×N×N Voxel zu einem zusammen. Der Blockwert wird über die
**Aluminiumphase** bestimmt, Default `majority` (≥ 50 % der Untervoxel).

Quelle: 1187 × 1188 × 886 Voxel bei 16,7 µm ⇒ 19,8 × 19,8 × 14,8 mm,
Porosität 85,551 % (das `85p55` im Dateinamen).

| reduce | Gitter | Voxel | Voxelgröße | Bemerkung |
|---:|---|---:|---|---|
| 1 | 1187 × 1188 × 886 | 1249 MVoxel | 16,7 µm | nur mit Crop sinnvoll (1,25 GB `.npy`) |
| **2** | 593 × 594 × 443 | **156 MVoxel** | 33,4 µm | **Default** — 4× feiner als die bisherige Studie |
| 4 | 296 × 297 × 221 | 19 MVoxel | 66,8 µm | |
| 8 | 148 × 148 × 110 | 2,4 MVoxel | 133,6 µm | ≈ Auflösung der bisherigen `Bin4-reduce-2`-Studie (0,1339 mm) |

**Rechenaufwand beachten:** Die Elementgröße im Netz ist an die Voxelgröße
gekoppelt (`max_cell_circumradius = 1,485 · dx`). reduce=2 bedeutet gegenüber
der bisherigen Studie eine 4× feinere Auflösung bei gleichzeitig größerem
Gebiet — Vernetzung und FE-Lauf werden entsprechend teuer. Wenn die neue
Fließfläche mit der bestehenden vergleichbar sein soll, ist **reduce=8** die
passende Wahl; reduce=2 ist eine Auflösungsstudie.

Gemessene Auswirkung der Reduktion auf die relative Dichte (Majority-Vote):
reduce=4 −0,08 Prozentpunkte, reduce=8 −0,13 Prozentpunkte — die Phasenanteile
bleiben also praktisch erhalten.

Ein zusätzlicher Gauß-Filter auf den Labels ist **nicht** vorgesehen: der
Majority-Vote ist bereits ein Boxfilter mit 0,5-Schwelle, und die
Oberflächenglättung passiert in Schritt 03 über `sdf_sigma_voxels` (Default 1,0).
Für Experimente bei großen reduce-Faktoren gibt es `reduce.smooth_sigma`
(Gauß auf dem Belegungsanteil im reduzierten Gitter, Default 0 = aus).

## 5. Config erzeugen

Die Default-Config `config-A01-les.json` ist eingecheckt. Neu erzeugen:

```bash
cd "$HPC_SCRATCH/pygalmesh/data/scripts/010-Yield-Surface-Generation"

# Variante A: über die LES_*-Variablen in config.sh
./create_les_config.sh

# Variante B: direkt, mit abweichenden Werten
python3 create_les_dataset_config.py \
  --base-config config-Bin4-reduce-2.json \
  --output config-A01-les-r8.json \
  --dataset-id JM-25-77_A01_les_r8 \
  --les-input /data/resources/A01_segmented \
  --reduce 8
```

Die Config wird aus einer bestehenden, validierten DICOM-Config **abgeleitet**,
damit Vernetzungs-, Randschalen- und Fließflächenparameter identisch bleiben.
Einzelwerte lassen sich überschreiben:

```bash
  --set '02b_build_subvolume_arrays.xy_divisions=2' \
  --set '02d_axis_aligned_cuboid_crop.boundary_seal.thicknesses.y_min=6'
```

Ausschnitt statt ganzem Volumen:

```bash
  --x-range 300 900 --y-range 300 900 --z-range 100 700
```

(Die Ausschnittsgrenzen beziehen sich auf das **Originalgitter** vor der
Reduktion und werden automatisch auf Vielfache von `reduce` gekürzt.)

## 6. Auf dem Cluster laufen lassen

```bash
# 1. Daten und Projekt nach $HPC_SCRATCH synchronisieren, dann:
sbatch "$HPC_SCRATCH/pygalmesh/data/scripts/010-Yield-Surface-Generation/job_prepare_mesh_CLUSTER.sh"
#    ^ ohne Argument = config-A01-les.json (neuer Default)

# alternativ explizit:
sbatch ".../job_prepare_mesh_CLUSTER.sh" config-A01-les-r8.json

# zurück auf den DICOM-Pfad:
sbatch ".../job_prepare_mesh_CLUSTER.sh" config-Bin4-reduce-2.json
```

Das Prepare-Skript (`job_prepare_mesh_Bin4_reduce_2_CLUSTER.sh`, wird vom
Wrapper aufgerufen) entscheidet anhand von `A01_les_2_npy.enabled` in der
Config, ob es `A01_les_2_npy.py` oder die DICOM-Kette `00/01/02/02a` ausführt.
Danach ist der Ablauf für beide Quellen identisch.

Fließflächen-Jobs (Default-Basisconfig ist jetzt ebenfalls `config-A01-les.json`):

```bash
./setup_yield_surface_jobs.sh 192
# oder mit anderer Basis:
YIELD_SURFACE_BASE_CONFIG=config-A01-les-r8.json \
YIELD_SURFACE_OUTPUT_DIR=yield_surface_jobs/JM-25-77_A01_les_r8/n192 \
./setup_yield_surface_jobs.sh 192

bash yield_surface_jobs/n192/submit_all_yield_surface_points.sh
```

## 7. Sichtprüfung

```bash
python3 A02_preview_voxel_volume.py \
  --npy .../JM-25-77_A01_les_segmented_3D/segmented_3D_volume.npy \
  --metadata .../JM-25-77_A01_les_segmented/metadata.json \
  --preview-reduce 2
```

Erzeugt `*_slices.png` (drei orthogonale Schnitte) und `*_3d.png`
(zwei Schrägansichten, reiner numpy/scipy/matplotlib-Renderer ohne VTK).

## 8. Verifikationsstand

* Format: Dateigröße geht exakt auf (`27 + 1 410 156 × 1773` Byte), Ausschnitt
  `x[600:602]` ist bitgleich mit den Rohzeilen.
* Zeilenordnung C: Übergangsdichte 0,94 / 0,96 / 1,00 % in x/y/z — bei falscher
  Ordnung wären ~21 % zu erwarten.
* Globale Porosität 85,551 % = `85p55` aus dem Dateinamen.
* Unit-Tests gegen synthetische `.leS`-Dateien: Phasenkonvention, reduce-Modi
  (majority/threshold/any/all, r = 2 und 3), Crop-Kürzung, F-Order, viele
  Puffergrößen, Config-Modus, `bounds_mode`, `--smooth-sigma`.
* End-to-End auf den echten Daten (lokal, reduce=8): `A01 → 02b → 02d` liefert
  `subvolume_x0_y0/volume.npy` (148 × 148 × 110) und eine geschlossene
  Randschale aus Aluminium — identisches Verhalten wie im DICOM-Pfad.
* Noch offen: `02c` (braucht scipy) und `03` (braucht nanomesh/pygalmesh) sind
  lokal nicht lauffähig und wurden nur über die Konfiguration geprüft, nicht
  ausgeführt.
