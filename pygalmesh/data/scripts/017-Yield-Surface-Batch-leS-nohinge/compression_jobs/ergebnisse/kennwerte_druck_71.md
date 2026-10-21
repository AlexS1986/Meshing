# Kennwerte 1D-Druckversuch JM-25-71 (Studie 017, r4, freie Seitenflaechen, haftende Platten)

Stand 21.10.2026 ~09:30. Nennspannung = Volumenmittel sigma_aa ueber das reduzierte Volumen (`_averages.txt` bzw. `yield_averages_std_x.json`),
ausgewertet mit `evaluate_compression_run.py` (E = Sekante 10-40 % von sigma_max). Werte in MPa, Dehnung = Plattenstauchung.
Kurven: `druck_71_y.png`; Rohdaten und CSV je Lauf in `druck<a>_sigy<XXX>/`; Tabelle maschinenlesbar in `kennwerte_druck_71.csv`.

| Lauf | Job | E_10_40 | Rp0,2 (eps) | sig 0,5 % | sig 1,0 % | sig 1,25 % | sig 2,0 % | sig_end (eps_end) | quer/axial Ende |
|---|---|---|---|---|---|---|---|---|---|
| y / 75  | 55499944 | 3679 | 4,07 (0,31 %) | 4,34 | 4,70 | 4,83 | 5,11 | 5,26 (2,48 %) | 0,141 |
| y / 100 | 55499950 | 3892 | 5,26 (0,34 %) | 5,58 | 6,07 | 6,23 | 6,59 | 6,77 (2,50 %) | 0,135 |
| y / 180 | 55499947 | 3806 | 8,92 (0,43 %) | 9,18 | 10,20 | 10,49 | 11,09 | 11,38 (2,49 %) | 0,124 |
| x / 75  | 55498714 | laeuft (0,82 % um 09:00), Historie nach Walltime-Stopp ~15:25 | | | | | | | |
| x / 100 | 55498720 | laeuft (1,64 % um 09:00) | | | | | | | |
| x / 180 | 55498717 | 4027 | 9,88 (0,45 %) | 10,12 | 11,28 | 11,60 | 12,23 | 12,53 (2,48 %) | 0,123 |

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
