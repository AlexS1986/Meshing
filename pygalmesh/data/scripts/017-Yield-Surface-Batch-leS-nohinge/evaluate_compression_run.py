#!/usr/bin/env python3
"""evaluate_compression_run.py - Spannungs-Dehnungs-Kurve und Kennwerte eines 1D-Druck-
laufs (setup_compression_jobs.py) aus yield_averages_std_x.json (20.10.2026).

  python3 evaluate_compression_run.py <lauf>/subvolume_x0_y0/yield_averages_std_x.json [weitere ...] [--plot kurve.png]

Spannung  = -sigma_nominal_reaction (R_axis / Querschnitt der Box), Kontrolle: -sigma_avg_reduced_volume[a][a]
Dehnung   = -eps_axial_platen (Plattenweg / Laenge, technische Stauchung)
E         = Sekante/Regression im Belastungsast zwischen 10 % und 40 % der Maximalspannung (wie Sven)
Rp0,2     = Schnitt der Kurve mit der um 0,2 % versetzten E-Geraden
Ausgabe: Kennwerte je Datei auf stdout, CSV (<json>.csv) mit allen Schritten.
"""
import argparse, csv, json, os, sys
import numpy as np


def load_history(path):
    with open(path) as h:
        d = json.load(h)
    if isinstance(d, dict):
        d = d.get("averaged_history") or d.get("history") or d
    return [s for s in d if isinstance(s, dict) and "eps_axial_platen" in s]


def kennwerte(eps, sig, sig_box):
    out = {}
    smax = sig.max(); imax = int(sig.argmax())
    out["sigma_max_MPa"] = float(smax); out["eps_at_sigma_max"] = float(eps[imax])
    m = (sig >= 0.1 * smax) & (sig <= 0.4 * smax) & (np.arange(len(sig)) <= imax)
    if m.sum() >= 2:
        E = float(np.polyfit(eps[m], sig[m], 1)[0])
    else:
        E = float(sig[1] / eps[1]) if len(sig) > 1 and eps[1] > 0 else float("nan")
    out["E_10_40_MPa"] = E
    # Rp0,2: erste Stelle, an der sig < E*(eps-0.002)
    off = sig - E * (eps - 0.002)
    k = np.nonzero(off <= 0.0)[0]
    if len(k):
        i = k[0]; j = max(i - 1, 0)
        # lineare Interpolation zwischen j und i
        t = off[j] / (off[j] - off[i]) if off[j] != off[i] else 0.0
        out["Rp0_2_MPa"] = float(sig[j] + t * (sig[i] - sig[j]))
        out["eps_at_Rp0_2"] = float(eps[j] + t * (eps[i] - eps[j]))
    else:
        out["Rp0_2_MPa"] = float("nan")
    for e in (0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.02, 0.025):
        out[f"sigma_at_{e*100:g}pct_MPa"] = float(np.interp(e, eps, sig)) if eps.max() >= e else float("nan")
    out["eps_max_reached"] = float(eps.max())
    out["max_rel_diff_reaction_vs_volume_avg"] = float(np.nanmax(np.abs(sig_box - sig) / np.maximum(sig, 1e-9)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--plot", default=None, help="PNG-Datei; braucht matplotlib")
    a = ap.parse_args()
    curves = []
    for f in a.files:
        hist = load_history(f)
        if not hist:
            print(f"{f}: keine Historie mit eps_axial_platen", file=sys.stderr); continue
        # Achse aus eps_mac_eigenvalues_current
        ax = int(np.argmax(np.abs(hist[-1]["eps_mac_eigenvalues_current"])))
        eps = np.array([-s["eps_axial_platen"] for s in hist])
        sig = np.array([-s["sigma_nominal_reaction"] for s in hist])
        sig_box = np.array([-s["sigma_avg_reduced_volume"][ax][ax] for s in hist])
        quer = np.array([[abs(s["sigma_avg_reduced_volume"][i][i]) for i in range(3) if i != ax] for s in hist])
        order = np.argsort(eps); eps, sig, sig_box, quer = eps[order], sig[order], sig_box[order], quer[order]
        kw = kennwerte(eps, sig, sig_box)
        kw["max_quer_zu_axial"] = float(np.max(quer.max(axis=1) / np.maximum(sig, 1e-9)))
        kw["alpha_avg_material_end"] = float(hist[-1].get("alpha_avg_reduced_material_volume", float("nan")))
        print(f"\n== {f}")
        for k, v in kw.items():
            print(f"  {k:40s} {v:.4g}")
        csv_path = f + ".csv"
        with open(csv_path, "w", newline="") as h:
            w = csv.writer(h); w.writerow(["eps_axial", "sigma_reaction_MPa", "sigma_volume_avg_MPa", "sigma_quer_max_MPa", "alpha_avg_material"])
            for i in range(len(eps)):
                w.writerow([eps[i], sig[i], sig_box[i], quer[i].max(), hist[order[i]].get("alpha_avg_reduced_material_volume", "")])
        print(f"  CSV: {csv_path}")
        curves.append((os.path.basename(os.path.dirname(os.path.dirname(f))) or f, eps, sig, kw))
    if a.plot and curves:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, axp = plt.subplots(figsize=(6, 4))
        for name, eps, sig, kw in curves:
            axp.plot(eps * 100, sig, label=f"{name}: E {kw['E_10_40_MPa']:.0f} MPa, Rp0,2 {kw['Rp0_2_MPa']:.2f} MPa")
        axp.set_xlabel("Stauchung [%]"); axp.set_ylabel("Nennspannung [MPa]"); axp.grid(alpha=.3); axp.legend(fontsize=8)
        fig.tight_layout(); fig.savefig(a.plot, dpi=150); print(f"Plot: {a.plot}")


if __name__ == "__main__":
    main()
