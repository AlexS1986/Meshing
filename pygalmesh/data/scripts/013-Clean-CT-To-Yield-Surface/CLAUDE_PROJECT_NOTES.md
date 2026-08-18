# Projekt-Notizen: 013-Clean-CT-To-Yield-Surface

Diese Datei dokumentiert, was hier entschieden und gebaut wurde, damit es in
künftigen Sessions wiedergefunden wird.

## Wo liegt der Code

Projekt-Root: `~/Work/Hypo/Hypo/Simulation` (Container-Bind:
`Meshing/pygalmesh/data` → `/data`).

- **Dieses Projekt:** `Meshing/pygalmesh/data/scripts/013-Clean-CT-To-Yield-Surface/`
- Vorgänger: `010-Yield-Surface-Generation/` (bleibt unverändert bestehen)
- DolfinX-Module: `dolfinx_alex/shared/utils/alex/` (`plasticity.py`,
  `homogenization.py`, `boundaryconditions.py`, `materials.py`,
  `postprocessing.py`, `linearelastic.py`)
- CT-Rohdaten: `Meshing/pygalmesh/data/resources/`
- Analyse der Altpipeline:
  `010-Yield-Surface-Generation/PIPELINE_ANNAHMEN_DICOM_TO_FEM.md`
- Bericht fürs Paper:
  `Publications/02_WAAM_N1_Mikrostruktur/Bericht_Voxelgroesse_und_Phasenkonvention.md`
  (auch als PDF)

## Entscheidungen dieser Session (2026-08-07)

Vom Nutzer vorgegeben:

1. **Umfang:** Aufräumen + ungenutzte Backends entfernen. Skriptstruktur und
   Nummerierung bleiben erkennbar (kein Neuschnitt).
2. **Glättung:** 3D-Gauß vor der Segmentierung, σ **in Voxeln**, Default 1.0.
   SDF-σ bleibt 1.0.
3. **Phasen:** *„Es muss sichergestellt werden, dass die Bibliotheken die zu
   vernetzenden Bereiche weiterhin mit exakt derselben 0/1-Bezeichnung bekommen
   wie vorher."* → Die numerische Konvention wurde **nicht** angefasst. Nur
   Benennung, Reports und Metadaten wurden korrigiert. `verify_pipeline.py`
   Prüfung A beweist die Bitgleichheit der Maske.
4. **Inhalt:** komplette Kette, mit `MESH_ONLY=1` als Option für reine
   Netzerzeugung.

Daraus abgeleitet:

- Neue Config-Felder: `smoothing_mode`, `gaussian_sigma_voxels`,
  `threshold_scope`, `meshed_phase_array_value`.
- Entfallene Config-Felder: `gaussian_filter_sigma_factor`,
  `gaussian_sigma_pixels`, `median_filter_size`, `remove_small_*`,
  `binary_opening_radius`, `binary_closing_radius`, `save_visualizations`,
  `specimen_name`, `smoothing_sigma_factor`, `segmentation_algorithm`,
  `z_slice`, `scale_factor`, `meshing_method`, `nanomesh_parameters`,
  `sdf_gmsh_parameters`, Top-Level `pygalmesh_parameters`,
  `06_gmsh_postprocess`, die vier auf 0 stehenden CGAL-Schranken,
  die `surface_decimation_*`-Felder (Code-Defaults sind identisch).
- 3D-Morphologie gehört nach `02c` (dort sieht sie echte Komponenten), nicht
  schichtweise nach `01`.

## Verifikationsstand

`python3 verify_pipeline.py --npy <volume.npy>` — 5/5 bestanden:

- **A** Maske identisch zu 010 auf 20 Zufallsvolumen **und** auf
  `011-.../subvolume_x52_y74/volume.npy`; nicht-binäre Eingabe wird abgewiesen.
- **B** 010er σ = 0.1339 mm ändert die Daten nachweislich nicht;
  σ = 1.0 Voxel ergibt mittleres |Δ| = 0.213.
- **C** Streaming-3D-Gauß == `scipy.ndimage.gaussian_filter` (max. 6e-08).
- **D** `relative_density` ist wieder der Feststoffanteil.
- **E** Reales Teilvolumen: Feststoffanteil **0.4068**, Porosität 0.5932.
  (010 hatte diese beiden Zahlen in den Metadaten vertauscht.)

Zusätzlich: `01_segment_slice_wise.py` wurde an synthetischen Schaumdaten
end-to-end durchlaufen (24 Schichten, Metadaten korrekt geschrieben).

## Noch nicht getan

- Kein Lauf auf den echten CT-Daten — Container mit `pygalmesh` / DolfinX war
  in dieser Session nicht verfügbar. Erster Produktivlauf sollte mit
  `MESH_ONLY=1` starten und die Reports `*.quality.txt`, `*.topology.txt`,
  `volume_topology.txt` prüfen.
- σ = 1.0 Voxel ist ein Vorschlag, kein begründeter Wert. Mit
  `01_segmentation_topology_sweep.py` gegen relative Dichte und
  Komponentenzahl absichern, bevor die Zahl ins Paper geht.
- Cluster-Skripte (`job_mesh_CLUSTER.sh`, `job_yield_surface_point_CLUSTER.sh`,
  `sync_to_scratch_CLUSTER.sh`) wurden nur pfadangepasst und mit `bash -n`
  geprüft, nicht auf dem Cluster ausgeführt. SLURM-Header (`-A p0023647`,
  Partition, Constraints) sind aus 010 übernommen.
- `threshold_scope: "volume"` (globales Otsu) ist implementiert, aber Default
  bleibt `slice` wie in 010.
