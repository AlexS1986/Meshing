# Restart von Punkt-Jobs nach SLURM-Timeout (Studie 015, Batch)

Stand: 30.08.2026. Der Restart-Mechanismus aus Studie 014 ist hier übernommen.
**Konzept, Funktionsweise, Annahmen und Einschränkungen: siehe
`../014-Yield-Surface-From-leS/RESTART_NACH_TIMEOUT.md`** — dieses Dokument
beschreibt nur die 015-Besonderheiten (Batch-Struktur).

Kurzfassung des Konzepts: `elastoplastic.py` schreibt je Zeitschritt u, sigma
und alpha in die XDMF/HDF5-Ausgabe; bei `quadrature_degree = 1` ist daraus der
komplette Zustand exakt rekonstruierbar (`e_p = dev(eps(u)) − dev(sigma)/(2µ)`).
Ein neu eingereichter Punkt-Job setzt deshalb automatisch dort fort, wo der
abgebrochene aufgehört hat — auch ohne dass der alte Lauf Checkpoints
geschrieben hätte. Zusätzlich schreibt jeder Lauf jetzt je Schritt eine kleine
`restart_meta_*.json` (t, dt, `yield_states`, Historie), womit künftige
Fortsetzungen auch die Kriterien-Historie verlustfrei behalten.

## Beteiligte Dateien in 015

| Datei | Rolle |
|---|---|
| `00_template/elastoplastic.py` | restart-fähiger Solver (identisch mit 014) |
| `00_template/yield_restart.py` | Restart-Logik (identisch mit 014) |
| `job_yield_surface_point_CLUSTER.sh` | löscht den Zielordner unter `yield_surface_runs/<run_id>/<binning_label>/<sample>/` nicht mehr, wenn dort ein Rechenstand liegt; `YS_FORCE_FRESH=1` erzwingt Neustart. Der Slim-Copy-Default (`KEEP_FULL_RUN_COPY=0`) bleibt unverändert |
| `resubmit_yield_surface_timeouts_CLUSTER.sh` | findet Timeout-Punkte über alle 8 Kombinationen und reicht je Punkt eine Restart-Kette ein |

## Bedienung auf dem Cluster

```bash
# 1. 015 wie gewohnt nach $HPC_SCRATCH bringen
data/scripts/015-Yield-Surface-Batch-leS/batch_create_folders_CLUSTER.sh

# 2. einmalig: h5py im Simulationscontainer pruefen
apptainer exec "$HOME/dolfinx_alex/alex-dolfinx.sif" python3 -c "import h5py; print(h5py.version.version)"

# 3. ansehen, dann einreichen
cd "$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS"
DRY_RUN=1 ./resubmit_yield_surface_timeouts_CLUSTER.sh
./resubmit_yield_surface_timeouts_CLUSTER.sh
```

Optionen wie in 014: `MAX_CHAIN` (Default 5 Jobs je Kette),
`INCLUDE_FAILED=1`, `DRY_RUN=1`. Einschränken auf eine Kombination oder einen
Jobsatz über das Argument, z. B.:

```bash
./resubmit_yield_surface_timeouts_CLUSTER.sh yield_surface_jobs/JM-25-77_sigy075
./resubmit_yield_surface_timeouts_CLUSTER.sh yield_surface_jobs/JM-25-83_sigy100/n096
```

## 015-Besonderheiten

- **Ordnerstruktur:** Punkt-Jobs liegen unter
  `yield_surface_jobs/<combo>/<nNNN>/ys_*/`; das Skript durchsucht alle
  Kombinationen. Arbeitsordner ist
  `yield_surface_runs/<run_id>/<binning_label>/<sample>/` (das binning label
  trennt die beiden sig_y-Varianten).
- **Jobnamen:** in 015 heißen die Jobs `<dataset>_s<sig_y>-ysNNN` (nicht
  sample_id); das Resubmit-Skript liest den Namen aus der `#SBATCH -J`-Zeile
  des Punkt-Jobskripts und prüft damit gegen `squeue` (kein Doppel-Einreichen).
- **Fertig-Erkennung:** `yield_run_<mat>_<richtung>.json` unter
  `00_results/<run_id>/<binning_label>/yield_surface/<sample>-<mat>-<richtung>/`
  (funktioniert für Slim- und Vollkopie). Liegt die Zusammenfassung nur im
  Arbeitsordner (Job starb nach dem Solver, vor der Ergebniskopie), wird der
  Punkt neu eingereicht — der Solver beendet sich dann sofort (Exit 0) und der
  Job holt nur die Ergebniskopie nach.
- **Zeitlimit:** jedes Kettenglied läuft mit den unveränderten
  SBATCH-Einstellungen seines Punkt-Jobskripts (in 015 je nach Erzeugung z. B.
  `-t 10080` auf `long`); es wird nichts an Partition oder Limit geändert.
- `batch_status_CLUSTER.sh` funktioniert unverändert (JSONs und Queue-Namen
  sind unberührt); `batch_submit_CLUSTER.sh` bleibt das Werkzeug für die
  Erst-Einreichung, das Resubmit-Skript das für Wiederanläufe.

## Ergänzung 30.08.2026: ausgedünnte Feldausgabe und Wandzeit-Deadline

Die Feldausgabe ist zugleich der Checkpoint, deshalb hängen beide Themen
zusammen (Herleitung und alle Details: `CLAUDE_PROJECT_NOTES.md`, Abschnitt
„Session 30.08.2026 (2)").

- **Nicht mehr jeder Zeitschritt.** `elastoplastic.py` schreibt höchstens alle
  `yield_surface.field_output.min_minutes_between_writes` Minuten Wandzeit
  einen Snapshot (Default **720 = 12 h**), zusätzlich immer den ersten Schritt,
  jedes erstmalige Erreichen eines Fließkriteriums und den letzten Schritt vor
  einem Abbruch. Der Restart wird dadurch gröber: verloren gehen höchstens die
  Zeitschritte seit dem letzten Snapshot.
- **`restart_meta_*.json` wird nur zusammen mit einem Snapshot geschrieben**,
  sonst zeigte sie auf einen Zeitschritt, der nicht in der XDMF steht.
  `--restart-meta-every` ist damit wirkungslos.
- **Kontrolliertes Beenden vor dem Zeitlimit.** Der Solver kennt die
  Job-Endzeit (`YIELD_WALLTIME_DEADLINE_EPOCH`, gesetzt vom Punkt-Jobskript aus
  `SLURM_JOB_END_TIME` bzw. `squeue`) und stoppt, sobald
  `Restzeit <= safety_margin_minutes + reserve_factor * (Dauer Zeitschritt + Dauer Schreiben)`.
  Davor schreibt er den zuletzt gerechneten Zeitschritt als Snapshot plus
  Restart-Meta. Abschalten: `--no-walltime-stop` bzw.
  `walltime.stop_before_deadline = false`.
- **Der Lauf gilt dann nicht als fertig:** kein `yield_run_*.json`, Exit-Code 3,
  Marker `YIELD_WALLTIME_STOP` in der `.err`-Datei. Die `afternotok`-Kette läuft
  damit weiter, und `resubmit_yield_surface_timeouts_CLUSTER.sh` behandelt den
  Marker wie einen echten Timeout.
- **`u`, `sigma`, `alpha` bleiben Pflichtfelder** in `field_output.fields` —
  ohne sie ist kein Restart möglich; abwählbar ist nur `sig_vm`.
