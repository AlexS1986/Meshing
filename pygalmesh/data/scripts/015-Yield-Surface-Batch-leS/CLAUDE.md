# CLAUDE.md — 015-Yield-Surface-Batch-leS

Fließflächen-Erzeugung aus **bereits segmentierten Voxelbildern** (`.leS`).
Kopie von `014-Yield-Surface-From-leS` (das seinerseits die DICOM-freie
Abspaltung von `010-Yield-Surface-Generation` ist) mit einer zusätzlichen
Batch-Schicht.

**Studie dieses Ordners:** vier Datensätze (`JM-25-77`, `JM-25-71`, `JM-25-83`,
`JM-25-88`) × zwei Anfangsfließgrenzen (75 und 100 MPa) = acht Kombinationen,
je 96 Fließflächenpunkte. Ein vorbereitetes Netz je Datensatz, `reduce = 2`,
Punkt-Jobs mit `-t 3000` auf der Partition `long`.
**Bedienung: `README.md`. Entscheidungen: `CLAUDE_PROJECT_NOTES.md`.**

**Grundregel (Projektvorgabe):** Alles, was entschieden oder gelernt wird, wird
in einer `.md`-Datei dokumentiert — hier bzw. in `CLAUDE_PROJECT_NOTES.md`.

---

## 1. Ordnerstruktur und Container-Mapping

| Zweck | Pfad |
|---|---|
| dieses Projekt (Host, Mac) | `~/Work/Hypo/Hypo/Simulation/Meshing/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS/` |
| dieses Projekt (Cluster) | `$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS/` |
| dieses Projekt (Container) | `/data/scripts/015-Yield-Surface-Batch-leS/` |
| `.leS`-Quelldaten | `/data/resources/A01_segmented/` (Cluster: `$HPC_SCRATCH/pygalmesh/data/resources/A01_segmented/`) |
| Paper-/Publikationsordner | `~/Work/Hypo/Hypo/Publications/Folgepaper Homogenisierung von elasto-plastischen Eigenschaften/` |
| DolfinX-Module | `~/Work/Hypo/Hypo/Simulation/dolfinx_alex/shared/utils/alex/` |
| Vorgängerprojekt (DICOM-Pfad) | `.../scripts/010-Yield-Surface-Generation/` |

Der Container-Bind ist unverändert `Meshing/pygalmesh/data → /data`. In
JSON-Configs steht **immer der Container-Pfad** (`/data/...`), nie ein
unaufgelöstes `$HPC_SCRATCH`; die Cluster-Skripte rechnen das per
`${pfad/#\/data/$HPC_SCRATCH/pygalmesh/data}` auf den Host zurück.

### Dokumentation in diesem Ordner

- **`FILES.md`** — jede Datei mit Zweck, Aufrufer und Config-Abschnitt.
- **`LES_PIPELINE.md`** — Bedienung: Datenablage, Auflösung, Config, Cluster.
- `PIPELINE_ANNAHMEN_DICOM_TO_FEM.md` — Algorithmen, Parameter und Annahmen der
  gemeinsamen Kette ab Schritt 02b (Name aus 010 übernommen).
- **`README.md`** — Bedienung der Batch-Studie: erzeugen, einreichen, überwachen, einsammeln, zippen.
- `CLAUDE_PROJECT_NOTES.md` — Session-Protokoll, inklusive der Vorgeschichte aus 010.

---

## 2. Konventionen

1. **Vor dem Bauen lesen:** `FILES.md`, `LES_PIPELINE.md`, `CLAUDE_PROJECT_NOTES.md`.
2. **Skripte werden vorbereitet, nicht blind ausgeführt.** Rechenintensive Läufe
   startet der Nutzer selbst im Container bzw. auf dem Cluster; Ausnahme sind
   kleine Verifikationsläufe auf Teilausschnitten.
3. **Nummerierung** spiegelt die Pipeline-Reihenfolge; der `.leS`-Zweig nutzt `A0x`.
4. **Configs werden abgeleitet, nicht von Hand geschrieben:** `create_les_config.sh`
   (Variablen in `config.sh`) → `create_les_dataset_config.py` → `config-A01-les.json`.
   `config.json` ist eine Kopie davon und der Default ohne `--config`.
5. **Array-Konvention:** `uint8`, Form `(x, y, z)`, `z` ist die Slice-Achse.
6. **⚠ Phasenkonvention:** Vor Schritt 03 gilt im Array **1 = Pore, 0 = Aluminium**
   — entgegen der Benennung `material_value = 1`. Schritt 03 invertiert erneut, erst
   danach ist `material_mask == 1` das Aluminium; die Randschale aus 02d (Wert 0)
   ist darauf abgestimmt. In der `.leS`-Quelldatei ist es umgekehrt (1 = Material),
   deshalb invertiert `A01_les_2_npy.py` per Default. Details:
   `PIPELINE_ANNAHMEN_DICOM_TO_FEM.md` §3 und §9.1.
7. **Voxelgröße:** `A01_les_2_npy.py` schreibt sie als
   `metadata.json → 00_dicom2npy.SliceThickness` in **mm** (Voxelgröße × Reduktion);
   `03` und `04` lesen genau diesen Wert.
8. **Dokumentieren statt merken.**

---

## 3. Datensatz

`JM-25_77_85p55.leS` (2,5 GB): `1187 × 1188 × 886` Voxel bei 16,7 µm
= 19,8 × 19,8 × 14,8 mm, Porosität **85,551 %** (das `85p55` im Dateinamen).
Zeilenformat: `nx*ny` Zeilen mit je `nz` Werten, Zeilenindex `l = ix*ny + iy`
(C-Order), feste Zeilenbreite 1773 Byte. Belege für diese Interpretation stehen
in `LES_PIPELINE.md`.

---

## 4. Auflösung und Vernetzungsparameter (entschieden)

| reduce | Gitter | Voxel | Voxelgröße | |
|---:|---|---:|---|---|
| 1 | 1187 × 1188 × 886 | 1249 MVoxel | 16,7 µm | nur mit Crop |
| **2** | 593 × 594 × 443 | 156 MVoxel | 33,4 µm | **Default** |
| 4 | 296 × 297 × 221 | 19 MVoxel | 66,8 µm | |
| 8 | 148 × 148 × 110 | 2,4 MVoxel | 133,6 µm | ≈ Auflösung der alten `Bin4-reduce-2`-Studie |

- Blockwert per **Majority-Vote** über die Aluminiumphase; die relative Dichte
  verschiebt sich dabei um weniger als 0,15 Prozentpunkte.
- **Kein zusätzlicher Gauß auf den Labels.** Der Gauß in `03`
  (σ = `sigma_factor × SliceThickness`) ist bei mm-Voxelgrößen wirkungslos
  (σ ≈ 0,03 Voxel); wirksam ist `sdf_sigma_voxels = 1.0` auf dem
  Signed-Distance-Field. `sdf_sigma_voxels` nur zusammen mit `pad_width ≥ 3`
  erhöhen (gemessen: σ = 1,25 bei `pad_width = 1` erzeugt 7180 offene Kanten).
- **`pad_width = 3`** (statt 1) als Absicherung gegen abgeschnittene Isoflächen.
- **`keep_largest_component = true`** ist hier **Default**: im Datensatz stecken
  99,98 % des Aluminiums in einer Komponente, der Rest sind freischwebende Inseln
  (meist ≤ 10 Voxel), die im FE Starrkörpermoden erzeugen.
- `03` repariert punktuelle Oberflächendefekte selbst (doppelte Flächen,
  nicht-mannigfaltige Kanten) — siehe `LES_PIPELINE.md`.

---

## 5. Ablauf auf dem Cluster

```bash
# 1. Jobs erzeugen und nach $HPC_SCRATCH synchronisieren (Login-Node)
cd "$HOME/meshing/Meshing/pygalmesh"
YIELD_SURFACE_POINTS=192 data/scripts/015-Yield-Surface-Batch-leS/02_create_folders_CLUSTER.sh

# 2. Netzvorbereitung und alle Punkt-Jobs in einem Aufruf einreihen
"$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS/submit_les_pipeline_CLUSTER.sh"
```

Details, Optionen und Diagnose: `LES_PIPELINE.md`.

---

## 6. Offene Punkte

- **Auflösung für den Produktionslauf:** reduce=2 ist 4× feiner als die alte
  Studie bei größerem Gebiet — Vernetzung und FE werden entsprechend teuer
  (Elementgröße `max_cell_circumradius = 1,485 · dx`). Für Vergleichbarkeit mit
  der bestehenden Fließfläche wäre reduce=8 die passende Wahl.
- **Randschalendicken** (`x/z = 3`, `y = 12` Voxel) stammen aus der alten
  DICOM-Config und sind auf deren Voxelgröße abgestimmt; für 33,4 µm prüfen.
- **`02c`** läuft als reiner Report (`cleanup.enabled = false`). Falls die
  Oberfläche doch Probleme macht, wäre hier der Hebel für eine Voxel-Bereinigung.
