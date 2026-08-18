# Annahmen und Verfahren der Pipeline: DICOM → segmentiertes Array → FEM-Netz

Stand: 2026-08-07. Referenz-Case: `JM-25-74`, Bin4 + reduce-2, Konfiguration
`config.json` / `config-Bin4-reduce-2.json` in diesem Ordner.

---

## 0. Wo liegt der Code (für künftige Sessions)

Alle Pfade relativ zum Projekt-Root **`~/Work/Hypo/Hypo/Simulation`**
(im Container: `Meshing/pygalmesh/data` → `/data`).

| Zweck | Pfad |
|---|---|
| **Preprocessing + Vernetzung (Hauptpipeline)** | `Meshing/pygalmesh/data/scripts/014-Yield-Surface-From-leS/` |
| Frakturvariante derselben Pipeline | `Meshing/pygalmesh/data/scripts/011-Fracture-From-CT-Scans/`, `012-Fracture-Mesh-Sim-Split/` |
| Vorgängerstudie (linear-elastisch, Binning-Variation) | `Meshing/pygalmesh/data/scripts/009-Binning-Variation-CT-Stiffness/` |
| Ursprung des Plastizitäts-Solvers | `Meshing/pygalmesh/data/scripts/007-Plasticity-From-CT-Scans/` |
| **Simulationstemplate (elasto-plastisch)** | `.../014-Yield-Surface-From-leS/00_template/elastoplastic.py` |
| **DolfinX-Bibliothek (eigene Module)** | `dolfinx_alex/shared/utils/alex/` (u. a. `plasticity.py`, `homogenization.py`, `boundaryconditions.py`, `materials.py`, `postprocessing.py`, `linearelastic.py`, `imageprocessing.py`) |
| Fremdmodule | `dolfinx_alex/shared/utils/ronny/` |
| Container-Definitionen | `Meshing/pygalmesh/{Dockerfile,apptainer.def}`, `dolfinx_alex/{Dockerfile,apptainer.def}` |
| CT-Rohdaten (DICOM) | `Meshing/pygalmesh/data/resources/B02_Mevert_AlSi10MgSchaum_...` |
| Ergebnisse | `.../014-Yield-Surface-From-leS/00_results/` |
| Bestehende Doku | `README.md`, `FILES.md`, `LES_PIPELINE.md`, `CLAUDE_PROJECT_NOTES.md`, `SCAN_DATASET_WORKFLOW.md`, `_archive/PIPELINE_DOCUMENTATION.txt` (veraltet) (alle im 010-Ordner), `Documentation/Workflows/000-Special-Issue-2025.md` |

Ausführung der Vernetzungskette: `run_prepare_mesh_CLUSTER.sh`
(SLURM + Apptainer) bzw. `job_prepare_mesh_CLUSTER.sh <config>`; lokal
`job_yield_Bin4_reduce_2_LOCAL.sh`.

---

## 1. Gesamtkette (Reihenfolge laut Job-Skript)

```
DICOM-Stack
 → 00_dicom_2_npy.py                (Einlesen, Binning/Reduktion)          → npy je Schicht
 → 01_segment_slice_wise.py         (2D-Segmentierung, schichtweise)       → npy je Schicht, uint8 {0,1}
 → 02_build3D_segmented_array.py    (Stapeln + z/xy-Ausschnitt)            → segmented_3D_volume.npy
 → 02a_rotate_pic_to_align_with_axis.py (Rotation + Randpuffer)            → (überschreibt) volume
 → 02b_build_subvolume_arrays.py    (Bounding-Box + Unterteilung)          → subvolume_*/volume.npy
 → 02c_voxel_topology_cleanup.py    (nur Audit, Default)                   → volume_topology.txt
 → 02d_axis_aligned_cuboid_crop.py  (anisotrope Randschale)                → volume_boundary_shell_aniso.npy
 → 03_mesh_3D_array_pygalmesh.py    (SDF → Marching Cubes → CGAL)          → mesh.xdmf
 → 04_scale_and_translate_mesh_mod.py (Skalierung/Translation in CT-Koords)
 → 05_tetgen_postprocess_mesh.py    (TetGen-Check/Repair)
 → 08_mesh_quality_report.py / 09_mesh_topology_audit.py (Reports)
 → make_mesh_dlfx_compatible_cluster.py                                    → dlfx_mesh.xdmf
 → 00_template/elastoplastic.py (DolfinX)
```

---

## 2. DICOM → npy (`00_dicom_2_npy.py`)

**Verfahren**

- Einlesen über `pydicom.fileset.FileSet(DICOMDIR)`; Schichtreihenfolge = Reihenfolge im FileSet.
- Pixel als `np.uint16` aus `data.pixel_array`, **keine** Rescale-Slope/Intercept-Anwendung, **keine** HU-Umrechnung.
- Modi (`dicom2npy.option`): `full`, `crop` (fester x/y-Bereich), `reduce` (aktiv).
- `reduce`: **3D-Blockmittelung** über `factor³`-Würfel (`reduce_3d_chunk`, `mean`) — je `factor` aufeinanderfolgende Schichten werden zu einer zusammengefasst. Vorher `auto_crop_to_fit`: x/y werden auf das größte durch `factor` teilbare Maß beschnitten. Ein unvollständiger Restblock am Stapelende wird **verworfen**.
- Ausgabe: `slice_XXX.npy` + PNG-Vorschau.

**Aktive Parameter (Bin4-reduce-2)**

| Parameter | Wert |
|---|---|
| `option` | `reduce` |
| `reduce.factor` | 2 |
| `crop` | alle `null` (inaktiv) |
| `slice_start` / `slice_end` | 0 / `null` |
| Scanner-Binning | 4 → **effektiver Binningfaktor 8** |

**Metadaten**: `SliceThickness` und `PixelSpacing` werden mit `reduce_factor`
multipliziert und in `metadata.json` geschrieben. Ab hier gilt in der gesamten
Pipeline **`dx = SliceThickness`** als *isotrope* Voxelkantenlänge.

**Annahmen / Fallstricke**

1. **Isotropie der Voxel wird vorausgesetzt.** Nur `SliceThickness` wird weiterverwendet; `PixelSpacing` wird gespeichert, aber **nirgends im Repository wieder gelesen**. Für `JM-25-74` ist die Annahme erfüllt (`SliceThickness = PixelSpacing[0] = PixelSpacing[1] = 0.13390576171875 mm`; Bin1 ≈ 16.7 µm), sie wird aber nicht geprüft. Details: `Publications/02_WAAM_N1_Mikrostruktur/Bericht_Voxelgroesse_und_Phasenkonvention.md`.
2. Reduktion ist ein reines **Mittelwert-Downsampling** (kein Anti-Aliasing-Filter davor) → Teilvolumeneffekte werden verstärkt.
3. Die Schichtreihenfolge des `FileSet` wird ungeprüft als geometrische z-Reihenfolge angenommen.
4. `uint16` ohne Intensitätskalibrierung: Schwellwerte sind scannerspezifisch, nicht übertragbar.

---

## 3. npy → segmentiertes Array (`01_segment_slice_wise.py`)

**Verfahren (pro Schicht, 2D)**

1. optional Median-Filter (`median_filter_size > 1`) — hier **aus** (0).
2. Gauß-Filter `scipy.ndimage.gaussian_filter`, σ in **Pixeln**.
   σ wird bestimmt als `gaussian_sigma_pixels`, falls gesetzt; sonst
   `gaussian_filter_sigma_factor × SliceThickness`.
3. Schwellwert: `filters.threshold_otsu` (alternativ yen/li/triangle/isodata/mean/minimum oder fester Zahlenwert), dann `threshold = t·multiplier + offset`.
4. Maske: `mask = image <= threshold`; bei `invert_contrast = false` wird invertiert.
   Der Codekommentar behauptet „nach `invert_contrast()` ist Material = 1".
   **Verifiziert am Bildvergleich ist es umgekehrt:** `mask = image <= threshold`
   selektiert die *dunkle* Phase, also Pore und Umgebung → **Arraywert 1 = Pore,
   Arraywert 0 = Aluminium**. Die Kette ist trotzdem konsistent, weil Schritt 03
   ein zweites `invert_contrast()` anwendet (siehe 9.1).
5. Morphologische Nachbearbeitung (`remove_small_objects`, `remove_small_holes`, `binary_opening`, `binary_closing` mit `disk`-Footprint) — hier **alle aus**.
6. Ausgabe `segmented_slice_XXXX.npy` als `uint8`.

**Aktive Parameter**

| Parameter | Wert |
|---|---|
| `seg_algorithm` | `otsu` |
| `gaussian_filter_sigma_factor` | 1 |
| `gaussian_sigma_pixels` | `null` → σ = 1 · `SliceThickness` |
| `median_filter_size` | 0 (aus) |
| `threshold_multiplier` / `threshold_offset` | 1.0 / 0.0 |
| `invert_contrast` | `true` |
| Morphologie (4 Parameter) | 0 (aus) |

**Annahmen / Fallstricke**

1. **σ-Einheitenfehler — der Filter ist wirkungslos.** σ wird in *Pixeln* an `gaussian_filter` übergeben, aber aus der *physikalischen* `SliceThickness` in mm berechnet: σ = 1 · 0.1339 = **0.1339 px**. Nachgerechnet ergibt das ein Kernel-Zentralgewicht von 1.000000 und Nachbargewichte 0.000000 — numerisch die Identität. Die Segmentierung arbeitet also auf **ungeglätteten** Daten. Dasselbe gilt für `smoothing_sigma_factor` in Schritt 03. Die einzige wirksame Glättung der Pipeline ist `sdf_sigma_voxels = 1.0` auf dem SDF (korrekt in Voxeln definiert). Für definierte Bildglättung müsste `gaussian_sigma_pixels` explizit gesetzt werden.
2. **Otsu wird schichtweise neu berechnet.** Der Schwellwert variiert also über z (Beam-Hardening, Drift). Das ist eine bewusste Adaptivität, aber keine global konsistente Segmentierung.
3. **Bimodalität wird vorausgesetzt** (Otsu). Bei dünnen Stegen / starken Teilvolumeneffekten ist der Schwellwert systematisch zugunsten einer Phase verschoben → die relative Dichte ist schwellwertsensitiv und dominiert die späteren Steifigkeits-/Fließergebnisse.
4. Keine 3D-Konnektivitäts- oder Rauschbehandlung an dieser Stelle (Morphologie aus).
5. Keine Verifikation gegen eine Referenzdichte (z. B. gravimetrisch) im Skript.

---

## 4. Stapeln und Ausschnitt (`02_build3D_segmented_array.py`)

- Schichten werden alphabetisch sortiert zu `volume[x, y, z]` gestapelt (`uint8`).
- Achsenkonvention: `volume[:, :, i] = slice[min_x:max_x, min_y:max_y]`, d. h. **die erste Achse der Schicht wird x**, die zweite y, der Stapelindex z.
- Ausschnitt: `min_z` (inkl.) / `max_z` (exkl.); x/y über `desired_width_x/y` + `center_x/y` (hier `null` → volles Bild).
- Ausgabe `segmented_3D_volume.npy`.

**Aktive Parameter:** `min_z = 55`, `max_z = 143` (entspricht Region 220–570 der Bin2-Referenz, umgerechnet auf Bin4+reduce-2), x/y voll.

**Annahme:** Der z-Bereich ist als repräsentativer, artefaktfreier Bereich manuell gewählt und wird bei neuen Scans **nicht** automatisch validiert (siehe `SCAN_DATASET_WORKFLOW.md`).

---

## 5. Ausrichtung und Randpuffer (`02a_rotate_pic_to_align_with_axis.py`)

**Verfahren**

- Binärvolumen → float, dann drei nacheinander ausgeführte `scipy.ndimage.rotate`
  um die Achsenpaare `(1,0)`, `(2,0)`, `(2,1)` mit `reshape=False`,
  **`order=0` (Nearest-Neighbor)**, `prefilter=False`, `cval = material_value`.
- Re-Binarisierung: `rotated > 0.5 → 1`.
- `clear_boundary_artifacts`: äußere Bänder werden auf `material_value` gesetzt (Randpuffer, füllt Rotationsartefakte an den Rändern mit Material).
- Materialgrenzen (`material_bounds`) werden über `pore_value` (!) bestimmt und in `metadata.json` abgelegt.
- Ergebnis überschreibt `segmented_3D_volume.npy`.

**Aktive Parameter**

| Parameter | Wert |
|---|---|
| `angles` (Grad) | `[-3.05, -2.90, -5.00]` |
| `buffer_width_min/max_x` | 40 / 40 |
| `buffer_width_min/max_y` | 40 / 40 |
| `buffer_width_min/max_z` | 6 / 6 |
| `material_value` / `pore_value` | 1 / 0 |

**Annahmen / Fallstricke**

1. **Die Rotationswinkel sind manuell/visuell bestimmt**, nicht aus einer Registrierung oder Trägheitstensor-Hauptachsenanalyse. Sie sind scanspezifisch und müssen für neue Datensätze neu gesetzt werden.
2. Nearest-Neighbor-Rotation erhält die Binärstruktur, erzeugt aber Treppenartefakte an den Grenzflächen; die anschließende SDF-Glättung ist teilweise dafür da, diese wieder zu glätten.
3. Die Rotationen sind **nicht kommutativ** — die Reihenfolge (1,0) → (2,0) → (2,1) ist Teil der Definition.
4. `cval = material_value = 1`: hineinrotierte Außenbereiche und die Randpuffer werden mit Arraywert 1 gefüllt — das ist nach der tatsächlichen Konvention die **Porenphase**, also physikalisch korrekt (Artefaktränder werden zu Luft).
5. `print_material_bounds(rotated, pore_value = 0)` liefert die Bounding-Box der Voxel mit Wert 0. Nach der tatsächlichen Konvention ist das genau die **Aluminiumstruktur** — der Aufruf ist also korrekt, obwohl die Argumentbenennung das Gegenteil suggeriert.

---

## 6. Teilvolumen (`02b_build_subvolume_arrays.py`)

- Zuschnitt auf `material_bounds` aus 02a, dann Unterteilung in `xy_divisions²` Blöcke in x/y (z ungeteilt).
- Pro Block: `volume.npy`, plus relative Dichte und Porosität in `metadata.json`.
- **Aktiv: `xy_divisions = 1`** → genau ein Teilvolumen `subvolume_x<..>_y<..>`.

**⚠ `relative_density` und `porosity` sind in den Metadaten vertauscht.** Das
Skript zählt `volume == material_value (= 1)`, und Arraywert 1 ist die Porenphase
(Abschnitt 3). Für `JM-25-74`, `subvolume_x52_y74` steht
`relative_density = 0.5932` / `porosity = 0.4068`; die **tatsächliche relative
Dichte beträgt ≈ 0.41**. Nicht ungeprüft ins Paper übernehmen.

**Annahme:** Ein einziges Teilvolumen wird als RVE für die Homogenisierung
verwendet; RVE-Größenkonvergenz wird in dieser Pipeline nicht geprüft.

---

## 7. Topologie-Audit (`02c_voxel_topology_cleanup.py`)

- `enabled = true`, aber `cleanup.enabled = false` und `use_cleaned_for_meshing = false`
  → **reiner Report** (`volume_topology.txt`), das Vernetzungs-Input bleibt unverändert.
- Konnektivität: 6 für Material und Pore.
- Verfügbar, aber deaktiviert: größte Materialkomponente behalten, Mindest-Komponentengröße, Porenkavitäten füllen, Opening/Closing.

**⚠ Phasenverwechslung:** Das Skript arbeitet mit `material_value = 1`, also auf
der **Porenphase**. Der Report bezeichnet Porenkomponenten als
„Materialkomponenten" und umgekehrt. Solange `cleanup.enabled = false` ist, wirkt
sich das nur auf die Interpretation aus; bei Aktivierung würde die falsche Phase
bereinigt.

**Annahme:** Isolierte Materialinseln („floating islands") und eingeschlossene
Poren werden **nicht** entfernt. Sie erscheinen im Netz und im FE-Modell.
Freistehende Inseln erzeugen im Solver Starrkörpermoden, sofern sie nicht durch
die Randschale angebunden sind — das ist bei jedem wichtigen Fall über den
Topologiereport zu prüfen.

---

## 8. Anisotrope Randschale (`02d_axis_aligned_cuboid_crop.py`)

- `crop.enabled = false` (kein weiteres Zuschneiden).
- `boundary_seal.enabled = true`: äußere Bänder werden auf **Wert 0** gesetzt.
- Dicken (Voxel): `x_min/x_max = 3`, `y_min/y_max = 12`, `z_min/z_max = 3`.
- Ausgabe `volume_boundary_shell_aniso.npy` + `.txt`-Report; `use_cuboid_for_meshing = true`
  → **dieses Volumen geht in die Vernetzung**.

**Annahmen / Fallstricke**

1. **Vorzeichenkonvention (verifiziert):** Der Schalenwert ist 0 — und Arraywert 0
   ist die Aluminiumphase (Abschnitt 3). Nach der erneuten `invert_contrast()` in
   Schritt 03 wird daraus die vernetzte Materialphase. Die Schale ist also eine
   massive Materialhülle, kein Loch. Das ist die am leichtesten zu verwechselnde
   Stelle der Kette (siehe 9.1).
2. Die Schale existiert, um **glatte, vollflächige Dirichlet-Ränder** zu erhalten.
   Sie ist ein künstliches Bauteil: sie versteift das RVE an den Rändern und
   verfälscht die effektive Antwort systematisch (Randschichteffekt). Die
   y-Schale ist mit 12 Voxeln deutlich dicker als x/z (3) — die Anisotropie der
   Schale erzeugt für sich genommen bereits eine anisotrope effektive Antwort.
3. Die Schalendicke wird später in `elastoplastic.py` über Volumenform und
   Netzgrenzen in **physikalische Breiten** zurückgerechnet, um die Dirichlet-
   Bereiche zu definieren.

---

## 9. Segmentiertes Array → Oberfläche → Volumennetz (`03_mesh_3D_array_pygalmesh.py`)

`meshing_method = "sdf_pygalmesh"`.

**Verfahren**

1. Laden von `volume_boundary_shell_aniso.npy` in `nanomesh.Image`.
2. `select_subvolume(xs=x_range)` (voller Bereich), dann
   `.apply(rescale, scale=scale_factor).gaussian(sigma = smoothing_sigma_factor × SliceThickness)`
   und **erneut** `binary_digitize(threshold="otsu").invert_contrast()`.
3. `voxel_dim = SliceThickness / scale_factor`, isotrop.
4. Materialmaske: `segmented == material_value` (1).
   Optional größte Komponente behalten — **aus**.
5. **Signed Distance Field:** `ndi.distance_transform_edt(mask) − ndi.distance_transform_edt(~mask)`
   (euklidisch, in Voxeleinheiten), vorher `np.pad(pad_width, constant=False)`.
6. Glättung des SDF: `ndi.gaussian_filter(sdf, sigma = sdf_sigma_voxels)`.
7. **Marching Cubes:** `skimage.measure.marching_cubes(sdf, level=0.0, spacing=(dx,dx,dx), method="lewiner", step_size=1, allow_degenerate=False)`; anschließend Rückversatz um `pad_width · dx`.
8. **Oberflächenreparatur (trimesh):** `Trimesh(process=True)`, `fill_holes`, `fix_winding`, `fix_normals`, `merge_vertices`; optional Komponentenfilter und PyVista-Dezimierung (**beide aus**, `surface_decimation_reduction = 0`).
9. Oberflächen-Audit (`*_sdf_surface.topology.txt`), Anforderung `require_watertight_surface = true`.
10. Export als **OFF**, dann `pygalmesh.generate_volume_mesh_from_surface_mesh(...)` (CGAL 3D Mesh Generation, Delaunay-Verfeinerung) → `mesh.xdmf` (Tetraeder).

**Aktive Parameter**

| Parameter | Wert | Bedeutung |
|---|---|---|
| `material_value` | 1 | |
| `sdf_sigma_voxels` | 1.0 | Gauß-σ auf dem SDF, in Voxeln |
| `level` | 0.0 | Isolevel des SDF |
| `pad_width` | 1 | Rand-Padding vor SDF |
| `marching_cubes_step_size` | 1 | volle Auflösung |
| `keep_largest_component` | false | |
| `fill_holes` | true | |
| `require_watertight_surface` | true | |
| `reorient` | false | |
| `surface_decimation_reduction` | 0.0 | keine Dezimierung |
| `smoothing_sigma_factor` (03) | 1 | zusätzliche Glättung vor SDF |
| `scale_factor` | 1.0 | keine Umskalierung |
| **`max_element_size_factor`** | **1.48530842676** | → `max_cell_circumradius = 1.4853 · dx` |
| **`max_facet_distance_factor`** | **0.0891185056** | → `max_facet_distance = 0.0891 · dx` |
| `perturb` / `exude` | true / true | CGAL-Optimierer |
| `lloyd` / `odt` | false / false | |
| `exude_time_limit` | 30 s | |
| `min_facet_angle`, `max_circumradius_edge_ratio`, `max_radius_surface_delaunay_ball_factor`, `max_edge_size_at_feature_edges_factor` | 0.0 | **deaktiviert** (CGAL-Default „keine Schranke") |
| `seed` | 0 | |

Die beiden Größenfaktoren stammen aus dem Parameter-Sweep
`07_pygalmesh_parameter_sweep.py` in Studie 009 und sind dort als bester
Kompromiss aus Netzqualität und Elementzahl bestimmt worden.

**Annahmen / Fallstricke**

1. **Doppelte Segmentierung — hier kippt die Phase.** Das Eingangsarray ist bereits
   binär {0,1}, wird aber erneut geglättet (wirkungslos, s. o.), Otsu-geschwellt
   und **invertiert**. Erst nach diesem `invert_contrast()` gilt
   `material_mask = (segmented == 1)` = **Aluminium**. Vor Schritt 03 ist im Array
   1 = Pore und 0 = Aluminium. Die Schalenkonvention aus 02d (Wert 0) ist genau
   darauf abgestimmt. Jede Änderung an einer der beiden Stellen kippt Material und
   Pore — im Ergebnis würde dann der Porenraum vernetzt.
2. **Die Oberfläche ist geglättet, nicht voxeltreu.** SDF-Glättung
   (σ = 1 Voxel) + Marching Cubes verschieben die Grenzfläche und runden dünne
   Stege ab → systematische Abweichung der relativen Dichte gegenüber dem
   Voxelbild. Diese Abweichung wird nicht quantifiziert.
3. **Elementgröße ≈ 1.49 · Voxelkantenlänge.** Die Netzauflösung ist damit an die
   CT-Auflösung gekoppelt; dünne Stege werden über wenige Elemente aufgelöst.
   Eine Netzkonvergenzstudie unabhängig vom Binning existiert nicht in 010
   (nur die Binning-Variation in 009).
4. Es wird ein **einphasiges** Netz erzeugt: nur das Material wird vernetzt, die
   Poren sind leer (kein Zweiphasen-Mesh, keine Interface-Kennzeichnung).
5. `keep_largest_component = false` → isolierte Komponenten bleiben erhalten
   (vgl. Abschnitt 7).
6. CGAL-Qualitätsschranken (Facettenwinkel, Radius-Kanten-Verhältnis) sind auf 0
   gesetzt, also **nicht aktiv**. Qualität wird stattdessen nachträglich über
   `exude`/`perturb` und die Reports 08/09 kontrolliert.

---

## 10. Netz-Nachbearbeitung

**`04_scale_and_translate_mesh_mod.py`**

- Achsenweise affine Abbildung der Netz-Bounding-Box auf `[0, N_i · dx]`
  mit `N` = Form des ersten Teilvolumens und `dx = SliceThickness`.
- Anschließend Translation, sodass der Mittelpunkt auf
  `(center_x · dx, center_y · dx, z-Mitte)` liegt (`center_x/y` aus dem Ordnernamen).
- **Achtung:** Die Skalierung ist **nicht uniform** — jede Achse wird einzeln
  gestreckt, damit die Bounding-Box exakt passt. Da Marching Cubes die Oberfläche
  minimal einwärts/auswärts verschiebt, ist die tatsächliche Netz-Bounding-Box
  nicht exakt `N·dx`; die Korrektur führt daher eine kleine, achsenabhängige
  Verzerrung ein.

**`05_tetgen_postprocess_mesh.py`** — `enabled = true`, Switches `-rO2CV`
(rekonstruieren, Optimierungsstufe 2, Konsistenzprüfung, verbose).
`06_gmsh_postprocess` ist deaktiviert.

**`08_mesh_quality_report.py`** — Schwellen: Aspect Ratio gut ≤ 20 / akzeptabel ≤ 50;
kleinster Diederwinkel gut ≥ 10° / akzeptabel ≥ 5°; Anteil Diederwinkel 0–5° gut = 0 /
akzeptabel ≤ 1e-3; Anteil 5–10° gut ≤ 0.01 / akzeptabel ≤ 0.05; kleinster Facettenwinkel
gut ≥ 5° / akzeptabel ≥ 2°.

**`09_mesh_topology_audit.py`** — prüft Tetraeder-Volumenvorzeichen, winzige/degenerierte
Elemente (`tiny_volume_absolute = 1e-12`, relativ zum Median `1e-8`), doppelte Facetten,
offene und nicht-mannigfaltige Randkanten. `repair.enabled = false` → **nur Bericht**.

**`make_mesh_dlfx_compatible_cluster.py`** — liest `mesh.xdmf` mit meshio, filtert
Tetraeder mit Referenz ≠ 0 (`medit:ref` bei pygalmesh, sonst `tetgen:ref` /
`gmsh:physical`), baut ein DolfinX-Mesh mit **linearen Lagrange-Tetraedern (P1,
Geometriegrad 1)** und schreibt `dlfx_mesh.xdmf`.

**Annahme:** Elementtyp ist durchgehend **linearer Tetraeder**. Für J2-Plastizität
mit nahezu inkompressiblem plastischem Fließen ist P1-Tet volumetrisch versteifend
(Locking), sofern im Solver keine gemischte/F-bar-Formulierung verwendet wird —
das ist beim Solver in `00_template/elastoplastic.py` bzw.
`dolfinx_alex/shared/utils/alex/plasticity.py` zu prüfen.

---

## 11. Übergabe an die Simulation (Kurzfassung)

- `dlfx_mesh.xdmf` + `config.json` je Teilvolumenordner → `00_template/elastoplastic.py`.
- Material `std`: `E = 70000`, `nu = 0.35`, `sig_y = 140`, `hard = 0.0` (ideal plastisch).
- Makrodehnung: diagonal, `strain_scale(t) · [eps_1, eps_2, eps_3]` mit
  `strain_scale(t) = 1e-6 + 1.0·t`, `time_step = 1e-4`, `dt_min = 1e-11`,
  `total_time = 1e9` nur als Solver-Horizont.
- Fließkriterium der Auswertung: erster Zeitschritt, in dem
  `yielded_volume_fraction = 2 %` des reduzierten Materialvolumens
  `alpha > alpha_yield_tolerance = 1e-5` erreicht.
- Dirichlet-Ränder über die volle Dicke der Randschale aus 02d auf Min-/Max-Fläche
  der aktiven Lastachse; Fallback: geometrische Flächentoleranz.
- `quadrature_degree = 1`.

---

## 12. Zusammenfassung der wichtigsten Annahmen

1. Voxel sind isotrop; nur `SliceThickness` definiert die Länge (für alle
   geprüften Scans faktisch erfüllt, aber ungeprüft). dx = 0.133906 mm.
2. Segmentierung: schichtweises Otsu auf ungeeichten uint16-Werten **ohne
   wirksame Vorglättung** (σ-Einheitenfehler); keine Dichtevalidierung.
3. Keine morphologische Bereinigung und keine Komponentenfilterung — isolierte
   Inseln und geschlossene Poren bleiben erhalten (nur Report).
4. Ausrichtung über drei manuell bestimmte Winkel, Nearest-Neighbor-Rotation,
   Ränder werden mit Material aufgefüllt.
5. Eine künstliche, anisotrope Randschale (3/12/3 Voxel) ersetzt die
   Originalstruktur am Rand, um Dirichlet-Ränder zu ermöglichen.
6. Vernetzung über geglättetes SDF + Marching Cubes + CGAL: die Oberfläche ist
   bewusst glatter als die Voxeldaten; Elementgröße ≈ 1.49 Voxel.
7. Einphasiges P1-Tetraedernetz; ein einzelnes Teilvolumen dient als RVE, ohne
   RVE-Größen- oder Netzkonvergenznachweis in diesem Projekt.
8. Die Phasenkonvention hängt an zwei aufeinander abgestimmten Stellen
   (Schalenwert 0 in 02d und `invert_contrast()` in 03). Im Array gilt vor
   Schritt 03: **1 = Pore, 0 = Aluminium** — entgegen allen `material_value`-
   Feldnamen. Folge: `relative_density` in den Metadaten ist die Porosität; die
   relative Dichte des vernetzten Teilvolumens beträgt ≈ 0.41.
