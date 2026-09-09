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
