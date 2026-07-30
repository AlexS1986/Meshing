# WAAM 316L & 17-4PH — EBSD-basierte 3D-Mikrostruktur mit Neper → FEniCSx

> **Aktueller Modellstand (2026-07):** 316L ist **orthotrop** (nicht kolumnar).
> Alle EBSD-Schliffe sind Querschnitte **senkrecht zur Probenachse**, daher
> `k_build=3.41` (aus dem H-Schliff, Aufbau/Wandnormale), `k_inplane=3.18` (aus
> dem V-Schliff, Schweiß/Wandnormale), Kornform ≈ 3.4:3.2:1, Textur: Aufbau =
> V-Schliff-Normale → z. Maßgeblich sind `materials.py`, `documentation.txt` und
> `AGENTS.md`; einige Detailtabellen unten sind noch auf einen früheren Stand.

Pipeline zur Erzeugung statistisch äquivalenter 3D-Mikrostrukturen aus den
EBSD-Schliffen (`data_c04/`) und Vernetzung für FEM (dolfinx / XDMF), für **zwei
Stähle** (316L, 17-4PH) sowie einen **kombinierten Zugstab** (V-Orientierung) mit
316L-, Übergangs- und 17-4PH-Bereich übereinander.

## Ausführen (komplett, von vorne)

Alle Schritte laufen **im Neper/Gmsh-Container**. Vom Host aus:

```bash
# im Ordner Neper/ (Host):
docker compose up -d --build
docker compose exec ubuntu_custom bash -c \
  "CLEAN=1 bash /data/04_anisotropy_waam/neper_pipeline/run_pipeline.sh"
```

`CLEAN=1` löscht zuerst **alle** zuvor generierten Dateien (via
`clean_generated.sh`, behält nur die Quellskripte), dann baut `run_pipeline.sh`
die komplette Netz-Suite für beide Stähle:

1. **Homogenisierungs-RVE** je Stahl (`09_homogenization_rve.sh`, n=300, rcl=0.5)
   → `waam_<MAT>_n300.xdmf/.h5` + `grain_ori_<MAT>.txt`
2. **Gerichtete Zugstäbe** V/H/45° je Stahl (`07_tensile_specimens.py`)
   → `spec_<MAT>_V/H/45deg.xdmf/.h5` + `grain_ori_<MAT>_<orient>.txt`
3. **Kombinierter V-Stab** 316L/Übergang/17-4PH (`08_combined_specimen.py`)
   → `spec_combined_V.xdmf/.h5` + `spec_combined_V_grain_ori.txt`

Steuerung über Umgebungsvariablen:

```bash
MATERIALS="316L 17-4PH"   # Stähle (Default beide)
N=300  RCL=0.5            # Kornzahl / Netzfeinheit des Homogenisierungs-RVE
SPECIMENS=0              # gerichtete Stäbe (Schritt 2) überspringen
COMBINED=0               # kombinierten Stab (Schritt 3) überspringen
FAST=1                   # schnelle Voronoi-Tessellationen (Sekunden, nur zum Testen)
CLEAN=1                  # vorher alles Generierte entfernen
```

> **Erst testen:** `FAST=1 CLEAN=1 bash run_pipeline.sh` läuft in Minuten (Voronoi,
> ohne Größenoptimierung) und prüft, dass die ganze Kette durchläuft. Danach
> ohne `FAST` für die echten, optimierten Netze.

**Nur aufräumen** (ohne Neulauf): `bash clean_generated.sh` (bzw. `--dry` zum
Anzeigen). Die Rohdaten in `../data_c04` werden nie angefasst.

**Nur die einfachen n=200-RVEs + Kombistab** (schneller, ohne Homogenisierungs-
Auflösung/Stäbe): weiterhin `bash run_all.sh` (`SPECIMENS=1` für die Stäbe).

### Danach: FEM im dolfinx-Container

Die Steifigkeits-Homogenisierung und der einaxiale Zugversuch liegen in
`dolfinx_alex/shared/scripts/069-waam-polycrystal-anisotropy` (eigene README).
Kurz:

```bash
# Host: Netze ins dolfinx-Projekt kopieren
cd .../dolfinx_alex/shared/scripts/069-waam-polycrystal-anisotropy
python3 prepare_inputs.py --rve 316L 17-4PH --n 300
python3 prepare_inputs.py --specimens 316L 17-4PH
# dolfinx-Container:
python3 homogenize_rve.py  --mesh inputs/waam_316L_n300.xdmf --ori inputs/grain_ori_316L.txt --tag 316L
python3 uniaxial_tension.py --mesh inputs/spec_316L_V.xdmf    --ori inputs/grain_ori_316L_V.txt --tag 316L_V
```

`06_fenicsx_example.py` zeigt zusätzlich das reine Einlesen eines RVE in dolfinx
inkl. **rotierter, phasenabhängiger Steifigkeitstensoren** pro Zelle.

Netz-Cell-Tag `grain` = Korn-ID; `grain_ori_<MAT>.txt` bildet
`Korn-ID → φ1 Φ φ2 Kristallsystem` (Bunge, Grad).

## Zwei Stähle — Datenaufbereitung

Die Rohdaten der beiden Stähle unterscheiden sich; `materials.py` kapselt das:

| | 316L | 17-4PH | Übergang (trans) |
|---|---|---|---|
| Dateien | `Grain_Info_WAAM316L_*` | `WAAM_17-4PH_*` | `WAAM_N=1_A12D_Uebergangsbereich` |
| Zeilenenden | Unix | **CRLF** (wird abgefangen) | CRLF |
| Ablage | `data_c04/` | `data_c04/` | Unterordner `Übergangsbereich/` (per Glob gefunden) |
| Phasen | nur FCC (Austenit) | **alle Phasen gepoolt** (BCC-Martensit ~96 % Fläche, + Rest-Austenit FCC) | FCC + BCC gepoolt |
| Rauschfilter `MIN_POINTS` | 10 | **50** | 10 |
| Größenmaß | Breite 2·Nebenachse | **Äquivalenzdurchmesser** (Sp. 33) | Breite |
| Morphologie | **kolumnar** (k) | **equiaxed** (k=1) | kolumnar |
| Schliffe für Fit | V + 45° | V + 45° | nur eine Map (als V genutzt) |

Pro Korn wird das **Kristallsystem** (fcc/bcc) mitgeführt (`n<N>_<MAT>.meta`,
Spalte `crystal` in `grain_ori_<MAT>.txt`), damit die dolfinx-Elastizität je Korn
den passenden Steifigkeitstensor (FCC-Austenit vs. BCC-Martensit) wählen kann.

> **17-4PH-Modellierung (datenbasiert):** Die BCC-Martensitkörner sind zwar
> einzeln elongiert (k≈4), aber richtungslos (Achsenkonzentration R≈0.09 gegen
> 0.73 bei 316L) — ein globaler kolumnarer Stretch würde eine morphologische
> Anisotropie *erfinden*, die die Daten nicht zeigen. Daher wird 17-4PH
> **equiaxed** (k=1) modelliert; die elastische Anisotropie stammt aus der
> **kristallographischen Textur** (mittlere resultierende Länge der ⟨001⟩-Achsen
> ≈0.45, sogar etwas stärker als 316L mit 0.39) und wird über das
> Orientierungs-Sampling erfasst. Größe: robuster Äquivalenzdurchmesser +
> stärkerer Rauschfilter (`MIN_POINTS=25`) statt der rausch-getriebenen
> 2·Nebenachse. Der Horizontal-Schliff (abweichende Phasen-Indizierung) geht
> nicht in den Fit ein.
>
> Hinweis zum CV: Die gepoolte Größenverteilung ist inhärent sehr breit
> (gemessener CV≈1.4, auch mit `MIN_POINTS=50`). Da die **Größenverteilung für
> die effektive elastische Anisotropie unkritisch** ist (equiaxed + Textur
> bestimmen sie), wird der CV der **Neper-Zielverteilung** über `cv_cap=0.8`
> gekappt — der Median (~27 µm) bleibt erhalten, aber die Tessellation
> konvergiert und vernetzt robust (keine extremen Kleinstkörner). Der gemessene
> CV bleibt in `params` als `width2D_cv` erhalten; der genutzte Wert steht als
> `neper.morpho_cv`. Alles über `MIN_POINTS`/`cv_cap`/`morphology` in
> `materials.py` einstellbar (`cv_cap=None` → voller gemessener CV).

## Angepasste Parameter (automatisch aus den Messdaten, `params_<MAT>.json`)

| Größe | 316L | 17-4PH | trans |
|---|---|---|---|
| 3D-Korndurchmesser d₃D Median | 141 µm | 27 µm | 590 µm |
| CV (gemessen → Neper-Ziel) | 0.43 → 0.43 | 1.40 → **0.80** (cv_cap) | 0.86 → 0.86 |
| Elongation k (gemessen → genutzt) | 2.9 → 2.9 | 4.1 → **1.0** | 2.0 → 2.0 |
| Morphologie | kolumnar | **equiaxed** | kolumnar |
| Aufbaurichtung im V-Schliff | 122° (R=0.73) | 72° (R=0.10, schwach) | 8° (R=0.66) |

## Kombinierter Zugstab (`08_combined_specimen.py`)

Flacher Zugstab (V-Orientierung → Aufbaurichtung = Lastachse x), drei
**gleich lange** Bereiche entlang x gestapelt (unten → oben):

```
 x=0 ........ LX/3 ........ 2LX/3 ........ LX
   |  316L   | Übergang(trans) |  17-4PH  |
```

Der **Übergangsbereich ist standardmäßig homogen** (1 Bereich = 1 Korn, n=1)
mit einer repräsentativen Orientierung aus der Übergangs-EBSD-Map; mit
`HOMOGENEOUS=""` wird er stattdessen als aufgelöstes Polykristall modelliert.
316L und 17-4PH tragen ihre **eigene** gefittete Mikrostruktur (Korngröße, CV,
Elongation k, Orientierungen/Textur). Methode „multi-domain, merged":
je Bereich Tessellation im skalierten Raum + Streckung entlang x (kolumnare
Körner) → Vernetzung → Zusammenführen zu **einem** Netz in Python (meshio).
Cell-Tags im XDMF:

- `grain` — global eindeutige Korn-ID
- `region` — 0 (316L) / 1 (trans) / 2 (17-4PH)
- `material` — analog (getrennt für Erweiterbarkeit)

Steuerung über Env: `LX,LY,LZ` (Default 1800/600/300 µm), `MAXGRAINS` (700),
`MINGRAINS` (20), `RCL`, `FAST`.

> **Wichtig – Grenzflächen:** Die drei Bereichsnetze werden unabhängig erzeugt;
> die beiden Grenzflächen (x=LX/3, 2LX/3) sind geometrisch deckungsgleich, aber
> **nicht knotenkonform**. Für ein gebundenes (verschiebungsstetiges)
> Elastizitätsmodell in dolfinx müssen die Grenzflächen gekoppelt werden
> (Mortar-/MPC-Constraint auf den zugehörigen Facet-Sets) oder alternativ eine
> **konforme Variante** erzeugt werden (eine einzige Tessellation der Gesamtbox
> mit bereichsabhängigen Startkeimen, dann Bereichs-Tag pro Zelle). Sag Bescheid,
> falls die konforme Variante gebraucht wird.

> **Skalen-Hinweis:** Die Korngrößen der Bereiche unterscheiden sich stark
> (316L 141 µm, 17-4PH 10 µm, trans 590 µm). In einem mm-großen Stab lassen sich
> nicht alle repräsentativ auflösen; `MAXGRAINS`/`MINGRAINS` begrenzen die
> Kornzahl je Bereich (mit Konsolen-Warnung + effektivem d). Für einen
> „vereinfachten" Stab ist das beabsichtigt.

## Modellansatz (unverändert ggü. 316L-Basis)

1. **Analyse (01):** EBSD-Grain-Files einlesen (Filter: Phase, ≥10 Messpunkte),
   flächengewichtete Statistik (mechanisch relevante Körner dominieren).
2. **Tessellation (02):** Neper im skalierten (isotropen) Raum
   `diameq:lognormal(1,CV)`, danach Streckung `scale(1,1,k)` entlang z
   (= Aufbaurichtung) → kolumnare Körner. Bei `morphology=equiaxed` (17-4PH)
   ist k=1, d.h. keine Streckung → gleichachsige Körner.
3. **Orientierungen:** flächengewichtetes Bootstrap-Sampling der gemessenen
   Eulerwinkel (+3° Streuung), Probenframe so rotiert, dass die Aufbaurichtung
   auf +z fällt. Die Kristalltextur (und damit die elastische Anisotropie
   relativ zur Aufbaurichtung) wird so übernommen — auch für equiaxed-Körner.
4. **Vernetzung (03):** `neper -M`, lineare Tets, `RCL=0.75`.
5. **Konvertierung (04):** meshio: `.msh` → `.xdmf` mit `grain`-CellTag.
6. **Elastizität (06):** dolfinx-Loader baut pro Zelle den in den Probenframe
   rotierten kubischen Einkristall-Steifigkeitstensor
   `C_sample = M(g)·C_crystal·M(g)ᵀ` (6×6-Bond-Rotation), Materialkonstanten je
   Kristallsystem (FCC/BCC — **Platzhalterwerte, bitte ersetzen**).
7. **Verifikation (05):** Vergleich Tessellations- vs. EBSD-Statistik.

## Dateien

- `materials.py` — zentrale Material-/Phasen-Konfiguration + robuster EBSD-Loader
- `01_fit_ebsd.py --material 316L|17-4PH|trans` — Statistik-Fit → `params_<MAT>.json`, `n<N>_<MAT>.ori/.meta`, Plot
- `02_generate_tess.sh` (`MAT=…`) — Neper-Tessellation → `waam_<MAT>_n<N>.tess`, `grain_ori_<MAT>.txt`
- `03_mesh.sh` (`MAT=…`) — Vernetzung → `waam_<MAT>_n<N>.msh`
- `04_convert_to_xdmf.py <mesh.msh>` — XDMF-Export für dolfinx
- `05_verify_stats.py <MAT>` — Statistik-Verifikation + Plot
- `06_fenicsx_example.py <MAT|combined>` — dolfinx-Loader inkl. anisotroper Steifigkeit
- `07_tensile_specimens.py` (`MAT=…`, optional) — drei Einzelstäbe V/H/45° je Stahl → `spec_<MAT>_V/H/45deg.*` + `grain_ori_<MAT>_*.txt`; in `run_all.sh` via `SPECIMENS=1` aktivierbar
- `08_combined_specimen.py` — kombinierter V-Stab (316L / Übergang / 17-4PH)
- `09_homogenization_rve.sh` (`MAT=…`, `N=`, `RCL=`) — feineres RVE mit mehr Körnern für die Homogenisierung → `waam_<MAT>_n<N>.xdmf/.h5`
- `run_pipeline.sh` — **kompletter Lauf** (RVE + Stäbe + Kombistab), Env: `CLEAN/MATERIALS/N/RCL/SPECIMENS/COMBINED/FAST`
- `run_all.sh` — einfacher Lauf: n=200-RVEs + Kombistab (Stäbe via `SPECIMENS=1`)
- `clean_generated.sh` [`--dry`] — entfernt alle generierten Dateien (behält Quellskripte)
- `recover_and_continue.sh` (`MAT=…`) — aus fertiger `.tess` neu vernetzen (ohne Re-Optimierung)

## Einheiten / Annahmen

- Einheiten: **µm** (Netzkoordinaten), Steifigkeiten im Beispiel in **GPa** —
  im echten Solve konsistentes Einheitensystem wählen.
- Transversal isotrop; In-plane-Superelongation (mm-lange Körner im H-Schliff)
  nicht abgebildet. Stereologie: einfache π/4-Korrektur.
- 17-4PH als kolumnare Körner mit gepoolter Phase modelliert (siehe Hinweis).
