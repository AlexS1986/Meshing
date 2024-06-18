import numpy as np
import meshio
from scipy.spatial import cKDTree

import numpy as np
import meshio
import os

import utils.alex.process_meshes as mmm 

script_path = os.path.dirname(__file__)
input_mesh_path = os.path.join(script_path,"foam128_corrected_to_box.xdmf")
# input_mesh_path = os.path.join(script_path,"foam128.xdmf")
output_mesh_path = os.path.join(script_path,"coarse_pores.xdmf")

merging_tolerance = 1.0e-2

# read pygal output mesh
original_mesh = meshio.read(input_mesh_path)

mirror_plane_values =  np.max(original_mesh.points,axis=0)
mirror_dir_index = 2

mirrored_merged_vertices,  mirrored_merged_cells = mmm.mirror_and_merge(
    original_mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
    merging_tolerance=merging_tolerance)

# Create a new mesh object from vertices and cells
mirrored_mesh = meshio.Mesh(mirrored_merged_vertices, {"tetra": mirrored_merged_cells})

# translate to xmin = 0
minimum_coordinates_new_mesh =  np.min(mirrored_mesh.points,axis=0)
translate_to_zero = np.array([0,0,0])
translate_to_zero[mirror_dir_index] = -minimum_coordinates_new_mesh[mirror_dir_index]
mesh = mmm.translate_mesh(mirrored_mesh,translate_to_zero)
mirror_plane_values =  np.min(mesh.points,axis=0)

# Save the merged mesh
meshio.write(output_mesh_path, mesh)


