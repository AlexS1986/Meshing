#!/usr/bin/env python3
"""Fliessflaechenpunkte offline aus den Zeitschritt-Historien bestimmen (Studie 015).

Quelle je Punkt: `averaged_history` in restart_meta_*.json (Arbeitsordner) bzw. in
yield_run_*.json (00_results). Jeder Eintrag enthaelt u. a. strain_scale,
sigma_avg_reduced_volume (makroskopischer Spannungstensor), sig_vm_avg_reduced_volume,
alpha_avg_reduced_material_volume, yielded_fraction_reduced_material_volume,
eps_p_eq_macroscopic, eps_mac_eigenvalues_current.

Je Lauf werden bestimmt (lineare Interpolation zwischen den Schritten):
  * Fliesspunkt bei alpha_avg = ALPHA (Default 1e-3): Spannungstensor, sig_vm, Dehnung
  * zum Vergleich der Punkt bei yielded_fraction = YF (Default 2e-3, Kriterium der Vorstudie)
  * Tangente dSig_vm/dE relativ zur Anfangssteigung am alpha-Punkt und am Ende
  * Plateauspannung per Saettigungsfit sig(e) = s_inf*(1-exp(-e/e_c)) an sig_vm(e)
    (Fit ab 0,3 % Dehnung; e_c per Log-Raster, s_inf linear) plus Guete R^2
  * Status: reached_alpha, letzte Dehnung, Schritte, max. alpha

Ausgabe: CSV je Kombination (<out>/yield_points_<ds>_sigy<XXX>.csv) und Gesamt-CSV.
Aufruf (Login-Knoten, numpy reicht):
  python3 evaluate_yield_points_from_history.py [--root $S] [--alpha 1e-3] [--yf 2e-3] [--out $S/00_results/_packages/yield_points_20260906]
"""
import argparse, csv, glob, json, math, os, re, sys
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--root", default=os.path.expandvars("$HPC_SCRATCH/pygalmesh/data/scripts/015-Yield-Surface-Batch-leS"))
ap.add_argument("--alpha", type=float, default=1e-3)
ap.add_argument("--yf", type=float, default=2e-3)
ap.add_argument("--tag", default="r4")
ap.add_argument("--out", default=None)
a = ap.parse_args()
out = a.out or os.path.join(a.root, "00_results", "_packages", f"yield_points_{a.tag}")
os.makedirs(out, exist_ok=True)

def flat(x):
    return np.array(x, dtype=float).ravel()

def load_history(path):
    d = json.load(open(path))
    h = d.get("averaged_history") or []
    return d, h

def crossing(h, key, thr):
    """Index i und Gewicht w, so dass Wert(key) bei i-1 < thr <= i; None wenn nie erreicht."""
    prev = None
    for i, s in enumerate(h):
        v = s.get(key)
        if v is None: continue
        if v >= thr:
            if prev is None or i == 0: return i, 0.0
            v0 = h[i-1].get(key, 0.0)
            w = (thr - v0) / (v - v0) if v != v0 else 1.0
            return i, min(max(w, 0.0), 1.0)
        prev = v
    return None

def interp(h, i, w, key):
    if i == 0 or w == 0.0: return flat(h[i][key])
    return (1 - w) * flat(h[i-1][key]) + w * flat(h[i][key])

def tangent_ratio(e, s, at, win=0.004):
    m0 = e < 1e-3
    if m0.sum() < 3: return float("nan"), float("nan")
    E0 = np.polyfit(e[m0], s[m0], 1)[0]
    wsel = (e >= at - win) & (e <= at)
    if wsel.sum() < 4 or E0 <= 0: return E0, float("nan")
    return E0, np.polyfit(e[wsel], s[wsel], 1)[0] / E0

def plateau_fit(e, s, emin=3e-3):
    sel = e >= emin
    if sel.sum() < 8: return float("nan"), float("nan"), float("nan")
    ee, ss = e[sel], s[sel]
    best = None
    for ec in np.logspace(-3.5, -1, 60):
        f = 1 - np.exp(-ee / ec)
        sinf = float(np.dot(f, ss) / np.dot(f, f))
        r = ss - sinf * f
        sse = float(np.dot(r, r))
        if best is None or sse < best[0]: best = (sse, sinf, ec)
    sse, sinf, ec = best
    r2 = 1 - sse / float(np.sum((ss - ss.mean()) ** 2)) if ss.size > 1 else float("nan")
    return sinf, ec, r2

def sample_info(path):
    """dataset, sigy, sample_id, direction eigenvalues aus dem Pfad."""
    p = path.split("/")
    run_dir = [x for x in p if x.startswith("ys_")]
    smp = run_dir[0] if run_dir else "?"
    m = re.search(r"(JM-25-\d+)", path); ds = m.group(1) if m else "?"
    m = re.search(r"sigy(\d+)", path); sigy = m.group(1) if m else "?"
    ev = re.findall(r"e[123]_([mp])(\d)p(\d+)", smp)
    eig = [(-1 if s == "m" else 1) * float(f"{a}.{b}") for s, a, b in ev]
    return ds, sigy, smp, eig

rows = []
seen = {}
patterns = [os.path.join(a.root, "yield_surface_runs", f"*_les_{a.tag}", "*", "ys_*", "subvolume_x0_y0", "restart_meta_*.json"),
            os.path.join(a.root, "00_results", f"*_les_{a.tag}", "*", "yield_surface", "*", "*", "*", "yield_run_*.json")]
for pat in patterns:
    for path in sorted(glob.glob(pat)):
        if "_failed" in path: continue
        ds, sigy, smp, eig = sample_info(path)
        key = (ds, sigy, smp[:6])
        try:
            d, h = load_history(path)
        except Exception as ex:
            print("unlesbar:", path, ex); continue
        if not h: continue
        # laengere Historie gewinnt (restart_meta vs. Ergebnis-JSON)
        if key in seen and seen[key][0] >= len(h): continue
        if key in seen:
            rows[:] = [r for r in rows if not (r["dataset"], r["sigy"], r["sample"]) == key]
        seen[key] = (len(h), path)
        e = np.array([s["strain_scale"] for s in h]); sv = np.array([s["sig_vm_avg_reduced_volume"] for s in h])
        row = dict(dataset=ds, sigy=sigy, sample=smp[:6], run=smp, e1=eig[0] if len(eig) > 0 else "", e2=eig[1] if len(eig) > 1 else "", e3=eig[2] if len(eig) > 2 else "",
                   steps=len(h), strain_last=e[-1], sig_vm_last=sv[-1],
                   alpha_last=h[-1]["alpha_avg_reduced_material_volume"], yf_last=h[-1]["yielded_fraction_reduced_material_volume"],
                   eps_p_mac_last=h[-1].get("eps_p_eq_macroscopic", ""), source=os.path.relpath(path, a.root))
        E0, tr_end = tangent_ratio(e, sv, e[-1]); row["E0_vm"] = E0; row["tangent_ratio_last"] = tr_end
        sinf, ec, r2 = plateau_fit(e, sv); row["plateau_sig_vm_fit"] = sinf; row["plateau_e_c"] = ec; row["plateau_fit_r2"] = r2
        for label, k, thr in (("alpha", "alpha_avg_reduced_material_volume", a.alpha), ("yf", "yielded_fraction_reduced_material_volume", a.yf)):
            c = crossing(h, k, thr)
            row[f"reached_{label}"] = c is not None
            if c is None:
                for name in ("strain", "sig_vm", "tangent_ratio", "eps_p_mac", "alpha", "yf"): row[f"{label}_{name}"] = ""
                for j in range(9): row[f"{label}_sig{j}"] = ""
                for j in range(3): row[f"{label}_eps_eig{j}"] = ""
                continue
            i, w = c
            st = interp(h, i, w, "strain_scale")[0]; sig = interp(h, i, w, "sigma_avg_reduced_volume")
            row[f"{label}_strain"] = st; row[f"{label}_sig_vm"] = interp(h, i, w, "sig_vm_avg_reduced_volume")[0]
            row[f"{label}_tangent_ratio"] = tangent_ratio(e, sv, st)[1]
            row[f"{label}_eps_p_mac"] = interp(h, i, w, "eps_p_eq_macroscopic")[0] if "eps_p_eq_macroscopic" in h[i] else ""
            row[f"{label}_alpha"] = interp(h, i, w, "alpha_avg_reduced_material_volume")[0]
            row[f"{label}_yf"] = interp(h, i, w, "yielded_fraction_reduced_material_volume")[0]
            for j in range(9): row[f"{label}_sig{j}"] = sig[j] if j < sig.size else ""
            ev = interp(h, i, w, "eps_mac_eigenvalues_current") if "eps_mac_eigenvalues_current" in h[i] else np.array([])
            for j in range(3): row[f"{label}_eps_eig{j}"] = ev[j] if j < ev.size else ""
        rows.append(row)

if not rows:
    print("keine Historien gefunden"); sys.exit(1)
cols = list(rows[0].keys())
def write(path, rs):
    with open(path, "w", newline="") as fh:
        wtr = csv.DictWriter(fh, fieldnames=cols); wtr.writeheader(); wtr.writerows(rs)
write(os.path.join(out, f"yield_points_{a.tag}_all.csv"), rows)
combos = sorted({(r["dataset"], r["sigy"]) for r in rows})
print(f"{len(rows)} Laeufe ausgewertet -> {out}")
print(f"{'KOMBINATION':20s} {'LAEUFE':>6s} {'alpha>=%g' % a.alpha:>10s} {'yf>=%g' % a.yf:>9s} {'Plateau-Fit R2>0.99':>19s} {'sig_vm@alpha median':>20s} {'Plateau median':>15s}")
for ds, sy in combos:
    rs = [r for r in rows if r["dataset"] == ds and r["sigy"] == sy]
    write(os.path.join(out, f"yield_points_{ds}_sigy{sy}.csv"), rs)
    na = sum(r["reached_alpha"] for r in rs); ny = sum(r["reached_yf"] for r in rs)
    good = sum(1 for r in rs if isinstance(r["plateau_fit_r2"], float) and r["plateau_fit_r2"] > 0.99)
    sa = sorted(r["alpha_sig_vm"] for r in rs if r["reached_alpha"]); sp = sorted(r["plateau_sig_vm_fit"] for r in rs if isinstance(r["plateau_sig_vm_fit"], float) and not math.isnan(r["plateau_sig_vm_fit"]))
    med = lambda v: f"{v[len(v)//2]:.2f}" if v else "-"
    print(f"{ds+'_sigy'+sy:20s} {len(rs):6d} {na:10d} {ny:9d} {good:19d} {med(sa):>20s} {med(sp):>15s}")
