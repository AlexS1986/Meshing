#!/usr/bin/env python3
"""Ueberlagert die 1D-Druck-Kurven (017, JM-25-71) mit dem Versuch JM-25-71 (MTS, Fusspunkt-korrigiert, Sven).
Aufruf aus compression_jobs/ergebnisse/:  python3 plot_druck_vs_versuch.py
Versuchsdatei: Publikationsordner .../Auswertung_Claude_20261020/JM-25-71_sigma_eps_MTS_korrigiert.csv (21.10.2026)."""
import os, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
EXP = os.path.expanduser("~/Work/Hypo/Hypo/Publications/03_Folgepaper_Homogenisierung_elasto-plastischen_Eigenschaften /"
                         "AlSi10MgSchaeumeDruckversucheelasto-plastisch/Auswertung_Claude_20261020/JM-25-71_sigma_eps_MTS_korrigiert.csv")
RUNS = [("y, σ_y 75", "drucky_sigy075/elastoplastic_std_y_averages.txt.csv", "C0", "-"),
        ("y, σ_y 100", "drucky_sigy100/elastoplastic_std_y_averages.txt.csv", "C1", "-"),
        ("y, σ_y 180", "drucky_sigy180/elastoplastic_std_y_averages.txt.csv", "C2", "-"),
        ("x, σ_y 180", "druckx_sigy180/yield_averages_std_x.json.csv", "C2", "--")]
KUBC = {75: 6.40, 100: 8.41, 180: 14.5}
fig, ax = plt.subplots(figsize=(7, 4.5))
if os.path.exists(EXP):
    e = np.loadtxt(EXP, delimiter=",", skiprows=1)
    m = e[:, 0] <= 0.06
    ax.plot(100 * e[m, 0], e[m, 1], "k-", lw=1.5, label="Versuch JM-25-71 (MTS, Fußpunkt-korr.)")
for lab, f, c, ls in RUNS:
    if os.path.exists(f):
        d = np.genfromtxt(f, delimiter=",", names=True)
        ax.plot(100 * d["eps_axial"], d["sigma_volume_avg_MPa"], color=c, ls=ls, label=f"1D-FEM {lab}")
for s, v in KUBC.items():
    ax.axhline(v, color="0.5", lw=0.7, ls=":"); ax.text(5.9, v + 0.15, f"KUBC σ̄⊥ ({s})", ha="right", fontsize=7, color="0.4")
ax.axhline(4.5, color="C0", lw=0.7, ls=":"); ax.text(5.9, 4.65, "A01-FFT Plateau (75)", ha="right", fontsize=7, color="C0")
ax.set_xlim(0, 6); ax.set_ylim(0, 16); ax.set_xlabel("Stauchung [%]"); ax.set_ylabel("Nennspannung [MPa]")
ax.grid(alpha=.3); ax.legend(fontsize=7, loc="lower right"); fig.tight_layout()
fig.savefig("druck_71_vs_versuch.png", dpi=160); print("druck_71_vs_versuch.png")
