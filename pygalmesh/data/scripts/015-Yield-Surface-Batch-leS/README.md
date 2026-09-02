# 015 — Fliessflaechen fuer vier .leS-Datensaetze x zwei Fliessgrenzen

Dieser Ordner ist die Batch-Variante von `014-Yield-Surface-From-leS`. Die
Pipeline (`.leS` → Voxelvolumen → Netz → elasto-plastischer Solve →
Fliessflaeche) ist unveraendert; neu ist eine duenne Schicht `batch_*`, die
**acht Kombinationen** in einem Rutsch erzeugt, einreicht, ueberwacht und die
Ergebnisse zum Herunterladen einpackt.

| | |
|---|---|
| Datensaetze | `JM-25-77`, `JM-25-71`, `JM-25-83`, `JM-25-88` |
| Anfangsfliessgrenzen | **75 MPa** und **100 MPa** (`yield_surface.material_sets.std.sig_y`) |
| Kombinationen | 4 x 2 = **8** |
| Punkte je Kombination | **96** (Fibonacci-Sphere, `YIELD_SURFACE_POINTS`) |
| Punkt-Jobs gesamt | 768 |
| Netzvorbereitungen | **4** — eine je Datensatz, nicht je Kombination |
| Zeitlimit je Punkt-Job | seit 01.09.2026 **`-t 1440`** in der Default-Partition, 32 Tasks (Fortsetzungskette bei Ueberlauf); vorher `-t 10080` auf `long` mit 64 Tasks |

> **Warum nur vier Netzvorbereitungen?** Das Netz haengt nicht von der
> Fliessgrenze ab. Beide sig_y-Varianten eines Datensatzes bekommen dieselbe
> `dataset.id` (`JM-25-77_les_r2`) und benutzen dasselbe vorbereitete Netz.
> Getrennt werden die Laeufe ueber `binning.label` (`leS-r2-sigy075` bzw.
> `leS-r2-sigy100`), das in allen Ergebnispfaden auftaucht.

> **(Historisch, r2-Studie bis 01.09.2026) Warum `-p long`?** Die Default-Partition `deflt` erlaubt hoechstens 1440
> Minuten. `-t 10080` (7 d) wuerde dort mit *"Requested time limit is invalid"*
> abgelehnt. `long` hat dieselben i01-Knoten und laesst genau diese 7 Tage zu —
> mehr ist nicht moeglich, laengere Rechnungen laufen ueber die
> Fortsetzungskette. Beides steht in `config.sh` (`YIELD_JOB_TIME`,
> `YIELD_JOB_PARTITION`).

---

## 0. Vorbereitung

### 0.1 Ordner auf den Cluster bringen

Wie bei 014: dieser Ordner muss zuerst in der Home-Kopie des Clusters liegen
(`$HOME/meshing/Meshing/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS/`) —
ueber den ueblichen Weg (git pull bzw. rsync vom Mac). Von dort synchronisiert
`batch_create_folders_CLUSTER.sh` in Schritt 1 nach `$HPC_SCRATCH`.

> Die Punkt-Jobs bekommen ihre `#SBATCH -e/-o`-Zeilen nur, wenn `HPC_SCRATCH`
> beim Erzeugen gesetzt ist. Deshalb `batch_create_folders_CLUSTER.sh` **auf dem
> Login-Node** laufen lassen, nicht auf dem Mac.

### 0.2 Die vier .leS-Dateien ablegen

Erwartet werden sie auf dem Cluster unter

```text
$HPC_SCRATCH/pygalmesh/data/resources/A01_segmented/     (Container: /data/resources/A01_segmented/)
    JM-25_77_85p55.leS
    JM-25-71_79p85.leS
    JM-25-83_80p55.leS
    JM-25-88_78p86.leS
```

Die Zuordnung Datensatz → Dateiname steht in `config.sh` im Block
`BATCH_DATASETS`. Weicht ein Dateiname ab, sucht `batch_lib.sh` ersatzweise per
Glob (`JM-25[-_]88*.leS`) und meldet, was es genommen hat — Anpassen ist trotzdem
sauberer. Ein anderer Ablageort geht ueber `LES_RESOURCE_DIR`.

Pruefen, ob alle vier gefunden werden:

```bash
cd "$HOME/meshing/Meshing/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS"
bash batch_create_configs.sh          # meldet je Datensatz die verwendete Datei
```

---

## 1. Der Ablauf in vier Kommandos

```bash
# --- Login-Node -------------------------------------------------------------

# 1) Configs + Punkt-Jobs erzeugen und nach $HPC_SCRATCH synchronisieren
cd "$HOME/meshing/Meshing/pygalmesh"
data/scripts/015-Yield-Surface-Batch-leS/batch_create_folders_CLUSTER.sh

# 2) alles einreichen: 4 Netzvorbereitungen + 768 Punkt-Jobs mit afterok
"$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS/batch_submit_CLUSTER.sh"

# 3) Stand ansehen (jederzeit)
"$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS/batch_status_CLUSTER.sh"

# 4) Ergebnisse einsammeln und zippen
"$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS/batch_collect_results.sh"
```

Das entspricht dem Ablauf aus 014 (`02_create_folders_CLUSTER.sh` →
`submit_les_pipeline_CLUSTER.sh`), nur ueber alle Kombinationen.

### Erst schauen, dann einreichen

```bash
DRY_RUN=1 .../batch_submit_CLUSTER.sh | head -40
```

zeigt jede `sbatch`-Zeile, ohne etwas abzuschicken.

---

## 2. Schritt fuer Schritt

### 2.1 `batch_create_configs.sh` — acht Configs

Erzeugt aus `config-A01-les.json` je Kombination eine Config:

```text
config-JM-25-77-r2-sigy075.json     config-JM-25-77-r2-sigy100.json
config-JM-25-71-r2-sigy075.json     config-JM-25-71-r2-sigy100.json
config-JM-25-83-r2-sigy075.json     config-JM-25-83-r2-sigy100.json
config-JM-25-88-r2-sigy075.json     config-JM-25-88-r2-sigy100.json
```

Unterschiede zwischen zwei Configs desselben Datensatzes: `sig_y` und
`binning.label`. Alles andere — Netzfeinheit (75 µm), Randschale (8/12/8 Voxel),
`pad_width = 3`, `keep_largest_component = true`, die drei Fliesskriterien mit
Schwelle 0,002 — ist identisch mit dem Stand von 014.

Einzelne Kombinationen neu erzeugen:

```bash
ONLY_DATASETS="JM-25-83" ONLY_SIG_Y="100" bash batch_create_configs.sh
```

### 2.2 `batch_setup_jobs.sh` — die Punkt-Jobs

```bash
bash batch_setup_jobs.sh          # Punktzahl aus config.sh (96)
bash batch_setup_jobs.sh 48       # andere Punktzahl
```

Ergebnis je Kombination:

```text
yield_surface_jobs/JM-25-77_sigy075/n096/
├── manifest.csv                     Richtungen + Jobnamen
├── submit_all_yield_surface_points.sh
└── 96 x ys_NNN_e1_..._e2_..._e3_.../
        ├── config.json              Kopie der Kombi-Config + diese Richtung
        ├── parameters.txt           aufgeloeste Solver-Parameter
        └── job_ys_..._CLUSTER.sh    SLURM-Job
```

Der SLURM-**Jobname** ist `JM-25-77_s075-ys000` statt der langen `sample_id` —
sonst waeren in `squeue` 768 Jobs nicht auseinanderzuhalten. Der lange Name
bleibt als Ordnername erhalten.

### 2.3 `batch_create_folders_CLUSTER.sh` — erzeugen + synchronisieren

Das Gegenstueck zu `02_create_folders_CLUSTER.sh` aus 014: ruft 2.1 und 2.2 auf
und synchronisiert dann `$HOME/meshing/Meshing/pygalmesh/` nach
`$HPC_SCRATCH/pygalmesh/` (`rsync -av --update`).

```bash
SKIP_GENERATE=1 .../batch_create_folders_CLUSTER.sh    # nur synchronisieren
```

### 2.4 `batch_submit_CLUSTER.sh` — einreichen

1. **Queue-Pruefung.** Account `p0023647` erlaubt `MaxSubmit = 1000` und
   `MaxJobs = 400`. Das Skript zaehlt vorher `squeue -u $USER` und bricht ab,
   wenn die Summe `BATCH_MAX_SUBMIT` (1000) ueberschreiten wuerde. Bei 8 x 96 +
   4 = 772 Jobs passt es; bei mehr Punkten in Teilen einreichen:

   ```bash
   ONLY_SIG_Y=100 .../batch_submit_CLUSTER.sh
   # spaeter, wenn Platz ist:
   ONLY_SIG_Y=75  .../batch_submit_CLUSTER.sh
   ```

2. **Netzvorbereitung je Datensatz** (`job_prepare_mesh_CLUSTER.sh`, Partition
   `deflt`, `-C i01`, `-n 8`, `--mem-per-cpu=15000`, 120 min). Existiert das fertige
   `dlfx_mesh.xdmf` schon, wird sie uebersprungen (`AUTO_SKIP_PREPARE=0`
   erzwingt sie trotzdem). Jobname: `prep-JM-25-77`.

3. **Punkt-Jobs** mit `--dependency=afterok:<prep-id> --kill-on-invalid-dep=yes`.
   Scheitert die Netzvorbereitung eines Datensatzes, verwirft SLURM genau dessen
   192 Punkt-Jobs; die anderen Datensaetze laufen weiter.

| Variable | Wirkung |
|---|---|
| `DRY_RUN=1` | nur anzeigen |
| `SKIP_PREPARE=1` | Netze existieren bereits, keine Abhaengigkeit setzen |
| `AUTO_SKIP_PREPARE=0` | Netzvorbereitung auch bei vorhandenem Netz einreichen |
| `ONLY_DATASETS="JM-25-77 JM-25-83"` | nur diese Datensaetze |
| `ONLY_SIG_Y="100"` | nur diese Fliessgrenze |
| `PREP_JOB_TIME=2880` | Zeitlimit der Netzvorbereitung (Minuten) |
| `FORCE=1` | Queue-Pruefung uebergehen |

### 2.5 `batch_status_CLUSTER.sh` — Stand

```text
KOMBINATION              NETZ     JOBS ERGEBNIS  GUELTIG  RUNNING  PENDING    SONST
------------------------------------------------------------------------------------
JM-25-77_sigy075         ja         96       96       81        0        0        0
JM-25-77_sigy100         ja         96       94       79        2       15        0
...
```

* **NETZ** — `dlfx_mesh.xdmf` des Datensatzes vorhanden
* **ERGEBNIS** — gefundene `yield_run_*.json`
* **GUELTIG** — davon mit `final_yield_state` (Punkte, die in die Fliessflaeche
  eingehen; Laeufe ohne Fliesszustand im Solver-Horizont fehlen hier)

### 2.6 `batch_collect_results.sh` — einsammeln und zippen

```bash
.../batch_collect_results.sh
```

schreibt nach `00_results/_packages/`:

```text
00_results/_packages/results_20260820-1530.zip      <- das hier herunterladen
00_results/_packages/results_20260820-1530/
├── README.md                    Inhaltsverzeichnis + Uebersichtstabelle
├── summary.csv                  je Kombination: erwartet / gefunden / gueltig
├── yield_points_all.csv         ALLE Punkte aller Kombinationen
└── JM-25-77_sigy075/
    ├── config.json              die Config dieser Kombination
    ├── manifest.csv             die gesampelten Richtungen
    ├── parameters.txt           aufgeloeste Solver-Parameter
    ├── yield_points.csv         nur diese Kombination
    ├── mesh/                    Netzqualitaets- und Topologiereports
    └── points/                  die unveraenderten yield_run_*.json
```

`yield_points_all.csv` hat **eine Zeile je Fliesskriterium**, Spalte
`criterion`:

| `criterion` | Bedeutung |
|---|---|
| `final` | der Zustand aus `primary_criterion` — entspricht der bisherigen Auswertung |
| `eps_p_eq_macroscopic` | Rp0,2-Analogon, makroskopisches plastisches Dehnungsmass |
| `alpha_avg_material` | mittlere akkumulierte plastische Dehnung der Materialphase |
| `yielded_fraction_material` | Anteil des fliessenden Materialvolumens |

Damit lassen sich aus einem Lauf drei Fliessflaechen zeichnen, ohne die JSONs
noch einmal anzufassen. Spalten unter anderem: `eps_1..3`,
`sigma_xx/yy/zz/yz/xz/xy`, `sig_vm_avg_reduced_volume`, `strain_scale`,
`relative_density`, `stop_reason`, `criteria_missed`.

Optionen:

| Variable | Wirkung |
|---|---|
| `NAME=zwischenstand-1` | Name des Pakets statt Zeitstempel |
| `WITH_AVERAGES=1` | die vollstaendigen Zeitreihen `yield_averages_*.json` mitnehmen (deutlich groesser) |
| `WITH_LOGS=1` | SLURM `.out`/`.err` der Punkt-Jobs mitnehmen |
| `PER_COMBO_ZIP=1` | acht kleine Zips statt eines grossen |
| `NO_ZIP=1` | nur den Ordner erzeugen |
| `ONLY_DATASETS`, `ONLY_SIG_Y` | nur Teile einsammeln |

Herunterladen:

```bash
scp '<user>@<login-node>:$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS/00_results/_packages/*.zip' .
```

(Das Skript druckt die passende Zeile am Ende selbst aus.)

---

## 3. Was gegenueber 014 geaendert wurde

| Datei | Aenderung |
|---|---|
| `config.sh` | `BATCH_DATASETS`, `BATCH_SIG_Y`, `LES_RESOURCE_DIR`, `YIELD_JOB_TIME=10080`, `YIELD_JOB_PARTITION=long`, `YIELD_SURFACE_POINTS=96`, `PREP_JOB_*`, `BATCH_MAX_SUBMIT` |
| `setup_yield_surface_jobs.py` | neue Option `--job-name-prefix` (kurze, eindeutige SLURM-Jobnamen); Projektname wird aus dem Ordnernamen abgeleitet statt fest verdrahtet; `job_name` steht jetzt im `manifest.csv` |
| `setup_yield_surface_jobs.sh` | reicht `YIELD_JOB_NAME_PREFIX` durch |
| `job_yield_surface_point_CLUSTER.sh` | `run_root` enthaelt jetzt das `binning_label` — sonst wuerden sich die beiden sig_y-Varianten desselben Datensatzes denselben Arbeitsordner teilen und gegenseitig ueberschreiben. Ausserdem kopiert der Job per Default nur noch die Auswertungsdateien nach `00_results` (`KEEP_FULL_RUN_COPY=1` stellt die Vollkopie aus 014 wieder her) |
| neu | `batch_lib.sh`, `batch_create_configs.sh`, `batch_setup_jobs.sh`, `batch_create_folders_CLUSTER.sh`, `batch_submit_CLUSTER.sh`, `batch_status_CLUSTER.sh`, `batch_collect_results.sh`, `batch_collect_results.py` |

Alles andere — `A01_les_2_npy.py`, `02b`–`09`, `00_template/elastoplastic.py`,
`create_les_dataset_config.py`, die Auswertungsskripte — ist unveraendert aus 014
uebernommen.

### Speicherplatz

`00_results` bekommt in 015 nur noch die Auswertungsdateien (JSON, `parameters.txt`,
Logs, Plots), nicht mehr den kompletten Arbeitsordner mit Netz, XDMF/H5 und
Voxeldaten. Bei 768 Punkt-Jobs waere die Vollkopie aus 014 mehrere hundert GB.
Die vollstaendigen Laufordner liegen weiterhin unter
`yield_surface_runs/<dataset>/<binning_label>/<sample_id>/`.

### Feldausgabe und Zeitlimit (seit 30.08.2026)

`elastoplastic.py` schreibt **nicht mehr jeden Zeitschritt** in die XDMF/H5,
sondern hoechstens einen Snapshot je zwoelf Stunden Wandzeit
(`yield_surface.field_output.min_minutes_between_writes`) — plus erster
Zeitschritt, Fliess-Ereignisse und der letzte Zeitschritt vor einem Abbruch.
Damit die letzte Rechenzeit nicht verloren geht, kennt der Solver die Endzeit
des Jobs und **beendet sich rechtzeitig selbst**; davor schreibt er den zuletzt
gerechneten Zeitschritt als Snapshot plus `restart_meta_*.json`. Ein so
beendeter Punkt gilt bewusst als *nicht fertig* (kein `yield_run_*.json`,
Exit-Code 3, Marker `YIELD_WALLTIME_STOP` in der `.err`); die Fortsetzung
laeuft ueber `resubmit_yield_surface_timeouts_CLUSTER.sh` wie bei einem echten
Timeout. Details: `RESTART_NACH_TIMEOUT.md` und `CLAUDE_PROJECT_NOTES.md`.

---

## 4. Einzellauf (wie in 014)

Der Weg aus 014 funktioniert unveraendert weiter, wenn nur eine Kombination
gerechnet werden soll:

```bash
LES_DATASET_ID=JM-25-83_les_r2 \
LES_INPUT=/data/resources/A01_segmented/JM-25-83_80p55.leS \
LES_CONFIG_FILENAME=config-test.json \
YIELD_SIG_Y=100 \
bash create_les_config.sh

YIELD_SURFACE_BASE_CONFIG=config-test.json bash setup_yield_surface_jobs.sh 6
sbatch job_prepare_mesh_CLUSTER.sh config-test.json
```

`submit_les_pipeline_CLUSTER.sh` aus 014 liegt ebenfalls noch hier und reicht
eine einzelne Config mit ihren Punkt-Jobs ein.

---

## 5. Weiterlesen

| Datei | Inhalt |
|---|---|
| `LES_PIPELINE.md` | die Pipeline von der `.leS`-Datei bis zum Netz: Aufloesung, Randschale, SDF, Fehlerbilder |
| `FILES.md` | jede Datei dieses Ordners mit Zweck und Aufrufer |
| `CLAUDE_PROJECT_NOTES.md` | Protokoll der Entscheidungen, auch die dieser Studie |
| `PIPELINE_ANNAHMEN_DICOM_TO_FEM.md` | Algorithmen und Annahmen von den Voxeln bis zum FE-Netz |
| `CLAUDE.md` | Arbeitsweise und Ordnerkonventionen des Projekts |


## Neustart 01.09.2026: reduce=4 / 150 um / 32 Tasks / 1440 min

Die r2-Studie wurde am 01.09.2026 abgebrochen (LU/MUMPS am Speicherlimit,
Details `CLAUDE_PROJECT_NOTES.md` Session 01.09.2026). Neue Defaults in
`config.sh`: `LES_REDUCE_FACTOR=4`, `LES_MAX_ELEMENT_SIZE_UM=150`,
Randschale 6/9, `YIELD_JOB_NTASKS=32`, `YIELD_JOB_TIME=1440`, Default-Partition.
Namen: `<ds>_les_r4`, `leS-r4-sigy<XXX>`, `config-<ds>-r4-sigy<XXX>.json`.
Vor `batch_create_folders_CLUSTER.sh` den alten Jobordner auf Scratch
archivieren: `mv yield_surface_jobs yield_surface_jobs_r2_20260901`.
