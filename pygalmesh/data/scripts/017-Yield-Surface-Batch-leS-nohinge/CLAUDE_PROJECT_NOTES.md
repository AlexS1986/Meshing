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
- ~17:00 **H0-Testjobs eingereicht:** 54500935 (JM-25-77), 54500936 (JM-25-71),
  54500937 (JM-25-83), 54500938 (JM-25-88), je ys_095 sigy075, hard 0,
  total_time 0.1, sechs Doku-Kriterien (blocking false), dt 1e-4 (dt_max 1e-3).
  Configs/Jobskripte unter `yield_surface_jobs_H0/`, Ergebnisse unter
  `yield_surface_runs/<DS>_les_r4/leS-r4-sigy075-H0/` bzw. `00_results/.../
  leS-r4-sigy075-H0/`. Erwartete Laufzeit bis 10 %: JM-25-77 ~3-6 h, JM-25-83
  moeglicherweise > 24 h (dann Walltime-Stop + Fortsetzung per Restart;
  manuell: denselben Job erneut einreichen, kein YS_FORCE_FRESH).
- ~17:15 `scontrol top <ids kommagetrennt>` fuer die H0-Jobs (funktioniert
  fuer eigene Jobs): 54500935/37/36 laufen sofort, 54500938 an der Spitze der
  Wartenden. Kontrolle in ~1 h mit dem H0-Block (Verwerfungen JM-25-71,
  Dehnung je alpha-Stufe vs. Hauptstudie, Tangente/Anfangssteigung).
- ~18:30 **H0 nach 77 min: konvergiert.** JM-25-77 23 Schritte / 1 Verwerfung
  (mpsd0505), JM-25-83 11 / 0 (mpsd0505), JM-25-88 8 / 2 (mpsd0231), JM-25-71
  4 / 2 (mpsc0456, i01, langsamstes Netz) — kein dt_below_minimum, Newton 6-7
  Iterationen. `yielded_fraction 2e-3` bei 0,25-0,30 % Dehnung (das Fenster,
  in dem 015 starb) ohne Abbruch. Kurven/Stufen: fruehestens nach 3-5 h
  (2-3 % Dehnung), Plateau-Frage 09.09. mittags. Beobachten: JM-25-71
  (fruehe Verwerfungen).

## Session 09.09.2026 — Status nach ~18 h

**Hauptstudie 017:** 397/768 fertig (JM-25-77 192/192, JM-25-88 192/192,
JM-25-71 13 von 27 gestarteten), 0 dt_below_minimum, 0 Traceback, 0 Walltime-
Stop, 0 Haenger. Verwerfungen aber hoch: JM-25-77 ~7/Job, JM-25-88 ~8/Job,
JM-25-71 ~27/Job (Median 39 Schritte) -> jede Verwerfung = 30 Newton-
Iterationen umsonst; bei JM-25-71 ist das der Kostentreiber. Queue: 17 RUNNING,
347 Priority, **10 PENDING AssocMaxJobsLimit** (Durchsatz eingebrochen, gestern
95 laufend) -> Limit pruefen (sacctmgr assoc / GrpJobs des Kontos).
**Vergleich alt/neu (alpha 1e-3, interpoliert):** JM-25-77 77 gemeinsame
Richtungen, Median +-0,0 %, aber 19 mit |Abw| > 2 % (min -15,7 %, neu niedriger);
JM-25-88 12 gemeinsame, +1,1 % (+0,6..+1,6 %). Ausreisser noch unerklaert
(Kandidaten: alte Laeufe mit H = 0 vs. neu H = 70? Kriech-dt-Pfad? Scharnier-
Beitrag zur mittleren Spannung?) -> Einzelliste pruefen.
**H0-Tests (ys_095, sigy075):**
- JM-25-77: FERTIG bis 10 % (112 Schritte, 17 Verwerfungen, < 20 h). Stufen:
  a=1e-3 bei 2,55 %, 2e-3 bei 4,20 %, 5e-3 bei 8,35 % (1e-2 nicht erreicht).
  sig_vm: 2,50 (0,5 %), 3,58 (1 %), 4,74 (2 %), 5,45 (3 %), 5,92 (4 %),
  6,25 (5 %), 6,70 (7,1 %); Tangente/E0: 79/36/16/10/7/5/3 %. Ab ~5 %
  quasi-Plateau (Tangente < 5 % E0), bei 7 % noch +2 % je 1 % Dehnung.
- JM-25-88: bis 4,5 %: 6,83/8,87/10,73/11,74/12,36 MPa (0,5-4 %), T/E0 bei
  4 % = 3 %; Stufen 1e-3 bei 1,45 %, 2e-3 bei 2,30 %, 5e-3 bei 4,50 %.
- JM-25-83: 34 Schritte / 24 Verwerfungen, 1,5 % (a=1e-3 bei 1,50 %).
- JM-25-71: 29 Schritte / **26 Verwerfungen**, erst 0,63 % nach ~16 h — die
  Verwerfungen fressen die Zeit (26 x 30 Iterationen).
Erkenntnis: H = 0 konvergiert; Plateau-Annaeherung bei 5-10 % sichtbar (JM-25-77,
-88); Kosten werden von Verwerfungen dominiert -> NEWTON_MAX_IT senken (Verteilung
der Iterationen akzeptierter Schritte pruefen: wenn > 12 praktisch nie vorkommt,
max_it 12-15 statt 30 = halbe Verwerfungskosten).
**Kontrolle 09.09. (2):** (A) MaxJobs 400/Nutzer, MaxSubmit 1000; 10 Jobs
`AssocMaxJobsLimit` bei nur 17 laufenden -> Konto der Jobs pruefen (squeue -A
p0023647 zeigt 0 -> Jobs laufen unter anderem Konto?). Hauptgrund fuer 17
statt 95 laufend: 347 x Priority = Clusterlast, nicht das Limit.
(B) **Ausreisser alt/neu sind systematisch:** alle 18 negativen (-14..-16 %)
sind alte 015-Laeufe mit H = 0 (aus .out), JM-25-77 (15 x sigy100, 3 x
sigy075); alt erreicht alpha 1e-3 FRUEHER (1,69 % vs 1,88 %) bei HOEHERER
Spannung (9,85 vs 8,31 MPa) -> alte Antwort ist steifer, nicht nur "H = 0".
Mit H = 70 muesste neu eher hoeher liegen -> H erklaert das Vorzeichen nicht.
Hypothese: Teil der Scharnierteile waren keine haengenden Enden, sondern
**Bruecken** (an zwei getrennten Stellen ueber Kanten/Knoten angebunden) und
haben Last uebertragen -> Entfernen macht den Schaum in manchen Richtungen
weicher; JM-25-77 (85,5 % Porositaet, duennste Stege, 1186 Scharnierzellen)
am empfindlichsten, JM-25-88 (130 Zellen) +1,1 %. Pruefung: elastische
Anfangssteigung E0 alt/neu je Richtung (gleich -> Plastizitaet/H; 15 %
kleiner -> Netz/Bruecken) und Zaehlung der Anbindungsknoten je Scharnierteil.
Fuer das Paper relevant: Netzfilter aendert Steifigkeit in einzelnen
Richtungen messbar -> quantifizieren und begruenden (Sub-Voxel-Verbindungen,
numerisch nicht darstellbar).
(C) Newton-Iterationen akzeptierter Schritte (9499): > 12 nur 3 (0,03 %),
> 10: 11, > 8: 83 -> **NEWTON_MAX_IT 30 -> 12** verliert praktisch nichts,
spart 60 % je Verwerfung (JM-25-71: 27 Verwerfungen/Job). Stelle:
`job_yield_surface_point_CLUSTER.sh` Z. 35 Default.
**09.09. — Konto:** Die 017-Jobs liefen unter `l0003507` (Default
`JOB_ACCOUNT` in config.sh, MaxJobs 200) — entgegen der Entscheidung vom 03.09.
(p0023647). Nutzer 09.09.: nicht auf l0003507 rechnen. Massnahme: wartende
Jobs per `scontrol update Account=p0023647` umhaengen (laufende bleiben, wo
sie sind), `#SBATCH -A` in allen Scratch-Jobskripten (768 + H0) auf p0023647,
Default in `config.sh` und `setup_yield_surface_jobs.sh` auf p0023647 (Mac,
Git). Sekundaer erklaert das auch `AssocMaxJobsLimit` teilweise (MaxJobs 200
auf l0003507 statt 400).
**09.09. (3) — H-Test und alt/neu-Kurven:** (a) ys_095 JM-25-77 sigy075 auf
dem neuen Netz, H = 0 vs H = 70: +0,1 % (0,3 %) ... +0,7 % (2,5 %) — richtiges
Vorzeichen, Verfestigungsimplementierung ok, H-Einfluss bei alpha 1e-3 < 1 %
(bestaetigt §20). (b) Kurven alt(015)/neu(017) fuer die Ausreisser stimmen bei
0,75-1,0 % Dehnung auf +-2 % ueberein (E0 identisch, s. o.); Abweichungen bei
0,3-0,5 % sind ein Artefakt meines Vergleichs (grobe neue Schritte, "erster
Eintrag >= s"). Die 15 % am Fliesspunkt entstehen also erst ZWISCHEN 1,0 % und
1,7 % im ALTEN Lauf (sig alt springt von 6,9 auf 9,85 MPa bei 1,0 -> 1,69 %,
Tangente ~430 MPa ≈ E0/2 — im Plastischen unplausibel; neu: 7,0 -> 8,3 ueber
0,9 %, Tangente ~150). Verdacht: Artefakt in der alten Historie (Kriechphase
dt 1e-5, Restart-Ueberlappung, nicht-monotone t?) -> Historie im Detail
ansehen, bevor die alten Punkte als Validierung gelten.
(c) csreport: **l0003507 September 42,9k von 30k Kernstunden (ueberzogen!)**;
p0025962 hat 1250k/Monat (Sep: 870k genutzt) — Assoziation fuer as12vapa
fehlt noch (Anfrage 02.09.). p0023647 nicht in csreport (kein Kontingent).
**09.09. — Konto umgestellt:** 357 wartende Jobs per `scontrol update
Account=p0023647` umgehaengt (Alter bleibt), alle 772 Scratch-Jobskripte
(768 + 4 H0) `#SBATCH -A p0023647`; 17 laufende + 2 H0 bleiben auf l0003507
bis sie enden. Default in config.sh/setup_yield_surface_jobs.sh auf p0023647
(Mac, Push ausstehend). FairShare: p0023647 0,025, l0003507 0,014 — beide
niedrig, p0023647 trotzdem etwas besser. Reason nach Umhaengen: "None" (neu
bewertet), Starts erwartbar langsamer als gestern.
**09.09. (4) — Ausreisser aufgeklaert: mein Vergleich hatte r2 und r4 vermischt.**
Die alten r4-Historien von ys_020/ys_012 (015) enden bei t = 1,02 % / 1,24 %
mit alpha max 2,6e-4 / 3,0e-4 — sie haben alpha 1e-3 NIE erreicht. Die
"alten Fliesspunkte" bei 1,69 % / 9,85 MPa stammen aus `JM-25-77_les_r2`
(r2-Studie, 33 um Voxel, 75 um Elemente, H = 0), weil mein Schluessel
(Datensatz, sig_y, ys) die Aufloesung ignorierte. Die 15 % sind also kein
Scharnier- und kein H-Effekt, sondern **Netzaufloesung r2 vs r4**: r4 liefert
bei JM-25-77 (duennste Stege) ~15 % niedrigere Fliessspannung als r2 —
bei identischer Elastizitaet? (E0 r2 vs r4 noch pruefen). Fuer das Paper
wichtig (Reviewer-Kritik Konvergenz/Repraesentativitaet): r2-Punkte aus 015
als Konvergenzvergleich nutzen. Der korrekte Vergleich 015-r4 (Scharniere)
vs 017-r4 ist noch zu machen (erwartet +-1-2 %).
Die r4-Historien alt/neu stimmen bis 1 % Dehnung auf < 0,5 % ueberein
(ys_020: 6,725 vs 6,725 MPa bei 0,95 %) -> Scharniere ohne Einfluss auf die
Makroantwort, nur auf die Konvergenz. Alte r4-Laeufe: dt 1,25e-5..5e-5,
4-5 Iterationen, 119-175 Eintraege bis ~1,2 %, Tod ohne alpha 1e-3.
**09.09. (5) — Vergleiche mit Aufloesung im Schluessel:**
A. Scharniereffekt (015-r4 vs 017-r4, gleiche Richtungen): E0 -0,1 % (min
-1,5 %), Fliessspannung alpha 1e-3: JM-25-77 sigy075 -0,0 % (40 Punkte),
sigy100 +1,4 % (19), JM-25-88 +1,0/+1,1 % (5/7) -> **Scharnierfilter ohne
Einfluss auf die Homogenisierung (< 1,5 %, davon ~0,7 % H-Effekt)**; Satz
fuers Methodenkapitel.
B. Aufloesung (015-r2 vs 017-r4, JM-25-77, 162 Richtungen E0 / 25 Fliess-
punkte): **E0 bei r4 um 21 % niedriger (-18..-29 %), Fliessspannung -15 %,
Fliessdehnung +12 %.** r4 (150 um Elemente, 67 um Voxel) ist beim poroesesten
Schaum NICHT konvergiert — die duennen Stege sind mit 1-2 Elementen ueber die
Dicke zu weich abgebildet. Fuer JM-25-71/83/88 gibt es keine r2-Daten (r2-
Laeufe OOM, §12). Konsequenz fuer das Paper (Reviewer: Konvergenz!): entweder
(1) r2-Stichprobe je Datensatz mit neuem Setup (Scharnierfilter, H = 70) auf
Grossspeicherknoten (`mem`-Partition, 1,5 TB, wie 016) fuer ~12-24 Richtungen
-> Konvergenzordnung und Richardson-Extrapolation je Richtung; oder (2) r3
(reduce 3, ~112 um Elemente, ~8 M dofs, LU ~300 GB -> i02-Knoten 490 GB mit
--mem-per-cpu 15000) als Zwischenstufe; oder (3) nur dokumentieren. Empfehlung:
(1) fuer JM-25-77 (r2-Netz existiert in 015, nur Scharnierfilter neu) + je 12
Richtungen fuer die anderen drei. Entscheidung Nutzer offen.
Vorbereitet: `job_yield_surface_point_CLUSTER.sh` NEWTON_MAX_IT Default 30 -> 12
(Mac 017; Scratch per sed nachziehen, wirkt auf wartende Jobs).
**Entscheidung Nutzer 09.09.: vorerst KEINE Netzkonvergenzstudie.** Erst auf
den bestehenden r4-Netzen den Datenpunkt (vollstaendige Fliessflaeche, 768
Punkte) erzeugen; Konvergenz (r2-Stichprobe/Richardson) spaeter, wenn
Kapazitaet und Deadline (15.10.) es zulassen. Der r2/r4-Befund (-21 % E0,
-15 % Fliessspannung bei JM-25-77) wird im Paper als bekannte Aufloesungs-
abhaengigkeit dokumentiert; die 25 r2-Fliesspunkte aus 015 dienen als
vorhandener Vergleichswert.
**09.09. — Scratch nachgezogen:** `job_yield_surface_point_CLUSTER.sh`
(NEWTON_MAX_IT 12, Backup `.vor_maxit12_20260909`), `config.sh`,
`setup_yield_surface_jobs.sh` (p0023647). Queue: 17 laufend (l0003507),
357 wartend (p0023647, Priority). 397/768 fertig. H0 nach ~22 h:
JM-25-77 fertig (10 %); JM-25-88 97 Schritte, 1e-2 bei 8,0 % erreicht;
JM-25-83 35 Schritte / 24 Verwerfungen, 1,5 %; JM-25-71 30 / 27, < 1 % —
die beiden grossen Netze werden das 24-h-Limit reissen -> Walltime-Stop +
Fortsetzung (denselben Job erneut einreichen; erster Ernstfall des Restarts).

## Session 09.09.2026 (2) — Variante A umgesetzt: H = 0, Abbruch alpha 2e-3

**Entscheidung Nutzer:** A. Wartende Jobs (357, JM-25-71/83) rechnen mit
`hard = 0`, Abbruch `alpha_avg_material >= 2e-3`, Doku-Stufen 1e-3/5e-3/1e-2
(Ereignis + Snapshot). Fertige 397 (JM-25-77/88, H = 70, 1e-3) bleiben als
initiale Fliessflaeche/Entwurf und werden spaeter mit derselben Config frisch
nachgerechnet (kein H-Wechsel im Lauf). Laufende 17 (H = 70) enden regulaer.
Erwartung Konvergenz: wie H = 70 (H0-Tests: 0 dt_min, Verwerfungen im
Fenster 0,2-1 %); Risiko ist Laufzeit (JM-25-83 bis ~2,3-4 % > 24 h ->
Walltime-Fortsetzung, MAX_IT 12). Plateau spaeter durch Fortsetzung derselben
Laeufe (Snapshots liegen lassen! Scratch-Loeschfrist pruefen).
**Aenderungen (Mac 017):** `patch_yield_criteria_CLUSTER.py` (Defaults 2e-3 /
hard 0, `--doc-levels`, idempotent, Backup-Suffix `--tag`),
`create_les_dataset_config.py` (`--alpha-doc-levels`, Default 0.001,0.005,0.01),
`create_les_config.sh` (Schwelle 0.002), `config.sh` (`YIELD_ALPHA_AVG_THRESHOLD`
0.002, `LES_HARDENING` 0). Ablauf Cluster: Push -> pull -> Patch-Skript nach
Scratch -> Trockenlauf -> scharf (alle 768 Punkt-Configs + 8 Datensatz-Configs).
- ~12:30 **Variante A scharf:** 776 Configs auf Scratch gepatcht (768 Punkt- +
  8 Datensatz-Configs; Backups `.vor_kriterien_20260909`): hard 0 (std/am/conv),
  Abbruch alpha_avg_material 2e-3, Doku-Stufen 1e-3/5e-3/1e-2, eps_p_eq und
  yielded_fraction nur Doku, total_time unveraendert (1e9). Die 17 laufenden
  Jobs (H = 70, 1e-3) bleiben unberuehrt; alle 357 wartenden starten mit A.
  Kontrolle JM-25-83_sigy100/ys_000: korrekt.
- 09:45 Tagescheck: 401/768 fertig (77/88 komplett, 71_sigy075 17 mit H = 70),
  13 laufend (l0003507, H = 70), 357 wartend (p0023647, Priority) — noch kein
  A-Job gestartet. dt_small/Traceback/stumm = 0. JM-25-71: 28 Verwerfungen je
  Job (Median 39 Schritte). H0: 71 bei 31/28, 83 bei 36/25 (1,5 %), 88 102
  Schritte (1e-2 bei 8,0 %). Nichts fortzusetzen.

## Session 09.09.2026 (3) — Nachmittag: Konten, FAILED-Jobs, Selbstschutz

**Lage 17:40 (sacct/squeue):** 240 laufend (120 p0023647 = JM-25-71, 120
special00008 = JM-25-83 107 + 71_s100 13), 0 wartend. Die special00008-Jobs
sind die urspruenglichen Job-IDs (umgehaengt, nicht neu eingereicht — in der
anderen Claude-Sitzung cse_01N981k9Vcfa8eVrzuAbPvyz; Ralf hat as12vapa auf
special00008 eingetragen, 386k Kernstunden/Monat). special00008 funktioniert
(87 COMPLETED + 120 RUNNING heute). Nutzer: special00008 nur wenn noetig,
moeglichst wenig verbrauchen; heute dort schon ~35-40k.
**JM-25-83 viel billiger als geschaetzt:** 18 Schritte in 5,5 h, Punkte in
6-8 h fertig (MAX_IT 12) -> Reststudie eher 80-100k Kernstunden statt 250-300k.
`config.sh` auf Scratch steht auf JOB_ACCOUNT special00008 (andere Sitzung);
Jobskripte (772) auf p0023647 -> Punkt-Jobs landen auf p0023647.

**21 FAILED heute — drei Ursachen:**
1. **17 x JM-25-71_s075 (l0003507, H = 70, 14-21 h Laufzeit): Solver fertig
   ([STOP], JSON im Laufordner), danach `syntax error` in
   job_yield_surface_point_CLUSTER.sh Z. 248/250 -> Exit 2, Kopie nach
   00_results fehlt.** Ursache: ich habe um ~09:30 das gemeinsame Skript per
   `cp` IN-PLACE ersetzt (MAX_IT 12 + laengere Kommentarzeile), waehrend 13-17
   Jobs darin im srun standen; bash liest Skripte stueckweise -> nach dem srun
   an falscher Byte-Position weitergelesen. Gleiches Risiko fuer die drei H0-
   Jobs. Regel ab jetzt: **gemeinsame Skripte auf Scratch nur per temp + mv
   ersetzen (neuer Inode), nie cp/Editor in-place.** Fix: Selbstkopie-Guard am
   Skriptanfang (exec aus mktemp-Kopie; Backup `.vor_selfcopy_20260909`).
   Reparatur: Slim-Kopie nach 00_results fuer alle Punkte mit JSON nachholen.
2. **JM-25-71_s100-ys028 (p0023647, H = 0): Task 12 abgestuerzt bei t = 6e-3,
   32 Tracebacks, Exit 143** -> Traceback noch zu lesen (OOM? MUMPS?).
3. **3 x JM-25-83_s100 ys093-095 (special00008, neue IDs 14:49, 5 s):**
   `FATAL: Couldn't determine user account information: unknown userid` auf
   mpsd0138 -> Knotenproblem (LDAP), nicht unser Fehler; neu einreichen.
4. H0-Tests 71/83 (+88?): **Walltime-Stop sauber** (Exit 3 = FAILED in sacct,
   gewollt), 83 bei t = 2,3 % nach 42 Schritten; Fortsetzung per Resubmit.
Bilanz 17:40: 71_s075 fertig 36 / Queue 60; 71_s100 22 / 73 / 1 fehlt;
83_s075 32 / 64; 83_s100 50 / 43 / 3 fehlen. 77/88: 384 H = 70 (Nachrechnung
offen, Archiv-Block noch nicht gelaufen).
- 18:30 **Entwarnung zu Ursache 1:** Die 17 FAILED-Jobs hatten ihre
  00_results-Kopie bereits geschrieben (Syntaxfehler traf erst die letzten
  Zeilen: config/parameters-Kopie, rm case_scratch) -> kein Datenverlust.
  Meine zwei Reparaturversuche hatten den 00_results-Pfad falsch (echte
  Struktur: `00_results/<ds>_les_r4/<sample>/yield_surface/<punkt>-std-tensor/
  <punkt>/subvolume_x0_y0/yield_run_std_tensor.json`); 2 x 528 Fehlkopien
  wieder entfernt (Ordner ohne `_les_r4` bzw. `leS-r4-sigy*-std-*`), Stand
  531 JSONs = 529 Studie + H0. **Merke fuer den Archiv-/Nachrechnungsblock:
  00_results-Punktordner heissen `<punkt>-std-tensor`, Ebene 2 ist der
  Sample-Name (leS-r4-sigyXXX), Ebene 1 `<ds>_les_r4`.**
- ys028 (71_s100): `RuntimeError: Failed just-in-time compilation of form`
  (JIT-Cache-Wettlauf bei ~240 gleichzeitig startenden Jobs, 1 von ~700) ->
  Resubmit. Eingereicht 18:30 auf p0023647: ys028, 83_s100 ys093-095 (Knoten-
  LDAP-Fehler), H0-Fortsetzungen 71/83/88 (Job-IDs 54509679-81, 54509719-22).
- Queue 18:30: 121 laufend p0023647, 116 laufend special00008, 7 wartend
  p0023647. Offen fuer die komplette H = 0-Studie: Nachrechnung der 414
  H = 70-Punkte (77/88 komplett, 71_s075 30) — Block morgen mit korrekten
  Pfaden; Archiv nach `-H70` (Laufordner) und `00_results_H70_alpha1e-3/`.
- Tagesblock korrigieren: Walltime-Stop-Erkennung ueber `[WALLTIME] Lauf
  sauber unterbrochen` in .out (YIELD_WALLTIME_STOP steht nur in .err).
- 19:00 **Komplette H = 0-Studie in der Queue.** H = 70-Punkte archiviert
  (Laufordner -> `leS-r4-sigyXXX-H70/`, Auswertung -> `00_results_H70_alpha1e-3/`;
  77: 192, 88: 192, 71_s075: 27), 411 Nachrechnungen (A-Config) auf p0023647
  eingereicht (Doppel-Sperre: Jobname in Queue / JSON im Laufordner). Queue:
  141 laufend + 392 wartend p0023647, 114 laufend special00008 (laufen aus,
  nichts Neues dort). Erwartet: 77/88 je 1,5-3 h, gesamt 25-35k Kernstunden,
  ueber Nacht weitgehend durch. Morgen: Tagescheck (Walltime-Erkennung
  korrigiert), Fortsetzungen bei Bedarf.

## Session 10.09.2026 — Tagescheck: 249 Nachrechnungen an Knotenfehler gestorben

- 08:10: 510/768 H = 0 fertig (71: 87+96, 83: 96+96, 77: 81+13, 88: 15+26),
  11 laufend, Queue leer. **249 Nachrechnungs-Jobs (77/88) FAILED Exit 127
  nach 4-9 s** (18:07-18:51 am 09.09.): `FATAL: Couldn't determine user
  account information: unknown userid 661424150` beim Apptainer-Start —
  Knotenproblem (sssd/NSS), nicht unseres. **Schwarze-Loch-Knoten:**
  mpsd0319 (85 Abbrueche), mpsd0401 (81), mpsd0415 (83), mpsd0138 (3, 14:49).
  Kein Rechenstand verloren (0 Schritte). Resubmit der 249 mit
  `sbatch --exclude=mpsd0138,mpsd0319,mpsd0401,mpsd0415` auf p0023647.
  -> Support informieren (Knotenliste, Uhrzeiten, Fehlertext).
  Lehre: Nach einer Einreichwelle nach ~15 min `sacct ... State,ExitCode`
  pruefen — ein defekter Knoten frisst in 45 min eine ganze Welle.
- special00008: alle 116 fertig (COMPLETED), Endverbrauch ~50k Kernstunden.
  Nichts mehr dort.
- H0-Tests: 77 fertig (10 %), 88 fertig (JSON vorhanden, Resubmit hat
  uebersprungen), 71 laeuft (130 Schritte, 2e-3 bei 2,57 %), 83 laeuft (Fortsetzung).
- Speicher: /work 4,9 von 40 TB (015: 3,1 TB, 017: 1,5 TB) — kein Problem.
  $HOME 44 von 60 GB (74 %) — dort liegt der FEniCS-JIT-Cache; im Auge behalten.
- **special00008 endgueltig: 49 991 Kernstunden** (sreport = sacct-Summe;
  csreport 48,5k Stand Nacht) = 12,9 % von 386 496. Davon JM-25-83 komplett
  (192 Punkte, 44,7k) + 17 x JM-25-71_s100 (5,3k). Keine Jobs mehr dort.
- 09:00: 249 Nachrechnungen (77/88) mit --exclude der 4 Knoten auf p0023647
  eingereicht; 48 laufend, 212 wartend. Kontrolle nach 15 min auf FAILED 127.
- 08:40 Kontrolle der Resubmit-Welle: keine FAILED 127 mehr, 63 laufend /
  196 wartend, Knoten sauber verteilt (mpsc/mpsd, je 2 Jobs). Knotenausschluss
  wirkt. 511/768 fertig, alle H = 0. sig(2e-3)/sig(1e-3) = 1,068-1,092 ueber
  alle 8 Kombinationen -> Fliessflaeche waechst nahezu selbstaehnlich
  (interessant fuers Paper: Familie mit einem Skalierungsparameter).
- 14:05 **632/768 fertig, alle H = 0, keine Warteschlange mehr** (138 laufend,
  0 wartend, 83 COMPLETED in 3 h). dt_small/wallt/Traceback/stumm = 0.
  Fertig: 71_s100, 77_s075, 83_s075, 83_s100 (je 96); 71_s075 93, 77_s100 90.
  Rest: JM-25-88 (38 + 27 von je 96) — laeuft, ~2-3 h/Punkt -> heute Abend
  vollstaendig. Danach: Auswertung/Fit der Fliessflaechen.

## 10.09.2026, 21:18 — **STUDIE 017 KOMPLETT: 768/768 Punkte, alle H = 0**

4 Proben x 2 sig_y x 96 Richtungen, `hard = 0`, Abbruch alpha_avg = 2e-3,
Doku-Stufen 1e-3/5e-3/1e-2 mit Snapshot. Keine Abbrueche: dt_small 0,
Traceback 0, stumm 0, Walltime-Stops 0 (Hauptstudie). 29 652 akzeptierte
Schritte, 14 644 Verwerfungen. Queue leer.
Verbrauch: special00008 49 991 Kernstunden (nur JM-25-83 + 17 Punkte 71_s100),
Rest auf p0023647 (+ die 17 alten H = 70-Laeufe auf l0003507).
H = 70-Vorlauf (411 Punkte, Abbruch 1e-3) archiviert unter
`yield_surface_runs/*/leS-r4-sigyXXX-H70/` und `00_results_H70_alpha1e-3/`
-> vollstaendiger H-Sensitivitaetsvergleich fuer 384 Richtungen moeglich.
**H0-Plateau-Laeufe (ys_095, Ziel 10 %):** JM-25-77 fertig (9,95 %),
JM-25-88 fertig, JM-25-71 Walltime-Stop bei 5,13 % (211 Schritte),
JM-25-83 Walltime-Stop bei 5,75 % (68 Schritte) -> Resubmit noetig.
**Naechster Schritt: Auswertung** — Fliessflaechen (1e-3 und 2e-3) je Probe
und sig_y fitten, Selbstaehnlichkeit pruefen (sig2/sig1 = 1,068-1,092),
H-Vergleich H=0 vs H=70 fuer 384 Richtungen, Aufloesungsbefund r2/r4
dokumentieren.

## 10.09.2026 — Plateau-Teilstudie vorbereitet (Entscheidung Nutzer)

Umfang: **nur sigy075, 24 Richtungen je Probe** (jede 4. der 96), 4 Proben =
96 Punkte, Fortsetzung aus den vorhandenen 2e-3-Snapshots bis **5 %
Boxdehnung**. Grundlage (gemessen an den 4 H0-Laeufen): Tangente bei 5 %
zwischen 2,0 % (83/88) und 4,7 % (77) von E0 -> Quasi-Plateau; sig(5 %) liegt
15-20 % ueber sig(2e-3). Kosten je Punkt bis 5 %: 77 4,4 h, 88 11,7 h,
83 39 h, 71 44 h -> alle 768 Punkte waeren ~600k Kernstunden (ausgeschlossen);
96 Punkte ca. **75k**, durch Restart ab ~2,3 % effektiv ca. 55-60k.
Ziel der Teilstudie: pruefen, ob sig(5 %)/sig(2e-3) richtungsunabhaengig ist
(analog sig(2e-3)/sig(1e-3) = 1,068-1,092). Wenn ja, ist die Plateauflaeche
die skalierte 2e-3-Flaeche und die Vollstudie eruebrigt sich.
**Neues Skript `prepare_plateau_subset.py`** (Mac 017): sichert je Punkt
`yield_run_*.json` + `restart_meta_*.json` als `*.alpha2e-3` und entfernt die
yield_run-Datei (sonst ueberspringt der Job den Solverlauf); patcht die
Punkt-Config auf `total_time = 0.05` (t == strain_scale, Solver endet dort
regulaer und schreibt die Zusammenfassung — in elastoplastic.py geprueft:
after_last_timestep-Hook laeuft), setzt die alpha-Schwelle auf 0,05
(unerreichbar), damit alle Richtungen dieselbe Enddehnung erreichen, und
haelt 1e-3/2e-3/5e-3/1e-2 als Doku-Stufen mit Snapshot. Backups:
`config.json.vor_plateau`. Jobliste nach /tmp/plateau_jobs.txt.
Achtung: JM-25-71/83 brauchen > 24 h -> Walltime-Stop + Fortsetzung per
`resubmit_yield_surface_timeouts_CLUSTER.sh` (1-2 Ketten). Konto p0023647.
Die 2e-3-Auswertung bleibt unveraendert in `00_results/` — der Plateau-Lauf
ueberschreibt nur den Arbeitsordner-Stand (Backups s. o.).
- 21:40 **Plateau-Teilstudie eingereicht:** 96 Jobs (4 Proben x sigy075 x
  24 Richtungen, jede 4.) auf p0023647, `--exclude` der 4 defekten Knoten.
  Kontrolle vor Einreichung: total_time 0.05, hard 0.0, alpha-Abbruch 0,05
  (unerreichbar), Doku-Stufen 1e-3/2e-3/5e-3/1e-2, yield_run entfernt +
  Backup `.alpha2e-3`, 96 Config-Backups `.vor_plateau`, 00_results unberuehrt
  (770 JSONs) und zusaetzlich als `00_results_alpha2e-3_20260910.tar.gz` (37 MB)
  gesichert. Ausgangsstand der Punkte: 1,3-3,8 % Dehnung.
  Erwartung: 77/88 in einem Job durch; 71/83 brauchen 25-30 h ->
  Walltime-Stop + `INCLUDE_FAILED=1 MAX_CHAIN=2 resubmit_yield_surface_timeouts_CLUSTER.sh`.
  Auswertungsziel: sig(5 %)/sig(2e-3) je Richtung -> richtungsunabhaengig?

## 11.09.2026 — Plateau-Fortsetzung stoppte sofort: `yield_states` im Restart

Alle 96 Plateau-Jobs endeten nach 4-10 min mit `[STOP] alle Abbruchkriterien
erreicht: alpha_avg_material`, obwohl die Schwelle auf 0,05 stand und
`total_time_solver_horizon: 0.05` korrekt geladen wurde. **Ursache:**
`elastoplastic.py` laedt beim Restart `yield_states` aus `restart_meta`
(Z. 700) und prueft in Z. 959 nur `all(name in yield_states for name in
blocking_criteria)` — die (neue) Schwelle wird nicht erneut ausgewertet.
`alpha_avg_material` stand dort noch aus dem 2e-3-Lauf -> sofortiger Abbruch
nach einem Zeitschritt. Kosten: ~96 x 7 min x 32 = ca. 360 Kernstunden.
**Fix in `prepare_plateau_subset.py`:** vor dem Fortsetzen den Eintrag
`alpha_avg_material` aus `yield_states` in allen `restart_meta_*.json`
entfernen (Doku-Stufen bleiben stehen, damit keine doppelten Snapshots).
Zustand der Punkte danach unveraendert nutzbar (je ein Schritt weiter,
z. B. 2,690 % statt 2,680 %); Backups `.alpha2e-3` intakt.
**Merke:** Kriterien-Schwellen eines laufenden/fortgesetzten Punktes zu
aendern wirkt nur, wenn der zugehoerige `yield_states`-Eintrag entfernt wird.
- 11.09. 12:30 **Plateau-Fortsetzung laeuft korrekt** (nach yield_states-Fix):
  Laeufe enden regulaer bei t + dt > Tend, letzter Eintrag 4,91-5,00 %.
  Zwei Auswertungsfallen: (1) `restart_meta` wird beim regulaeren Ende NICHT
  aktualisiert (nur bei Ereignissen) -> Historie aus `yield_averages_*.json`
  (Liste) lesen; Feld-Snapshot bei 5 % fehlt -> spaetere Fortsetzung Richtung
  10 % wuerde beim letzten Ereignis-Snapshot (~2,7 %) ansetzen. TODO
  elastoplastic.py: Schluss-Snapshot + Meta bei Tend. (2) Schwelle "fertig"
  = letzter Eintrag >= 4,9 %, sig linear auf 5 % extrapoliert.
  **Erstes Ergebnis (33/96 Punkte):** sig(5 %)/sig(2e-3) Median 1,082,
  Spanne 1,045-1,130, Streuung +-2,0 %. Tangente bei 5 %: 0,9-2,2 % von E0
  (Plateau bestaetigt). JM-25-71 1,072 (3 Pkt), JM-25-88 1,073 (10, Spanne
  1,063-1,085), JM-25-77 1,088 (20, Spanne 1,045-1,130). Hoechste Verhaelt-
  nisse bei 77 in Richtungen mit grosser Spur (ys_016, 032, 080, 040:
  nahezu volumetrisch, Zug wie Druck), niedrigste bei deviatorischen
  (ys_092, 004) -> beim poroesesten Schaum milde Triaxialitaetsabhaengigkeit
  (Plateauflaeche entlang der hydrostatischen Achse ~13 % vs ~5 % im Schub
  ueber der 2e-3-Flaeche), bei den dichteren Schaeumen +-1 %.
  Laufzeiten bis 5 %: 77 0,75-2,5 h, 88 ~2,3 h, 71 ~2,2 h (Fortsetzung ab
  ~2,3 %) — viel billiger als geschaetzt, weil die Steifigkeit im Plateau
  grosse Schritte (dt 1e-3) erlaubt. 83 noch keiner fertig.
- 11.09. 13:00 **Fix umgesetzt und auf Scratch (per mv):** `00_template/
  elastoplastic.py` schreibt bei regulaerem Ende an total_time den letzten
  Schritt als Snapshot + restart_meta (`write_pending_state(
  "final_state_at_total_time")`, stop_reason `total_time_reached`, Logzeile
  `[STOP] total_time ... erreicht`). Gilt fuer alle Jobs, die ab jetzt
  starten; die laufenden 62 Plateau-Jobs haben noch die alte Kopie (ihre
  Historie liegt vollstaendig in yield_averages, nur der 5 %-Feldstand fehlt).

## 12.09.2026 — Plateau-Teilstudie: Ergebnis und zwei Auswertungsfallen

**Ergebnis (88 von 96 Punkten, sigy075, 5 % Dehnung, H = 0):**
sig(5 %)/sig(2e-3) Median **1,093**, Spanne 1,045-1,174. Kein konstanter
Faktor, sondern **klar von der Triaxialitaet abhaengig, und zwar vom BETRAG**
(U-Form: an beiden hydrostatischen Enden hoch, im Schub niedrig):
  |tr|/(|tr|+dev)   0,0-0,1: 1,081 (n=4) | 0,1-0,2: 1,073 (12) |
  0,2-0,3: 1,085 (19) | 0,3-0,45: 1,089 (15) | > 0,45: **1,133** (38)
Korrelation r = **+0,851** (signiert nur +0,21 -> der Betrag ist der
richtige Korrelat). Je Probe: 71 +0,914, 77 +0,803, 83 +0,951, 88 +0,865;
Mediane 1,091-1,100 (proben- und dichteunabhaengig!).
Deutung: unter hydrostatischer Last (Zug wie Druck) werden nach dem Erst-
fliessen fortlaufend weitere Stege rekrutiert -> weitere Verfestigung;
im Schub saettigt das frueh. Tangente bei 5 %: 0,9-2,2 % von E0 (Plateau).
**Fuers Paper:** Plateauflaeche = 2e-3-Flaeche, skaliert mit einem Faktor
f(|Triaxialitaet|) von 1,07 (Schub) bis 1,13 (hydrostatisch) - ein
zusaetzlicher Parameter, nicht 768 neue Rechnungen. Die Vollstudie bis zum
Plateau eruebrigt sich damit.

**Auswertungsfallen (beide haben mich heute in die Irre gefuehrt):**
1. `yield_averages_*.json` (und `restart_meta`) werden nur bei EREIGNISSEN
   geschrieben. Bei hart abgebrochenen Jobs steht dort ein alter Stand
   (z. B. 1,50 %), waehrend das .out-Log 3,82 % zeigt. Fortschritt immer am
   Log pruefen (`Computing solution at time =`), nicht an der Averages-Datei.
2. `[STOP] alle Abbruchkriterien erreicht` kann aus `yield_states` im
   Restart stammen (s. 11.09.), nicht aus der aktuellen Schwelle.
**Status:** 5 Punkte wurden nach 23,5 h hart von SLURM gekillt (Exit 15 statt
kontrolliertem Stop 3 — Walltime-Reserve zu klein bei 7-min-Schritten, 3
WALLTIME-Zeilen im Log). Alle 7 unterbrochenen Punkte (71: ys_024/036/072/088,
83: ys_016/072, 88: ys_068) standen bei 2,8-4,8 % und sind 12.09. 11:20 neu
eingereicht (Jobs 54533209-15), brauchen 1-3 h. **Echt gescheitert: nur
JM-25-88 ys_040** (`dt_below_minimum` bei 4,49 %) -> als Einzelfall
dokumentieren oder mit anderem Resume-dt wiederholen.
**TODO:** Walltime-Reserve in elastoplastic.py erhoehen (Faktor auf die
gemessene Schrittzeit), damit der kontrollierte Stop auch bei langen
Schritten greift.
- 12.09. 11:45 **Plateau-Teilstudie sigy100 eingereicht** (96 Punkte, 24 Ri.
  je Probe, p0023647, Knotenausschluss). Zweck: pruefen, ob f(|Triaxialitaet|)
  sigma_y-unabhaengig ist — bei sigy100 wird alpha 2e-3 spaeter erreicht,
  5 % liegt also relativ naeher am Erstfliessen, der Faktor koennte kleiner
  ausfallen. Dann waere die saubere Formulierung f(eps/eps_yield) statt
  f(eps absolut). Kosten sigy075 gemessen: **22 723 Kernstunden** fuer 96
  Punkte (Mittel je Punkt: 77 62 h*Kerne, 88 150, 83 301, 71 345;
  inkl. ~3 700 fuer 5 hart gekillte Jobs) -> sigy100 erwartet 15-20k.
  Diese Jobs haben den neuen Template-Stand -> Schluss-Snapshot bei 5 %
  vorhanden (bei sigy075 nicht).
  Nachtrag: Die 7 fortgesetzten sigy075-Punkte setzten bei 3,82-4,87 % auf
  (nur 88/ys_068 bei 2,27 %) — der harte Kill kostete also kaum Arbeit,
  Walltime-Reserve-Fix damit unkritisch.

## 13.09.2026 — Plateau-Teilstudie ABGESCHLOSSEN: 191/192 Punkte

Beide sig_y fertig (24 Richtungen je Probe, 5 % Dehnung, H = 0), keine
Abbrueche in der letzten Runde (103 COMPLETED, 0 Fehler).
**Kernergebnis: f = sig(5 %)/sig(2e-3) haengt vom BETRAG der Triaxialitaet ab
und ist sig_y-UNABHAENGIG** (Abweichung < 0,5 %):
  |tr|/(|tr|+dev)      sigy075        sigy100
  0,0-0,1 (Schub)      1,081 (4)      1,081 (4)
  0,1-0,2              1,073 (12)     1,076 (12)
  0,2-0,3              1,085 (20)     1,088 (20)
  0,3-0,45             1,091 (16)     1,092 (16)
  > 0,45 (hydrostat.)  1,135 (43)     1,140 (44)
  gesamt: 1,098 +-2,7 % (n=95) bzw. 1,102 +-2,8 % (n=96)
Korrelation je Probe/sig_y: r = +0,76 bis +0,95 (77 am schwaechsten,
83 am staerksten). Proben-Mediane 1,087-1,110 — dichteunabhaengig.
**Aussage fuers Paper:** Die Plateauflaeche (5 % Dehnung, Tangente < 2 % E0)
ist die 2e-3-Fliessflaeche, skaliert mit f(|Triaxialitaet|) ~ 1,07 (Schub)
bis 1,14 (hydrostatisch) — unabhaengig von Dichte und Grundfliessspannung.
Zusatzbefund: signierte Auswertung zeigte Zug 1,134 vs Druck 1,108 ->
leichte Zug-Druck-Asymmetrie, mit beiden sig_y jetzt belastbar pruefbar.
Kosten gesamt: sigy075 22 723 + sigy100 ca. 15-20k Kernstunden (statt
~600k fuer alle 768 Punkte bis 5 %).
**Offen: nur JM-25-88 sigy075 ys_040** (`dt_below_minimum` bei 4,49 %) —
als Einzelfall dokumentieren (Historie bis 4,49 % vorhanden).
**Naechster Schritt: Auswertung/Fit der Fliessflaechen** (1e-3, 2e-3,
Plateau), H-Vergleich H=0/H=70 (384 Richtungen), Aufloesung r2/r4.
- 14.09. Prompt fuer den Auswertungs-Chat geschrieben
  (`PROMPT_Auswertung_und_Datenpublikation.md`, im Studienordner): Kontext,
  Pfade, Datenstruktur, gesicherte Befunde, Fallen; Aufgabe A = Auswertung
  (Datensatz mit vollem Spannungszustand, Fits Deshpande-Fleck/Ellipsoid/Lode,
  Skalierungen, Plateau-Faktor, Numerikteil, Abbildungen), Aufgabe B =
  **Datenpublikation nach FAIR** (Zenodo/TUdatalib: Netze r4 (ggf. r2),
  Configs, Job- und Solverskripte, alex-Version, alle Ergebnis-JSONs,
  Auswertungsskripte, Abbildungen; Feldausgaben ~1,5 TB bleiben draussen;
  README + Datenwoerterbuch, LICENSE CC-BY-4.0/MIT, CITATION.cff, DataCite,
  Provenienz mit Commit-/Container-Hashes und Job-IDs, SHA256SUMS,
  JSON-Schema + flache CSV/Parquet, Packaging- und Pruefskript mit Sollzahlen
  768 + 191 + 411).

## 20.10.2026 — 1D-Druckversuch (verschiebungsgesteuert, freie Seitenflaechen) im 017-Modell

Anlass: Abgleich mit A01 (FFT, Julian): Plateau 4,5 MPa bei sig_y = 75 gegen unsere 6,4 MPa
(sig_y^perp aus der Fliessflaeche, KUBC auf geschlossener Schale). Hauptverdacht Randbedingung
-> den Druckversuch an JM-25-71 direkt nachrechnen. Dokumentation der Entscheidung:
Publikationsordner `decisions_log.md` Nachtrag 20.10. (28), Projekt-Doc `claude/abgleich_a01_fft_vs_fem_017.md`.

Aenderungen (Sicherungen `*.vor_druck_20261020`, volle Schale = Verhalten wie bisher):
- `make_mesh_dlfx_compatible_cluster.py`: `--anchor-faces` / `--config`. Fragment- und Scharnierfilter
  verankern nur noch an Schalenflaechen mit Dicke > 0 (aus `02d…boundary_seal.thicknesses`). Vorher
  galt jede Boxflaeche als Verankerung; ohne Seitenschale waeren seitlich "verankerte" Teile Starrkoerper.
  `dlfx_mesh.components.txt` nennt jetzt `anchor_faces`.
- `run_prepare_mesh_CLUSTER.sh`: uebergibt `--config "$CONFIG_PATH"` an den Konverter.
- `00_template/elastoplastic.py`: `shell_band_marker` / `interior_marker_from_shell` ueberspringen
  Flaechen mit Dicke 0 (sonst wuerden Knoten exakt auf der Boxflaeche gehalten und randnahe Zellen
  aus dem reduzierten Volumen fallen). Neu in `averaged_history`: `sigma_nominal_reaction`
  (= R_axis / Querschnitt der Bounding-Box senkrecht zur Lastachse) und `eps_axial_platen`;
  im Summary-JSON `cross_section_area_perp_to_loading_axis`, `loading_axis`, `dirichlet_faces`;
  Log druckt `dirichlet_faces:` und `cross_section_area_perp_to_loading_axis:`.
- neu `setup_compression_jobs.py` (Aufruf: `python3 setup_compression_jobs.py --dataset JM-25-71 --sig-y 75 180 100`):
  leitet aus `config-JM-25-71-r4-sigy075.json` (aus dem Publikationsordner hierher kopiert) die Configs
  `config-JM-25-71-r4-druckx-sigy{075,100,180}.json` ab: dataset.id `JM-25-71_les_r4_druckx` (eigenes Netz),
  Schale y/z = 0, x = 6 Voxel, `loading_directions ["x"]`, eps = diag(-0,25 s, 0, 0) -> u = eps.x auf den
  x-Platten = haftende Platten, `total_time 0.1` (|eps| = 2,5 %), alle Kriterien `blocking false`,
  Snapshots alle 0,25 % Dehnung (strain_scale_interval 0.01) bzw. 120 min.
  Jobs in `compression_jobs/<ds>_druckx_sigy<XXX>/ys_druck_x/` (Header wie Produktion: -A p0023647,
  -t 1440, -n 32, -N 1, 5600 MB/CPU), Einreichen mit `compression_jobs/submit_compression_CLUSTER.sh`
  (1 Prep-Job, dann je sig_y eine Kette aus 3 Gliedern: afterok:prep + afternotok:Vorgaenger).
- Erwartung: Prep 15-20 min; Lauf 71 bis Stufe-II-Dehnung ~12 h, bis 2,5 % 2-3 Glieder.
  Vorhersage fuer sig_y = 180 aus der Skalierung m = 0,93: sig_y^perp(KUBC) ~ 14,5 MPa.
- Kontrollen nach dem Start: Prep-Log "Prepared mesh"; `dlfx_mesh.components.txt` -> `anchor_faces: x_min,x_max`;
  `dlfx_mesh.hinges.txt` -> 1 Komponente; Punkt-Log -> `dirichlet_faces: ['x_min', 'x_max']`,
  Querschnitt ~ 343 mm^2 (19,5 x 17,6); in der Historie sigma_avg_reduced_volume[1][1], [2][2] ~ 0
  (freie Seitenflaechen) und sigma_nominal_reaction ~ sigma_avg_reduced_volume[0][0].
- neu `evaluate_compression_run.py <…>/yield_averages_std_x.json [--plot kurve.png]`: Nennspannung (Reaktionskraft)
  und Volumenmittel gegen Plattenstauchung, E (10-40 % von sigma_max, wie Sven), Rp0,2, sigma bei 0,25…2,5 %,
  Kontrolle Querspannungen/Axial und Reaktion/Volumenmittel; CSV je Lauf. Mit synthetischer Kurve getestet.
- **20.10.2026 15:20 eingereicht (p0023647):** Prep 55498713; Ketten sigy075 55498714-716, sigy180 55498717-719,
  sigy100 55498720-722 (je afterok:Prep, Glieder 2/3 zusaetzlich afternotok:Vorgaenger). Commit a90969d (Meshing-Repo).
- Befund beim `git pull` auf dem Login-Node: die dort liegenden, ungetrackten `config-JM-25-71-r4-sigy{075,100}.json`
  waren ein **Altstand** (hard = 70, alpha-Schwelle 0,001, ohne Doku-Stufen = Stand vor patch_yield_criteria 09.09.);
  die Repo-Fassung (aus dem Publikationsordner = Scratch-Produktion) hat hard = 0, Schwelle 0,002, history "Variante A".
  Altstand liegt in `$HOME/cfg_bak_20261020/` (loeschbar). Die Druck-Configs sind aus der Produktionsfassung abgeleitet.
- Dry-Run-Ausgabe von submit_compression_CLUSTER.sh war verschachtelt (Echo der sbatch-Zeile landete in der Job-ID);
  behoben (Echo nach stderr), wirkt sich auf den echten Lauf nicht aus. Beim naechsten Commit mitnehmen.
- **20.10. 18:30, Kontrolle der laufenden Druck-Jobs (55498714/717/720 seit 15:40 auf mpsd0010/12/30):** dirichlet_faces ['x_min','x_max'],
  Schalenbreiten y/z = 0, Querschnitt 342,68 mm^2 (L_x 19,372 mm), Netz 3 900 334 Tets / 1 192 196 Knoten.
  **Relative Dichte des Druckmodells: reduced_volume_material 1203,64 mm^3 / Innenvolumen (19,372 - 0,8016) x 342,68 = 6363,6 mm^3 = 0,1891**
  (KUBC-Produktionsnetz 0,1768). Grund: die aeusseren 9/6 Voxellagen in y/z sind jetzt echter Schaum statt Al-Schale, und JM-25-71 hat
  dichte Raender (Voxelprofil: dichte Raender, duenne Mitte). +7 % Dichte ~ +12 % Festigkeit (rho^1,75) - beim Vergleich 1D gegen KUBC
  herausrechnen bzw. nennen; gegenueber Sven ist 0,189 die passendere Probendichte (Voxel 0,194/0,202).
  Lauf 075 bei t = 6,5e-3 (eps 0,16 %) nach 2 h 50, dt 2,5e-4 mit einzelnen Verwerfungen (normal, Produktion 28,8 % Verwerfungen).
  Apptainer-Warnung "Error changing the container working directory ... /home/as12vapa/meshing/Meshing" ist harmlos (sbatch-Startordner
  nicht gebunden, run_container setzt --chdir auf den Zielordner; Solver laeuft).
- Login-Hosts Lichtenberg (aus ~/.ssh/config des Nutzers, 20.10.2026): `lcluster13.hrz.tu-darmstadt.de` (Key id_ed25519_tu_darmstadt),
  `lcluster20.hrz.tu-darmstadt.de`; User as12vapa. scp direkt in den Scratch moeglich:
  `scp <datei> lcluster13.hrz.tu-darmstadt.de:/work/scratch/as12vapa/pygalmesh/data/scripts/017-Yield-Surface-Batch-leS-nohinge/`
- `evaluate_compression_run.py` liest seit 20.10. 18:40 auch die laufend geschriebene `elastoplastic_std_x_graphs.txt`
  (`--area 342.68`, eps = 0,25 t); `yield_averages_std_x.json` entsteht erst am Laufende. Im Container `--bind /work/scratch/as12vapa` setzen.
- **20.10. 18:45 — Falle Reaktionskraft:** `elastoplastic_*_graphs.txt` (R_x, R_y, R_z) ist die Eigenspannung der zwangsverschobenen
  Platte/Schale (alle Knoten im Schalenband haben u = eps.x, die Aussenflaeche traegt sigma_xx der einachsig gedehnten Vollplatte:
  "E" 68 GPa, 109 MPa bei 0,16 %). Fuer die Nennspannung des 1D-Versuchs gilt nur das Volumenmittel sigma_avg[a][a] ueber das
  reduzierte Volumen (= F/A bei freien Seitenflaechen und lastfreien Poren). `sigma_nominal_reaction` aus der Historie entfernt,
  ersetzt durch `sigma_nominal_volume_avg`. Neu: `<script>_<mat>_<dir>_averages.txt` wird je Schritt geschrieben
  (t, strain_scale, eps_axial, sig_xx, sig_yy, sig_zz, alpha_avg, eps_p_eq_macro, Newton-Iter.) -> `evaluate_compression_run.py` liest sie.
  Die laufenden Glieder 1 (alte Template-Kopie) schreiben sie nicht; ihre Historie kommt mit dem JSON am Walltime-Stopp (~21.10. 15:40),
  Glieder 2/3 kopieren das neue Template beim Restart. Bewusst NICHT abgebrochen (Restart-Sprung +1,3 % laege sonst im Rp0,2-Bereich).
- 20.10. 18:46: Commit 41fa115 (Template mit _averages.txt, Auswerteskript, Transferregel) per git pull + Sync im Scratch. Glieder 1 laufen
  weiter mit alter Kopie; Stand 18:44: sigy075 0,17 %, sigy100 0,31 %, sigy180 0,66 % Stauchung. Naechster Schritt: 21.10. ab ~15:40
  JSON der Glieder 1 auswerten (evaluate_compression_run.py), danach Live-Datei der Glieder 2/3.
- **20.10. 18:55 — zweite Querrichtung y angelegt** (Nutzer: Lastrichtung des Versuchs im CT-System unbekannt, x und y sind beide 20-mm-Kanten):
  `python3 setup_compression_jobs.py --dataset JM-25-71 --sig-y 75 180 100 --axis y` -> eigenes Netz `JM-25-71_les_r4_drucky`
  (Platten y_min/y_max 9 Voxel = 0,6 mm, x/z frei), Configs `config-JM-25-71-r4-drucky-sigy*.json`, Jobs `compression_jobs/JM-25-71_drucky_sigy*/ys_druck_y/`,
  Submit-Skript jetzt je Achse: `submit_compression_druckx_CLUSTER.sh` (umbenannt, bereits eingereicht) und `submit_compression_drucky_CLUSTER.sh`.
  Querschnitt y: 19,37 x 17,6 ~ 341 mm^2 (steht im Job-Log). Erwartung: x/y-Isotropie der KUBC-Flaeche (0,98-1,01) auch im freien Druckversuch;
  Abweichung waere Randeffekt/Probenstreuung der Randzellen.
- **20.10. 18:52 y-Richtung eingereicht (Commit 311ac49, p0023647):** Prep 55499943 (Priority-Wartung); Ketten sigy075 55499944-946,
  sigy180 55499947-949, sigy100 55499950-952. Auf dem Scratch liegt noch die alte `submit_compression_CLUSTER.sh` (rsync loescht nicht;
  identisch mit druckx-Fassung, ignorieren/loeschen). Exec-Bits der Submit-Skripte auf dem Mac wieder gesetzt (naechster Commit).

## 21.10.2026 — Druckversuche, Stand 08:50 und Uebergabe an Claude Code auf dem Cluster
- Netz y (Prep 55499943) fertig: 3 994 011 Tets, 1 197 751 Knoten, 1 Komponente, anchor_faces y_min,y_max, 11 Fragmente (912 Knoten) und
  127 Scharnierteile (402 Zellen) entfernt. y-Ketten 55499944-952 koennen starten (neues Template -> `_averages.txt` live).
- Uebergabe-Prompt fuer eine Claude-Code-Session auf dem Login-Node: `CLAUDE_CLUSTER_HANDOFF_20261021.md` (Regeln: nichts abbrechen,
  nur p0023647, Transfer nur Git, Ergebnisse klein nach compression_jobs/ergebnisse/, alles hier dokumentieren).

## 21.10.2026 — Druckversuche, Cluster-Session (Claude Code auf dem Mac, Cluster per ssh)
**09:00 — Block 1: Status (Aufgabe 1) und Erstkontrolle y (Aufgabe 2).** Nichts abgebrochen, nichts eingereicht.
- **y-Richtung komplett in Glied 1** (neues Template, je 1 Glied gereicht, kein Restart): sigy075 55499944 COMPLETED 0:0 nach 9:42 h
  (t = 0,0991 / eps 2,478 %, 110 Schritte), sigy100 55499950 nach 7:23 h (t = 0,0999 / 2,498 %, 104), sigy180 55499947 nach 6:48 h
  (t = 0,0995 / 2,488 %, 103). Log jeweils `[STOP] total_time = 0.1 erreicht`, `Yield-surface point complete`.
  Letzte Historienzeile liegt knapp unter 0,1, weil der letzte Schritt ueber 0,1 hinausgeht (t = 0,1001…0,1009) und der
  Schluss-Snapshot den vorletzten Stand schreibt -> fuer 2,5 % den Wert bei 2,48 % nehmen bzw. extrapolieren.
- **x/sigy180 55498717 ebenfalls in Glied 1 fertig** (10:13 h, t = 0,099 / 2,475 %, 118 Schritte, alte Template-Kopie ->
  `yield_averages_std_x.json` liegt vor, kein `_averages.txt`).
- Kettenmechanik: Glieder 2 (55498718, 55499945/948/951) wurden von Slurm CANCELLED (afternotok nie erfuellt, Glied 1 war ok);
  dadurch wurde afternotok fuer Glied 3 erfuellt und Glieder 3 (55498719, 55499946/949/952) liefen 2-10 s, erkannten den fertigen
  Lauf und kopierten nur die Ergebnisse erneut nach `00_results/` (Exit 0, harmlos). Kein Handlungsbedarf.
- **x/sigy075 55498714 und x/sigy100 55498720 laufen** (mpsd0010/0030, 17:19 h um 08:59), Stand eps 0,82 % (t 0,0328) bzw. 1,64 % (t 0,0655).
  Walltime-Stopp 21.10. ~15:25 (15 min Sicherheitsabstand vor 15:40) -> Glieder 2 (55498715 / 55498721, PENDING Dependency) setzen fort.
- **Erstkontrolle y (alle drei Laeufe identisch):** `dirichlet_faces: ['y_min', 'y_max']`; Querschnitt **340,34 mm^2** (L_y 19,506 mm);
  `reduced_volume_material` **1176,22 mm^3** (x-Netz: 1203,64; y-Netz hat andere Randlagen frei -> Dichte y separat rechnen:
  1176,22 / ((19,506 - 1,2) x 340,34) = **0,1888**, praktisch gleich x 0,1891). Newton max. 9 (075) / 7 (100) / 7 (180) <= 12.
  "NO CONVERGENCE" (dt-Halbierung) 14x / 1x / 0x. Keine MUMPS-Fehler, kein Traceback, keine NaN in `_averages.txt`.
  `.err` je 1 Zeile = harmlose Apptainer-chdir-Warnung.
- Auffaellig fuer Aufgabe 3 (noch nicht ausgewertet): Querspannungen am Ende nicht klein — y075 bei 2,48 %: sig_yy -5,26, sig_xx -0,74,
  sig_zz -0,57 MPa (|quer|/axial bis 0,14), y100 -6,77 / -0,91 / -0,71, y180 -11,38 / -1,42 / -1,15 (0,12). Erwartung war <= 0,05.
  Vermutung: haftende Platten (u = eps.x auf dem Plattenband, Querdehnung an den Platten behindert) -> Volumenmittel enthaelt
  Querdruck aus den plattennahen Schichten. Bei der Auswertung pruefen (Verlauf ueber eps, nicht nur Endwert).

**09:03 — Block 2: Auswertung (Aufgabe 3) y/75, y/100, y/180, x/180.** Nichts abgebrochen, nichts eingereicht.
- Per scp nach `compression_jobs/ergebnisse/druck<a>_sigy<XXX>/` geholt: `_averages.txt` (y), `yield_averages_*.json`, `yield_run_*.json`, `*_log.txt`
  (zusammen ~0,8 MB). Hinweis: scp auf dem Mac (SFTP-Modus) expandiert `{a,b}` im Remote-Pfad nicht -> Dateien einzeln holen.
- Lokal ausgewertet (`python3 evaluate_compression_run.py --axis y … --plot ergebnisse/druck_71_y.png`; x/180 aus dem JSON).
  `_averages.txt` und JSON liefern fuer y/75 identische Kennwerte (Kontrolle). Tabelle: `compression_jobs/ergebnisse/kennwerte_druck_71.md` + `.csv`.
- Kennwerte (MPa; E Sekante 10-40 %):
  y/75 E 3679, Rp0,2 4,07, sig1% 4,70, sig_end 5,26 (2,48 %); y/100 E 3892, Rp 5,26, sig1% 6,07, sig_end 6,77;
  y/180 E 3806, Rp 8,92, sig1% 10,20, sig_end 11,38; x/180 E 4027, Rp 9,88, sig1% 11,28, sig_end 12,53. Alle Kurven monoton.
- **1D / KUBC (sig^perp 6,40 / 8,41 / 14,5):** Rp0,2 roh 0,62-0,64 (y), 0,68 (x/180); dichtekorrigiert (rho 0,189 -> 0,1768, Faktor 1,12/1,14)
  0,54-0,57 (y), 0,60-0,61 (x). sig 1 % roh 0,70-0,74 (y), 0,78 (x); korr. 0,62-0,66 (y), 0,68-0,69 (x).
  -> Die KUBC-Schale ueberschaetzt die Druckfestigkeit um Faktor ~1,4-1,8. y/75 (4,7 bei 1 %, 5,1 bei 2 %) liegt nahe am A01-FFT-Plateau 4,5.
- **x/y bei 180:** 1,10-1,11 (Rp, sig1%, sig_end), E 1,06 — trotz gleicher Dichte (0,1891/0,1888). KUBC-Flaeche war isotrop (0,98-1,01).
- **Versuch** (Rp 7,7 / sig_max 11,2 / Plateau 9,6 / E 1760): liegt zwischen sig_y 100 und 180; y/180 trifft sig_max und Plateau-Niveau gut.
  Modell-E 2,1-2,3 x Versuch.
- **Querspannungs-Kriterium <= 0,05 NICHT erfuellt:** quer/axial 0,09-0,11 schon elastisch, steigt auf 0,12-0,14 am Ende (x-Querrichtung staerker als z).
  Deutung: haftende Platten sperren die Querdehnung; bei freien Seitenflaechen ist das Volumenmittel der Querspannung das Moment der
  Schubtraktionen an den Plattengrenzflaechen. Kein Fehler im Lauf, aber Randbedingungs-Effekt -> axialer Kennwert eher leicht ueberschaetzt.
  Gegenprobe mit gleitenden Platten waere eine Parameteraenderung -> nur nach Entscheidung des Nutzers.
- Kleinigkeit: Legende im Plot zeigt den Elternordnernamen ("ergebnisse") statt des Laufs (Label aus dem Pfad) — kosmetisch, nicht geaendert.
- Offen: x/75 und x/100 (Glieder 1 bis ~15:25, Historie dann im JSON; Glieder 2 55498715/55498721 setzen fort).
- `.gitignore` der Repo-Wurzel ignoriert `*.csv`/`*.png` -> Ergebnis-CSVs und `druck_71_y.png` in `compression_jobs/ergebnisse/` mit `git add -f` aufgenommen.

**09:19 — Block 3: Klärung Randbedingung, Rp0,2-Vorschrift, Interpretation, Learnings.** Nichts abgebrochen, nichts eingereicht.
- Nutzerfragen beantwortet in `compression_jobs/ergebnisse/INTERPRETATION_Diskrepanz_druck_71_20261021.md`:
  (1) „Behinderung der Querdehnung" = Haftung an den beiden Platten ⊥ Last (u_quer = 0 auf dem Plattenband); parallel zur Last keine Platten
  (geprueft: Config thicknesses x/z = 0, Log dirichlet_faces nur y). (2) Rp0,2 wie Versuch (E 10–40 % σ_max, 0,2-%-Parallele); robust gegen E
  (E₀: −0,5 %, Versuchs-E 1760: +5…+11 %). (3) Interpretation: KUBC→1D Randbedingung (Faktor 1,4–1,8), 1D-FEM ≈ A01-FFT (±10 %),
  Versuch braucht σ_y,eff 136–177 MPa (ideal plastisch) = σ_y,0 ~100 + Verfestigung; σ̄_1D ∝ σ_y^0,88–0,90. KUBC-Fläche nicht neu rechnen;
  Vorschlag (Entscheidung Nutzer): 1D-Lauf mit Verfestigung H (σ_y 100) und ggf. Gleitplatten-Lauf.
- Neu: `ergebnisse/plot_druck_vs_versuch.py` → `druck_71_vs_versuch.png` (Versuch 71 MTS-korrigiert gegen 1D-Kurven, KUBC-/FFT-Linien).
- Learnings fuer andere Agenten: `CLAUDE.md` Abschnitt 7; Kurzfassung im Publikationsordner `decisions_log.md` Nachtrag 21.10. (34).
- Check x/75, x/100 fuer 15:43 eingeplant (Session-Cron, Nutzer-Freigabe).
- (Korrektur: Blockzeiten 2/3 urspruenglich falsch als 09:35/10:40 notiert, richtig 09:03/09:19 = Commitzeiten.)

**09:40 — Block 4: 1D-Lauf mit Verfestigung VORBEREITET (nicht eingereicht), Mail-Entwurf an Julian.**
- `setup_compression_jobs.py` um `--hard H` (lineare isotrope Verfestigung, sigma = sig_y + H*alpha, alpha = plastische Vergleichsdehnung)
  und `--variant <tag>` erweitert (Pflicht mit --hard; haengt den Tag an Label/Jobordner/Config/Submit-Skript, damit nichts ueberschrieben wird).
  Sicherung `setup_compression_jobs.py.vor_hard_20261021` (nicht im Repo).
- Erzeugt: `python3 setup_compression_jobs.py --dataset JM-25-71 --axis y --sig-y 100 --hard 2000 --variant h2000` ->
  `config-JM-25-71-r4-drucky-sigy100h2000.json`, `compression_jobs/JM-25-71_drucky_sigy100h2000/ys_druck_y/` (Job JM-25-71_s100h2000-drucky),
  `compression_jobs/submit_compression_drucky-h2000_CLUSTER.sh` (Netz y vorhanden -> kein Prep; Kette 3 Glieder, p0023647).
  Diff zur Config sigy100: nur binning.label, history, material_sets.std.hard 0 -> 2000. Laufordner `yield_surface_runs/.../leS-r4-drucky-sigy100h2000/`.
- Wahl H = 2000 MPa: AlSi10Mg Guss (DIN EN 1706, EN AC-43000 Kokille F, Mindestwerte Rp0,2 90 / Rm 180 MPa, A 2,5 %; typische Werte hoeher)
  -> von sig_y,0 = 100 auf ~ 200 MPa ueber ~ 5 % plastische Vergleichsdehnung. Werte vor Verwendung im Paper belegen.
  Erwartung (grob): alpha_avg_material am Ende von y/100 ideal 0,0086 -> mittlere Zusatzspannung nur ~ +17 MPa, lokal mehr; der Lauf wird
  das Versuchsmaximum 11,2 vermutlich NICHT erreichen (ideal braucht sig_y,eff ~ 177). Er zeigt, ob gusstypische Verfestigung die Kurvenform
  (runder Uebergang) erklaert und wie viel vom Abstand sie traegt. Weitere H-Werte: gleicher Aufruf mit anderem --hard/--variant.
- Einreichen (nur nach Freigabe): Mac push -> Cluster `git pull` + `SKIP_GENERATE=1 …/batch_create_folders_CLUSTER.sh` ->
  `DRY_RUN=1 $S017/compression_jobs/submit_compression_drucky-h2000_CLUSTER.sh`, dann ohne DRY_RUN.
- Mail-Entwurf an Julian (A01): Publikationsordner `emails/entwurf_mail_julian_druckversuch_1D_20261021.txt` (Versand durch Nutzer).

**09:44 — Block 5: Verfestigungslauf EINGEREICHT (Freigabe Nutzer).** Commit 4a9e26c per git pull auf dem Cluster, Sync (rsync code 23 = harmlos),
cmp: Job-Config, Job-Skript, Submit-Skript, Template aktuell. Dry-Run ok (Netz vorhanden, kein Prep). Eingereicht 09:43 auf p0023647:
**JM-25-71_drucky_sigy100h2000 (σ_y 100, H 2000): Glied 1 55505395, Glied 2 55505396, Glied 3 55505397** (afternotok-Kette).
Glied 1 PENDING (None) um 09:44. Laufordner `yield_surface_runs/JM-25-71_les_r4_drucky/leS-r4-drucky-sigy100h2000/ys_druck_y/`, live `_averages.txt`.
- Nutzer: Julian (A01, FFT) rechnet mit grossen Deformationen und spaeter mit Kontakt -> Stegknicken moeglich, Kleindehnungsmodell nicht;
  FFT leicht unter 1D-FEM ist erwartbar. Interpretation und Mail-Entwurf entsprechend angepasst.

**10:19 — Block 6: Status, Erstkontrolle Verfestigungslauf.** Mail an Julian vom Nutzer verschickt (Entwurf im Publikationsordner `emails/`).
- 55505395 (sigy100h2000) laeuft seit ~09:44 auf mpsd0008. Erstkontrolle ok: `sig_y: 100.0, hard: 2000.0`, dirichlet_faces ['y_min','y_max'],
  Querschnitt 340,34, reduced_volume_material 1176,22 (wie y-Netz), kein MUMPS-Fehler/Traceback, `.err` nur Apptainer-Warnung,
  Newton max. 6 nach 12 Schritten. Stand 0,21 %: sig_yy 5,20 MPa (ideal sigy100 bei 0,20 %: 4,72).
- x/75 bei 0,875 %, x/100 bei 1,775 % (Glieder 1, Walltime-Stopp ~15:25).

**10:46 — Status.** Alles laeuft, keine Fehler.
- x/75 (55498714) 0,894 %, x/100 (55498720) 1,825 % nach 19:06 h; Glieder 2/3 PENDING (Dependency), Walltime-Stopp ~15:25.
- sigy100h2000 (55505395) nach 1:02 h bei 0,438 % (21 Schritte, Newton max. 6, keine dt-Halbierung, kein Traceback/MUMPS):
  sig_yy 6,55 MPa gegen ideal sigy100 5,48 und Versuch (MTS korr.) 5,83 bei gleicher Stauchung -> liegt schon ueber dem Versuch
  (Versuch hat flacheren Anstieg/Belastungsmodul 1760); Gesamtbild erst mit der vollen Kurve bewerten.

**Nachmittag — Block 7: Antwort Julian (A01) eingearbeitet.** (Text vom Nutzer im Chat weitergereicht, mit zwei Kurvenbildern σ_y 75/180.)
- GeoDict, RB „Mixed" = glatte starre Platten + freie Seiten (Luftschicht), small strain mit Updated Lagrange, ideal plastisch, E 70 GPa, ν 0,33,
  Voxel 66,8 µm, 290×292×263, ρ 0,214 (voll aufgeloest 0,2015). Neu hoeher aufgeloest bis 1,5 %: σ_y 75 → Rp0,2 5,05, σ(1 %) 5,26, σ(1,5 %) 5,256.
  Schaetzt σ_y,eff 160–170 MPa; will σ_y 100 + lineare Verfestigung mit unseren Parametern nachrechnen.
- Vergleich (1D-FEM y auf ρ 0,214 hochgerechnet, ×1,245): Rp0,2 5,07 gegen 5,05 (**Faktor 1,00**); σ(1 %) 5,86 / 5,26; σ(1,5 %) 6,15 / 5,26;
  E 4860 / ≈ 4400. FFT-Rp0,2 auf KUBC-Dichte / KUBC = 0,565 (FEM 0,56).
- **Korrektur:** strukturelle Verfestigung im 1D-FEM (+21 % Rp→1,5 %) kommt grossteils von den haftenden Platten (FFT glatt: +4 %).
  Interpretation §4(d) als ueberholt markiert, neuer §7. Empfehlung: Gleitplatten-Variante im FEM (Entscheidung Nutzer).
- Antwortentwurf mit Verfestigungsparametern: Publikationsordner `emails/entwurf_antwort_julian_verfestigung_20261021.txt`.
- Nutzer: Gleitung im Versuch eher behindert → Arbeitsannahme haftende Platten (FEM) naeher am Versuch, glatte Platten (FFT) = untere Grenze;
  Gleitplatten-Variante im FEM nicht gebaut. Antwortentwurf an Julian umformuliert (Frage, ob GeoDict haftende Stirnflaechen rechnen kann).
- Nutzer hat Julian selbst geantwortet (H = 2000 genannt; Bitte, die Querkontraktion an den Stirnflaechen zu sperren = haftend wie im FEM).
  Antwortentwurf im Publikationsordner damit ueberholt. Erwartet: FFT mit haftenden Stirnflaechen → Kurvenvergleich nach dem Fliessbeginn.

**15:43 — Block 8: Check Walltime-Stopp x/75, x/100; Verfestigungslauf fertig.** Nichts abgebrochen, nichts eingereicht.
- 55498714 (x/75) FAILED 3:0 nach 23:29 h = kontrollierter Walltime-Stopp bei t 0,04375 (1,09 %); 55498720 (x/100) 3:0 nach 23:32 h bei t 0,09 (2,26 %).
  Glieder 2 laufen: 55498715 seit 15:09:48 (mpsd0008), 55498721 seit 15:12:28 (mpsd0010); Glieder 3 (716/722) PENDING.
- Erstkontrolle Glieder 2 ok: dirichlet_faces ['x_min','x_max'], A 342,68, reduced_volume_material 1203,64, sig_y 75/100 hard 0, Newton 6–8,
  kein Traceback/MUMPS/NaN, `.err` nur Apptainer-Warnung. Neues Template -> `_averages.txt` ab Restart. **Kein Restart-Sprung** (σ Ende Glied 1 = Start Glied 2).
- Kein `yield_averages_std_x.json` am Walltime-Stopp; die Historie steht in `restart_meta_elastoplastic_std_x.json` (`averaged_history`, 171/182 Eintraege)
  -> nach `ergebnisse/druckx_sigy0{75,100}/glied1_restart_meta_*.json` geholt; evaluate_compression_run.py liest sie direkt.
  x/75 (bis 1,09 %): E 3997, Rp0,2 4,52, σ1% 5,21; x/100 (bis 2,26 %): E 3956, Rp0,2 5,86, σ1% 6,72, σ2% 7,27. **x/y = 1,11** bei allen σ_y.
- **sigy100h2000 (55505395) COMPLETED 0:0 nach 5:17 h** (bis 2,49 %; Glied 2 CANCELLED, Glied 3 9 s = harmlos). Gegen Versuch:
  0,5 % 6,82/6,32 · 1 % 8,49/8,70 · 1,5 % 9,80/9,90 · 2 % 10,97/10,61 · 2,48 % 12,02/11,02 MPa -> **0,5–2 % auf ±5 % getroffen**, danach zu steil
  (lineare Verfestigung ohne Saettigung, 219 MPa Steigung; Versuch flacht zum Max. 11,2 bei 3,1 % ab). Rp0,2 (E0) 6,16, mit E 1760: 7,26 (Versuch 7,7).
  E_10_40 = 2551 ist Artefakt (Fenster reicht in den Fliessbereich). Vorbehalte: y (x +11 %), Dichte 0,189 vs ~0,20, haftende Platten.
- Ergebnisse: `kennwerte_druck_71.md/.csv` ergaenzt, `druck_71_vs_versuch.png` mit x/75, x/100, h2000 und neuer FFT-Linie (5,26).

## 22.10.2026 — Druckversuche, Fortsetzung
**09:20 — DIC-Check Tonnenform, x-Verfestigungslauf vorbereitet.**
- DIC-Videos JM-25-71 (Hauptdehnung 1, 1 Bild je Schritt) mit ffmpeg ausgewertet, Ablage Publikationsordner
  `AlSi10MgSchaeumeDruckversucheelasto-plastisch/Auswertung_Claude_20261020/DIC_Tonnenform_Check_20261022.md` (+ 3 Bilder).
  Ergebnis: bis ~3 % nicht aufloesbar (Farbskala 0–150 mstrain, Kontur ±0,1–0,15 mm); auch bei ~10 % keine messbare Ausbauchung
  (Querdehnung des Schaums klein, zerdrueckender Schaum) -> wenig Reibung reicht zum Haften (stuetzt „eher haftend"), Querbehinderung im
  Versuch aber vermutlich schwaecher als im FEM. Quetschband nach dem Maximum an der bewegten Platte. Quantitativ nur mit DIC-Rohdaten (Sven).
- Vorbereitet (nicht eingereicht): `python3 setup_compression_jobs.py --dataset JM-25-71 --axis x --sig-y 100 --hard 2000 --variant h2000`
  -> `config-JM-25-71-r4-druckx-sigy100h2000.json`, `compression_jobs/JM-25-71_druckx_sigy100h2000/ys_druck_x/`,
  `compression_jobs/submit_compression_druckx-h2000_CLUSTER.sh`. Diff zur Config druckx-sigy100: nur label, history, hard 0 -> 2000.
  Zweck: x ist bei gleichem σ_y 11 % fester als y; zeigt, ob H 2000 in x ueber dem Versuch liegt (Klammer fuer H).
- Nebenbefund: **x/100 fertig** — Glied 2 55498721 COMPLETED 0:0 am 21.10. 18:02 nach 2:50 h (t = 0,1 erreicht, letzte Zeile 2,475 %), Glied 3 55498722 CANCELLED (harmlos).
  JSON geholt, Kennwerte unveraendert gegenueber Glied 1 bis 2,26 %, σ_end 7,46 MPa bei 2,48 %, quer/axial 0,131. Tabelle/CSV/Plot aktualisiert.
  x/75 (Glied 2 55498715) um 09:25 bei 1,93 %, Walltime-Stopp ~15:10 -> Glied 3 (55498716) noetig fuer den Rest bis 2,5 %.
- x-Verfestigungslauf: Sync + Dry-Run ok (Netz x vorhanden, kein Prep). Einreichen wartet auf Freigabe.
