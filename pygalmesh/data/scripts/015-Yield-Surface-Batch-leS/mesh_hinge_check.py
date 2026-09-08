"""mesh_hinge_check.py - Flaechen- vs. knotenbasierte Zusammenhangskomponenten eines
Tet-Netzes (dlfx_mesh.h5 oder Snapshot-h5 von dolfinx).

Teile, die mit dem Rest nur Kanten oder Knoten teilen ("Scharniere"), erscheinen
als eigene flaechenbasierte Komponente, obwohl knotenbasiert alles EINE
Komponente ist. Solche Teile haben Starrkoerpermoden (Rotation um Kante/Knoten);
MUMPS faktorisiert trotzdem (Pivot rundungsklein, nicht null), die Loesung
enthaelt dort aber Unsinn (|u| bis 1e11 mm beobachtet, JM-25-71 ys_000) und das
Newton-Residuum erreicht die Toleranz nicht mehr. Befund 08.09.2026, CLAUDE.md §22.
Der Konverter make_mesh_dlfx_compatible_cluster.py entfernt sie seit 08.09.2026.

Aufruf (Container, braucht h5py + scipy):
  apptainer exec $HOME/dolfinx_alex/alex-dolfinx.sif python3 mesh_hinge_check.py <pfad>/dlfx_mesh.h5
Erwartung nach dem Filter: "flaechenbasiert 1 Komponente(n)".
"""
import sys, time
import numpy as np
import h5py


def find(h5, name):
    out = []
    h5.visititems(lambda n, o: out.append(n) if isinstance(o, h5py.Dataset) and n.split("/")[-1] == name else None)
    if not out:
        raise KeyError(f"Datensatz '{name}' nicht gefunden")
    return h5[out[0]][...]


def components(n, a, b):
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    m = coo_matrix((np.ones(len(a), dtype=np.int8), (a, b)), shape=(n, n))
    return connected_components(m, directed=False)[1]


def main(path):
    t0 = time.time()
    with h5py.File(path, "r") as h5:
        T = find(h5, "topology").astype(np.int64)
        X = find(h5, "geometry")
    nc, nv = T.shape[0], X.shape[0]
    # knotenbasiert (Referenz): Knoten-Zell-Graph
    lab_v = components(nc + nv, np.repeat(np.arange(nc), T.shape[1]), nc + T.reshape(-1))
    n_vert = len(np.unique(lab_v[:nc]))
    # flaechenbasiert: gleiche (sortierte) Dreiecksflaeche = Nachbarn
    F = np.sort(np.stack([T[:, [1, 2, 3]], T[:, [0, 2, 3]], T[:, [0, 1, 3]], T[:, [0, 1, 2]]], axis=1)
                .reshape(-1, 3), axis=1)
    cell_of = np.repeat(np.arange(nc), 4)
    order = np.lexsort((F[:, 2], F[:, 1], F[:, 0]))
    Fs, cs = F[order], cell_of[order]
    same = np.all(Fs[1:] == Fs[:-1], axis=1)
    lab = components(nc, cs[:-1][same], cs[1:][same])
    ids, sizes = np.unique(lab, return_counts=True)
    order = np.argsort(-sizes)
    big = sizes[order[0]]
    print(f"{path}: {nc} Tets, {nv} Knoten | knotenbasiert {n_vert} Komponente(n) | "
          f"flaechenbasiert {len(ids)} Komponente(n), groesste {big} ({big / nc:.4%}), "
          f"Rest {nc - big} Tets in {len(ids) - 1} Teilen  [{time.time() - t0:.0f} s]")
    for k in order[1:11]:
        cells = np.nonzero(lab == ids[k])[0]
        pts = X[np.unique(T[cells])]
        print(f"    Teil mit {sizes[k]:6d} Tets  Box x=[{pts[:, 0].min():.2f},{pts[:, 0].max():.2f}] "
              f"y=[{pts[:, 1].min():.2f},{pts[:, 1].max():.2f}] z=[{pts[:, 2].min():.2f},{pts[:, 2].max():.2f}]")
    if len(ids) > 1:
        rest = sizes[order[1:]]
        print(f"    Groessenverteilung der Nebenteile: <=10 Tets: {np.sum(rest <= 10)}, "
              f"11-100: {np.sum((rest > 10) & (rest <= 100))}, >100: {np.sum(rest > 100)}")
    return len(ids)


if __name__ == "__main__":
    n = 0
    for p in sys.argv[1:]:
        n = max(n, main(p))
    sys.exit(0 if n <= 1 else 1)
