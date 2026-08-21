# 016 — Phasenfeld-Bruch aus .leS-Daten

Vernetzt ein bereits segmentiertes Voxelbild (`.leS`) zu einem langen Riegel und
rechnet darauf eine Phasenfeld-Bruchsimulation mit Surfing-Randbedingungen.

* Vorverarbeitung und Vernetzung: unverändert aus **015-Yield-Surface-Batch-leS**
* Aufteilung in zwei Jobs und Netzarchiv: aus **012-Fracture-Mesh-Sim-Split**
* Bruchmodell (`00_template/`): aus **011-Fracture-From-CT-Scans**

Datensatz: `JM-25-88_78p86.leS` · Riegel ≈ 19,8 × 8 × 4 mm ·
Elementgröße 400 µm (Stufe `coarse`)

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
ls 00_results/JM-25-88/leS-reduce-8/fracture/
```

---

## Die drei Auflösungsstufen

| Stufe | reduce | Voxel | Elementgröße | Elemente je epsilon |
|---|---:|---:|---:|---:|
| **coarse** (Default) | 8 | 133,6 µm | 400 µm | 2,5 |
| medium | 4 | 66,8 µm | 267 µm | 3,7 |
| fine | 4 | 66,8 µm | 200 µm | 5,0 |

`epsilon = Ly / eps_factor_param ≈ 1,0 mm` ist über alle Stufen gleich — die
Familie ist damit eine Netzkonvergenzstudie, keine Variation der Physik.

```bash
sbatch job_generate_mesh_CLUSTER.sh  config-fracture-JM-25-88-medium.json
sbatch job_run_simulation_CLUSTER.sh config-fracture-JM-25-88-medium.json
```

Beide Stufen brauchen **dieselbe** Config.

---

## Etwas ändern

Alles läuft über `config.sh`; jede Variable ist über die Umgebung
überschreibbar:

```bash
LES_BAR_Y_MM=12 ./create_fracture_config.sh              # höherer Riegel
LES_MAX_ELEMENT_SIZE_UM=600 ONLY_TIERS=coarse ./create_fracture_config.sh
SPECIMEN_NAME=JM-25-77 LES_FILENAME=JM-25_77_85p55.leS ./create_fracture_config.sh
FRACTURE_EPS_FACTOR_PARAM=6 ./create_fracture_config.sh  # größeres epsilon
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
