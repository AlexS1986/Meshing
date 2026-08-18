# CLAUDE.md — Folgepaper: Homogenisierung von elasto-plastischen Eigenschaften

Diese Datei beschreibt, **wie in diesem Projekt gearbeitet wird**: wo welche
Daten und Skripte liegen, welche Konventionen gelten und was bereits entschieden
wurde. Sie ist die erste Datei, die in einer neuen Session gelesen werden soll.

**Grundregel (Projektvorgabe):** Alles, was entschieden oder gelernt wird, wird
in einer `.md`-Datei dokumentiert — Projekt-übergreifend hier, code-nah in
`CLAUDE_PROJECT_NOTES.md` im jeweiligen Skriptordner.

---

## 1. Ordnerstruktur

| Zweck | Pfad (macOS) |
|---|---|
| Paper-/Publikationsordner (dieser Ordner) | `~/Work/Hypo/Hypo/Publications/Folgepaper Homogenisierung von elasto-plastischen Eigenschaften/` |
| **Pipeline- und Simulationsordner (Arbeitspferd)** | `~/Work/Hypo/Hypo/Simulation/Meshing/pygalmesh/data/scripts/010-Yield-Surface-Generation/` |
| Simulations-Root | `~/Work/Hypo/Hypo/Simulation` |
| CT-Rohdaten | `~/Work/Hypo/Hypo/Simulation/Meshing/pygalmesh/data/resources/` |
| DolfinX-Module | `~/Work/Hypo/Hypo/Simulation/dolfinx_alex/shared/utils/alex/` |

### Container-Mapping

Die Pipeline läuft in einem Container. Dort ist
`Meshing/pygalmesh/data` als `/data` eingehängt:

```text
Host: .../Meshing/pygalmesh/data/scripts/010-Yield-Surface-Generation/
Container: /data/scripts/010-Yield-Surface-Generation/
```

**Alle Skripte werden im Container ausgeführt** und verwenden deshalb
`/data/...`-Pfade als Defaults. Auf dem Cluster liegt derselbe Ordner unter
`$HOME/meshing/Meshing/pygalmesh/data/scripts/010-Yield-Surface-Generation`.

### Wichtige Dokumentationsdateien im Pipeline-Ordner

- `CLAUDE_PROJECT_NOTES.md` — laufendes Session-Protokoll: was verstanden,
  entschieden und gebaut wurde.
- `PIPELINE_ANNAHMEN_DICOM_TO_FEM.md` — vollständige Beschreibung DICOM →
  segmentiertes Array → FEM-Netz inkl. aller Algorithmen und Annahmen.
- `README.md` — Bedienung der Yield-Surface-Jobs (Cluster, SLURM).
- `SCAN_DATASET_WORKFLOW.md` — Workflow für neue Scans.

---

## 2. Arbeitsweise / Konventionen

1. **Vor dem Bauen lesen:** `CLAUDE_PROJECT_NOTES.md` und
   `PIPELINE_ANNAHMEN_DICOM_TO_FEM.md` im Pipeline-Ordner.
2. **Skripte werden nur vorbereitet, nicht blind ausgeführt.** Rechenintensive
   Läufe (Konvertierung, Vernetzung, FEM) startet der Nutzer selbst im
   Container bzw. auf dem Cluster. Ausnahme: kleine Verifikationsläufe auf
   Teilausschnitten.
3. **Nummerierung der Skripte** spiegelt die Pipeline-Reihenfolge wider
   (`00_dicom_2_npy.py`, `01_...`, `02_...`, `03_mesh_3D_array_pygalmesh.py`, …).
   Neue Datenquellen bekommen ein eigenes Präfix (`A01_…` für den .leS-Pfad).
4. **Konfiguration über `config.json`** im Pipeline-Ordner; Skripte akzeptieren
   `--config` und meist zusätzlich explizite Pfad-Argumente.
5. **Array-Konvention:** Volumen sind `uint8`-Arrays der Form `(x, y, z)`,
   `0` = void/Pore, `1` = Material; `z` ist die Slice-Achse.
   `03_mesh_3D_array_pygalmesh.py --npy <datei>` erwartet genau das.
6. **Voxelgröße** wird in der Pipeline aus
   `metadata.json → 00_dicom2npy.SliceThickness` gelesen (DICOM-Herkunft,
   daher üblicherweise in **mm**). Bei nicht-DICOM-Quellen muss dieser Wert
   passend geschrieben werden.
7. **Dokumentieren statt merken:** Nach jeder Session die Erkenntnisse in
   dieser Datei bzw. in `CLAUDE_PROJECT_NOTES.md` festhalten.

---

## 3. Datenquelle .leS (segmentiertes Voxelbild)

Neben dem DICOM-Pfad gibt es jetzt eine zweite Quelle: bereits segmentierte
Voxelbilder im ASCII-Format `.leS`.

**Ablageort:** `.../010-Yield-Surface-Generation/A01_segmented/`
(im Container `/data/scripts/010-Yield-Surface-Generation/A01_segmented/`).

Aktueller Datensatz: `JM-25_77_85p55.leS` (2,5 GB).

### Format (durch Analyse verifiziert)

```text
Zeile 1: nx ny nz voxel_size        z.B.  1187 1188 886 1.670000e-05
Zeile 2..nx*ny+1: je nz Labelwerte, durch Leerzeichen getrennt
```

- `nx=1187, ny=1188, nz=886` → 1 249 398 216 Voxel (1,25 GB als `uint8`).
- `voxel_size = 1.67e-05 m = 16,7 µm`, isotrop.
- Labels: `0` = void/Pore, `1` = Material.
- Es gibt **genau `nx*ny` Datenzeilen**; jede Zeile ist eine Voxelsäule entlang
  `z`. Zeilenindex `l = ix*ny + iy` (**C-Order**).
- Jede Zeile ist byte-identisch lang (`2*nz + 1 = 1773` Bytes: einstelliges
  Label + Leerzeichen je Wert, abschließendes Leerzeichen + `\n`).
  Rechnung: `27 + 1 410 156 * 1773 = 2 500 206 615` Bytes = exakte Dateigröße.

### Belege für die C-Order-Annahme

- Übergangsdichte (Anteil benachbarter Voxel mit unterschiedlichem Label) in
  einem Testausschnitt: **0,94 % (x), 0,96 % (y), 1,00 % (z)** — bei falscher
  Zeilenordnung wäre eine Achse ~21 % (Zufallswert `2p(1-p)`). Die
  Rekonstruktion ist also in allen drei Richtungen räumlich zusammenhängend.
- Materialanteil über Stichproben-Slabs: 11,6 – 17,2 %, im Mittel ≈ 15 %
  → Porosität ≈ 85 %, konsistent mit dem `85p55` im Dateinamen (85,55 %
  Porosität).

---

## 4. Skript `A01_les_2_npy.py`

Liegt in `.../010-Yield-Surface-Generation/A01_les_2_npy.py` und konvertiert
`.leS` → `volume.npy` (uint8, `(x, y, z)`), direkt verwendbar mit
`03_mesh_3D_array_pygalmesh.py --npy volume.npy`.

**Aufruf im Container (Defaults zeigen bereits auf `A01_segmented/`):**

```bash
python3 /data/scripts/010-Yield-Surface-Generation/A01_les_2_npy.py
```

**Nützliche Optionen**

| Option | Bedeutung |
|---|---|
| `--input` / `--output` | Pfade (Default: `A01_segmented/JM-25_77_85p55.leS` → `A01_segmented/volume.npy`) |
| `--x-range A B`, `--y-range`, `--z-range` | Teilvolumen direkt beim Einlesen ausschneiden (halboffen, 0-basiert) |
| `--dry-run` | Nur Header/Layout prüfen, nichts schreiben |
| `--line-order {C,F}` | Zeilenordnung umschalten, falls ein Datensatz `l = iy*nx + ix` verwendet |
| `--material-value` | Labelwert des Materials für die Statistik (Default `1`) |
| `--pipeline-metadata PFAD --pipeline-unit {m,mm,um}` | schreibt die Voxelgröße als `00_dicom2npy.SliceThickness` in eine `metadata.json` (Default-Einheit `mm`) |
| `--force-generic`, `--chunk-mb`, `--lines-per-block` | Parser-/Puffersteuerung |

**Eigenschaften**

- Streamt blockweise und schreibt über `np.lib.format.open_memmap` direkt auf
  die Platte → RAM-Bedarf konstant (~64 MB), unabhängig von der Volumengröße.
- Zwei Parser: Fast-Path (feste Zeilenbreite, einstellige Labels, Bytes werden
  direkt in `uint8` umgerechnet) und generischer Fallback (`split()`), der
  automatisch greift, wenn der Fast-Path nicht anwendbar ist.
- Schreibt eine Sidecar-JSON (`volume.json`) mit Shape, Voxelgröße (m/mm/µm),
  Crop, Labelhistogramm, Materialanteil und Porosität.

**Verifikation (bereits durchgeführt)**

- Unit-Tests gegen synthetische `.leS`-Dateien: C-/F-Order, mit und ohne
  abschließendes Leerzeichen, mehrstellige Labels, Crop in allen drei Achsen,
  viele Blockgrößen (Carry-Logik über Blockgrenzen), Metadaten — alle bestanden.
- Realdaten-Gegenprobe: Ausschnitt `x[600:602]` aus dem Skript ist **bitgleich**
  mit den entsprechenden Rohzeilen (`sed` + `np.loadtxt`).

---

## 5. Praktische Hinweise zur Größe

Das volle Volumen hat 1,25 GVoxel → `volume.npy` ist **1,25 GB**. Für Vernetzung
und FEM ist das zu groß; sinnvoll ist ein Ausschnitt direkt beim Konvertieren,
z. B.

```bash
python3 A01_les_2_npy.py --x-range 400 800 --y-range 400 800 --z-range 200 600 \
    --output /data/scripts/010-Yield-Surface-Generation/A01_segmented/volume_400.npy
```

Die weitere Verarbeitung (Rotation, Subvolumen, Topologie-Cleanup, Randabdichtung)
übernehmen wie gehabt `02a_…`, `02b_…`, `02c_…`, `02d_…` aus dem Pipeline-Ordner.

---

## 6. Offene Punkte

- **Einheit der Voxelgröße in der Pipeline** klären: `load_original_voxel_size()`
  in `03_mesh_3D_array_pygalmesh.py` liest `00_dicom2npy.SliceThickness` aus der
  `metadata.json`. Für den `.leS`-Datensatz muss dort `1.67e-05 m` in derselben
  Einheit stehen wie bei den DICOM-Läufen (vermutlich mm → `0.0167`). Vor dem
  ersten Vernetzungslauf gegen eine bestehende `metadata.json` prüfen.
- Sinnvollen Ausschnitt (RVE-Größe) für den neuen Datensatz festlegen.
- Entscheiden, ob `A01_segmented/` mit in die Cluster-Synchronisierung geht
  (2,5 GB Rohdatei — ggf. nur die konvertierte `.npy` übertragen).
