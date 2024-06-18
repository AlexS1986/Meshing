import numpy as np
import meshio
from scipy.spatial import cKDTree

import numpy as np
import meshio
import os

import utils.alex.process_meshes as mmm 

script_path = os.path.dirname(__file__)
input_mesh_path = os.path.join(script_path,"foam128.xdmf")
output_mesh_path = os.path.join(script_path,"foam128_corrected_to_box.xdmf")


voxel_num_x = 128
voxel_num_y = voxel_num_x
voxel_num_z = voxel_num_x

voxel_size_x = 1.0e-2
voxel_size_y = voxel_size_x
voxel_size_z = voxel_size_x



# xmin = 0.0
# xmax = voxel_num_x * voxel_size_x
# ymin = 0.0
# ymax = voxel_num_y * voxel_size_y
# zmin = 0.0
# zmax = voxel_num_z * voxel_size_z

max_element_size = 2.0e-2

# read pygal output mesh
original_mesh = meshio.read(input_mesh_path)
points = original_mesh.points

tolerance = 0.9*max_element_size

# Get the minimum values in each column
min_values_before = np.min(points, axis=0)
# Get the maximum values in each column
max_values_before = np.max(points, axis=0)

xmin = min_values_before[0]
xmax = max_values_before[0]
ymin = min_values_before[1]
ymax = max_values_before[1]
zmin = min_values_before[2]
zmax = max_values_before[2]





points = mmm.correct_mesh_to_box(points,xmin,xmax,ymin,ymax,zmin,zmax,tolerance=tolerance)

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


