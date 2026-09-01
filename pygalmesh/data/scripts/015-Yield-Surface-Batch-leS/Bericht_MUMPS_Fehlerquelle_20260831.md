# Bericht: Fehlerquelle „dt_below_minimum" in Studie 015 (31.08.2026)

**Kurzfassung.** 30 der 192 gestarteten JM-25-77-Punkt-Jobs endeten nach 1–5 h
mit Exit 0 und einer `yield_run_std_tensor.json`, enthielten aber **keinen
Fließflächenpunkt** (`stop_reason = dt_below_minimum`, `final_yield_state = null`).
Ursache ist nicht das Materialmodell und keine Hardware, sondern die parallele
LU-Faktorisierung (MUMPS) des dolfinx-NewtonSolvers, die bei ~16 % der Jobs
schon im ersten, rein elastischen Schritt scheitert. Behoben durch mehr
MUMPS-Workspace (`ICNTL(14)` 20 % → 200 %) im Solver-Template; die 30 Punkte
werden frisch neu gerechnet.

## 1. Symptom

| Beobachtung | Wert |
|---|---|
| Betroffene Jobs | 17 × `JM-25-77_sigy075`, 13 × `JM-25-77_sigy100` (30 von 192) |
| SLURM-Status | `COMPLETED`, ExitCode 0:0, Laufzeit 1 h 10 min – 5 h |
| Ergebnis-JSON | vorhanden, aber `criteria_reached = []`, `yield_states = {}`, `final_yield_state = null` |
| Zeitschritte | 2–20 „erfolgreiche" Schritte, alle bei dt ≈ 1e-10 (Artefakte), 26–42 verworfene |
| Zustand beim Abbruch | σ_vm,avg = 0,00 MPa, keine Plastizität — rein elastischer Bereich |

Dazu 28 weitere Jobs („Kriecher") mit 5–16 verworfenen Schritten, die nach
~75 Schritten erst bei t ≈ 1–2·10⁻³ stehen (gesunde Läufe: 6·10⁻³ nach 60).

## 2. Diagnoseweg

1. `squeue`/`sacct`: 30 Jobs fehlten in der Queue → alle `COMPLETED`, nicht abgestürzt.
2. JSON-Inhalt: kein Kriterium erreicht, Abbruch `dt_below_minimum`.
3. Rekonstruktion aus `alex/solution.py`: der Zeitschrittregler halbiert dt bei
   jedem `RuntimeError` des Newton-Solvers bis `dt_min = 1e-11` (≈ 27 Halbierungen
   ab 1e-4). Eine Halbierung kann nur helfen, wenn das Inkrement das Problem ist.
4. Entscheidender Befund: im ersten Schritt ist die Matrix für σ_y = 75 und 100
   **identisch** (linear elastisch). Trotzdem scheitert z. B. ys_020 nur bei
   `s075` und läuft bei `s100` sauber (ys_001 umgekehrt) → nicht-deterministisch
   zwischen Jobs, deterministisch innerhalb eines Jobs (28+ Fehlversuche in Folge).
5. Log (`.out` von Job 54430539): `Default KSP Type: preonly`, `Default PC Type: lu`
   und beim ersten Solve
   `Failed to successfully call PETSc function 'KSPSolve'. PETSc error code is: 76, Error in external library`.
   Error 76 = Fehler in der externen Bibliothek = MUMPS-Faktorisierung (typisch
   INFOG(1) = −9: Workspace zu klein).
6. Knotenkorrelation (`sacct -o NodeList`): jeder Job auf einem Knoten; tote und
   gesunde Jobs teilen sich Knoten (z. B. mpsc0617: 2 tot + 1 ok) → keine Hardware.

## 3. Ursache

Der dolfinx-NewtonSolver löst per Default direkt (`preonly` + `lu` → MUMPS).
MUMPS schätzt in der Analysephase den Speicherbedarf und legt per Default nur
20 % Reserve an (`ICNTL(14) = 20`). Ob das reicht, hängt von Partitionierung,
Ordering und Pivotierung des jeweiligen Jobs ab — deshalb scheitern ~16 % der
Jobs reproduzierbar, andere mit identischer Matrix nicht. Der Zeitschrittregler
interpretiert den Faktorisierungsfehler als Nicht-Konvergenz und halbiert dt,
was die Matrix nicht ändert; nach ~27 Versuchen endet der Lauf regulär mit
Exit 0. Die Kriecher sind derselbe Effekt intermittierend in späteren Schritten
(Pivotierung ändert sich mit dem plastischen Zustand).

## 4. Behebung (eingebaut 31.08.2026)

| Datei | Änderung |
|---|---|
| `015…/00_template/elastoplastic.py` | Block nach `comm/rank`: PETSc-Optionen mit Prefix `nls_solve_`: `pc_factor_mat_solver_type = mumps`, **`mat_mumps_icntl_14 = 200`**, `mat_mumps_icntl_4 = 1` (MUMPS-Fehlercodes ins `.out`); überschreibbar über `yield_surface.petsc_options` in der Config; druckt `PETSc options (prefix nls_solve_): {...}` |
| `dolfinx_alex/shared/utils/alex/solution.py::get_solver` | `solver.krylov_solver.setFromOptions()` — stellt sicher, dass gesetzte Optionen greifen; ohne Optionen ein No-op |
| Backups | `015…/_to_delete/elastoplastic.py.vor_mumps_patch_20260831`, `…/alex_solution.py.vor_mumps_patch_20260831` |

Wirkung: jeder Punkt-Job kopiert `00_template/*` beim Start (auch beim
Fortsetzen). Seit dem Sync nach `$HPC_SCRATCH` (31.08.) nutzen alle noch
wartenden Jobs (JM-25-71/83/88, 576 Stück) und alle Resubmits den Patch;
laufende Jobs bleiben unverändert.

## 5. Neustart der 30 toten Punkte — fertig zum Einfügen

Erledigt (31.08.): Template auf Scratch, `solution.py` auf dem Cluster geprüft,
30 Slim-Kopien nach `00_results/_failed_mumps_20260831/` verschoben, Dry-Run
zeigt exakt 17 + 13 Punkte. Es fehlt nur noch das Einreichen:

```bash
S="$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS"
INCLUDE_FAILED=1 YS_FORCE_FRESH=1 MAX_CHAIN=1 "$S/resubmit_yield_surface_timeouts_CLUSTER.sh" "$S/yield_surface_jobs/JM-25-77_sigy075/n096"
INCLUDE_FAILED=1 YS_FORCE_FRESH=1 MAX_CHAIN=1 "$S/resubmit_yield_surface_timeouts_CLUSTER.sh" "$S/yield_surface_jobs/JM-25-77_sigy100/n096"
# Erwartung: je Aufruf "neu eingereicht=17" bzw. "=13"
```

Warum so: `INCLUDE_FAILED=1`, weil der letzte Abbruch kein Timeout war;
`YS_FORCE_FRESH=1`, weil der alte Rechenstand wertlos ist (Artefakt-Schritte);
`MAX_CHAIN=1`, weil `YS_FORCE_FRESH` sonst in **jedem** Kettenglied den Stand
verwerfen würde. Sollte ein neu gestarteter Punkt später ans 7-Tage-Limit
laufen, die Fortsetzung wie gewohnt **ohne** `YS_FORCE_FRESH` einreichen:
`resubmit_yield_surface_timeouts_CLUSTER.sh <combo>/n096`.

Kontrolle nach dem Start (1–2 h):

```bash
cd "$S"
for o in $(ls -t yield_surface_jobs/JM-25-77_*/n096/ys_*/*.out.* | head -30); do
  printf "%-60s opts=%s ok=%s fail=%s\n" "$(basename $o)" \
    "$(grep -c 'PETSc options (prefix nls_solve_)' $o)" \
    "$(grep -c 'Computing solution at time' $o)" "$(grep -c 'NO CONVERGENCE' $o)"
done
# opts=1 (Patch aktiv), fail=0 und wachsendes ok = Problem gelöst.
# Falls MUMPS weiter scheitert: grep -m3 "INFOG\|INFO(1)" <out> → Code deutet auf ICNTL(14) höher (-9) oder Speicher (-13/-17).
```

Die 28 Kriecher laufen weiter (sie kommen voran). Option später: `scancel` und
`INCLUDE_FAILED=1 MAX_CHAIN=3 resubmit… <combo>/n096` **ohne** `YS_FORCE_FRESH`
→ Fortsetzung vom letzten Snapshot (max. 12 h Verlust) mit gepatchtem Template.

## 6. Gilt das auch für andere dolfinx-Jobs auf dem Cluster?

Seit dem zweiten Patch (31.08., spät) **ja — als Default in
`alex/solution.py`**: `DEFAULT_KSP_OPTIONS = {pc_factor_mat_solver_type: mumps,
mat_mumps_icntl_14: 200, mat_mumps_icntl_4: 1}` wird in `get_solver()` über
`apply_default_ksp_options()` unter dem echten Prefix des NewtonSolver gesetzt —
aber nur für Optionen, die ein Skript nicht schon selbst in `PETSc.Options()`
gesetzt hat (Skript gewinnt). Damit profitiert jedes Skript, das
`solve_with_newton_adaptive_time_stepping` ohne eigenen `solver` benutzt.
Nicht betroffen: Skripte, die ihren NewtonSolver selbst bauen und übergeben.
Ergebnisse ändern sich nicht (gleiche LU, mehr Reserve); `icntl_4 = 1` gibt nur
im Fehlerfall etwas aus. Abschalten pro Skript: `sol.DEFAULT_KSP_OPTIONS.clear()`
vor dem ersten Solve; Kontrolle im Log: Zeile
`KSP options (prefix 'nls_solve_'): defaults applied = {...}`.
Voraussetzung: die neue `solution.py` muss nach `$HOME/dolfinx_alex/shared/utils/alex/`
auf dem Cluster (wird in den Container als `/home` eingebunden).

Der explizite Block in `elastoplastic.py` bleibt (Config-steuerbar über
`yield_surface.petsc_options`); er ist damit doppelt abgesichert. Rückblick
lohnt sich: auch in 014/010 könnten Punkte mit `stop_reason = dt_below_minimum`
und `final_yield_state = null` dieselbe Ursache haben.

## 7. Nebenbefund zum Stand der Studie

134 von 192 JM-25-77-Läufen haben `yielded_fraction_material` (0,2 % des
Materialvolumens plastisch) erreicht — bereits als CSV gesichert
(`00_results/_packages/partial_yield_states_from_restart_meta.csv`). Kein Lauf hat
bisher `alpha_avg_material` oder das Primärkriterium `eps_p_eq_macroscopic`;
letzteres liegt noch ~65× unter der Schwelle und wird erst nahe der Traglast
des RVE erreicht (bei `hard = 0` numerisch der heikelste Bereich). Restlaufzeit
nicht abschätzbar.

Details, Skripte und Befehle: `CLAUDE_PROJECT_NOTES_015.md`, Abschnitt
„Session 31.08.2026"; Neustart-Sonderfall auch in `RESTART_NACH_TIMEOUT_015.md`.

## 8. Nachtrag 01.09.2026: zweites Gesicht derselben Ursache, Neustart mit reduce=4

Der Health-Check am 01.09. zeigte, dass die dichteren Datensätze das Problem
nicht als Workspace-, sondern als **physischen Speicherfehler** haben: alle 190
JM-25-88- und 26 JM-25-71-Jobs standen nach bis zu 26 h im ersten Solve, in den
`.err` stand mehrfach `Killed apptainer exec …` (OOM-Killer), die übrigen Ränge
hingen in der MUMPS-Kollektive, der Job blieb RUNNING. Freiheitsgrade:
JM-25-77 12,3 M, JM-25-88 14,2 M, JM-25-71 16,1 M bei 358 GB je Job (64 × 5600 MB,
i01-Knoten 364,8 GB). Gleichzeitig war bei JM-25-77 die Zahl der Kriecher auf
72/192 gestiegen (54 + 52 Läufe mit Fehler 76). Der Patch mit `icntl_14 = 200`
hätte nahe am Knotenlimit selbst OOM auslösen können (Allokation bis 3× der
Schätzung) — auf 100 gesenkt.

**Entscheidung:** alle 768 Punkt-Jobs abgebrochen, Studie mit `reduce = 4`,
Elementgröße 150 µm (~1/8 der dofs), 32 Tasks, 1440 min neu aufgesetzt; zusätzlich
`srun --kill-on-bad-exit=1`, damit ein OOM-Kill den Job beendet statt ihn 7 Tage
zu blockieren. r2-Teilergebnisse (138 Erstfließpunkte, 13 × alpha_avg) gesichert in
`00_results/_packages/partial_yield_states_r2_final_20260901.csv`. Runbook und
Parametertabelle: `CLAUDE_PROJECT_NOTES_015.md`, „Session 01.09.2026 (2)".
