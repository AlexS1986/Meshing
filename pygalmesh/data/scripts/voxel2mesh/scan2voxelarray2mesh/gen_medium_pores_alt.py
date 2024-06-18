import numpy as np
import meshio
from scipy.spatial import cKDTree

import numpy as np
import meshio
import os

import utils.alex.process_meshes as mmm 

max_element_size = 2.0e-2

script_path = os.path.dirname(__file__)
input_mesh_path = os.path.join(script_path,"foam128_corrected_to_box.xdmf")
merging_tolerance = 0.5*max_element_size

# input_mesh_path = os.path.join(script_path,"foam128.xdmf")
# merging_tolerance = 0.86*max_element_size

output_mesh_path = os.path.join(script_path,"medium_pores.xdmf")


# merging_tolerance = 0.72*max_element_size


# read pygal output mesh
original_mesh = meshio.read(input_mesh_path)

mirror_plane_values =  np.min(original_mesh.points,axis=0)
mirror_dir_index = 0

mirrored_merged_vertices,  mirrored_merged_cells = mmm.mirror_and_merge(
    original_mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
    merging_tolerance=merging_tolerance)

# Create a new mesh object from vertices and cells
mesh = meshio.Mesh(mirrored_merged_vertices, {"tetra": mirrored_merged_cells})

# translate to origin
minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
translate_to_zero = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
mesh = mmm.translate_mesh(mesh,translate_to_zero)


# 2. mirror in y-direction
mirror_plane_values =  np.min(mesh.points,axis=0)
mirror_dir_index = 1

mirrored_merged_vertices,  mirrored_merged_cells = mmm.mirror_and_merge(
    mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
    merging_tolerance=merging_tolerance)

# Create a new mesh object from vertices and cells
mesh = meshio.Mesh(mirrored_merged_vertices, {"tetra": mirrored_merged_cells})

# translate to origin
minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
translate_to_zero = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
mesh = mmm.translate_mesh(mesh,translate_to_zero)


# 3. mirror in z-direction
mirror_plane_values =  np.min(mesh.points,axis=0)
mirror_dir_index = 2

mirrored_merged_vertices,  mirrored_merged_cells = mmm.mirror_and_merge(
    mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
    merging_tolerance=merging_tolerance)

# Create a new mesh object from vertices and cells
mesh = meshio.Mesh(mirrored_merged_vertices, {"tetra": mirrored_merged_cells})

# translate to origin
minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
translate_to_zero = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
# translate_to_zero[mirror_dir_index] = -minimum_coordinates_new_mesh[mirror_dir_index]
mesh = mmm.translate_mesh(mesh,translate_to_zero)
# mirror_plane_values =  np.min(mesh.points,axis=0)


# 4. mirror in x-direction again
mirror_plane_values =  np.min(mesh.points,axis=0)
mirror_dir_index = 0

mirrored_merged_vertices,  mirrored_merged_cells = mmm.mirror_and_merge(
    mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
    merging_tolerance=merging_tolerance)

# Create a new mesh object from vertices and cells
mesh = meshio.Mesh(mirrored_merged_vertices, {"tetra": mirrored_merged_cells})

# translate to origin
minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
translate_to_zero = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
# translate_to_zero[mirror_dir_index] = -minimum_coordinates_new_mesh[mirror_dir_index]
mesh = mmm.translate_mesh(mesh,translate_to_zero)



# Save the merged mesh
meshio.write(output_mesh_path, mesh)





