# 013 — CT → FEM → Fließfläche (aufgeräumte Pipeline)

Bereinigte Fassung von `010-Yield-Surface-Generation`. Gleiche Schrittfolge und
Nummerierung, aber ohne die toten Pfade, mit **wirksamer Glättung** und mit
korrigierter Buchführung.

**Die 0/1-Bedeutung, die an Marching Cubes und pygalmesh übergeben wird, ist
unverändert.** `verify_pipeline.py` weist das bitgenau nach.

---

## Schnellstart

```bash
# Nur Netze erzeugen (lokal)
MESH_ONLY=1 ./run_pipeline_LOCAL.sh

# Komplette Kette inkl. elasto-plastischem Solve (lokal)
./run_pipeline_LOCAL.sh

# Andere Config
CONFIG_PATH=/data/scripts/013-Clean-CT-To-Yield-Surface/config-XY.json ./run_pipeline_LOCAL.sh

# Cluster: Netz einmalig vorbereiten
sbatch job_mesh_CLUSTER.sh config.json

# Cluster: N Belastungsrichtungen erzeugen und submitten
./setup_yield_surface_jobs.sh 192
bash yield_surface_jobs/n192/submit_all_yield_surface_points.sh

# Selbsttests (läuft ohne pygalmesh/DolfinX)
python3 verify_pipeline.py
python3 verify_pipeline.py --npy .../subvolume_x52_y74/volume.npy
```

---

## Phasenkonvention — bitte vor jeder Änderung lesen

Die Segmentierung wählt über `mask = image <= threshold` die **dunkle** Phase.
Aluminium ist im µCT die helle Phase. Im gespeicherten Array gilt deshalb:

| Arraywert | Bedeutung |
|---|---|
| **0** | Aluminium — **das ist die Phase, die vernetzt wird** |
| **1** | Pore / Luft / Umgebung |

Drei Stellen hängen zusammen und dürfen nur gemeinsam geändert werden:

1. `01_segment_slice_wise.py` — `invert_contrast: true`
2. `02d_axis_aligned_cuboid_crop.py` — `boundary_seal.value: 0` (die Randschale
   ist damit massives Material und trägt die Dirichlet-Ränder)
3. `03_mesh_3D_array_pygalmesh.py` — `meshed_phase_array_value: 0`

Achtung bei den Feldnamen: `material_value` in `02a` ist das *Arraylabel* 1,
also die Porenphase. Das ist Absicht — die Rotationsartefakte am Rand werden
mit Luft gefüllt, und `material_bounds` wird über den Wert 0 bestimmt und ist
damit die Bounding-Box des Aluminiums.

---

## Was gegenüber 010 geändert wurde

### 1. Die Glättung wirkt jetzt

010 berechnete `sigma = gaussian_filter_sigma_factor × SliceThickness`, also
eine **Länge in mm**, und übergab sie an `scipy.ndimage.gaussian_filter`, das
sigma in **Voxeln** erwartet. Für `JM-25-74` ergab das σ = 0.134 Voxel — ein
Kernel mit Zentralgewicht 1.000000, also die Identität. Die Segmentierung lief
auf ungeglätteten Daten, und `smoothing_sigma_factor` in Schritt 03 war
ebenfalls wirkungslos.

013:

| Parameter | Wert | Bedeutung |
|---|---|---|
| `smoothing_mode` | `3d` | Glättung auf dem gestapelten Volumen statt schichtweise 2D |
| `gaussian_sigma_voxels` | `1.0` | σ **in Voxeln** |
| `sdf_sigma_voxels` | `1.0` | unverändert, war schon korrekt |

Das Volumen wird nicht komplett in den Speicher geladen: der Filter ist
separabel und wird in zwei Strömungsdurchläufen angewandt (in-plane je Schicht,
dann 1D entlang z blockweise über Spalten). `verify_pipeline.py` Prüfung C
vergleicht das Ergebnis gegen `scipy.ndimage.gaussian_filter` auf dem vollen
Volumen (max. Abweichung 6e-08).

Jeder Lauf schreibt eine Kernel-Prüfung ins Log und in die Metadaten:

```
Gaussian check: sigma = 1 voxels -> centre weight 0.398943,
                neighbour weight 0.241971 (effective)
```

Bei einem zu kleinen σ steht dort `NO-OP -- sigma is far too small`. Der Fehler
von 010 kann also nicht unbemerkt zurückkommen.

Zusätzlich neu: `threshold_scope` (`slice` oder `volume`). Default bleibt
`slice`, also schichtweises Otsu wie in 010.

### 2. Nur noch ein Meshing-Backend

`03` enthielt vier Pfade (`pygalmesh` über INR, `nanomesh`, `sdf_gmsh`,
`sdf_pygalmesh`); produktiv war ausschließlich `sdf_pygalmesh`. Die anderen drei
sind entfernt, ebenso `nanomesh_parameters`, `sdf_gmsh_parameters`, der
Top-Level-Block `pygalmesh_parameters` und die nanomesh-Abhängigkeit.
743 → 484 Zeilen.

Ebenfalls entfernt: die **Scheinsegmentierung**. 010 schickte das bereits binäre
Array durch `gaussian(...) → binary_digitize('otsu') → invert_contrast()`. Auf
einem {0,1}-Array ist der Gauß ein No-op und `digitize + invert` exakt eine
Komplementbildung, die ganze Kette also `material_mask = (volume == 0)`. Genau
das steht jetzt explizit da, plus eine Assertion, dass das Eingangsarray binär
ist. Prüfung A in `verify_pipeline.py` vergleicht beide Varianten auf 20
Zufallsvolumen und auf einem echten Teilvolumen — identisch.

`pygalmesh` wird erst in `write_sdf_pygalmesh_mesh` importiert, damit die
Voxel-Helfer auch ohne Meshing-Container importierbar sind.

### 3. Korrigierte Buchführung

| Was | 010 | 013 |
|---|---|---|
| `02b` `relative_density` | zählte Wert 1 = **Porosität** (0.5932) | zählt Feststoff (**0.4068**) |
| `02c` `material_value` | `1`, das Audit beschrieb also die Poren | `0` = Aluminium; `material_*` heißt jetzt Material |
| `02c` Cleanup-Schreiben | `np.where(mask, material_value, 0)` → all-null, sobald `material_value = 0` | schreibt beide Phasenlabels explizit |
| `02` y-Zuschnitt | las `desired_width_y`, Configs schrieben `desired_height_y` → wirkungslos | akzeptiert beide |
| `00` Voxelisotropie | `PixelSpacing` wurde geschrieben, aber nie gelesen | Assertion gegen `SliceThickness` |

Die Voxelarrays selbst sind von diesen Korrekturen nicht betroffen.

### 4. Entfernte Dateien

`06_gmsh_postprocess_mesh.py` (deaktiviert), `02a_..._bu.py`,
`04_scale_and_translate_mesh.py` (alte, ungenutzte Variante — die produktive
`_mod`-Fassung heißt jetzt so), `make_mesh_dlfx_compatible.py` (lokale
Dublette), `create_config.sh`, `package_yield_run_jsons.py`,
`create_yield_surface_n192.sh`, die fallspezifischen
`job_*_Bin4_reduce_2_*.sh`-Wrapper.

In `00_template/` lagen 13 Dateien aus einem alten E-Modul-/Druckversuch
(Fortran-Quellen, `Makefile`, `emodul.lay`, `find_e33.py`, …). Der Job-Runner
kopiert `00_template/*` in **jeden** Punkt-Job — bei 192 Richtungen also rund
2500 überflüssige Dateien. Übrig bleibt `elastoplastic.py`.

### 5. Angepasste Werkzeuge

- `01_segmentation_topology_sweep.py` variiert jetzt `gaussian_sigma_voxels` /
  `smoothing_mode` statt der entfallenen Parameter. Die Variante
  `no_smoothing_010_equivalent` reproduziert das Verhalten von 010.
- `07_pygalmesh_parameter_sweep.py` schreibt in
  `sdf_pygalmesh_parameters.pygalmesh_parameters` statt in den entfernten
  Top-Level-Block.

---

## Ablauf

```
DICOM
 → 00_dicom_2_npy.py            Einlesen, 3D-Blockmittelung, Isotropie-Assertion
 → 01_segment_slice_wise.py     3D-Gauß (σ in Voxeln) + Otsu → uint8 {0,1}
 → 02_build3D_segmented_array.py  Stapeln, z/xy-Ausschnitt
 → 02a_rotate_pic_to_align_with_axis.py  Rotation + Randpuffer
 → 02b_build_subvolume_arrays.py  Bounding-Box, Teilvolumen, Dichte/Porosität
 → 02c_voxel_topology_cleanup.py  3D-Topologie-Audit (Cleanup optional)
 → 02d_axis_aligned_cuboid_crop.py  anisotrope Randschale 3/12/3 Voxel
 → 03_mesh_3D_array_pygalmesh.py  SDF → Gauß → Marching Cubes → trimesh → CGAL
 → 04_scale_and_translate_mesh.py  Skalierung/Translation in CT-Koordinaten
 → 05_tetgen_postprocess_mesh.py / 08 Qualität / 09 Topologie
 → make_mesh_dlfx_compatible.py   → dlfx_mesh.xdmf (P1-Tetraeder)
 → 00_template/elastoplastic.py   elasto-plastischer Solve  [entfällt bei MESH_ONLY=1]
 → collect_yield_surface_points.py / create_yield_surface_paraview.py
```

---

## Offene Punkte, die 013 *nicht* löst

Das sind Modellannahmen, keine Codefehler — bewusst unverändert gelassen:

1. **Randschale.** Die anisotrope Schale (3/12/3 Voxel) ersetzt die
   Originalstruktur am Rand und versteift das RVE richtungsabhängig. Bei
   Isotropieannahmen für die Fließfläche im Hinterkopf behalten.
2. **Ein Teilvolumen als RVE.** `xy_divisions = 1`, keine
   RVE-Größenkonvergenz.
3. **P1-Tetraeder bei ideal-plastischem J2-Fließen** (`hard = 0.0`) locken
   volumetrisch, sofern `alex/plasticity.py` keine gemischte oder F-bar-
   Formulierung verwendet. Ungeprüft.
4. **Rotationswinkel** sind visuell bestimmt, nicht aus einer Registrierung.
5. **Isolierte Komponenten** werden nur berichtet, nicht entfernt
   (`02c.cleanup.enabled = false`).

Ausführliche Herleitung: `../010-Yield-Surface-Generation/PIPELINE_ANNAHMEN_DICOM_TO_FEM.md`
und `Publications/02_WAAM_N1_Mikrostruktur/Bericht_Voxelgroesse_und_Phasenkonvention.md`.
