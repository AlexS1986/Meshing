# Abschlussbericht 1D-Druckversuche JM-25-71 (Studie 017), 23.10.2026

Grundlage: `kennwerte_druck_71.md/.csv`, `INTERPRETATION_Diskrepanz_druck_71_20261021.md`, Kurven `druck_71_vs_versuch.png`.
Protokoll: `../../CLAUDE_PROJECT_NOTES.md` (20.–23.10.2026).

## Modell

- CT-Volumen JM-25-71, r4 (66,95 µm), P1, Kleindehnung, von Mises, E 70 GPa, ν 0,35.
- Al-Plattenbänder nur senkrecht zur Lastachse, **haftend** (u = ε·x auf dem Plattenband, Querverschiebung 0), Seitenflächen frei.
- Verschiebungsgesteuert bis 2,5 % Stauchung.
- Nennspannung = Volumenmittel σ̄_aa (= F/A).
- Netze:
  - x: 3,90 Mio. Tets, ρ_rel 0,1891, A 342,68 mm²;
  - y: 3,99 Mio. Tets, ρ_rel 0,1888, A 340,34 mm².
  - Zum Vergleich: KUBC-Produktionsnetz ρ_rel 0,1768.

## Läufe (alle fertig, alle Exit 0 bzw. kontrollierter Walltime-Stopp mit sprungfreiem Restart)

| Lauf | Jobs | Laufzeit | Stauchung |
|---|---|---|---|
| y / σ_y 75, 100, 180 | 55499944 / 950 / 947 | 9,7 / 7,4 / 6,8 h (je 1 Glied) | 2,48–2,50 % |
| x / σ_y 75 | 55498714–716 | 23,5 + 23,5 + 5,2 h | 2,49 % |
| x / σ_y 100 | 55498720–721 | 23,5 + 2,8 h | 2,48 % |
| x / σ_y 180 | 55498717 | 10,2 h | 2,48 % |
| y / σ_y 100 + H 2000 | 55505395 | 5,3 h | 2,49 % |
| x / σ_y 100 + H 2000 | 55528156 | 4,8 h | 2,49 % |

**Kernstunden** (sacct CPUTimeRAW, p0023647):

| Posten | Kernstunden |
|---|---|
| ideal plastisch, x | 2843 |
| ideal plastisch, y | 764 |
| Verfestigung | 323 |
| Netzvorbereitung | 5 |
| **gesamt** | **≈ 3940** |

x/75 und x/100 liefen mit der alten Template-Kopie deutlich langsamer (≈ 8–9 min je Schritt gegen ≈ 4–5 min).

## Kennwerte (MPa; E = Sekante 10–40 % σ_max, Rp0,2 mit diesem E; σ_end bei 2,48–2,50 %)

| Lauf | E | Rp0,2 | σ(0,5 %) | σ(1 %) | σ(2 %) | σ_end | quer/axial |
|---|---|---|---|---|---|---|---|
| y / 75 | 3679 | 4,07 | 4,34 | 4,70 | 5,11 | 5,26 | 0,14 |
| y / 100 | 3892 | 5,26 | 5,58 | 6,07 | 6,59 | 6,77 | 0,13 |
| y / 180 | 3806 | 8,92 | 9,18 | 10,20 | 11,09 | 11,38 | 0,12 |
| x / 75 | 3997 | 4,52 | 4,81 | 5,21 | 5,65 | 5,81 | 0,13 |
| x / 100 | 3956 | 5,86 | 6,18 | 6,72 | 7,27 | 7,46 | 0,13 |
| x / 180 | 4027 | 9,88 | 10,12 | 11,28 | 12,23 | 12,53 | 0,12 |
| y / 100 + H 2000 | 3944 (E₀) | 6,16 (E₀) / 7,26 (E 1760) | 6,82 | 8,49 | 10,97 | 12,02 | 0,15 |
| x / 100 + H 2000 | 4165 (E₀) | 6,63 (E₀) / 7,85 (E 1760) | 7,29 | 8,96 | 11,46 | 12,55 | 0,14 |
| **Versuch JM-25-71** | 1760 (DIC) | 7,7 | 6,32 | 8,70 | 10,61 | σ_max 11,2 bei 3,1 % | – |

Bei den Läufen mit Verfestigung ist `E_10_40` unbrauchbar, weil das Fenster in den Fließbereich reicht; deshalb steht dort E₀.
Rp0,2 ist robust gegen E: mit E₀ statt E_10_40 ändert es sich um −0,5 %, mit dem Versuchs-E 1760 um +5 bis +11 %.

## Verhältnisse

**1D / KUBC (σ̄_y^⊥ 6,40 / 8,41 / 14,5).** „korrigiert" = 1D-Wert auf KUBC-Dichte 0,1768 umgerechnet (ρ^1,75; Faktor 1,12).

| | σ_y 75 | σ_y 100 | σ_y 180 |
|---|---|---|---|
| Rp0,2 y: roh / korrigiert | 0,64 / 0,57 | 0,63 / 0,56 | 0,62 / 0,55 |
| Rp0,2 x: roh / korrigiert | 0,71 / 0,63 | 0,70 / 0,62 | 0,68 / 0,61 |
| σ(1 %) y: roh / korrigiert | 0,73 / 0,65 | 0,72 / 0,64 | 0,70 / 0,63 |
| σ(1 %) x: roh / korrigiert | 0,81 / 0,72 | 0,80 / 0,71 | 0,78 / 0,69 |

- Ein Teil des Abstands kommt vom Fließkriterium: KUBC bei α_avg 2·10⁻³ liegt beim Rp0,2-Analogon ≈ 5 % tiefer.
- **x/y** (gleiche Dichte): 1,10–1,11 ideal plastisch, bei allen σ_y gleich; mit H 2000 nur 1,04–1,07. Die KUBC-Fläche war isotrop (0,98–1,01).
- **Skalierung mit σ_y:** σ̄_1D ∝ σ_y^m mit m 0,88–0,90 (KUBC 0,93).
- **A01-FFT (Julian, GeoDict, glatte Platten, ρ 0,214):** Rp0,2 bei σ_y 75 = 5,05. Das 1D-FEM, auf ρ 0,214 hochgerechnet, liefert 5,07, also **Fließbeginn identisch**.
  - FFT / KUBC auf gleiche Dichte: 0,565, FEM 0,56. Der Randbedingungsfaktor ist damit von zwei Lösern bestätigt.
  - Nach dem Fließbeginn steigt das FEM weiter (+21 % bis 1,5 %), die FFT nicht (+4 %). Ursache sind die haftenden Platten im FEM.

## Kernaussagen

1. **KUBC → freie Probe: Faktor ≈ 0,55–0,63 auf Rp0,2 bei gleicher Dichte** (roh 0,62–0,71). Die geschlossene KUBC-Schale ist
   eine obere Schranke; die angeschnittenen Randzellen an freien Seitenflächen tragen kaum.
2. **FEM und FFT stimmen im Fließbeginn überein.** Die frühere Lücke von 6,4 gegen 4,5 MPa war Randbedingung plus niedrige FFT-Auflösung.
3. **Versuch 71:**
   - Ein ideal plastisches Modell bräuchte σ_y,eff ≈ 150–170 MPa (Konsens mit A01).
   - Physikalisch passt besser **σ_y,0 ≈ 100 MPa + lineare Verfestigung H ≈ 2000 MPa**. Das trifft x und y zwischen 1 und 2 % auf +3 bis +8 %, und Rp0,2 mit Versuchs-E auf −6 % bis +2 %.
   - Ab ≈ 2 % ist das Modell zu steil: keine Sättigung, kein Knicken.
4. **Grenzen:**
   - E im Modell 2,1–2,4× Versuch. Das ist eine Frage der Messung (Belastungsmodul, monotone Erstbelastung).
   - Kein Maximum und keine Entfestigung (Kleindehnung, kein Kontakt).
   - Plattenbedingung haftend. Im Versuch ist die Gleitung eher behindert (Arbeitsannahme), quantitativ aber offen.
   - Dichte des Modells 0,189 gegen Probe ≈ 0,20; nicht gewogen.

## Offene Punkte

- **A01 (Julian):**
  - FFT mit haftenden Stirnflächen, um den Platteneffekt zu beziffern;
  - FFT mit σ_y 100 + H 2000 (Parameter übergeben).
- **Sven:** Schmierung der Platten; DIC-Rohdaten der Querdehnung entlang der Probenhöhe. Die Videos lösen die Tonnenform nicht auf (`DIC_Tonnenform_Check_20261022.md`).
- **Sättigende Verfestigung (Voce):** erst nach den A01-Ergebnissen; dafür ist eine Codeänderung im Materialmodell nötig.
- **Für eine Anfangsfließfläche des Schaums (A02-Ziel):** siehe nächster Abschnitt.

## Was für die Anfangsfließfläche noch fehlt (Empfehlung)

Vorhanden:
- **Form:** KUBC-Flächen für 4 Proben × σ_y 75/100 (96 Richtungen, Materialgesetz TI-Quadrik, ±3–4 %).
- **Niveau:** der Randbedingungsfaktor für einachsigen Druck ⊥ z an einer Probe.
- **σ_y,0 ≈ 100 MPa:** an einer Probe gegen den Versuch geprüft.

Noch nicht belegt sind zwei Annahmen, auf denen eine „Fließfläche, die den Schaum abbildet" beruhen würde:

1. **Der Randbedingungsfaktor ist richtungsunabhängig,** sodass die KUBC-Fläche als Ganzes skaliert werden darf. Gemessen ist er nur einachsig ⊥ z.
   Vorschlag:
   - 1D-Druck in **z** an JM-25-71 (KUBC σ_z/σ_⊥ 0,86; ein Prep-Job und ein Lauf σ_y 100, ≈ 1 Tag);
   - optional ein **biaxialer** Fall mit freiem drittem Flächenpaar. Dafür ist eine kleine Erweiterung von `setup_compression_jobs.py` nötig.

   Ist der Faktor in z gleich, ist „KUBC-Form × Faktor" gut begründet; sonst ist der Faktor selbst richtungsabhängig.
2. **Die Parameter gelten probenübergreifend.**
   Vorschlag: 1D-Druck für **JM-25-83 und JM-25-88** mit σ_y 100 + H 2000. Für beide liegen Versuche vor: σ_max 15,7 / 15,5, Rp0,2 8,7 / 10,2 MPa.
   Aufwand: je ein Prep-Job und ein Lauf, ≈ 1 Tag, ≈ 1–1,5 k Kernstunden.

   Trifft derselbe Parametersatz alle drei Proben, ist das der stärkste Beleg für das Paper.

Außerdem zu entscheiden (A02/Partner): Was heißt „Fließfläche des Schaums"?
- (a) **Materialeigenschaft im Inneren eines großen Bauteils**, ohne freie Ränder. Sie liegt zwischen KUBC (oberer Wert) und der 1D-Probe.
- (b) **Probenantwort**, mit Randzelleneffekt; vergleichbar mit dem Versuch.

Für (a) wäre eine untere Schranke (Spannungs-RB bzw. gemischte RB auf wenigen Richtungen) nötig, für (b) genügt die skalierte KUBC-Fläche plus die Prüfungen 1 und 2.
