# CLAUDE.md — 017-Yield-Surface-Batch-leS-nohinge

Fließflächen-Erzeugung aus **bereits segmentierten Voxelbildern** (`.leS`).
Kopie von `014-Yield-Surface-From-leS` (das seinerseits die DICOM-freie
Abspaltung von `010-Yield-Surface-Generation` ist) mit einer zusätzlichen
Batch-Schicht.

**Studie dieses Ordners:** vier Datensätze (`JM-25-77`, `JM-25-71`, `JM-25-83`,
`JM-25-88`) × zwei Anfangsfließgrenzen (75 und 100 MPa) = acht Kombinationen,
je 96 Fließflächenpunkte. Ein vorbereitetes Netz je Datensatz, `reduce = 2`,
Punkt-Jobs mit `-t 10080` (7 d) auf der Partition `long`.
**Bedienung: `README.md`. Entscheidungen: `CLAUDE_PROJECT_NOTES.md`.**

**Grundregel (Projektvorgabe):** Alles, was entschieden oder gelernt wird, wird
in einer `.md`-Datei dokumentiert — hier bzw. in `CLAUDE_PROJECT_NOTES.md`.

---

## 1. Ordnerstruktur und Container-Mapping

| Zweck | Pfad |
|---|---|
| dieses Projekt (Host, Mac) | `~/Work/Hypo/Hypo/Simulation/Meshing/pygalmesh/data/scripts/017-Yield-Surface-Batch-leS-nohinge/` |
| dieses Projekt (Cluster) | `$HPC_SCRATCH/pygalmesh/data/scripts/017-Yield-Surface-Batch-leS-nohinge/` |
| **Cluster-Login (Lichtenberg)** | `ssh lcluster13.hrz.tu-darmstadt.de` (User `as12vapa`, Key in `~/.ssh/config`; Ersatz `lcluster20.hrz.tu-darmstadt.de`). Interner Name im Prompt: `logc0001`. **Nie einen Hostnamen raten.** Direkt in den Scratch: `scp <datei> lcluster13.hrz.tu-darmstadt.de:/work/scratch/as12vapa/pygalmesh/data/scripts/017-Yield-Surface-Batch-leS-nohinge/` |
| Container auf dem Cluster | `apptainer exec --bind /work/scratch/as12vapa $HOME/dolfinx_alex/alex-dolfinx.sif python3 …` — ohne `--bind` ist der Scratch im Container unsichtbar (nur Home + cwd) |
| dieses Projekt (Container) | `/data/scripts/017-Yield-Surface-Batch-leS-nohinge/` |
| `.leS`-Quelldaten | `/data/resources/A01_segmented/` (Cluster: `$HPC_SCRATCH/pygalmesh/data/resources/A01_segmented/`) |
| Paper-/Publikationsordner | `~/Work/Hypo/Hypo/Publications/Folgepaper Homogenisierung von elasto-plastischen Eigenschaften/` |
| DolfinX-Module | `~/Work/Hypo/Hypo/Simulation/dolfinx_alex/shared/utils/alex/` |
| Vorgängerprojekt (DICOM-Pfad) | `.../scripts/010-Yield-Surface-Generation/` |

Der Container-Bind ist unverändert `Meshing/pygalmesh/data → /data`. In
JSON-Configs steht **immer der Container-Pfad** (`/data/...`), nie ein
unaufgelöstes `$HPC_SCRATCH`; die Cluster-Skripte rechnen das per
`${pfad/#\/data/$HPC_SCRATCH/pygalmesh/data}` auf den Host zurück.

### Dokumentation in diesem Ordner

- **`FILES.md`** — jede Datei mit Zweck, Aufrufer und Config-Abschnitt.
- **`LES_PIPELINE.md`** — Bedienung: Datenablage, Auflösung, Config, Cluster.
- `PIPELINE_ANNAHMEN_DICOM_TO_FEM.md` — Algorithmen, Parameter und Annahmen der
  gemeinsamen Kette ab Schritt 02b (Name aus 010 übernommen).
- **`README.md`** — Bedienung der Batch-Studie: erzeugen, einreichen, überwachen, einsammeln, zippen.
- `CLAUDE_PROJECT_NOTES.md` — Session-Protokoll, inklusive der Vorgeschichte aus 010.

---


## 0. Transfer Mac ↔ Cluster — IMMER über Git (Nutzerregel 20.10.2026, kein scp)

Repo `AlexS1986/Meshing` (Wurzel Mac `~/Work/Hypo/Hypo/Simulation/Meshing`, Cluster `$HOME/meshing/Meshing`, Branch `main`).
Jede Änderung in diesem Ordner geht den Weg **Mac commit+push → Cluster pull → Sync nach Scratch**. Agenten geben genau diese drei Blöcke aus:

```bash
# --- Mac --------------------------------------------------------------------
cd ~/Work/Hypo/Hypo/Simulation/Meshing/pygalmesh/data/scripts/017-Yield-Surface-Batch-leS-nohinge
git status --short .
git add <geänderte Dateien>            # Sicherungen *.vor_* nicht aufnehmen
git commit -m "017: <was und warum>"
git push

# --- Cluster (ssh lcluster13.hrz.tu-darmstadt.de) ---------------------------
cd "$HOME/meshing/Meshing" && git pull && git log --oneline -1
SKIP_GENERATE=1 "$HOME/meshing/Meshing/pygalmesh/data/scripts/017-Yield-Surface-Batch-leS-nohinge/batch_create_folders_CLUSTER.sh" 2>&1 | tail -n 2
#   (rsync -av --update nach $HPC_SCRATCH/pygalmesh; "rsync error code 23" = harmloser Symlink in 009)

# --- Kontrolle --------------------------------------------------------------
cmp "$HOME/meshing/Meshing/pygalmesh/data/scripts/017-Yield-Surface-Batch-leS-nohinge/<datei>" \
    "$HPC_SCRATCH/pygalmesh/data/scripts/017-Yield-Surface-Batch-leS-nohinge/<datei>" && echo "Scratch aktuell"
```
Fallen: (a) `index.lock` auf dem Mac → `pgrep -fl git`, dann `rm .git/index.lock`; (b) `git pull` bricht ab, wenn auf dem Cluster
ungetrackte Dateien überschrieben würden → beiseitelegen (`mv … $HOME/cfg_bak_<datum>/`), dann erneut ziehen;
(c) `rsync --update` kopiert nur neuere Dateien — eine auf dem Scratch von Hand geänderte Datei wird nicht überschrieben.

## 2. Konventionen

1. **Vor dem Bauen lesen:** `FILES.md`, `LES_PIPELINE.md`, `CLAUDE_PROJECT_NOTES.md`.
2. **Skripte werden vorbereitet, nicht blind ausgeführt.** Rechenintensive Läufe
   startet der Nutzer selbst im Container bzw. auf dem Cluster; Ausnahme sind
   kleine Verifikationsläufe auf Teilausschnitten.
3. **Nummerierung** spiegelt die Pipeline-Reihenfolge; der `.leS`-Zweig nutzt `A0x`.
4. **Configs werden abgeleitet, nicht von Hand geschrieben:** `create_les_config.sh`
   (Variablen in `config.sh`) → `create_les_dataset_config.py` → `config-A01-les.json`.
   `config.json` ist eine Kopie davon und der Default ohne `--config`.
5. **Array-Konvention:** `uint8`, Form `(x, y, z)`, `z` ist die Slice-Achse.
6. **⚠ Phasenkonvention:** Vor Schritt 03 gilt im Array **1 = Pore, 0 = Aluminium**
   — entgegen der Benennung `material_value = 1`. Schritt 03 invertiert erneut, erst
   danach ist `material_mask == 1` das Aluminium; die Randschale aus 02d (Wert 0)
   ist darauf abgestimmt. In der `.leS`-Quelldatei ist es umgekehrt (1 = Material),
   deshalb invertiert `A01_les_2_npy.py` per Default. Details:
   `PIPELINE_ANNAHMEN_DICOM_TO_FEM.md` §3 und §9.1.
7. **Voxelgröße:** `A01_les_2_npy.py` schreibt sie als
   `metadata.json → 00_dicom2npy.SliceThickness` in **mm** (Voxelgröße × Reduktion);
   `03` und `04` lesen genau diesen Wert.
8. **Dokumentieren statt merken.**

---

## 3. Datensatz

`JM-25_77_85p55.leS` (2,5 GB): `1187 × 1188 × 886` Voxel bei 16,7 µm
= 19,8 × 19,8 × 14,8 mm, Porosität **85,551 %** (das `85p55` im Dateinamen).
Zeilenformat: `nx*ny` Zeilen mit je `nz` Werten, Zeilenindex `l = ix*ny + iy`
(C-Order), feste Zeilenbreite 1773 Byte. Belege für diese Interpretation stehen
in `LES_PIPELINE.md`.

---

## 4. Auflösung und Vernetzungsparameter (entschieden)

| reduce | Gitter | Voxel | Voxelgröße | |
|---:|---|---:|---|---|
| 1 | 1187 × 1188 × 886 | 1249 MVoxel | 16,7 µm | nur mit Crop |
| **2** | 593 × 594 × 443 | 156 MVoxel | 33,4 µm | **Default** |
| 4 | 296 × 297 × 221 | 19 MVoxel | 66,8 µm | |
| 8 | 148 × 148 × 110 | 2,4 MVoxel | 133,6 µm | ≈ Auflösung der alten `Bin4-reduce-2`-Studie |

- Blockwert per **Majority-Vote** über die Aluminiumphase; die relative Dichte
  verschiebt sich dabei um weniger als 0,15 Prozentpunkte.
- **Kein zusätzlicher Gauß auf den Labels.** Der Gauß in `03`
  (σ = `sigma_factor × SliceThickness`) ist bei mm-Voxelgrößen wirkungslos
  (σ ≈ 0,03 Voxel); wirksam ist `sdf_sigma_voxels = 1.0` auf dem
  Signed-Distance-Field. `sdf_sigma_voxels` nur zusammen mit `pad_width ≥ 3`
  erhöhen (gemessen: σ = 1,25 bei `pad_width = 1` erzeugt 7180 offene Kanten).
- **`pad_width = 3`** (statt 1) als Absicherung gegen abgeschnittene Isoflächen.
- **`keep_largest_component = true`** ist hier **Default**: im Datensatz stecken
  99,98 % des Aluminiums in einer Komponente, der Rest sind freischwebende Inseln
  (meist ≤ 10 Voxel), die im FE Starrkörpermoden erzeugen.
- `03` repariert punktuelle Oberflächendefekte selbst (doppelte Flächen,
  nicht-mannigfaltige Kanten) — siehe `LES_PIPELINE.md`.

---

## 5. Ablauf auf dem Cluster

```bash
# 1. Jobs erzeugen und nach $HPC_SCRATCH synchronisieren (Login-Node)
cd "$HOME/meshing/Meshing/pygalmesh"
YIELD_SURFACE_POINTS=192 data/scripts/017-Yield-Surface-Batch-leS-nohinge/02_create_folders_CLUSTER.sh

# 2. Netzvorbereitung und alle Punkt-Jobs in einem Aufruf einreihen
"$HPC_SCRATCH/pygalmesh/data/scripts/017-Yield-Surface-Batch-leS-nohinge/submit_les_pipeline_CLUSTER.sh"
```

Details, Optionen und Diagnose: `LES_PIPELINE.md`.

---

## 6. Offene Punkte

- **Auflösung für den Produktionslauf:** reduce=2 ist 4× feiner als die alte
  Studie bei größerem Gebiet — Vernetzung und FE werden entsprechend teuer
  (Elementgröße `max_cell_circumradius = 1,485 · dx`). Für Vergleichbarkeit mit
  der bestehenden Fließfläche wäre reduce=8 die passende Wahl.
- **Randschalendicken** (`x/z = 3`, `y = 12` Voxel) stammen aus der alten
  DICOM-Config und sind auf deren Voxelgröße abgestimmt; für 33,4 µm prüfen.
- **`02c`** läuft als reiner Report (`cleanup.enabled = false`). Falls die
  Oberfläche doch Probleme macht, wäre hier der Hebel für eine Voxel-Bereinigung.

---

## 7. Learnings 1D-Druckversuch JM-25-71 (21.10.2026, für alle Agenten)

Einstieg Ergebnisse: `compression_jobs/ergebnisse/` — `kennwerte_druck_71.md/.csv`, `INTERPRETATION_Diskrepanz_druck_71_20261021.md`,
`druck_71_vs_versuch.png` (Skript `plot_druck_vs_versuch.py`). Protokoll: `CLAUDE_PROJECT_NOTES.md` 20./21.10.2026.

**Modell/Randbedingung**
- Nur zwei Plattenbänder ⊥ Lastachse (Schalendicke > 0 nur dort), Seitenflächen frei. Dirichlet u = ε·x auf dem ganzen Plattenband,
  ε = diag(nur Lastachse) → Querverschiebung der Platten = 0 = **haftende Platten**. Gleitende Platten gibt es (noch) nicht.
- Nennspannung = Volumenmittel `sigma_avg_reduced_volume[a][a]`, normiert auf das Quadervolumen inkl. Poren (= F/A).
  Die Reaktionskraft in `*_graphs.txt` ist die Eigenspannung der zwangsverschobenen Platte — **nie verwenden** (auch nicht in 017-Produktionsläufen).
- Querspannungen im Volumenmittel 0,09–0,14 der Axialspannung kommen ausschließlich aus der Plattenhaftung (Satz von der mittleren
  Spannung: Seiten und Poren lastfrei). Kriterium ≤ 0,05 ist mit diesem Modell nicht erreichbar — kein Laufehler.
- Dichten: x-Netz 0,1891 (reduced_volume_material 1203,6 mm³, A 342,68 mm²), y-Netz 0,1888 (1176,2 mm³, A 340,34 mm², L 19,506 mm).
  KUBC-Produktionsnetz 0,1768. Beim Vergleich immer nennen.

**Läufe/Numerik**
- Mit neuem Template laufen alle y-Läufe in **einem** 24-h-Glied durch (6,8–9,7 h, ≈ 105 Schritte); x/180 ebenso (10,2 h). x/75 und x/100
  (alte Template-Kopie, Start 20.10. 15:40) brauchen Walltime-Restart.
- Ketten: Ist Glied 1 ok, werden Glieder 2 (afternotok) von Slurm CANCELLED; dadurch startet Glied 3, erkennt den fertigen Lauf, kopiert
  Ergebnisse erneut und endet nach < 15 s mit Exit 0. Harmlos, nichts tun.
- Am Walltime-Stopp (Exit 3) wird **kein** `yield_averages_*.json` geschrieben; die bisherige Historie steht in `restart_meta_elastoplastic_std_<a>.json`
  (`averaged_history`) und ist direkt mit `evaluate_compression_run.py` auswertbar. Restart x/75, x/100 ohne Sprung.
- Verfestigende Läufe: `E_10_40` aus evaluate_compression_run.py ist unbrauchbar (Fenster 10–40 % σ_max reicht in den Fließbereich) → E0 (erster Schritt) nehmen.
- σ_y 100 + H 2000 (y, haftend) trifft den Versuch 71 zwischen 0,5 und 2 % auf ±5 %, steigt danach zu steil (lineare Verfestigung ohne Sättigung).
- Letzte Historienzeile liegt bei 2,475–2,498 % (letzter Schritt schießt über total_time 0,1); `sigma_at_2.5pct` = nan → σ_end mit ε_end angeben.
- Newton max. 7–9 (Grenze 12); dt-Halbierungen 0–14 je Lauf; `.err` enthält nur die harmlose Apptainer-chdir-Warnung.

**Auswertung**
- Rp0,2-Vorschrift = Versuchsauswertung (E Regression 10–40 % σ_max, 0,2-%-Parallele). Rp0,2 ist robust gegen E: E₀ statt E_10_40 −0,5 %,
  Versuchs-E 1760 statt ≈ 3900 +5…+11 %. E_10_40 liegt 3–7 % unter E₀ (Plastizität im Fenster).
- σ̄_1D ∝ σ_y^m mit m = 0,88–0,90 (KUBC 0,93). 1D/KUBC: Rp0,2 0,62–0,68, σ(1 %) 0,70–0,78 (roh); x/y = 1,10 bei gleicher Dichte.
- Rückgerechnetes σ_y,eff (ideal plastisch) für Versuch 71: 136–153 (Rp0,2), 150–168 (σ 1 % ↔ Plateau), 159–177 MPa (σ_max).
- **Abgleich A01-FFT (Julian, GeoDict, 21.10.):** glatte Platten (symmetrische RB), Seiten frei (Luftschicht), ν 0,33, ρ 0,214, gleiches
  Voxelgitter. Rp0,2 nach Dichtekorrektur (ρ^1,75) **identisch** (FEM 5,07 / FFT 5,05 bei σ_y 75). Nach dem Fließbeginn steigt das FEM
  weiter (+21 % bis 1,5 %), die FFT nicht (+4 %) → die strukturelle Verfestigung des 1D-FEM ist großteils **Plattenhaftung**.
  Vergleiche nach dem Fließbeginn nur mit gleicher Plattenbedingung; Gleitplatten-Variante fehlt noch (Codeänderung `get_bcs`).
  Arbeitsannahme (Nutzer 21.10.): im Versuch ist die Gleitung eher behindert → haftende Platten (FEM) näher am Versuch, glatte (FFT) = untere Grenze;
  H gegen den Versuch am FEM mit haftenden Platten kalibrieren.
- Interpretation in Kürze: KUBC → Versuch ist hauptsächlich Randbedingung (Faktor 1,4–1,8); 1D-FEM und A01-FFT stimmen auf ±10 %;
  der Rest zum Versuch ist fehlende Materialverfestigung (σ_y,0 ≈ 100 + Verfestigung ≈ σ_y,eff 150–180). KUBC-Fläche nicht neu rechnen.

**Werkzeug/Transfer**
- Cluster nur per `ssh -o BatchMode=yes lcluster13.hrz.tu-darmstadt.de 'bash -lc "…"'`; im Doppelquote-Block `\$HPC_SCRATCH`, `\$USER` escapen.
  ControlMaster steht in `~/.ssh/config`. Banner/PQ-Warnung am Anfang jeder Ausgabe ignorieren.
- `scp` auf dem Mac (SFTP-Modus) expandiert `{a,b}` im Remote-Pfad nicht → Dateien einzeln holen.
- Varianten mit Verfestigung: `setup_compression_jobs.py … --hard H --variant h<H>` (eigene Ordner/Configs, gleiches Netz). Vorbereitet:
  `JM-25-71_drucky_sigy100h2000` (sig_y 100, H 2000), Submit `compression_jobs/submit_compression_drucky-h2000_CLUSTER.sh` — Einreichen nur nach Freigabe.
- Repo-`.gitignore` ignoriert `*.csv`/`*.png` → Ergebnisdateien in `compression_jobs/ergebnisse/` mit `git add -f` aufnehmen (klein halten, keine H5/XDMF).
