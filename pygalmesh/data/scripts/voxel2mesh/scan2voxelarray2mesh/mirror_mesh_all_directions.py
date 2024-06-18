import numpy as np
import meshio
from scipy.spatial import cKDTree

import numpy as np
import meshio
import os

import utils.alex.mirror_merge_meshes as mmm 

script_path = os.path.dirname(__file__)
input_mesh_path = os.path.join(script_path,"foam128_corrected_to_box.xdmf")
output_mesh_path = os.path.join(script_path,"mirrored_hypo_test_128.xdmf")


# 1. Mirror at xmin
# read pygal output mesh
input_mesh_path = os.path.join(script_path,"foam128_corrected_to_box.xdmf")
output_mesh_path = os.path.join(script_path,"tmp.xdmf")
original_mesh = meshio.read(input_mesh_path)

max_coordinates =  np.max(original_mesh.points,axis=0)
mirror_dir_index = 0

mirrored_merged_vertices,  mirrored_merged_cells = mmm.mirror_and_merge(
    original_mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=0.0, merging_tolerance=3.0e-2)

# Create a new mesh object from vertices and cells
merged_mesh = meshio.Mesh(mirrored_merged_vertices, {"tetra": mirrored_merged_cells})

# Save the merged mesh
meshio.write(output_mesh_path, merged_mesh)


# 2. Mirror at ymin
# read pygal output mesh
input_mesh_path = os.path.join(script_path,"tmp.xdmf")
output_mesh_path = os.path.join(script_path,"tmp.xdmf")
original_mesh = meshio.read(input_mesh_path)

max_coordinates =  np.max(original_mesh.points,axis=0)
mirror_dir_index = 1

mirrored_merged_vertices,  mirrored_merged_cells = mmm.mirror_and_merge(
    original_mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=0.0, merging_tolerance=3.0e-2)

# Create a new mesh object from vertices and cells
merged_mesh = meshio.Mesh(mirrored_merged_vertices, {"tetra": mirrored_merged_cells})

# Save the merged mesh
meshio.write(output_mesh_path, merged_mesh)

# 2. Mirror at zmin
# read pygal output mesh
input_mesh_path = os.path.join(script_path,"tmp.xdmf")
output_mesh_path = os.path.join(script_path,"hypo_128_mirrored_all_directions.xdmf")
original_mesh = meshio.read(input_mesh_path)

max_coordinates =  np.max(original_mesh.points,axis=0)
mirror_dir_index = 2

mirrored_merged_vertices,  mirrored_merged_cells = mmm.mirror_and_merge(
    original_mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=0.0, merging_tolerance=3.0e-2)

# Create a new mesh object from vertices and cells
merged_mesh = meshio.Mesh(mirrored_merged_vertices, {"tetra": mirrored_merged_cells})

# Save the merged mesh
meshio.write(output_mesh_path, merged_mesh)


