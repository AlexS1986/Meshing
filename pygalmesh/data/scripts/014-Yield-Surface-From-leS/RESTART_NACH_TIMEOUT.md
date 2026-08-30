# Restart von Punkt-Jobs nach SLURM-Timeout (Studie 014)

Stand: 30.08.2026. Einige Fließflächen-Punktjobs wurden mit
`CANCELLED ... DUE TO TIME LIMIT` abgebrochen (Zeitlimit 1440 min, Partition
deflt). Dieses Dokument beschreibt den dafür eingebauten
Restart-/Resubmit-Mechanismus: abgebrochene Läufe werden **fortgesetzt**, nicht
neu gerechnet; vorhandene Ergebnisse werden nicht überschrieben.

## Idee

`elastoplastic.py` schreibt ohnehin in jedem erfolgreichen Zeitschritt `u`
(P1-Vektor), `sigma` (DP0-Tensor) und `alpha` (DP0-Skalar) in die
XDMF/HDF5-Ausgabe, und das Newton-Logfile enthält `t` und `dt` jedes Schritts.
Bei `quadrature_degree = 1` (ein Gausspunkt je Zelle, unsere Konfiguration) ist
das der **vollständige Zustand** des small-strain-J2-Modells:

```
e_p   = dev(eps(u)) − dev(sigma) / (2 µ)     (exakt, da DP0 je Zelle = Gausspunktwert)
alpha = DP0-Ausgabe von alpha                 (aus demselben Grund verlustfrei)
```

Ein neu gestarteter Job lädt also den letzten konsistenten Zeitschritt aus der
vorhandenen Ausgabe und rechnet ab `t_state + dt` weiter. Es waren **keine**
Checkpoints im ursprünglichen Lauf nötig — auch die bereits abgebrochenen Jobs
sind damit fortsetzbar.

## Geänderte / neue Dateien

| Datei | Änderung |
|---|---|
| `00_template/yield_restart.py` | **neu**: liest XDMF/HDF5-Ausgabe zurück (XML-geparst, versionsunabhängig), verifiziert die Partitionierung, rekonstruiert `e_p`/`alpha`, verwaltet `restart_meta_*.json` |
| `00_template/elastoplastic.py` | Restart-Erkennung beim Start; schreibt je erfolgreichem Schritt `restart_meta_<base>.json` (t, dt, `yield_states`, `averaged_history`); Fortsetzungen schreiben in neue Dateien `..._rN.xdmf`; Log-/Graphdateien werden fortgeschrieben statt gelöscht; übergibt `trestart` an den Solver (wichtig: sonst fiele `t` nach einem nicht konvergierten ersten Fortsetzungsschritt auf ~0 zurück); Optionen `--fresh`, `--restart-meta-every` |
| `job_yield_surface_point_CLUSTER.sh` | löscht den Zielordner **nicht** mehr, wenn dort ein Rechenstand liegt (`elastoplastic_*.xdmf` / `restart_meta_*.json`); aktualisiert dann nur die Skripte. Überspringt den Solver, wenn `yield_run_<mat>_<richtung>.json` schon existiert. `YS_FORCE_FRESH=1` erzwingt das alte Verhalten (alles löschen, neu rechnen) |
| `resubmit_yield_surface_timeouts_CLUSTER.sh` | **neu**: findet Timeout-Jobs und reicht je Punkt eine Restart-Kette ein |

## Bedienung auf dem Cluster

1. Geänderten 014-Ordner wie gewohnt nach `$HPC_SCRATCH` synchronisieren
   (derselbe Weg wie beim Einrichten der Studie, z. B. über
   `02_create_folders_CLUSTER.sh`; wichtig sind `00_template/`,
   `job_yield_surface_point_CLUSTER.sh` und das Resubmit-Skript).
2. Einmalig prüfen, dass der Simulationscontainer h5py hat (wird zum
   Zurücklesen der HDF5-Ausgabe gebraucht):

   ```bash
   apptainer exec "$HOME/dolfinx_alex/alex-dolfinx.sif" python3 -c "import h5py; print(h5py.version.version)"
   ```
3. Erst ansehen, was passieren würde, dann einreichen:

   ```bash
   cd "$HPC_SCRATCH/pygalmesh/data/scripts/014-Yield-Surface-From-leS"
   DRY_RUN=1 ./resubmit_yield_surface_timeouts_CLUSTER.sh          # nur anzeigen
   ./resubmit_yield_surface_timeouts_CLUSTER.sh                     # einreichen
   ```

   Optional: `./resubmit_...sh yield_surface_jobs/n192` schränkt auf einen
   Jobsatz ein; `MAX_CHAIN=8` verlängert die Kette; `INCLUDE_FAILED=1` nimmt
   auch Jobs mit, deren letzter Abbruch kein Timeout war.

Das Skript klassifiziert jeden `ys_*`-Punkt: **fertig** (Zusammenfassung liegt
unter `00_results/...`), **läuft** (Job/Kette mit diesem Namen in `squeue`),
**Timeout**, **anderer Fehler**, **nie gestartet** — und reicht nur die
Timeout-Fälle neu ein.

## Automatisches Weiter-Einreichen (Kette)

Je Punkt werden `MAX_CHAIN` (Default 5) Jobs eingereicht: der erste sofort,
jeder weitere mit `--dependency=afternotok:<Vorgänger>` und
`--kill-on-invalid-dep=yes`. Damit gilt, ohne manuelles Zutun:

- Bricht ein Glied am Zeitlimit ab → das nächste startet und **setzt fort**.
- Läuft ein Glied erfolgreich durch → die restlichen Glieder werden von SLURM
  automatisch entfernt (`DependencyNeverSatisfied` + kill-on-invalid-dep).
- Scheitert ein Glied aus einem anderen Grund → das nächste Glied versucht es
  erneut; ist der Fehler reproduzierbar, schlagen die restlichen Glieder schnell
  fehl und die Kette endet (kein Endlos-Loop, begrenzt durch `MAX_CHAIN`).
- Jedes Glied läuft mit dem unveränderten Zeitlimit des Punkt-Jobskripts
  (`-t 1440`), es ist also keine Partition/Policy-Änderung nötig.

Reichen `MAX_CHAIN` Glieder nicht, das Resubmit-Skript einfach **erneut
aufrufen** — es erkennt fertige und laufende Punkte und reicht nur nach, was
fehlt. Manuell für einen einzelnen Punkt geht ebenso:
`sbatch yield_surface_jobs/n192/ys_.../job_ys_..._CLUSTER.sh` (der Restart
passiert im Job automatisch).

## Was der Restart genau macht

1. `elastoplastic.py` prüft zuerst, ob `yield_run_<mat>_<richtung>.json` schon
   existiert → dann sofort Exit 0 (macht Kettenglieder idempotent).
2. `yield_restart.try_restore()` sucht die jüngste lesbare Ausgabe
   (`..._rN.xdmf` absteigend, dann die Basisdatei), bevorzugt den Zeitschritt
   aus `restart_meta_*.json`, sonst den letzten gemeinsamen Zeitschritt von
   `u`/`sigma`/`alpha`. Nicht lesbare Zeitschritte (z. B. HDF5 beim Kill
   mitten im Schreiben beschädigt) werden übersprungen → nächst älterer.
3. **Verifikation statt blindem Vertrauen:** Die Knotenkoordinaten und die
   Zell-Konnektivität der alten HDF5-Ausgabe müssen exakt zur globalen
   Nummerierung des neuen Laufs passen (gleiches Netz, gleiche Prozesszahl,
   gleicher Container ⇒ reproduzierbare Partitionierung). Passt es nicht,
   bricht der Lauf mit klarer Meldung ab — es wird nie ein falscher Zustand
   geladen.
4. Zustand setzen: `u`, `um1`, `alpha`, `e_p` (rekonstruiert), `t`, `dt`
   (aus Meta bzw. Newton-Logfile), `yield_states`/`averaged_history` aus der
   Meta-Datei. Fortsetzung schreibt in `..._r1.xdmf`, `..._r2.xdmf`, …;
   Newton-Logfile und Graphdatei werden mit `# restart N:`-Markerzeile
   fortgeschrieben (der Plot-Parser überliest `#`-Zeilen).

## Randbedingungen und Einschränkungen

- **Gleiche MPI-Prozesszahl wie der Originallauf** (steht im Punkt-Jobskript,
  `#SBATCH -n 64` — beim Resubmit desselben Skripts automatisch erfüllt).
  Abweichungen werden erkannt und abgelehnt.
- Gilt für `quadrature_degree = 1` (unsere Configs). Bei anderem Grad wird der
  Restart übersprungen und von vorne gerechnet (DP0-Ausgabe wäre nicht
  verlustfrei).
- Für die **bereits abgebrochenen** Läufe existiert noch keine Meta-Datei:
  `yield_states`/`averaged_history` beginnen dann beim Resume. Ein Kriterium,
  das schon vor dem Abbruch überschritten war, wird im ersten fortgesetzten
  Schritt erneut registriert — also geringfügig **später** (konservativ,
  Werte wachsen monoton). Ab jetzt schreibt jeder Lauf die Meta-Datei je
  Schritt, künftige Fortsetzungen sind damit verlustfrei inkl. Historie.
- `hard = 0` und `sig_y` konstant (unsere Materialsätze) — `alpha` geht dann
  nicht in die Spannung ein; die Rekonstruktion über `u`/`sigma`/`alpha` ist
  auch mit Hardening korrekt, solange DP0 verlustfrei ist (deg 1).
- Die Fortsetzung beginnt bei `t_state + dt` mit dem zuletzt erfolgreichen
  `dt`; ein evtl. Scale-up des Originallaufs nach dem letzten Schritt geht
  verloren (harmlos, nur minimal kleinere Schritte direkt nach dem Resume).
- Jede Fortsetzung erzeugt eine eigene `..._rN.xdmf`-Datei; die Feldhistorie
  ist also über mehrere Dateien verteilt. Die Auswertung
  (`collect_yield_surface_points.py` etc.) nutzt nur die JSONs und ist nicht
  betroffen.

## Übertragen auf Studie 015

**Erledigt (30.08.2026):** Die Template-Dateien (`elastoplastic.py`,
`yield_restart.py`) liegen byteidentisch in `015-…/00_template/`, das
015-Job-Skript hat denselben Restart-Block, und
`015-…/resubmit_yield_surface_timeouts_CLUSTER.sh` ist an die Batch-Struktur
angepasst (Kombinationsordner, Jobnamen aus `#SBATCH -J`). 015-Besonderheiten:
`RESTART_NACH_TIMEOUT.md` im 015-Ordner.
