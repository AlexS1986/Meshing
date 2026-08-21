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

**Ausgewählter Datensatz:** `JM-25-88_78p86.leS` (78,86 % Porosität — der
dichteste der vier). Wechsel über `SPECIMEN_NAME`/`LES_FILENAME` in `config.sh`.

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

* Grobe Elemente ⇒ `epsilon` muss groß sein ⇒ `eps_factor_param` klein.
* 011/012 verwendeten `eps_factor_param = 20`. Hier steht er auf **8**, damit
  bei 8 mm Riegelhöhe `epsilon ≈ 1,0 mm` herauskommt und die 400-µm-Elemente
  der Stufe `coarse` 2,5 Elemente je epsilon liefern.

`create_fracture_config.py` schreibt `fracture_geometry_check.elements_per_epsilon`
in jede Config und warnt beim Erzeugen, wenn der Wert unter 2 fällt;
`job_run_simulation_CLUSTER.sh` warnt beim Start noch einmal.

**Offener Punkt:** `epsilon ≈ 1 mm` ist größer als die Stegdicke des Schaums.
Der Riss wird damit über mehrere Stege verschmiert — das ist die bewusst in Kauf
genommene Folge der groben Auflösung. Siehe `CLAUDE_PROJECT_NOTES.md`, Abschnitt
„Offene Punkte".

---

## 5. Probengeometrie (entschieden)

Die Surfing-Randbedingungen setzen den Rissstart bei `x = 0,2·Lx` und lassen den
Riss nach `+x` laufen. Das Gebiet muss deshalb in x deutlich länger sein als in
y und z.

**Entscheidung:** langer Riegel, direkt aus dem `.leS`-Volumen geschnitten —
x voll (≈ 19,8 mm), y = 8 mm, z = 4 mm, mittig platziert.

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
| **coarse** (Default) | 8 | 133,6 µm | **400 µm** | 2,5 |
| medium | 4 | 66,8 µm | 267 µm | 3,7 |
| fine | 4 | 66,8 µm | 200 µm | 5,0 |

\* für eine Quelle mit 16,7 µm/Voxel; der Generator rechnet mit dem Wert aus dem
`.leS`-Header des jeweiligen Datensatzes.
\** bei `Ly = 8 mm` und `eps_factor = 8`, also `epsilon ≈ 1,0 mm`.

Zum Vergleich: 011/012 rechneten mit 199 µm, 015 mit 75 µm Elementen.
`epsilon` bleibt über alle drei Stufen gleich — die Familie ist damit eine
saubere Netzkonvergenzstudie und keine Variation der Physik.

Die Randschale in 02d wird **aus der Elementgröße abgeleitet**
(`ceil(3 · h / dx)` Voxel), damit sie in jeder Stufe rund drei Elemente dick
bleibt und die Dirichlet-Ränder tragen kann. Feste Werte über
`LES_BOUNDARY_SHELL_XZ` / `LES_BOUNDARY_SHELL_Y`.

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
sbatch job_generate_mesh_CLUSTER.sh  config-fracture-JM-25-88-coarse.json
sbatch job_run_simulation_CLUSTER.sh config-fracture-JM-25-88-coarse.json
```

**Beide Stufen müssen dieselbe Config bekommen**, sonst zeigt der Archivpfad
(`specimen/label/run_name`) ins Leere. Details: `LES_FRACTURE_PIPELINE.md`.

---

## 8. Offene Punkte

Siehe `CLAUDE_PROJECT_NOTES.md`, Abschnitt „Offene Punkte" — kurz:

- **Gitter von JM-25-88 ist noch nicht verifiziert.** Die mitgelieferten Configs
  wurden mit dem Gitter von JM-25-77 (1187 × 1188 × 886 @ 16,7 µm) erzeugt.
  `02_create_folders_CLUSTER.sh` erzeugt sie auf dem Cluster aus dem echten
  Header neu — **einmal prüfen**, ob der Riegel dann noch passt.
- **Elementgröße gegen Stegdicke prüfen.** 400 µm können dicker sein als die
  Stege. `evaluate_pore_size_distribution.py` liegt im Ordner und misst das.
- `02c` (scipy) und `03` (nanomesh/pygalmesh) sind lokal nicht lauffähig.
