# .leS → Phasenfeld-Bruch — Bedienung

Vollständige Beschreibung des Ablaufs in 016. Für die Konventionen und die
getroffenen Entscheidungen: `CLAUDE.md`. Für den Voxel→FEM-Teil im Detail:
`PIPELINE_ANNAHMEN_DICOM_TO_FEM.md`.

---

## 1. Die Kette in einem Bild

```text
JM-25_77_85p55.leS  (ASCII, 1 = Material)
        │  A01_les_2_npy.py      Crop (Riegel) + reduce + Phaseninversion
        ▼
segmented_3D_volume.npy  (uint8, 1 = Pore, 0 = Aluminium)
        │  02b_build_subvolume_arrays.py     Teilvolumen (xy_divisions = 1)
        │  02c_voxel_topology_cleanup.py     nur Audit (cleanup aus)
        │  02d_axis_aligned_cuboid_crop.py   AUS (innerer Seal, bis 2026-08-31)
        │  02f_add_voxel_shell.py            externe Aluminiumschale 0,4 mm (wie 011)
        ▼
volume_external_shell.npy
        │  03_mesh_3D_array_pygalmesh.py     SDF + Marching Cubes + CGAL
        │  04_scale_and_translate_mesh_mod.py  auf mm skalieren, Schale herausrechnen (011-Version)
        │  10_snap_mesh_to_crop_boundary.py  Randknoten auf die Box-Flächen ziehen
        │  05 / 08 / 09                      TetGen, Qualität, Topologie
        ▼
mesh.xdmf
        │  make_mesh_dlfx_compatible_cluster.py
        ▼
dlfx_mesh.xdmf / .h5   ─── archiviert ───►  resources/generated_meshes/…
                                                    │
                                                    │  Stufe 2, eigener Job
                                                    ▼
                                    00_template/script.py
                                    → pfmfrac_function.py (DOLFINx)
                                    → pfmfrac_function.xdmf, *_graphs.txt
```

Stufe 1 endet beim Archiv, Stufe 2 liest es. Zwischenarrays und QA-Reports
bleiben im Arbeitsverzeichnis und werden **nicht** archiviert — sie entstehen
bei einem erneuten Lauf wieder.

---

## 2. Configs erzeugen

```bash
cd "$HPC_SCRATCH/pygalmesh/data/scripts/016-Fracture-From-leS"

./create_fracture_config.sh                    # alle Stufen aus MESH_TIERS
ONLY_TIERS="coarse" ./create_fracture_config.sh
LES_BAR_Y_MM=12 ./create_fracture_config.sh    # höherer Riegel
LES_MAX_ELEMENT_SIZE_UM=600 ONLY_TIERS="coarse" ./create_fracture_config.sh
```

Das Skript liest `config.sh`, holt Gitter und Voxelgröße aus dem `.leS`-Header
(`A04_les_header_info.py`) und ruft für jede Stufe `create_fracture_config.py`
auf. Ergebnis: `config-fracture-<SPECIMEN_NAME>-<tier>.json`.

`02_create_folders_CLUSTER.sh` ruft es vor dem Synchronisieren automatisch auf.
Abschalten mit `SKIP_CONFIGS=1`.

### Woher Gitter und Voxelgröße kommen

```bash
python3 A04_les_header_info.py /data/resources/A01_segmented/JM-25_77_85p55.leS
python3 A04_les_header_info.py <datei> --format shell   # LES_GRID=... LES_VOXEL_SIZE_M=...
```

Das Skript liest nur die erste Zeile — bei einer 2,5-GB-Datei also in
Millisekunden, ohne numpy. Ist die Datei nicht erreichbar (z.B. auf dem Mac),
warnt `create_fracture_config.sh` und erzeugt Configs **ohne** Riegel-Crop.
Dann `LES_GRID` und `LES_VOXEL_SIZE_M` in `config.sh` eintragen oder die
Configs auf dem Cluster neu erzeugen.

### Was in der Config steht

Zusätzlich zu allem, was schon aus 015 kommt:

| Block | Zweck |
|---|---|
| `fracture` | Materialsätze, `Gc`-Sätze, `eps_factor_param`, `element_order` — gelesen von `00_template/script.py` |
| `mesh_resolution` | Stufe, reduce, Voxel- und Elementgröße |
| `fracture_geometry_check` | Riegelmaße in mm (inkl. Schale), `epsilon`, Elemente je epsilon, `surfing_bc_band_fraction`, Schale, verwendetes Gitter — Dokumentation und Warnquelle |
| `dataset.specimen` | Probenname für den Archivpfad |

Der `yield_surface`-Block aus 015 wird entfernt.

---

## 3. Auf dem Cluster laufen lassen

```bash
# einmalig: Configs erzeugen und alles nach $HPC_SCRATCH spiegeln
cd "$HOME/meshing/Meshing/pygalmesh"
data/scripts/016-Fracture-From-leS/02_create_folders_CLUSTER.sh

# die ganze Kette (Netz -> Simulation, mit --dependency=afterok)
"$HPC_SCRATCH/pygalmesh/data/scripts/016-Fracture-From-leS/submit_fracture_pipeline_CLUSTER.sh"

# Varianten
submit_fracture_pipeline_CLUSTER.sh config-fracture-JM-25-77-medium.json
ONLY_MESH=1 submit_fracture_pipeline_CLUSTER.sh     # nur vernetzen
SKIP_MESH=1 submit_fracture_pipeline_CLUSTER.sh     # Netz existiert schon
DRY_RUN=1   submit_fracture_pipeline_CLUSTER.sh     # nur anzeigen
```

Einzeln:

```bash
sbatch job_generate_mesh_CLUSTER.sh  config-fracture-JM-25-77-coarse.json
sbatch job_run_simulation_CLUSTER.sh config-fracture-JM-25-77-coarse.json
```

⚠ **Dieselbe Config für beide Stufen.** Der Archivpfad wird aus
`dataset.specimen`, `binning.label` und `03_mesh_3D_array.specimen_name`
gebildet. Letzteres ist bewusst **auflösungsspezifisch** — in 012 war das eine
Falle: `01_segment_slice_wise.specimen_name` ist über die Stufen hinweg gleich,
und alle drei Stufen hätten sich gegenseitig im Archiv überschrieben.

### Wie viele Jobs sind das?

**Zwei SLURM-Jobs je Config** — mehr nicht. `submit_fracture_pipeline_CLUSTER.sh`
reicht genau einen Netz-Job und einen Simulations-Job ein, verkettet über
`--dependency=afterok`. Für alle drei Auflösungsstufen also 6 Jobs.

Das ist der große Unterschied zu 015: dort waren es 4 Datensätze × 2
Fließgrenzen × 96 Punkte = **768** Punkt-Jobs, weil jeder Punkt der Fließfläche
ein eigener FE-Lauf ist. Eine Bruchsimulation ist **ein** Lauf.

Innerhalb der Jobs laufen `srun`-Steps:

| Job | Steps | wie viele |
|---|---|---:|
| Netzerzeugung | `A01`, `02b` | 2 |
| | je Teilvolumen: `02c`, `02d`, `03`, `04`, `05`, `08`, `09` | 7 |
| | `make_mesh_dlfx_compatible` | 1 |
| | **Summe** bei `xy_divisions = 1` | **10** |
| Bruchsimulation | `script.py`, je Teilvolumen × Material × Richtung | **1** |

Alle Steps der Netzerzeugung laufen mit `srun -n 1` — der Job fordert 32 Tasks
nur wegen des Speichers an. Der Simulations-Step läuft mit `-n 96`.

Die Zahlen skalieren mit:

* `02b_build_subvolume_arrays.xy_divisions` — bei 2 wären es 4 Teilvolumen und
  damit 4 × 7 + 3 = 31 Netz-Steps und 4 Simulations-Steps. Default ist 1.
* `fracture.materials` × `fracture.directions` — Default `["std"] × ["y"]` = 1.
* Die `enabled`-Flags von `02e`, `02f`, `10`, `11`. Diese vier Blöcke fehlen in
  der Config, `config_bool` liefert dafür 0 — sie laufen also nicht.

Die Config-Abfragen (`config_bool`, `config_value_default`) laufen **auf dem
Host**, nicht über `srun`. In 015 gingen sie noch durch den Container und
kosteten pro Abfrage einen Job-Step.

### Ressourcen

| Job | Header | Werte | Begründung |
|---|---|---|---|
| Netzerzeugung | `job_generate_mesh_CLUSTER.sh` | `-p mem`, `-n 32`, `--mem-per-cpu=45000`, `-C "m01&mem1536g"`, `-t 1440` | Es arbeitet nur **ein** Task (`srun -n 1`); die Zuteilung dient dem Speicher. 32 × 45 GB = 1,44 TB — dieselbe Größe wie beim erfolgreichen 015-Lauf, nur ohne 64 brachliegende Kerne. |
| Bruchsimulation | `job_run_simulation_CLUSTER.sh` | `-n 96`, `-N 1`, `--mem-per-cpu=4000`, `-C i01`, `-t 10080` | wie in 012; ein Phasenfeldlauf kann Tage dauern. |

Die `srun`-Steps setzen **keine** eigenen `--time`/`--mem-per-cpu`-Werte, sondern
erben sie vom Job. Feste Werte im Step haben in 015 zu

```
srun: error: Unable to create step for job <id>: More processors requested than permitted
```

geführt, sobald der Job weniger Speicher je CPU bekam als der Step anforderte.
Über `SRUN_MEM_PER_CPU` lässt sich das bei Bedarf weiterhin setzen.

Speicherbedarf nach einem Lauf messen:

```bash
sacct -j <jobid> --format=JobID,JobName,AllocCPUS,MaxRSS,Elapsed
```

---

## 4. Was die Bruchsimulation rechnet

`00_template/pfmfrac_function.py` (unverändert aus 011):

* **Modell:** statisches Phasenfeld, quadratische Degradation,
  `alex.phasefield.StaticPhaseFieldProblem3D`, gemischter Ansatz (u, s) mit
  `element_order`.
* **Regularisierung:** `epsilon = (y_max − y_min) / eps_factor_param`,
  `eta = 0.005`, `Mob = 1000`.
* **Anriss:** `s = 0` für `x < 0,2·Lx` in einem Band von ±2 % `Ly` um die
  Mittelebene — ein durchgehender Kerb über die volle Dicke.
* **Randbedingungen (Surfing):** auf dem Box-Rand wird das
  K-Feld-Verschiebungsfeld einer Modus-I-Rissspitze aufgebracht, deren Position
  mit `v_crack = 2·(x_max − x_start)/Tend` nach `+x` wandert.
  `K1 = sig_c · sqrt(Ly)` mit `sig_c` aus `Gc`, `mu` und `epsilon`.
  Dazu die Irreversibilitäts-Nebenbedingung.
  **⚠ Nicht auf dem ganzen Rand:** `alex.boundaryconditions.get_boundary_of_box_as_function`
  spart das Rissband aus und setzt die Verschiebung nur bei
  `|y − y_mid| ≥ 4·epsilon`, also auf dem Anteil `1 − 8/eps_factor_param` der
  Höhe (20 → 60 %, 16 → 50 %, 12 → 33 %, **8 → 0 %**). Mit `eps_factor = 8`
  (016 bis 2026-08-31) greift die BC auf keinem Knoten; das Ergebnis ist eine
  Starrkörperrotation. Der Generator und das Simulationsjob-Skript brechen
  deshalb bei `eps_factor ≤ 8` ab.
* **Zeit:** `dt = 1e-4`, `Tend = 1000·dt`, adaptive Newton-Schrittweite,
  Abbruch wenn `dt < 1e-14`.
* **Auswertung je Zeitschritt:** J-Integral aus dem Eshelby-Tensor über den
  Außenrand (roh und durch die z-Dicke geteilt), Reaktionskräfte auf der
  Oberseite, äußere Arbeit, Rissoberfläche `A`, Rissspitzenposition.
  Ausgabe in `pfmfrac_function_graphs.txt` und `pfmfrac_function.xdmf`
  (jeder 5. erfolgreiche Schritt).

**Warum der Riegel in x lang sein muss:** der Riss startet bei `0,2·Lx` und
läuft bis `x_max`. Ist `Lx` klein, ist die Rissbahn kurz und die Surfing-BC hat
kaum Weg.

### Material

`script.py` liest `fracture.material_sets[<name>]` und rechnet daraus
`lambda` und `mu`:

| Satz | E [MPa] | nu |
|---|---:|---:|
| `std` (Default) | 70 000 | 0,35 |
| `am` | 73 000 | 0,36 |
| `conv` | 82 000 | 0,35 |

`Gc` kommt aus `fracture.fracture_toughness_sets`:

| Satz | Gc [N/mm] | Quelle |
|---|---:|---|
| `alsi10mg_as_built` (Default) | 7,2 | Literaturbereich 6,0–8,4; DOI 10.1016/j.ijmecsci.2021.106868 |
| `original` | 1,0 | dimensionsloser Testwert aus 005 |

Einheiten durchgehend: **mm, MPa, N/mm**.

---

## 5. Ergebnisse

```text
00_results/<specimen>/<binning.label>/fracture/<run_name>-<material>-<direction>/
    <run_name>_from_resources/
        subvolume_x0_y0/
            dlfx_mesh.xdmf/.h5
            config.json
            simulation_<zeitstempel>_dlfx_mesh_std_alsi10mg_as_built_lam…/
                pfmfrac_function.xdmf / .h5
                pfmfrac_function_graphs.txt
                pfmfrac_function_log.txt
```

Die Spaltenreihenfolge in `pfmfrac_function_graphs.txt`:

```text
t, Jx, Jy, Jz, Jx/t_z, Jy/t_z, Jz/t_z, x_tip, xtip_soll, Rx, Ry, Rz, dW, W, A
```

`x_tip` ist die aus dem Phasenfeld verfolgte Rissspitze, `xtip_soll` die von der
Surfing-BC vorgegebene. Laufen sie auseinander, folgt der Riss der Randbedingung
nicht mehr — typisch, wenn `epsilon` zu klein für das Netz ist oder der Riegel
zu kurz.

---

## 6. Wenn etwas schiefgeht

| Symptom | Ursache | Gegenmittel |
|---|---|---|
| `Kein archiviertes Netz unter …` | Stufe 1 fehlt oder andere Config | `job_generate_mesh_CLUSTER.sh` mit **derselben** Config |
| `can't open file '/work/scratch/…/A01_les_2_npy.py'` + `Error changing the container working directory` | srun-Step erbt das sbatch-Verzeichnis außerhalb der Binds; Apptainer hängt nur cwd, `/home` und `/data` ein | `run_generate_mesh_CLUSTER.sh` macht seit 2026-08-31 selbst `cd "$working_directory"` (wie 015). Alte Skriptversion: aus `$HPC_SCRATCH/…/016-Fracture-From-leS` heraus `sbatch` aufrufen |
| `In … liegen 4 .leS-Dateien` | `A01_les_2_npy.input` zeigt auf den Ordner | `LES_FILENAME` in `config.sh` setzen, Config neu erzeugen |
| `SDF surface is not watertight/manifold` in 03 | siehe Diagnosetabelle unten | |
| `surface_open_edges > 0` | Isofläche am Domänenrand abgeschnitten | `sdf_pygalmesh_parameters.pad_width` erhöhen (Default hier 3); `sdf_sigma_voxels` **nicht** erhöhen |
| `surface_nonmanifold_edges > 0` | zwei Oberflächenblätter berühren sich | `03` repariert das selbst (`repair_nonmanifold`); sonst `level` minimal verschieben |
| Starrkörpermoden im FE | freischwebende Materialinseln | `keep_largest_component = true` (Default hier) |
| **uY linear in x, uX linear in y, Dehnung ≈ 0 (reine Rotation)** | Surfing-BC greift nirgends: `eps_factor_param ≤ 8` → `4·epsilon ≥ Ly/2` | `FRACTURE_EPS_FACTOR_PARAM = 20`; grobe Elemente über `LES_BAR_Y_MM` auffangen |
| Wenige Poren, dicke Vollmaterialwände | innerer 02d-Seal frisst den Schaum (9/14/9 Voxel = 1,2/1,9/1,2 mm bei 134-µm-Voxeln) | `LES_SHELL_MODE=external` (Default seit 2026-08-31): 02f fügt die Schale außen an |
| Netz um die Schale gestaucht (z um ~20 % zu kurz) | 015-Version von `04_scale_and_translate_mesh_mod.py` kennt 02f nicht | 011-Version verwenden (liegt jetzt hier), Aufruf mit `--npy` |
| `More processors requested than permitted` | `srun`-Step fordert mehr Speicher je CPU als der Job hat | Step erbt die Werte — `SRUN_MEM_PER_CPU` leer lassen |
| Weniger als 2 Elemente je epsilon | Netz zu grob für `epsilon` | Elemente verfeinern **oder** Riegel höher (`LES_BAR_Y_MM`). **Nicht** `eps_factor` senken (siehe oben) |

Gemessen in 014 an einem 300³-Ausschnitt bei reduce = 2: `pad_width = 1` mit
`sigma = 1,25` erzeugt 7180 offene Kanten; mit `pad_width = 3` keine. Deshalb ist
`pad_width = 3` Default.

---

## 7. Sichtprüfung

```bash
# Struktur des .leS-Volumens (schnell, grob)
python3 A03_plot_les_structure.py --reduce 8 --slices

# ein konkretes Voxelvolumen aus der Pipeline
python3 A02_preview_voxel_volume.py \
  --npy .../subvolume_x0_y0/volume_boundary_shell_aniso.npy \
  --preview-reduce 2
```

`A02` erwartet per Default `--material-value 0` (Pipeline-Konvention).

Stegdicken und Porengrößen messen — die Grundlage für die Wahl der
Elementgröße:

```bash
python3 evaluate_pore_size_distribution.py --config config-fracture-JM-25-77-coarse.json
```
