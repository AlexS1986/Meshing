import numpy as np
import pandas as pd
import os
import matplotlib.pyplot as plt
import pygalmesh
import nanomesh
import meshio
import sys
import re

DEFAULT_BASE_FOLDER_RELATIVE = os.path.join(
    "data",
    "resources",
    "2D_structure_Hannover",
    "260504_dcb_beta_phi_a_rho_var_min_max",
)
DEFAULT_BASE_FOLDER_ABSOLUTE = os.path.join(os.sep, DEFAULT_BASE_FOLDER_RELATIVE)

def resolve_default_base_folder():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))
    workspace_default = os.path.join(repo_root, DEFAULT_BASE_FOLDER_RELATIVE)

    if os.path.isdir(workspace_default):
        return workspace_default
    return DEFAULT_BASE_FOLDER_ABSOLUTE

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

def get_dataset_cases(folder_path):
    numbered_cell_data_files = sorted(
        [f for f in os.listdir(folder_path) if re.match(r'cell_data_\d+\.csv$', f)],
        key=lambda x: int(re.findall(r'\d+', x)[0])
    )

    if numbered_cell_data_files:
        dataset_cases = []
        for cell_data_file in numbered_cell_data_files:
            x_val = int(re.findall(r'\d+', cell_data_file)[0])
            dataset_cases.append(
                {
                    "label": x_val,
                    "cell_data": os.path.join(folder_path, cell_data_file),
                    "node": os.path.join(folder_path, f"node_coords_{x_val}.csv"),
                    "connectivity": os.path.join(folder_path, f"connectivity_{x_val}.csv"),
                    "point": os.path.join(folder_path, f"points_data_{x_val}.csv"),
                    "output_suffix": str(x_val),
                }
            )
        return dataset_cases

    cell_data_file = os.path.join(folder_path, "cell_data.csv")
    if os.path.isfile(cell_data_file):
        return [
            {
                "label": os.path.basename(folder_path),
                "cell_data": cell_data_file,
                "node": os.path.join(folder_path, "node_coords.csv"),
                "connectivity": os.path.join(folder_path, "connectivity.csv"),
                "point": os.path.join(folder_path, "points_data.csv"),
                "output_suffix": None,
            }
        ]

    return []

def find_dataset_folders(base_path):
    dataset_folders = []
    for root, dirs, files in os.walk(base_path):
        if "cell_data.csv" in files or any(re.match(r'cell_data_\d+\.csv$', f) for f in files):
            dataset_folders.append(root)
            dirs[:] = []
    return sorted(dataset_folders)

def find_vtu_leaf_folders(base_path):
    vtu_folders = []
    for root, dirs, files in os.walk(base_path):
        vtu_files = sorted(f for f in files if f.lower().endswith(".vtu"))
        if vtu_files:
            vtu_folders.append((root, vtu_files))
            dirs[:] = []
    return sorted(vtu_folders)

def choose_vtu_for_folder(folder_path, vtu_files):
    if len(vtu_files) == 1:
        return vtu_files[0]

    folder_name = os.path.basename(folder_path)
    folder_named_vtu = f"{folder_name}.vtu"
    if folder_named_vtu in vtu_files:
        return folder_named_vtu

    raise ValueError(
        f"Expected one VTU file in {folder_path}, found {len(vtu_files)}: {', '.join(vtu_files)}"
    )

def get_density_from_vtu(mesh):
    if "density" not in mesh.cell_data:
        raise ValueError("VTU file does not contain cell_data named 'density'.")

    for cell_block, density_block in zip(mesh.cells, mesh.cell_data["density"]):
        if cell_block.type in ["quad", "triangle"]:
            return cell_block, np.asarray(density_block).reshape(-1)

    raise ValueError("VTU file does not contain quad or triangle cells with density data.")

def map_vtu_density_to_grid(mesh, cell_block, density_values):
    if cell_block.type == "quad" and len(cell_block.data) > 0:
        first_cell = cell_block.data[0]
        node_count_per_row = int(first_cell[3] - first_cell[0])
        num_cols = node_count_per_row - 1
        if num_cols > 0 and len(density_values) % num_cols == 0:
            num_rows = len(density_values) // num_cols
            return density_values.reshape((num_rows, num_cols))

    points_2d = mesh.points[:, :2]
    centers = points_2d[cell_block.data].mean(axis=1)

    x_edges = np.sort(np.unique(points_2d[:, 0]))
    y_edges = np.sort(np.unique(points_2d[:, 1]))
    if len(x_edges) < 2 or len(y_edges) < 2:
        raise ValueError("Cannot infer a 2D grid from the VTU points.")

    num_cols = len(x_edges) - 1
    num_rows = len(y_edges) - 1
    density_grid = np.full((num_rows, num_cols), np.nan)

    col_idx = np.searchsorted(x_edges, centers[:, 0], side="right") - 1
    row_idx = np.searchsorted(y_edges, centers[:, 1], side="right") - 1
    col_idx = np.clip(col_idx, 0, num_cols - 1)
    row_idx = np.clip(row_idx, 0, num_rows - 1)
    density_grid[row_idx, col_idx] = density_values

    if np.isnan(density_grid).any():
        missing_count = int(np.isnan(density_grid).sum())
        raise ValueError(f"Could not map {missing_count} VTU cells into the density grid.")

    return density_grid

def generate_physical_mesh_from_density_grid(density_grid, threshold_value):
    density_grid_3d = add_third_dimension_to_segmented_grid(density_grid)
    vol = nanomesh.Image(density_grid_3d)
    plane = vol.select_plane(x=0)
    plane_segmented = plane.digitize(bins=[threshold_value])
    mesher = nanomesh.Mesher2D(plane_segmented)
    mesher.generate_contour(level=threshold_value, group_regions=False)
    mesh = mesher.triangulate(opts='q30a0.5')
    return mesh.get('triangle')

def write_mesh_xdmf_from_vtu(folder_path, vtu_files):
    vtu_file = choose_vtu_for_folder(folder_path, vtu_files)
    input_vtu_path = os.path.join(folder_path, vtu_file)
    output_mesh_path = os.path.join(folder_path, "mesh.xdmf")

    print(f"  - Building physical mesh from VTU density: {input_vtu_path}")
    vtu_mesh = meshio.read(input_vtu_path)
    cell_block, density_values = get_density_from_vtu(vtu_mesh)
    density_grid = map_vtu_density_to_grid(vtu_mesh, cell_block, density_values)
    triangle_mesh = generate_physical_mesh_from_density_grid(density_grid, threshold_value=0.5)
    triangle_mesh.write(output_mesh_path, file_format="xdmf")
    print(f"  - Mesh saved: {output_mesh_path}")

def process_vtu_leaf_folders(base_path):
    print(f"[INFO] Processing VTU leaf folders in: {base_path}")
    vtu_folders = find_vtu_leaf_folders(base_path)
    print(f"[INFO] Found {len(vtu_folders)} VTU leaf folders to process.")

    for folder_path, vtu_files in vtu_folders:
        print(f"\n[INFO] Processing VTU leaf folder: {folder_path}")
        write_mesh_xdmf_from_vtu(folder_path, vtu_files)

    return len(vtu_folders)

# ---------------------------
# Main Processing
# ---------------------------
def process_folder(folder_path, threshold_value=0.5, only_x=None, layout="cols", density_source="point"):
    print("\n[INFO] Starting process in folder:", folder_path)

    dataset_cases = get_dataset_cases(folder_path)

    print(f"[INFO] Found {len(dataset_cases)} cell_data files to process.")
    aggregated_results = []

    for idx, dataset_case in enumerate(dataset_cases, 1):
        label = dataset_case["label"]
        if only_x is not None and label != only_x:
            continue

        print(f"\n[STEP {idx}/{len(dataset_cases)}] Processing {os.path.basename(dataset_case['cell_data'])} ({label})...")

        # --- Load corresponding node and connectivity files ---
        node_file = dataset_case["node"]
        connectivity_file = dataset_case["connectivity"]

        if not os.path.isfile(node_file) or not os.path.isfile(connectivity_file):
            print(f"  [WARNING] Missing node/connectivity files for {label}, skipping.")
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
        current_density_source = density_source
        if current_density_source == "point":
            point_file = dataset_case["point"]
            if not os.path.isfile(point_file):
                print(f"  [WARNING] Missing points_data file for {label}, falling back to cell_data.")
                current_density_source = "cell"
            else:
                print("  - Mapping density to grid from points_data...")
                point_data_df = load_point_data(point_file)
                density_grid = map_density_to_grid_from_points(nodes_df, mesh_dims, point_data_df)
        if current_density_source == "cell":
            cell_data_df = load_cell_data(dataset_case["cell_data"])
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
        plt.title(f'Density Distribution ({label})', fontsize=16)
        plt.xticks(fontsize=16)
        plt.yticks(fontsize=16)
        plt.xlabel("X [units]", fontsize=16)
        plt.ylabel("Y [units]", fontsize=16)
        density_plot_name = "segmented_density_distribution.png"
        if dataset_case["output_suffix"] is not None:
            density_plot_name = f"segmented_density_distribution_{dataset_case['output_suffix']}.png"
        plt.savefig(os.path.join(folder_path, density_plot_name), dpi=300, bbox_inches='tight')
        plt.close()

        aggregated_results.append((label, segmented_density_grid_3d[:, :, 0], coord_bounds))

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

        mesh_name = "mesh.xdmf"
        if dataset_case["output_suffix"] is not None:
            mesh_name = f"mesh_{dataset_case['output_suffix']}.xdmf"
        output_mesh_path = os.path.join(folder_path, mesh_name)
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
        axes = np.atleast_1d(axes).flatten()

        for ax, (label, seg_grid, coord_bounds) in zip(axes, aggregated_results):
            im = ax.imshow(seg_grid, cmap='viridis', interpolation='nearest',
                           origin='lower',
                           extent=[coord_bounds['min_x'], coord_bounds['max_x'],
                                   coord_bounds['min_y'], coord_bounds['max_y']])
            ax.set_title(str(label), fontsize=16)
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

def process_subfolders(base_path, threshold_value=0.5, only_x=None, layout="cols", density_source="point"):
    print(f"[INFO] Processing subfolders in: {base_path}")
    if process_vtu_leaf_folders(base_path):
        return

    dataset_folders = find_dataset_folders(base_path)
    print(f"[INFO] Found {len(dataset_folders)} dataset folders to process.")
    for dataset_folder in dataset_folders:
        print(f"\n[INFO] Processing dataset folder: {dataset_folder}")
        process_folder(dataset_folder, threshold_value, only_x, layout, density_source)

# ---------------------------
# Entry Point
# ---------------------------
if __name__ == "__main__":
    base_path = resolve_default_base_folder()
    only_x = None
    layout = "cols"  # default to 3 columns layout
    density_source = "point"  # default

    if len(sys.argv) > 1:
        base_path = sys.argv[1]
        if not os.path.isdir(base_path):
            sys.exit(f"Invalid base folder path: {base_path}")

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

    if not os.path.isdir(base_path):
        sys.exit(f"Invalid base folder path: {base_path}")

    process_subfolders(base_path, threshold_value=0.5, only_x=only_x, layout=layout, density_source=density_source)
