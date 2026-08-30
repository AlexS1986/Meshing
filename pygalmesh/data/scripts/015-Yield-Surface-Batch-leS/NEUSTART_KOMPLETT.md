# Kompletter Neustart von 015 auf dem Cluster (ohne Restart alter Läufe)

Stand: 30.08.2026. Anlass: der Stand vom 30.08.2026 (ausgedünnte Feldausgabe,
Wandzeit-Deadline, `-t 10080` auf `long`, Snapshot-Abstand 12 h) soll für **alle
768 Punkt-Jobs von Grund auf** gerechnet werden — kein Fortsetzen der Läufe, die
mit dem alten Stand begonnen wurden.

**Warum überhaupt aufräumen?** Seit dem Restart-Umbau ist der Punkt-Job
*idempotent*: liegt im Arbeitsordner ein Rechenstand
(`elastoplastic_*.xdmf` / `restart_meta_*.json`), wird er **fortgesetzt** statt
gelöscht; liegt bereits ein `yield_run_*.json`, wird der Solver **übersprungen**.
Beides ist beim Wiederanlauf erwünscht und beim Neustart genau falsch. Ein
Neustart heißt deshalb: alte Läufe und Ergebnisse wegräumen *und* zur Sicherheit
`YS_FORCE_FRESH=1` setzen.

---

## Schritt für Schritt (alles auf dem Login-Node)

Abkürzung für die folgenden Blöcke:

```bash
H="$HOME/meshing/Meshing/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS"
S="$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS"
```

### 1. Alte Jobs abbrechen — zuerst, sonst schreiben sie in die neuen Ordner

Wichtig wegen der `afterok`/`afternotok`-Ketten: ein einzelnes `scancel` auf
einen laufenden Job lässt das nächste Kettenglied ggf. anlaufen.

```bash
squeue -u "$USER"
scancel -u "$USER"          # oder gezielt: scancel -u "$USER" -n <jobname>
squeue -u "$USER"           # muss leer sein
```

### 2. Alten Stand sichern (optional, aber billig)

```bash
NAME=vor-neustart-30-08 "$S/batch_collect_results.sh"
# ergibt 00_results/_packages/vor-neustart-30-08.zip
mkdir -p "$HOME/015_archiv"
mv "$S"/00_results/_packages/*.zip "$HOME/015_archiv/"    # aus 00_results heraus, das gleich geloescht wird
```

### 3. Prüfen, dass HOME wirklich den neuen Stand hat

```bash
cd "$H" && git log --oneline -3
grep -n 'min_minutes_between_writes' config-JM-25-77-r2-sigy075.json   # 720.0
grep -n 'YIELD_JOB_TIME\|YIELD_JOB_PARTITION' config.sh                # 10080 / long
grep -n 'walltime_deadline' 00_template/elastoplastic.py | head -3
```

### 4. Auf dem Scratch aufräumen — Netze behalten

Die vorbereiteten Netze liegen in `<dataset>_les_r2_segmented/…/subvolume_x*_y*/`
und hängen **nicht** von sig_y, Feldausgabe oder Zeitlimit ab. Sie werden
behalten; das spart vier `mem`-Jobs.

```bash
du -sh "$S/yield_surface_runs" "$S/00_results" 2>/dev/null
rm -rf "$S/yield_surface_runs"     # Arbeitsordner = der Rechenstand
rm -rf "$S/00_results"             # Fertig-Marker der Punkte (Zips aus Schritt 2 sind gesichert)
rm -rf "$S/yield_surface_jobs"     # alte Jobskripte + alte .out/.err
rm -f  "$S"/prep-*.out.* "$S"/prep-*.err.*
```

> `rsync` läuft mit `-av --update` und **ohne** `--delete` — es löscht auf dem
> Scratch nichts und überschreibt nichts, was dort neuer ist. Deswegen muss der
> alte Kram von Hand weg. Frisch per `git pull` geholte Dateien haben die
> Checkout-Zeit als mtime und sind damit neuer als die Scratch-Kopie; sie werden
> also übertragen.

Soll auch neu vernetzt werden (hier nicht nötig), zusätzlich
`rm -rf "$S"/*_les_r2_segmented` und später `AUTO_SKIP_PREPARE=0`.

### 5. Configs und Punkt-Jobs neu erzeugen und synchronisieren

```bash
cd "$HOME/meshing/Meshing/pygalmesh"
data/scripts/015-Yield-Surface-Batch-leS/batch_create_folders_CLUSTER.sh
```

Das erzeugt die acht Configs (`batch_create_configs.sh`), die 8 × 96 Punkt-Jobs
(`batch_setup_jobs.sh`) und synchronisiert nach `$HPC_SCRATCH`. **Auf dem
Login-Node ausführen** — nur dort ist `HPC_SCRATCH` gesetzt, und nur dann bekommen
die Jobskripte ihre `-e/-o`-Zeilen.

### 5a. Wo das Zeitlimit der Punkt-Jobs herkommt

`-t` steht **fest im SBATCH-Header jedes Punkt-Jobskripts** und wird beim
Erzeugen hineingeschrieben — es gibt keinen Schalter beim Einreichen. Die Kette:

```text
config.sh: YIELD_JOB_TIME=10080, YIELD_JOB_PARTITION=long
  -> batch_setup_jobs.sh
     -> setup_yield_surface_jobs.sh  (--job-time / --job-partition)
        -> setup_yield_surface_jobs.py  ->  "#SBATCH -t 10080" / "#SBATCH -p long"
```

Das heisst: **`batch_setup_jobs.sh` neu laufen lassen** (steckt in
`batch_create_folders_CLUSTER.sh` aus Schritt 5 schon drin), sonst tragen die
alten `job_ys_*_CLUSTER.sh` weiter das alte Limit.

```bash
cd "$H"
grep -n 'YIELD_JOB_TIME\|YIELD_JOB_PARTITION' config.sh   # 10080 / long
bash batch_setup_jobs.sh                                   # alle 8 x 96 neu
# ohne config.sh anzufassen ginge auch:
# YIELD_JOB_TIME=10080 YIELD_JOB_PARTITION=long bash batch_setup_jobs.sh
```

Auf dem Login-Node ausfuehren: nur mit gesetztem `HPC_SCRATCH` bekommen die
Skripte ihre `#SBATCH -e/-o`-Zeilen.

Was bewusst bei **1440** bleibt (alles Netz- bzw. Hilfsjobs, keine Rechenlaeufe):

| Stelle | Job |
|---|---|
| `job_prepare_mesh_CLUSTER.sh`, `run_prepare_mesh_CLUSTER.sh` (`#SBATCH -t 1440`) | Netzvorbereitung |
| `batch_submit_CLUSTER.sh`: `--time="${PREP_JOB_TIME:-1440}"` | ueberschreibt den Header der Netzvorbereitung; `PREP_JOB_TIME=2880` bei Bedarf |
| `setup_yield_surface_jobs.py:117` (`submit_all_yield_surface_points.sh`) | reicht nur ein, rechnet nichts — `batch_submit_CLUSTER.sh` benutzt es gar nicht |

Die `srun`-Steps im Punkt-Job erben Zeit und Speicher des Jobs
(`SRUN_TIME`/`SRUN_MEM_PER_CPU` sind leer) — sonst wuerden sie auf `long` nach
24 h abgeschnitten.

### 6. Kontrolle auf dem Scratch, bevor 768 Jobs starten

```bash
cd "$S"
grep -h '^#SBATCH -t' yield_surface_jobs/*/n096/ys_*/job_*.sh | sort | uniq -c   # 768 x -t 10080
grep -h '^#SBATCH -p' yield_surface_jobs/*/n096/ys_*/job_*.sh | sort | uniq -c   # 768 x -p long
grep -c min_minutes_between_writes yield_surface_jobs/*/n096/ys_000*/config.json | head
ls -1 "$S"/*_segmented/*_3D/subvolume_x*_y*/dlfx_mesh.xdmf                  # 4 Netze da?
ls -1 "$S"/yield_surface_jobs/*/n096/ys_*/job_*.sh | wc -l                  # 768
apptainer exec "$HOME/dolfinx_alex/alex-dolfinx.sif" python3 -c "import h5py; print(h5py.version.version)"
```

### 7. Einreichen

```bash
DRY_RUN=1 "$S/batch_submit_CLUSTER.sh" | head -40
YS_FORCE_FRESH=1 "$S/batch_submit_CLUSTER.sh"
```

* `YS_FORCE_FRESH=1` wird von `sbatch` (Default `--export=ALL`) in jeden
  Punkt-Job vererbt und schaltet dort beide Idempotenz-Pfade ab: vorhandener
  Rechenstand wird verworfen (`rm -rf`), vorhandenes `yield_run_*.json` wird
  ignoriert. Nach Schritt 4 ist es Redundanz — und genau deshalb sinnvoll.
* Die vier Netzvorbereitungen werden automatisch übersprungen
  (`AUTO_SKIP_PREPARE=1`, Netz vorhanden), die Punkt-Jobs laufen dann ohne
  `--dependency`.
* Queue-Prüfung: 768 < `BATCH_MAX_SUBMIT=1000`, passt in einem Rutsch — nur wenn
  noch Fremdjobs in der Queue stehen, in zwei Hälften einreichen
  (`ONLY_SIG_Y=100` … dann `ONLY_SIG_Y=75`).

> **`YS_FORCE_FRESH` gehört nur an diese eine Erst-Einreichung.**
> `resubmit_yield_surface_timeouts_CLUSTER.sh` später **ohne** die Variable
> aufrufen, sonst rechnet jede Fortsetzung wieder bei null los.

### 8. Den ersten Job kontrollieren (der noch ungetestete Teil)

Feldausgabe-Ausdünnung und Deadline-Wache sind bisher nur außerhalb des
Containers mit Stubs getestet. Am ersten laufenden Punkt-Job also nachsehen:

```bash
"$S/batch_status_CLUSTER.sh"
J=$(ls -t "$S"/yield_surface_jobs/*/n096/ys_*/*.out.* | head -1); echo "$J"
grep -n -A14 '=== Feldausgabe / Wandzeit ===' "$J"
grep -n 'FIELDOUT' "$J" | head
```

Erwartet: `field_output_min_minutes_between_writes: 720.0`,
`walltime_deadline: <Zeitpunkt> (noch ~10000 min)` und **nicht**
`walltime_deadline: unbekannt`. Später dann `[FIELDOUT] Snapshot …`-Zeilen im
12-Stunden-Takt.

---

## Kurzfassung — ein Block zum Kopieren (Login-Node)

```bash
set -e
H="$HOME/meshing/Meshing/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS"
S="$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS"

# 1) alte Jobs abbrechen (zuerst - sonst laufen afterok/afternotok-Ketten nach)
squeue -u "$USER"; read -r -p "scancel -u $USER ? [Enter]" _; scancel -u "$USER" || true
sleep 5; squeue -u "$USER"

# 2) alten Stand sichern und aus 00_results herausholen
NAME=vor-neustart-30-08 "$S/batch_collect_results.sh" || true
mkdir -p "$HOME/015_archiv"; mv "$S"/00_results/_packages/*.zip "$HOME/015_archiv/" 2>/dev/null || true

# 3) HOME-Stand pruefen
cd "$H"; git log --oneline -3
grep -n 'min_minutes_between_writes' config-JM-25-77-r2-sigy075.json   # 720.0
grep -n 'YIELD_JOB_TIME\|YIELD_JOB_PARTITION' config.sh                # 10080 / long

# 4) Scratch aufraeumen - *_les_r2_segmented (die 4 Netze) bleiben liegen
du -sh "$S/yield_surface_runs" "$S/00_results" 2>/dev/null || true
read -r -p "yield_surface_runs, 00_results, yield_surface_jobs loeschen? [Enter]" _
rm -rf "$S/yield_surface_runs" "$S/00_results" "$S/yield_surface_jobs"
rm -f  "$S"/prep-*.out.* "$S"/prep-*.err.*

# 5) Configs + 768 Punkt-Jobs neu erzeugen (setzt -t 10080 / -p long) und syncen
cd "$HOME/meshing/Meshing/pygalmesh"
data/scripts/015-Yield-Surface-Batch-leS/batch_create_folders_CLUSTER.sh

# 6) Kontrolle vor dem Einreichen
cd "$S"
grep -h '^#SBATCH -t' yield_surface_jobs/*/n096/ys_*/job_*.sh | sort | uniq -c   # 768 x -t 10080
grep -h '^#SBATCH -p' yield_surface_jobs/*/n096/ys_*/job_*.sh | sort | uniq -c   # 768 x -p long
grep -l 'min_minutes_between_writes' yield_surface_jobs/*/n096/ys_*/config.json | wc -l   # 768
ls -1 "$S"/*_segmented/*_3D/subvolume_x*_y*/dlfx_mesh.xdmf                       # 4 Netze
ls -1 yield_surface_jobs/*/n096/ys_*/job_*.sh | wc -l                            # 768
apptainer exec "$HOME/dolfinx_alex/alex-dolfinx.sif" python3 -c "import h5py; print(h5py.version.version)"

# 7) einreichen (erst trocken, dann echt) - AUS $S HERAUS, sonst scheitert die
#    Netzvorbereitung: sie erbt das Absende-Verzeichnis, und Apptainer sieht die
#    Host-Pfade unter /work/scratch nur ueber das eingehaengte CWD.
cd "$S"
DRY_RUN=1 "$S/batch_submit_CLUSTER.sh" | head -40
read -r -p "768 Punkt-Jobs jetzt einreichen? [Enter]" _
YS_FORCE_FRESH=1 "$S/batch_submit_CLUSTER.sh"

# 8) ersten laufenden Punkt-Job kontrollieren (Deadline-Wache, erster echter Containerlauf)
"$S/batch_status_CLUSTER.sh"
J=$(ls -t "$S"/yield_surface_jobs/*/n096/ys_*/*.out.* 2>/dev/null | head -1); echo "$J"
grep -n -A14 '=== Feldausgabe / Wandzeit ===' "$J"    # walltime_deadline darf nicht "unbekannt" sein
grep -n 'FIELDOUT' "$J" | head
```

`YS_FORCE_FRESH=1` gehoert nur an diese Erst-Einreichung, nie an
`resubmit_yield_surface_timeouts_CLUSTER.sh`.
