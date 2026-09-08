"""Restart-Unterstuetzung fuer elastoplastic.py (Fliessflaechen-Punktlaeufe).

Idee: elastoplastic.py schreibt ohnehin in jedem erfolgreichen Zeitschritt
u (P1-Vektor), sigma (DP0-Tensor) und alpha (DP0-Skalar) in die XDMF/HDF5-
Ausgabe. Zusammen mit dem Newton-Logfile (t, dt) genuegt das, um einen durch
das SLURM-Zeitlimit abgebrochenen Lauf exakt fortzusetzen:

    e_p = dev(eps(u)) - dev(sigma) / (2 mu)        (J2, small strain)
    alpha aus der DP0-Ausgabe (deg_quad = 1: ein Gausspunkt je Zelle,
    DP0-Interpolation ist dort verlustfrei)

Zusaetzlich schreibt elastoplastic.py seit der Restart-Erweiterung je
erfolgreichem Zeitschritt eine kleine Datei restart_meta_<base>.json
(t, dt, yield_states, averaged_history), damit beim Fortsetzen auch die
Kriterien-Historie erhalten bleibt. Alte Laeufe ohne Meta-Datei werden nur
aus XDMF + Newton-Logfile fortgesetzt (Historie beginnt dann beim Resume).

ZUORDNUNG ALT -> NEU (seit 08.09.2026 partitionsunabhaengig):
dolfinx schreibt Geometrie, Topologie und Felder in seiner INTERNEN globalen
Nummerierung, und die haengt von der Netzpartitionierung ab. Die Partition
ist mit PT-SCOTCH NICHT reproduzierbar - derselbe Punkt mit demselben Netz
und derselben Rangzahl bekam in drei Laeufen drei verschiedene dofs-Zahlen,
und alle Restarts der Studie 015 scheiterten daran (CLAUDE.md §21). Deshalb
wird die alte Nummerierung nicht mehr vorausgesetzt, sondern rekonstruiert:
  * Knoten: jeder lokale Knoten des neuen Laufs wird ueber seine Koordinaten
    (exakte float64-Bitmuster, Fallback quantisiert auf 1e-7 mm) in der alten
    Geometrie-Ausgabe gesucht -> Zeilenindex im alten Datensatz.
  * Zellen: jede lokale Zelle wird ueber das sortierte Knoten-Tupel (in
    alten Zeilenindizes) in der alten Topologie gesucht.
Voraussetzung ist nur noch dasselbe Netz (dlfx_mesh.xdmf); Prozesszahl und
Partition duerfen abweichen. Kann ein Knoten oder eine Zelle nicht zugeordnet
werden (anderes Netz), bricht der Lauf mit RestartMismatchError ab.
"""

import glob
import json
import os
import re
import xml.etree.ElementTree as ET

import numpy as np
from mpi4py import MPI as _MPI

FORMAT_VERSION = 1


class RestartMismatchError(RuntimeError):
    """Partitionierung/Nummerierung passt nicht zur alten Ausgabe."""


# ---------------------------------------------------------------------------
# Pfade / kleine Helfer
# ---------------------------------------------------------------------------

def meta_path(script_path, base_name):
    return os.path.join(script_path, f"restart_meta_{base_name}.json")


def list_candidate_xdmfs(script_path, base_name):
    """Alle vorhandenen Ausgabedateien, neueste Restart-Generation zuerst."""
    cands = []
    for path in glob.glob(os.path.join(script_path, f"{base_name}_r*.xdmf")):
        m = re.search(r"_r(\d+)\.xdmf$", path)
        if m:
            cands.append((int(m.group(1)), path))
    cands.sort(reverse=True)
    ordered = [p for _, p in cands]
    base = os.path.join(script_path, f"{base_name}.xdmf")
    if os.path.isfile(base):
        ordered.append(base)
    return ordered


def next_output_xdmf(script_path, base_name):
    """Naechster freier Ausgabename (base_r1, base_r2, ...)."""
    used = [0]
    for path in glob.glob(os.path.join(script_path, f"{base_name}_r*.xdmf")):
        m = re.search(r"_r(\d+)\.xdmf$", path)
        if m:
            used.append(int(m.group(1)))
    return os.path.join(script_path, f"{base_name}_r{max(used) + 1}.xdmf")


def write_meta_atomic(script_path, base_name, payload):
    """Meta-Datei atomar schreiben (nur von Rang 0 aufrufen)."""
    path = meta_path(script_path, base_name)
    tmp = path + ".tmp"
    with open(tmp, "w") as handle:
        json.dump(payload, handle)
    os.replace(tmp, path)


def read_meta(script_path, base_name):
    path = meta_path(script_path, base_name)
    if not os.path.isfile(path):
        return None
    try:
        with open(path) as handle:
            meta = json.load(handle)
        if meta.get("format") != FORMAT_VERSION:
            return None
        return meta
    except (OSError, ValueError):
        return None


def dt_from_newton_logfile(logfile_path, t_state):
    """dt des Zeitschritts mit t == t_state aus dem Newton-Logfile.

    Fallback fuer alte Laeufe ohne Meta-Datei. Liefert None, wenn nichts
    Passendes gefunden wird.
    """
    if not os.path.isfile(logfile_path):
        return None
    best = None
    last = None
    try:
        with open(logfile_path) as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                try:
                    t_val, dt_val = float(parts[0]), float(parts[1])
                except ValueError:
                    continue
                last = (t_val, dt_val)
                if abs(t_val - t_state) <= 1e-12 * max(1.0, abs(t_state)):
                    best = dt_val
    except OSError:
        return None
    if best is not None:
        return best
    if last is not None and last[0] <= t_state + 1e-12:
        return last[1]
    return None


# ---------------------------------------------------------------------------
# XDMF-XML parsen (versionsunabhaengig ueber die DataItem-Pfade)
# ---------------------------------------------------------------------------

def _strip_ns(tag):
    return tag.split("}", 1)[-1]


def _dataitem_target(grid_dir, text):
    """'datei.h5:/pfad' -> (absoluter h5-Pfad, Datensatzpfad)."""
    text = (text or "").strip()
    if ":" not in text:
        return None
    h5file, dset = text.split(":", 1)
    if not os.path.isabs(h5file):
        h5file = os.path.join(grid_dir, h5file)
    return h5file, dset


def parse_xdmf(xdmf_path):
    """Zeitreihen und Netz-Datensaetze aus einer dolfinx-XDMF-Datei.

    Rueckgabe:
        {"functions": {name: [(t, h5file, dset), ...] aufsteigend},
         "geometry": (h5file, dset) oder None,
         "topology": (h5file, dset) oder None}
    """
    grid_dir = os.path.dirname(os.path.abspath(xdmf_path))
    tree = ET.parse(xdmf_path)
    result = {"functions": {}, "geometry": None, "topology": None}

    def walk(elem):
        for child in elem:
            tag = _strip_ns(child.tag)
            if tag == "Grid":
                time_value = None
                attrs = []
                for sub in child:
                    stag = _strip_ns(sub.tag)
                    if stag == "Time":
                        try:
                            time_value = float(sub.get("Value"))
                        except (TypeError, ValueError):
                            time_value = None
                    elif stag == "Geometry" and result["geometry"] is None:
                        for di in sub:
                            if _strip_ns(di.tag) == "DataItem":
                                result["geometry"] = _dataitem_target(grid_dir, di.text)
                    elif stag == "Topology" and result["topology"] is None:
                        for di in sub:
                            if _strip_ns(di.tag) == "DataItem":
                                result["topology"] = _dataitem_target(grid_dir, di.text)
                    elif stag == "Attribute":
                        name = sub.get("Name")
                        for di in sub:
                            if _strip_ns(di.tag) == "DataItem":
                                target = _dataitem_target(grid_dir, di.text)
                                if name and target:
                                    attrs.append((name, target))
                if time_value is not None:
                    for name, target in attrs:
                        result["functions"].setdefault(name, []).append(
                            (time_value, target[0], target[1]))
                walk(child)
            else:
                walk(child)

    walk(tree.getroot())
    for name in result["functions"]:
        result["functions"][name].sort(key=lambda item: item[0])
    return result


def common_times(functions, names, tol=1e-12):
    """Zeitpunkte, zu denen ALLE genannten Felder vorliegen (aufsteigend)."""
    if any(name not in functions for name in names):
        return []
    base = [t for t, _, _ in functions[names[0]]]
    out = []
    for t in base:
        ok = True
        for name in names[1:]:
            if not any(abs(t - t2) <= tol * max(1.0, abs(t)) for t2, _, _ in functions[name]):
                ok = False
                break
        if ok:
            out.append(t)
    return out


def _entry_for_time(entries, t, tol=1e-12):
    for t2, h5file, dset in entries:
        if abs(t2 - t) <= tol * max(1.0, abs(t)):
            return h5file, dset
    return None


# ---------------------------------------------------------------------------
# dolfinx-Zugriffe (API-Unterschiede 0.6/0.7 abfedern)
# ---------------------------------------------------------------------------

def _as_2d_dofmap(dofmap_like, ncells):
    arr = getattr(dofmap_like, "array", None)
    if arr is not None:
        arr = np.asarray(arr)
    else:
        arr = np.asarray(dofmap_like)
    if arr.ndim == 1:
        arr = arr.reshape(ncells, -1)
    return arr.astype(np.int64, copy=False)


def _geometry_index_map(domain):
    imap = domain.geometry.index_map
    return imap() if callable(imap) else imap


def _local_to_global(imap, n):
    idx = np.arange(n, dtype=np.int32)
    return np.asarray(imap.local_to_global(idx), dtype=np.int64)


def _read_rows(dset, global_indices, gap=65536):
    """Zeilen eines HDF5-Datensatzes zu (evtl. unsortierten) globalen Indizes.

    Liest zusammenhaengende Bereiche als Slabs (eigene Zeilen liegen als Block
    beieinander, Ghost-Zeilen bilden wenige weitere Blocks) - Punktselektionen
    ueber Millionen Indizes waeren in h5py unbrauchbar langsam.
    """
    uniq, inverse = np.unique(global_indices, return_inverse=True)
    if uniq.size == 0:
        return np.empty((0,) + dset.shape[1:], dtype=dset.dtype)
    data = np.empty((uniq.size,) + dset.shape[1:], dtype=dset.dtype)
    breaks = np.nonzero(np.diff(uniq) > gap)[0]
    starts = np.concatenate(([0], breaks + 1))
    ends = np.concatenate((breaks, [uniq.size - 1]))
    for s, e in zip(starts, ends):
        lo, hi = int(uniq[s]), int(uniq[e])
        slab = dset[lo:hi + 1]
        data[s:e + 1] = slab[uniq[s:e + 1] - lo]
    return data[inverse]


# ---------------------------------------------------------------------------
# Partitionsunabhaengige Zuordnung alt -> neu (08.09.2026)
# ---------------------------------------------------------------------------

def _coord_keys(xyz, quantum=None, shift=0.0):
    """(n, 3)-Koordinaten -> (n, 3)-int64-Schluessel fuer exakte Zeilenvergleiche.

    quantum=None: Bitmuster der float64-Werte (exakt; -0.0 wird vorher zu 0.0).
    quantum=q   : auf Vielfache von q gerundet, Gitter um shift*q versetzt
                  (Fallback, falls die Koordinaten nicht bitgleich sind).
    """
    xyz = np.ascontiguousarray(np.asarray(xyz, dtype=np.float64)[:, :3]) + 0.0
    if quantum is None:
        return xyz.view(np.int64)
    return np.round(xyz / float(quantum) + float(shift)).astype(np.int64)


def _match_rows(old_keys, new_keys):
    """Zeilenindex in old_keys fuer jede Zeile von new_keys (-1 = nicht gefunden).

    Beide Arrays (n, k) int64. Mehrdeutige alte Zeilen (Duplikate) liefern -1.
    Rein numpy (np.unique ueber Zeilen), O((n_old + n_new) log n).
    """
    old_keys = np.ascontiguousarray(old_keys, dtype=np.int64)
    new_keys = np.ascontiguousarray(new_keys, dtype=np.int64)
    n_old = old_keys.shape[0]
    if new_keys.shape[0] == 0:
        return np.empty(0, dtype=np.int64)
    if n_old == 0:
        return np.full(new_keys.shape[0], -1, dtype=np.int64)
    allk = np.concatenate([old_keys, new_keys], axis=0)
    _, inv = np.unique(allk, axis=0, return_inverse=True)
    inv = np.asarray(inv).reshape(-1)
    n_ids = int(inv.max()) + 1
    old_of_id = np.full(n_ids, -1, dtype=np.int64)
    old_ids = inv[:n_old]
    old_of_id[old_ids] = np.arange(n_old, dtype=np.int64)
    dup = np.bincount(old_ids, minlength=n_ids) > 1
    new_ids = inv[n_old:]
    result = old_of_id[new_ids]
    result[dup[new_ids]] = -1
    return result


def _old_index_maps(h5py, info, x_loc, gdm):
    """Zeilenindizes der alten Ausgabe fuer die lokalen Knoten und Zellen.

    x_loc: (nnodes_all, 3) lokale Knotenkoordinaten (eigene + Ghosts)
    gdm  : (ncells_all, nverts) lokale Zell-Knoten-Liste (lokale Knotenindizes)
    Rueckgabe: (node_old, cell_old, geo_all) mit
        node_old[i] = Zeile des lokalen Knotens i im alten Geometrie-Datensatz
        cell_old[c] = Zeile der lokalen Zelle c im alten Topologie-Datensatz
        geo_all     = alte Geometrie (n_old_nodes, 3) fuer Plausibilitaetscheck
    Wirft RestartMismatchError, wenn etwas nicht zugeordnet werden kann.
    """
    if info["geometry"] is None or info["topology"] is None:
        raise OSError("Kein Netz in der Ausgabedatei")
    gfile, gdset = info["geometry"]
    tfile, tdset = info["topology"]
    with h5py.File(gfile, "r") as h5:
        geo_all = np.asarray(h5[gdset][...], dtype=np.float64)
    if geo_all.ndim != 2 or geo_all.shape[1] < 3:
        raise RestartMismatchError(
            f"Alte Geometrie hat Form {geo_all.shape}, erwartet (n, 3).")
    geo_all = np.ascontiguousarray(geo_all[:, :3])

    node_old = _match_rows(_coord_keys(geo_all), _coord_keys(x_loc))
    if np.any(node_old < 0):
        # Fallback fuer nicht bitgleiche Koordinaten: quantisiert (1e-7 mm,
        # weit unter dem Knotenabstand) auf zwei um q/2 versetzten Gittern -
        # ein Punkt kann nicht auf beiden nahe einer Rundungsgrenze liegen.
        for shift in (0.0, 0.5):
            miss = np.nonzero(node_old < 0)[0]
            if miss.size == 0:
                break
            node_old[miss] = _match_rows(_coord_keys(geo_all, 1e-7, shift),
                                         _coord_keys(x_loc[miss], 1e-7, shift))
    missing = int(np.count_nonzero(node_old < 0))
    if missing:
        raise RestartMismatchError(
            f"{missing} von {node_old.size} lokalen Knoten sind in der alten "
            f"Ausgabe ({geo_all.shape[0]} Knoten) nicht enthalten - anderes "
            "Netz? Abbruch, um keine falschen Zustaende zu laden "
            "(Punkt mit YS_FORCE_FRESH=1 neu starten).")

    with h5py.File(tfile, "r") as h5:
        topo_all = np.asarray(h5[tdset][...], dtype=np.int64)
    if topo_all.ndim != 2 or topo_all.shape[1] != gdm.shape[1]:
        raise RestartMismatchError(
            f"Alte Topologie hat Form {topo_all.shape}, erwartet "
            f"(n, {gdm.shape[1]}) - anderer Zelltyp?")
    if topo_all.size and (topo_all.min() < 0 or topo_all.max() >= geo_all.shape[0]):
        raise RestartMismatchError("Alte Topologie verweist auf unbekannte Knoten.")
    conn_old = np.sort(node_old[gdm], axis=1)
    cell_old = _match_rows(np.sort(topo_all, axis=1), conn_old)
    missing = int(np.count_nonzero(cell_old < 0))
    if missing:
        raise RestartMismatchError(
            f"{missing} von {cell_old.size} lokalen Zellen sind in der alten "
            f"Topologie ({topo_all.shape[0]} Zellen) nicht enthalten - anderes "
            "Netz? Abbruch (Punkt mit YS_FORCE_FRESH=1 neu starten).")
    return node_old, cell_old, geo_all


# ---------------------------------------------------------------------------
# Kernfunktion: Zustand aus XDMF/HDF5 wiederherstellen
# ---------------------------------------------------------------------------

def try_restore(domain, comm, V, u_fun, alpha_n, e_p_funcs, mu_value,
                script_path, base_name, logfile_path):
    """Versucht, den letzten konsistenten Zustand zu laden.

    e_p_funcs: Liste [e_p_11_n, e_p_22_n, e_p_33_n, e_p_12_n, e_p_13_n, e_p_23_n]
    Rueckgabe: dict {t_state, dt_last, meta, source_xdmf, timestamp} oder None,
    wenn keine (lesbare) alte Ausgabe existiert.
    Wirft RestartMismatchError, wenn alte Ausgabe existiert, aber Knoten oder
    Zellen des aktuellen Netzes darin nicht gefunden werden (anderes Netz).
    """
    try:
        import h5py
    except ImportError as exc:
        raise RuntimeError(
            "Restart benoetigt h5py im Simulationscontainer "
            "(alex-dolfinx.sif). Bitte pruefen: apptainer exec <sif> "
            "python3 -c 'import h5py'") from exc

    rank = comm.Get_rank()

    meta = read_meta(script_path, base_name) if rank == 0 else None
    meta = comm.bcast(meta, root=0)

    candidates = list_candidate_xdmfs(script_path, base_name) if rank == 0 else None
    candidates = comm.bcast(candidates, root=0)
    if meta and meta.get("xdmf"):
        preferred = os.path.join(script_path, meta["xdmf"])
        if preferred in candidates:
            candidates = [preferred] + [c for c in candidates if c != preferred]
    if not candidates:
        return None

    # --- lokale Index-Strukturen (einmalig) -------------------------------
    tdim = domain.topology.dim
    cell_imap = domain.topology.index_map(tdim)
    ncells_all = cell_imap.size_local + cell_imap.num_ghosts
    cell_glob = _local_to_global(cell_imap, ncells_all)

    geom_imap = _geometry_index_map(domain)
    nnodes_all = geom_imap.size_local + geom_imap.num_ghosts
    node_glob = _local_to_global(geom_imap, nnodes_all)

    gdm = _as_2d_dofmap(domain.geometry.dofmap, ncells_all)
    x_loc = np.ascontiguousarray(
        np.asarray(domain.geometry.x)[:nnodes_all, :3], dtype=np.float64)

    bs = V.dofmap.index_map_bs
    dof_imap = V.dofmap.index_map
    ndofs_all = dof_imap.size_local + dof_imap.num_ghosts
    c2d = _as_2d_dofmap(V.dofmap.list, ncells_all)
    node_of_dof = np.full(ndofs_all, -1, dtype=np.int64)
    node_of_dof[c2d.reshape(-1)] = gdm.reshape(-1)

    # Konsistenzpruefung der P1-Dof-zu-Knoten-Zuordnung (kollektiv, damit bei
    # einem Fehler kein Rang in einem spaeteren allreduce haengen bleibt).
    map_ok = 1 if not np.any(node_of_dof < 0) else 0
    if map_ok:
        try:
            dof_coords = np.asarray(V.tabulate_dof_coordinates())[:ndofs_all, :3]
            node_coords = np.asarray(domain.geometry.x)[node_of_dof, :3]
            if not np.allclose(dof_coords, node_coords, rtol=0.0, atol=1e-10):
                map_ok = 0
        except AttributeError:
            pass  # aeltere dolfinx-Version ohne tabulate_dof_coordinates
    if comm.allreduce(map_ok, op=_MPI.MIN) == 0:
        raise RestartMismatchError(
            "P1-Dof-zu-Knoten-Zuordnung inkonsistent - Restart nicht moeglich "
            "(unerwartete Elementordnung?).")

    def qdof_of_cell(func):
        space = func.function_space
        arr = _as_2d_dofmap(space.dofmap.list, ncells_all)
        if arr.shape[1] != 1:
            raise RestartMismatchError(
                "Erwartet einen Quadraturpunkt je Zelle (deg_quad = 1).")
        return arr[:, 0]

    q_cells = qdof_of_cell(alpha_n)

    names = ["u", "sigma", "alpha"]

    for cand in candidates:
        info = None
        if rank == 0:
            try:
                info = parse_xdmf(cand)
            except Exception as exc:  # kaputtes XML nach Abbruch mitten im Schreiben
                print(f"[RESTART] {os.path.basename(cand)} nicht lesbar ({exc}), "
                      "versuche aeltere Ausgabe.")
                info = None
        info = comm.bcast(info, root=0)
        if info is None:
            continue
        functions = info["functions"]
        times = common_times(functions, names)
        if not times:
            continue

        # --- Zuordnung alt -> neu (partitionsunabhaengig, je Ausgabedatei) --
        # Fehler werden eingesammelt und kollektiv entschieden, damit kein
        # Rang in einem allreduce haengen bleibt.
        map_ok = 1
        map_msg = ""
        node_old = cell_old = geo_all = None
        try:
            node_old, cell_old, geo_all = _old_index_maps(h5py, info, x_loc, gdm)
        except RestartMismatchError as exc:
            map_ok = -1
            map_msg = str(exc)
        except Exception as exc:
            map_ok = 0
            map_msg = str(exc)
        map_state = comm.allreduce(map_ok, op=_MPI.MIN)
        if map_state == -1:
            raise RestartMismatchError(
                map_msg or "Netz der alten Ausgabe passt nicht zum aktuellen "
                "Netz (Details auf einem anderen Rang).")
        if map_state == 0:
            if rank == 0:
                print(f"[RESTART] {os.path.basename(cand)}: Netzdaten nicht "
                      f"lesbar ({map_msg}); versuche aeltere Ausgabe.")
            continue
        n_same = int(np.count_nonzero(node_old == node_glob))
        n_same = comm.allreduce(n_same, op=_MPI.SUM)
        n_tot = comm.allreduce(int(nnodes_all), op=_MPI.SUM)
        if rank == 0:
            print(f"[RESTART] Zuordnung alt->neu aus {os.path.basename(cand)}: "
                  f"{geo_all.shape[0]} alte Knoten; Partition reproduziert: "
                  f"{'ja' if n_same == n_tot else 'nein'} "
                  f"({n_same}/{n_tot} Knoten mit unveraenderter Nummer).")

        if meta is not None and os.path.join(script_path, meta.get("xdmf", "")) == cand:
            t_target = meta["t_state"]
            trial_times = [t for t in times
                           if abs(t - t_target) <= 1e-12 * max(1.0, abs(t_target))]
            # Sicherheitsnetz: Meta kann maximal einen Schritt hinterherhinken
            trial_times += [t for t in reversed(times) if t not in trial_times]
        else:
            trial_times = list(reversed(times))

        for t_state in trial_times:
            # ok_local: 1 = geladen, 0 = lesbar fehlgeschlagen (aelteren
            # Zeitschritt versuchen), -1 = Partitionierung passt nicht
            # (kollektiv abbrechen). Ausnahmen duerfen hier NICHT direkt
            # geworfen werden, sonst haengen die anderen Raenge im allreduce.
            ok_local = 1
            err_msg = ""
            mismatch_msg = ""
            try:
                u_entry = _entry_for_time(functions["u"], t_state)
                sig_entry = _entry_for_time(functions["sigma"], t_state)
                alp_entry = _entry_for_time(functions["alpha"], t_state)
                if not (u_entry and sig_entry and alp_entry):
                    raise OSError("Zeitschritt unvollstaendig")

                # Plausibilitaet: Koordinaten der zugeordneten alten Zeilen
                # muessen (bis auf Rundung) die lokalen Koordinaten sein.
                if not np.allclose(geo_all[node_old], x_loc[:, :geo_all.shape[1]],
                                   rtol=0.0, atol=1e-6):
                    raise RestartMismatchError(
                        "Zugeordnete Knotenkoordinaten weichen von den lokalen "
                        "ab - interner Fehler der Zuordnung.")

                with h5py.File(u_entry[0], "r") as h5:
                    # --- u (Zeilen = alte Knotennummern) -----------------
                    u_rows = _read_rows(h5[u_entry[1]], node_old[node_of_dof])
                    u_rows = np.asarray(u_rows, dtype=np.float64).reshape(ndofs_all, -1)
                    u_fun.x.array[:] = u_rows[:, :bs].reshape(-1)

                # sigma / alpha koennen in derselben oder einer anderen h5 liegen
                with h5py.File(sig_entry[0], "r") as h5s:
                    sig_rows = np.asarray(
                        _read_rows(h5s[sig_entry[1]], cell_old), dtype=np.float64)
                sig_rows = sig_rows.reshape(ncells_all, -1)
                if sig_rows.shape[1] != 9:
                    raise OSError(f"sigma-Datensatz hat Breite {sig_rows.shape[1]}, erwartet 9")

                with h5py.File(alp_entry[0], "r") as h5a:
                    alp_rows = np.asarray(
                        _read_rows(h5a[alp_entry[1]], cell_old), dtype=np.float64)
                alp_rows = alp_rows.reshape(ncells_all, -1)[:, 0]
            except RestartMismatchError as exc:
                ok_local = -1
                mismatch_msg = str(exc)
            except Exception as exc:
                ok_local = 0
                err_msg = str(exc)

            ok = comm.allreduce(ok_local, op=_MPI.MIN)
            if ok == -1:
                raise RestartMismatchError(
                    mismatch_msg or
                    "Alte Ausgabe passt nicht zum aktuellen Netz "
                    "(Details auf einem anderen Rang).")
            if ok == 0:
                if rank == 0:
                    print(f"[RESTART] t = {t_state:g} aus "
                          f"{os.path.basename(cand)} nicht lesbar ({err_msg}); "
                          "versuche aelteren Zeitschritt.")
                continue

            # --- e_p aus u und sigma rekonstruieren ------------------------
            eps_rows = _cellwise_eps(domain, u_fun, ncells_all)
            _assign_plastic_state(alpha_n, e_p_funcs, q_cells,
                                  eps_rows, sig_rows, alp_rows, mu_value)

            dt_last = None
            if meta is not None and abs(meta["t_state"] - t_state) <= \
                    1e-12 * max(1.0, abs(t_state)):
                dt_last = meta.get("dt_last")
                meta_used = meta
            else:
                meta_used = None
            if dt_last is None:
                dt_last = dt_from_newton_logfile(logfile_path, t_state) if rank == 0 else None
                dt_last = comm.bcast(dt_last, root=0)

            return {
                "t_state": float(t_state),
                "dt_last": dt_last,
                "meta": meta_used,
                "source_xdmf": cand,
                "timestamp": float(t_state),
            }

    return None


def _cellwise_eps(domain, u_fun, ncells_all):
    """eps(u) je Zelle als (ncells, 9)-Array (DP0-Interpolation, exakt fuer P1)."""
    import dolfinx as dlfx
    import ufl

    dim = domain.topology.dim
    TEN0 = dlfx.fem.functionspace(domain, ("DP", 0, (dim, dim)))
    expr = dlfx.fem.Expression(ufl.sym(ufl.grad(u_fun)),
                               TEN0.element.interpolation_points())
    tmp = dlfx.fem.Function(TEN0)
    tmp.interpolate(expr)
    tmp.x.scatter_forward()
    vals = np.asarray(tmp.x.array, dtype=np.float64).reshape(-1, dim * dim)
    tdof = _as_2d_dofmap(TEN0.dofmap.list, ncells_all)[:, 0]
    return vals[tdof]


def _assign_plastic_state(alpha_n, e_p_funcs, q_cells,
                          eps_rows, sig_rows, alp_rows, mu_value):
    """alpha und e_p an den Quadraturpunkten setzen.

    e_p = dev(eps) - dev(sigma) / (2 mu); Komponentenreihenfolge der Zeilen
    (3x3, C-Order): 11,12,13,21,22,23,31,32,33.
    """
    tr_eps = eps_rows[:, 0] + eps_rows[:, 4] + eps_rows[:, 8]
    tr_sig = sig_rows[:, 0] + sig_rows[:, 4] + sig_rows[:, 8]

    def dev(rows, tr, col):
        vals = rows[:, col].copy()
        if col in (0, 4, 8):
            vals -= tr / 3.0
        return vals

    two_mu = 2.0 * float(mu_value)
    comp_cols = {"11": 0, "22": 4, "33": 8, "12": 1, "13": 2, "23": 5}
    order = ["11", "22", "33", "12", "13", "23"]
    for func, comp in zip(e_p_funcs, order):
        col = comp_cols[comp]
        e_p_vals = dev(eps_rows, tr_eps, col) - dev(sig_rows, tr_sig, col) / two_mu
        func.x.array[q_cells] = e_p_vals

    alpha_n.x.array[q_cells] = alp_rows
