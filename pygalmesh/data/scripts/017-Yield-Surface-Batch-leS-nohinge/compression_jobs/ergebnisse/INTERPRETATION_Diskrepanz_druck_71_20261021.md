# Interpretation: KUBC ↔ 1D-FEM ↔ A01-FFT ↔ Versuch (JM-25-71)

Stand 21.10.2026, ~10:30. Grundlage: 1D-Druckläufe y/75, y/100, y/180, x/180 (fertig). x/75 und x/100 laufen noch
(Ergebnis ab 21.10. ~15:40). Zahlen: `kennwerte_druck_71.md/.csv`; Bild: `druck_71_vs_versuch.png` (Skript `plot_druck_vs_versuch.py`).

## 1. Randbedingung des 1D-Modells (Klarstellung)

- Es gibt **nur zwei Plattenbänder, senkrecht zur Lastachse** (y-Lauf: y_min/y_max, je 9 Voxel = 0,6 mm Al;
  x-Lauf: x_min/x_max, je 6 Voxel = 0,4 mm). Die vier Seitenflächen parallel zur Last haben Schalendicke 0, sind
  frei (kein Dirichlet) und gehören zum ausgewerteten Volumen. **Keine Platten parallel zur Last** — geprüft im Log
  (`dirichlet_faces: ['y_min', 'y_max']`) und in der Config (`boundary_seal.thicknesses` x/z = 0).
- Dirichlet auf allen Knoten der Plattenbänder: u = ε·x mit ε = diag(0, −0,25 s, 0), also u_y = ε_yy·y und
  **u_x = u_z = 0**. Die Platten sind in Querrichtung starr und mit dem Schaum verklebt (haftend, „unendliche
  Reibung"). Die „Behinderung der Querdehnung" meint genau das: An den beiden Plattengrenzflächen darf sich der
  Schaum nicht quer ausdehnen (Tonneneffekt), dazwischen frei.
- Die Nennspannung ist das Volumenmittel über das Gebiet zwischen den Platten, normiert auf das Quadervolumen
  einschließlich Poren (`vol = reduced_volume_box`), also σ̄_aa = F/A. Für die Querspannung gilt
  ∫σ_xx dV = ∫ x·t_x dA über den Rand; Seitenflächen und Porenoberflächen sind lastfrei, es bleiben nur die
  Schubtraktionen an den Plattengrenzflächen. **σ̄_xx ≠ 0 kommt also ausschließlich aus der Haftung an den Platten.**
  Gemessen: quer/axial 0,09–0,11 elastisch, 0,10–0,14 am Ende. Das Prüfkriterium ≤ 0,05 aus dem Handoff ist mit
  haftenden Platten nicht erreichbar. Das ist kein Fehler im Lauf.
- Im Versuch liegen Stahlplatten mit Reibung an (Schmierung unbekannt → bei Sven nachfragen). Der Versuch liegt
  zwischen „haftend" und „gleitend"; das Modell ist der Grenzfall „haftend". Der Querdruck wirkt nur in den
  plattennahen Zonen. Der Einfluss auf die Axialspannung ist vermutlich klein (einige %), aber noch nicht beziffert.
  Beziffern ließe er sich nur mit einem Lauf mit gleitenden Platten (Codeänderung: Dirichlet nur auf u_axial).

## 2. Wie Rp0,2 gerechnet ist und ob es zum Versuch passt

| | 1D-FEM (`evaluate_compression_run.py`) | Versuch (`auswertung_druckversuche.py`, Publikationsordner) |
|---|---|---|
| Dehnung | Plattenweg / Probenlänge | DIC, virtuelles Extensometer ≈ 17 mm, 1,5–2 mm Abstand zu den Platten |
| E | Regression im Bereich 10–40 % von σ_max | gleich (10–40 % σ_max, DIC-Dehnung) |
| σ_max | Endwert bei 2,5 % (Kurve steigt monoton) | echtes Maximum 11,2 MPa bei 3,1 % |
| Rp0,2 | Schnitt mit der um 0,2 % verschobenen E-Geraden | gleich, mit Achsenabschnitt; σ als Median über 5 Punkte |

Die Vorschrift ist also dieselbe. Unterschiede gibt es bei der Dehnungsmessung (Platten gegen Mitte) und vor allem
bei E: Modell 3680–4030 MPa, Versuch 1760 MPa.
**Rp0,2 ist robust gegen diese E-Lücke:**
- mit der Anfangstangente E₀ (3944 / 4165 MPa) ändert sich Rp0,2 um −0,5 %;
- mit dem Versuchs-E 1760 MPa steigt es um +5 % (σ_y 75) bis +11 % (σ_y 180).

E_10_40 liegt 3–7 % unter E₀, weil im 10–40-%-Fenster lokal schon Stege fließen.

## 3. Zahlen nebeneinander (MPa)

| | σ_y 75 | σ_y 100 | σ_y 180 |
|---|---|---|---|
| KUBC σ̄_y^⊥ (Fließfläche, ρ 0,177) | 6,40 | 8,41 | 14,5 (Skalierung) |
| 1D-FEM Rp0,2 y / x | 4,07 / – | 5,26 / – | 8,92 / 9,88 |
| 1D-FEM σ(1 %) y / x | 4,70 / – | 6,07 / – | 10,20 / 11,28 |
| 1D-FEM σ(2,5 %) y / x | 5,26 / – | 6,77 / – | 11,38 / 12,53 |
| A01-FFT Plateau | 4,5 | – | ≈ Versuch (Julian) |
| Versuch JM-25-71 | Rp0,2 7,7 · σ_max 11,2 (3,1 %) · Plateau 20–30 % 9,6 · E_DIC 1760 | | |

Skalierung im 1D-Modell: σ̄ ∝ σ_y^m mit m = 0,88–0,90 (Rp0,2, σ(1 %), σ_end; 75–100–180 konsistent).
KUBC: m = 0,93.

## 4. Interpretation

**(a) KUBC → 1D: Randbedingungseffekt, Faktor ≈ 1,4–1,8.**
- Verhältnis 1D/KUBC:
  - Rp0,2: 0,62–0,68 roh, 0,54–0,61 nach Dichtekorrektur auf 0,177;
  - σ(1 %): 0,70–0,78 roh, 0,62–0,69 korrigiert.
- Mechanismus: KUBC auf der geschlossenen Schale zwingt jede angeschnittene Randzelle in den affinen
  Verschiebungszustand. Das ist eine obere Schranke. Im Versuch sind die Zellen an den vier freien Seitenflächen
  angeschnitten und tragen kaum.
- Das ist der bekannte Größeneffekt duktiler Schäume bei wenigen Zellen über die Probenbreite (Onck, Andrews &
  Gibson 2001, „Size effects in ductile cellular solids", Teil I/II, IJMS; Zitat vor Verwendung prüfen).
- x/y differiert im 1D-Modell um 10 % (KUBC isotrop ≤ 2 %). Das ist die Randzellen-Streuung einer Einzelprobe;
  im Versuch ist ebenfalls Probenstreuung dieser Größe zu erwarten (vgl. 83 > 71).

**(b) 1D-FEM ↔ A01-FFT: konsistent.**
- Bei σ_y = 75 liefert das 1D-Modell 4,7 (1 %) bis 5,3 MPa (2,5 %), die FFT ein Plateau von 4,5 MPa: Abstand 5–15 %.
- Die Diskrepanz KUBC ↔ FFT (6,4 gegen 4,5) ist damit im Wesentlichen die Randbedingung, nicht Löser,
  Auflösung oder Materialgesetz.
- Für den Rest kommen Plattenhaftung, Netzauflösung (r4 liegt bei JM-25-77 eher unter r2) und die
  Kurvenpunktwahl in Frage. Dichte erklärt ihn nicht: die FFT nutzt das dichtere Voxelbild und läge damit eher höher.

**(c) Modelle ↔ Versuch: welches σ_y braucht ein ideal plastisches Modell?** (Rückrechnung über die 1D-Kurven, log-log interpoliert)

| Anpassung an | Lastrichtung y | Lastrichtung x |
|---|---|---|
| Rp0,2 = 7,7 | 153 MPa | 136 MPa |
| σ(1 %) ↔ Plateau-Niveau 9,6 | 168 MPa | 150 MPa |
| σ(2,5 %) ↔ σ_max 11,2 | 177 MPa | 159 MPa |

- Die Dichte der Versuchsprobe ist nicht gewogen (Voxel 0,194–0,202 gegen Modell 0,189). Ist sie 3–7 % höher,
  sinken die Werte um 5–13 % auf ≈ 125–165 MPa.
- Mit dem KUBC-Modell kam dagegen 92 MPa heraus (Nachtrag 23 im decisions_log). Dieser Wert war durch die
  Randbedingung zu niedrig angesetzt.
- Die FFT trifft den Versuch mit 180 MPa, das 1D-FEM mit ≈ 150–180 MPa: beide Modelle sind konsistent.

**(d) Ist σ_y = 75 oder 100 MPa vernünftig? Liegt der Rest an fehlender Verfestigung? — Ja, so lässt es sich lesen.**
- Als **Anfangsfließgrenze des Stegmaterials** ist 100 MPa plausibel: gussähnlicher Zustand nach dem Schäumen
  bei 750 °C mit Luftabkühlung, typisch 90–140 MPa (Nachtrag 23). 75 MPa liegt am unteren Rand.
- Im ideal plastischen Modell ist σ_y aber zugleich die Endfließspannung. AlSi10Mg im Gusszustand verfestigt deutlich
  (Rm erheblich über Rp0,2 bei wenigen % Bruchdehnung; Werte aus Literatur/Datenblatt belegen). Lokal erreichen die
  Stege beim makroskopischen Rp0,2 bereits mehrere % plastische Dehnung, ihre Fließspannung liegt dort also über Rp0,2.
  Das σ_y,eff ≈ 140–180 MPa, das ein ideal plastisches Modell zum Treffen braucht, widerspricht σ_y,0 ≈ 100 MPa
  nicht. Es ist die über die relevanten Stegdehnungen gemittelte Fließspannung.
- **Die Kurvenform stützt das** (`druck_71_vs_versuch.png`):
  - Der Versuch hat einen sehr runden Übergang (≈ 6,5 MPa bei 0,5 %, Maximum erst bei 3,1 %).
  - σ_y 180 hat ein scharfes Knie (10 MPa bei 1 %) und liegt bis ≈ 2 % über dem Versuch.
  - σ_y 100 folgt dem Anfang besser und bleibt dann darunter.
  - Genau dieses Bild ergibt sich mit „Fließbeginn ≈ 100 MPa, danach Verfestigung".
- Strukturelle Verfestigung Rp0,2 → σ(2,5 %): 1D-Modell +27–29 %, KUBC nur ≈ +5 %, Versuch Rp0,2 → σ_max +45 %.
  Gut die Hälfte der scheinbaren Verfestigung im Versuch erklärt schon die freie Randbedingung (allmähliche
  Ausbreitung der Plastizität von den schwachen Randzonen), den Rest die Materialverfestigung.
  (Die Kennwerte sind nicht exakt gleich definiert: σ_max des Versuchs bei 3,1 % gegen Modell-Endwert bei 2,5 %.)

**(e) Was das Modell grundsätzlich nicht abbildet** (im Paper als Grenzen nennen):
- **E (Faktor 2,2):**
  - Ursache ist die Messgröße: Belastungsmodul bei monotoner Erstbelastung, wenige DIC-Punkte, Einzellinie.
  - Das Vorgängerpaper mit Einebnungsläufen und 6 Extensometern passte.
  - Die freie Randbedingung senkt E nur um ≈ 10–25 % (4440 → 3680–4030 roh).
- **Maximum und Entfestigung auf das Plateau 9,6** (Stegknicken, Kollapsbänder, Selbstkontakt): bräuchte große
  Dehnungen und Kontakt; das Kleindehnungsmodell sättigt nur.
- **Zug-Druck-Asymmetrie:** Das Modell ist zentralsymmetrisch (von Mises, ideal plastisch, kleine Dehnungen).
  Ein 1D-Zuglauf ergäbe dieselbe Kurve mit umgekehrtem Vorzeichen und muss nicht gerechnet werden.
- 83 im Versuch fester als 71 trotz gleicher Modelldichte.

## 5. Darstellbarkeit im Paper — Vorschlag für die Argumentationskette

Ja, die Abweichungen sind darstellbar und erklärbar, wenn die Kette explizit gemacht wird:

1. **Fließfläche (KUBC)** = homogenisierte Materialantwort des Volumens (obere Schranke bezüglich der Randbedingung),
   σ̄ ∝ σ_y^0,93, Form unabhängig von σ_y.
2. **Probenversuch = Strukturantwort mit freien Seitenflächen.** Mit dem 1D-Modell desselben CT-Volumens
   numerisch belegt: Faktor ≈ 0,6–0,7 (Rp0,2) bzw. 0,7–0,8 (σ bei 1 %) gegenüber KUBC, dichtekorrigiert 0,55–0,69.
3. **Unabhängige Bestätigung durch A01-FFT** (gleiches σ_y, ≈ ±10 %).
4. **Versuch:** Ein ideal plastisches Modell braucht σ_y,eff ≈ 140–180 MPa (je nach Kennwert, Richtung und Dichte).
   Physikalisch gelesen: σ_y,0 ≈ 100 MPa plus Materialverfestigung. Ohne Mikrozugversuche (C02, nicht vor der
   Deadline) ist σ_y als **invers identifizierter, effektiver Parameter** zu benennen.
5. Grenzen: E als Belastungsmodul, kein Kollaps/Kontakt, Plattenhaftung im Modell, Dichte nicht gewogen,
   Einzelprobe (x/y ± 10 %).

Formulierungsregeln: „1D-Druckmodell mit haftenden Platten und freien Seitenflächen"; „σ_y,eff"; Dichte jedes
Modells angeben (KUBC 0,177, 1D 0,189, Voxel 0,194–0,202); Dehnung = technische Stauchung (nicht `strain_scale`).

## 6. Empfehlung zu Neurechnungen

- **KUBC-Fließfläche mit höherem σ_y neu rechnen: nicht nötig.**
  - Die Form ist invariant (Abweichungsmuster 75 gegen 100 korrelieren mit r = 0,999).
  - Die Skalierung ist glatt: KUBC m = 0,93, 1D m = 0,88–0,90, ohne Knick bis 180.
  - Fehler der Extrapolation auf 180 MPa über m: ≈ 2,4^(0,93−0,90) ≈ 3 %.
  - Im Paper normiert darstellen (σ̄ / σ_y^m) oder mit σ_y,eff skalieren.
  - Optional als billige Kontrolle: 2–3 KUBC-Punkte in einachsigen Richtungen bei 180 MPa statt einer vollen Fläche.
- **Sinnvoller (Entscheidung Nutzer):**
  1. **1D-Lauf mit Verfestigung** (Config `hard` = lineare isotrope Verfestigung H in σ = σ_y + H·α), z. B.
     σ_y 100 MPa mit H aus Literaturwerten für AlSi10Mg im Gusszustand (Größenordnung 1–3 GPa, belegen).
     Testet direkt die Hypothese „σ_y,0 100 + Verfestigung erklärt runden Übergang und Maximum".
     Kosten: ein Glied, ≈ 7–10 h auf 32 Kernen je Richtung, Netz y liegt vor.
  2. **1D-Lauf mit gleitenden Platten** (nur u_axial vorgeben), um den Haftungseinfluss zu beziffern. Kleine
     Codeänderung in `get_bcs`, nur nach Freigabe.
- Keine weiteren Netzvarianten hier, dafür läuft 018.
