# CLAUDE_PROJECT_NOTES.md — 017-Yield-Surface-Batch-leS-nohinge

Angelegt 08.09.2026 als Kopie von `015-Yield-Surface-Batch-leS` (Skripte, Configs,
`00_template`, Doku; keine Daten). Anlass: alle r4-Netze in 015 enthielten
87-253 "Scharnierteile" (Zellgruppen, die mit dem Rest nur Kanten/Knoten teilen),
Ursache der Newton-Nichtkonvergenz am Fliessbeginn in r2 und r4
(Publikationsordner `CLAUDE.md` §22). Hier: Netzvorbereitung komplett neu mit
Scharnierfilter im Konverter (`make_mesh_dlfx_compatible_cluster.py`) und
Pruefung `mesh_hinge_check.py` in `run_prepare_mesh_CLUSTER.sh`; alle 768 Punkte
frisch (H = 70, alpha_avg 1e-3 einziges Abbruchkriterium, 32 Tasks, 1440 min).
015 bleibt als Archiv unveraendert. Vorgeschichte bis 08.09.:
`CLAUDE_PROJECT_NOTES_015_bis_20260908.md`.

## Session 08.09.2026 — Anlage

- 13:30 Ordner angelegt (81 Dateien), Referenzen ersetzt (`BASE_PATH`,
  Configs, Skripte), `00_template` ohne Unterverzeichnisse. Geprueft:
  `config.sh` -> reduce 4, 150 um, H = 70, 32 Tasks, 1440 min, Constraint leer;
  `YIELD_PRIMARY_CRITERION=alpha_avg_material`, Schwelle 1e-3, `YIELD_BLOCKING=primary`.
  Hinweis: `config-A01-les.json` (Basis) traegt noch die alten Kriterien
  (eps_p_eq primaer, 0.002, alle blocking) und keine material_sets — der
  Generator `create_les_dataset_config.py` ueberschreibt Kriterien und `hard`
  aus `config.sh`; die erzeugten `config-<DS>-r4-sigy*.json` sind massgeblich
  (nach `batch_create_configs.sh` pruefen!).
- Naechster Schritt (Cluster): 015-Jobs abbrechen, `git pull`,
  `batch_create_folders_CLUSTER.sh`, Trockenlauf `batch_submit`, scharf:
  4 Netzvorbereitungen (mit Scharnier-Gate) + 768 Punkt-Jobs (afterok).
- 14:19 Eingereicht: Prep-Jobs 54499326 (JM-25-77), 54499327 (JM-25-71),
  54499328 (JM-25-83), 54499329 (JM-25-88), sofort gestartet; 768 Punkt-Jobs
  PENDING (Dependency afterok). Alle 015-Jobs vorher abgebrochen (scancel nach
  Name `JM-25-*`). rsync-Code 23 bei `batch_create_folders` war harmlos:
  Checkout und Scratch datei- und md5-gleich (nur drei alte Vorschau-PNGs auf
  Scratch zusaetzlich), 768 Jobskripte + 768 Configs, `00_template` ohne
  Unterverzeichnisse. Voxel-Shapes: JM-25-77 296x297x221, JM-25-71 290x292x263,
  JM-25-83 293x295x264, JM-25-88 297x295x221 (r4).
- 14:45 **Netzvorbereitung aller vier Datensaetze COMPLETED (11-22 min), Gate
  bestanden: je genau 1 Flaechenkomponente.** Vernetzung ist offenbar bit-
  reproduzierbar (Fragmentfilter: identische Komponenten- und Knotenzahlen wie
  am 05.09., z. B. JM-25-77 23 Komponenten / 893 374 Knoten). Scharnierfilter:
  JM-25-77 87 Teile / 1186 Tets, JM-25-71 140 / 613, JM-25-83 253 / 997,
  JM-25-88 89 / 130 entfernt; keine verankerten Nebenteile (kept_anchored 0).
  Tets danach: 3 157 990 / 4 353 024 / 5 401 397 / 3 725 184. 95 Punkt-Jobs
  laufen sofort, 672 warten (Priority), 1 Knotenreservierung.
- `health_check_CLUSTER.sh` (017): Schwelle auf 1e-3, Fortschrittsspalte
  alpha_avg statt eps_p_eq, Primaer-Label korrigiert (war seit 06.09. veraltet).
- ~16:00 **Erste Kontrolle 017 (nur JM-25-77 gestartet, 102 Jobs): 1656
  akzeptierte Schritte (Median 17 je Job), 222 Verwerfungen (~2 je Job), 14 Jobs
  mit >= 5 Verwerfungen, 0 dt_below_minimum, 0 MUMPS, 0 Traceback, Newton-
  Iterationen Median 6, 23 Punkte FERTIG (alpha_avg >= 1e-3, yield_run-JSON) nach
  < 2 h.** Zum Vergleich 015 am selben Datensatz: Kaskaden bis dt_min, 0 fertig
  am ersten Tag. Die Scharnierteile waren die Ursache. Offen: Verhalten der
  grossen Netze (JM-25-71/83), die noch in der Queue stehen; Konsistenzcheck
  Fliesspunkte alt (015, mit Scharnieren) vs. neu fuer gleiche Richtungen.

## Session 08.09.2026 (2) — H = 0-Tests, Kriterienstaffel, Richtungsverteilung

**Entscheidungen (Nutzer):** (1) H = 0 (ideal plastisch) vorbereiten — fuer
alles jenseits des initialen Fliessens ist H = 70 keine kleine Regularisierung
mehr (H*alpha_lokal = 7-70 MPa bei alpha_lokal 0,1-1 in den Stegen, gegenueber
sig_y = 75), ein Plateau existiert mit H > 0 nicht. (2) Perspektivisch
alpha_avg = 2e-3 als Abbruchkriterium der Hauptstudie ("0,2 % im Stegmaterial",
urspruengliche Schwelle der Studie) — Weg: `YIELD_ALPHA_AVG_THRESHOLD=0.002`
in config.sh + Patch der Scratch-Configs; bereits bei 1e-3 beendete Punkte per
`ALPHA_THRESHOLD=0.002 restart_dead_points_CLUSTER.sh` aus dem Snapshot
fortsetzen (Restart funktioniert). Sauber getrennt davon: makroskopisches
0,2-%-Offset aus der Makrokurve (Rp0,2 des Schaums, Vergleich Druckversuch),
offline aus der Historie. (3) Hauptstudie (H = 70, Abbruch alpha 1e-3) laeuft
unveraendert weiter -> gesichertes Hauptergebnis.

**Neu: `setup_H0_tests_CLUSTER.sh`** — legt aus vorhandenen Punkt-Jobs Kopien
unter `yield_surface_jobs_H0/<combo>/<sample>/` an: binning label `<label>-H0`
(eigene Run-/Ergebnisordner), `hard = 0`, `total_time = 0.10` (= 10 % Makro-
dehnung, Abbruch nur darueber), alle Kriterien `blocking: false`, alpha-Stufen
1e-3/2e-3/5e-3/1e-2 als eigene Eintraege (Name `alpha_avg_material_<x>`,
gleiche quantity) -> je Stufe [YIELD]-Ereignis + Feld-Snapshot. Jobname
`<DS>_s075-H0-ysNNN`; batch_status/health_check/resubmit ignorieren den Ordner.
Default: ys_095 (Fibonacci-Index 95, Richtung (-0.03, 0.14, -0.99) ~ Druck in
z, dem Druckversuch am naechsten) fuer alle vier Datensaetze, sigy075.
Fragen an die Tests: Konvergenz mit H = 0 ohne Scharniere; Verlauf zur
Traglast; Kosten bis 5/10 %. Kleindehnung ab ~3-5 % nur noch qualitativ.

**Richtungsverteilung geprueft (Frage Nutzer):** `sample_directions` =
Fibonacci-Kugel, z_i = 1 - (2i+1)/n, phi_i = i * goldener Winkel -> gleiche
Flaeche je Punkt. 96 Richtungen: Naechster-Nachbar-Winkel 18,1-20,2 deg
(ideal 20,7), Verteilung nach Winkel zur hydrostatischen Achse 3/26/39/28
gegen 3/25/43/25 bei Gleichverteilung -> gleichverteilt, keine Klumpen. Die
Namen der Punkt-Jobs (e1/e2/e3 = 0,25 * Richtung) stimmen mit der Formel
ueberein (ys_000 = +z, ys_095 = -z, ys_082 = (-0.30, 0.63, -0.72)).
Einordnung: (a) Strahlen liegen im Raum der Hauptdehnungen mit Achsen =
Boxachsen (keine Schubkomponenten) -> 3D-Schnitt der 6D-Flaeche; fuer
invariantenbasierte Fits (Ehlers, Deshpande-Fleck, P-Norm) und Orthotropie
entlang der Boxachsen ausreichend, Schubkopplung nicht erfasst. (b) Fuer
quasi-isotrope Elastizitaet (K/2mu ~ 1 bei nu ~ 0,3) ist die Abbildung
Dehnungs- auf Spannungsrichtung nahezu identisch -> auch in Spannungsrichtung
gleichverteilt. (c) Gleichverteilt ist nicht optimal: Kappen-Flaechen haben
die hoechste Kruemmung an der hydrostatischen Achse, dort liegen nur 3 von 96
Punkten (naechster 6,6 deg Druck / 6,9 deg Zug). Empfehlung: bei Bedarf ~12
Zusatzrichtungen um +/- hydrostatisch (Kappen) als eigene Tranche, nicht das
96er-Gitter aendern.
