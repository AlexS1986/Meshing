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

# ---------------------------
# Utilities
# ---------------------------
import numpy as np


import numpy as np

def map_triangle_centers_to_data(triangle_centers: np.ndarray,
                                 cell_data: np.ndarray,
                                 dtype=float) -> np.ndarray:
    """
    Assign data from a regular grid of 1x1 cells to triangle mesh cells.

    Parameters
    ----------
    triangle_centers : (N_tri, 2) float ndarray
        X and Y coordinates of triangle cell centers.
    cell_data : (Nx, Ny) ndarray
        Data values for each 1x1 quadratic cell.
    dtype : data-type, optional
        Output dtype (default: float).

    Returns
    -------
    tri_values : (N_tri,) ndarray
        Assigned data value for each triangle cell, cast to dtype.
    """
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
    for index, row in connectivity_df.iterrows():
        cell_id = row['Cell ID']
        row_idx = index // mesh_dims[1]
        col_idx = index % mesh_dims[1]
        cell_grid[row_idx, col_idx] = cell_id
    return cell_grid

def map_density_to_grid(cell_id_grid, cell_data_df):
    density_grid = np.full(cell_id_grid.shape, np.nan)
    densities = cell_data_df['density'].values
    for row in range(cell_id_grid.shape[0]):
        for col in range(cell_id_grid.shape[1]):
            cell_id = cell_id_grid[row, col]
            if cell_id < len(densities):
                density_grid[row, col] = densities[cell_id]
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
def process_folder(folder_path, threshold_value=0.5, only_x=None):
    script_path = os.getcwd()

    # Paths for shared files
    node_file = os.path.join(folder_path, 'node_coord.csv')
    connectivity_file = os.path.join(folder_path, 'connectivity.csv')

    # Load shared data
    nodes_df = load_node_data(node_file)
    connectivity_df = load_cell_connectivity(connectivity_file)
    mesh_dims = infer_mesh_dimensions_from_nodes(nodes_df)
    cell_id_grid = arrange_cells_2D(connectivity_df, mesh_dims)
    element_size = calculate_element_size(nodes_df)

    print(f"Element size: {element_size:.4f} units")
    print("Node coordinate bounds:", get_min_max_coords_from_df(nodes_df))

    # Find all matching cell_data_x.csv files
    cell_data_files = sorted(
        [f for f in os.listdir(folder_path) if re.match(r'cell_data_\d+\.csv$', f)],
        key=lambda x: int(re.findall(r'\d+', x)[0])
    )

    for cell_data_file in cell_data_files:
        x_val = int(re.findall(r'\d+', cell_data_file)[0])
        if only_x is not None and x_val != only_x:
            continue

        print(f"\nProcessing {cell_data_file} (x={x_val})...")

        # Load cell data
        cell_data_df = load_cell_data(os.path.join(folder_path, cell_data_file))

        # Create density grids
        density_grid = map_density_to_grid(cell_id_grid, cell_data_df)
        segmented_density_grid = segment_density(density_grid, threshold_value)
        segmented_density_grid_3d = add_third_dimension_to_segmented_grid(segmented_density_grid)

        # Save segmentation plot
        plt.figure(figsize=(10, 8))
        plt.imshow(segmented_density_grid_3d[:, :, 0], cmap='viridis', interpolation='nearest')
        plt.colorbar(label='Density')
        plt.title(f'Density Distribution (x={x_val})')
        plt.savefig(os.path.join(folder_path, f'segmented_density_distribution_{x_val}.png'), dpi=300)
        plt.close()

        # Mesh generation
        density_grid_3d = add_third_dimension_to_segmented_grid(density_grid)
        # vol = nanomesh.Image(density_grid_3d)
        vol = nanomesh.Image(density_grid_3d)
        plane = vol.select_plane(x=0)
        plane_gauss = plane #plane.gaussian(sigma=1)
        thresh = threshold_value
        #thresh = plane_gauss.threshold('li')
        print(thresh)
        plane_gauss_segmented = plane_gauss.digitize(bins=[thresh])
        mesher = nanomesh.Mesher2D(plane_gauss_segmented)
        #mesher.generate_contour(max_edge_dist=10, level=thresh, precision = 1, group_regions=True)
        mesher.generate_contour(max_edge_dist= 1, level=thresh, precision = 1, group_regions=False)
        mesh = mesher.triangulate(opts='q30a0.5')
        
        # mesh.number_to_field
        # mesh.set_field_data('triangle', {1: 'Material', 2: 'Void'})
        
        triangle_mesh = mesh.get('triangle')
        # triangle_mesh.number_to_field
        
        #mid_points_triangle_mesh = triangle_mesh.cell_centers
        
        # triangle_cell_data = map_triangle_centers_to_data(mid_points_triangle_mesh,segmented_density_grid)
        # triangle_mesh.cell_data["physical"] = triangle_cell_data
        
        # triangle_mesh.set_field_data('triangle', {1: 'Material', 2: 'Void'})
        #meshio_mesh = triangle_mesh.to_meshio()

        # Save mesh
        output_mesh_path = os.path.join(folder_path, f"mesh_{x_val}.xdmf")
        triangle_mesh.write(output_mesh_path,file_format='xdmf')
        print(f"Mesh saved: {output_mesh_path}")
        output_mesh_path = os.path.join(folder_path, f"out_{x_val}.msh")
        triangle_mesh.write(output_mesh_path, file_format='gmsh', binary=False)
        print(f"Mesh saved: {output_mesh_path}")

# ---------------------------
# Entry Point
# ---------------------------
if __name__ == "__main__":
    default_folder = '/data/resources/2D_structure_Hannover/310125_var_bcpos_rho_10_120_004/'
    folder_path = default_folder
    only_x = None

    if len(sys.argv) > 1:
        if os.path.isdir(sys.argv[1]):
            folder_path = sys.argv[1]
            if len(sys.argv) > 2:
                try:
                    only_x = int(sys.argv[2])
                except ValueError:
                    sys.exit(f"Invalid x_value: {sys.argv[2]}")
        else:
            # If first argument is not a folder, try to interpret as only_x
            try:
                only_x = int(sys.argv[1])
            except ValueError:
                sys.exit(f"Invalid folder path or x_value: {sys.argv[1]}")

    # At this point only_x=None means "process all"
    process_folder(folder_path, threshold_value=0.5, only_x=only_x)


