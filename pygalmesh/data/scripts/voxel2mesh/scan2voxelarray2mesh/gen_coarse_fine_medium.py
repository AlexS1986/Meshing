import numpy as np
import meshio

import numpy as np
import meshio
import os

from scipy.spatial import KDTree

import utils.alex.process_meshes as mmm 

max_element_size = 3.0e-2

script_path = os.path.dirname(__file__)
input_mesh_path = os.path.join(script_path,"foam128_corrected_to_box.xdmf")
# input_mesh_path = os.path.join(script_path,"foam128.xdmf")
merging_tolerance = 0.019*max_element_size


output_mesh_path_coarse = os.path.join(script_path,"coarse_pores.xdmf")
output_mesh_path_medium = os.path.join(script_path,"medium_pores.xdmf")
output_mesh_path_fine = os.path.join(script_path,"fine_pores.xdmf")


# read pygal output mesh
mesh = meshio.read(input_mesh_path)

tolerance_for_points_to_be_considered_identical = 0.019*max_element_size  # tolerance within which points are considered identical
##### check mesh
pairs, has_pairs = mmm.check_for_identical_points(mesh,tolerance_for_points_to_be_considered_identical)
# mmm.print_points(mesh, pairs)
missing_points, any_missing = mmm.check_all_points_referenced(mesh) # missing is not bad
incorrect_orientation_cells, any_incorrect_orientation, zero_volume_cells, any_zero_volume = mmm.check_cell_orientation(mesh,tolerance=0.001*max_element_size**3) # zero volume or incorrect orientation breaks the mesh!
mmm.print_mesh_status(missing_points, any_missing, incorrect_orientation_cells, any_incorrect_orientation, zero_volume_cells, any_zero_volume)
# correct_mesh
mesh = mmm.remove_invalid_cells(mesh,incorrect_orientation_cells,zero_volume_cells)

# remove points that are not referenced by a cell
# def remove_points_at_indices(mesh, point_indices_to_remove):
#     points_filtered, offset = mmm.remove_vertices_and_compute_offset_2(mesh.points,missing_points)
#     points, cells = mmm.get_points_and_cells_from_mesh(mesh)
#     cells_with_applied_offset = mmm.apply_offset_to_cells(cells,offset,indices_of_removed_points=missing_points)
#     mesh = meshio.Mesh(points=points_filtered, cells={"tetra": cells_with_applied_offset})
#     return mesh

# mesh = remove_points_at_indices(mesh, missing_points)


# missing_points, any_missing = mmm.check_all_points_referenced(mesh) # missing is not bad
# incorrect_orientation_cells, any_incorrect_orientation, zero_volume_cells, any_zero_volume = mmm.check_cell_orientation(mesh,tolerance=0.001*max_element_size**3) # zero volume or incorrect orientation breaks the mesh!
# mmm.print_mesh_status(missing_points, any_missing, incorrect_orientation_cells, any_incorrect_orientation, zero_volume_cells, any_zero_volume)


mirror_plane_values =  np.min(mesh.points,axis=0)
mirror_dir_index = 0

# mirrored_merged_vertices,  mirrored_merged_cells = mmm.mirror_and_merge_old(
#     mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
#     merging_tolerance=merging_tolerance)

# # Create a new mesh object from vertices and cells
# mesh = meshio.Mesh(mirrored_merged_vertices, {"tetra": mirrored_merged_cells})

# 1. mirror in x-direction
# mesh = mmm.mirror_and_merge_old(
#     mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
#     merging_tolerance=merging_tolerance)

mesh = mmm.mirror_and_merge_old(mesh,mirror_direction=0,merging_tolerance=merging_tolerance,
                                mirror_plane_value=mirror_plane_values[mirror_dir_index])

pairs, has_pairs = mmm.check_for_identical_points(mesh,tolerance_for_points_to_be_considered_identical)

# translate to origin
minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
translate_to_origin = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
mesh = mmm.translate_mesh(mesh,translate_to_origin)

meshio.write(output_mesh_path_coarse, mesh)

################
# MEDIUM     ###
################

# pairs, has_pairs = mmm.check_for_identical_points(mesh,tolerance_for_points_to_be_considered_identical)


# 2. mirror in z-direction
mirror_plane_values =  np.min(mesh.points,axis=0)
mirror_dir_index = 2

# mirrored_merged_vertices,  mirrored_merged_cells = mmm.mirror_and_merge_old(
#     mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
#     merging_tolerance=merging_tolerance)

# # Create a new mesh object from vertices and cells
# mesh = meshio.Mesh(mirrored_merged_vertices, {"tetra": mirrored_merged_cells})

mesh = mmm.mirror_and_merge_old(
    mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
    merging_tolerance=merging_tolerance)

# translate to origin
minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
translate_to_origin = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
# translate_to_zero[mirror_dir_index] = -minimum_coordinates_new_mesh[mirror_dir_index]
mesh = mmm.translate_mesh(mesh,translate_to_origin)
# mirror_plane_values =  np.min(mesh.points,axis=0)

# 3. mirror in x-direction again
mirror_plane_values =  np.min(mesh.points,axis=0)
mirror_dir_index = 0

# mirrored_merged_vertices,  mirrored_merged_cells = mmm.mirror_and_merge_old(
#     mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
#     merging_tolerance=merging_tolerance)

# # Create a new mesh object from vertices and cells
# mesh = meshio.Mesh(mirrored_merged_vertices, {"tetra": mirrored_merged_cells})

mesh = mmm.mirror_and_merge_old(
    mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
    merging_tolerance=merging_tolerance)

# translate to origin
minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
translate_to_origin = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
# translate_to_zero[mirror_dir_index] = -minimum_coordinates_new_mesh[mirror_dir_index]
mesh = mmm.translate_mesh(mesh,translate_to_origin)
mesh_copy = mmm.copy_mesh(mesh)


# 4 mirror in y-direction min
mirror_plane_values =  np.min(mesh.points,axis=0)
mirror_dir_index = 1

# mirrored_merged_vertices,  mirrored_merged_cells = mmm.mirror_and_merge_old(
#     mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
#     merging_tolerance=merging_tolerance)

# # Create a new mesh object from vertices and cells
# mesh = meshio.Mesh(mirrored_merged_vertices, {"tetra": mirrored_merged_cells})

mesh= mmm.mirror_and_merge_old(
    mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
    merging_tolerance=merging_tolerance)

# translate to origin
minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
translate_to_origin = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
mesh = mmm.translate_mesh(mesh,translate_to_origin)


# # 5. mirror previous mesh
# mirror_plane_values =  np.max(mesh_copy.points,axis=0)
# mirror_dir_index = 1

# # mirrored_merged_vertices,  mirrored_merged_cells = mmm.mirror_and_merge_old(
# #     mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
# #     merging_tolerance=merging_tolerance)

# # # Create a new mesh object from vertices and cells
# # mesh = meshio.Mesh(mirrored_merged_vertices, {"tetra": mirrored_merged_cells})

# mesh_copy= mmm.mirror_mesh(mesh_copy,mirror_dir_index,mirror_plane_value=mirror_plane_values[mirror_dir_index])

# # 6. merge 
# # align both meshes for merge at plane y = 0
# minimum_coordinates_new_mesh =  np.min(mesh_copy.points,axis=0)
# translate_to_origin = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
# mesh_copy = mmm.translate_mesh(mesh_copy,translate_to_origin)


# maximum_coordinates_new_mesh =  np.max(mesh.points,axis=0)
# translate_to_origin = np.array([0,-maximum_coordinates_new_mesh[1],0])
# mesh = mmm.translate_mesh(mesh,translate_to_origin)


# # merge both meshes at y = 0
# mesh = mmm.merge_mesh(mesh,mesh_copy,1,merging_tolerance=merging_tolerance,merge_plane_value=0.0)





# # translate to origin
# minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
# translate_to_origin = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
# mesh = mmm.translate_mesh(mesh,translate_to_origin)



mesh = mmm.scale_mesh(mesh,scal=1.0/2.0)

# Save the merged mesh
meshio.write(output_mesh_path_medium, mesh)


################
# FINE     #####
################

# 1. mirror in z-direction
mirror_plane_values =  np.min(mesh.points,axis=0)
mirror_dir_index = 2

mesh = mmm.mirror_and_merge_old(
    mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
    merging_tolerance=merging_tolerance)

# translate to origin
minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
translate_to_origin = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
mesh = mmm.translate_mesh(mesh,translate_to_origin)


# 2. mirror in y-direction
mirror_plane_values =  np.min(mesh.points,axis=0)
mirror_dir_index = 1

mesh = mmm.mirror_and_merge_old(
    mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
    merging_tolerance=merging_tolerance)

# translate to origin
minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
translate_to_origin = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
mesh = mmm.translate_mesh(mesh,translate_to_origin)


# 3. mirror in x-direction
mirror_plane_values =  np.min(mesh.points,axis=0)
mirror_dir_index = 0

mesh = mmm.mirror_and_merge_old(
    mesh, mirror_direction =  mirror_dir_index, mirror_plane_value=mirror_plane_values[mirror_dir_index], 
    merging_tolerance=merging_tolerance)

# translate to origin
minimum_coordinates_new_mesh =  np.min(mesh.points,axis=0)
translate_to_origin = np.array([-minimum_coordinates_new_mesh[0],-minimum_coordinates_new_mesh[1],-minimum_coordinates_new_mesh[2]])
mesh = mmm.translate_mesh(mesh,translate_to_origin)


mesh = mmm.scale_mesh(mesh,scal=1.0/2.0)

# Save the merged mesh
meshio.write(output_mesh_path_fine, mesh)





