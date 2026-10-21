# Übergabe an Claude Code (lokal im Mac-Terminal, Arbeit auf dem Cluster per ssh) — 1D-Druckversuche JM-25-71 (Studie 017)

Du läufst **auf dem Mac** im Ordner `~/Work/Hypo/Hypo/Simulation/Meshing/pygalmesh/data/scripts/017-Yield-Surface-Batch-leS-nohinge`
(Git-Wurzel `~/Work/Hypo/Hypo/Simulation/Meshing`, Remote `AlexS1986/Meshing`, Branch `main`) und managst Simulationen auf dem
Lichtenberg-Cluster. Lies zuerst `CLAUDE.md` (Abschnitt 0 Transferregel, Abschnitt 1 Pfade) und die Einträge vom 20./21.10.2026 in `CLAUDE_PROJECT_NOTES.md`.

**Cluster-Zugang:** `ssh lcluster13.hrz.tu-darmstadt.de` (User und Key stehen in `~/.ssh/config`; Ersatz `lcluster20.hrz.tu-darmstadt.de`).
Jeden Cluster-Befehl so ausführen: `ssh lcluster13.hrz.tu-darmstadt.de 'bash -lc "…"'` (Login-Shell, damit `$HPC_SCRATCH` gesetzt ist).
Mehrere Kommandos pro ssh-Aufruf bündeln. Für wiederholte Aufrufe ControlMaster nutzen, falls in `~/.ssh/config` erlaubt:
`ssh -o ControlMaster=auto -o ControlPath=~/.ssh/cm-%r@%h:%p -o ControlPersist=2h lcluster13.hrz.tu-darmstadt.de true` einmal, danach läuft alles über die Verbindung.
Kleine Ergebnisdateien holen: `scp lcluster13.hrz.tu-darmstadt.de:<pfad> compression_jobs/ergebnisse/` (nur JSON/CSV/PNG/TXT, keine H5/XDMF).
Skript-/Doku-Änderungen gehen **nur** über Git: lokal ändern → commit → push → `ssh … 'bash -lc "cd ~/meshing/Meshing && git pull && SKIP_GENERATE=1 pygalmesh/data/scripts/017-Yield-Surface-Batch-leS-nohinge/batch_create_folders_CLUSTER.sh"'`.

## Feste Regeln
1. **Nichts abbrechen, nichts neu einreichen ohne Rückfrage**, außer dem Ketten-Fall unter „Aufgaben 4". `scancel` nur nach ausdrücklicher Freigabe.
2. Rechnen nur auf Account **p0023647** (nie l0003507). Keine neuen Studien anlegen.
3. **Transfer nur über Git** (siehe oben). Niemals Dateien auf dem Scratch direkt editieren (rsync `--update` würde sie später nicht mehr überschreiben).
   Ergebnisdateien (JSON, CSV, PNG) per scp nach `compression_jobs/ergebnisse/` holen und mit committen (klein halten: keine H5/XDMF).
4. **Alles dokumentieren** in `CLAUDE_PROJECT_NOTES.md` (Abschnitt „21.10.2026 — Druckversuche, Cluster-Session"), mit Uhrzeit, Job-IDs, Zahlen. Committen.
5. Python auf dem Login-Node: `cd $S017 && apptainer exec --bind /work/scratch/as12vapa $HOME/dolfinx_alex/alex-dolfinx.sif python3 …` (innerhalb des ssh-Aufrufs). Auswertung alternativ lokal auf dem Mac mit den per scp geholten Dateien (`python3 evaluate_compression_run.py …`, braucht numpy; matplotlib für `--plot`).
6. Keine Hostnamen raten. Den Nutzer nichts kopieren lassen — alles selbst per ssh/scp/Git erledigen.

## Lage (Stand 21.10.2026 08:50)
```
S017=$HPC_SCRATCH/pygalmesh/data/scripts/017-Yield-Surface-Batch-leS-nohinge
R=$S017/yield_surface_runs/JM-25-71_les_r4_druckx    bzw. …_drucky
```
| Richtung | Netz | σ_y | Jobs (Kette à 3 × 24 h) | Stand |
|---|---|---|---|---|
| x | JM-25-71_les_r4_druckx, 3,90 Mio. Tets, ρ 0,189, Platten x (0,4 mm), A = 342,68 mm² | 75 / 100 / 180 | 55498714-716 / 720-722 / 717-719 | Glieder 1 laufen seit 20.10. 15:40 (alte Template-Kopie: **kein** `_averages.txt`, Historie erst im JSON am Walltime-Stopp ≈ 21.10. 15:40) |
| y | JM-25-71_les_r4_drucky, 3,99 Mio. Tets, Platten y (0,6 mm), A ≈ 341 mm² | 75 / 100 / 180 | 55499944-946 / 950-952 / 947-949 | Prep 55499943 fertig 21.10. früh; Glieder 1 starten/laufen mit neuem Template → `elastoplastic_std_y_averages.txt` live |

Physik der Läufe: Kleindehnung, ideal plastisch (E 70 GPa, ν 0,35), Platten haftend (u = ε·x auf dem Plattenband), Seitenflächen frei,
ε_axial = −0,25·t, Ende bei total_time 0,1 (= 2,5 % Stauchung), kein Abbruch am Fließbeginn. Exit 3 = kontrollierter Walltime-Stopp, nächstes Glied setzt fort (Restart-Sprung +1,3 % möglich).
**Nennspannung = Volumenmittel σ̄_aa** (`sigma_avg_reduced_volume[a][a]`, `_averages.txt` Spalte sig_aa). Die Plattenreaktion in `*_graphs.txt` ist unbrauchbar (Eigenspannung der Platte).

## Aufgaben
1. **Status** (alle 1–2 h, bis alle Ketten fertig oder du gestoppt wirst):
   `squeue -u $USER -o "%.10i %.24j %.8T %.10M %R" | grep druck`; `sacct -u $USER -S 2026-10-20 -X -o JobID,JobName%26,State,Elapsed,ExitCode | grep druck`.
   Fortschritt: `awk '!/^#/{t=$1} END{printf "t=%.4f eps=%.3f %% n=%d\n",t,25*t,NR-1}' <lauf>/subvolume_x0_y0/elastoplastic_std_<a>_graphs.txt`.
2. **Erstkontrolle jedes neu gestarteten Glieds** im `*.out.<jobid>` unter `compression_jobs/<combo>/ys_druck_<a>/`:
   `dirichlet_faces` = nur die beiden Platten der Lastachse, `cross_section_area_perp_to_loading_axis` ≈ 343 (x) / 341 (y), `reduced_volume_material` ≈ 1204 (x), kein MUMPS-Fehler, Newton-Iterationen ≤ 12.
   „NO CONVERGENCE => dt“ ist normal (Schrittweitensteuerung). `*.err.*` auf echte Fehler prüfen (Traceback, MUMPS INFO(1) < 0, NaN).
3. **Auswertung**, sobald Daten da sind (y live, x nach JSON):
   `python3 $S017/evaluate_compression_run.py --axis y $R_y/leS-r4-drucky-sigy*/ys_druck_y/subvolume_x0_y0/elastoplastic_std_y_averages.txt`
   `python3 $S017/evaluate_compression_run.py $R_x/leS-r4-druckx-sigy*/ys_druck_x/subvolume_x0_y0/yield_averages_std_x.json --plot $S017/compression_jobs/druck_71.png`
   Prüfen: `max_quer_zu_axial` ≲ 0,05 (freie Seitenflächen), Verlauf monoton. Kennwerte je Lauf in eine Tabelle (E_10_40, Rp0,2, σ bei 0,5/1,0/1,25/2,5 %, erreichte Dehnung) → `compression_jobs/ergebnisse/kennwerte_druck_71.md` + CSVs; committen.
   Vergleichswerte dazuschreiben: Versuch Rp0,2 7,7 / σ_max 11,2 / Plateau 9,6 MPa (E 1760); KUBC-Fläche σ̄_y^⊥ 6,40 (75) / 8,41 (100) / 14,5 (180, Skalierung m 0,93), E_⊥ 4440 MPa bei ρ 0,177 (Druckmodell ρ 0,189: Dichtekorrektur ρ^1,75 ≈ +12 %, ρ^2 ≈ +14 %); A01-FFT Plateau 4,5 MPa (75).
4. **Ketten**: Endet das letzte Glied einer Kette mit Exit 3 (Walltime) vor 2,5 % Dehnung → genau ein weiteres Glied nachreichen:
   `sbatch -A p0023647 --error=<dir>/%x.err.%j --output=<dir>/%x.out.%j <dir>/job_ys_druck_<a>_CLUSTER.sh` (Restart ist automatisch). Endet ein Glied mit anderem Exit-Code → Log sichern, **nicht** neu einreichen, Nutzer informieren.
5. **Abschlussbericht** (kurz, Stichpunkte, Zahlen): Tabelle Kennwerte x/y × 75/100/180, Verhältnisse 1D/KUBC (roh und dichtekorrigiert), x/y-Verhältnis, Kernstunden (`sacct … -o CPUTimeRAW`), offene Punkte. In `CLAUDE_PROJECT_NOTES.md` und als `compression_jobs/ergebnisse/BERICHT_druck_71_<datum>.md`; committen, pushen.

## Was du NICHT tun sollst
Keine Parameter ändern, keine Netze neu bauen, keine Jobs der 018-Konvergenzstudie (`JM-25-77-h*`) oder fremde Jobs (`r2_*`) anfassen, keine großen Dateien ins Repo.
