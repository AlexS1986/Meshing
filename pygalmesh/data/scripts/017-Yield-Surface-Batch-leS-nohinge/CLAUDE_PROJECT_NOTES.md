# CLAUDE_PROJECT_NOTES.md — 017-Yield-Surface-Batch-leS-nohinge

Angelegt 08.09.2026 als Kopie von `015-Yield-Surface-Batch-leS` (Skripte, Configs,
`00_template`, Doku; keine Daten). Anlass: alle r4-Netze in 015 enthielten
87-253 "Scharnierteile" (Zellgruppen, die mit dem Rest nur Kanten/Knoten teilen),
Ursache der Newton-Nichtkonvergenz am Fliessbeginn in r2 und r4
(Publikationsordner `CLAUDE.md` §22). Hier: Netzvorbereitung komplett neu mit
Scharnierfilter im Konverter (`make_mesh_dlfx_compatible_cluster.py`) und
Pruefung `mesh_hinge_check.py` in `run_prepare_mesh_CLUSTER.sh`; alle 768 Punkte
frisch (H = 70, alpha_avg 1e-3 einziges Abbruchkriterium, 32 Tasks, 1440 min).
015 bleibt als Archiv unveraendert. Vorgeschichte bis 08.09.:
`CLAUDE_PROJECT_NOTES_015_bis_20260908.md`.

## Session 08.09.2026 — Anlage
