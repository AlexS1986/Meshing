import numpy as np
import meshio
from scipy.spatial import cKDTree

import numpy as np
import meshio
import os

import utils.alex.mirror_merge_meshes as mmm 

script_path = os.path.dirname(__file__)
input_mesh_path = os.path.join(script_path,"foam128.xdmf")
output_mesh_path = os.path.join(script_path,"foam128_corrected_to_box.xdmf")


voxel_num_x = 128
voxel_num_y = voxel_num_x
voxel_num_z = voxel_num_x

voxel_size_x = 1.0e-2
voxel_size_y = voxel_size_x
voxel_size_z = voxel_size_x

xmin = 0.0
xmax = voxel_num_x * voxel_size_x
ymin = 0.0
ymax = voxel_num_y * voxel_size_y
zmin = 0.0
zmax = voxel_num_z * voxel_size_z


# read pygal output mesh
original_mesh = meshio.read(input_mesh_path)
points = original_mesh.points

# Get the minimum values in each column
min_values_before = np.min(points, axis=0)
# Get the maximum values in each column
max_values_before = np.max(points, axis=0)

def correct_values(arr, xmin, xmax, ymin, ymax, zmin, zmax, tolerance):
    # Correct first column (x values)
    arr[:, 0] = np.where(np.abs(arr[:, 0] - xmin) <= tolerance, xmin, arr[:, 0])
    arr[:, 0] = np.where(np.abs(arr[:, 0] - xmax) <= tolerance, xmax, arr[:, 0])
    
    # Correct second column (y values)
    arr[:, 1] = np.where(np.abs(arr[:, 1] - ymin) <= tolerance, ymin, arr[:, 1])
    arr[:, 1] = np.where(np.abs(arr[:, 1] - ymax) <= tolerance, ymax, arr[:, 1])
    
    # Correct third column (z values)
    arr[:, 2] = np.where(np.abs(arr[:, 2] - zmin) <= tolerance, zmin, arr[:, 2])
    arr[:, 2] = np.where(np.abs(arr[:, 2] - zmax) <= tolerance, zmax, arr[:, 2])
    
    return arr

points = correct_values(points,xmin,xmax,ymin,ymax,zmin,zmax,tolerance=0.9*3.0*voxel_size_x)

# Get the minimum values in each column
min_values_after = np.min(points, axis=0)
# Get the maximum values in each column
max_values_after = np.max(points, axis=0)

# mirrored_merged_vertices, mirrored_merged_faces, mirrored_merged_cells = mmm.mirror_and_merge(
#     original_mesh, mirror_direction = [-1, 1, 1], merging_tolerance=3.0e-2)

tetra_cells = original_mesh.cells[1].data
# Create a new mesh object from vertices and cells
corrected_mesh = meshio.Mesh(points, {"tetra": tetra_cells})

# Save the merged mesh
meshio.write(output_mesh_path,corrected_mesh)


