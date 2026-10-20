#!/usr/bin/env python3
"""setup_compression_jobs.py - 1D-Druckversuch (verschiebungsgesteuert) im Modell
der Studie 017 vorbereiten (20.10.2026).

Unterschied zur Fliessflaechen-Studie:
  * Randschale nur an den beiden Flaechen senkrecht zur Lastachse (Druckplatten),
    Seitenflaechen frei  -> eigenes Netz, dataset.id "<ds>_les_r4_druck<achse>".
  * Last: eps_mac = diag(-s, 0, 0) (Achse x) mit u = eps_mac . x auf den Platten,
    d.h. haftende Platten (u_quer = 0 auf den Platten), Seitenflaechen lastfrei.
  * Lauf bis total_time = Zieldehnung/0,25 (t == strain_scale, ||eps|| = 0,25 t),
    kein Abbruch am Fliessbeginn: alle Kriterien blocking=false (werden weiter
    protokolliert).
  * Auswertung aus averaged_history: sigma_nominal_reaction = R_axis / A_quer,
    eps_axial_platen = eps_mac_axis; Kontrolle sigma_avg_reduced_volume[axis][axis].

Erzeugt im Projektordner:
  config-<ds>-r4-druck<achse>-sigy<XXX>.json           je sig_y
  compression_jobs/<ds>_druck<achse>_sigy<XXX>/ys_druck_<achse>/
      config.json, parameters.txt, job_ys_druck_<achse>_CLUSTER.sh
  compression_jobs/submit_compression_druck<achse>_CLUSTER.sh   Prep + Ketten einreichen (je Achse eine Datei)

Aufruf (Mac oder Login-Node, im Projektordner):
  python3 setup_compression_jobs.py --dataset JM-25-71 --sig-y 75 180
  python3 setup_compression_jobs.py --dataset JM-25-71 --sig-y 75 100 180 --target-strain 0.025 --chain 3
"""
import argparse
import json
import os
from pathlib import Path

from write_yield_surface_parameters import parameter_text

FACES = ["x_min", "x_max", "y_min", "y_max", "z_min", "z_max"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="JM-25-71")
    ap.add_argument("--reduce", type=int, default=4)
    ap.add_argument("--sig-y", type=float, nargs="+", default=[75.0, 180.0])
    ap.add_argument("--axis", default="x", choices=["x", "y", "z"],
                    help="Lastachse; Druckplatten = die beiden Flaechen senkrecht dazu")
    ap.add_argument("--base-config", default=None,
                    help="Default: config-<dataset>-r<reduce>-sigy075.json (Produktions-Config der Studie)")
    ap.add_argument("--target-strain", type=float, default=0.025,
                    help="Enddehnung |eps_axial| (0.025 = 2,5 %%); total_time = Wert / max_mean_strain")
    ap.add_argument("--max-mean-strain", type=float, default=0.25)
    ap.add_argument("--snapshot-strain-interval", type=float, default=0.0025,
                    help="Feldausgabe (u, sigma, alpha) alle so viel Dehnung (0.0025 = 0,25 %%); 0 = aus")
    ap.add_argument("--chain", type=int, default=3, help="Glieder je Restart-Kette (24 h je Glied)")
    ap.add_argument("--job-account", default="p0023647")
    ap.add_argument("--job-ntasks", type=int, default=32)
    ap.add_argument("--job-mem-per-cpu", type=int, default=5600)
    ap.add_argument("--job-time", default="1440")
    ap.add_argument("--exclude-nodes", default="",
                    help="SBATCH --exclude, z.B. mpsd0138,mpsd0319 (leer = keiner)")
    ap.add_argument("--project-dir", default=None)
    a = ap.parse_args()

    project_dir = Path(a.project_dir).resolve() if a.project_dir else Path(__file__).resolve().parent
    tag = f"druck{a.axis}"
    base_name = a.base_config or f"config-{a.dataset}-r{a.reduce}-sigy075.json"
    base_path = Path(base_name) if os.path.isabs(base_name) else project_dir / base_name
    base = json.loads(base_path.read_text())

    old_id = base["dataset"]["id"]                      # z.B. JM-25-71_les_r4
    new_id = f"{old_id}_{tag}"                          # JM-25-71_les_r4_druckx
    assert old_id in json.dumps(base), old_id

    scratch_root = (os.environ.get("HPC_SCRATCH") or "").rstrip("/")
    jobs_root = project_dir / "compression_jobs"
    jobs_root.mkdir(exist_ok=True)
    total_time = a.target_strain / a.max_mean_strain
    submit = [
        "#!/usr/bin/env bash",
        "# erzeugt von setup_compression_jobs.py - 1D-Druckversuch Studie 017",
        "# Aufruf auf dem Login-Node nach dem Sync nach $HPC_SCRATCH:",
        "#   DRY_RUN=1 .../compression_jobs/submit_compression_CLUSTER.sh   # nur anzeigen",
        "#   .../compression_jobs/submit_compression_CLUSTER.sh",
        "set -euo pipefail",
        'P="$HPC_SCRATCH/pygalmesh/data/scripts/%s"' % project_dir.name,
        'DRY="${DRY_RUN:-0}"',
        'ACC="${JOB_ACCOUNT:-%s}"' % a.job_account,
        'sb() { if [[ "$DRY" == 1 ]]; then echo "[dry-run] sbatch $*" >&2; echo 000000; else sbatch --parsable "$@" | sed "s/;.*//" | grep -E "^[0-9]+$" | tail -n 1; fi; }',
        "",
    ]
    # --- Netzvorbereitung (einmal je Datensatz/Achse) -------------------------
    mesh_cfg_name = f"config-{a.dataset}-r{a.reduce}-{tag}-sigy{int(a.sig_y[0]):03d}.json"
    subvol = base["02b_build_subvolume_arrays"]["subvolume_output_folder"].replace(old_id, new_id)
    submit += [
        f"# 1) Netz mit Schale nur in {a.axis} ({new_id}); uebersprungen, wenn dlfx_mesh.xdmf schon da ist",
        f'SUBVOL="{subvol}"; SUBVOL="${{SUBVOL/#\\/data/$HPC_SCRATCH/pygalmesh/data}}"',
        'PREP=""',
        'if compgen -G "$SUBVOL/subvolume_x*_y*/dlfx_mesh.xdmf" > /dev/null; then echo "Netz vorhanden: $SUBVOL"; else',
        f'  PREP="$(sb -A "$ACC" --time="${{PREP_JOB_TIME:-120}}" -J prep-{a.dataset}-{tag} "$P/job_prepare_mesh_CLUSTER.sh" {mesh_cfg_name})"',
        '  echo "Netzvorbereitung: Job $PREP"',
        "fi",
        "",
    ]

    for sig in a.sig_y:
        sig_tag = f"{int(round(sig)):03d}"
        cfg = json.loads(json.dumps(base).replace(old_id, new_id))
        cfg["dataset"]["id"] = new_id
        cfg["binning"]["label"] = f"leS-r{a.reduce}-{tag}-sigy{sig_tag}"
        seal = cfg["02d_axis_aligned_cuboid_crop"]["boundary_seal"]
        th = {f: int(seal.get("thickness", 0) or 0) for f in FACES}
        for k, v in (seal.get("thicknesses") or {}).items():
            if k in "xyz":
                th[k + "_min"] = th[k + "_max"] = int(v)
            else:
                th[k] = int(v)
        for f in FACES:
            if not f.startswith(a.axis):
                th[f] = 0
        seal["thicknesses"] = th
        seal["comment"] = (f"1D-Druckversuch: Schale nur an {a.axis}_min/{a.axis}_max (Druckplatten), "
                           "Seitenflaechen frei; 0 = keine Schale (elastoplastic.py/make_mesh_dlfx_compatible "
                           "ueberspringen Flaechen mit Dicke 0).")
        ys = cfg["yield_surface"]
        ys["material_sets"]["std"]["sig_y"] = float(sig)
        ys["materials"] = ["std"]
        ys["loading_directions"] = [a.axis]
        eps = [0.0, 0.0, 0.0]
        eps["xyz".index(a.axis)] = -a.max_mean_strain
        ys["eps_mac_eigenvalues"] = eps
        ys["max_mean_strain"] = a.max_mean_strain
        ys["total_time"] = total_time
        ys["sample_id"] = f"ys_druck_{a.axis}"
        ys["sample_method"] = "uniaxial_compression_test"
        ys["sample_direction_unit"] = [-e / a.max_mean_strain for e in eps]
        ys["sample_radius"] = a.max_mean_strain
        for c in ys.get("criteria", []):
            c["blocking"] = False
        fo = ys.setdefault("field_output", {})
        fo["enabled"] = True
        fo["strain_scale_interval"] = (a.snapshot_strain_interval / a.max_mean_strain
                                       if a.snapshot_strain_interval > 0 else 0.0)
        fo["min_minutes_between_writes"] = 120.0
        ys.setdefault("history", []).append({
            "date": "2026-10-20",
            "change": (f"1D-Druckversuch {a.axis}: Schale nur {a.axis}-Platten, haftende Platten (u = eps.x), "
                       f"Seitenflaechen frei, sig_y = {sig:g}, total_time = {total_time:g} "
                       f"(|eps| = {a.target_strain:g}), Kriterien nicht blockierend, "
                       f"Snapshots alle {a.snapshot_strain_interval:g} Dehnung (setup_compression_jobs.py)"),
        })
        cfg_name = f"config-{a.dataset}-r{a.reduce}-{tag}-sigy{sig_tag}.json"
        (project_dir / cfg_name).write_text(json.dumps(cfg, indent=2) + "\n")

        combo = f"{a.dataset}_{tag}_sigy{sig_tag}"
        sample_id = ys["sample_id"]
        sdir = jobs_root / combo / sample_id
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / "config.json").write_text(json.dumps(cfg, indent=2) + "\n")
        (sdir / "parameters.txt").write_text(parameter_text(cfg, "std", a.axis))
        cfg_container = f"/data/scripts/{project_dir.name}/compression_jobs/{combo}/{sample_id}/config.json"
        job_name = f"{a.dataset}_s{sig_tag}-{tag}"
        hdr = [f"#SBATCH -J {job_name}", f"#SBATCH -A {a.job_account}", f"#SBATCH -t {a.job_time}",
               f"#SBATCH -n {a.job_ntasks}", "#SBATCH -N 1", f"#SBATCH --mem-per-cpu={a.job_mem_per_cpu}"]
        if scratch_root:
            log_dir = f"{scratch_root}/pygalmesh/data/scripts/{project_dir.name}/compression_jobs/{combo}/{sample_id}"
            hdr += [f"#SBATCH -e {log_dir}/%x.err.%j", f"#SBATCH -o {log_dir}/%x.out.%j"]
        if a.exclude_nodes:
            hdr.append(f"#SBATCH --exclude={a.exclude_nodes}")
        hdr.append("#SBATCH --mail-type=END")
        job_path = sdir / f"job_{sample_id}_CLUSTER.sh"
        job_path.write_text("#!/bin/bash\n\n" + "\n".join(hdr) + "\n\n"
                            f'SCRIPT_DIR="$HPC_SCRATCH/pygalmesh/data/scripts/{project_dir.name}"\n'
                            f'bash "$SCRIPT_DIR/job_yield_surface_point_CLUSTER.sh" "{cfg_container}"\n')
        job_path.chmod(0o755)

        rel = f"compression_jobs/{combo}/{sample_id}"
        submit += [
            f"# 2) {combo}: Kette aus {a.chain} Gliedern (Exit 3 = Zeitlimit -> naechstes Glied setzt fort)",
            f'J="$P/{rel}/job_{sample_id}_CLUSTER.sh"; L="$P/{rel}"',
            'DEP=(); [[ -n "$PREP" ]] && DEP=(--dependency="afterok:$PREP" --kill-on-invalid-dep=yes)',
            'PREV="$(sb -A "$ACC" "${DEP[@]}" --error="$L/%x.err.%j" --output="$L/%x.out.%j" "$J")"',
            f'echo "{combo}: Glied 1 = $PREV"',
            f"for i in $(seq 2 {a.chain}); do",
            '  D="afternotok:$PREV"; [[ -n "$PREP" ]] && D="afterok:$PREP,$D"',
            '  PREV="$(sb -A "$ACC" --dependency="$D" --kill-on-invalid-dep=yes --error="$L/%x.err.%j" --output="$L/%x.out.%j" "$J")"',
            f'  echo "{combo}: Glied $i = $PREV"',
            "done",
            "",
        ]
        print(f"{combo}: {cfg_name}, {rel}/  (total_time {total_time:g} -> |eps| {a.target_strain:g})")

    submit += ['echo "Status: squeue -u $USER   Logs: $P/compression_jobs/*/*/"']
    sp = jobs_root / f"submit_compression_{tag}_CLUSTER.sh"
    sp.write_text("\n".join(submit) + "\n")
    sp.chmod(0o755)
    print(f"Netz-Config der Vorbereitung: {mesh_cfg_name} (dataset.id {new_id})")
    print(f"Einreichen auf dem Cluster: {sp}")


if __name__ == "__main__":
    main()
