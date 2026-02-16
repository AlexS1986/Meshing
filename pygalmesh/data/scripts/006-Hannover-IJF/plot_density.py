import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.tri import Triangulation
import numpy as np


def plot_density(folder, x, source="cell"):
    # File paths
    node_file = os.path.join(folder, f"node_coords_{x}.csv")
    conn_file = os.path.join(folder, f"connectivity_{x}.csv")
    cell_file = os.path.join(folder, f"cell_data_{x}.csv")
    point_file = os.path.join(folder, f"points_data_{x}.csv")

    # Read nodes and connectivity
    nodes = pd.read_csv(node_file)
    conn = pd.read_csv(conn_file)

    X = nodes["Points_0"].values
    Y = nodes["Points_1"].values

    quads = conn[["Point Index 0", "Point Index 1", "Point Index 2", "Point Index 3"]].values
    triangles = []
    for q in quads:
        triangles.append([q[0], q[1], q[2]])
        triangles.append([q[0], q[2], q[3]])
    triangles = np.array(triangles)

    # Density source: cell or point
    if source == "cell":
        cell_data = pd.read_csv(cell_file)
        density = cell_data["density"].values
        density_tri = []
        for d in density:
            density_tri.extend([d, d])
        density_tri = np.array(density_tri)
        triang = Triangulation(X, Y, triangles)
        plot_data = (triang, density_tri, "flat")

    elif source == "point":
        point_data = pd.read_csv(point_file)
        density = point_data.set_index("Point ID")["density"].reindex(range(len(X))).values
        triang = Triangulation(X, Y, triangles)
        plot_data = (triang, density, "gouraud")

    else:
        raise ValueError("source must be 'cell' or 'point'")

    # Plot
    plt.figure(figsize=(8, 6))
    triang, values, shading = plot_data
    tpc = plt.tripcolor(triang, values, shading=shading, cmap="viridis")
    plt.colorbar(tpc, label="Density")
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.title(f"Density field (x={x}, source={source})")
    plt.axis("equal")

    # Save figure in script’s directory
    out_file = os.path.join(os.path.dirname(__file__), f"density_contour_{x}_{source}.png")
    plt.savefig(out_file, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved contour plot to {out_file}")


if __name__ == "__main__":
    folder = "/data/resources/2D_structure_Hannover/newBCs/250925_TTO_mbb_festlager_var_a_E_var_min_max/mbb_festlager_var_a_E_min"
    x = 3
    source = "point"
    plot_density(folder, x, source)

# if __name__ == "__main__":
#     # if len(sys.argv) != 3:
#     #     print("Usage: python script.py <folder> <x>")
#     #     sys.exit(1)
#     folder = "/data/resources/2D_structure_Hannover/newBCs/250925_TTO_mbb_festlager_var_a_E_var_min_max/mbb_festlager_var_a_E_min"
#     x = 3
#     import numpy as np  # needed for array operations
#     plot_density(folder, x)
