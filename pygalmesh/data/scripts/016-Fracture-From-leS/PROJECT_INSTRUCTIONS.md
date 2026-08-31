# Projektanweisungen für ein separates Claude-Projekt „Bruch aus .leS-Daten"

Ein Claude-Projekt lässt sich von hier aus nicht selbst anlegen — das geht nur
in der App. Diese Datei enthält alles, was dafür gebraucht wird.

---

## Schritt 1 — Projekt anlegen

In der Claude-App ein neues Projekt erstellen, Name z.B.

> **Bruch aus .leS-Daten (pygalmesh 016)**

## Schritt 2 — Ordner verbinden

Diesen Ordner als Projektordner verbinden:

```text
~/Work/Hypo/Hypo/Simulation/Meshing/pygalmesh/data/scripts
```

(Nicht nur `016-Fracture-From-leS` — die Vorgänger 011, 012, 014 und 015 müssen
mitlesbar sein, sonst fehlt der Kontext, aus dem 016 abgeleitet ist.)

## Schritt 3 — Projektanweisungen eintragen

Den folgenden Block in das Feld „Projektanweisungen" kopieren:

---

```text
Kontext: Phasenfeld-Bruchsimulationen an segmentierten Aluminiumschaum-
Voxeldaten (.leS-Format), gerechnet mit DOLFINx auf einem SLURM-Cluster.
Arbeitsordner ist data/scripts/016-Fracture-From-leS im verbundenen
scripts-Ordner.

Vor jeder Aufgabe lesen, in dieser Reihenfolge:
  1. 016-Fracture-From-leS/CLAUDE.md          — Konventionen, Entscheidungen
  2. 016-Fracture-From-leS/CLAUDE_PROJECT_NOTES.md — Protokoll, offene Punkte
  3. 016-Fracture-From-leS/LES_FRACTURE_PIPELINE.md — Bedienung
  4. 016-Fracture-From-leS/FILES.md           — welche Datei was tut
Bei Fragen zur Voxel-zu-FEM-Kette zusätzlich
     016-Fracture-From-leS/PIPELINE_ANNAHMEN_DICOM_TO_FEM.md.
Die Vorgängerprojekte 011, 012, 014 und 015 liegen im selben scripts-Ordner
und sind die Quelle für alles, was hier unverändert übernommen wurde.

Arbeitsweise:
- Alles, was entschieden oder gelernt wird, wird in einer .md-Datei
  dokumentiert: projektübergreifend in CLAUDE.md, sessionbezogen in
  CLAUDE_PROJECT_NOTES.md. Das ist die wichtigste Regel.
- Skripte werden vorbereitet, nicht blind ausgeführt. Vernetzung und FE-Läufe
  startet der Nutzer selbst auf dem Cluster. Ausnahme: kleine
  Verifikationsläufe auf Teilausschnitten.
- Configs werden aus einer bestehenden, validierten Config abgeleitet
  (create_fracture_config.sh / create_fracture_config.py), nie von Hand
  geschrieben. Basis ist config-A01-les-base.json.
- In JSON-Configs steht immer der Container-Pfad (/data/...), nie ein
  unaufgelöstes $HPC_SCRATCH.
- Antworten auf Deutsch.

Harte Fakten, die nie verletzt werden dürfen:
- Phasenkonvention: In der .leS-Quelldatei ist 1 = Material, 0 = void. Die
  Pipeline arbeitet umgekehrt (1 = Pore, 0 = Aluminium); A01_les_2_npy.py
  invertiert, Schritt 03 invertiert erneut. Die Randschale aus 02d (Wert 0)
  ist genau darauf abgestimmt.
- Arrays sind uint8 der Form (x, y, z); z ist die Slice-Achse.
- Der Archivpfad der Netze wird aus 03_mesh_3D_array.specimen_name gebildet,
  nicht aus 01_segment_slice_wise.specimen_name — letzteres ist über die
  Auflösungsstufen hinweg gleich und würde sie sich gegenseitig überschreiben
  lassen.
- srun-Steps setzen keine eigenen --time/--mem-per-cpu-Werte, sondern erben
  sie vom Job.
- sdf_pygalmesh_parameters.pad_width = 3, keep_largest_component = true.
- Beim Phasenfeld ist die bindende Auflösungsgrenze nicht die Voxelgröße,
  sondern epsilon = (y_max - y_min) / eps_factor_param. Mindestens 2, besser
  4 Elemente je epsilon.
- eps_factor_param nie <= 8: die Surfing-BC wirkt nur bei |y - y_mid| >= 4*epsilon
  (Anteil der Höhe 1 - 8/eps_factor). Grobe Elemente über LES_BAR_Y_MM auffangen.
- Randschale extern (02f, 0,4 mm), 02d-Seal aus; 04_scale_and_translate_mesh_mod.py
  ist die 011-Version und braucht --npy.
```

---

## Schritt 4 — Wissensstand hochladen

`WISSENSSTAND_011_012_014_015.md` (liegt in diesem Ordner) als Projektdatei
hochladen. Damit kennt das neue Projekt die Vorgeschichte auch dann, wenn der
Ordner gerade nicht verbunden ist.

## Schritt 5 — Erster Prompt zum Prüfen

> Lies CLAUDE.md und CLAUDE_PROJECT_NOTES.md in 016-Fracture-From-leS und fasse
> mir in fünf Sätzen zusammen, was der aktuelle Stand ist und was als nächstes
> zu tun wäre.

Wenn die Antwort den Datensatz JM-25-77, `eps_factor = 20` mit dem 4·epsilon-BC-Band
und die externe 0,4-mm-Schale nennt, ist das Projekt richtig aufgesetzt.
