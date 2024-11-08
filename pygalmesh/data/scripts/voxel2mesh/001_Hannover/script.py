import numpy as np
import pandas as pd
import os
import matplotlib.pyplot as plt
import pygalmesh
import nanomesh
import meshio

# File path
folder_path = '/data/resources/2D_structure_Hannover/'
voxel_number = 128
script_path = os.path.dirname(__file__)

# Load node data
def load_node_data(file_path):
    nodes_df = pd.read_csv(file_path)
    return nodes_df

# Load cell connectivity data
def load_cell_connectivity(file_path):
    connectivity_df = pd.read_csv(file_path)
    return connectivity_df

# Load cell data (e.g., material properties)
def load_cell_data(file_path):
    cell_data_df = pd.read_csv(file_path)
    return cell_data_df

def infer_mesh_dimensions_from_nodes(nodes_df):
    unique_y_coords = nodes_df['Points_1'].unique()
    unique_x_coords = nodes_df['Points_0'].unique()

    # Sort unique coordinates in ascending order
    unique_y_coords.sort()
    unique_x_coords.sort()

    # Calculate mesh dimensions (cells = nodes - 1 along each dimension)
    num_rows = len(unique_y_coords) - 1  # Number of cells along the y dimension
    num_cols = len(unique_x_coords) - 1  # Number of cells along the x dimension
    return num_rows, num_cols


# def arrange_cells_2D(connectivity_df, mesh_dims):
#     cell_grid = np.zeros(mesh_dims, dtype=int)  # 2D array to store cell IDs

#     # Fill the cell_grid row by row based on Cell ID order in the file
#     for index, row in connectivity_df.iterrows():
#         cell_id = row['Cell ID']
        
#         # Adjust row index to reverse the y-axis
#         row_idx = (mesh_dims[0] - 1) - (index // mesh_dims[1])
#         col_idx = index % mesh_dims[1]
        
#         cell_grid[row_idx, col_idx] = cell_id

#     return cell_grid

# Create 2D array of cell IDs based on inferred mesh dimensions
def arrange_cells_2D(connectivity_df, mesh_dims):
    cell_grid = np.zeros(mesh_dims, dtype=int)  # 2D array to store cell IDs

    # Fill the cell_grid row by row based on Cell ID order in the file
    for index, row in connectivity_df.iterrows():
        cell_id = row['Cell ID']
        row_idx = index // mesh_dims[1]
        col_idx = index % mesh_dims[1]
        cell_grid[row_idx, col_idx] = cell_id

    return cell_grid



# Create a 2D array for density values based on cell_id_grid
def map_density_to_grid(cell_id_grid, cell_data_df):
    # Create an empty array for densities with the same shape as cell_id_grid
    density_grid = np.full(cell_id_grid.shape, np.nan)  # Using NaN for any missing values

    # Access density column from cell_data_df
    densities = cell_data_df['density'].values

    # Populate the density grid based on cell_id_grid
    for row in range(cell_id_grid.shape[0]):
        for col in range(cell_id_grid.shape[1]):
            cell_id = cell_id_grid[row, col]
            if cell_id < len(densities):
                density_grid[row, col] = densities[cell_id]
            else:
                density_grid[row, col] = np.nan  # Handle cases where cell_id exceeds density data

    return density_grid

# Segment the density grid based on a threshold
def segment_density(density_grid, threshold):
    # Create a new grid with 0s and 1s based on the threshold
    segmented_grid = np.zeros_like(density_grid,dtype=np.uint8)  # Initialize with 0s
    
    # Set cells to 1 if their density is >= threshold
    segmented_grid[density_grid >= threshold] = 1
    
    return segmented_grid

# Add a third dimension to the segmented density grid with a layer size of 1
def add_third_dimension_to_segmented_grid(segmented_density_grid):
    # Add a third dimension (axis 2) with size 1
    return np.expand_dims(segmented_density_grid, axis=2)


# Calculate the size of each square element (distance between adjacent nodes)
def calculate_element_size(nodes_df):
    # Get the x and y coordinates of the first two nodes (assuming they are adjacent)
    x1, y1 = nodes_df.iloc[0]['Points_0'], nodes_df.iloc[0]['Points_1']
    x2, y2 = nodes_df.iloc[1]['Points_0'], nodes_df.iloc[1]['Points_1']
    
    # Compute the Euclidean distance between the two nodes
    distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    return distance



# Paths to the text files
node_file = folder_path + 'node_coord.csv'
connectivity_file = folder_path + 'connectivity.csv'
cell_data_file = folder_path + 'cell_data.csv'

# Load data
nodes_df = load_node_data(node_file)
connectivity_df = load_cell_connectivity(connectivity_file)
cell_data_df = load_cell_data(cell_data_file)

# Infer mesh dimensions
mesh_dims = infer_mesh_dimensions_from_nodes(nodes_df)

# Arrange cell IDs in a 2D array
cell_id_grid = arrange_cells_2D(connectivity_df, mesh_dims)

# Map density values to a second grid
density_grid = map_density_to_grid(cell_id_grid, cell_data_df)

# Define a threshold value for segmentation
threshold_value = 0.5  # Example threshold value, you can adjust this as needed

# Create a segmented grid based on the threshold
segmented_density_grid = segment_density(density_grid, threshold_value)
segmented_density_grid = add_third_dimension_to_segmented_grid(segmented_density_grid)

# Calculate the size of each square element
element_size = calculate_element_size(nodes_df)

# Output the element size
print(f"The size of each square element (distance between adjacent nodes) is: {element_size:.4f} units.")


# Plot the density distribution
plt.figure(figsize=(10, 8))
plt.imshow(segmented_density_grid, cmap='viridis', interpolation='nearest')
plt.colorbar(label='Density')
plt.title('Density Distribution')

# Save the plot to a PNG file
output_image_path = script_path + 'segmented_density_distribution.png'
plt.savefig(output_image_path, dpi=300)


#https://nanomesh.readthedocs.io/en/latest/examples/nanopores_generate_a_2d_triangular_mesh.html

density_grid = add_third_dimension_to_segmented_grid(density_grid)
vol = nanomesh.Image(density_grid)


plane = vol.select_plane(x=0)
plane_gauss = plane.gaussian(sigma=1)


mesher = nanomesh.Mesher2D(plane_gauss)
# thresh = plane_gauss.threshold('isodata')
thresh = 0.95
segmented = plane_gauss.digitize(bins=[thresh])
mesher.generate_contour(max_edge_dist=5,level=thresh)
mesh = mesher.triangulate(opts='q30a0.5')

#mesh.plot_pyvista(jupyter_backend='static', show_edges=True)

triangle_mesh = mesh.get('triangle')
pv_mesh = triangle_mesh.to_pyvista_unstructured_grid()
#trimesh_mesh = triangle_mesh.to_trimesh()
meshio_mesh = triangle_mesh.to_meshio()
mesh.write('mesh.xdmf')
mesh.write('out.msh', file_format='gmsh22', binary=False)

#plane_gauss.compare_with_mesh(mesh)

a = 1
# voxel_size = (element_size, element_size, element_size)
# mesh = pygalmesh.generate_from_array(
#     segmented_density_grid, voxel_size, max_cell_circumradius=1.0*element_size, #max_facet_distance=0.1*voxel_dim
# )

# mesh.write(os.path.join(script_path,"structure" + str(voxel_number) + ".vtk"))

# # Output the result
# print("2D Array of Cell IDs:")
# print(cell_id_grid)
