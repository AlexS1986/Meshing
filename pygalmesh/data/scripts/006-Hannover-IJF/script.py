import numpy as np
import pandas as pd
import os
import matplotlib.pyplot as plt
import pygalmesh
import nanomesh
import meshio
import sys
import re

# ---------------------------
# Loaders
# ---------------------------
def load_node_data(file_path):
    return pd.read_csv(file_path)

def load_cell_connectivity(file_path):
    return pd.read_csv(file_path)

def load_cell_data(file_path):
    return pd.read_csv(file_path)

def load_point_data(file_path):
    return pd.read_csv(file_path)

# ---------------------------
# Utilities
# ---------------------------
def map_triangle_centers_to_data(triangle_centers: np.ndarray,
                                 cell_data: np.ndarray,
                                 dtype=float) -> np.ndarray:
    Nx, Ny = cell_data.shape
    ix = np.floor(triangle_centers[:, 0]).astype(int)
    iy = np.floor(triangle_centers[:, 1]).astype(int)
    ix = np.clip(ix, 0, Nx - 1)
    iy = np.clip(iy, 0, Ny - 1)
    return cell_data[ix, iy].astype(dtype)

def infer_mesh_dimensions_from_nodes(nodes_df):
    unique_y_coords = np.sort(nodes_df['Points_1'].unique())
    unique_x_coords = np.sort(nodes_df['Points_0'].unique())
    num_rows = len(unique_y_coords) - 1
    num_cols = len(unique_x_coords) - 1
    return num_rows, num_cols

def get_min_max_coords_from_df(nodes_df):
    return {
        'min_x': nodes_df['Points_0'].min(),
        'max_x': nodes_df['Points_0'].max(),
        'min_y': nodes_df['Points_1'].min(),
        'max_y': nodes_df['Points_1'].max()
    }

def arrange_cells_2D(connectivity_df, mesh_dims):
    cell_grid = np.zeros(mesh_dims, dtype=int)
    iterrows = connectivity_df.iterrows()
    for index, row in iterrows:
        cell_id = index  # row['Cell ID']
        row_idx = index // mesh_dims[1]
        col_idx = index % mesh_dims[1]
        cell_grid[row_idx, col_idx] = cell_id
    return cell_grid

def map_density_to_grid_from_cells(cell_id_grid, cell_data_df):
    density_grid = np.full(cell_id_grid.shape, np.nan)
    densities = cell_data_df['density'].values
    for row in range(cell_id_grid.shape[0]):
        for col in range(cell_id_grid.shape[1]):
            cell_id = cell_id_grid[row, col]
            if cell_id < len(densities):
                density_grid[row, col] = densities[cell_id]
    return density_grid

def map_density_to_grid_from_points(nodes_df, mesh_dims, point_data_df):
    density_grid = np.full(mesh_dims, np.nan)
    x_coords = np.sort(nodes_df['Points_0'].unique())
    y_coords = np.sort(nodes_df['Points_1'].unique())
    node_density = point_data_df.set_index('Point ID')['density']

    for i in range(mesh_dims[0]):
        for j in range(mesh_dims[1]):
            # bottom-left node of the cell
            x = x_coords[j]
            y = y_coords[i]
            node_id = nodes_df[(nodes_df['Points_0'] == x) & (nodes_df['Points_1'] == y)]['Point ID'].values
            if len(node_id) > 0 and node_id[0] in node_density:
                density_grid[i, j] = node_density[node_id[0]]

    return density_grid

def segment_density(density_grid, threshold):
    segmented_grid = np.zeros_like(density_grid, dtype=np.uint8)
    segmented_grid[density_grid >= threshold] = 1
    return segmented_grid

def add_third_dimension_to_segmented_grid(segmented_density_grid):
    return np.expand_dims(segmented_density_grid, axis=2)

def calculate_element_size(nodes_df):
    x1, y1 = nodes_df.iloc[0]['Points_0'], nodes_df.iloc[0]['Points_1']
    x2, y2 = nodes_df.iloc[1]['Points_0'], nodes_df.iloc[1]['Points_1']
    return np.sqrt((x2 - x1)**2 + (y2 - y1)**2)

# ---------------------------
# Main Processing
# ---------------------------
def process_folder(folder_path, threshold_value=0.5, only_x=None, layout="cols", density_source="point"):
    print("\n[INFO] Starting process in folder:", folder_path)

    cell_data_files = sorted(
        [f for f in os.listdir(folder_path) if re.match(r'cell_data_\d+\.csv$', f)],
        key=lambda x: int(re.findall(r'\d+', x)[0])
    )

    print(f"[INFO] Found {len(cell_data_files)} cell_data files to process.")
    aggregated_results = []

    for idx, cell_data_file in enumerate(cell_data_files, 1):
        x_val = int(re.findall(r'\d+', cell_data_file)[0])
        if only_x is not None and x_val != only_x:
            continue

        print(f"\n[STEP {idx}/{len(cell_data_files)}] Processing {cell_data_file} (BC position x={x_val})...")

        # --- Load corresponding node and connectivity files ---
        node_file = os.path.join(folder_path, f'node_coords_{x_val}.csv')
        connectivity_file = os.path.join(folder_path, f'connectivity_{x_val}.csv')

        if not os.path.isfile(node_file) or not os.path.isfile(connectivity_file):
            print(f"  [WARNING] Missing node/connectivity files for x={x_val}, skipping.")
            continue

        print("  - Loading node and connectivity data...")
        nodes_df = load_node_data(node_file)
        connectivity_df = load_cell_connectivity(connectivity_file)
        mesh_dims = infer_mesh_dimensions_from_nodes(nodes_df)
        cell_id_grid = arrange_cells_2D(connectivity_df, mesh_dims)
        element_size = calculate_element_size(nodes_df)
        coord_bounds = get_min_max_coords_from_df(nodes_df)

        print(f"    Element size: {element_size:.4f} units")
        print("    Node coordinate bounds:", coord_bounds)

        # --- Load density ---
        if density_source == "point":
            point_file = os.path.join(folder_path, f'points_data_{x_val}.csv')
            if not os.path.isfile(point_file):
                print(f"  [WARNING] Missing points_data file for x={x_val}, falling back to cell_data.")
                density_source = "cell"
            else:
                print("  - Mapping density to grid from points_data...")
                point_data_df = load_point_data(point_file)
                density_grid = map_density_to_grid_from_points(nodes_df, mesh_dims, point_data_df)
        if density_source == "cell":
            cell_data_df = load_cell_data(os.path.join(folder_path, cell_data_file))
            print("  - Mapping density to grid from cell_data...")
            density_grid = map_density_to_grid_from_cells(cell_id_grid, cell_data_df)

        segmented_density_grid = segment_density(density_grid, threshold_value)
        segmented_density_grid_3d = add_third_dimension_to_segmented_grid(segmented_density_grid)

        print("  - Saving individual density plot...")
        plt.figure(figsize=(20, 2))
        im = plt.imshow(segmented_density_grid_3d[:, :, 0], cmap='viridis', interpolation='nearest',
                        origin='lower',
                        extent=[coord_bounds['min_x'], coord_bounds['max_x'],
                                coord_bounds['min_y'], coord_bounds['max_y']])
        cbar = plt.colorbar(im)
        cbar.set_label('Density', fontsize=16)
        cbar.ax.tick_params(labelsize=16)
        plt.title(f'Density Distribution (BC position x={x_val})', fontsize=16)
        plt.xticks(fontsize=16)
        plt.yticks(fontsize=16)
        plt.xlabel("X [units]", fontsize=16)
        plt.ylabel("Y [units]", fontsize=16)
        plt.savefig(os.path.join(folder_path, f'segmented_density_distribution_{x_val}.png'), dpi=300, bbox_inches='tight')
        plt.close()

        aggregated_results.append((x_val, segmented_density_grid_3d[:, :, 0], coord_bounds))

        print("  - Generating mesh...")
        density_grid_3d = add_third_dimension_to_segmented_grid(density_grid)
        vol = nanomesh.Image(density_grid_3d)
        plane = vol.select_plane(x=0)
        plane_gauss = plane
        thresh = threshold_value
        plane_gauss_segmented = plane_gauss.digitize(bins=[thresh])
        mesher = nanomesh.Mesher2D(plane_gauss_segmented)
        mesher.generate_contour(level=thresh, group_regions=False)
        mesh = mesher.triangulate(opts='q30a0.5')

        triangle_mesh = mesh.get('triangle')

        output_mesh_path = os.path.join(folder_path, f"mesh_{x_val}.xdmf")
        triangle_mesh.write(output_mesh_path, file_format='xdmf')
        print(f"  - Mesh saved: {output_mesh_path}")
        # output_mesh_path = os.path.join(folder_path, f"out_{x_val}.msh")
        # triangle_mesh.write(output_mesh_path, file_format='gmsh', binary=False)
        # print(f"  - Mesh saved: {output_mesh_path}")

    # ---------------------------
    # Aggregate Plot in Grid
    # ---------------------------
    if aggregated_results:
        print("\n[INFO] Creating aggregated density distribution plot...")
        n = len(aggregated_results)

        if layout == "cols":
            ncols = 3
            nrows = int(np.ceil(n / ncols))
        elif layout == "rows":
            nrows = 3
            ncols = int(np.ceil(n / nrows))
        else:
            raise ValueError("layout must be either 'cols' or 'rows'")

        fig, axes = plt.subplots(nrows, ncols, figsize=(20, 2 * nrows), sharex=True, sharey=True)
        axes = axes.flatten()

        for ax, (x_val, seg_grid, coord_bounds) in zip(axes, aggregated_results):
            im = ax.imshow(seg_grid, cmap='viridis', interpolation='nearest',
                           origin='lower',
                           extent=[coord_bounds['min_x'], coord_bounds['max_x'],
                                   coord_bounds['min_y'], coord_bounds['max_y']])
            ax.set_title(f"BC position x={x_val}", fontsize=16)
            ax.tick_params(axis='both', labelsize=16)

        for ax in axes[len(aggregated_results):]:
            ax.axis('off')

        fig.subplots_adjust(wspace=0.05, hspace=0.15)
        cbar = fig.colorbar(im, ax=axes, orientation='vertical', fraction=0.02, pad=0.02)
        cbar.set_label("Density", fontsize=16)
        cbar.ax.tick_params(labelsize=16)
        fig.suptitle("Aggregated Segmented Density Distributions", fontsize=16)
        aggregated_path = os.path.join(folder_path, 'aggregated_density_distribution.png')
        plt.savefig(aggregated_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"[INFO] Aggregated plot saved: {aggregated_path}")

    print("\n[INFO] Processing complete.")

# ---------------------------
# Entry Point
# ---------------------------
if __name__ == "__main__":
    #default_folder = '/data/resources/2D_structure_Hannover/newBCs/250925_TTO_mbb_festlager_var_a_E_var_min_max/mbb_var_a_E_max'
    default_folder = '/data/resources/2D_structure_Hannover/February2026/dcb_var_bcpos_E_var/export'
    folder_path = default_folder
    only_x = None
    layout = "cols"  # default to 3 columns layout
    density_source = "point"  # default

    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
        if not os.path.isdir(folder_path):
            sys.exit(f"Invalid folder path: {folder_path}")

        if len(sys.argv) > 2:
            arg2 = sys.argv[2]
            if arg2 in ["cols", "rows"]:
                layout = arg2
            elif arg2 in ["cell", "point"]:
                density_source = arg2
            else:
                try:
                    only_x = int(arg2)
                except ValueError:
                    sys.exit(f"Invalid second argument: {arg2}")

        if len(sys.argv) > 3:
            arg3 = sys.argv[3]
            if arg3 in ["cols", "rows"]:
                layout = arg3
            elif arg3 in ["cell", "point"]:
                density_source = arg3
            else:
                sys.exit(f"Invalid third argument: {arg3}")

    process_folder(folder_path, threshold_value=0.5, only_x=only_x, layout=layout, density_source=density_source)

