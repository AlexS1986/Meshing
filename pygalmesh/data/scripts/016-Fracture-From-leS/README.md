# 016 — Phasenfeld-Bruch aus .leS-Daten

Vernetzt ein bereits segmentiertes Voxelbild (`.leS`) — die ganze Probe, in x
gespiegelt und in eine homogene Aluminiumschale eingebettet (wie 011) — und
rechnet darauf eine Phasenfeld-Bruchsimulation mit Surfing-Randbedingungen.

* Vorverarbeitung und Vernetzung: unverändert aus **015-Yield-Surface-Batch-leS**
* Aufteilung in zwei Jobs und Netzarchiv: aus **012-Fracture-Mesh-Sim-Split**
* Bruchmodell (`00_template/`): aus **011-Fracture-From-CT-Scans**

Datensatz: `JM-25_77_85p55.leS` (JM-25-77) · ganze Probe 19,8 × 19,8 × 14,8 mm,
1× in x gespiegelt → Schaum 39,5 × 19,8 × 14,8 mm · Schale 0,4 mm (y/z), 4 mm
Endblöcke (x) · reduce 4 (66,8 µm) · Elementgröße 200 µm (Stufe `medium`) ·
`eps_factor = 20` → epsilon 1,03 mm

---

## In vier Kommandos

```bash
# 1. Configs erzeugen und nach $HPC_SCRATCH spiegeln (Login-Node)
cd "$HOME/meshing/Meshing/pygalmesh"
data/scripts/016-Fracture-From-leS/02_create_folders_CLUSTER.sh

# 2. Netz und Simulation als abhängige Kette einreihen
"$HPC_SCRATCH/pygalmesh/data/scripts/016-Fracture-From-leS/submit_fracture_pipeline_CLUSTER.sh"

# 3. Status
squeue -u "$USER"

# 4. Ergebnisse
ls 00_results/JM-25-77/leS-reduce-4/fracture/
```

---

## Die drei Auflösungsstufen

| Stufe | reduce | Voxel | Elementgröße | Elemente je epsilon | Tets (geschätzt) |
|---|---:|---:|---:|---:|---:|
| coarse | 4 | 66,8 µm | 250 µm | 4,1 | ~2,5 Mio |
| **medium** (Default) | 4 | 66,8 µm | 200 µm | 5,2 | ~5 Mio |
| fine | 4 | 66,8 µm | 150 µm | 6,9 | ~12 Mio |

`epsilon = Ly / eps_factor_param ≈ 1,03 mm` ist über alle Stufen gleich — die
Familie ist damit eine Netzkonvergenzstudie, keine Variation der Physik.
**`eps_factor_param` nie ≤ 8:** die Surfing-BC greift nur bei
`|y − y_mid| ≥ 4·epsilon` (Anteil der Höhe `1 − 8/eps_factor`).

```bash
sbatch job_generate_mesh_CLUSTER.sh  config-fracture-JM-25-77-medium.json
sbatch job_run_simulation_CLUSTER.sh config-fracture-JM-25-77-medium.json
```

Beide Stufen brauchen **dieselbe** Config.

---

## Etwas ändern

Alles läuft über `config.sh`; jede Variable ist über die Umgebung
überschreibbar:

```bash
LES_MIRROR_X_REPETITIONS=2 ./create_fracture_config.sh   # zweimal spiegeln wie 011 (Lx/Ly ≈ 4)
LES_SHELL_X_UM=2000 ./create_fracture_config.sh          # dünnere Endblöcke (spart ~¼ der Elemente)
LES_BAR_Y_MM=16 LES_BAR_Z_MM=4 ./create_fracture_config.sh   # Riegel-Ausschnitt statt ganzer Probe
LES_MAX_ELEMENT_SIZE_UM=300 ONLY_TIERS=coarse ./create_fracture_config.sh
SPECIMEN_NAME=JM-25-71 LES_FILENAME=JM-25-71_79p85.leS LES_GRID= LES_VOXEL_SIZE_M= ./create_fracture_config.sh
LES_SHELL_UM=600 ./create_fracture_config.sh             # dickere Außenschale
# FRACTURE_EPS_FACTOR_PARAM unter 12 ist keine Option: BC-Band wird zu klein, bei <= 8 Abbruch.
```

Danach neu synchronisieren (`02_create_folders_CLUSTER.sh`).

---

## Weiterlesen

| Datei | Inhalt |
|---|---|
| `CLAUDE.md` | Konventionen und getroffene Entscheidungen — **zuerst lesen** |
| `LES_FRACTURE_PIPELINE.md` | Bedienung im Detail, Modellbeschreibung, Fehlerbilder |
| `FILES.md` | Was jede Datei tut und woher sie kommt |
| `CLAUDE_PROJECT_NOTES.md` | Session-Protokoll und offene Punkte |
