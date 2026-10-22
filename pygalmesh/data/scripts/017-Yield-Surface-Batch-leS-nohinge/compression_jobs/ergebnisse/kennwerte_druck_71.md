# Kennwerte 1D-Druckversuch JM-25-71 (Studie 017, r4, freie Seitenflaechen, haftende Platten)

Stand 21.10.2026 09:03. Nennspannung = Volumenmittel sigma_aa ueber das reduzierte Volumen (`_averages.txt` bzw. `yield_averages_std_x.json`),
ausgewertet mit `evaluate_compression_run.py` (E = Sekante 10-40 % von sigma_max). Werte in MPa, Dehnung = Plattenstauchung.
Kurven: `druck_71_y.png`; Rohdaten und CSV je Lauf in `druck<a>_sigy<XXX>/`; Tabelle maschinenlesbar in `kennwerte_druck_71.csv`.

| Lauf | Job | E_10_40 | Rp0,2 (eps) | sig 0,5 % | sig 1,0 % | sig 1,25 % | sig 2,0 % | sig_end (eps_end) | quer/axial Ende |
|---|---|---|---|---|---|---|---|---|---|
| y / 75  | 55499944 | 3679 | 4,07 (0,31 %) | 4,34 | 4,70 | 4,83 | 5,11 | 5,26 (2,48 %) | 0,141 |
| y / 100 | 55499950 | 3892 | 5,26 (0,34 %) | 5,58 | 6,07 | 6,23 | 6,59 | 6,77 (2,50 %) | 0,135 |
| y / 180 | 55499947 | 3806 | 8,92 (0,43 %) | 9,18 | 10,20 | 10,49 | 11,09 | 11,38 (2,49 %) | 0,124 |
| x / 75  | 55498714 (Glied 1, Stopp 1,09 %) | 3997 | 4,52 (0,31 %) | 4,81 | 5,21 | – | – | 5,31 (1,09 %) | 0,123 |
| x / 100 | 55498720 + 55498721 (fertig 21.10. 18:02) | 3956 | 5,86 (0,35 %) | 6,18 | 6,72 | 6,89 | 7,27 | 7,46 (2,48 %) | 0,131 |
| x / 180 | 55498717 | 4027 | 9,88 (0,45 %) | 10,12 | 11,28 | 11,60 | 12,23 | 12,53 (2,48 %) | 0,123 |

Rp0,2-Vorschrift wie Versuchsauswertung; mit E0 statt E_10_40 -0,5 %, mit Versuchs-E 1760 +5 % (75) bis +11 % (180).
sigma bei genau 2,5 % liegt nicht vor (letzter Schritt 2,475-2,498 %); Steigung zuletzt 30-60 MPa -> Unterschied zu sig_end < 0,01 MPa.
Alle Kurven monoton steigend (ideal plastisches Grundmaterial, Verfestigung nur strukturell).

## Vergleich mit KUBC-Fliessflaeche (sig_y^perp, rho 0,1768) und Versuch

Dichte des Druckmodells 0,1891 (x) / 0,1888 (y) gegen KUBC 0,1768 -> Korrekturfaktor (rho_1D/rho_KUBC)^n = 1,12 (n 1,75) / 1,14 (n 2).
"korr." = 1D-Wert / Faktor, also auf KUBC-Dichte heruntergerechnet.

| Lauf | KUBC sig^perp | Rp0,2 / KUBC roh | korr. n 1,75 / n 2 | sig 1 % / KUBC roh | korr. n 1,75 / n 2 |
|---|---|---|---|---|---|
| y / 75  | 6,40 | 0,64 | 0,57 / 0,56 | 0,74 | 0,66 / 0,65 |
| y / 100 | 8,41 | 0,63 | 0,56 / 0,55 | 0,72 | 0,64 / 0,63 |
| y / 180 | 14,5 (Skalierung m 0,93) | 0,62 | 0,55 / 0,54 | 0,70 | 0,63 / 0,62 |
| x / 180 | 14,5 | 0,68 | 0,61 / 0,60 | 0,78 | 0,69 / 0,68 |

- E: 1D 3680-4030 MPa gegen KUBC E_perp 4440 -> roh 0,83-0,91, dichtekorrigiert (n 2) 0,73-0,79.
  E_10_40 haengt leicht von sig_y ab (3679/3892/3806 in y) -> im 10-40-%-Fenster sind schon lokale Plastizitaeten dabei, kein reiner E-Modul.
- **x/y bei sig_y 180:** Rp0,2 1,11, sig 1 % 1,11, sig_end 1,10, E 1,06 — x ist rund 10 % steifer/fester (KUBC-Flaeche: x/y 0,98-1,01).
  Dichte gleich (0,1891/0,1888) -> Effekt der freien Randzellen bzw. der Plattenlage, nicht der Dichte.
- **A01-FFT (Plateau 4,5 MPa bei sig_y 75):** y/75 liefert 4,70 (1 %) / 5,11 (2 %) / 5,26 (2,48 %) -> deutlich naeher an 4,5 als KUBC 6,40.
  Der Randbedingungs-Verdacht (KUBC-Schale ueberschaetzt um Faktor ~1,4-1,6) wird damit gestuetzt.
- **Versuch (Rp0,2 7,7 / sig_max 11,2 / Plateau 9,6, E 1760):** liegt zwischen sig_y 100 und 180; y/180 trifft sig_max (11,38 bei 2,5 %)
  und das Plateau-Niveau (10,2 bei 1 %) gut, Rp0,2 des Modells 8,9 etwas hoeher. Modell-E 3700-4000 ist 2,1-2,3 x Versuchs-E
  (bekannt: Versuchs-E aus der Maschinenkurve inkl. Setzungen). Achtung: Versuch hat 2,5 % nicht als Endpunkt, Plateau dort ggf. spaeter.

## Querspannungen (Pruefkriterium <= 0,05 NICHT erfuellt)
quer/axial (sig_xx bzw. sig_zz / sig_yy) liegt schon im elastischen Anfang bei 0,09-0,11 und steigt plastisch auf 0,10-0,14.
Ursache nach Verlauf: haftende Platten (u = eps.x auf dem ganzen Plattenband, Querdehnung an den Platten gesperrt). Bei freien Seitenflaechen
ist das Volumenmittel der Querspannung = Moment der Schubtraktionen an den Plattengrenzflaechen; ohne Haftung waere es ~0.
Konsequenz: der Versuch ist "1D mit haftenden Platten" (wie ein Versuch ohne Schmierung), nicht einachsig im strengen Sinn.
Der axiale Kennwert ist dadurch eher etwas ueberschaetzt (Querdruck ~ 10-14 % der Axialspannung in der Platten-Naehe).
Offener Punkt: Plattenmodell mit Gleitlagerung (nur u_a vorgegeben) als Gegenprobe — nur nach Entscheidung des Nutzers.

Interpretation und Empfehlungen: `INTERPRETATION_Diskrepanz_druck_71_20261021.md`; Ueberlagerung mit dem Versuch: `druck_71_vs_versuch.png`.

## Nachtrag 21.10.2026 15:45 — x/75, x/100 (Glied 1) und Verfestigungslauf

- x/75 und x/100: Glied 1 per Walltime gestoppt (Exit 3) bei 1,09 % bzw. 2,26 %; Glied 2 laeuft, **kein Restart-Sprung**
  (Ende Glied 1 = Start Glied 2 auf 3 Stellen). Historie aus `glied1_restart_meta_elastoplastic_std_x.json` (`averaged_history`).
  **x/y bei gleichem sigma_y: 1,11** (Rp0,2 und sig 1 %, fuer 75, 100 und 180 gleich).
- **y / sigma_y 100 + H 2000 (55505395, fertig in 5:17 h):**

| Stauchung | ideal sigma_y 100 | sigma_y 100 + H 2000 | Versuch JM-25-71 (MTS korr.) |
|---|---|---|---|
| 0,25 % | 4,99 | 5,50 | 3,79 |
| 0,5 % | 5,58 | 6,82 | 6,32 |
| 1,0 % | 6,07 | 8,49 | 8,70 |
| 1,5 % | 6,37 | 9,80 | 9,90 |
| 2,0 % | 6,59 | 10,97 | 10,61 |
| 2,48 % | 6,77 | 12,02 | 11,02 (Max. 11,2 bei 3,1 %) |

  Rp0,2 mit E0 3944: 6,16 MPa; mit Versuchs-E 1760: 7,26 (Versuch 7,7). `E_10_40` = 2551 ist hier ein Artefakt
  (40 % von sig_max = 4,8 MPa liegt schon im Fliessbereich) -> fuer verfestigende Laeufe E0 bzw. das Fenster des idealen Laufs nehmen.
  Zwischen 0,5 und 2 % liegt der Lauf auf ±5 % am Versuch; danach steigt er weiter (Steigung 219 MPa, lineare Verfestigung ohne
  Saettigung), der Versuch flacht zum Maximum ab. Vorbehalte: y-Richtung (x waere ~11 % hoeher), Modelldichte 0,189 gegen Versuch ~0,20
  (+~10 %), Anfangsbereich durch E-Unterschied verschoben.
