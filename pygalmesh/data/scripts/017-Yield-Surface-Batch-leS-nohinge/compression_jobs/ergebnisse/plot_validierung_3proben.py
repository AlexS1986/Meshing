#!/usr/bin/env python3
"""Validierung sigma_y 100 + H 2000 (1D-Druck, haftende Platten) an drei Proben gegen die Versuche (Sven, MTS Fusspunkt-korrigiert).
Aufruf aus compression_jobs/ergebnisse/:  python3 plot_validierung_3proben.py
Schreibt validierung_3proben.png und validierung_3proben.csv (23.10.2026). Fehlende Laufdateien werden uebersprungen."""
import json, os, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt

AUSW = os.path.expanduser("~/Work/Hypo/Hypo/Publications/03_Folgepaper_Homogenisierung_elasto-plastischen_Eigenschaften /"
                          "AlSi10MgSchaeumeDruckversucheelasto-plastisch/Auswertung_Claude_20261020")
# Modell-CSV (aus evaluate_compression_run.py) je Probe; Dichte = reduced_volume_material / reduced_volume_box des 1D-Netzes
RUNS = {
    "71": [("y + H 2000", "drucky_sigy100h2000/elastoplastic_std_y_averages.txt.csv", "-"),
           ("x + H 2000", "druckx_sigy100h2000/yield_averages_std_x.json.csv", "--")],
    "83": [("y + H 2000", "JM-25-83_drucky_sigy100h2000/elastoplastic_std_y_averages.txt.csv", "-")],
    "88": [("y + H 2000", "JM-25-88_drucky_sigy100h2000/elastoplastic_std_y_averages.txt.csv", "-")],
}
RHO = {"71": "ρ 1D 0,189", "83": "ρ 1D 0,179", "88": "ρ 1D 0,206"}
EPS = (0.005, 0.01, 0.015, 0.02, 0.0248)


def rp02(e, s, E):
    o = s - E * (e - 0.002)
    k = np.nonzero(o <= 0)[0]
    if not len(k) or k[0] == 0:
        return float("nan")
    i, j = k[0], k[0] - 1
    t = o[j] / (o[j] - o[i])
    return float(s[j] + t * (s[i] - s[j]))


kw = {d["probe"][-2:]: d for d in json.load(open(os.path.join(AUSW, "kennwerte_druckversuche.json")))}
fig, axs = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
rows = [["probe", "lauf", "groesse", "modell_MPa", "versuch_MPa", "modell_zu_versuch"]]
for ax, p in zip(axs, ("71", "83", "88")):
    x = np.loadtxt(os.path.join(AUSW, f"JM-25-{p}_sigma_eps_MTS_korrigiert.csv"), delimiter=",", skiprows=1)
    m = x[:, 0] <= 0.06
    ax.plot(100 * x[m, 0], x[m, 1], "k-", lw=1.5, label="Versuch (MTS korr.)")
    k = kw[p]
    E_exp = k["dic_E_10_40_MPa"]
    for lab, f, ls in RUNS[p]:
        if not os.path.exists(f):
            continue
        c = np.genfromtxt(f, delimiter=",", names=True)
        e, s = c["eps_axial"], c["sigma_volume_avg_MPa"]
        ax.plot(100 * e, s, "C3", ls=ls, label=f"FEM {lab}")
        for ee in EPS:
            if e.max() >= ee - 1e-4:
                sm, sv = np.interp(ee, e, s), np.interp(ee, x[:, 0], x[:, 1])
                rows.append([p, lab, f"sigma_{ee*100:g}pct", f"{sm:.3f}", f"{sv:.3f}", f"{sm/sv:.3f}"])
        r = rp02(e, s, E_exp)
        rows.append([p, lab, f"Rp02_mit_E_exp_{E_exp:.0f}", f"{r:.3f}", f"{k['dic_Rp02_MPa']:.3f}", f"{r/k['dic_Rp02_MPa']:.3f}"])
    ax.set_title(f"JM-25-{p} ({RHO[p]}; Versuch Rp0,2 {k['dic_Rp02_MPa']:.1f}, σ_max {k['sig_max_MPa']:.1f})", fontsize=9)
    ax.set_xlim(0, 6); ax.set_ylim(0, 18); ax.grid(alpha=.3); ax.set_xlabel("Stauchung [%]")
    ax.legend(fontsize=7, loc="lower right")
axs[0].set_ylabel("Nennspannung [MPa]")
fig.suptitle("1D-Druck, σ_y 100 MPa + H 2000 MPa (haftende Platten) gegen Versuch", fontsize=10)
fig.tight_layout(); fig.savefig("validierung_3proben.png", dpi=150)
with open("validierung_3proben.csv", "w") as h:
    h.write("\n".join(",".join(r) for r in rows) + "\n")
for r in rows:
    print("  ".join(r))
print("validierung_3proben.png, validierung_3proben.csv")
